# SPDX-License-Identifier: GPL-2.0-only

"""Integration checks using real QGIS providers and temporary local files.

Run: QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
"""

import atexit
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

# Never read or modify the developer's desktop QGIS profile in tests.
if "QGIS_CUSTOM_CONFIG_PATH" not in os.environ:
    TEST_PROFILE = tempfile.TemporaryDirectory(prefix="snapshot-test-profile-")
    os.environ["QGIS_CUSTOM_CONFIG_PATH"] = TEST_PROFILE.name
    atexit.register(TEST_PROFILE.cleanup)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QGIS_SNAPSHOT_LANGUAGE", "pl")

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsRasterLayer,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from mbtiles_batch_exporter.archive import create_archive, polygon_area
from mbtiles_batch_exporter.archive_dialog import ArchiveDialog

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.project = QgsProject()
        self.crs = QgsCoordinateReferenceSystem("EPSG:2180")
        self.project.setCrs(self.crs)
        self.area = QgsGeometry.fromWkt("POLYGON((0 0,10 10,11 10,1 0,0 0))")
        self.group = self.project.layerTreeRoot().addGroup("Wyłączona grupa")
        self.group.setItemVisibilityChecked(False)
        self.layer = self.add_points("Ta sama nazwa", [(5, 5), (1, 9), (0, 0)])
        self.layer.renderer().symbol().setColor(QColor("#123456"))
        self.layer.setFieldAlias(1, "Opis obiektu")
        self.original = self.folder / "oryginał.qgz"
        self.assertTrue(self.project.write(str(self.original)))
        self.original_bytes = self.original.read_bytes()

    def tearDown(self):
        self.project.clear()
        self.temporary.cleanup()

    def add_points(self, name, coordinates):
        layer = QgsVectorLayer(
            "Point?crs=EPSG:2180&field=fid:integer&field=opis:string", name, "memory"
        )
        features = []
        for index, (x, y) in enumerate(coordinates):
            feature = QgsFeature(layer.fields())
            feature.setAttributes([42, f"obiekt {index}"])
            feature.setGeometry(QgsGeometry.fromWkt(f"POINT({x} {y})"))
            features.append(feature)
        self.assertTrue(layer.dataProvider().addFeatures(features)[0])
        layer.updateExtents()
        self.project.addMapLayer(layer, False)
        self.group.addLayer(layer)
        return layer

    def archive(self, selected=None, **kwargs):
        return create_archive(
            self.project,
            selected if selected is not None else self.project.mapLayers().keys(),
            self.area,
            self.crs,
            self.folder,
            **kwargs,
        )

    def manifest(self, result):
        return json.loads(
            (result / "diagnostyka" / "manifest.json").read_text(encoding="utf-8")
        )

    def test_vectors_keep_attributes_edits_styles_tree_and_source_state(self):
        second = self.add_points("Ta sama nazwa", [(6, 6)])
        self.project.layerTreeRoot().setHasCustomLayerOrder(True)
        self.project.layerTreeRoot().setCustomLayerOrder([second, self.layer])
        self.layer.startEditing()
        original_features = list(self.layer.getFeatures())
        feature = original_features[0]
        self.assertTrue(
            self.layer.changeAttributeValue(feature.id(), 1, "niezapisana zmiana")
        )
        self.assertTrue(
            self.layer.changeGeometry(
                original_features[1].id(), QgsGeometry.fromWkt("POINT(8 8)")
            )
        )
        self.assertTrue(self.layer.deleteFeature(original_features[2].id()))
        added = QgsFeature(self.layer.fields())
        added.setAttributes([42, "niezapisany nowy obiekt"])
        added.setGeometry(QgsGeometry.fromWkt("POINT(7 7)"))
        self.assertTrue(self.layer.addFeature(added))
        self.project.setDirty(True)
        original_path_type = self.project.filePathStorage()
        result = self.archive()
        manifest = self.manifest(result)
        events = [
            json.loads(line)
            for line in (result / "diagnostyka" / "diagnostic.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertEqual(events[-1]["event"], "archive_end")
        self.assertTrue(any(e["event"] == "vector_read" for e in events))
        iterations = [e for e in events if e["event"] == "vector_iteration"]
        self.assertEqual([e["written"] for e in iterations], [3, 1])
        self.assertTrue(all(e["received"] >= e["written"] for e in iterations))
        self.assertTrue(all(e["read_complete"] for e in iterations))

        self.assertEqual(manifest["status"], "partial")
        self.assertEqual([row["feature_count"] for row in manifest["layers"]], [3, 1])
        self.assertEqual(len({row["table"] for row in manifest["layers"]}), 2)
        self.assertEqual(self.project.fileName(), str(self.original))
        self.assertEqual(self.project.filePathStorage(), original_path_type)
        self.assertTrue(self.project.isDirty())
        self.assertTrue(self.layer.isModified())
        self.assertFalse(self.group.itemVisibilityChecked())
        self.assertTrue(self.group.findLayer(self.layer.id()).itemVisibilityChecked())
        self.assertEqual(self.original.read_bytes(), self.original_bytes)

        moved = self.folder / "przeniesione"
        shutil.move(str(result), str(moved))
        copy = QgsProject()
        try:
            self.assertTrue(copy.read(str(next(moved.glob("*.qgz")))))
            self.assertEqual(copy.crs(), self.crs)
            self.assertEqual(set(copy.mapLayers()), {self.layer.id(), second.id()})
            local = copy.mapLayer(self.layer.id())
            self.assertTrue(local.isValid())
            self.assertEqual(local.providerType(), "ogr")
            self.assertEqual(local.featureCount(), 3)
            self.assertEqual([f["fid"] for f in local.getFeatures()], [42, 42, 42])
            self.assertIn(
                "niezapisana zmiana", [f["opis"] for f in local.getFeatures()]
            )
            self.assertIn(
                "niezapisany nowy obiekt", [f["opis"] for f in local.getFeatures()]
            )
            self.assertEqual(
                {f.geometry().asWkt() for f in local.getFeatures()},
                {"Point (5 5)", "Point (7 7)", "Point (8 8)"},
            )
            self.assertEqual(local.renderer().symbol().color().name(), "#123456")
            self.assertEqual(
                local.attributeAlias(local.fields().indexFromName("opis")),
                "Opis obiektu",
            )
            self.assertFalse(
                copy.layerTreeRoot()
                .findGroup("Wyłączona grupa")
                .itemVisibilityChecked()
            )
            self.assertEqual(
                [layer.id() for layer in copy.layerTreeRoot().customLayerOrder()],
                [second.id(), self.layer.id()],
            )
        finally:
            copy.clear()
        for name, digest in manifest["sha256"].items():
            self.assertEqual(
                hashlib.sha256((moved / name).read_bytes()).hexdigest(), digest
            )

    def test_filters_materialized_and_whole_geometry_kept(self):
        self.layer.setSubsetString("\"opis\" = 'obiekt 0'")
        result = self.archive()
        row = self.manifest(result)["layers"][0]
        self.assertEqual(row["feature_count"], 1)
        copy = QgsProject()
        try:
            self.assertTrue(copy.read(str(next(result.glob("*.qgz")))))
            self.assertEqual(copy.mapLayer(self.layer.id()).subsetString(), "")
        finally:
            copy.clear()
        line = QgsVectorLayer("LineString?crs=EPSG:2180", "Linia", "memory")
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt("LINESTRING(-100 5,100 5)"))
        line.dataProvider().addFeatures([feature])
        line.updateExtents()
        self.project.addMapLayer(line)
        result = self.archive([line.id()])
        row = next(r for r in self.manifest(result)["layers"] if r["id"] == line.id())
        local = QgsVectorLayer(
            f"{result}/dane/dane.gpkg|layername={row['table']}", "local", "ogr"
        )
        self.assertEqual(
            next(local.getFeatures()).geometry().asWkt(), feature.geometry().asWkt()
        )

    def test_excluded_unsupported_and_invalid_layers_reported_without_remote_sources(
        self,
    ):
        other = self.add_points("Pominięta", [(3, 3)])
        invalid = QgsVectorLayer(
            str(self.folder / "missing.gpkg"), "Brak źródła", "ogr"
        )
        self.project.addMapLayer(invalid)
        raster = QgsRasterLayer(str(self.folder / "missing.tif"), "<b>Mapa</b>", "gdal")
        self.project.addMapLayer(raster)
        result = self.archive([self.layer.id(), invalid.id(), raster.id()])
        statuses = {r["id"]: r["status"] for r in self.manifest(result)["layers"]}
        self.assertEqual(statuses[other.id()], "excluded")
        self.assertEqual(statuses[invalid.id()], "failed")
        self.assertEqual(statuses[raster.id()], "failed")
        with ZipFile(next(result.glob("*.qgz"))) as z:
            xml = z.read(next(n for n in z.namelist() if n.endswith(".qgs"))).decode()
        self.assertNotIn("missing.gpkg", xml)
        self.assertNotIn("missing.tif", xml)
        self.assertIn("&lt;b&gt;Mapa&lt;/b&gt;", (result / "raport.html").read_text())
        self.assertFalse(list(result.glob("_source*")))

    def test_polygon_selection_and_invalid_area(self):
        mask = QgsVectorLayer("Polygon?crs=EPSG:2180", "Pas", "memory")
        features = []
        for wkt in (self.area.asWkt(), "POLYGON((20 20,21 20,21 21,20 21,20 20))"):
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        mask.dataProvider().addFeatures(features)
        self.assertAlmostEqual(polygon_area(mask).area(), self.area.area() + 1)
        mask.selectByIds([next(mask.getFeatures()).id()])
        self.assertTrue(polygon_area(mask).equals(self.area))
        with self.assertRaises(ValueError):
            create_archive(
                self.project, [self.layer.id()], QgsGeometry(), self.crs, self.folder
            )
        with self.assertRaises(ValueError):
            self.archive([])

    def test_cancellation_keeps_finished_layers_and_no_partial_table(self):
        second = self.add_points("Druga", [(3, 3)])
        cancelled = False

        def layer_status(record, completed, total):
            nonlocal cancelled
            if record["id"] == second.id() and record["status"] == "pending":
                cancelled = True

        result = self.archive(cancelled=lambda: cancelled, layer_status=layer_status)
        manifest = self.manifest(result)
        self.assertTrue(manifest["cancelled"])
        statuses = {r["id"]: r["status"] for r in manifest["layers"]}
        self.assertEqual(statuses[self.layer.id()], "saved")
        self.assertEqual(statuses[second.id()], "cancelled")
        with closing(sqlite3.connect(result / "dane" / "dane.gpkg")) as database:
            self.assertEqual(
                database.execute(
                    "SELECT count(*) FROM gpkg_contents WHERE data_type='features'"
                ).fetchone()[0],
                1,
            )

    def test_cancel_during_layer_removes_incomplete_table(self):
        calls = 0

        def cancelled():
            nonlocal calls
            calls += 1
            return calls >= 3

        result = self.archive(cancelled=cancelled)
        self.assertEqual(self.manifest(result)["layers"][0]["status"], "cancelled")
        with closing(sqlite3.connect(result / "dane" / "dane.gpkg")) as database:
            self.assertEqual(
                database.execute("SELECT count(*) FROM gpkg_contents").fetchone()[0], 0
            )

    def test_snapshot_failure_restores_project_and_keeps_recovery_manifest(self):
        self.project.setDirty(True)
        with patch.object(QgsProject, "write", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "kopii projektu"):
                self.archive()
        self.assertEqual(self.project.fileName(), str(self.original))
        self.assertTrue(self.project.isDirty())
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        self.assertFalse(list(self.folder.glob(".archive-*")))
        checkpoints = list(self.folder.glob("*_archive_*.in-progress-*"))
        self.assertEqual(len(checkpoints), 1)
        logs = list((checkpoints[0] / "diagnostyka").glob("diagnostic.jsonl"))
        self.assertEqual(len(logs), 1)
        self.assertIn('"archive_exception"', logs[0].read_text())
        self.assertFalse((checkpoints[0] / "_source.qgz").exists())
        self.assertFalse((checkpoints[0] / ".workers").exists())
        manifest = self.manifest(checkpoints[0])
        self.assertTrue(manifest["checkpoint"])
        self.assertEqual(manifest["layers"][0]["status"], "pending")

    def test_repeated_archive_never_overwrites_previous(self):
        first = self.archive()
        contents = (first / "diagnostyka" / "manifest.json").read_bytes()
        second = self.archive()
        self.assertNotEqual(first, second)
        self.assertEqual(
            (first / "diagnostyka" / "manifest.json").read_bytes(), contents
        )

    def test_failed_vector_write_falls_back_to_image_and_continues(self):
        second = self.add_points("Druga", [(3, 3)])
        original_add = QgsVectorFileWriter.addFeature
        failed = False

        def fail_once(writer, *args):
            nonlocal failed
            if not failed:
                failed = True
                return False
            return original_add(writer, *args)

        with patch.object(QgsVectorFileWriter, "addFeature", fail_once):
            result = self.archive(zoom_min=17, zoom_max=17)
        statuses = {r["id"]: r["status"] for r in self.manifest(result)["layers"]}
        self.assertEqual(statuses[self.layer.id()], "saved")
        self.assertEqual(statuses[second.id()], "saved")
        first = next(
            r for r in self.manifest(result)["layers"] if r["id"] == self.layer.id()
        )
        self.assertEqual(first["method"], "raster_render")
        self.assertIn("nie zachowuje obiektów", first["reason"])
        with closing(sqlite3.connect(result / "dane" / "dane.gpkg")) as database:
            self.assertEqual(
                database.execute("SELECT count(*) FROM gpkg_contents").fetchone()[0], 2
            )
            self.assertEqual(
                database.execute(
                    "SELECT count(*) FROM gpkg_contents WHERE data_type='features'"
                ).fetchone()[0],
                1,
            )

    def test_zero_features_is_valid_not_a_download_error(self):
        empty = self.add_points("Poza pasem", [(1, 9)])
        result = self.archive([empty.id()])
        record = next(
            r for r in self.manifest(result)["layers"] if r["id"] == empty.id()
        )
        self.assertEqual(record["status"], "saved")
        self.assertEqual(record["feature_count"], 0)

    def test_coordinate_transform_to_layer_crs(self):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "Inny CRS", "memory")
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromWkt("POINT(19 52)"))
        layer.dataProvider().addFeatures([feature])
        layer.updateExtents()
        self.project.addMapLayer(layer)
        from qgis.core import QgsCoordinateTransform

        area = QgsGeometry.fromWkt(
            "POLYGON((18.9 51.9,19.1 51.9,19.1 52.1,18.9 52.1,18.9 51.9))"
        )
        area.transform(QgsCoordinateTransform(layer.crs(), self.crs, self.project))
        result = create_archive(self.project, [layer.id()], area, self.crs, self.folder)
        record = next(
            r for r in self.manifest(result)["layers"] if r["id"] == layer.id()
        )
        self.assertEqual(record["feature_count"], 1)
        self.assertEqual(record["crs"], "EPSG:4326")

    def test_dialog_selects_hidden_layers_without_changing_original_tree(self):
        with patch("mbtiles_batch_exporter.archive_dialog.QgsProject") as project_class:
            project_class.instance.return_value = self.project
            dialog = ArchiveDialog(None)
        try:
            self.assertEqual(dialog._selected_ids(), {self.layer.id()})
            self.assertFalse(self.group.itemVisibilityChecked())
            dialog._select_all(False)
            self.assertEqual(dialog._selected_ids(), set())
            dialog.tree.topLevelItem(0).setCheckState(0, Qt.Checked)
            self.assertEqual(dialog._selected_ids(), {self.layer.id()})
            dialog._running = True
            dialog.reject()
            self.assertTrue(dialog._cancelled)
        finally:
            dialog._running = False
            dialog.close()


if __name__ == "__main__":
    unittest.main()
