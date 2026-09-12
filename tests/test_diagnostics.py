# SPDX-License-Identifier: GPL-2.0-only

"""Diagnostics retain actionable code locations without serializing secrets."""

import json
import tempfile
import unittest
from pathlib import Path

from mbtiles_batch_exporter.diagnostics import Diagnostics, network_details


class DiagnosticsTests(unittest.TestCase):
    def test_failure_survives_and_omits_message_and_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "diagnostic.jsonl"
            with self.assertRaises(PermissionError):
                with Diagnostics(path):
                    raise PermissionError(13, "password=secret-token", "/private/user")
            text = path.read_text()
            rows = [json.loads(line) for line in text.splitlines()]
            error = rows[1]["exception"]
            self.assertEqual(error["type"], "PermissionError")
            self.assertEqual(error["errno"], 13)
            self.assertTrue(error["frames"])
            self.assertFalse(rows[-1]["completed"])
            self.assertNotIn("secret-token", text)
            self.assertNotIn("/private/user", text)

    def test_logging_failure_does_not_break_worker_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            diagnostic = Diagnostics(Path(folder) / "absent" / "log.jsonl")
            with self.assertLogs("mbtiles_batch_exporter.diagnostics", level="WARNING"):
                diagnostic.emit("worker_exit", exit_code=1)
            self.assertTrue(diagnostic.write_failed)

    def test_proxy_summary_omits_sensitive_settings(self):
        summary = network_details(
            {
                "settings": {
                    "proxyEnabled": True,
                    "proxyType": "HttpProxy",
                    "proxyHost": "private-server",
                    "noProxyUrls": "secret-url",
                },
                "credentials": {"user": "private-user", "password": "secret-password"},
                "system": False,
                "timeout": 60000,
            }
        )
        self.assertTrue(summary["proxy_enabled"])
        self.assertTrue(summary["credentials_available"])
        self.assertTrue(summary["exclusions_configured"])
        text = json.dumps(summary)
        for secret in (
            "private-server",
            "secret-url",
            "private-user",
            "secret-password",
        ):
            self.assertNotIn(secret, text)


