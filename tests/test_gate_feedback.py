# SPDX-License-Identifier: GPL-2.0-only

"""Tile feedback preserves permission safety without waiting on harmless ACKs."""

import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import test_adaptive as adaptive_fixtures
import test_raster_archive as fixtures

from mbtiles_batch_exporter.adaptive import (
    PROTOCOL,
    DownloadError,
    HostDeferred,
    WorkerGate,
    write_state,
)
from mbtiles_batch_exporter.raster_archive import write_rendered_raster, zoom_levels


class GateFeedbackTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.control = self.folder / "control.json"
        self.cancelled = False
        self.pump = Mock()
        self.gate = WorkerGate(self.folder, lambda: self.cancelled, self.pump)
        self.command = {
            "version": PROTOCOL,
            "allowed": True,
            "expires": time.monotonic() + 60,
            "generation": 4,
            "ack": 0,
        }
        write_state(self.control, self.command)

    def test_xml_failure_uses_valid_permission_and_retains_events_until_ack(self):
        for _ in range(3):
            self.gate.before()
            self.gate.outcome(RuntimeError("private XML message and credentials"))
        self.gate.before()
        self.pump.assert_not_called()
        self.assertEqual(self.gate.required_ack, 0)
        self.assertEqual([e["sequence"] for e in self.gate.events], [1, 2, 3])
        self.assertTrue(all(e["generation"] == 4 for e in self.gate.events))
        self.assertTrue(all(e["status"] is None for e in self.gate.events))
        telemetry = (self.folder / "telemetry.json").read_text()
        self.assertNotIn("private", telemetry)
        self.assertNotIn("credentials", telemetry)

        self.gate.outcome()
        write_state(self.control, dict(self.command, ack=2))
        self.gate.before()
        self.assertEqual([e["sequence"] for e in self.gate.events], [3])
        self.assertEqual(self.gate.counts, {"4": 1})
        write_state(self.control, dict(self.command, ack=3))
        self.gate.before()
        self.assertFalse(self.gate.events)

    def test_overload_and_timeout_wait_for_ack_and_use_updated_generation(self):
        cases = [TimeoutError("private timeout")] + [
            DownloadError("private server message", status=status)
            for status in (429, 502, 503, 504)
        ]
        for error in cases:
            with self.subTest(
                error=type(error).__name__, status=getattr(error, "status", None)
            ):
                self.gate.before()
                self.gate.outcome(error)
                required = self.gate.sequence
                self.assertEqual(self.gate.required_ack, required)
                acknowledged = dict(
                    self.command,
                    ack=required,
                    generation=self.gate.command["generation"] + 1,
                )

                def acknowledge():
                    self.assertFalse(self.gate.state["running"])
                    self.assertTrue(self.gate.state["waiting"])
                    write_state(self.control, acknowledged)

                self.pump.reset_mock()
                self.pump.side_effect = acknowledge
                with patch("mbtiles_batch_exporter.adaptive.time.sleep"):
                    self.gate.before()
                self.pump.assert_called_once()
                self.assertFalse(self.gate.events)
                self.assertEqual(
                    self.gate.command["generation"], acknowledged["generation"]
                )

    def test_probe_success_and_failure_both_wait_for_coordinator(self):
        for error in (None, RuntimeError("private probe failure")):
            with self.subTest(error=error):
                write_state(
                    self.control,
                    dict(self.command, probe=True, ack=self.gate.sequence),
                )
                self.gate.before()
                self.gate.outcome(error)
                self.assertEqual(self.gate.required_ack, self.gate.sequence)

                def acknowledge():
                    write_state(
                        self.control,
                        dict(self.command, probe=False, ack=self.gate.sequence),
                    )

                self.pump.reset_mock()
                self.pump.side_effect = acknowledge
                with patch("mbtiles_batch_exporter.adaptive.time.sleep"):
                    self.gate.before()
                self.pump.assert_called_once()
                self.assertFalse(self.gate.command["probe"])
                self.assertFalse(self.gate.events)

    def test_non_overload_http_error_is_reported_without_waiting(self):
        for status in (400, 401, 403, 404, 407, 500):
            self.gate.before()
            self.gate.outcome(DownloadError("private URL", status=status))
        self.gate.before()
        self.pump.assert_not_called()
        self.assertEqual(
            [e["status"] for e in self.gate.events], [400, 401, 403, 404, 407, 500]
        )

    def test_xml_feedback_does_not_bypass_revoked_or_expired_permission(self):
        for changes in ({"allowed": False}, {"expires": 0}):
            with self.subTest(changes=changes):
                self.cancelled = False
                write_state(self.control, self.command)
                self.gate.before()
                self.gate.outcome(RuntimeError("XML failure"))
                write_state(self.control, dict(self.command, **changes))

                def cancel():
                    self.cancelled = True

                self.pump.side_effect = cancel
                with patch("mbtiles_batch_exporter.adaptive.time.sleep"):
                    with self.assertRaises(InterruptedError):
                        self.gate.before()
                self.assertFalse(self.gate.state["running"])

    def test_expired_lease_still_fails_closed_after_coordinator_disappears(self):
        self.gate.before()
        self.gate.outcome(RuntimeError("XML failure"))
        write_state(self.control, dict(self.command, expires=0))
        with (
            patch(
                "mbtiles_batch_exporter.adaptive.time.monotonic", side_effect=range(20)
            ),
            patch("mbtiles_batch_exporter.adaptive.time.sleep"),
        ):
            with self.assertRaises(HostDeferred):
                self.gate.before()
        self.assertFalse(self.gate.state["running"])


