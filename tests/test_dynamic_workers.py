# SPDX-License-Identifier: GPL-2.0-only

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
        memory = [2 * gib]
        observed = Condition()
        started = []
        running = set()
        peak = [0]
        release = {name: Event() for name in ("a", "b", "c", "d")}

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
                side_effect=lambda **kwargs: memory[0],
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
                        workers.condition.wait_for(lambda: workers.workers == 3, 2)
                    )
                with observed:
                    self.assertTrue(observed.wait_for(lambda: len(running) == 3, 2))
                    self.assertFalse(observed.wait_for(lambda: len(started) > 3, 0.1))

                memory[0], clock[0] = gib // 2, 10.0
                with workers.condition:
                    self.assertTrue(
                        workers.condition.wait_for(lambda: not workers.memory_ok, 2)
                    )
                self.assertEqual(workers.workers, 3)
                self.assertFalse(workers.stop.is_set())
                self.assertTrue(futures["a"].running())
                self.assertTrue(futures["b"].running())
                self.assertTrue(futures["c"].running())
                for name in ("a", "b", "c"):
                    release[name].set()
                    self.assertEqual(futures[name].result(2), {"status": "saved"})
                self.assertFalse(futures["d"].running())
                self.assertFalse(futures["d"].done())
                with observed:
                    self.assertFalse(observed.wait_for(lambda: len(started) > 3, 0.1))

                memory[0], clock[0] = 7 * gib // 4, 15.0
                with observed:
                    self.assertTrue(observed.wait_for(lambda: len(started) == 4, 2))
                self.assertEqual(workers.workers, 1)
                self.assertEqual(peak[0], 3)
                release["d"].set()
                self.assertEqual(futures["d"].result(2), {"status": "saved"})
                self.assertFalse(workers.coordinator_failed)
                self.assertEqual(
                    [event["budget"] for event in workers.memory_history], [3, 3, 1]
                )
            finally:
                for event in release.values():
                    event.set()
                workers.__exit__()

    def test_one_host_grows_past_two_without_reusing_a_memory_sample(self):
        clock = [0.0]
        memory = [4999708672]
        release = {name: Event() for name in ("a", "b", "c", "d")}
        started = []
        with (
            TemporaryDirectory() as temporary,
            patch(
                "mbtiles_batch_exporter.parallel_archive.time.monotonic",
                side_effect=lambda: clock[0],
            ),
            patch(
                "mbtiles_batch_exporter.parallel_archive.available_memory",
                side_effect=lambda **kwargs: memory[0],
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
                workers=2,
                cpu=4,
                adaptive=True,
            )

            def run(folder):
                with workers.condition:
                    started.append(folder.name)
                    workers.jobs[folder.name]["state"]["running"] = True
                    workers.jobs[folder.name]["state"]["memory"] = {
                        "rss": 640 * 1024**2,
                        "peak": 640 * 1024**2,
                    }
                    workers.condition.notify_all()
                if not release[folder.name].wait(10):
                    raise TimeoutError("The test did not release a map job")
                return {"status": "saved"}

            workers._run = run
            futures = {}
            try:
                for name in release:
                    folder = workers.folder / name
                    folder.mkdir()
                    workers._register("one-server", folder)
                    future = futures[name] = Future()
                    workers.queue.append(("one-server", future, folder))
                policy = workers.policies["one-server"]
                workers.coordinator = Thread(target=workers._coordinate)
                workers.coordinator.start()
                for _ in range(workers.ceiling):
                    workers.pool.submit(workers._work_loop)
                with workers.condition:
                    self.assertTrue(
                        workers.condition.wait_for(lambda: len(started) == 1, 2)
                    )
                    self.assertEqual(policy.limit, 1)
                    # A ready worker can be sampled between outcome and before:
                    # neither flag is set, but it has already rendered tiles.
                    workers.jobs["a"]["state"]["running"] = False
                    workers.jobs["a"]["counts"]["0"] = 30
                    policy.success(30, 15.0, policy.generation)
                    clock[0] = 15.0
                    self.assertTrue(
                        workers.condition.wait_for(lambda: len(started) == 2, 2)
                    )
                    self.assertEqual(policy.limit, 2)

                    # Existing processes have already reduced MemAvailable.
                    memory[0], clock[0] = int(2.6 * 1024**3), 20.0
                    self.assertTrue(
                        workers.condition.wait_for(
                            lambda: workers.next_memory_check == 25.0, 2
                        )
                    )
                    self.assertEqual(workers.workers, 3)
                    policy.success(60, 30.0, policy.generation)
                    clock[0] = 30.0
                    self.assertTrue(
                        workers.condition.wait_for(lambda: len(started) == 3, 2)
                    )
                    self.assertEqual(policy.limit, 3)
                    self.assertFalse(policy.frozen)
                    self.assertEqual(workers.launch_slots, 0)

                release["a"].set()
                self.assertEqual(futures["a"].result(2), {"status": "saved"})
                with workers.condition:
                    # A completed job cannot spend the same RAM sample again.
                    self.assertEqual(workers.active_hosts["one-server"], 2)
                    self.assertFalse(
                        workers.condition.wait_for(lambda: len(started) > 3, 0.6)
                    )
                    self.assertFalse(futures["d"].running())
                    clock[0] = 35.0
                    self.assertTrue(
                        workers.condition.wait_for(lambda: len(started) == 4, 2)
                    )
                    self.assertEqual(workers.launch_slots, 0)
                    self.assertEqual(workers.active_hosts["one-server"], 3)
                for event in release.values():
                    event.set()
                for future in futures.values():
                    self.assertEqual(future.result(2), {"status": "saved"})
                self.assertEqual([event["limit"] for event in policy.history], [2, 3])
                self.assertFalse(workers.coordinator_failed)
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
