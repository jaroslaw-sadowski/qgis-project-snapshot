"""Regression coverage for QGIS timeouts, transparent maps and progress."""

import json
import re
import time
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import test_adaptive as adaptive_fixtures
import test_raster_archive as fixtures
from qgis.core import QgsNetworkAccessManager
from qgis.PyQt.QtGui import QColor, QImage

from mbtiles_batch_exporter.adaptive import HostDeferred, HostPolicy
from mbtiles_batch_exporter.diagnostics import Diagnostics, NetworkDiagnostics
from mbtiles_batch_exporter.raster_archive import _mask_image


class RasterEvidenceTests(unittest.TestCase):
    setUp = fixtures.RasterTests.setUp
    tearDown = fixtures.RasterTests.tearDown

    def test_adaptive_progress_counts_tiles_and_reports_zoom_results(self):
        messages = []
        gate = SimpleNamespace(
            folder=self.folder,
            retrying=False,
            before=lambda retry=False: None,
            outcome=lambda error=None, recoverable=True: None,
        )
        result = fixtures.write_rendered_raster(
            self.layer,
            self.project,
            self.area,
            self.crs,
            self.database,
            "map",
            fixtures.zoom_levels(self.project, self.area, self.crs, 17, 17),
            lambda: False,
            messages.append,
            gate=gate,
        )
        counts = [
            tuple(map(int, match.groups()))
            for text in messages
            if (match := re.search(r"fragment (\d+)/(\d+),", text))
        ]
        self.assertTrue(counts)
        self.assertEqual([n for n, _ in counts], list(range(1, len(counts) + 1)))
        self.assertTrue(all(total == len(counts) for _, total in counts))
        self.assertTrue(any("zoom 17 zakończony" in text for text in messages))
        stats = result["raster"]
        self.assertEqual(stats["raw_nonempty"], len(counts))
        self.assertEqual(stats["raw_empty"], 0)
        self.assertGreater(stats["timing_seconds"]["render"], 0)
        self.assertGreater(stats["timing_seconds"]["write"], 0)

    def test_transparency_diagnostic_distinguishes_source_from_mask(self):
        bounds = fixtures.QgsRectangle(256, 0, 512, 256)
        area = fixtures.QgsGeometry.fromRect(fixtures.QgsRectangle(0, 0, 256, 256))
        stats = {
            "raw_empty": 0,
            "raw_nonempty": 0,
            "masked_out": 0,
            "timing_seconds": {"mask": 0.0},
        }
        for color in (QColor("red"), QColor(0, 0, 0, 0)):
            image = QImage(256, 256, QImage.Format_ARGB32_Premultiplied)
            image.fill(color)
            _mask_image(image, area, bounds, 1, stats)
        self.assertEqual(stats["raw_empty"], 1)
        self.assertEqual(stats["raw_nonempty"], 1)
        self.assertEqual(stats["masked_out"], 1)


class NativeWmsTimeoutTests(unittest.TestCase):
    setUp = fixtures.LocalWmsTests.setUp
    tearDown = fixtures.LocalWmsTests.tearDown
    start_server = fixtures.LocalWmsTests.start_server
    add_map = adaptive_fixtures.AdaptiveWmsTests.add_map

    def test_three_native_timeouts_trigger_backoff_without_immediate_retries(self):
        layer = self.add_map()
        self.server.delay = 0.3
        policy = HostPolicy("127.0.0.1")
        errors = []

        def before(retry=False):
            if policy.until > time.monotonic():
                raise HostDeferred("Test ends at the native timeout backoff")

        def outcome(error=None, recoverable=True):
            errors.append(error)
            if error:
                policy.failure(
                    "timeout" if isinstance(error, TimeoutError) else None,
                    None,
                    time.monotonic(),
                    policy.generation,
                )

        gate = SimpleNamespace(
            folder=self.folder, retrying=False, before=before, outcome=outcome
        )
        manager = QgsNetworkAccessManager.instance()
        timeout = manager.timeout()
        manager.setTimeout(80)
        try:
            result = fixtures.write_rendered_raster(
                layer,
                self.project,
                self.area,
                self.crs,
                self.database,
                "map",
                fixtures.zoom_levels(self.project, self.area, self.crs, 17, 17),
                lambda: False,
                lambda _: None,
                gate=gate,
            )
        finally:
            manager.setTimeout(timeout)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(self.server.requests), 3)
        self.assertTrue(all(isinstance(error, TimeoutError) for error in errors))
        self.assertEqual(len(errors), 3)
        self.assertTrue(policy.frozen)
        self.assertGreater(policy.until, time.monotonic())
        self.assertTrue(result["raster"]["deferred"])
        self.assertEqual(result["raster"]["retries"], 0)
        self.assertEqual(result["raster"]["subdivisions"], 0)

    def test_native_timeout_of_redirected_wms_is_not_a_valid_empty_tile(self):
        parent = self.server.RequestHandlerClass

        class RedirectHandler(parent):
            def do_GET(handler):
                query = {
                    k.upper(): values[0]
                    for k, values in parse_qs(urlsplit(handler.path).query).items()
                }
                if query.get("REQUEST", "").lower() == "getmap" and handler.headers[
                    "Host"
                ].startswith("127.0.0.1"):
                    handler.send_response(302)
                    handler.send_header(
                        "Location",
                        f"http://localhost:{handler.server.server_port}{handler.path}",
                    )
                    handler.send_header("Content-Length", "0")
                    handler.end_headers()
                    return
                super().do_GET()

        self.server.RequestHandlerClass = RedirectHandler
        self.server.delay = 0.3
        layer = self.add_map()
        manager = QgsNetworkAccessManager.instance()
        timeout = manager.timeout()
        diagnostic = Diagnostics(self.folder / "diagnostic.jsonl")
        monitor = NetworkDiagnostics(diagnostic)
        manager.setTimeout(80)
        try:
            with self.assertRaises(TimeoutError):
                fixtures._render_image(
                    layer,
                    self.project,
                    self.area.boundingBox(),
                    256,
                    256,
                    lambda: False,
                    lambda _: None,
                )
        finally:
            manager.setTimeout(timeout)
            monitor.close()
        events = [json.loads(line) for line in diagnostic.path.read_text().splitlines()]
        native_timeouts = [e for e in events if e["event"] == "network_timeout"]
        self.assertTrue(native_timeouts, events)
        self.assertEqual(native_timeouts[0]["host"], "localhost")
        replies = [e for e in events if e["event"] == "network_reply"]
        self.assertTrue(any(e["qt_error"] == 5 for e in replies), events)
