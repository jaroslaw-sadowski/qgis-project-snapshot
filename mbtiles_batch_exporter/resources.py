# SPDX-License-Identifier: GPL-2.0-only

"""Native OS measurements and conservative budgets; no speed-test traffic."""

import ctypes
import os
import sys
import time
from pathlib import Path

from qgis.PyQt.QtNetwork import QNetworkInterface

MAX_WORKERS = 32
MEMORY_RESERVE = 768 * 1024**2
MEMORY_PER_WORKER = 1024**3
MIN_WORKER_MEMORY = 384 * 1024**2


# Stable ctypes types allow the sampler and scheduler to read concurrently.
class _MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
        (name, ctypes.c_ulonglong)
        for name in (
            "total",
            "available",
            "page_total",
            "page_available",
            "virtual_total",
            "virtual_available",
            "extended",
        )
    ]


class _MemoryCounters(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint32), ("faults", ctypes.c_uint32)] + [
        (name, ctypes.c_size_t)
        for name in (
            "peak_working_set",
            "working_set",
            "peak_paged_pool",
            "paged_pool",
            "peak_nonpaged_pool",
            "nonpaged_pool",
            "pagefile",
            "peak_pagefile",
        )
    ]


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_ulonglong)
        for name in (
            "read_operations",
            "write_operations",
            "other_operations",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


def _system_memory():
    """Native memory counters; Windows commit values are process-limited."""
    try:
        if sys.platform.startswith("linux"):
            values = dict(
                line.split(":", 1)
                for line in Path("/proc/meminfo").read_text().splitlines()
            )
            result = {"source": "proc_meminfo"}
            for field, native in (
                ("total_bytes", "MemTotal"),
                ("available_bytes", "MemAvailable"),
                ("swap_total_bytes", "SwapTotal"),
                ("swap_free_bytes", "SwapFree"),
                ("commit_limit_bytes", "CommitLimit"),
                ("committed_as_bytes", "Committed_AS"),
            ):
                try:
                    result[field] = int(values[native].split()[0]) * 1024
                except (ValueError, KeyError, IndexError):
                    result[field] = None
            return result
        if sys.platform == "win32":
            status = _MemoryStatus()
            status.length = ctypes.sizeof(status)
            memory_status = ctypes.windll.kernel32.GlobalMemoryStatusEx
            memory_status.argtypes = [ctypes.POINTER(_MemoryStatus)]
            memory_status.restype = ctypes.c_int
            if memory_status(ctypes.byref(status)):
                return {
                    "source": "GlobalMemoryStatusEx",
                    "total_bytes": status.total,
                    "available_bytes": status.available,
                    "process_commit_limit_bytes": status.page_total,
                    "process_commit_available_bytes": status.page_available,
                }
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def available_memory(*, include_commit=False):
    """Available RAM, optionally bounded by Windows process commit headroom."""
    memory = _system_memory()
    available = memory.get("available_bytes") if memory is not None else None
    if include_commit and available is not None:
        commit = memory.get("process_commit_available_bytes")
        if isinstance(commit, int) and not isinstance(commit, bool) and commit >= 0:
            return min(available, commit)
    return available


def process_memory():
    """Current and peak resident bytes of this process, with None if unavailable."""
    try:
        rss = None
        if sys.platform.startswith("linux"):
            values = dict(
                line.split(":", 1)
                for line in Path("/proc/self/status").read_text().splitlines()
            )
            rss = int(values["VmRSS"].split()[0]) * 1024
            peak = int(values["VmHWM"].split()[0]) * 1024
        elif sys.platform == "win32":
            current_process = ctypes.windll.kernel32.GetCurrentProcess
            current_process.argtypes = []
            current_process.restype = ctypes.c_void_p
            memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            memory_info.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(_MemoryCounters),
                ctypes.c_uint32,
            ]
            memory_info.restype = ctypes.c_int
            counters = _MemoryCounters()
            counters.size = ctypes.sizeof(counters)
            if not memory_info(
                current_process(), ctypes.byref(counters), counters.size
            ):
                return {"rss": None, "peak": None}
            rss = counters.working_set
            peak = counters.peak_working_set
        else:
            import resource

            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform != "darwin":
                peak *= 1024
        peak = int(peak)
        return {
            "rss": rss if rss is not None and rss > 0 else None,
            "peak": peak if peak > 0 else None,
        }
    except (
        ImportError,
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
        KeyError,
        IndexError,
    ):
        return {"rss": None, "peak": None}


