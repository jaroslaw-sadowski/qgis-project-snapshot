# SPDX-License-Identifier: GPL-2.0-only

"""Out-of-order completed maps must be merged and retained on cancellation."""

import json
import time
from concurrent.futures import Future
from hashlib import sha256
from threading import Event
from unittest.mock import patch

import test_adaptive as adaptive_fixtures
import test_raster_archive as fixtures
from qgis.PyQt.QtCore import QCoreApplication

from mbtiles_batch_exporter.archive import _ready_records
from mbtiles_batch_exporter.parallel_archive import RasterWorkers


class ReadyRecordTests(fixtures.unittest.TestCase):
    def test_ready_map_and_vector_bypass_slow_first_map(self):
        slow, ready = Future(), Future()
        ready.set_result({"status": "saved"})
        workers = type(
            "Workers",
            (),
            {
                "futures": {"slow": (slow, None), "ready": (ready, None)},
                "stop": Event(),
            },
        )()
        records = [{"id": x, "status": "pending"} for x in ("slow", "ready", "vector")]
        sequence = _ready_records(records, workers, lambda: False, lambda _: None)
        self.assertEqual(next(sequence)["id"], "ready")
        self.assertEqual(next(sequence)["id"], "vector")
        slow.set_result({"status": "saved"})
        self.assertEqual(next(sequence)["id"], "slow")

    def test_cancel_still_yields_completed_result_first(self):
        slow, ready = Future(), Future()
        ready.set_result({"status": "saved"})
        workers = type(
            "Workers",
            (),
            {
                "futures": {"slow": (slow, None), "ready": (ready, None)},
                "stop": Event(),
            },
        )()
        records = [{"id": x, "status": "pending"} for x in ("slow", "ready")]
        order = list(_ready_records(records, workers, lambda: True, lambda _: None))
        self.assertEqual([r["id"] for r in order], ["ready", "slow"])
        self.assertTrue(workers.stop.is_set())

    def test_cancel_waits_for_running_supervisor_to_publish_finished_result(self):
        finishing = Future()
        finishing.set_running_or_notify_cancel()
        workers = type(
            "Workers",
            (),
            {"futures": {"map": (finishing, None)}, "stop": Event()},
        )()

        def publish_result(_):
            self.assertTrue(workers.stop.is_set())
            finishing.set_result({"status": "saved"})

        record = {"id": "map", "status": "pending"}
        order = list(_ready_records([record], workers, lambda: True, publish_result))
        self.assertEqual(order, [record])
        self.assertTrue(finishing.done())
        self.assertEqual(finishing.result()["status"], "saved")


class ReadyWmsTests(fixtures.unittest.TestCase):
    setUp = fixtures.LocalWmsTests.setUp
    tearDown = fixtures.LocalWmsTests.tearDown
    start_server = fixtures.LocalWmsTests.start_server
    add_map = adaptive_fixtures.AdaptiveWmsTests.add_map
    capture = adaptive_fixtures.AdaptiveWmsTests.capture

    def test_cancel_before_merge_preserves_all_eight_completed_maps(self):
        layers = [
            self.add_map(host="127.0.0.1" if i % 2 else "localhost", name=f"Map {i}")
            for i in range(8)
        ]
        cancelled = Event()
        original = RasterWorkers.__enter__

        def enter(workers):
            result = original(workers)
            deadline = time.monotonic() + 30
            try:
                while not all(future.done() for future, _ in workers.futures.values()):
                    self.assertLess(time.monotonic(), deadline)
                    QCoreApplication.processEvents()
                    time.sleep(0.02)
                self.assertTrue(all(workers.completed(layer.id()) for layer in layers))
                self.assertFalse(workers.merged)
                cancelled.set()
                return result
            except Exception:
                workers.__exit__(None, None, None)
                raise

        with patch.object(RasterWorkers, "__enter__", enter):
            folder, manifest = self.capture(layers, cancelled=cancelled.is_set)
        self.assertTrue(manifest["cancelled"])
        self.assertEqual(manifest["parallel"]["completed_in_workers"], 8)
        self.assertFalse((folder / ".workers").exists())
        selected = {r["id"]: r for r in manifest["layers"]}
        with fixtures.closing(
            fixtures.sqlite3.connect(folder / "dane" / "dane.gpkg")
        ) as db:
            for layer in layers:
                record = selected[layer.id()]
                self.assertEqual(record["status"], "saved")
                self.assertGreater(
                    db.execute(f'SELECT count(*) FROM "{record["table"]}"').fetchone()[
                        0
                    ],
                    0,
                )
        self.assertTrue(manifest["local_layer_audit"]["passed"])

    def test_fast_map_is_saved_before_slow_map_and_survives_cancel(self):
        slow = self.add_map(name="Slow first")
        fast = self.add_map(host="localhost", name="Fast second")
        slow_job = "layer_" + sha256(slow.id().encode()).hexdigest()[:24]
        original = RasterWorkers._run
        cancelled = Event()
        order = []

        def run(workers, folder):
            if folder.name == slow_job:
                if not workers.stop.wait(8):
                    raise RuntimeError("Ready map blocked behind first map")
                raise InterruptedError()
            return original(workers, folder)

        def status(record, completed, total):
            if record["status"] in ("saved", "empty"):
                order.append(record["id"])
                if record["id"] == fast.id():
                    cancelled.set()

        with patch.object(RasterWorkers, "_run", run):
            folder, manifest = self.capture(
                [slow, fast], cancelled=cancelled.is_set, layer_status=status
            )
        selected = {r["id"]: r for r in manifest["layers"]}
        self.assertEqual(selected[fast.id()]["status"], "saved")
        self.assertEqual(selected[slow.id()]["status"], "cancelled")
        self.assertEqual(order, [fast.id()])
        self.assertTrue(manifest["cancelled"])
        self.assertEqual(manifest["parallel"]["completed_in_workers"], 1)
        self.assertFalse((folder / ".workers").exists())
        with fixtures.closing(
            fixtures.sqlite3.connect(folder / "dane" / "dane.gpkg")
        ) as db:
            self.assertGreater(
                db.execute(
                    f'SELECT count(*) FROM "{selected[fast.id()]["table"]}"'
                ).fetchone()[0],
                0,
            )
        diagnostics = [
            json.loads(line)
            for line in (folder / "diagnostyka" / "diagnostic.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertTrue(
            any(
                e["event"] == "layer_result" and e["status"] == "saved"
                for e in diagnostics
            )
        )
