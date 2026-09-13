# SPDX-License-Identifier: GPL-2.0-only

"""Reject XML entities and preserve data when SQL identifiers contain quotes."""

import sqlite3
import unittest
from contextlib import closing
from unittest.mock import Mock, patch

import test_archive as fixtures
from qgis.core import QgsMapLayerStyle, QgsSqliteUtils

from mbtiles_batch_exporter.archive import _source_fingerprint
from mbtiles_batch_exporter.archive_resources import ProjectResources
from mbtiles_batch_exporter.raster_archive import _empty_zoom_overviews
from mbtiles_batch_exporter.vendor.defusedxml import DefusedXmlException
from mbtiles_batch_exporter.vendor.defusedxml import ElementTree as ET


class SecurityTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    tearDown = fixtures.ArchiveTests.tearDown
    add_points = fixtures.ArchiveTests.add_points

    def test_entity_expansion_and_external_entities_are_rejected(self):
        payloads = (
            '<!DOCTYPE x [<!ENTITY a "payload"><!ENTITY b "&a;&a;">]><x>&b;</x>',
            '<!DOCTYPE x [<!ENTITY a SYSTEM "file:///private-marker">]><x>&a;</x>',
            '<!DOCTYPE x [<!ENTITY % a SYSTEM "https://example.invalid/private">'
            "%a;]><x/>",
        )
        for text in payloads:
            for encoding in ("utf-8", "utf-16"):
                with self.subTest(text=text, encoding=encoding):
                    with self.assertRaises(DefusedXmlException):
                        ET.fromstring(text.encode(encoding))
                    path = self.folder / "hostile.xml"
                    path.write_bytes(text.encode(encoding))
                    with self.assertRaises(DefusedXmlException):
                        ET.parse(path)

    def test_normal_qgis_doctype_and_builtin_entities_still_work(self):
        root = ET.fromstring(
            '<!DOCTYPE qgis PUBLIC "http://mrcc.com/qgis.dtd" "SYSTEM">'
            "<qgis><name>A &amp; B</name></qgis>"
        )
        self.assertEqual(root.findtext("name"), "A & B")

    def test_rejected_resource_is_not_left_for_qgis_to_load(self):
        bad = self.folder / "bad.svg"
        payload = '<!DOCTYPE svg [<!ENTITY x "expanded">]><svg>&x;</svg>'
        bad.write_text(payload)
        parent = self.folder / "parent.svg"
        parent.write_text(f'<svg><image href="{bad}"/></svg>')
        output = self.folder / "output"
        resources = ProjectResources(
            self.project, output, lambda: False, lambda _: None
        )
        copied = resources.copy(str(parent), "symbol")
        self.assertEqual(ET.parse(output / copied[2:]).find("image").get("href"), "")
        self.assertEqual(resources.copy(str(bad), "symbol"), "")
        self.assertEqual(bad.read_text(), payload)
        self.assertFalse(list(output.rglob("bad.svg")))
        self.assertTrue(resources.issues)

    def test_style_validation_keeps_existing_resume_fingerprint(self):
        import hashlib
        import json
        from xml.etree.ElementTree import canonicalize

        style = QgsMapLayerStyle()
        style.readFromLayer(self.layer)
        previous = [
            self.layer.source(),
            self.layer.providerType(),
            self.layer.crs().toWkt(),
            self.layer.subsetString(),
            canonicalize(style.xmlData()),
        ]
        self.assertEqual(
            _source_fingerprint(self.layer),
            hashlib.sha256(
                json.dumps(previous, ensure_ascii=False).encode()
            ).hexdigest(),
        )
        fake = Mock()
        fake.xmlData.return_value = '<!DOCTYPE x [<!ENTITY a "bad">]><x>&a;</x>'
        with patch(
            "mbtiles_batch_exporter.archive.QgsMapLayerStyle", return_value=fake
        ):
            with self.assertRaises(DefusedXmlException):
                _source_fingerprint(self.layer)

    def test_quoted_tile_table_cannot_execute_sql_from_its_name(self):
        database = self.folder / "quoted.sqlite"
        table = 'tiles"; DROP TABLE sentinel; --'
        quoted = QgsSqliteUtils.quotedIdentifier(table)
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("CREATE TABLE sentinel (value INTEGER)")
            connection.execute("INSERT INTO sentinel VALUES (42)")
            connection.execute(
                f"CREATE TABLE {quoted} (zoom_level INTEGER, tile_column INTEGER, "
                "tile_row INTEGER, tile_data BLOB)"
            )
        stats = {"levels": [{"zoom": 0, "empty": 1, "nonempty": 0, "failed": 0}]}
        self.assertEqual(_empty_zoom_overviews(database, table, stats), [0])
        self.assertEqual(_empty_zoom_overviews(database, table, stats), [0])
        with closing(sqlite3.connect(database)) as connection, connection:
            self.assertEqual(
                connection.execute("SELECT * FROM sentinel").fetchall(), [(42,)]
            )
            self.assertEqual(
                connection.execute(f"SELECT count(*) FROM {quoted}").fetchone(), (1,)
            )


if __name__ == "__main__":
    unittest.main()
