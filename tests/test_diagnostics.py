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
