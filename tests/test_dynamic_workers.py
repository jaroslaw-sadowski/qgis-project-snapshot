"""Real supervisor threads with controlled RAM and disposable fake map jobs."""

import unittest
from concurrent.futures import Future
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Condition, Event, Thread
from unittest.mock import patch

import test_archive as fixtures

from mbtiles_batch_exporter.parallel_archive import RasterWorkers


class DynamicWorkerTests(unittest.TestCase):
    def test_recovered_ram_starts_parallel_jobs_and_drop_preserves_running_jobs(self):
        self.assertIsNotNone(fixtures.APP)
        gib = 1024**3
        clock = [0.0]
        memory = [4111540224]
        observed = Condition()
        started = []
        running = set()
        peak = [0]
        release = {name: Event() for name in ("a", "b", "c")}

        def run(folder):
            name = folder.name
            with observed:
                started.append(name)
                running.add(name)
                peak[0] = max(peak[0], len(running))
                observed.notify_all()
            try:
                if not release[name].wait(5):
                    raise TimeoutError("The test did not release a map job")
                return {"status": "saved"}
            finally:
                with observed:
                    running.remove(name)
                    observed.notify_all()

        with (
            TemporaryDirectory() as temporary,
            patch(
                "mbtiles_batch_exporter.parallel_archive.time.monotonic",
                side_effect=lambda: clock[0],
            ),
            patch(
                "mbtiles_batch_exporter.parallel_archive.available_memory",
                side_effect=lambda: memory[0],
            ),
        ):
            workers = RasterWorkers(
                None,
                Path(temporary),
                None,
                [],
                None,
                None,
                [],
                workers=1,
                cpu=2,
                adaptive=True,
            )
            workers._run = run
            futures = {}
            try:
                for name in release:
                    folder = workers.folder / name
                    folder.mkdir()
                    workers._register(name, folder)
                    future = futures[name] = Future()
                    workers.queue.append((name, future, folder))
                workers.coordinator = Thread(target=workers._coordinate)
                workers.coordinator.start()
                for _ in range(workers.ceiling):
                    workers.pool.submit(workers._work_loop)
                with observed:
                    self.assertTrue(observed.wait_for(lambda: len(started) == 1, 2))
                    self.assertFalse(observed.wait_for(lambda: len(started) > 1, 0.1))
                self.assertEqual(workers.workers, 1)

                memory[0], clock[0] = 4 * gib, 5.0
                with workers.condition:
                    self.assertTrue(
                        workers.condition.wait_for(lambda: workers.workers == 2, 2)
                    )
                with observed:
                    self.assertTrue(observed.wait_for(lambda: len(running) == 2, 2))
                    self.assertFalse(observed.wait_for(lambda: len(started) > 2, 0.1))

                memory[0], clock[0] = gib, 10.0
                with workers.condition:
                    self.assertTrue(
                        workers.condition.wait_for(lambda: not workers.memory_ok, 2)
                    )
                self.assertEqual(workers.workers, 1)
                self.assertFalse(workers.stop.is_set())
                self.assertTrue(futures["a"].running())
                self.assertTrue(futures["b"].running())
                for name in ("a", "b"):
                    release[name].set()
                    self.assertEqual(futures[name].result(2), {"status": "saved"})
                self.assertFalse(futures["c"].running())
                self.assertFalse(futures["c"].done())
                with observed:
                    self.assertFalse(observed.wait_for(lambda: len(started) > 2, 0.1))

                memory[0], clock[0] = 3 * gib, 15.0
                with observed:
                    self.assertTrue(observed.wait_for(lambda: len(started) == 3, 2))
                self.assertEqual(workers.workers, 1)
                self.assertEqual(peak[0], 2)
                release["c"].set()
                self.assertEqual(futures["c"].result(2), {"status": "saved"})
                self.assertFalse(workers.coordinator_failed)
                self.assertEqual(
                    [event["budget"] for event in workers.memory_history], [2, 1, 1]
                )
            finally:
                for event in release.values():
                    event.set()
                workers.__exit__()

    def test_fixed_mode_retains_requested_worker_count(self):
        all_running = Event()
        observed = Condition()
        started = []

        def run(folder):
            with observed:
                started.append(folder.name)
                if len(started) == 3:
                    all_running.set()
            if not all_running.wait(2):
                raise TimeoutError("Fixed mode did not start all three map jobs")
            return {"status": "saved"}

        with TemporaryDirectory() as temporary:
            workers = RasterWorkers(
                None,
                Path(temporary),
                None,
                [],
                None,
                None,
                [],
                workers=3,
                cpu=1,
                adaptive=False,
            )
            workers._run = run
            try:
                futures = []
                for name in ("a", "b", "c"):
                    future = Future()
                    futures.append(future)
                    workers.queue.append((name, future, workers.folder / name))
                for _ in range(workers.ceiling):
                    workers.pool.submit(workers._work_loop)
                for future in futures:
                    self.assertEqual(future.result(3), {"status": "saved"})
                self.assertCountEqual(started, ["a", "b", "c"])
                self.assertIsNone(workers.coordinator)
            finally:
                all_running.set()
                workers.__exit__()
