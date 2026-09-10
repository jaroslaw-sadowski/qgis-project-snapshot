"""A host recovers using missing data even after one tile exhausts its budget."""

import json
import sqlite3
import unittest
from collections import Counter
from concurrent.futures import Future
from contextlib import closing
from threading import Event
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import test_adaptive as adaptive_fixtures
import test_raster_archive as fixtures
from qgis.PyQt.QtGui import QColor, QImage

from mbtiles_batch_exporter.adaptive import DownloadError, WorkerGate
from mbtiles_batch_exporter.parallel_archive import RasterWorkers


class HostRecoveryTests(unittest.TestCase):
    setUp = fixtures.RasterTests.setUp
    tearDown = fixtures.RasterTests.tearDown

    def coordinator(self):
        workers = RasterWorkers(
            None, self.folder, None, [], None, None, [], workers=2, adaptive=True
        )
        workers.next_memory_check = float("inf")
        self.clock = 100.0

        def step():
            # Advance a controlled clock to the next real recovery deadline.
            self.clock = max(
                self.clock + 0.01,
                *(p.until for p in workers.policies.values()),
            )
            with patch.object(
                workers.stop, "wait", side_effect=lambda _: workers.stop.set()
            ):
                workers._coordinate()
            workers.stop.clear()
            self.assertFalse(workers.coordinator_failed)

        return workers, step

    def register(self, workers, name, active=True):
        folder = workers.folder / name
        folder.mkdir()
        workers._register("host", folder)
        workers.jobs[name]["active"] = active
        return folder

    def test_timeout_exhausted_tile_recovers_on_next_missing_tile(self):
        workers, step = self.coordinator()
        calls = Counter()
        operations = []
        try:
            with patch(
                "mbtiles_batch_exporter.adaptive.time.monotonic",
                side_effect=lambda: self.clock,
            ):
                folder = self.register(workers, "map")
                gate = WorkerGate(folder, lambda: False, step)

                def render(layer, project, bounds, width, height, *args):
                    key = (bounds.xMinimum(), bounds.yMaximum())
                    calls[key] += 1
                    operations.append((key, self.clock))
                    if len(operations) <= 3:
                        raise TimeoutError("Test timeout")
                    image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
                    image.fill(QColor("red"))
                    return image

                with patch(
                    "mbtiles_batch_exporter.raster_archive._render_image",
                    side_effect=render,
                ):
                    result = fixtures.write_rendered_raster(
                        self.layer,
                        self.project,
                        self.area,
                        self.crs,
                        self.database,
                        "map",
                        fixtures.zoom_levels(self.project, self.area, self.crs, 17, 17),
                        lambda: False,
                        lambda _: None,
                        gate=gate,
                    )
                step()
                gate.close()
                policy = workers.policies["host"]
                self.assertFalse(policy.blocked)
                self.assertFalse(policy.recovering)
                self.assertTrue(policy.frozen)
                self.assertEqual(
                    [event["reason"] for event in policy.history],
                    ["timeout", "recovered"],
                )
                self.assertEqual(result["status"], "partial", result)
                self.assertFalse(result["raster"]["deferred"])
                self.assertEqual(calls[operations[0][0]], 3)
                self.assertTrue(
                    all(v == 1 for k, v in calls.items() if k != operations[0][0])
                )
                self.assertGreaterEqual(operations[3][1] - operations[2][1], 30)
                with closing(sqlite3.connect(folder / "map.tiles.sqlite")) as db:
                    self.assertEqual(
                        db.execute("SELECT max(attempts) FROM tiles").fetchone()[0], 3
                    )
                    self.assertEqual(
                        db.execute(
                            'SELECT count(*) FROM tiles WHERE status="failed"'
                        ).fetchone()[0],
                        1,
                    )
        finally:
            workers.__exit__()

    def test_three_failed_probes_stop_host_without_more_tile_attempts(self):
        workers, step = self.coordinator()
        calls = Counter()
        try:
            with patch(
                "mbtiles_batch_exporter.adaptive.time.monotonic",
                side_effect=lambda: self.clock,
            ):
                folder = self.register(workers, "map")
                gate = WorkerGate(folder, lambda: False, step)

                def fail(layer, project, bounds, *args):
                    calls[(bounds.xMinimum(), bounds.yMaximum())] += 1
                    raise TimeoutError("Test timeout")

                with patch(
                    "mbtiles_batch_exporter.raster_archive._render_image",
                    side_effect=fail,
                ):
                    result = fixtures.write_rendered_raster(
                        self.layer,
                        self.project,
                        self.area,
                        self.crs,
                        self.database,
                        "map",
                        fixtures.zoom_levels(self.project, self.area, self.crs, 17, 17),
                        lambda: False,
                        lambda _: None,
                        gate=gate,
                    )
                gate.close()
                policy = workers.policies["host"]
                self.assertTrue(policy.blocked)
                self.assertEqual(policy.probe_failures, 3)
                self.assertEqual(sum(calls.values()), 6)
                self.assertTrue(all(v <= 3 for v in calls.values()))
                self.assertTrue(result["raster"]["deferred"])
                self.assertEqual(policy.history[-1]["reason"], "recovery_exhausted")
        finally:
            workers.__exit__()

    def test_last_failed_tile_does_not_discard_next_queued_map(self):
        workers, step = self.coordinator()
        operations = []
        try:
            with patch(
                "mbtiles_batch_exporter.adaptive.time.monotonic",
                side_effect=lambda: self.clock,
            ):
                futures = {}
                for name in ("first", "second"):
                    folder = self.register(workers, name, active=False)
                    future = futures[name] = Future()
                    workers.queue.append(("host", future, folder))

                def run(folder):
                    gate = WorkerGate(folder, lambda: False, step)
                    try:
                        for attempt in range(3 if folder.name == "first" else 1):
                            gate.before(retry=attempt > 0)
                            operations.append((folder.name, self.clock))
                            gate.outcome(
                                TimeoutError("Test timeout")
                                if folder.name == "first"
                                else None,
                                recoverable=attempt < 2,
                            )
                        return {
                            "status": "failed" if folder.name == "first" else "saved"
                        }
                    finally:
                        gate.close()

                workers._run = run
                with patch.object(
                    workers.condition, "wait", side_effect=lambda _: step()
                ):
                    workers._work_loop()
                self.assertEqual(futures["first"].result()["status"], "failed")
                self.assertEqual(futures["second"].result()["status"], "saved")
                self.assertEqual(
                    [name for name, _ in operations], ["first"] * 3 + ["second"]
                )
                self.assertGreaterEqual(operations[3][1] - operations[2][1], 30)
                self.assertFalse(workers.policies["host"].blocked)
                self.assertFalse(workers.policies["host"].recovering)
        finally:
            workers.__exit__()

    def test_recovery_waits_for_preparation_then_grants_only_one_probe(self):
        workers, step = self.coordinator()
        cancelled = Event()
        try:
            with patch(
                "mbtiles_batch_exporter.adaptive.time.monotonic",
                side_effect=lambda: self.clock,
            ):
                gates = [
                    WorkerGate(self.register(workers, name), cancelled.is_set)
                    for name in ("first", "second")
                ]
                policy = workers.policies["host"]
                policy.failure(429, 0, self.clock, policy.generation)
                step()
                self.assertFalse(policy.blocked)
                for gate in gates:
                    gate.state.update(waiting=True, recoverable=True)
                    gate.publish()
                step()
                commands = [
                    json.loads((gate.folder / "control.json").read_text())
                    for gate in gates
                ]
                self.assertEqual(sum(c["allowed"] for c in commands), 1)
                self.assertEqual(sum(c["probe"] for c in commands), 1)
                permitted = next(g for g, c in zip(gates, commands) if c["allowed"])
                permitted.before(retry=False)
                self.assertTrue(permitted.command["probe"])
                cancelled.set()
                blocked = next(g for g in gates if g is not permitted)
                with self.assertRaises(InterruptedError):
                    blocked.before()
        finally:
            workers.__exit__()

    def test_generic_error_has_only_three_ledger_attempts_without_subdivision(self):
        calls = Counter()

        def fail(layer, project, bounds, *args):
            calls[(bounds.xMinimum(), bounds.yMaximum())] += 1
            raise DownloadError("Test HTTP 500", 500)

        with patch(
            "mbtiles_batch_exporter.raster_archive._render_image", side_effect=fail
        ):
            result = fixtures.write_rendered_raster(
                self.layer,
                self.project,
                self.area,
                self.crs,
                self.database,
                "map",
                fixtures.zoom_levels(self.project, self.area, self.crs, 17, 17),
                lambda: False,
                lambda _: None,
                gate=adaptive_fixtures.RepairTests.gate(self),
            )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(calls)
        self.assertTrue(all(count == 3 for count in calls.values()))
        self.assertEqual(result["raster"]["retries"], 0)
        self.assertEqual(result["raster"]["subdivisions"], 0)


