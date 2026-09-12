# SPDX-License-Identifier: GPL-2.0-only

"""Deterministic control decisions and real QGIS tile repair invariants."""

import sqlite3
import time
import unittest
from collections import Counter
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import test_raster_archive as fixtures

from mbtiles_batch_exporter.adaptive import (
    DownloadError,
    HostDeferred,
    HostPolicy,
    WorkerGate,
    retry_after,
    write_state,
)


class PolicyTests(unittest.TestCase):
    def test_growth_requires_time_successes_and_backlog(self):
        p = HostPolicy("test")
        p.success(10, 1, 0)
        p.evaluate(14, True)
        self.assertEqual(p.limit, 1)
        p.evaluate(15, True)
        self.assertEqual(p.limit, 2)
        p.success(30, 30, p.generation)
        p.evaluate(30, True)
        self.assertEqual(p.limit, 3)
        p.success(100, 45, p.generation)
        p.evaluate(45, False)
        self.assertEqual(p.limit, 3)

    def test_two_bad_windows_revert_and_wait_for_stabilization(self):
        p = HostPolicy("test")
        p.success(20, 15, 0)
        p.evaluate(15, True)
        for now in (30, 45):
            p.success(20, now, p.generation)
            p.evaluate(now, True)
        self.assertEqual(p.limit, 1)
        self.assertTrue(p.frozen)
        p.success(1000, 60, p.generation)
        p.evaluate(60, True)
        self.assertEqual(p.limit, 1)

    def test_unfilled_limit_does_not_misidentify_a_server_ceiling(self):
        p = HostPolicy("test", ceiling=8)
        p.success(20, 15, 0)
        p.evaluate(15, True, active=1)
        self.assertEqual(p.limit, 2)
        # The second process cannot start yet (RAM/CPU/startup). Two slow
        # windows at the old concurrency are not evidence against the server.
        for now in (30, 45):
            p.success(20, now, p.generation)
            p.evaluate(now, True, active=1)
        self.assertFalse(p.frozen)
        self.assertEqual(p.limit, 2)
        p.success(50, 60, p.generation)
        p.evaluate(60, True, active=2)
        self.assertEqual(p.limit, 3)

    def test_draining_queue_does_not_lower_a_successful_limit(self):
        p = HostPolicy("test", ceiling=3)
        for now, count in ((15, 20), (30, 50)):
            p.success(count, now, p.generation)
            p.evaluate(now, True, active=p.limit)
        self.assertEqual(p.limit, 3)
        for now in (45, 60):
            p.success(20, now, p.generation)
            p.evaluate(now, False, active=1)
        self.assertFalse(p.frozen)
        self.assertEqual(p.limit, 3)

    def test_map_handoffs_pause_measurement_without_losing_full_load_samples(self):
        p = HostPolicy("test", ceiling=8)
        p.success(20, 15, 0)
        p.evaluate(15, True, active=1)
        self.assertEqual(p.limit, 2)
        for now, active, count in ((20, 2, 20), (25, 1, 1), (30, 2, 20)):
            p.success(count, now, p.generation)
            p.evaluate(now, True, active=active)
        self.assertEqual(p.limit, 2)
        self.assertEqual(p.successes, 40)
        p.success(20, 35, p.generation)
        p.evaluate(35, True, active=2)
        self.assertEqual(p.limit, 3)
        self.assertEqual(p.rate, 4.0)  # 60 successes / 15 seconds at full load.

    def test_backoff_probe_exhaustion_and_old_wave_errors(self):
        p = HostPolicy("a", limit=4)
        p.failure(429, None, 0, 0)
        self.assertEqual((p.limit, p.until), (3, 30))
        p.failure(429, None, 1, 0)
        self.assertEqual(p.limit, 3)
        for now, pause in ((30, 60), (90, 120)):
            p.failure(503, None, now, p.generation, probe=True)
            self.assertEqual(p.until, now + pause)
        p.failure(429, None, 210, p.generation, probe=True)
        self.assertTrue(p.blocked)
        self.assertTrue(p.frozen)

    def test_other_transient_probe_failures_also_exhaust_recovery(self):
        p = HostPolicy("test", limit=4)
        p.failure(429, 0, 0, 0)
        for index, status in enumerate((500, None, "timeout"), 1):
            p.failure(status, 0, index, p.generation, probe=True)
            self.assertEqual(p.probe_failures, index)
        self.assertTrue(p.blocked)
        other = HostPolicy("other", limit=4)
        other.failure(429, 0, 0, 0)
        other.failure(403, None, 1, other.generation, probe=True)
        self.assertEqual(other.limit, 3)

    def test_successful_probe_requires_healthy_windows_before_growth_resumes(self):
        p = HostPolicy("a", limit=3)
        p.failure(503, 1, 0, 0)
        p.success(1, 1, p.generation, probe=True)
        self.assertFalse(p.recovering)
        p.success(100, 16, p.generation)
        p.evaluate(16, True)
        self.assertEqual(p.limit, 2)
        for now in (31, 46, 61):
            p.success(100, now, p.generation)
            p.evaluate(now, True, active=p.limit)
        self.assertEqual(p.limit, 3)
        self.assertEqual(p.history[-1]["reason"], "reprobe")
        p.failure(429, 0, 62, p.generation)
        self.assertEqual(p.limit, 2)

    def test_reprobe_uses_current_rate_and_backs_off_repeated_failed_trials(self):
        p = HostPolicy("test")
        now = 0

        def window(count=20, backlog=True):
            nonlocal now
            now += 15
            p.success(count, now, p.generation)
            p.evaluate(now, backlog, active=p.limit)

        window()
        self.assertEqual(p.limit, 2)
        for delay in (60, 120, 240, 300):
            window()
            window()
            self.assertEqual(p.limit, 1)
            self.assertTrue(p.frozen)
            self.assertEqual(p.retry_seconds, delay)
            for _ in range(int(delay / 15) - 1):
                window()
                self.assertEqual(p.limit, 1)
            window()
            self.assertEqual(p.limit, 2)
            self.assertEqual(p.history[-1]["reason"], "reprobe")
        # A recovered service really benefits from the new slot. An old peak
        # from a different map must not prevent subsequent growth.
        window(60)
        self.assertEqual(p.limit, 3)
        self.assertEqual(p.retry_seconds, 30)

    def test_stable_limit_is_reduced_after_sustained_throughput_drop(self):
        p = HostPolicy("test", limit=4, ceiling=4)
        for now, count in ((15, 150), (30, 140), (45, 50), (60, 50)):
            p.success(count, now, p.generation)
            p.evaluate(now, False, active=p.limit)
        self.assertEqual(p.limit, 3)
        self.assertEqual(p.history[-1]["reason"], "throughput_drop")
        self.assertTrue(p.frozen)

    def test_single_slow_window_and_low_rate_at_one_do_not_lock_growth(self):
        p = HostPolicy("test", limit=1, frozen=True, retry_seconds=60)
        for now, count in ((15, 150), (30, 20), (45, 20), (60, 20)):
            p.success(count, now, p.generation)
            p.evaluate(now, True, active=1)
        self.assertEqual(p.limit, 2)
        q = HostPolicy("test", limit=4, ceiling=4)
        for now, count in ((15, 150), (30, 20), (45, 150)):
            q.success(count, now, q.generation)
            q.evaluate(now, False, active=4)
        self.assertEqual(q.limit, 4)
        self.assertFalse(q.frozen)

    def test_idle_time_errors_and_memory_pressure_cannot_unlock_reprobe(self):
        p = HostPolicy("test", frozen=True, retry_seconds=60)
        p.evaluate(600, True, active=0)
        self.assertEqual(p.limit, 1)
        for now in (615, 630, 645):
            p.success(100, now, p.generation)
            p.evaluate(now, True, active=1)
        p.failure("timeout", None, 650, p.generation)
        p.success(100, 665, p.generation)
        p.evaluate(665, True, active=1)
        self.assertEqual(p.limit, 1)
        for now in (680, 695, 710):
            p.success(100, now, p.generation)
            p.evaluate(now, True, active=1, memory_ok=False)
        self.assertEqual(p.limit, 1)
        p.success(100, 725, p.generation)
        p.evaluate(725, True, active=1)
        self.assertEqual(p.limit, 2)

    def test_repeated_gateway_errors_reduce_and_pause_a_host(self):
        p = HostPolicy("test", limit=4)
        for index, code in enumerate((502, 504, 502)):
            p.failure(code, None, index, p.generation)
        self.assertEqual(p.limit, 3)
        self.assertTrue(p.recovering)
        self.assertEqual(p.until, 32)

    def test_timeouts_and_permanent_errors(self):
        p = HostPolicy("a", limit=4)
        for code in (401, 403, 404):
            p.failure(code, None, 0, p.generation)
        self.assertEqual(p.limit, 4)
        for _ in range(2):
            p.failure("timeout", None, 1, p.generation)
        self.assertFalse(p.recovering)
        p.failure("timeout", None, 2, p.generation)
        self.assertTrue(p.recovering)

    def test_retry_after_formats_and_long_wait(self):
        self.assertEqual(retry_after("17"), 17)
        self.assertEqual(retry_after("Thu, 01 Jan 1970 00:01:00 GMT", now=10), 50)
        self.assertIsNone(retry_after("invalid"))
        p = HostPolicy("a")
        p.failure(429, 301, 0, 0)
        self.assertTrue(p.blocked)
        self.assertEqual(p.until, 301)

    def test_late_retry_after_restarts_pause_without_counting_an_old_probe(self):
        p = HostPolicy("test", limit=4)
        p.failure(503, 0, 0, 0)
        p.success(1, 1, p.generation, probe=True)
        previous_generation = p.generation
        self.assertFalse(p.recovering)
        p.failure(429, 120, 2, 0)
        self.assertEqual(p.limit, 3)
        self.assertTrue(p.recovering)
        self.assertEqual(p.until, 122)
        self.assertEqual(p.probe_failures, 0)
        p.success(1, 3, previous_generation, probe=True)
        self.assertTrue(p.recovering)
        p.failure(503, 120, 4, previous_generation)
        self.assertEqual(p.until, 124)
        self.assertEqual(p.limit, 3)
        self.assertEqual(p.probe_failures, 0)

    def test_memory_pressure_prevents_growth(self):
        p = HostPolicy("a")
        p.success(100, 15, 0)
        p.evaluate(15, True, memory_ok=False)
        self.assertEqual(p.limit, 1)
        p.success(100, 30, 0)
        p.evaluate(30, True, memory_ok=True)
        self.assertEqual(p.limit, 2)

    def test_gate_cancellation_and_explicit_defer(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            gate = WorkerGate(folder, lambda: True)
            with self.assertRaises(InterruptedError):
                gate.before()
            gate = WorkerGate(folder, lambda: False)
            write_state(folder / "control.json", {"version": 1, "blocked": True})
            with self.assertRaises(HostDeferred):
                gate.before()

    def test_expired_coordinator_permission_fails_closed(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            clock = [1.0]
            gate = WorkerGate(folder, lambda: False, lambda: clock.__setitem__(0, 12.0))
            write_state(
                folder / "control.json", {"version": 1, "allowed": True, "expires": 0}
            )
            with patch(
                "mbtiles_batch_exporter.adaptive.time.monotonic",
                side_effect=lambda: clock[0],
            ):
                with self.assertRaises(HostDeferred):
                    gate.before()

    def test_lowered_permission_blocks_next_operation_and_can_be_cancelled(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            cancel = [False]
            gate = WorkerGate(
                folder, lambda: cancel[0], lambda: cancel.__setitem__(0, True)
            )
            command = {
                "version": 1,
                "allowed": True,
                "expires": time.monotonic() + 10,
                "generation": 0,
                "ack": 0,
            }
            write_state(folder / "control.json", command)
            gate.before()
            gate.outcome()
            write_state(folder / "control.json", dict(command, allowed=False))
            with self.assertRaises(InterruptedError):
                gate.before()
            self.assertEqual(gate.counts, {"0": 1})

    def test_coordinator_resamples_ram_and_reports_pressure(self):
        from threading import Condition

        from mbtiles_batch_exporter.parallel_archive import RasterWorkers

        coordinator = RasterWorkers.__new__(RasterWorkers)

        class Stop:
            turns = 0

            def is_set(self):
                return self.turns >= 2

            def wait(self, seconds):
                self.turns += 1

            def set(self):
                self.turns = 2

        coordinator.stop = Stop()
        coordinator.condition = Condition()
        coordinator.next_memory_check = 0
        coordinator.memory_history = []
        coordinator.memory_ok = True
        coordinator.origin = 0
        coordinator.jobs = {}
        coordinator.policies = {"test": HostPolicy("test")}
        coordinator.queue = []
        coordinator.active_hosts = {}
        coordinator.workers = 4
        coordinator.worker_memory = 1024**3
        coordinator.worker_peak_memory = 0
        coordinator.reserved_growth = 0
        coordinator.coordinator_failed = False
        coordinator.memory_growth_ok = True
        coordinator.cpu = 2
        coordinator.diagnostic = None
        with (
            patch(
                "mbtiles_batch_exporter.parallel_archive.time.monotonic",
                side_effect=[20, 40],
            ),
            patch(
                "mbtiles_batch_exporter.parallel_archive.available_memory",
                side_effect=[512 * 1024**2] * 2 + [3 * 1024**3] * 2,
            ) as memory,
        ):
            coordinator._coordinate()
        self.assertEqual(memory.call_count, 4)
        self.assertEqual(
            [r["memory_ok"] for r in coordinator.memory_history], [False, True]
        )
        self.assertFalse(coordinator.coordinator_failed)


class RepairTests(unittest.TestCase):
    setUp = fixtures.RasterTests.setUp
    tearDown = fixtures.RasterTests.tearDown

    def gate(self):
        folder = self.folder

        class Gate:
            retrying = False

            def before(self, retry=False):
                pass

            def outcome(self, error=None, recoverable=True):
                pass

        gate = Gate()
        gate.folder = folder
        return gate

    def test_only_failed_tiles_are_repaired_including_empty_successes(self):
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QImage

        calls = Counter()
        empty_key = [None]
        failed_key = [None]

        def render(layer, project, bounds, width, height, cancelled, progress):
            key = (round(bounds.xMinimum(), 3), round(bounds.yMaximum(), 3), width)
            calls[key] += 1
            if empty_key[0] is None:
                empty_key[0] = key
            if key == empty_key[0]:
                image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
                image.fill(Qt.transparent)
                return image
            if failed_key[0] is None:
                failed_key[0] = key
            if key == failed_key[0] and calls[key] == 1:
                raise DownloadError("[HTTP 503] Test", 503, 0)
            return fixtures._render_image(
                layer, project, bounds, width, height, cancelled, progress
            )

        with patch(
            "mbtiles_batch_exporter.raster_archive._render_image", side_effect=render
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
                gate=self.gate(),
            )
        self.assertEqual(result["status"], "saved", result)
        self.assertEqual(calls[empty_key[0]], 1)
        self.assertEqual(calls[failed_key[0]], 2)
        self.assertTrue(all(v == 1 for k, v in calls.items() if k != failed_key[0]))
        self.assertEqual(result["raster"]["repaired"], 1)
        with closing(sqlite3.connect(self.folder / "map.tiles.sqlite")) as db:
            self.assertGreater(
                db.execute(
                    'SELECT count(*) FROM tiles WHERE status="empty"'
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute("SELECT max(attempts) FROM tiles").fetchone()[0], 2
            )

    def test_permanent_error_is_not_retried_and_remains_missing(self):
        calls = Counter()

        def fail(layer, project, bounds, *args):
            calls[(bounds.xMinimum(), bounds.yMaximum())] += 1
            raise DownloadError("HTTP 403", 403)

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
                gate=self.gate(),
            )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(all(v == 1 for v in calls.values()))
        self.assertEqual(result["raster"]["repair_attempts"], 0)

    def test_proxy_refusal_stops_map_and_preserves_completed_tiles(self):
        for saved_tiles in (0, 1):
            with self.subTest(saved_tiles=saved_tiles):

                def render(*args):
                    if drawing.call_count <= saved_tiles:
                        return fixtures._render_image(*args)
                    raise DownloadError("HTTP 407", 407)

                table = f"proxy_{saved_tiles}"
                with patch(
                    "mbtiles_batch_exporter.raster_archive._render_image",
                    side_effect=render,
                ) as drawing:
                    result = fixtures.write_rendered_raster(
                        self.layer,
                        self.project,
                        self.area,
                        self.crs,
                        self.database,
                        table,
                        fixtures.zoom_levels(self.project, self.area, self.crs, 16, 17),
                        lambda: False,
                        lambda _: None,
                        gate=self.gate(),
                    )
                self.assertEqual(drawing.call_count, saved_tiles + 1)
                self.assertEqual(
                    result["status"], "partial" if saved_tiles else "failed"
                )
                self.assertEqual(result["tile_count"], saved_tiles)
                self.assertEqual("local_source" in result, bool(saved_tiles))
                self.assertIn("proxy", result["reason"].lower())
                self.assertEqual(result["raster"]["stop_http_status"], 407)
                self.assertTrue(result["raster"]["stopped_early"])
                self.assertFalse(result["raster"]["deferred"])
                self.assertEqual(result["raster"]["repair_attempts"], 0)
                with closing(sqlite3.connect(self.database)) as database:
                    self.assertEqual(
                        database.execute(f'SELECT count(*) FROM "{table}"').fetchone()[
                            0
                        ],
                        saved_tiles,
                    )

    def test_repair_budget_is_three_total_attempts_per_tile(self):
        calls = Counter()

        def fail(layer, project, bounds, *args):
            calls[(bounds.xMinimum(), bounds.yMaximum())] += 1
            raise DownloadError("[HTTP 503] Test", 503, 0)

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
                gate=self.gate(),
            )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(all(v == 3 for v in calls.values()))
        with closing(sqlite3.connect(self.folder / "map.tiles.sqlite")) as db:
            self.assertEqual(
                db.execute("SELECT max(attempts) FROM tiles").fetchone()[0], 3
            )

    def test_cancel_during_repair_does_not_repeat_successful_tiles(self):
        gate = self.gate()
        calls = Counter()
        first = [None]

        def before(retry=False):
            if retry:
                raise InterruptedError()

        gate.before = before

        def render(layer, project, bounds, *args):
            key = (bounds.xMinimum(), bounds.yMaximum())
            calls[key] += 1
            if first[0] is None:
                first[0] = key
            if key != first[0]:
                raise DownloadError("[HTTP 503] Test", 503, 0)
            return fixtures._render_image(layer, project, bounds, *args)

        with patch(
            "mbtiles_batch_exporter.raster_archive._render_image", side_effect=render
        ):
            with self.assertRaises(InterruptedError):
                fixtures.write_rendered_raster(
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
        self.assertEqual(calls[first[0]], 1)


class AdaptiveWmsTests(unittest.TestCase):
    start_server = fixtures.LocalWmsTests.start_server
    setUp = fixtures.LocalWmsTests.setUp
    tearDown = fixtures.LocalWmsTests.tearDown

    def add_map(self, host="127.0.0.1", name="Adaptive WMS"):
        from qgis.core import QgsDataSourceUri, QgsRasterLayer

        uri = QgsDataSourceUri()
        for key, value in {
            "url": f"http://{host}:{self.server.server_port}/wms",
            "layers": "map",
            "styles": "",
            "format": "image/png",
            "crs": "EPSG:2180",
            "version": "1.3.0",
        }.items():
            uri.setParam(key, value)
        layer = QgsRasterLayer(bytes(uri.encodedUri()).decode(), name, "wms")
        self.assertTrue(layer.isValid())
        self.project.addMapLayer(layer, False)
        self.group.addLayer(layer)
        return layer

    def capture(self, layers, **kwargs):
        # Fix both the initial and live RAM samples. Resource-pressure behavior
        # is covered separately by DynamicWorkerTests with a controlled clock.
        with (
            patch(
                "mbtiles_batch_exporter.archive.detect_resources",
                return_value={"cpu": 2, "memory": 8 * 1024**3, "online": True},
            ),
            patch(
                "mbtiles_batch_exporter.parallel_archive.available_memory",
                return_value=8 * 1024**3,
            ),
        ):
            result = fixtures.create_archive(
                self.project,
                [layer.id() for layer in layers],
                self.area,
                self.crs,
                self.folder,
                zoom_min=17,
                zoom_max=17,
                adaptive=True,
                **kwargs,
            )
        return result, fixtures.read_resume_manifest(result)

    def test_windows_control_lock_recovers_and_map_is_saved(self):
        from test_ipc import windows_lock

        layer = self.add_map()
        replace = Path.replace
        failures = []

        def locked(source, destination):
            if Path(destination).name == "control.json" and Path(destination).exists():
                if len(failures) < 3:
                    failures.append(1)
                    raise windows_lock()
            return replace(source, destination)

        with patch.object(Path, "replace", locked):
            folder, manifest = self.capture([layer])
        self.assertEqual(len(failures), 3)
        self.assertFalse(manifest["adaptive"]["coordinator_failed"])
        record = next(r for r in manifest["layers"] if r["id"] == layer.id())
        self.assertEqual(record["status"], "saved")
        with closing(sqlite3.connect(folder / "dane" / "dane.gpkg")) as db:
            count = db.execute(f'SELECT COUNT(*) FROM "{record["table"]}"').fetchone()[
                0
            ]
        self.assertGreater(count, 0)
        self.assertIn(
            '"ipc_replace_recovered"',
            (folder / "diagnostyka" / "diagnostyka.jsonl").read_text(),
        )

    def test_persistent_control_lock_reports_coordinator_for_queued_maps(self):
        from test_ipc import windows_lock

        layers = [self.add_map(name=f"Map {i}") for i in range(3)]
        replace = Path.replace

        def locked(source, destination):
            if Path(destination).name == "control.json" and Path(destination).exists():
                raise windows_lock()
            return replace(source, destination)

        with patch.object(Path, "replace", locked):
            folder, manifest = self.capture(layers)
        self.assertTrue(manifest["adaptive"]["coordinator_failed"])
        selected = [
            r for r in manifest["layers"] if r["id"] in {layer.id() for layer in layers}
        ]
        self.assertTrue(all(r["status"] == "failed" for r in selected))
        self.assertTrue(
            all(r["worker_error"]["stage"] == "coordinator" for r in selected)
        )
        self.assertFalse((folder / ".workers").exists())
        self.assertIn(
            '"ipc_replace_failed"',
            (folder / "diagnostyka" / "diagnostyka.jsonl").read_text(),
        )

    def test_rate_limit_repairs_same_map_and_records_recovery(self):
        layer = self.add_map()
        self.server.scripted_statuses = [429]
        self.server.retry_after = "0"
        rows = []
        result, manifest = self.capture(
            [layer], server_activity=lambda values: rows.extend(values)
        )
        record = next(r for r in manifest["layers"] if r["id"] == layer.id())
        self.assertEqual(record["status"], "saved", record)
        self.assertEqual(record["raster"]["repaired"], 1)
        self.assertIn("worker_pid", record)
        self.assertEqual(manifest["schema_version"], 4)
        history = manifest["adaptive"]["hosts"][0]["history"]
        self.assertIn("429", [h["reason"] for h in history])
        self.assertIn("recovered", [h["reason"] for h in history])
        self.assertTrue(manifest["local_layer_audit"]["passed"])
        self.assertTrue(rows)
        self.assertFalse((result / ".workers").exists())

    def test_long_retry_after_defers_one_host_but_another_finishes(self):
        first = self.add_map()
        second = self.add_map("localhost", "Other host")
        self.server.scripted_statuses = [429]
        self.server.retry_after = "301"
        _, manifest = self.capture([first, second])
        records = [
            r for r in manifest["layers"] if r["id"] in (first.id(), second.id())
        ]
        self.assertEqual(sorted(r["status"] for r in records), ["failed", "saved"])
        self.assertEqual(sum(p["deferred"] for p in manifest["adaptive"]["hosts"]), 1)
        self.assertTrue(
            any(
                "retry_after_exceeds_300s" in [h["reason"] for h in p["history"]]
                for p in manifest["adaptive"]["hosts"]
            )
        )

    def test_cancel_during_cooldown_preserves_completed_vector(self):
        layer = self.add_map()
        self.server.scripted_statuses = [429]
        self.server.retry_after = "30"
        cancel = [False]

        def observe(rows):
            if any(r["state"] == "cooldown" for r in rows):
                cancel[0] = True

        _, manifest = self.capture(
            [self.layer, layer], server_activity=observe, cancelled=lambda: cancel[0]
        )
        self.assertTrue(manifest["cancelled"])
        records = {r["id"]: r for r in manifest["layers"]}
        self.assertEqual(records[self.layer.id()]["status"], "saved")
        self.assertEqual(records[layer.id()]["status"], "cancelled")

    def test_worker_crash_never_falls_back_outside_host_control(self):
        layer = self.add_map()
        with patch(
            "mbtiles_batch_exporter.parallel_archive.RasterWorkers._run",
            side_effect=RuntimeError("crash"),
        ):
            _, manifest = self.capture([layer])
        record = next(r for r in manifest["layers"] if r["id"] == layer.id())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(len(self.server.requests), 0)

    def test_http_date_retry_after_and_503_recovery(self):
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime

        layer = self.add_map()
        self.server.scripted_statuses = [503]
        self.server.retry_after = format_datetime(
            datetime.now(timezone.utc) + timedelta(seconds=4), usegmt=True
        )
        _, manifest = self.capture([layer])
        record = next(r for r in manifest["layers"] if r["id"] == layer.id())
        self.assertEqual(record["status"], "saved", record)
        history = manifest["adaptive"]["hosts"][0]["history"]
        pause = next(h["pause_seconds"] for h in history if h["reason"] == "503")
        self.assertGreater(pause, 0)
        self.assertLessEqual(pause, 4)
        self.assertIn("recovered", [h["reason"] for h in history])

    def test_main_qgis_map_uses_same_host_controller(self):
        layer = self.add_map()
        self.server.scripted_statuses = [429]
        self.server.retry_after = "0"
        # Exercise the main-QGIS route without needing an authentication database.
        with patch.object(
            layer, "source", return_value=layer.source() + "&authcfg=test"
        ):
            _, manifest = self.capture([layer])
        record = next(r for r in manifest["layers"] if r["id"] == layer.id())
        self.assertEqual(record["status"], "saved", record)
        self.assertNotIn("worker_pid", record)
        self.assertEqual(record["raster"]["repaired"], 1)
        self.assertIn(
            "429", [h["reason"] for h in manifest["adaptive"]["hosts"][0]["history"]]
        )
