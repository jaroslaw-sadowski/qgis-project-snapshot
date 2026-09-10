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

        from qgis.PyQt.QtNetwork import QNetworkRequest

        reply = Mock()
        reply.rawHeader.return_value = mime
        reply.content.return_value = body
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
                b"<ows:ExceptionText>password=secret https://user:pass@host/private</ows:ExceptionText>"
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
            observer.last_error = {}
            observer.started_signal = Mock()
            observer.finished_signal = Mock()
            reply = self.reply(b"")
            reply.requestId.return_value = 1
            reply.request.return_value = QNetworkRequest(
                QUrl(
                    "https://private-user:secret-password@example.test/private-path"
                    "?request=GetFeature&token=secret-token&srsname=EPSG:2180"
                )
            )
            for _ in range(10):
                observer.pending[1] = (None, "layer_test")
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
