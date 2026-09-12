# SPDX-License-Identifier: GPL-2.0-only

"""Measured utilization remains useful during waits, failures and finalization."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_adaptive as adaptive_fixtures
import test_raster_archive as fixtures

from mbtiles_batch_exporter.adaptive import HostPolicy
from mbtiles_batch_exporter.diagnostics import Diagnostics, PerformanceDiagnostics
from mbtiles_batch_exporter.parallel_archive import RasterWorkers


class PerformanceDiagnosticsTests(unittest.TestCase):
    def test_known_cpu_deltas_and_first_sample_coverage(self):
        diagnostic = Mock()
        sampler = PerformanceDiagnostics(diagnostic, "main", Path("/private/token"))
        counters = [
            {
                "monotonic_seconds": 10.0,
                "process_cpu_seconds": 3.0,
                "system_cpu": {
                    "source": "fixture",
                    "total_seconds": 100.0,
                    "idle_seconds": 60.0,
                },
            },
            {
                "monotonic_seconds": 12.0,
                "process_cpu_seconds": 6.0,
                "system_cpu": {
                    "source": "fixture",
                    "total_seconds": 128.0,
                    "idle_seconds": 68.0,
                },
            },
        ]
        with (
            patch(
                "mbtiles_batch_exporter.resources.performance_counters",
                side_effect=counters,
            ) as probe,
            patch(
                "mbtiles_batch_exporter.diagnostics.shutil.disk_usage",
                return_value=SimpleNamespace(total=1000, free=250),
            ),
        ):
            sampler.sample()
            sampler.sample()
        self.assertTrue(all(c.kwargs["include_system"] for c in probe.call_args_list))
        first, second = [call.kwargs for call in diagnostic.emit.call_args_list]
        self.assertIsNone(first["process_cpu_percent_one_core"])
        self.assertIsNone(first["system_cpu_percent"])
        self.assertIsNone(first["interval_seconds"])
        self.assertEqual(second["process_cpu_percent_one_core"], 150.0)
        self.assertAlmostEqual(second["system_cpu_percent"], 20 / 28 * 100)
        self.assertEqual(second["interval_seconds"], 2.0)
        self.assertEqual(second["volume"], {"total_bytes": 1000, "free_bytes": 250})
        self.assertNotIn("private", str(diagnostic.emit.call_args_list))
        self.assertNotIn("token", str(diagnostic.emit.call_args_list))

    def test_unavailable_cpu_and_io_do_not_discard_other_measurements(self):
        diagnostic = Mock()
        sampler = PerformanceDiagnostics(diagnostic, "worker")
        measurements = [
            {
                "monotonic_seconds": float(index),
                "process_cpu_seconds": cpu,
                "process_memory": {"current_bytes": 12345},
                "process_io": None,
                "system_cpu": None,
                "system_memory": None,
            }
            for index, cpu in enumerate((None, None, 5.0, 5.5), 1)
        ]
        with patch(
            "mbtiles_batch_exporter.resources.performance_counters",
            side_effect=measurements,
        ) as probe:
            for _ in measurements:
                sampler.sample()
        self.assertTrue(
            all(not c.kwargs["include_system"] for c in probe.call_args_list)
        )
        diagnostic.error.assert_not_called()
        rows = [call.kwargs for call in diagnostic.emit.call_args_list]
        self.assertEqual(len(rows), 4)
        for row in rows[:3]:
            self.assertIsNone(row["process_cpu_percent_one_core"])
        self.assertEqual(rows[3]["process_cpu_percent_one_core"], 50.0)
        for row in rows:
            self.assertIsNone(row["counters"]["process_io"])
            self.assertIsNone(row["system_cpu_percent"])
            self.assertEqual(row["counters"]["process_memory"]["current_bytes"], 12345)

    def test_probe_failure_is_logged_without_secrets_and_recovers(self):
        with TemporaryDirectory() as folder:
            diagnostic = Diagnostics(Path(folder) / "diagnostic.jsonl")
            sampler = PerformanceDiagnostics(diagnostic, "main", folder)
            with (
                patch(
                    "mbtiles_batch_exporter.resources.performance_counters",
                    side_effect=[
                        OSError(13, "secret-password", "/private/source"),
                        {"monotonic_seconds": 2.0, "process_cpu_seconds": 1.0},
                    ],
                ),
                patch(
                    "mbtiles_batch_exporter.diagnostics.shutil.disk_usage",
                    side_effect=OSError("secret-volume"),
                ),
            ):
                sampler.sample()
                sampler.sample()
            text = diagnostic.path.read_text()
            rows = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(rows[0]["event"], "performance_probe_error")
            self.assertEqual(rows[1]["event"], "performance_sample")
            self.assertIsNone(rows[1]["volume"])
            for secret in (
                folder,
                "secret-password",
                "/private/source",
                "secret-volume",
            ):
                self.assertNotIn(secret, text)

    def test_sampling_continues_while_main_thread_waits_and_stops_on_errors(self):
        for error_type in (InterruptedError, ValueError):
            with self.subTest(error=error_type.__name__):
                captured = []
                sampled_while_waiting = Event()
                diagnostic = Mock()

                def emit(event, **fields):
                    if event == "performance_sample":
                        captured.append(fields)
                        if len(captured) >= 2:
                            sampled_while_waiting.set()

                diagnostic.emit.side_effect = emit
                sampler = PerformanceDiagnostics(diagnostic, "worker", interval=0.01)
                with self.assertRaises(error_type):
                    with sampler:
                        sampler.set_phase("render", "layer_test")
                        # No Qt event processing or progress callbacks during this wait.
                        self.assertTrue(sampled_while_waiting.wait(1.0))
                        raise error_type("private-cancellation-or-failure")
                self.assertTrue(sampler.stop.is_set())
                self.assertFalse(sampler.thread.is_alive())
                self.assertGreaterEqual(len(captured), 3)
                self.assertTrue(any(row["phase"] == "render" for row in captured))
                self.assertNotIn(
                    "private-cancellation-or-failure", str(diagnostic.mock_calls)
                )

    def test_failed_sampler_thread_start_does_not_interrupt_work(self):
        diagnostic = Mock()
        sampler = PerformanceDiagnostics(diagnostic, "worker")
        with patch(
            "mbtiles_batch_exporter.diagnostics.Thread.start",
            side_effect=RuntimeError("threads unavailable"),
        ):
            with sampler:
                sampler.set_phase("render", "layer_test")
        self.assertIsNone(sampler.thread)
        self.assertTrue(sampler.stop.is_set())
        diagnostic.error.assert_called_once()
        self.assertEqual(diagnostic.error.call_args.args[0], "performance_probe_error")

    def test_unavailable_phase_cpu_still_reports_elapsed_time(self):
        diagnostic = Mock()
        with (
            patch(
                "mbtiles_batch_exporter.diagnostics.time.process_time",
                side_effect=OSError("private-native-error"),
            ),
            patch(
                "mbtiles_batch_exporter.diagnostics.time.monotonic",
                side_effect=(10.0, 14.0),
            ),
        ):
            sampler = PerformanceDiagnostics(diagnostic, "worker")
            sampler.set_phase("render", "layer_test")
        row = diagnostic.emit.call_args.kwargs
        self.assertEqual(row["seconds"], 4.0)
        self.assertIsNone(row["process_cpu_seconds"])
        self.assertEqual(sampler.context, ("render", "layer_test"))
        self.assertNotIn("private-native-error", str(diagnostic.mock_calls))

    def test_scheduler_explains_nine_processes_and_seven_active_tasks(self):
        workers = RasterWorkers.__new__(RasterWorkers)
        workers.diagnostic = Mock()
        workers.jobs = {
            f"layer_{index}": {
                "active": True,
                "host": "example.test",
                "state": {
                    "running": index < 7,
                    "waiting": index >= 7,
                    "sampled_at": 9.0,
                },
            }
            for index in range(9)
        }
        workers.rows = [
            {
                "host": "example.test",
                "active": 7,
                "processes": 9,
                "limit": 7,
                "queued": 2,
                "rate": 12.0,
                "state": "computer_limit",
                "pause": 0,
                "generation": 0,
                "successes": 100,
            }
        ]
        workers.policies = {"example.test": HostPolicy("example.test", ceiling=28)}
        workers.origin = 1.0
        workers.cpu, workers.ceiling, workers.workers = 14, 28, 9
        workers.active_hosts = {"example.test": 9}
        workers.queue = [None, None]
        workers.futures = {}
        workers.launch_slots = 0
        workers.memory_available = 3 * 1024**3
        workers.memory_budget_available = 2 * 1024**3
        workers.worker_memory = 400 * 1024**2
        workers.worker_peak_memory = 300 * 1024**2
        workers.reserved_growth = 900 * 1024**2
        workers.memory_ok = True
        workers.memory_growth_ok = True
        workers._diagnose_scheduler(10.0)
        event = workers.diagnostic.emit.call_args
        self.assertEqual(event.args[0], "scheduler_sample")
        row = event.kwargs
        self.assertEqual(
            (row["processes"], row["budget"], row["active_tasks"]), (9, 9, 7)
        )
        self.assertEqual(row["cpu_ceiling"], 28)
        self.assertEqual(row["memory_budget_available"], 2 * 1024**3)
        self.assertTrue(row["memory_growth_ok"])
        self.assertEqual(sum(job["waiting"] for job in row["jobs"]), 2)
        self.assertTrue(all(job["telemetry_age_seconds"] == 1.0 for job in row["jobs"]))
        self.assertEqual(row["hosts"][0]["limit"], 7)


class ArchivePerformanceDiagnosticsTests(unittest.TestCase):
    start_server = fixtures.LocalWmsTests.start_server
    setUp = fixtures.LocalWmsTests.setUp
    tearDown = fixtures.LocalWmsTests.tearDown
    add_map = adaptive_fixtures.AdaptiveWmsTests.add_map
    capture = adaptive_fixtures.AdaptiveWmsTests.capture

    def test_cancelled_archive_retains_final_outcomes_and_sampler_shutdown(self):
        from threading import enumerate as threads

        layer = self.add_map()
        cancelled = False

        def completed(record, count, total):
            nonlocal cancelled
            cancelled = count > 0

        folder, manifest = self.capture(
            [self.layer, layer],
            cancelled=lambda: cancelled,
            layer_status=completed,
        )
        rows = [
            json.loads(line)
            for line in (folder / "diagnostyka" / "diagnostyka.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertTrue(manifest["cancelled"])
        summaries = [row for row in rows if row["event"] == "layer_summary"]
        self.assertEqual(len(summaries), 2)
        self.assertEqual({row["status"] for row in summaries}, {"saved", "cancelled"})
        self.assertEqual(rows[-1]["event"], "archive_end")
        self.assertTrue(rows[-1]["completed"])
        self.assertFalse(
            any(thread.name == "archive-performance" for thread in threads())
        )

    def test_real_worker_archive_preserves_performance_plan_and_final_outcomes(self):
        layer = self.add_map(name="Private-user-layer-79")
        self.project.setFileName(str(self.folder / "Private-project-63.qgz"))
        folder, manifest = self.capture([layer])
        text = (folder / "diagnostyka" / "diagnostyka.jsonl").read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        self.assertFalse(manifest["cancelled"])
        workers = [row["details"] for row in rows if row["event"] == "worker_event"]
        samples = [
            row for row in [*rows, *workers] if row["event"] == "performance_sample"
        ]
        self.assertEqual({row["role"] for row in samples}, {"main", "worker"})
        for row in samples:
            self.assertIn("phase", row)
            self.assertIn("process_cpu_seconds", row["counters"])
            self.assertIn("process_io", row["counters"])
            self.assertIn("process_memory", row["counters"])
        phases = [
            row for row in [*rows, *workers] if row["event"] == "performance_phase"
        ]
        self.assertTrue(any(row["phase"] == "render" for row in phases))
        plan = next(row for row in rows if row["event"] == "archive_plan")
        self.assertEqual(plan["selected_layers"], 1)
        self.assertGreater(plan["bounding_width"], 0)
        job = plan["layers"][0]["job"]
        summary = next(row for row in rows if row["event"] == "layer_summary")
        self.assertEqual(summary["job"], job)
        record = next(item for item in manifest["layers"] if item["id"] == layer.id())
        self.assertEqual(summary["status"], record["status"])
        self.assertEqual(summary["tile_count"], record["tile_count"])
        self.assertTrue(summary["timing_seconds"])
        self.assertTrue(any(row["event"] == "scheduler_sample" for row in rows))
        intervals = [row for row in workers if row["event"] == "network_interval"]
        self.assertTrue(intervals)
        self.assertTrue(any(row["count"] > 0 for row in intervals))
        self.assertTrue(any(row["context"] == job for row in intervals))
        self.assertFalse(
            any(
                row["event"] in ("performance_probe_error", "scheduler_probe_error")
                for row in [*rows, *workers]
            )
        )
        self.assertEqual(rows[-1]["event"], "archive_end")
        for secret in (
            str(self.folder),
            "Private-project-63",
            "Private-user-layer-79",
            "http://",
        ):
            self.assertNotIn(secret, text)
