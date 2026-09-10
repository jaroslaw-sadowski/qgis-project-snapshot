"""Persistent structured diagnostics without source URLs or exception messages."""

import json
import logging
import os
import platform
import traceback
from datetime import datetime
from pathlib import Path
from threading import Lock


def exception_details(error):
    """Keep code locations and OS codes, never provider messages or local variables."""
    return {
        "type": type(error).__name__,
        "errno": getattr(error, "errno", None),
        "winerror": getattr(error, "winerror", None),
        "frames": [
            {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(error.__traceback__)
        ],
    }


class Diagnostics:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = Lock()
        self.write_failed = False

    def emit(self, event, **fields):
        row = {
            "time": datetime.now().astimezone().isoformat(),
            "pid": os.getpid(),
            "event": event,
            **fields,
        }
        try:
            with self.lock, self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=True) + "\n")
        except OSError:
            # Diagnostics must not prevent cancellation or leave a future unresolved.
            if not self.write_failed:
                logging.getLogger(__name__).warning("Cannot write archive diagnostics")
                self.write_failed = True

    def error(self, event, error, **fields):
        self.emit(event, exception=exception_details(error), **fields)

    def __enter__(self):
        self.emit(
            "archive_start",
            protocol=1,
            os=platform.system(),
            python=platform.python_version(),
        )
        return self

    def __exit__(self, kind, error, tb):
        if error is not None:
            self.error("archive_exception", error)
        self.emit("archive_end", completed=error is None)


def network_details(snapshot):
    settings = snapshot["settings"]
    return {
        "proxy_enabled": bool(settings.get("proxyEnabled")),
        "proxy_type": settings.get("proxyType"),
        "system_proxy": snapshot.get("system"),
        "exclusions_configured": bool(
            settings.get("proxyExcludedUrls") or settings.get("noProxyUrls")
        ),
        "credentials_available": bool(snapshot.get("credentials", {}).get("user")),
        "timeout_ms": snapshot.get("timeout"),
        "route": "not_observed; configuration alone does not prove proxy use",
    }
