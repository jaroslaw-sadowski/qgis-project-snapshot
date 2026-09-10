"""Bounded host scheduling and real requests to four loopback WMS servers."""

import json
import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Condition, Event, Lock
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import test_raster_archive as fixtures
from qgis.core import QgsDataSourceUri, QgsRasterLayer

from mbtiles_batch_exporter.adaptive import HostPolicy
from mbtiles_batch_exporter.parallel_archive import RasterWorkers


class HostQueueTests(unittest.TestCase):
    def run_queue(self, adaptive):
        """Hold the first four jobs: later jobs cannot hide a bad first choice."""
        with TemporaryDirectory() as temporary:
            queue = RasterWorkers.__new__(RasterWorkers)
            queue.stop = Event()
            queue.condition = Condition()
            queue.adaptive = adaptive
            queue.memory_ok = True
            queue.workers = 4
            queue.per_server_limit = 2
            queue.active_hosts = {}
            queue.policies = {}
            queue.jobs = {}
            queue.queue = []
            queue.diagnostic = None
            release = Event()
            claimed = []
            futures = []
            for host in ("slow", "second", "third", "fourth"):
                queue.policies[host] = HostPolicy(host, ceiling=2, limit=2)
                for index in range(2):
                    folder = Path(temporary) / f"{host}-{index}"
                    folder.mkdir()
                    future = Future()
                    futures.append(future)
                    queue.queue.append((host, future, folder))
                    queue.jobs[folder.name] = {"host": host, "active": False}

            def capture(folder):
                with queue.condition:
                    claimed.append(queue.jobs[folder.name]["host"])
                    queue.condition.notify_all()
                if not release.wait(5):
                    raise TimeoutError("The test did not release its workers")
                return {"status": "saved"}

            with (
                patch.object(queue, "_run", side_effect=capture),
                patch.object(queue, "_read_job", return_value=None, create=True),
                ThreadPoolExecutor(max_workers=4) as pool,
            ):
                runners = [pool.submit(queue._work_loop) for _ in range(4)]
                try:
                    with queue.condition:
                        self.assertTrue(
                            queue.condition.wait_for(lambda: len(claimed) == 4, 3)
                        )
                    first_wave = list(claimed)
                finally:
                    release.set()
                for runner in runners:
                    runner.result(timeout=5)
            self.assertTrue(all(f.result()["status"] == "saved" for f in futures))
            return first_wave

    def test_other_hosts_start_before_second_job_of_a_busy_host(self):
        self.assertCountEqual(
            self.run_queue(adaptive=True), ["slow", "second", "third", "fourth"]
        )

    def test_fixed_api_keeps_existing_queue_order(self):
        self.assertCountEqual(
            self.run_queue(adaptive=False), ["slow", "slow", "second", "second"]
        )


class FourHostWmsTests(unittest.TestCase):
    def test_four_servers_download_simultaneously_with_two_maps_each(self):
        cases = []
        first_requests = set()
        first_request_lock = Lock()
        together = Barrier(4)
        for index in range(4):
            host = f"127.0.0.{index + 1}"
            case = fixtures.LocalWmsTests()

            def server_factory(address, handler, host=host):
                class ObservedHandler(handler):
                    def do_GET(self):
                        params = parse_qs(urlsplit(self.path).query)
                        operation = next(
                            (v[0] for k, v in params.items() if k.lower() == "request"),
                            "",
                        )
                        if operation.lower() == "getmap":
                            with first_request_lock:
                                first = host not in first_requests
                                first_requests.add(host)
                            if first:
                                # Every host must reach a real HTTP request while
                                # the other three are still waiting for a reply.
                                together.wait(timeout=10)
                        super().do_GET()

                return ThreadingHTTPServer((host, 0), ObservedHandler)

            with patch.object(fixtures, "ThreadingHTTPServer", server_factory):
                case.setUp()
            cases.append(case)
            self.addCleanup(case.tearDown)
            case.server.delay = 0.08

        project = cases[0].project
        selected = []
        for index, case in enumerate(cases):
            for number in range(2):
                uri = QgsDataSourceUri()
                for key, value in {
                    "url": f"http://127.0.0.{index + 1}:{case.server.server_port}/wms",
                    "layers": "map",
                    "styles": "",
                    "format": "image/png",
                    "crs": "EPSG:2180",
                    "version": "1.3.0",
                }.items():
                    uri.setParam(key, value)
                layer = QgsRasterLayer(
                    bytes(uri.encodedUri()).decode(), f"Map {index}-{number}", "wms"
                )
                self.assertTrue(layer.isValid())
                project.addMapLayer(layer)
                selected.append(layer.id())
        with (
            patch(
                "mbtiles_batch_exporter.archive.detect_resources",
                return_value={"cpu": 2, "memory": 6 * 1024**3, "online": True},
            ),
            patch(
                "mbtiles_batch_exporter.parallel_archive.available_memory",
                return_value=6 * 1024**3,
            ),
        ):
            result = fixtures.create_archive(
                project,
                selected,
                cases[0].area,
                cases[0].crs,
                cases[0].folder,
                adaptive=True,
                zoom_min=17,
                zoom_max=17,
            )
        manifest = json.loads((result / "manifest.json").read_text())
        records = [r for r in manifest["layers"] if r["id"] in selected]
        self.assertEqual(len(records), 8)
        self.assertTrue(all(r["status"] == "saved" for r in records))
        self.assertEqual(len({r["worker_pid"] for r in records}), 8)
        self.assertEqual(len(first_requests), 4)
        self.assertFalse(together.broken)
        self.assertEqual(manifest["parallel"]["per_server_limit"], 2)
        self.assertTrue(all(case.server.peak <= 2 for case in cases))
        self.assertTrue(manifest["local_layer_audit"]["passed"])


if __name__ == "__main__":
    unittest.main()
