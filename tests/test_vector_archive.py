# SPDX-License-Identifier: GPL-2.0-only

"""Vector exports through the real QGIS WFS provider and a local HTTP service."""

import json
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from test_archive import APP

from mbtiles_batch_exporter.archive import _write_vector, create_archive
from mbtiles_batch_exporter.diagnostics import Diagnostics


class VectorWfsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                params = {
                    key.upper(): values[-1]
                    for key, values in parse_qs(urlsplit(self.path).query).items()
                }
                service = self.server
                request = params.get("REQUEST", "").upper()
                service.requests.append(params)
                if request == "GETCAPABILITIES":
                    url = f"http://127.0.0.1:{service.server_port}/"
                    operations = "".join(
                        f"<{operation}><DCPType><HTTP><Get onlineResource='{url}'/>"
                        f"</HTTP></DCPType></{operation}>"
                        for operation in (
                            "GetCapabilities",
                            "DescribeFeatureType",
                            "GetFeature",
                        )
                    )
                    body = (
                        "<WFS_Capabilities version='1.0.0' "
                        "xmlns='http://www.opengis.net/wfs' "
                        "xmlns:test='http://example.test/features'>"
                        "<Service><Name>WFS</Name>"
                        "<Title>Local fixture</Title></Service>"
                        f"<Capability><Request>{operations}</Request></Capability>"
                        "<FeatureTypeList><Operations><Query/></Operations>"
                        "<FeatureType><Name>test:points</Name><Title>Points</Title>"
                        "<SRS>EPSG:4326</SRS><LatLongBoundingBox minx='18' miny='49' "
                        "maxx='22' maxy='53'/></FeatureType></FeatureTypeList>"
                        "</WFS_Capabilities>"
                    )
                elif request == "DESCRIBEFEATURETYPE":
                    body = (
                        "<xsd:schema xmlns:xsd='http://www.w3.org/2001/XMLSchema' "
                        "xmlns:gml='http://www.opengis.net/gml' "
                        "xmlns:test='http://example.test/features' "
                        "targetNamespace='http://example.test/features' "
                        "elementFormDefault='qualified'>"
                        "<xsd:import namespace='http://www.opengis.net/gml'/>"
                        "<xsd:complexType name='pointsType'><xsd:complexContent>"
                        "<xsd:extension base='gml:AbstractFeatureType'><xsd:sequence>"
                        "<xsd:element name='geom' type='gml:PointPropertyType'/>"
                        "<xsd:element name='number' type='xsd:int'/>"
                        "<xsd:element name='label' type='xsd:string'/>"
                        "</xsd:sequence></xsd:extension></xsd:complexContent>"
                        "</xsd:complexType><xsd:element name='points' "
                        "type='test:pointsType' substitutionGroup='gml:_Feature'/>"
                        "</xsd:schema>"
                    )
                elif service.failure:
                    body = (
                        "<ows:ExceptionReport xmlns:ows='http://www.opengis.net/ows'>"
                        "<ows:Exception exceptionCode='NoApplicableCode'>"
                        "<ows:ExceptionText>password=private-test-value"
                        "</ows:ExceptionText></ows:Exception></ows:ExceptionReport>"
                    )
                else:
                    features = list(service.features)
                    bounds = None
                    if params.get("BBOX"):
                        bounds = [float(v) for v in params["BBOX"].split(",")[:4]]
                    if params.get("FILTER"):
                        tree = ET.fromstring(params["FILTER"])
                        coordinates = tree.find(".//{*}BBOX//{*}coordinates")
                        if coordinates is not None:
                            bounds = [
                                float(v)
                                for point in coordinates.text.split()
                                for v in point.split(",")
                            ]
                        literal = tree.find(".//{*}PropertyIsEqualTo/{*}Literal")
                        if literal is not None:
                            features = [
                                f for f in features if f[0] == int(literal.text)
                            ]
                    if bounds:
                        xmin, ymin, xmax, ymax = bounds
                        features = [
                            f
                            for f in features
                            if xmin <= f[1] <= xmax and ymin <= f[2] <= ymax
                        ]
                    limit = int(params.get("MAXFEATURES", len(features)))
                    members = "".join(
                        f"<gml:featureMember><test:points fid='points.{number}'>"
                        "<test:geom><gml:Point srsName='EPSG:4326'>"
                        f"<gml:coordinates>{x},{y}</gml:coordinates>"
                        "</gml:Point></test:geom>"
                        f"<test:number>{number}</test:number>"
                        f"<test:label>point {number}</test:label>"
                        "</test:points></gml:featureMember>"
                        for number, x, y in features[:limit]
                    )
                    body = (
                        "<wfs:FeatureCollection xmlns:wfs='http://www.opengis.net/wfs' "
                        "xmlns:gml='http://www.opengis.net/gml' "
                        "xmlns:test='http://example.test/features' "
                        f"numberOfFeatures='{len(features[:limit])}'>"
                        f"{members}</wfs:FeatureCollection>"
                    )
                payload = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        try:
            cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except PermissionError as error:
            raise unittest.SkipTest(
                "Local sockets unavailable for real WFS test"
            ) from error
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.assertIsNotNone(APP)
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.project = QgsProject()
        self.read_details = {}
        self.crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.area = QgsGeometry.fromRect(QgsRectangle(18.99, 51.99, 19.005, 52.005))
        self.server.features = [(1, 19, 52), (2, 19.01, 52.01), (3, 21, 50)]
        self.server.failure = False
        self.server.requests = []
        uri = (
            f"url='http://127.0.0.1:{self.server.server_port}/{id(self)}' "
            "typename='test:points' version='1.0.0' srsname='EPSG:4326' "
            "restrictToRequestBBOX='1'"
        )
        self.layer = QgsVectorLayer(uri, "points", "WFS")
        self.assertTrue(self.layer.isValid())
        self.project.addMapLayer(self.layer)

    def tearDown(self):
        self.project.clear()
        self.layer = None
        self.temporary.cleanup()

    def write(self, area=None, crs=None):
        return _write_vector(
            self.layer,
            self.area if area is None else area,
            self.crs if crs is None else crs,
            self.project,
            self.folder / "vectors.gpkg",
            "points",
            lambda: False,
            lambda count: None,
            Diagnostics(self.folder / "diagnostic.jsonl"),
            self.read_details,
        )

    def test_actual_wfs_reprojects_area_and_preserves_attributes(self):
        projected = QgsCoordinateReferenceSystem("EPSG:3857")
        area = QgsGeometry(self.area)
        area.transform(QgsCoordinateTransform(self.crs, projected, self.project))
        self.assertEqual(self.write(area, projected), 1)
        local = QgsVectorLayer(str(self.folder / "vectors.gpkg"), "local", "ogr")
        feature = next(local.getFeatures())
        self.assertEqual(feature["number"], 1)
        self.assertEqual(feature["label"], "point 1")

    def test_actual_wfs_empty_area_is_valid(self):
        empty = QgsGeometry.fromRect(QgsRectangle(20, 51, 20.001, 51.001))
        self.assertEqual(self.write(empty), 0)
        self.assertEqual(
            self.read_details,
            {"vector_read_version": 2, "empty_read_verified": True},
        )

    def test_actual_wfs_exception_is_not_successful_empty_result(self):
        self.server.failure = True
        with self.assertRaises(RuntimeError):
            self.write()
        self.assertNotIn(
            "private-test-value", (self.folder / "diagnostic.jsonl").read_text()
        )

    def test_actual_wfs_cached_empty_result_is_refreshed(self):
        self.server.features = []
        iterator = self.layer.getFeatures(
            QgsFeatureRequest().setFilterRect(self.area.boundingBox())
        )
        self.assertEqual(list(iterator), [])
        self.server.features = [(1, 19, 52)]
        self.assertEqual(self.write(), 1)

    def test_actual_wfs_subset_is_preserved(self):
        self.assertTrue(
            self.layer.setSubsetString("SELECT * FROM points WHERE number = 2")
        )
        subset = self.layer.subsetString()
        area = QgsGeometry.fromRect(QgsRectangle(18.9, 51.9, 19.1, 52.1))
        self.assertEqual(self.write(area), 1)
        local = QgsVectorLayer(str(self.folder / "vectors.gpkg"), "local", "ogr")
        self.assertEqual(next(local.getFeatures())["number"], 2)
        self.assertEqual(self.layer.subsetString(), subset)

    def test_resume_rechecks_legacy_wfs_zero_and_gets_new_features(self):
        self.project.setCrs(self.crs)
        self.server.features = []
        previous = create_archive(
            self.project, [self.layer.id()], self.area, self.crs, self.folder
        )
        manifest_path = previous / "diagnostyka" / "manifest.json"
        first = json.loads(manifest_path.read_text())
        record = first["layers"][0]
        self.assertEqual(record["status"], "saved")
        self.assertEqual(record["feature_count"], 0)
        self.assertEqual(record["vector_read_version"], 2)
        self.assertTrue(record["empty_read_verified"])
        # Preserve the canonical current source fingerprint; only emulate the
        # missing read verification in an archive from before this fix.
        record.pop("vector_read_version")
        record.pop("empty_read_verified")
        manifest_path.write_text(json.dumps(first), encoding="utf-8")
        self.server.features = [(1, 19, 52)]
        with patch(
            "mbtiles_batch_exporter.archive._write_vector", wraps=_write_vector
        ) as write:
            continued = create_archive(
                self.project,
                [self.layer.id()],
                self.area,
                self.crs,
                self.folder,
                resume_from=previous,
            )
        write.assert_called_once()
        second = json.loads((continued / "diagnostyka" / "manifest.json").read_text())
        self.assertEqual(second["layers"][0]["status"], "saved")
        self.assertEqual(second["layers"][0]["feature_count"], 1)
        self.assertEqual(second["layers"][0]["vector_read_version"], 2)
        self.assertEqual(second["continuation"]["reused_layers"], 0)
        self.assertTrue(second["local_layer_audit"]["passed"])
        local = QgsVectorLayer(str(continued / "dane" / "dane.gpkg"), "local", "ogr")
        self.assertEqual(local.featureCount(), 1)
        self.assertEqual(next(local.getFeatures())["label"], "point 1")


class VectorReadChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.project = QgsProject()
        self.read_details = {}
        self.crs = QgsCoordinateReferenceSystem("EPSG:2180")
        self.area = QgsGeometry.fromRect(QgsRectangle(1, 1, 2, 2))
        self.layer = QgsVectorLayer(
            "Point?crs=EPSG:2180&field=number:integer", "empty", "memory"
        )
        self.project.addMapLayer(self.layer)

    def tearDown(self):
        self.project.clear()
        self.temporary.cleanup()

    def write(self, layer=None, crs=None):
        return _write_vector(
            self.layer if layer is None else layer,
            self.area,
            self.crs if crs is None else crs,
            self.project,
            self.folder / "vectors.gpkg",
            "empty",
            lambda: False,
            lambda count: None,
            Diagnostics(self.folder / "diagnostic.jsonl"),
            self.read_details,
        )

    def mssql_layer(self):
        layer = Mock(wraps=self.layer)
        layer.providerType.return_value = "mssql"
        uri = QgsDataSourceUri()
        uri.setConnection("private-host", "1433", "private-db", "user", "secret-token")
        uri.setDataSource("odd]schema", "table]name", "geom")
        return layer, uri

    def test_empty_mssql_query_failure_is_not_saved_and_omits_secrets(self):
        layer, uri = self.mssql_layer()
        connection = Mock()
        connection.executeSql.side_effect = RuntimeError("secret-token private-host")
        registry = Mock()
        registry.providerMetadata.return_value.createConnection.return_value = (
            connection
        )
        with (
            patch.object(
                self.layer.dataProvider(), "dataSourceUri", return_value=uri.uri()
            ),
            patch(
                "mbtiles_batch_exporter.archive.QgsProviderRegistry.instance",
                return_value=registry,
            ),
            self.assertRaisesRegex(RuntimeError, "MSSQL") as raised,
        ):
            self.write(layer)
        self.assertNotIn("secret-token", str(raised.exception))
        text = (self.folder / "diagnostic.jsonl").read_text()
        self.assertNotIn("secret-token", text)
        self.assertNotIn("private-host", text)
        row = json.loads(text.splitlines()[-1])
        self.assertFalse(row["read_complete"])
        self.assertEqual(row["empty_source_probe"], "unconfirmed")

    def test_empty_mssql_probe_keeps_subset_and_quotes_identifiers(self):
        layer, uri = self.mssql_layer()
        self.assertTrue(self.layer.setSubsetString('"number" = 7'))
        connection = Mock()
        connection.executeSql.return_value = []
        registry = Mock()
        registry.providerMetadata.return_value.createConnection.return_value = (
            connection
        )
        with (
            patch.object(
                self.layer.dataProvider(), "dataSourceUri", return_value=uri.uri()
            ),
            patch(
                "mbtiles_batch_exporter.archive.QgsProviderRegistry.instance",
                return_value=registry,
            ),
        ):
            self.assertEqual(self.write(layer), 0)
        connection.executeSql.assert_called_once_with(
            'SELECT TOP (1) 1 FROM [odd]]schema].[table]]name] WHERE ("number" = 7)'
        )
        text = (self.folder / "diagnostic.jsonl").read_text()
        row = json.loads(text.splitlines()[-1])
        self.assertTrue(row["read_complete"])
        self.assertEqual(row["empty_source_probe"], "source_empty")
        self.assertEqual(self.read_details["vector_read_version"], 2)
        self.assertTrue(self.read_details["empty_read_verified"])
        self.assertTrue(row["empty_read_verified"])

    def test_mssql_table_with_rows_does_not_verify_empty_area(self):
        layer, uri = self.mssql_layer()
        connection = Mock()
        connection.executeSql.return_value = [[1]]
        registry = Mock()
        registry.providerMetadata.return_value.createConnection.return_value = (
            connection
        )
        with (
            patch.object(
                self.layer.dataProvider(), "dataSourceUri", return_value=uri.uri()
            ),
            patch(
                "mbtiles_batch_exporter.archive.QgsProviderRegistry.instance",
                return_value=registry,
            ),
        ):
            self.assertEqual(self.write(layer), 0)
        text = (self.folder / "diagnostic.jsonl").read_text()
        row = json.loads(text.splitlines()[-1])
        self.assertEqual(row["empty_source_probe"], "source_has_rows")
        self.assertIsNone(row["empty_read_verified"])
        self.assertIsNone(self.read_details["empty_read_verified"])

    def test_invalid_area_crs_cannot_be_saved_as_empty(self):
        with self.assertRaises(ValueError):
            self.write(crs=QgsCoordinateReferenceSystem())

    def test_wfs_edit_buffer_does_not_reload_provider(self):
        self.assertTrue(self.layer.startEditing())
        layer = Mock(wraps=self.layer)
        layer.providerType.return_value = "WFS"
        with patch.object(self.layer.dataProvider(), "reloadData") as reload:
            self.assertEqual(self.write(layer), 0)
        reload.assert_not_called()
        self.assertTrue(self.layer.isEditable())


if __name__ == "__main__":
    unittest.main()
