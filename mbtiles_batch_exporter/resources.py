# SPDX-License-Identifier: GPL-2.0-only

"""Conservative process budget from native OS resources; no speed-test traffic."""

import ctypes
import os
import sys
from pathlib import Path

from qgis.PyQt.QtNetwork import QNetworkConfigurationManager

MAX_WORKERS = 32
MEMORY_RESERVE = 768 * 1024**2
MEMORY_PER_WORKER = 1024**3
MIN_WORKER_MEMORY = 384 * 1024**2


def available_memory():
    """Currently available bytes, or None when the platform cannot report them."""
    try:
        if sys.platform.startswith("linux"):
            values = dict(
                line.split(":", 1)
                for line in Path("/proc/meminfo").read_text().splitlines()
            )
            return int(values["MemAvailable"].split()[0]) * 1024
        if sys.platform == "win32":

            class MemoryStatus(ctypes.Structure):
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

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.available
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    return None


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

            class MemoryCounters(ctypes.Structure):
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

            current_process = ctypes.windll.kernel32.GetCurrentProcess
            current_process.argtypes = []
            current_process.restype = ctypes.c_void_p
            memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            memory_info.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(MemoryCounters),
                ctypes.c_uint32,
            ]
            memory_info.restype = ctypes.c_int
            counters = MemoryCounters()
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
    manager = QNetworkConfigurationManager()
    return {"cpu": cpu, "memory": available_memory(), "online": manager.isOnline()}
