"""Exercise measured RAM budgets through real coordinator and supervisor threads."""

import unittest
from concurrent.futures import Future
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch

import test_archive as fixtures

from mbtiles_batch_exporter.adaptive import PROTOCOL, write_state
from mbtiles_batch_exporter.parallel_archive import RasterWorkers

MIB = 1024**2
GIB = 1024**3


class MeasuredWorkerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(fixtures.APP)
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.clock = 0.0
        self.memory = int(2.2 * GIB)
        self.started = []
        self.samples = {}
        self.account_rss = False
        self.release = Event()
        self.futures = {}
        for target, value in (
            ("time.monotonic", lambda: self.clock),
            ("available_memory", lambda: self.memory),
        ):
            mocked = patch(
                "mbtiles_batch_exporter.parallel_archive." + target,
                side_effect=value,
            )
            mocked.start()
            self.addCleanup(mocked.stop)
        self.workers = RasterWorkers(
            None,
            Path(temporary.name),
            None,
            [],
            None,
            None,
            [],
            workers=1,
            cpu=4,
            adaptive=True,
        )
        self.addCleanup(self._finish)
        self.workers._run = self._run

    def _finish(self):
        self.release.set()
        self.workers.__exit__()

    def _run(self, folder):
        with self.workers.condition:
            self.started.append(folder.name)
            sample = self.samples.get(folder.name)
            if sample is not None:
                if self.account_rss:
                    self.memory -= sample
                self._publish(folder.name, sample)
            self.workers.condition.notify_all()
        if not self.release.wait(20):
            raise TimeoutError("The test did not release a map job")
        return {"status": "saved"}

    def _publish(self, name, rss, peak=None, count=1, generation=None):
        job = self.workers.jobs[name]
        if generation is None:
            generation = self.workers.policies[job["host"]].generation
        write_state(
            job["folder"] / "telemetry.json",
            {
                "version": PROTOCOL,
                "waiting": True,
                "running": False,
                "counts": {str(generation): count},
                "events": [],
                "memory": {"rss": rss, "peak": rss if peak is None else peak},
            },
        )

    def _start(self, jobs):
        for name, host in jobs:
            folder = self.workers.folder / name
            folder.mkdir()
            self.workers._register(host, folder)
            future = self.futures[name] = Future()
            self.workers.queue.append((host, future, folder))
        self.workers.coordinator = Thread(target=self.workers._coordinate)
        self.workers.coordinator.start()
        for _ in range(self.workers.ceiling):
            self.workers.pool.submit(self.workers._work_loop)

    def _wait_started(self, count):
        with self.workers.condition:
            self.assertTrue(
                self.workers.condition.wait_for(lambda: len(self.started) >= count, 3),
                self.started,
            )
            self.assertEqual(len(self.started), count)

    def _advance(self, now):
        with self.workers.condition:
            self.clock = now
            self.assertTrue(
                self.workers.condition.wait_for(
                    lambda: self.workers.next_memory_check > now, 3
                )
            )
            self.assertFalse(self.workers.coordinator_failed)

    def test_one_server_reaches_three_with_2_2_gib_and_305_mib_workers(self):
        sample = 305 * MIB
        self.memory += sample
        self.samples = {name: sample for name in "abcd"}
        self.account_rss = True
        self._start([(name, "one-server") for name in "abcd"])
        self._wait_started(1)
        self._advance(5)
        self.assertEqual(self.workers.worker_memory, sample * 3 // 2)
        self.assertEqual(self.workers.workers, 3)

        with self.workers.condition:
            self._publish("a", sample, count=31)
        self._advance(15)
        self._wait_started(2)
        self._advance(20)
        with self.workers.condition:
            self._publish("a", sample, count=61)
            self._publish("b", sample, count=61)
        self._advance(30)
        self._wait_started(3)
        self._advance(35)

        self.assertEqual(self.workers.active_hosts["one-server"], 3)
        self.assertEqual(self.workers.policies["one-server"].limit, 3)
        self.assertEqual(self.workers.launch_slots, 0)
        self.assertFalse(self.futures["d"].running())
        self.assertEqual(
            [event["limit"] for event in self.workers.policies["one-server"].history],
            [2, 3],
        )

    def test_slow_startups_keep_their_reservation_across_ram_samples(self):
        self.memory = 3 * GIB + 256 * MIB
        self._start([(name, name) for name in "abcde"])
        self._wait_started(2)
        for now in (5, 10, 15):
            self._advance(now)
            self.assertEqual(len(self.started), 2)
            self.assertEqual(self.workers.worker_memory, GIB)
            self.assertEqual(self.workers.reserved_growth, 2 * GIB)
            self.assertEqual(self.workers.launch_slots, 0)
        self.assertTrue(self.futures["a"].running())
        self.assertTrue(self.futures["b"].running())
        self.assertFalse(self.futures["c"].running())

    def test_released_rss_keeps_peak_and_reserves_future_regrowth(self):
        self.samples = {"a": 400 * MIB}
        self._start([("a", "one-server")])
        self._wait_started(1)
        self._advance(5)
        before = self.workers.reserved_growth
        self.assertEqual(self.workers.worker_memory, 600 * MIB)
        with self.workers.condition:
            self.memory += 300 * MIB
            self._publish("a", 100 * MIB, peak=400 * MIB, count=2)
        self._advance(10)
        self.assertEqual(self.workers.worker_memory, 600 * MIB)
        self.assertEqual(self.workers.worker_peak_memory, 400 * MIB)
        self.assertEqual(self.workers.reserved_growth, before + 300 * MIB)

    def test_main_qgis_memory_is_excluded_from_process_estimate(self):
        folder = self.workers.folder / "local_main"
        folder.mkdir()
        self.workers._register("authenticated-server", folder)
        self.workers.jobs[folder.name]["active"] = True
        self._publish(folder.name, 2 * GIB)
        self.samples = {"a": 305 * MIB}
        self._start([("a", "one-server")])
        self._wait_started(1)
        self._advance(5)
        self.assertEqual(self.workers.worker_peak_memory, 305 * MIB)
        self.assertEqual(self.workers.worker_memory, 305 * MIB * 3 // 2)
        self.assertEqual(self.workers.reserved_growth, 305 * MIB // 2)

    def test_unknown_resources_keep_fallback_and_two_process_limit(self):
        self.memory = None
        self._start([(name, name) for name in "abcd"])
        self._wait_started(2)
        for now in (5, 10):
            self._advance(now)
            self.assertEqual(self.workers.worker_memory, GIB)
            self.assertEqual(self.workers.workers, 2)
            self.assertEqual(len(self.started), 2)
            self.assertEqual(self.workers.launch_slots, 0)

    def test_rising_process_memory_stops_new_starts_and_keeps_active_jobs(self):
        self.memory = 2 * GIB + 768 * MIB
        self.samples = {name: 305 * MIB for name in "abc"}
        self._start([(name, name) for name in "abc"])
        self._wait_started(2)
        with self.workers.condition:
            self.memory = 900 * MIB
            for name in "ab":
                self._publish(name, 900 * MIB, count=2)
        self._advance(5)
        self.assertEqual(self.workers.worker_memory, 1350 * MIB)
        self.assertEqual(self.workers.launch_slots, 0)
        self.assertEqual(len(self.started), 2)
        self.assertFalse(self.workers.stop.is_set())
        self.assertTrue(self.futures["a"].running())
        self.assertTrue(self.futures["b"].running())
        self.assertFalse(self.futures["c"].running())
