# SPDX-License-Identifier: GPL-2.0-only

"""Persistent structured diagnostics without source URLs or exception messages."""

import json
import logging
import os
import platform
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread


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


class PerformanceDiagnostics:
    """Sample only native process counters, even while the QGIS thread is busy."""

    def __init__(self, diagnostic, role, folder=None, interval=5.0):
        self.diagnostic = diagnostic
        self.role = role
        self.folder = folder
        self.interval = interval
        self.stop = Event()
        self.thread = None
        self.previous = None
        self.context = ("startup", None)
        self.phase_started = time.monotonic()
        try:
            self.phase_cpu = time.process_time()
        except (OSError, ValueError):
            self.phase_cpu = None

    def set_phase(self, phase, job=None):
        now = time.monotonic()
        try:
            cpu = time.process_time()
        except (OSError, ValueError):
            cpu = None
        old_phase, old_job = self.context
        self.diagnostic.emit(
            "performance_phase",
            role=self.role,
            phase=old_phase,
            job=old_job,
            seconds=max(0, now - self.phase_started),
            process_cpu_seconds=max(0, cpu - self.phase_cpu)
            if cpu is not None and self.phase_cpu is not None
            else None,
        )
        self.context = (phase, job)
        self.phase_started, self.phase_cpu = now, cpu

    def sample(self):
        from .resources import performance_counters

        started = time.monotonic()
        try:
            current = performance_counters(include_system=self.role == "main")
            previous = self.previous
            self.previous = current
            interval = (
                current["monotonic_seconds"] - previous["monotonic_seconds"]
                if previous
                else None
            )
            cpu_percent = None
            system_percent = None
            if interval and interval > 0:
                cpu, old_cpu = (
                    current["process_cpu_seconds"],
                    previous["process_cpu_seconds"],
                )
                if cpu is not None and old_cpu is not None and cpu >= old_cpu:
                    cpu_percent = (cpu - old_cpu) / interval * 100
                system, old_system = (
                    current.get("system_cpu"),
                    previous.get("system_cpu"),
                )
                if system and old_system and system["source"] == old_system["source"]:
                    total = system["total_seconds"] - old_system["total_seconds"]
                    idle = system["idle_seconds"] - old_system["idle_seconds"]
                    if total > 0 and 0 <= idle <= total:
                        system_percent = (total - idle) / total * 100
            volume = None
            if self.folder is not None:
                try:
                    usage = shutil.disk_usage(self.folder)
                    volume = {"total_bytes": usage.total, "free_bytes": usage.free}
                except OSError:
                    pass
            phase, job = self.context
            self.diagnostic.emit(
                "performance_sample",
                role=self.role,
                phase=phase,
                job=job,
                interval_seconds=interval,
                process_cpu_percent_one_core=cpu_percent,
                system_cpu_percent=system_percent,
                volume=volume,
                counters=current,
                probe_seconds=time.monotonic() - started,
            )
        except Exception as error:
            # A failed probe must not interrupt downloading or finalization.
            self.diagnostic.error("performance_probe_error", error, role=self.role)

    def _run(self):
        while not self.stop.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.diagnostic.emit(
            "performance_configuration",
            version=1,
            role=self.role,
            sample_interval_seconds=self.interval,
            os_version=platform.version(),
            architecture=platform.machine(),
        )
        self.sample()
        self.thread = Thread(target=self._run, name="archive-performance", daemon=True)
        try:
            self.thread.start()
        except RuntimeError as error:
            self.thread = None
            self.diagnostic.error("performance_probe_error", error, role=self.role)
        return self

    def __exit__(self, kind, error, tb):
        self.stop.set()
        if self.thread is not None:
            self.thread.join()
        self.sample()
        self.set_phase("finished")


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
    content = reply.content()
    # QByteArray is implicitly shared. size()/isNull() do not copy a tile to Python.
    # A null array means QGIS did not retain the body, not a zero-byte response.
    content_bytes = None if content.isNull() else content.size()
    length = bytes(reply.rawHeader(b"Content-Length")).strip()
    declared_length = int(length) if re.fullmatch(rb"[0-9]{1,19}", length) else None
    cached = reply.attribute(QNetworkRequest.Attribute.SourceIsFromCacheAttribute)
    result = {
        "http_status": reply.attribute(
            QNetworkRequest.Attribute.HttpStatusCodeAttribute
        ),
        "qt_error": int(getattr(reply.error(), "value", reply.error())),
        "content_type": mime.decode("ascii") if mime in known else "other",
        "from_cache": None if cached is None else bool(cached),
        "content_bytes": content_bytes,
        "declared_content_length": declared_length,
    }
    if b"xml" in mime or mime == b"text/html":
        prefix = bytes(content[:16384])
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

    latency_upper_seconds = (0.1, 0.5, 1.0, 2.0, 5.0, 15.0, 60.0)
    max_groups = 1024

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
        self.intervals = {}
        self.interval_started = time.monotonic()
        self.observer_started = self.interval_started
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
        try:
            if len(self.pending) >= 4096:
                self.diagnostic.emit("network_timing_overflow", count=len(self.pending))
                self.pending.clear()
                self.timed_out_requests.clear()
            host = parameters.request().url().host()
            self.pending[parameters.requestId()] = (
                time.monotonic(),
                self.context,
                host,
            )
            self._interval(self.context, host)["requests_started"] += 1
        except Exception as error:
            self.diagnostic.error("network_observer_error", error)

    def timed_out(self, parameters):
        """QGIS can report its request timeout as Qt OperationCanceledError."""
        try:
            request_id = parameters.requestId()
            if request_id in self.timed_out_requests:
                return
            if len(self.timed_out_requests) >= 4096:
                self.timed_out_requests.clear()
            self.timed_out_requests.add(request_id)
            started, context, _ = self.pending.get(request_id, (None, None, None))
            elapsed = None if started is None else max(0.0, time.monotonic() - started)
            host = parameters.request().url().host()
            self._interval(context, host)["timeout_count"] += 1
            if (context, host) not in self.timeout_groups and (
                len(self.timeout_groups) >= self.max_groups
            ):
                self._flush_timeout_summaries()
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

        from qgis.PyQt.QtCore import QUrl, QUrlQuery

        started, context, _ = self.pending.pop(reply.requestId(), (None, None, None))
        url = reply.request().url()
        operation = "other"
        request_crs = None
        bbox_present = False
        for key, value in QUrlQuery(url).queryItems(
            QUrl.ComponentFormattingOption.FullyDecoded
        ):
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
        group_details = {
            key: value
            for key, value in details.items()
            if key not in ("content_bytes", "declared_content_length")
        }
        key = (
            context,
            url.host(),
            operation,
            json.dumps(group_details, sort_keys=True),
        )
        if key not in self.groups and len(self.groups) >= self.max_groups:
            self._flush_summaries()
        if key not in self.groups:
            self.groups[key] = self._new_summary()
        summary = self.groups[key]
        elapsed = None if started is None else max(0.0, time.monotonic() - started)
        for counts in (summary, self._interval(context, url.host())):
            self._record_reply(counts, details, elapsed)
        if summary["count"] <= 3:
            self.diagnostic.emit(
                "network_reply",
                context=context,
                host=url.host(),
                operation=operation,
                seconds=elapsed,
                **details,
            )

    @classmethod
    def _new_summary(cls):
        return {
            "count": 0,
            "timed_count": 0,
            "seconds": 0.0,
            "min_seconds": None,
            "max_seconds": None,
            "latency_counts": [0] * (len(cls.latency_upper_seconds) + 1),
            "observed_body_bytes": 0,
            "observed_body_count": 0,
            "cached_body_bytes": 0,
            "uncached_body_bytes": 0,
            "cache_unknown_body_bytes": 0,
            "unavailable_body_count": 0,
            "declared_content_length_bytes": 0,
            "declared_content_length_count": 0,
            "cached_count": 0,
            "cache_unknown_count": 0,
            "http_error_count": 0,
            "qt_error_count": 0,
        }

    @classmethod
    def _record_reply(cls, summary, details, elapsed):
        summary["count"] += 1
        if elapsed is not None:
            summary["timed_count"] += 1
            summary["seconds"] += elapsed
            minimum, maximum = summary["min_seconds"], summary["max_seconds"]
            summary["min_seconds"] = (
                elapsed if minimum is None else min(minimum, elapsed)
            )
            summary["max_seconds"] = (
                elapsed if maximum is None else max(maximum, elapsed)
            )
            bucket = sum(elapsed > limit for limit in cls.latency_upper_seconds)
            summary["latency_counts"][bucket] += 1
        body_bytes = details["content_bytes"]
        if body_bytes is None:
            summary["unavailable_body_count"] += 1
        else:
            summary["observed_body_count"] += 1
            summary["observed_body_bytes"] += body_bytes
            if details["from_cache"] is True:
                summary["cached_body_bytes"] += body_bytes
            elif details["from_cache"] is False:
                summary["uncached_body_bytes"] += body_bytes
            else:
                summary["cache_unknown_body_bytes"] += body_bytes
        length = details["declared_content_length"]
        if length is not None:
            summary["declared_content_length_count"] += 1
            summary["declared_content_length_bytes"] += length
        summary["cached_count"] += details["from_cache"] is True
        summary["cache_unknown_count"] += details["from_cache"] is None
        summary["http_error_count"] += bool(
            details["http_status"] and details["http_status"] >= 400
        )
        summary["qt_error_count"] += bool(details["qt_error"])

    def _interval(self, context, host):
        key = (context, host)
        if key not in self.intervals and len(self.intervals) >= self.max_groups:
            self.flush_interval(force=True)
        if key not in self.intervals:
            self.intervals[key] = self._new_summary()
            self.intervals[key].update(requests_started=0, timeout_count=0)
        return self.intervals[key]

    def flush_interval(self, force=False):
        """Call from the observing QGIS thread, never a Python sampling thread."""
        try:
            self._flush_interval(force)
        except Exception as error:
            self.diagnostic.error("network_observer_error", error)

    def _flush_interval(self, force):
        now = time.monotonic()
        seconds = now - self.interval_started
        if not force and seconds < 5.0:
            return
        inflight = {}
        for _, context, host in self.pending.values():
            key = (context, host)
            inflight[key] = inflight.get(key, 0) + 1
        # Keep pending-only intervals visible when a server stops replying.
        for key in inflight:
            if key not in self.intervals:
                self.intervals[key] = self._new_summary()
                self.intervals[key].update(requests_started=0, timeout_count=0)
        for (context, host), summary in self.intervals.items():
            self.diagnostic.emit(
                "network_interval",
                context=context,
                host=host,
                interval_seconds=max(0.0, seconds),
                since_start_seconds=max(0.0, now - self.observer_started),
                inflight_requests=inflight.get((context, host), 0),
                latency_upper_seconds=[*self.latency_upper_seconds, None],
                **summary,
            )
        self.intervals.clear()
        self.interval_started = now

    def _flush_summaries(self):
        # Chunk only on the group bound; consumers sum chunks for lifetime totals.
        for (context, host, operation, details), summary in self.groups.items():
            self.diagnostic.emit(
                "network_summary",
                context=context,
                host=host,
                operation=operation,
                latency_upper_seconds=[*self.latency_upper_seconds, None],
                **json.loads(details),
                **summary,
            )
        self.groups.clear()

    def _flush_timeout_summaries(self):
        for (context, host), summary in self.timeout_groups.items():
            self.diagnostic.emit(
                "network_timeout_summary", context=context, host=host, **summary
            )
        self.timeout_groups.clear()

    def close(self):
        self.started_signal.disconnect(self.started)
        self.finished_signal.disconnect(self.finished)
        self.timeout_signal.disconnect(self.timed_out)
        self.flush_interval(force=True)
        self._flush_timeout_summaries()
        self._flush_summaries()
        self.diagnostic.emit(
            "network_observer_end", unmatched_requests=len(self.pending)
        )