def _system_cpu():
    """Cumulative CPU seconds; idle includes Linux I/O wait, also given separately.

    Windows reports all processors up to 64 logical CPUs, otherwise only the
    calling thread's processor group. Neither platform measures CPU frequency.
    """
    try:
        if sys.platform.startswith("linux"):
            with Path("/proc/stat").open() as stream:
                fields = stream.readline().split()
            if fields[0] != "cpu" or len(fields) < 9:
                return None
            ticks = os.sysconf("SC_CLK_TCK")
            values = [int(value) for value in fields[1:9]]
            # guest and guest_nice are already included in user and nice.
            return {
                "source": "proc_stat",
                "scope": "all_logical_cpus",
                "total_seconds": sum(values) / ticks,
                "idle_seconds": (values[3] + values[4]) / ticks,
                "iowait_seconds": values[4] / ticks,
            }
        if sys.platform == "win32":
            system_times = ctypes.windll.kernel32.GetSystemTimes
            system_times.argtypes = [ctypes.POINTER(_FileTime)] * 3
            system_times.restype = ctypes.c_int
            idle, kernel, user = _FileTime(), _FileTime(), _FileTime()
            if system_times(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            ):
                idle, kernel, user = (
                    ((value.high << 32) | value.low) / 10_000_000
                    for value in (idle, kernel, user)
                )
                return {
                    "source": "GetSystemTimes",
                    "scope": "current_processor_group",
                    "total_seconds": kernel + user,
                    "idle_seconds": idle,
                }
    except (
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        IndexError,
        ZeroDivisionError,
    ):
        pass
    return None


def _process_io():
    """Cumulative counters for this process, with explicit platform semantics.

    Linux read/write_bytes count storage-layer I/O; rchar/wchar include cache,
    pipes and terminals. Reaped children's I/O is included on Linux, so summing
    the parent's and children's counters would double count it. Windows counts
    this process's I/O transfers, not physical disk bytes. Neither platform
    measures disk busy time or link saturation here.
    """
    try:
        if sys.platform.startswith("linux"):
            values = dict(
                line.split(":", 1)
                for line in Path("/proc/self/io").read_text().splitlines()
            )
            return {
                "source": "proc_self_io",
                "byte_scope": "storage_layer",
                "accounting_scope": "process_and_reaped_children",
                "read_bytes": int(values["read_bytes"]),
                "write_bytes": int(values["write_bytes"]),
                "rchar": int(values["rchar"]),
                "wchar": int(values["wchar"]),
                "read_operations": int(values["syscr"]),
                "write_operations": int(values["syscw"]),
                "cancelled_write_bytes": int(values["cancelled_write_bytes"]),
            }
        if sys.platform == "win32":
            current_process = ctypes.windll.kernel32.GetCurrentProcess
            current_process.argtypes = []
            current_process.restype = ctypes.c_void_p
            io_counters = ctypes.windll.kernel32.GetProcessIoCounters
            io_counters.argtypes = [ctypes.c_void_p, ctypes.POINTER(_IoCounters)]
            io_counters.restype = ctypes.c_int
            counters = _IoCounters()
            if io_counters(current_process(), ctypes.byref(counters)):
                return {
                    "source": "GetProcessIoCounters",
                    "byte_scope": "all_io_transfers",
                    "accounting_scope": "process_only",
                    **{
                        name: getattr(counters, name)
                        for name, _type in _IoCounters._fields_
                    },
                }
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return None


def performance_counters(include_system=True):
    """Independent native readings as JSON data; unavailable counters stay None.

    CPU seconds include all threads of this process and exclude child processes.
    A caller can derive utilization and I/O rates from two monotonic samples;
    100% process CPU then means one fully occupied logical CPU. Workers may omit
    duplicate system readings. These counters never change scheduler policy.
    """
    try:
        cpu = time.process_time()
    except (OSError, ValueError):
        cpu = None
    return {
        "monotonic_seconds": time.monotonic(),
        "logical_cpu_count": os.cpu_count(),
        "process_cpu_seconds": cpu,
        "process_memory": process_memory(),
        "process_io": _process_io(),
        "system_cpu": _system_cpu() if include_system else None,
        "system_memory": _system_memory() if include_system else None,
    }


def recommend(
    cpu,
    memory,
    online,
    per_server=2,
    hosts=None,
    active_workers=0,
    worker_memory=MEMORY_PER_WORKER,
    reserved_growth=0,
):
    # Available RAM excludes current RSS, but not future growth or startup.
    memory_limit = (
        active_workers
        + max(0, int((memory - MEMORY_RESERVE - reserved_growth) // worker_memory))
        if memory is not None
        else 2
    )
    count = min(MAX_WORKERS, max(1, cpu * 2), memory_limit)
    if hosts is not None:
        count = min(count, sum(min(per_server, tasks) for tasks in hosts.values()) or 1)
    if not online:
        count = min(count, 2)
    return max(1, count)


def detect_resources():
    cpu = getattr(os, "process_cpu_count", os.cpu_count)() or 1
    if hasattr(os, "sched_getaffinity"):
        try:
            cpu = min(cpu, len(os.sched_getaffinity(0)))
        except OSError:
            pass
    # Interface availability is only a local hint, not an Internet/VPN probe.
    flags = QNetworkInterface.InterfaceFlag
    online = any(
        interface.flags() & flags.IsUp
        and interface.flags() & flags.IsRunning
        and not interface.flags() & flags.IsLoopBack
        for interface in QNetworkInterface.allInterfaces()
    )
    return {"cpu": cpu, "memory": available_memory(), "online": online}