class LocalWmsRecoveryTests(unittest.TestCase):
    setUp = fixtures.LocalWmsTests.setUp
    tearDown = fixtures.LocalWmsTests.tearDown
    start_server = fixtures.LocalWmsTests.start_server
    add_map = adaptive_fixtures.AdaptiveWmsTests.add_map
    capture = adaptive_fixtures.AdaptiveWmsTests.capture

    def test_real_workers_keep_recovering_after_tile_attempts_are_exhausted(self):
        from mbtiles_batch_exporter.parallel_archive import merge_raster

        parent = self.server.RequestHandlerClass
        self.server.remaining_failures = 3
        self.server.recovery_requests = []

        class Handler(parent):
            def do_GET(handler):
                query = {
                    key.upper(): values[0]
                    for key, values in parse_qs(urlsplit(handler.path).query).items()
                }
                if query.get("REQUEST", "").lower() == "getmap":
                    host = handler.headers["Host"].split(":", 1)[0]
                    with handler.server.lock:
                        fail = host == "127.0.0.1" and handler.server.remaining_failures
                        if fail:
                            handler.server.remaining_failures -= 1
                        handler.server.recovery_requests.append(
                            (host, query.get("BBOX"), 503 if fail else 200)
                        )
                    if fail:
                        handler.server.requests.append(query)
                        handler.send_response(503)
                        handler.send_header("Retry-After", "0")
                        handler.send_header("Content-Length", "0")
                        handler.end_headers()
                        return
                super().do_GET()

        self.server.RequestHandlerClass = Handler
        first = self.add_map(name="First map, one failed tile")
        second = self.add_map(name="Next map on the same host")
        peer = self.add_map("localhost", "Independent host")
        ledgers = {}

        def capture_ledger(source, destination, table, cancelled):
            with closing(
                sqlite3.connect(source.parent / f"{table}.tiles.sqlite")
            ) as db:
                ledgers[table] = db.execute(
                    "SELECT zoom,col,row,status,attempts FROM tiles "
                    "ORDER BY zoom,col,row"
                ).fetchall()
            return merge_raster(source, destination, table, cancelled)

        with (
            patch(
                "mbtiles_batch_exporter.parallel_archive.merge_raster",
                side_effect=capture_ledger,
            ),
            patch(
                "mbtiles_batch_exporter.parallel_archive.available_memory",
                return_value=8 * 1024**3,
            ),
        ):
            folder, manifest = self.capture([first, second, peer])
        selected = {first.id(), second.id(), peer.id()}
        records = {
            record["id"]: record
            for record in manifest["layers"]
            if record["id"] in selected
        }
        self.assertEqual(records[first.id()]["status"], "partial", records[first.id()])
        for layer in (second, peer):
            self.assertEqual(
                records[layer.id()]["status"], "saved", records[layer.id()]
            )
        self.assertEqual(manifest["parallel"]["completed_in_workers"], 3)
        self.assertFalse(manifest["adaptive"]["coordinator_failed"])
        self.assertTrue(manifest["local_layer_audit"]["passed"])
        policies = {p["host"]: p for p in manifest["adaptive"]["hosts"]}
        policy = policies["127.0.0.1"]
        self.assertFalse(policy["deferred"])
        self.assertEqual(
            [event["reason"] for event in policy["history"]],
            ["503", "503", "503", "recovered"],
        )
        self.assertFalse(policies["localhost"]["deferred"])

        first_tiles = ledgers[records[first.id()]["table"]]
        failures = [tile for tile in first_tiles if tile[3] == "failed"]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0][4], 3)
        self.assertTrue(
            all(
                tile[3] == "saved" and tile[4] == 1
                for tile in first_tiles
                if tile not in failures
            )
        )
        for layer in (second, peer):
            self.assertTrue(
                all(
                    tile[3] == "saved" and tile[4] == 1
                    for tile in ledgers[records[layer.id()]["table"]]
                )
            )
        network_failures = [
            entry for entry in self.server.recovery_requests if entry[2] == 503
        ]
        self.assertEqual(len(network_failures), 3)
        self.assertEqual(len({entry[1] for entry in network_failures}), 1)
        self.assertTrue(all(entry[0] == "127.0.0.1" for entry in network_failures))
        self.assertFalse((folder / ".workers").exists())

        self.project.clear()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        requests_before_offline = len(self.server.requests)
        copied = fixtures.QgsProject()
        try:
            self.assertTrue(copied.read(str(next(folder.glob("*.qgz")))))
            for record in records.values():
                local = copied.mapLayer(record["id"])
                self.assertTrue(local.isValid())
                self.assertEqual(local.providerType(), "gdal")
                image = fixtures._render_image(
                    local,
                    copied,
                    self.area.boundingBox(),
                    256,
                    256,
                    lambda: False,
                    lambda _: None,
                )
                image = image.convertToFormat(QImage.Format_RGBA8888)
                pixels = image.constBits().asstring(image.sizeInBytes())
                self.assertTrue(any(pixels[3::4]))
            self.assertEqual(len(self.server.requests), requests_before_offline)
        finally:
            copied.clear()
