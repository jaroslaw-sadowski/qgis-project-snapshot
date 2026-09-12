# SPDX-License-Identifier: GPL-2.0-only

"""Confirmed empty output labels preserve original names and resume identifiers."""

import sqlite3
import unittest
import xml.etree.ElementTree as ET
from contextlib import closing
from hashlib import sha256
from html import escape
from unittest.mock import patch
from zipfile import ZipFile

import test_archive as fixtures
from qgis.core import QgsProject

from mbtiles_batch_exporter import archive as archive_module

SUFFIX = "_nie-bylo-obiketow-w-zasiegu"


class EmptyVectorNameTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    tearDown = fixtures.ArchiveTests.tearDown
    add_points = fixtures.ArchiveTests.add_points
    archive = fixtures.ArchiveTests.archive

    def test_empty_names_in_project_tree_report_and_gpkg_keep_originals(self):
        name = '<b>Łąka "A" O\'Neil</b>'
        empty = self.add_points(name, [(1, 9)])
        duplicate = self.add_points(name, [(1, 9)])
        empty.renderer().symbol().setColor(fixtures.QColor("#123456"))
        result = self.archive()
        manifest = archive_module.read_resume_manifest(result)
        records = {record["id"]: record for record in manifest["layers"]}
        local = QgsProject()
        project_path = next(result.glob("*.qgz"))
        try:
            self.assertTrue(local.read(str(project_path)))
            for layer in (empty, duplicate):
                record = records[layer.id()]
                self.assertEqual(record["name"], name)
                self.assertEqual(record["output_name"], name + SUFFIX)
                self.assertEqual(record["feature_count"], 0)
                self.assertEqual(record["status"], "saved")
                self.assertEqual(
                    record["table"],
                    "layer_" + sha256(layer.id().encode()).hexdigest()[:24],
                )
                saved = local.mapLayer(layer.id())
                self.assertEqual(saved.name(), name + SUFFIX)
                self.assertEqual(saved.id(), layer.id())
                self.assertEqual(
                    local.layerTreeRoot().findLayer(layer.id()).name(), name + SUFFIX
                )
                self.assertEqual(layer.name(), name)
            self.assertEqual(
                local.mapLayer(empty.id()).renderer().symbol().color().name(),
                "#123456",
            )
            self.assertFalse(
                local.layerTreeRoot()
                .findGroup(self.group.name())
                .itemVisibilityChecked()
            )
            self.assertEqual(local.mapLayer(self.layer.id()).name(), self.layer.name())
            self.assertNotIn("output_name", records[self.layer.id()])
        finally:
            local.clear()
        with ZipFile(project_path) as archive:
            xml = ET.fromstring(
                archive.read(next(n for n in archive.namelist() if n.endswith(".qgs")))
            )
        for node in xml.iter("layer-tree-layer"):
            if node.get("id") in (empty.id(), duplicate.id()):
                self.assertEqual(node.get("name"), name + SUFFIX)
        for node in xml.iter("legendlayer"):
            if any(
                child.get("layerid") in (empty.id(), duplicate.id())
                for child in node.iter("legendlayerfile")
            ):
                self.assertEqual(node.get("name"), name + SUFFIX)
        database = result / records[empty.id()]["local_source"][2:].split("|", 1)[0]
        with closing(sqlite3.connect(database)) as connection:
            identifiers = dict(
                connection.execute("SELECT table_name,identifier FROM gpkg_contents")
            )
        names = [
            identifiers[records[layer.id()]["table"]] for layer in (empty, duplicate)
        ]
        self.assertEqual(names[0], name + SUFFIX)
        self.assertTrue(names[1].startswith(name + SUFFIX + " ["))
        self.assertEqual(len(set(names)), 2)
        report = next(result.rglob("raport.html")).read_text()
        self.assertIn(f"<td>{escape(name + SUFFIX)}</td>", report)
        self.assertNotIn("<b>Łąka", report)
        self.assertEqual(self.original.read_bytes(), self.original_bytes)

    def test_resume_keeps_single_suffix_and_reuses_confirmed_empty_table(self):
        empty = self.add_points("Poza zasięgiem", [(1, 9)])
        previous = self.archive([empty.id()])
        before = next(
            record
            for record in archive_module.read_resume_manifest(previous)["layers"]
            if record["id"] == empty.id()
        )
        with patch.object(archive_module, "_write_vector") as write:
            result = self.archive([empty.id()], resume_from=previous)
        write.assert_not_called()
        after = next(
            record
            for record in archive_module.read_resume_manifest(result)["layers"]
            if record["id"] == empty.id()
        )
        self.assertTrue(after["reused"])
        self.assertEqual(after["table"], before["table"])
        self.assertEqual(after["name"], empty.name())
        self.assertEqual(after["output_name"], empty.name() + SUFFIX)
        self.assertEqual(after["output_name"].count(SUFFIX), 1)
        local = QgsProject()
        try:
            self.assertTrue(local.read(str(next(result.glob("*.qgz")))))
            self.assertEqual(local.mapLayer(empty.id()).name(), empty.name() + SUFFIX)
        finally:
            local.clear()

    def test_unconfirmed_empty_read_does_not_claim_absent_objects(self):
        empty = self.add_points("Niepotwierdzony wynik", [(1, 9)])
        original = archive_module._write_vector

        def unconfirmed(*args, **kwargs):
            count = original(*args, **kwargs)
            kwargs["read_details"]["empty_read_verified"] = None
            return count

        with patch.object(archive_module, "_write_vector", side_effect=unconfirmed):
            result = self.archive([empty.id()])
        record = next(
            record
            for record in archive_module.read_resume_manifest(result)["layers"]
            if record["id"] == empty.id()
        )
        self.assertEqual(record["feature_count"], 0)
        self.assertIsNone(record["empty_read_verified"])
        self.assertNotIn("output_name", record)
        self.assertNotIn(SUFFIX, next(result.rglob("raport.html")).read_text())
        local = QgsProject()
        try:
            self.assertTrue(local.read(str(next(result.glob("*.qgz")))))
            self.assertEqual(local.mapLayer(empty.id()).name(), empty.name())
        finally:
            local.clear()

    def test_failed_vector_and_raster_fallback_do_not_get_empty_suffix(self):
        for failure in (False, True):
            with self.subTest(raster_failure=failure):
                with patch.object(
                    archive_module, "_write_vector", side_effect=RuntimeError("read")
                ):
                    if failure:
                        with patch.object(
                            archive_module,
                            "write_rendered_raster",
                            side_effect=RuntimeError("render"),
                        ):
                            result = self.archive(zoom_min=17, zoom_max=17)
                    else:
                        result = self.archive(zoom_min=17, zoom_max=17)
                record = archive_module.read_resume_manifest(result)["layers"][0]
                self.assertNotIn("output_name", record)
                self.assertNotIn(SUFFIX, next(result.rglob("raport.html")).read_text())
                self.assertEqual(record["status"], "failed" if failure else "saved")
                if not failure:
                    self.assertEqual(record["method"], "raster_render")

    def test_failed_retry_of_unconfirmed_vector_does_not_abort_other_results(self):
        empty = self.add_points("Niepotwierdzona pusta warstwa", [(100, 100)])
        original = archive_module._write_vector

        def unconfirmed(*args, **kwargs):
            count = original(*args, **kwargs)
            if args[0].id() == empty.id():
                kwargs["read_details"]["empty_read_verified"] = None
            return count

        # Exercise remote-zero continuation independently of service availability;
        # geometry reads and both output projects still use native QGIS providers.
        with patch.object(empty, "providerType", return_value="WFS"):
            with patch.object(archive_module, "_write_vector", side_effect=unconfirmed):
                previous = self.archive()
            first = archive_module.read_resume_manifest(previous)
            previous_records = {record["id"]: record for record in first["layers"]}
            self.assertEqual(previous_records[empty.id()]["feature_count"], 0)
            self.assertIsNone(previous_records[empty.id()]["empty_read_verified"])
            with (
                patch.object(
                    archive_module, "_write_vector", side_effect=RuntimeError("read")
                ) as write,
                patch.object(
                    archive_module,
                    "write_rendered_raster",
                    side_effect=RuntimeError("render"),
                ) as raster,
            ):
                result = self.archive(resume_from=previous)
        write.assert_called_once()
        self.assertEqual(write.call_args.args[0].id(), empty.id())
        raster.assert_called_once()
        second = archive_module.read_resume_manifest(result)
        records = {record["id"]: record for record in second["layers"]}
        self.assertEqual(records[empty.id()]["status"], "failed")
        self.assertNotIn("local_source", records[empty.id()])
        self.assertNotIn("output_name", records[empty.id()])
        self.assertEqual(records[self.layer.id()]["status"], "saved")
        self.assertTrue(records[self.layer.id()]["reused"])
        self.assertEqual(
            records[self.layer.id()]["feature_count"],
            previous_records[self.layer.id()]["feature_count"],
        )
        self.assertTrue(second["local_layer_audit"]["passed"])
        self.assertNotIn(SUFFIX, (result / "raport.html").read_text())
        local = QgsProject()
        try:
            self.assertTrue(local.read(str(next(result.glob("*.qgz")))))
            self.assertEqual(set(local.mapLayers()), {self.layer.id()})
            self.assertEqual(
                local.mapLayer(self.layer.id()).featureCount(),
                records[self.layer.id()]["feature_count"],
            )
        finally:
            local.clear()