class ResponseDiagnosticsTests(unittest.TestCase):
    def reply(self, body, mime=b"text/xml"):
        from unittest.mock import Mock

        from qgis.PyQt.QtCore import QByteArray
        from qgis.PyQt.QtNetwork import QNetworkRequest

        reply = Mock()
        reply.rawHeader.side_effect = lambda key: (
            QByteArray(mime) if key == b"Content-Type" else QByteArray()
        )
        reply.content.return_value = (
            QByteArray(body) if body is not None else QByteArray()
        )
        reply.error.return_value = 0
        reply.attribute.side_effect = lambda key: (
            200 if key == QNetworkRequest.HttpStatusCodeAttribute else False
        )
        return reply

    def test_ogc_error_inside_http_200_is_detected_without_message(self):
        from mbtiles_batch_exporter.diagnostics import response_details

        details = response_details(
            self.reply(
                b"<ows:ExceptionReport>"
                b'<ows:Exception exceptionCode="InvalidParameterValue">'
                b"<ows:ExceptionText>password=secret "
                b"https://user:pass@host/private</ows:ExceptionText>"
                b"</ows:Exception></ows:ExceptionReport>"
            )
        )
        self.assertEqual(details["http_status"], 200)
        self.assertTrue(details["ogc_exception"])
        self.assertEqual(details["ogc_codes"], ["InvalidParameterValue"])
        self.assertNotIn("password", json.dumps(details))
        self.assertNotIn("private", json.dumps(details))

    def test_wfs_counts_are_observed_without_feature_attributes(self):
        from mbtiles_batch_exporter.diagnostics import response_details

        details = response_details(
            self.reply(
                b'<wfs:FeatureCollection numberReturned="0" numberMatched="25">'
                b"<private>secret-record</private></wfs:FeatureCollection>"
            )
        )
        self.assertEqual(details["numberReturned"], 0)
        self.assertEqual(details["numberMatched"], 25)
        self.assertNotIn("secret-record", json.dumps(details))

    def test_missing_body_does_not_claim_empty_wfs_response(self):
        from mbtiles_batch_exporter.diagnostics import response_details

        details = response_details(self.reply(b""))
        self.assertFalse(details["body_available"])
        self.assertNotIn("numberReturned", details)

    def test_network_samples_are_bounded_and_omit_url_secrets(self):
        from unittest.mock import Mock

        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtNetwork import QNetworkRequest

        from mbtiles_batch_exporter.diagnostics import NetworkDiagnostics

        with tempfile.TemporaryDirectory() as folder:
            log = Diagnostics(Path(folder) / "diagnostic.jsonl")
            observer = NetworkDiagnostics.__new__(NetworkDiagnostics)
            observer.diagnostic = log
            observer.pending = {}
            observer.groups = {}
            observer.timed_out_requests = set()
            observer.timeout_groups = {}
            observer.last_error = {}
            observer.intervals = {}
            observer.interval_started = observer.observer_started = 0.0
            observer.started_signal = Mock()
            observer.finished_signal = Mock()
            observer.timeout_signal = Mock()
            reply = self.reply(b"")
            reply.requestId.return_value = 1
            reply.request.return_value = QNetworkRequest(
                QUrl(
                    "https://private-user:secret-password@example.test/private-path"
                    "?request=GetFeature&token=secret-token&srsname=EPSG%3A2180"
                )
            )
            for _ in range(10):
                observer.pending[1] = (None, "layer_test", "example.test")
                observer.finished(reply)
            observer.close()
            text = log.path.read_text()
            events = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(sum(e["event"] == "network_reply" for e in events), 3)
            summary = next(e for e in events if e["event"] == "network_summary")
            self.assertEqual(summary["count"], 10)
            self.assertEqual(summary["context"], "layer_test")
            self.assertEqual(summary["request_crs"], "EPSG:2180")
            for secret in (
                "private-user",
                "secret-password",
                "private-path",
                "secret-token",
            ):
                self.assertNotIn(secret, text)

    def test_native_qgis_timeouts_are_counted_separately_from_user_aborts(self):
        from unittest.mock import Mock, patch

        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

        from mbtiles_batch_exporter.diagnostics import NetworkDiagnostics

        observer = NetworkDiagnostics.__new__(NetworkDiagnostics)
        observer.diagnostic = Mock()
        observer.context = "layer_test"
        observer.pending = {}
        observer.groups = {}
        observer.timed_out_requests = set()
        observer.timeout_groups = {}
        observer.last_error = {}
        observer.intervals = {}
        observer.interval_started = observer.observer_started = 0.0
        observer.started_signal = Mock()
        observer.finished_signal = Mock()
        observer.timeout_signal = Mock()
        request = QNetworkRequest(
            QUrl("https://example.test/private?token=secret&REQUEST=GetMap")
        )
        parameters = Mock()
        parameters.request.return_value = request
        reply = self.reply(b"", b"image/png")
        reply.error.return_value = QNetworkReply.OperationCanceledError
        reply.attribute.return_value = None
        reply.request.return_value = request
        with patch("time.monotonic", return_value=15.0):
            for request_id in range(4):
                parameters.requestId.return_value = request_id
                reply.requestId.return_value = request_id
                observer.pending[request_id] = (10.0, "layer_test", "example.test")
                observer.timed_out(parameters)
                observer.timed_out(parameters)  # Duplicate notification is harmless.
                observer.finished(reply)
        self.assertEqual(observer.last_error["qt_error"], 5)
        self.assertTrue(observer.last_error["qgis_timeout"])
        self.assertFalse(observer.timed_out_requests)

        # Qt's abort code alone does not prove a timeout, e.g. user cancellation.
        reply.requestId.return_value = 5
        observer.finished(reply)
        self.assertFalse(observer.last_error["qgis_timeout"])
        observer.close()
        calls = observer.diagnostic.emit.call_args_list
        self.assertEqual(sum(c.args[0] == "network_timeout" for c in calls), 3)
        summary = next(
            c.kwargs for c in calls if c.args[0] == "network_timeout_summary"
        )
        self.assertEqual(summary["count"], 4)
        self.assertEqual(summary["seconds"], 20.0)
        self.assertEqual(summary["context"], "layer_test")
        self.assertEqual(summary["host"], "example.test")
        serialized = str(calls)
        self.assertNotIn("private", serialized)
        self.assertNotIn("secret", serialized)

    def test_available_empty_body_is_distinguished_from_missing_body(self):
        from mbtiles_batch_exporter.diagnostics import response_details

        self.assertEqual(response_details(self.reply(b""))["content_bytes"], 0)
        self.assertIsNone(response_details(self.reply(None))["content_bytes"])
        self.assertEqual(response_details(self.reply(b"abcd"))["content_bytes"], 4)

    def test_body_size_does_not_copy_content_or_trust_claimed_length(self):
        from unittest.mock import Mock

        from qgis.PyQt.QtCore import QByteArray

        from mbtiles_batch_exporter.diagnostics import response_details

        reply = self.reply(b"abc", b"image/png")
        reply.content.return_value = Mock()
        reply.content.return_value.isNull.return_value = False
        reply.content.return_value.size.return_value = 3
        reply.rawHeader.side_effect = lambda key: QByteArray(
            b"999999" if key == b"Content-Length" else b"image/png"
        )
        details = response_details(reply)
        self.assertEqual(details["content_bytes"], 3)
        self.assertEqual(details["declared_content_length"], 999999)
        reply.content.return_value.size.assert_called_once()

    def test_interval_covers_bytes_latencies_cache_and_error_without_losing_totals(
        self,
    ):
        from unittest.mock import Mock, patch

        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtNetwork import QNetworkRequest

        from mbtiles_batch_exporter.diagnostics import NetworkDiagnostics

        observer = NetworkDiagnostics.__new__(NetworkDiagnostics)
        observer.diagnostic = Mock()
        observer.context = "map_test"
        observer.pending = {}
        observer.groups = {}
        observer.timed_out_requests = set()
        observer.timeout_groups = {}
        observer.last_error = {}
        observer.intervals = {}
        observer.interval_started = observer.observer_started = 10.0
        observer.started_signal = Mock()
        observer.finished_signal = Mock()
        observer.timeout_signal = Mock()
        parameters = Mock()
        parameters.requestId.return_value = 1
        request = QNetworkRequest(QUrl("https://example.test/map?REQUEST=GetMap"))
        parameters.request.return_value = request
        with patch("time.monotonic", return_value=10.0):
            observer.started(parameters)
        reply = self.reply(b"abc", b"image/png")
        reply.attribute.side_effect = lambda key: (
            503 if key == QNetworkRequest.HttpStatusCodeAttribute else True
        )
        reply.error.return_value = 5
        reply.requestId.return_value = 1
        reply.request.return_value = request
        with patch("time.monotonic", return_value=15.0):
            observer.timed_out(parameters)
            observer.finished(reply)
            observer.flush_interval()
        interval = next(
            call.kwargs
            for call in observer.diagnostic.emit.call_args_list
            if call.args[0] == "network_interval"
        )
        self.assertEqual(interval["requests_started"], 1)
        self.assertEqual(interval["count"], 1)
        self.assertEqual(interval["observed_body_bytes"], 3)
        self.assertEqual(interval["observed_body_count"], 1)
        self.assertEqual(interval["unavailable_body_count"], 0)
        self.assertEqual(interval["cached_count"], 1)
        self.assertEqual(interval["http_error_count"], 1)
        self.assertEqual(interval["qt_error_count"], 1)
        self.assertEqual(interval["timeout_count"], 1)
        self.assertEqual(interval["min_seconds"], 5.0)
        self.assertEqual(interval["max_seconds"], 5.0)
        self.assertEqual(interval["latency_counts"], [0, 0, 0, 0, 1, 0, 0, 0])
        self.assertEqual(interval["inflight_requests"], 0)
        self.assertEqual(interval["interval_seconds"], 5.0)
        self.assertFalse(observer.intervals)

        # A later unavailable body must neither count as zero measured bytes nor
        # erase the previous lifetime totals. Unmatched replies have no latency.
        reply.content.return_value.clear()
        reply.requestId.return_value = 2
        with patch("time.monotonic", return_value=17.0):
            observer.finished(reply)
            observer.close()
        intervals = [
            call.kwargs
            for call in observer.diagnostic.emit.call_args_list
            if call.args[0] == "network_interval"
        ]
        self.assertEqual(len(intervals), 2)
        self.assertEqual(intervals[1]["unavailable_body_count"], 1)
        self.assertEqual(intervals[1]["timed_count"], 0)
        self.assertEqual(intervals[1]["interval_seconds"], 2.0)
        totals = [
            call.kwargs
            for call in observer.diagnostic.emit.call_args_list
            if call.args[0] == "network_summary"
        ]
        self.assertEqual(sum(row["count"] for row in totals), 2)
        self.assertEqual(sum(row["observed_body_bytes"] for row in totals), 3)

    def test_slow_pending_request_remains_visible_in_following_interval(self):
        from unittest.mock import Mock, patch

        from mbtiles_batch_exporter.diagnostics import NetworkDiagnostics

        observer = NetworkDiagnostics.__new__(NetworkDiagnostics)
        observer.diagnostic = Mock()
        observer.pending = {1: (1.0, "map", "example.test")}
        observer.intervals = {}
        observer.interval_started = observer.observer_started = 1.0
        with patch("time.monotonic", return_value=5.9):
            observer.flush_interval()
        observer.diagnostic.emit.assert_not_called()
        for now in (6.0, 11.0):
            with patch("time.monotonic", return_value=now):
                observer.flush_interval()
            row = observer.diagnostic.emit.call_args.kwargs
            self.assertEqual(row["inflight_requests"], 1)
            self.assertEqual(row["count"], 0)
            self.assertEqual(row["host"], "example.test")

    def test_native_qgis_response_reports_declared_size_and_body_coverage(self):
        import test_raster_archive as fixtures
        from qgis.core import QgsApplication, QgsBlockingNetworkRequest
        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtNetwork import QNetworkRequest

        from mbtiles_batch_exporter.diagnostics import NetworkDiagnostics

        fixture = fixtures.LocalWmsTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        diagnostic = Diagnostics(fixture.folder / "network.jsonl")
        observer = NetworkDiagnostics(diagnostic)
        observer.context = "native_map"
        request = QgsBlockingNetworkRequest()
        try:
            result = request.get(
                QNetworkRequest(
                    QUrl(
                        f"http://127.0.0.1:{fixture.server.server_port}/wms"
                        "?REQUEST=GetMap&WIDTH=32&HEIGHT=32"
                    )
                )
            )
            QgsApplication.processEvents()
        finally:
            observer.close()
        self.assertEqual(result, QgsBlockingNetworkRequest.NoError)
        body_bytes = request.reply().content().size()
        self.assertGreater(body_bytes, 0)
        events = [json.loads(row) for row in diagnostic.path.read_text().splitlines()]
        interval = next(row for row in events if row["event"] == "network_interval")
        self.assertEqual(interval["count"], 1)
        self.assertEqual(interval["declared_content_length_count"], 1)
        self.assertEqual(interval["declared_content_length_bytes"], body_bytes)
        self.assertEqual(
            interval["observed_body_count"] + interval["unavailable_body_count"], 1
        )
        if interval["observed_body_count"]:
            self.assertEqual(interval["observed_body_bytes"], body_bytes)
        else:
            self.assertEqual(interval["observed_body_bytes"], 0)

    def test_varying_body_sizes_do_not_create_unbounded_groups(self):
        from unittest.mock import Mock, patch

        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtNetwork import QNetworkRequest

        from mbtiles_batch_exporter.diagnostics import NetworkDiagnostics

        # Mock only Qt signal wiring, retaining production observer initialization.
        with patch("qgis.core.QgsNetworkAccessManager.instance"):
            observer = NetworkDiagnostics(Mock())
        reply = self.reply(b"", b"image/png")
        reply.requestId.return_value = 1
        reply.request.return_value = QNetworkRequest(QUrl("https://example.test/map"))
        total = 0
        for size in range(100):
            reply.content.return_value.resize(size)
            observer.finished(reply)
            total += size
        self.assertEqual(len(observer.groups), 1)
        self.assertEqual(next(iter(observer.groups.values()))["count"], 100)
        self.assertEqual(
            next(iter(observer.groups.values()))["observed_body_bytes"], total
        )

        # A varied project can still have many contexts; drain bounded chunks.
        observer.max_groups = 2
        for context in range(5):
            observer.pending[1] = (None, context, "example.test")
            observer.finished(reply)
            self.assertLessEqual(len(observer.groups), 2)
        observer.close()
        totals = [
            call.kwargs["count"]
            for call in observer.diagnostic.emit.call_args_list
            if call.args[0] == "network_summary"
        ]
        self.assertEqual(sum(totals), 105)
