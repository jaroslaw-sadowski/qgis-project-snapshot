"""Native process memory measurement, platform units and unavailable readings."""

import ctypes
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mbtiles_batch_exporter.resources import process_memory


class MemoryProbeTests(unittest.TestCase):
    def test_native_peak_is_positive_and_does_not_fall(self):
        first = process_memory()
        self.assertIsInstance(first["peak"], int)
        self.assertGreater(first["peak"], 0)
        if sys.platform.startswith("linux") or sys.platform == "win32":
            self.assertIsInstance(first["rss"], int)
            self.assertGreater(first["rss"], 0)
            self.assertGreaterEqual(first["peak"], first["rss"])
        self.assertGreaterEqual(process_memory()["peak"], first["peak"])

    def test_linux_reads_current_and_peak_of_own_process_in_bytes(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "linux"),
            patch(
                "mbtiles_batch_exporter.resources.Path.read_text", autospec=True
            ) as read,
        ):
            read.return_value = "Name:\tpython\nVmRSS:\t320000 kB\nVmHWM:\t420000 kB\n"
            self.assertEqual(
                process_memory(), {"rss": 320000 * 1024, "peak": 420000 * 1024}
            )
            read.assert_called_once_with(Path("/proc/self/status"))

    def test_linux_failed_or_invalid_readings_are_unavailable(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "linux"),
            patch("mbtiles_batch_exporter.resources.Path.read_text") as read,
        ):
            for contents in (
                "VmRSS:\t0 kB\nVmHWM:\t0 kB\n",
                "VmRSS:\t-1 kB\nVmHWM:\t-1 kB\n",
                "VmRSS:\tinvalid\nVmHWM:\t320000 kB\n",
                "VmRSS:\t320000 kB\n",
                "VmRSS:\nVmHWM:\n",
                "malformed",
            ):
                with self.subTest(contents=contents):
                    read.return_value = contents
                    self.assertEqual(process_memory(), {"rss": None, "peak": None})
            read.side_effect = OSError("unavailable")
            self.assertEqual(process_memory(), {"rss": None, "peak": None})

    def test_unix_peak_uses_own_process_and_platform_units(self):
        native = SimpleNamespace(
            RUSAGE_SELF=0,
            getrusage=Mock(return_value=SimpleNamespace(ru_maxrss=320000)),
        )
        for platform, expected in (("freebsd", 320000 * 1024), ("darwin", 320000)):
            with (
                self.subTest(platform=platform),
                patch("mbtiles_batch_exporter.resources.sys.platform", platform),
                patch.dict(sys.modules, resource=native),
            ):
                self.assertEqual(process_memory(), {"rss": None, "peak": expected})
                native.getrusage.assert_called_with(native.RUSAGE_SELF)

    def test_unix_failed_or_invalid_readings_are_unavailable(self):
        native = SimpleNamespace(RUSAGE_SELF=0, getrusage=Mock())
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "darwin"),
            patch.dict(sys.modules, resource=native),
        ):
            for value in (0, -1, None, "invalid", float("nan"), float("inf")):
                with self.subTest(value=value):
                    native.getrusage.return_value = SimpleNamespace(ru_maxrss=value)
                    self.assertEqual(process_memory(), {"rss": None, "peak": None})
            native.getrusage.side_effect = OSError("unavailable")
            self.assertEqual(process_memory(), {"rss": None, "peak": None})
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "darwin"),
            patch.dict(sys.modules, resource=None),
        ):
            self.assertEqual(process_memory(), {"rss": None, "peak": None})

    def test_windows_peak_preserves_handle_and_size_t_width(self):
        pointer_size = ctypes.sizeof(ctypes.c_void_p)
        handle = (1 << (pointer_size * 8)) - 1
        peak = 5 * 1024**3 if pointer_size == 8 else 700 * 1024**2

        def status(process, output, size):
            self.assertEqual(process, handle)
            native = output._obj
            self.assertEqual(size, 8 + 8 * pointer_size)
            self.assertEqual(native.size, size)
            self.assertEqual(type(native).peak_working_set.offset, 8)
            native.working_set = 200 * 1024**2
            native.peak_working_set = peak
            return 1

        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "win32"),
            patch("mbtiles_batch_exporter.resources.ctypes.windll", create=True) as dll,
        ):
            current_process = dll.kernel32.GetCurrentProcess
            current_process.return_value = handle
            memory_info = dll.psapi.GetProcessMemoryInfo
            memory_info.side_effect = status
            self.assertEqual(process_memory(), {"rss": 200 * 1024**2, "peak": peak})
            self.assertEqual(current_process.argtypes, [])
            self.assertIs(current_process.restype, ctypes.c_void_p)
            self.assertIs(memory_info.argtypes[0], ctypes.c_void_p)
            self.assertIs(memory_info.argtypes[2], ctypes.c_uint32)
            self.assertIs(memory_info.restype, ctypes.c_int)
            current_process.assert_called_once_with()
            dll.kernel32.OpenProcess.assert_not_called()
            dll.kernel32.CloseHandle.assert_not_called()

    def test_windows_failed_or_zero_readings_are_unavailable(self):
        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "win32"),
            patch("mbtiles_batch_exporter.resources.ctypes.windll", create=True) as dll,
        ):
            memory_info = dll.psapi.GetProcessMemoryInfo
            memory_info.return_value = 0
            self.assertEqual(process_memory(), {"rss": None, "peak": None})
            memory_info.return_value = 1
            self.assertEqual(process_memory(), {"rss": None, "peak": None})
            memory_info.side_effect = OSError("unavailable")
            self.assertEqual(process_memory(), {"rss": None, "peak": None})


if __name__ == "__main__":
    unittest.main()
