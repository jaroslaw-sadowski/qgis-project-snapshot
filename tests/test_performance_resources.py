# SPDX-License-Identifier: GPL-2.0-only

"""Native performance accounting, units, isolation and unsupported platforms."""

import ctypes
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mbtiles_batch_exporter.resources import available_memory, performance_counters


class PerformanceResourceTests(unittest.TestCase):
    def test_native_cpu_and_io_increase_without_qt_or_network(self):
        with patch(
            "mbtiles_batch_exporter.resources.QNetworkConfigurationManager"
        ) as qt:
            first = performance_counters()
            sum(value * value for value in range(200_000))
            with tempfile.TemporaryFile() as stream:
                stream.write(b"x" * 1024**2)
                stream.flush()
                stream.seek(0)
                self.assertEqual(len(stream.read()), 1024**2)
            second = performance_counters()
            qt.assert_not_called()
        json.dumps(second, allow_nan=False)
        self.assertGreater(second["monotonic_seconds"], first["monotonic_seconds"])
        self.assertGreater(second["process_cpu_seconds"], first["process_cpu_seconds"])
        self.assertEqual(second["logical_cpu_count"], os.cpu_count())
        if sys.platform.startswith("linux") or sys.platform == "win32":
            self.assertGreater(second["process_memory"]["rss"], 0)
            memory = second["system_memory"]
            self.assertGreater(memory["total_bytes"], memory["available_bytes"])
            cpu = second["system_cpu"]
            self.assertGreaterEqual(cpu["total_seconds"], cpu["idle_seconds"])
            fields = (
                ("rchar", "wchar")
                if sys.platform.startswith("linux")
                else ("read_bytes", "write_bytes")
            )
            for field in fields:
                self.assertGreaterEqual(
                    second["process_io"][field] - first["process_io"][field], 1024**2
                )

    def test_linux_cpu_avoids_counting_guest_and_iowait_as_busy(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "linux"),
            patch("mbtiles_batch_exporter.resources.os.sysconf", return_value=100),
            patch(
                "mbtiles_batch_exporter.resources.Path.open",
                return_value=io.StringIO("cpu 100 20 30 400 50 6 7 8 90 10\n"),
            ),
            patch("mbtiles_batch_exporter.resources.process_memory", return_value={}),
            patch("mbtiles_batch_exporter.resources._process_io", return_value=None),
            patch("mbtiles_batch_exporter.resources._system_memory", return_value=None),
        ):
            cpu = performance_counters()["system_cpu"]
        self.assertEqual(cpu["scope"], "all_logical_cpus")
        self.assertEqual(cpu["total_seconds"], 6.21)
        self.assertEqual(cpu["idle_seconds"], 4.5)
        self.assertEqual(cpu["iowait_seconds"], 0.5)

    def test_linux_memory_extra_fields_do_not_change_available_budget(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "linux"),
            patch(
                "mbtiles_batch_exporter.resources.Path.read_text",
                return_value=(
                    "MemTotal: 16777216 kB\nMemAvailable: 1234 kB\n"
                    "SwapTotal: 0 kB\nSwapFree: 0 kB\nCommitLimit: invalid\n"
                ),
            ),
            patch("mbtiles_batch_exporter.resources._system_cpu", return_value=None),
        ):
            memory = performance_counters()["system_memory"]
            self.assertEqual(available_memory(), 1234 * 1024)
            self.assertEqual(available_memory(include_commit=True), 1234 * 1024)
        self.assertEqual(memory["total_bytes"], 16 * 1024**3)
        self.assertEqual(memory["swap_total_bytes"], 0)
        self.assertEqual(memory["swap_free_bytes"], 0)
        self.assertIsNone(memory["commit_limit_bytes"])
        self.assertIsNone(memory["committed_as_bytes"])

    def test_windows_low_commit_limits_budget_without_changing_reported_ram(self):
        commit = [325 * 1024**2]
        ram = 4 * 1024**3

        def memory_status(output):
            native = output._obj
            self.assertEqual(native.length, 64)
            native.available = ram
            native.page_available = commit[0]
            return 1

        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "win32"),
            patch("mbtiles_batch_exporter.resources.ctypes.windll", create=True) as dll,
        ):
            dll.kernel32.GlobalMemoryStatusEx.side_effect = memory_status
            for value, expected in (
                (325 * 1024**2, 325 * 1024**2),
                (0, 0),
                (8 * 1024**3, ram),
            ):
                with self.subTest(commit=value):
                    commit[0] = value
                    self.assertEqual(available_memory(), ram)
                    self.assertEqual(available_memory(include_commit=True), expected)

    def test_unavailable_or_invalid_commit_keeps_physical_memory_budget(self):
        memory = {"available_bytes": 4 * 1024**3}
        with patch(
            "mbtiles_batch_exporter.resources._system_memory", return_value=memory
        ):
            self.assertEqual(
                available_memory(include_commit=True), memory["available_bytes"]
            )
            for value in (None, -1, True, "325", 3.5, float("nan"), float("inf")):
                with self.subTest(commit=value):
                    memory["process_commit_available_bytes"] = value
                    self.assertEqual(
                        available_memory(include_commit=True), memory["available_bytes"]
                    )

    def test_missing_physical_memory_does_not_use_commit_as_a_replacement(self):
        for sample in (
            None,
            {},
            {"process_commit_available_bytes": 8 * 1024**3},
            {"available_bytes": None, "process_commit_available_bytes": 0},
        ):
            with (
                self.subTest(sample=sample),
                patch(
                    "mbtiles_batch_exporter.resources._system_memory",
                    return_value=sample,
                ),
            ):
                self.assertIsNone(available_memory())
                self.assertIsNone(available_memory(include_commit=True))

    def test_linux_swap_and_overcommit_are_not_windows_commit_headroom(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "linux"),
            patch(
                "mbtiles_batch_exporter.resources.Path.read_text",
                return_value=(
                    "MemTotal: 16777216 kB\nMemAvailable: 4194304 kB\n"
                    "SwapTotal: 0 kB\nSwapFree: 0 kB\nCommitLimit: 1048576 kB\n"
                    "Committed_AS: 8388608 kB\n"
                ),
            ),
        ):
            self.assertEqual(available_memory(include_commit=True), 4 * 1024**3)

    def test_linux_io_preserves_large_counters_and_storage_semantics(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "linux"),
            patch(
                "mbtiles_batch_exporter.resources.Path.read_text",
                return_value=(
                    "rchar: 90000000000\nwchar: 80000000000\n"
                    "syscr: 30\nsyscw: 40\nread_bytes: 5000000000\n"
                    "write_bytes: 6000000000\ncancelled_write_bytes: 4096\n"
                ),
            ),
        ):
            measured = performance_counters(include_system=False)["process_io"]
        self.assertEqual(measured["source"], "proc_self_io")
        self.assertEqual(measured["byte_scope"], "storage_layer")
        self.assertEqual(measured["accounting_scope"], "process_and_reaped_children")
        self.assertEqual(measured["read_bytes"], 5_000_000_000)
        self.assertEqual(measured["write_bytes"], 6_000_000_000)
        self.assertEqual(measured["rchar"], 90_000_000_000)
        self.assertEqual(measured["wchar"], 80_000_000_000)
        self.assertEqual(measured["cancelled_write_bytes"], 4096)

    def test_windows_native_layout_and_64_bit_counters(self):
        handle = (1 << (ctypes.sizeof(ctypes.c_void_p) * 8)) - 1

        def memory_status(output):
            native = output._obj
            self.assertEqual(native.length, 64)
            native.total = 16 * 1024**3
            native.available = 4 * 1024**3
            native.page_total = 24 * 1024**3
            native.page_available = 6 * 1024**3
            return 1

        def process_memory(process, output, size):
            self.assertEqual(process, handle)
            native = output._obj
            self.assertEqual(native.size, size)
            native.working_set = 200 * 1024**2
            native.peak_working_set = 300 * 1024**2
            return 1

        def process_io(process, output):
            self.assertEqual(process, handle)
            native = output._obj
            self.assertEqual(ctypes.sizeof(native), 48)
            self.assertEqual(type(native).read_bytes.offset, 24)
            native.read_bytes = 5 * 1024**3
            native.write_bytes = 6 * 1024**3
            native.other_bytes = 100
            native.read_operations = 7
            native.write_operations = 8
            native.other_operations = 9
            return 1

        def system_times(idle, kernel, user):
            for pointer, seconds in ((idle, 700), (kernel, 900), (user, 400)):
                native = pointer._obj
                self.assertEqual(ctypes.sizeof(native), 8)
                native.low = (seconds * 10_000_000) & 0xFFFFFFFF
                native.high = (seconds * 10_000_000) >> 32
            return 1

        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "win32"),
            patch("mbtiles_batch_exporter.resources.ctypes.windll", create=True) as dll,
        ):
            dll.kernel32.GetCurrentProcess.return_value = handle
            dll.kernel32.GlobalMemoryStatusEx.side_effect = memory_status
            dll.psapi.GetProcessMemoryInfo.side_effect = process_memory
            dll.kernel32.GetProcessIoCounters.side_effect = process_io
            dll.kernel32.GetSystemTimes.side_effect = system_times
            counters = performance_counters()
            self.assertIs(dll.kernel32.GetCurrentProcess.restype, ctypes.c_void_p)
            self.assertIs(
                dll.kernel32.GetProcessIoCounters.argtypes[0], ctypes.c_void_p
            )
            self.assertIs(dll.kernel32.GetProcessIoCounters.restype, ctypes.c_int)
            self.assertIs(dll.kernel32.GetSystemTimes.restype, ctypes.c_int)
            self.assertEqual(available_memory(), 4 * 1024**3)
            dll.kernel32.OpenProcess.assert_not_called()
            dll.kernel32.CloseHandle.assert_not_called()
        self.assertEqual(counters["process_memory"]["rss"], 200 * 1024**2)
        cpu = counters["system_cpu"]
        self.assertEqual(cpu["total_seconds"], 1300)
        self.assertEqual(cpu["idle_seconds"], 700)
        self.assertEqual(cpu["scope"], "current_processor_group")
        memory = counters["system_memory"]
        self.assertEqual(memory["total_bytes"], 16 * 1024**3)
        self.assertEqual(memory["process_commit_limit_bytes"], 24 * 1024**3)
        self.assertEqual(memory["process_commit_available_bytes"], 6 * 1024**3)
        self.assertNotIn("swap_total_bytes", memory)
        measured = counters["process_io"]
        self.assertEqual(measured["byte_scope"], "all_io_transfers")
        self.assertEqual(measured["accounting_scope"], "process_only")
        self.assertEqual(measured["read_bytes"], 5 * 1024**3)
        self.assertEqual(measured["write_bytes"], 6 * 1024**3)
        self.assertEqual(measured["other_bytes"], 100)

    def test_windows_failed_sensors_do_not_remove_process_cpu(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "win32"),
            patch("mbtiles_batch_exporter.resources.ctypes.windll", create=True) as dll,
        ):
            functions = (
                dll.kernel32.GetSystemTimes,
                dll.kernel32.GetProcessIoCounters,
                dll.kernel32.GlobalMemoryStatusEx,
                dll.psapi.GetProcessMemoryInfo,
            )
            for failure in (False, True):
                for function in functions:
                    function.return_value = 0
                    function.side_effect = OSError("unavailable") if failure else None
                measured = performance_counters()
                self.assertGreater(measured["process_cpu_seconds"], 0)
                self.assertEqual(
                    measured["process_memory"], {"rss": None, "peak": None}
                )
                for field in ("system_cpu", "system_memory", "process_io"):
                    self.assertIsNone(measured[field])

    def test_worker_omits_system_readings(self):
        with (
            patch("mbtiles_batch_exporter.resources._system_cpu") as cpu,
            patch("mbtiles_batch_exporter.resources._system_memory") as memory,
        ):
            measured = performance_counters(include_system=False)
            self.assertIsNone(measured["system_cpu"])
            self.assertIsNone(measured["system_memory"])
            self.assertGreater(measured["process_cpu_seconds"], 0)
            cpu.assert_not_called()
            memory.assert_not_called()

    def test_unavailable_linux_io_does_not_remove_other_counters(self):
        native_linux = sys.platform.startswith("linux")
        read_text = Path.read_text

        def read(path):
            if str(path) == "/proc/self/io":
                raise OSError("unavailable")
            return read_text(path)

        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "linux"),
            patch(
                "mbtiles_batch_exporter.resources.Path.read_text",
                autospec=True,
                side_effect=read,
            ),
            patch("mbtiles_batch_exporter.resources.time.process_time", return_value=0),
        ):
            measured = performance_counters()
            self.assertIsNone(measured["process_io"])
            self.assertEqual(measured["process_cpu_seconds"], 0)
            if native_linux:
                self.assertGreater(measured["system_memory"]["total_bytes"], 0)

    def test_unsupported_native_metrics_are_none(self):
        with patch("mbtiles_batch_exporter.resources.sys.platform", "unsupported"):
            measured = performance_counters()
        self.assertGreater(measured["process_cpu_seconds"], 0)
        for field in ("system_memory", "system_cpu", "process_io"):
            self.assertIsNone(measured[field])

    def test_failed_process_clock_keeps_other_native_readings(self):
        with patch(
            "mbtiles_batch_exporter.resources.time.process_time", side_effect=OSError
        ):
            measured = performance_counters()
        self.assertIsNone(measured["process_cpu_seconds"])
        self.assertGreater(measured["monotonic_seconds"], 0)


if __name__ == "__main__":
    unittest.main()
