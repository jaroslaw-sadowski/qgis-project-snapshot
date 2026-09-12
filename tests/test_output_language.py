# SPDX-License-Identifier: GPL-2.0-only

"""Localized archive paths remain portable when continuation changes language."""

import hashlib
import json
import os
import sqlite3
import unittest
from contextlib import closing
from threading import Event
from unittest.mock import patch

import test_archive as fixtures
from osgeo import gdal
from qgis.core import QgsEditorWidgetSetup, QgsProject, QgsRasterLayer

from mbtiles_batch_exporter import archive


class OutputLanguageTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    tearDown = fixtures.ArchiveTests.tearDown
    add_points = fixtures.ArchiveTests.add_points
    archive = fixtures.ArchiveTests.archive

    def test_invalid_manifest_types_and_directory_paths_are_rejected(self):
        result = self.archive()
        original = archive.read_resume_manifest(result)
        manifest_path = archive.resume_manifest_path(result)
        for invalid in (
            None,
            [],
            "wrong",
            42,
            dict(original, resources_directory="../outside"),
            dict(original, recovery_directory="/tmp/outside"),
            dict(original, data_file="../outside.gpkg"),
        ):
            with self.subTest(
                value=invalid if not isinstance(invalid, dict) else "path"
            ):
                manifest_path.write_text(json.dumps(invalid))
                with self.assertRaises(ValueError):
                    archive.read_resume_manifest(result)

    def test_141_names_and_manifest_resume_with_correct_english_suffix(self):
        empty = self.add_points("Łąka", [(100, 100)])
        with patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE="pl"):
            previous = self.archive()
        manifest = archive.read_resume_manifest(previous)
        manifest.pop("resources_directory")
        manifest.pop("recovery_directory")
        record = next(r for r in manifest["layers"] if r["id"] == empty.id())
        record["output_name"] = record["name"] + "_nie-bylo-obiketow-w-zasiegu"
        database = previous / manifest["data_file"]
        with closing(sqlite3.connect(database)) as connection:
            connection.execute(
                "UPDATE gpkg_contents SET identifier=? WHERE table_name=?",
                (record["output_name"], record["table"]),
            )
            connection.commit()
        manifest["sha256"][manifest["data_file"]] = hashlib.sha256(
            database.read_bytes()
        ).hexdigest()
        (previous / "diagnostyka" / "manifest.json").write_text(json.dumps(manifest))
        (previous / "diagnostyka" / "diagnostyka.jsonl").rename(
            previous / "diagnostyka" / "diagnostic.jsonl"
        )
        before = database.read_bytes()
        with (
            patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE="en"),
            patch.object(archive, "_write_vector") as write,
        ):
            result = self.archive(resume_from=previous)
        write.assert_not_called()
        current = archive.read_resume_manifest(result)
        record = next(r for r in current["layers"] if r["id"] == empty.id())
        self.assertEqual(record["output_name"], "Łąka_no-features-in-area")
        with closing(sqlite3.connect(result / current["data_file"])) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT identifier FROM gpkg_contents WHERE table_name=?",
                    (record["table"],),
                ).fetchone()[0],
                record["output_name"],
            )
        self.assertEqual(database.read_bytes(), before)
        self.assertTrue(current["local_layer_audit"]["passed"])

    def test_switch_languages_reuses_vectors_raster_and_attachments(self):
        empty = self.add_points("Łąka", [(100, 100)])
        attachment = self.folder / "opis źródła.txt"
        attachment.write_text("Original attachment")
        self.layer.setEditorWidgetSetup(1, QgsEditorWidgetSetup("ExternalResource", {}))
        self.assertTrue(
            self.layer.dataProvider().changeAttributeValues(
                {
                    feature.id(): {1: str(attachment)}
                    for feature in self.layer.getFeatures()
                }
            )
        )
        original_raster = self.folder / "source.tif"
        with gdal.ExceptionMgr():
            dataset = gdal.GetDriverByName("GTiff").Create(
                str(original_raster), 128, 128, 1, gdal.GDT_UInt16
            )
            dataset.SetGeoTransform((-1, 0.1, 0, 12, 0, -0.1))
            dataset.SetProjection(self.crs.toWkt())
            dataset.GetRasterBand(1).Fill(1234)
            dataset = None
        raster = QgsRasterLayer(str(original_raster), "Pomiar", "gdal")
        self.assertTrue(raster.isValid())
        self.project.addMapLayer(raster)
        previous = None
        pixels = None
        for language, data, resources, diagnostics, report, suffix in (
            (
                "pl",
                "dane",
                "zasoby",
                "diagnostyka",
                "raport.html",
                "_nie-bylo-obiektow-w-zasiegu",
            ),
            (
                "en",
                "data",
                "resources",
                "diagnostics",
                "report.html",
                "_no-features-in-area",
            ),
            (
                "pl",
                "dane",
                "zasoby",
                "diagnostyka",
                "raport.html",
                "_nie-bylo-obiektow-w-zasiegu",
            ),
        ):
            with self.subTest(language=language, continuation=previous is not None):
                cancelled = Event()

                def status(record, completed, total):
                    if previous is not None and language == "pl" and completed == total:
                        cancelled.set()

                with (
                    patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE=language),
                    patch.object(
                        archive, "_write_vector", wraps=archive._write_vector
                    ) as vectors,
                    patch.object(
                        archive, "write_raster_data", wraps=archive.write_raster_data
                    ) as rasters,
                ):
                    result = self.archive(
                        resume_from=previous,
                        cancelled=cancelled.is_set,
                        layer_status=status,
                    )
                if previous is not None:
                    vectors.assert_not_called()
                    rasters.assert_not_called()
                manifest = archive.read_resume_manifest(result)
                self.assertEqual(
                    manifest["cancelled"], previous is not None and language == "pl"
                )
                self.assertEqual(manifest["data_file"], f"{data}/{data}.gpkg")
                self.assertEqual(manifest["resources_directory"], resources)
                self.assertEqual(
                    {p.name for p in result.iterdir() if p.is_dir()},
                    {data, resources, diagnostics},
                )
                self.assertTrue((result / report).is_file())
                self.assertIn(
                    "_archiwum_" if language == "pl" else "_archive_", result.name
                )
                log = "diagnostyka.jsonl" if language == "pl" else "diagnostic.jsonl"
                self.assertTrue((result / diagnostics / log).is_file())
                records = {r["id"]: r for r in manifest["layers"]}
                self.assertEqual(records[empty.id()]["output_name"], "Łąka" + suffix)
                self.assertTrue(manifest["local_layer_audit"]["passed"])
                self.assertEqual(manifest["resources"]["issues"], [])
                local = QgsProject()
                try:
                    self.assertTrue(local.read(str(next(result.glob("*.qgz")))))
                    self.assertEqual(local.mapLayer(empty.id()).name(), "Łąka" + suffix)
                    for feature in local.mapLayer(self.layer.id()).getFeatures():
                        self.assertTrue(
                            feature["opis"].startswith("./" + resources + "/")
                        )
                        self.assertEqual(
                            (result / feature["opis"]).read_text(),
                            "Original attachment",
                        )
                    self.assertTrue(local.mapLayer(raster.id()).isValid())
                    with gdal.ExceptionMgr():
                        saved = gdal.Open(
                            str(result / records[raster.id()]["local_source"][2:])
                        )
                        current_pixels = saved.ReadRaster()
                        if previous is None:
                            self.assertEqual(
                                records[raster.id()]["raster_size"],
                                [saved.RasterXSize, saved.RasterYSize],
                            )
                            self.assertEqual(
                                records[raster.id()]["overview_status"], "small_raster"
                            )
                        saved = None
                    if pixels is not None:
                        self.assertEqual(current_pixels, pixels)
                    pixels = current_pixels
                finally:
                    local.clear()
                attachment.unlink(missing_ok=True)
                previous = result
        self.assertEqual(empty.name(), "Łąka")
        self.assertEqual(self.original.read_bytes(), self.original_bytes)


if __name__ == "__main__":
    unittest.main()
