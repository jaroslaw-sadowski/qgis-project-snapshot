# SPDX-License-Identifier: GPL-2.0-only

"""Real worker downloads through a local proxy, with no corporate configuration."""

import base64
import json
import unittest
from unittest.mock import patch

import test_raster_archive as fixtures
from qgis.core import (
    QgsDataSourceUri,
    QgsNetworkAccessManager,
    QgsRasterLayer,
    QgsSettings,
)
from qgis.PyQt.QtNetwork import QNetworkProxy, QNetworkProxyFactory

from mbtiles_batch_exporter.archive import create_archive
from mbtiles_batch_exporter.worker_network import network_snapshot


class ProxyTests(unittest.TestCase):
    start_server = fixtures.LocalWmsTests.start_server

    def setUp(self):
        fixtures.LocalWmsTests.setUp(self)
        settings = QgsSettings()
        self.previous = {
            key: settings.value(key)
            for key in settings.allKeys()
            if key.startswith("proxy/")
        }
        self.application_proxy = QNetworkProxy.applicationProxy()
        self.system_proxy = QNetworkProxyFactory.usesSystemConfiguration()
        self.proxy_requests = []
        self.auth_required = False
        self.reject_auth = False
        self.reject_map_auth = False
        owner = self
        original = self.server.RequestHandlerClass

        class ProxyHandler(original):
            def do_GET(self):
                if self.path.startswith("http://"):
                    owner.proxy_requests.append(self.path)
                    wanted = (
                        "Basic "
                        + base64.b64encode(b"fixture-user:fixture-password").decode()
                    )
                    if owner.auth_required and (
                        owner.reject_auth
                        or (
                            owner.reject_map_auth
                            and "request=getmap" in self.path.lower()
                        )
                        or self.headers.get("Proxy-Authorization") != wanted
                    ):
                        self.send_response(407)
                        self.send_header(
                            "Proxy-Authenticate", 'Basic realm="snapshot-test"'
                        )
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                super().do_GET()

        self.server.RequestHandlerClass = ProxyHandler

    def tearDown(self):
        settings = QgsSettings()
        settings.remove("proxy")
        for key, value in self.previous.items():
            settings.setValue(key, value)
        settings.sync()
        QNetworkProxy.setApplicationProxy(self.application_proxy)
        QNetworkProxyFactory.setUseSystemConfiguration(self.system_proxy)
        QgsNetworkAccessManager.instance().setupDefaultProxyAndCache()
        fixtures.LocalWmsTests.tearDown(self)

    def configure(self, enabled=True, exclusions=None, credentials=False):
        settings = QgsSettings()
        settings.remove("proxy")
        values = {
            "proxyEnabled": enabled,
            "proxyType": "HttpProxy",
            "proxyHost": "127.0.0.1",
            "proxyPort": self.server.server_port,
            "noProxyUrls": exclusions or [],
            "proxyUser": "fixture-user" if credentials else "",
            "proxyPassword": "fixture-password" if credentials else "",
        }
        for key, value in values.items():
            settings.setValue("proxy/" + key, value)
        settings.sync()
        QgsNetworkAccessManager.instance().setupDefaultProxyAndCache()

    def map_layer(self, url):
        uri = QgsDataSourceUri()
        for key, value in dict(
            url=url,
            layers="map",
            styles="",
            format="image/png",
            crs="EPSG:2180",
            version="1.3.0",
        ).items():
            uri.setParam(key, value)
        layer = QgsRasterLayer(bytes(uri.encodedUri()).decode(), "Proxy map", "wms")
        self.assertTrue(layer.isValid())
        self.project.addMapLayer(layer)
        return layer

    def capture(self, layer):
        rows = []
        with patch(
            "mbtiles_batch_exporter.archive.detect_resources",
            return_value=dict(cpu=2, memory=8 * 1024**3, online=True),
        ):
            folder = create_archive(
                self.project,
                {layer.id()},
                self.area,
                self.crs,
                self.folder,
                zoom_min=17,
                zoom_max=17,
                adaptive=True,
                server_activity=rows.extend,
            )
        manifest = json.loads((folder / "diagnostyka" / "manifest.json").read_text())
        self.diagnostic_events = [
            json.loads(line)
            for line in (folder / "diagnostyka" / "diagnostyka.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertFalse((folder / ".workers").exists())
        for path in folder.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"fixture-password", path.read_bytes())
                self.assertNotIn(b"fixture-user", path.read_bytes())
        return manifest, rows

    def test_worker_uses_qgis_proxy_and_saved_credentials(self):
        self.auth_required = True
        self.configure(credentials=True)
        # This host is intentionally unresolvable; success requires the proxy.
        layer = self.map_layer("http://snapshot-proxy-test.invalid/wms")
        self.proxy_requests.clear()
        manifest, rows = self.capture(layer)
        self.assertEqual(manifest["layers"][0]["status"], "saved", manifest["layers"])
        self.assertEqual(manifest["parallel"]["completed_in_workers"], 1)
        self.assertTrue(manifest["local_layer_audit"]["passed"])
        self.assertTrue(self.proxy_requests)
        replies = [
            e["details"]
            for e in self.diagnostic_events
            if e.get("details", {}).get("event") == "network_reply"
        ]
        self.assertTrue(replies)
        self.assertTrue(any(e["seconds"] is not None for e in replies))
        self.assertTrue(any(e["http_status"] == 200 for e in replies))
        # Replies started before observation (e.g. startup/cache) stay unattributed.
        self.assertTrue(any(e["context"] is not None for e in replies))

        self.assertTrue(
            any(
                e.get("details", {}).get("event") == "proxy_authentication_requested"
                for e in self.diagnostic_events
            )
        )
        self.assertEqual(rows[-1]["state"], "finished")

    def test_proxy_disabled_and_no_proxy_exclusion_use_direct_connection(self):
        url = f"http://127.0.0.1:{self.server.server_port}/wms"
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.configure(enabled=enabled, exclusions=[url])
                layer = self.map_layer(url)
                self.proxy_requests.clear()
                manifest, _ = self.capture(layer)
                self.assertEqual(
                    manifest["layers"][0]["status"], "saved", manifest["layers"]
                )
                self.assertFalse(self.proxy_requests)
                self.project.removeMapLayer(layer)

    def test_proxy_failure_reports_http_407_without_credentials(self):
        self.configure(credentials=True)
        layer = self.map_layer("http://snapshot-proxy-test.invalid/rejected")
        self.auth_required = self.reject_auth = True
        manifest, rows = self.capture(layer)
        record = manifest["layers"][0]
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["worker_error"]["http_status"], 407)
        self.assertIn("proxy", record["reason"].lower())
        self.assertEqual(rows[-1]["state"], "failed")

    def test_proxy_refusal_during_render_stops_after_first_tile(self):
        self.configure(credentials=True)
        layer = self.map_layer("http://snapshot-proxy-test.invalid/rejected-map")
        self.auth_required = self.reject_map_auth = True
        manifest, _ = self.capture(layer)
        record = manifest["layers"][0]
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["worker_error"]["http_status"], 407)
        self.assertEqual(record["raster"]["stop_http_status"], 407)
        self.assertEqual(
            sum(level["attempted"] for level in record["raster"]["levels"]), 1
        )
        self.assertIn("proxy", record["reason"].lower())

    def test_disabled_proxy_snapshot_omits_stale_credentials(self):
        self.configure(enabled=False, credentials=True)
        config = network_snapshot()
        self.assertFalse(config["settings"]["proxyEnabled"])
        self.assertEqual(config["credentials"]["password"], "")
        self.assertEqual(config["credentials"]["user"], "")

    def test_worker_launch_failure_is_reported_without_raw_exception(self):
        self.configure(enabled=False)
        layer = self.map_layer(f"http://127.0.0.1:{self.server.server_port}/wms")
        with patch(
            "mbtiles_batch_exporter.parallel_archive.subprocess.Popen",
            side_effect=OSError("private-interpreter-path"),
        ):
            manifest, _ = self.capture(layer)
        record = manifest["layers"][0]
        self.assertEqual(record["worker_error"]["stage"], "process_start")
        self.assertNotIn("private-interpreter-path", json.dumps(manifest))