class NativeWmsGateFeedbackTests(unittest.TestCase):
    start_server = fixtures.LocalWmsTests.start_server
    setUp = fixtures.LocalWmsTests.setUp
    tearDown = fixtures.LocalWmsTests.tearDown
    add_map = adaptive_fixtures.AdaptiveWmsTests.add_map

    def test_xml_error_does_not_block_following_tiles_or_the_successful_repair(self):
        parent = self.server.RequestHandlerClass

        class XmlOnceHandler(parent):
            def do_GET(handler):
                parameters = {
                    key.upper(): values[0]
                    for key, values in parse_qs(urlsplit(handler.path).query).items()
                }
                if (
                    parameters.get("REQUEST", "").lower() == "getmap"
                    and handler.server.xml_once
                ):
                    handler.server.xml_once = False
                    body = (
                        b"<ServiceExceptionReport>"
                        b'<ServiceException code="NoApplicableCode">'
                        b"private source detail</ServiceException>"
                        b"</ServiceExceptionReport>"
                    )
                    handler.send_response(200)
                    handler.send_header("Content-Type", "text/xml")
                    handler.send_header("Content-Length", str(len(body)))
                    handler.end_headers()
                    handler.wfile.write(body)
                    return
                super().do_GET()

        self.server.RequestHandlerClass = XmlOnceHandler
        self.server.xml_once = True
        layer = self.add_map()
        pump = Mock(
            side_effect=AssertionError("Unexpected wait for XML acknowledgement")
        )
        gate = WorkerGate(self.folder, lambda: False, pump)
        write_state(
            self.folder / "control.json",
            {
                "version": PROTOCOL,
                "allowed": True,
                "expires": time.monotonic() + 60,
                "generation": 0,
                "ack": 0,
            },
        )
        result = write_rendered_raster(
            layer,
            self.project,
            self.area,
            self.crs,
            self.database,
            "map",
            zoom_levels(self.project, self.area, self.crs, 17, 17),
            lambda: False,
            lambda _: None,
            gate=gate,
        )
        self.assertFalse(self.server.xml_once)
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["raster"]["repaired"], 1)
        self.assertGreater(result["tile_count"], 0)
        self.assertEqual(len(gate.events), 1)
        pump.assert_not_called()
        self.assertNotIn(
            "private source detail", (self.folder / "telemetry.json").read_text()
        )
