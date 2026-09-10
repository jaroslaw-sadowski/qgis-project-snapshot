"""Conservative process budget from native OS resources; no speed-test traffic."""

import ctypes
import os
import sys
from pathlib import Path

from qgis.PyQt.QtNetwork import QNetworkConfigurationManager

MAX_WORKERS = 32


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
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
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


def recommend(cpu, memory, online, per_server=2, hosts=None):
    # Reserve room for the main QGIS and allow 1 GiB per additional process.
    memory_limit = (
        max(1, int((memory - 2 * 1024**3) // 1024**3)) if memory is not None else 2
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
