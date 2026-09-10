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


def response_details(reply):
    """Whitelist response metadata; never persist headers or response bodies."""
    import re

    from qgis.PyQt.QtNetwork import QNetworkRequest

    mime = bytes(reply.rawHeader(b"Content-Type")).split(b";", 1)[0].lower().strip()
    known = (
        b"image/png",
        b"image/jpeg",
        b"text/xml",
        b"application/xml",
        b"text/html",
        b"application/json",
        b"application/gml+xml",
    )
    result = {
        "http_status": reply.attribute(QNetworkRequest.HttpStatusCodeAttribute),
        "qt_error": int(reply.error()),
        "content_type": mime.decode("ascii") if mime in known else "other",
        "from_cache": bool(reply.attribute(QNetworkRequest.SourceIsFromCacheAttribute)),
    }
    if b"xml" in mime or mime == b"text/html":
        prefix = bytes(reply.content()[:16384])
        result["body_available"] = bool(prefix)
        result["ogc_exception"] = bool(
            re.search(
                rb"<(?:\w+:)?(?:ExceptionReport|ServiceExceptionReport)\b", prefix
            )
        )
        codes = re.findall(rb'(?:exceptionCode|code)=["\x27]([^"\x27]+)', prefix)
        known_codes = {
            b"InvalidParameterValue",
            b"MissingParameterValue",
            b"LayerNotDefined",
            b"StyleNotDefined",
            b"InvalidCRS",
            b"OperationNotSupported",
            b"NoApplicableCode",
        }
        if result["ogc_exception"]:
            result["ogc_codes"] = sorted(
                {c.decode("ascii") if c in known_codes else "other" for c in codes}
            )
        if re.search(rb"<(?:\w+:)?FeatureCollection\b", prefix):
            for key in ("numberReturned", "numberMatched", "numberOfFeatures"):
                match = re.search(key.encode() + rb'=["\x27](\d{1,15})["\x27]', prefix)
                if match:
                    result[key] = int(match[1])
    return result


class NetworkDiagnostics:
    """Observe QGIS signals; sample repeated replies and retain aggregate totals."""

    def __init__(self, diagnostic):
        from qgis.core import (
            QgsNetworkAccessManager,
            QgsNetworkReplyContent,
            QgsNetworkRequestParameters,
        )

        self.diagnostic = diagnostic
        self.context = None
        self.pending = {}
        self.groups = {}
        self.timed_out_requests = set()
        self.timeout_groups = {}
        self.last_error = {}
        manager = QgsNetworkAccessManager.instance()
        self.started_signal = manager.requestAboutToBeCreated[
            QgsNetworkRequestParameters
        ]
        self.finished_signal = manager.finished[QgsNetworkReplyContent]
        self.timeout_signal = manager.requestTimedOut[QgsNetworkRequestParameters]
        self.started_signal.connect(self.started)
        self.finished_signal.connect(self.finished)
        self.timeout_signal.connect(self.timed_out)

    def started(self, parameters):
        import time

        if len(self.pending) >= 4096:
            self.diagnostic.emit("network_timing_overflow", count=len(self.pending))
            self.pending.clear()
            self.timed_out_requests.clear()
        self.pending[parameters.requestId()] = (time.monotonic(), self.context)

    def timed_out(self, parameters):
        """QGIS can report its request timeout as Qt OperationCanceledError."""
        import time

        try:
            request_id = parameters.requestId()
            if request_id in self.timed_out_requests:
                return
            if len(self.timed_out_requests) >= 4096:
                self.timed_out_requests.clear()
            self.timed_out_requests.add(request_id)
            started, context = self.pending.get(request_id, (None, None))
            elapsed = None if started is None else max(0.0, time.monotonic() - started)
            host = parameters.request().url().host()
            summary = self.timeout_groups.setdefault(
                (context, host), {"count": 0, "timed_count": 0, "seconds": 0.0}
            )
            summary["count"] += 1
            if elapsed is not None:
                summary["timed_count"] += 1
                summary["seconds"] += elapsed
            if summary["count"] <= 3:
                self.diagnostic.emit(
                    "network_timeout", context=context, host=host, seconds=elapsed
                )
        except Exception as error:
            self.diagnostic.error("network_observer_error", error)

    def finished(self, reply):
        try:
            self._finished(reply)
        except Exception as error:
            # A diagnostic Qt slot must never abort the application's event loop.
            self.diagnostic.error("network_observer_error", error)

    def _finished(self, reply):
        import re
        import time

        from qgis.PyQt.QtCore import QUrl, QUrlQuery

        started, context = self.pending.pop(reply.requestId(), (None, None))
        url = reply.request().url()
        operation = "other"
        request_crs = None
        bbox_present = False
        for key, value in QUrlQuery(url).queryItems(QUrl.FullyDecoded):
            if key.lower() == "request" and value.lower() in (
                "getmap",
                "gettile",
                "getfeature",
                "getcapabilities",
                "describefeaturetype",
            ):
                operation = value.lower()
            if key.lower() in ("crs", "srs", "srsname"):
                match = re.fullmatch(
                    r"(?:EPSG:|urn:ogc:def:crs:EPSG:[^:]*:)([0-9]{1,6})", value
                )
                request_crs = "EPSG:" + match[1] if match else "other"
            if key.lower() == "bbox":
                bbox_present = True
        details = response_details(reply)
        details.update(
            request_crs=request_crs,
            bbox_present=bbox_present,
            qgis_timeout=reply.requestId() in self.timed_out_requests,
        )
        self.timed_out_requests.discard(reply.requestId())
        if details["qt_error"] or (
            details["http_status"] and details["http_status"] >= 400
        ):
            self.last_error.update(
                http_status=details["http_status"],
                qt_error=details["qt_error"],
                qgis_timeout=details["qgis_timeout"],
            )
        key = (context, url.host(), operation, json.dumps(details, sort_keys=True))
        summary = self.groups.setdefault(
            key, {"count": 0, "timed_count": 0, "seconds": 0.0}
        )
        summary["count"] += 1
        elapsed = None if started is None else max(0.0, time.monotonic() - started)
        if elapsed is not None:
            summary["timed_count"] += 1
            summary["seconds"] += elapsed
        if summary["count"] <= 3:
            self.diagnostic.emit(
                "network_reply",
                context=context,
                host=url.host(),
                operation=operation,
                seconds=elapsed,
                **details,
            )

    def close(self):
        self.started_signal.disconnect(self.started)
        self.finished_signal.disconnect(self.finished)
        self.timeout_signal.disconnect(self.timed_out)
        for (context, host), summary in self.timeout_groups.items():
            self.diagnostic.emit(
                "network_timeout_summary", context=context, host=host, **summary
            )
        for (context, host, operation, details), summary in self.groups.items():
            self.diagnostic.emit(
                "network_summary",
                context=context,
                host=host,
                operation=operation,
                **json.loads(details),
                **summary,
            )
        self.diagnostic.emit(
            "network_observer_end", unmatched_requests=len(self.pending)
        )
