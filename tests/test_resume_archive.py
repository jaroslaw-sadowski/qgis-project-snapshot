# SPDX-License-Identifier: GPL-2.0-only

"""Continuation reuses verified local results without changing old archives."""

import hashlib
import json
import shutil
import sqlite3
import unittest
from contextlib import closing
from threading import Event
from unittest.mock import patch

import test_adaptive as adaptive_fixtures
import test_archive as fixtures
import test_raster_archive as raster_fixtures
from qgis.core import QgsCoordinateReferenceSystem, QgsEditorWidgetSetup, QgsGeometry

from mbtiles_batch_exporter import archive as archive_module
from mbtiles_batch_exporter.parallel_archive import RasterWorkers


def legacy_resume_layout(folder):
    """Place recovery artifacts exactly where releases through 1.4.0 kept them."""
    manifest = archive_module.read_resume_manifest(folder)
    manifest.pop("data_file")
    for record in manifest["layers"]:
        if record.get("local_source"):
            record["local_source"] = record["local_source"].replace(
                "./dane/dane.gpkg|", "./dane.gpkg|", 1
            )
    manifest["sha256"] = {
        name.removeprefix("dane/").removeprefix("diagnostyka/"): digest
        for name, digest in manifest["sha256"].items()
    }
    for directory in (folder / "dane", folder / "diagnostyka"):
        for path in directory.iterdir():
            shutil.move(path, folder / path.name)
        directory.rmdir()
    (folder / "manifest.json").write_text(json.dumps(manifest))


class ResumeArchiveTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    tearDown = fixtures.ArchiveTests.tearDown
    add_points = fixtures.ArchiveTests.add_points
    archive = fixtures.ArchiveTests.archive
    manifest = fixtures.ArchiveTests.manifest

    def test_legacy_root_layout_reuses_data_and_keeps_previous_archive(self):
        previous = self.archive()
        legacy_resume_layout(previous)
        original_files = {
            path.relative_to(previous): path.read_bytes()
            for path in previous.rglob("*")
            if path.is_file()
        }
        with patch.object(archive_module, "_write_vector") as write:
            result = self.archive(resume_from=previous)
        write.assert_not_called()
        manifest = self.manifest(result)
        self.assertEqual(manifest["data_file"], "dane/dane.gpkg")
        self.assertTrue(manifest["layers"][0]["reused"])
        self.assertTrue(manifest["local_layer_audit"]["passed"])
        self.assertTrue((result / "dane" / "dane.gpkg").is_file())
        self.assertFalse((result / "dane.gpkg").exists())
        self.assertFalse((result / "manifest.json").exists())
        self.assertEqual(
            {
                path.relative_to(previous): path.read_bytes()
                for path in previous.rglob("*")
                if path.is_file()
            },
            original_files,
        )

    def test_cancel_then_resume_reuses_completed_and_empty_vectors(self):
        empty = self.add_points("No objects in the area", [(1, 9)])
        pending = self.add_points("Finish next time", [(6, 6)])
        cancelled = Event()

        def stop(record, completed, total):
            if record["id"] == pending.id() and record["status"] == "pending":
                cancelled.set()

        previous = self.archive(cancelled=cancelled.is_set, layer_status=stop)
        first = self.manifest(previous)
        self.assertTrue(first["cancelled"])
        self.assertEqual(
            [record["status"] for record in first["layers"]],
            ["saved", "saved", "cancelled"],
        )
        original_files = {
            path.relative_to(previous): path.read_bytes()
            for path in previous.rglob("*")
            if path.is_file()
        }
        with patch.object(
            archive_module, "_write_vector", wraps=archive_module._write_vector
        ) as write:
            continued = self.archive(resume_from=previous)
        self.assertEqual(
            [call.args[0].id() for call in write.call_args_list], [pending.id()]
        )
        self.assertNotEqual(continued, previous)
        self.assertEqual(
            {
                path.relative_to(previous): path.read_bytes()
                for path in previous.rglob("*")
                if path.is_file()
            },
            original_files,
        )
        manifest = self.manifest(continued)
        records = {record["id"]: record for record in manifest["layers"]}
        self.assertEqual({record["status"] for record in records.values()}, {"saved"})
        self.assertEqual(records[empty.id()]["feature_count"], 0)
        self.assertFalse(manifest["cancelled"])
        self.assertTrue(manifest["local_layer_audit"]["passed"])
        local = fixtures.QgsProject()
        try:
            self.assertTrue(local.read(str(next(continued.glob("*.qgz")))))
            self.assertEqual(
                set(local.mapLayers()), {self.layer.id(), empty.id(), pending.id()}
            )
            saved = local.mapLayer(self.layer.id())
            self.assertEqual(saved.renderer().symbol().color().name(), "#123456")
            self.assertEqual(saved.featureCount(), 2)
            self.assertEqual(
                saved.attributeAlias(saved.fields().indexFromName("opis")),
                "Opis obiektu",
            )
            group = local.layerTreeRoot().findGroup(self.group.name())
            self.assertFalse(group.itemVisibilityChecked())
            self.assertEqual(
                [node.layerId() for node in group.findLayers()],
                [self.layer.id(), empty.id(), pending.id()],
            )
        finally:
            local.clear()
        self.assertEqual(self.original.read_bytes(), self.original_bytes)

    def test_changed_source_is_rejected_before_export(self):
        previous = self.archive()
        self.layer.setDataSource(
            "Point?crs=EPSG:2180&field=different:string", self.layer.name(), "memory"
        )
        with (
            patch.object(archive_module, "_write_vector") as write,
            self.assertRaises(ValueError),
        ):
            self.archive(resume_from=previous)
        write.assert_not_called()

    def test_unsaved_edits_are_not_silently_replaced_by_previous_data(self):
        previous = self.archive()
        self.assertTrue(self.layer.startEditing())
        feature = next(self.layer.getFeatures())
        self.assertTrue(
            self.layer.changeAttributeValue(feature.id(), 1, "Unsaved new value")
        )
        with (
            patch.object(archive_module, "_write_vector") as write,
            self.assertRaises(ValueError),
        ):
            self.archive(resume_from=previous)
        write.assert_not_called()
        self.assertTrue(self.layer.isModified())
        self.assertEqual(
            self.layer.getFeature(feature.id())["opis"], "Unsaved new value"
        )
        self.assertEqual(self.original.read_bytes(), self.original_bytes)

    def test_changed_area_zoom_and_project_crs_are_rejected(self):
        previous = self.archive()
        original_area = QgsGeometry(self.area)
        with self.subTest(change="area"):
            self.area = QgsGeometry.fromWkt("POLYGON((0 0,9 9,10 9,1 0,0 0))")
            with self.assertRaises(ValueError):
                self.archive(resume_from=previous)
            self.area = original_area
        with self.subTest(change="zoom"):
            with self.assertRaises(ValueError):
                self.archive(resume_from=previous, zoom_max=18)
        with self.subTest(change="project CRS"):
            self.project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
            with self.assertRaises(ValueError):
                self.archive(resume_from=previous)

    def test_missing_or_changed_database_is_rejected_before_export(self):
        previous = self.archive()
        database = previous / "dane" / "dane.gpkg"
        original = database.read_bytes()
        for change in ("missing", "changed"):
            with self.subTest(change=change):
                if change == "missing":
                    database.unlink()
                else:
                    database.write_bytes(original + b"unexpected modification")
                with (
                    patch.object(archive_module, "_write_vector") as write,
                    self.assertRaises((ValueError, OSError, RuntimeError)),
                ):
                    self.archive(resume_from=previous)
                write.assert_not_called()
                database.write_bytes(original)

    def test_manifest_paths_cannot_escape_previous_archive(self):
        previous = self.archive()
        manifest = self.manifest(previous)
        outside = self.folder / "outside.txt"
        outside.write_text("Must not be copied")
        manifest["sha256"]["../outside.txt"] = hashlib.sha256(
            outside.read_bytes()
        ).hexdigest()
        (previous / "diagnostyka" / "manifest.json").write_text(json.dumps(manifest))
        with (
            patch.object(archive_module, "_write_vector") as write,
            self.assertRaises((ValueError, OSError, RuntimeError)),
        ):
            self.archive(resume_from=previous)
        write.assert_not_called()
        self.assertEqual(outside.read_text(), "Must not be copied")

    def test_legacy_manifest_without_source_fingerprint_can_continue(self):
        previous = self.archive()
        manifest = self.manifest(previous)
        for record in manifest["layers"]:
            record.pop("source_fingerprint", None)
        (previous / "diagnostyka" / "manifest.json").write_text(json.dumps(manifest))
        for continuation in range(2):
            with self.subTest(continuation=continuation):
                with patch.object(archive_module, "_write_vector") as write:
                    continued = self.archive(resume_from=previous)
                write.assert_not_called()
                current = self.manifest(continued)
                self.assertEqual(current["layers"][0]["status"], "saved")
                self.assertFalse(current["continuation"]["source_settings_verified"])
                self.assertFalse(current["layers"][0].get("source_fingerprint"))
                previous = continued

    def test_reused_attachment_keeps_working_after_original_file_is_deleted(self):
        source = self.folder / "source"
        source.mkdir()
        document = source / "opis.txt"
        document.write_text("Archived documentation")
        self.layer.setEditorWidgetSetup(
            1,
            QgsEditorWidgetSetup(
                "ExternalResource", {"DefaultRoot": str(source), "RelativeStorage": 2}
            ),
        )
        self.assertTrue(
            self.layer.dataProvider().changeAttributeValues(
                {feature.id(): {1: "opis.txt"} for feature in self.layer.getFeatures()}
            )
        )
        previous = self.archive()
        shutil.rmtree(source)
        with patch.object(archive_module, "_write_vector") as write:
            continued = self.archive(resume_from=previous)
        write.assert_not_called()
        self.assertEqual(self.manifest(continued)["resources"]["issues"], [])
        local = fixtures.QgsProject()
        try:
            self.assertTrue(local.read(str(next(continued.glob("*.qgz")))))
            for feature in local.mapLayer(self.layer.id()).getFeatures():
                self.assertEqual(
                    (continued / feature["opis"]).read_text(), "Archived documentation"
                )
        finally:
            local.clear()


class ResumeRasterTests(unittest.TestCase):
    setUp = raster_fixtures.RasterTests.setUp
    tearDown = raster_fixtures.RasterTests.tearDown
    archive = fixtures.ArchiveTests.archive
    manifest = fixtures.ArchiveTests.manifest

    def test_completed_transparent_map_is_reused_and_still_marked_for_review(self):
        def transparent(layer, project, bounds, width, height, cancelled, progress):
            image = raster_fixtures.QImage(
                width, height, raster_fixtures.QImage.Format_RGBA8888
            )
            image.fill(0)
            return image

        with (
            patch.object(archive_module, "_write_vector", side_effect=RuntimeError()),
            patch(
                "mbtiles_batch_exporter.raster_archive._render_image",
                side_effect=transparent,
            ),
        ):
            previous = self.archive(zoom_min=16, zoom_max=17)
        self.assertEqual(self.manifest(previous)["layers"][0]["status"], "empty")
        with (
            patch.object(archive_module, "_write_vector") as write,
            patch.object(archive_module, "write_rendered_raster") as render,
        ):
            continued = self.archive(resume_from=previous, zoom_min=16, zoom_max=17)
        write.assert_not_called()
        render.assert_not_called()
        manifest = self.manifest(continued)
        self.assertEqual(manifest["layers"][0]["status"], "empty")
        self.assertEqual(manifest["layers"][0]["tile_count"], 0)
        self.assertTrue(manifest["local_layer_audit"]["passed"])

    def test_old_partial_map_survives_failed_or_cancelled_continuation(self):
        with patch.object(archive_module, "_write_vector", side_effect=RuntimeError()):
            previous = self.archive(zoom_min=16, zoom_max=17)
        manifest = self.manifest(previous)
        record = manifest["layers"][0]
        self.assertEqual(record["method"], "raster_render")
        database = previous / "dane" / "dane.gpkg"
        with closing(sqlite3.connect(database)) as connection:
            table = record["table"]
            with connection:
                tile_id, zoom = connection.execute(
                    f'SELECT id,zoom_level FROM "{table}" LIMIT 1'
                ).fetchone()
                connection.execute(f'DELETE FROM "{table}" WHERE id=?', (tile_id,))
            original_tiles = connection.execute(
                f'SELECT zoom_level,tile_column,tile_row,tile_data FROM "{table}" '
                "ORDER BY zoom_level,tile_column,tile_row"
            ).fetchall()
        self.assertTrue(original_tiles)
        record.update(status="partial", tile_count=len(original_tiles))
        for level in record["raster"]["levels"]:
            if level["zoom"] == zoom:
                level["nonempty"] -= 1
                level["failed"] += 1
        manifest["sha256"]["dane/dane.gpkg"] = hashlib.sha256(
            database.read_bytes()
        ).hexdigest()
        (previous / "diagnostyka" / "manifest.json").write_text(json.dumps(manifest))
        previous_bytes = database.read_bytes()

        for stop in (False, True):
            with self.subTest(cancelled=stop):
                cancelled = Event()

                def cancel(record, completed, total):
                    if stop and record["status"] == "pending":
                        cancelled.set()

                with (
                    patch.object(
                        archive_module, "_write_vector", side_effect=RuntimeError()
                    ),
                    patch.object(
                        archive_module,
                        "write_rendered_raster",
                        side_effect=RuntimeError(),
                    ),
                ):
                    continued = self.archive(
                        zoom_min=16,
                        zoom_max=17,
                        resume_from=previous,
                        cancelled=cancelled.is_set,
                        layer_status=cancel,
                    )
                current = self.manifest(continued)
                self.assertEqual(current["cancelled"], stop)
                self.assertEqual(current["layers"][0]["status"], "partial")
                self.assertEqual(
                    current["layers"][0]["local_source"], record["local_source"]
                )
                self.assertTrue(current["local_layer_audit"]["passed"])
                with closing(
                    sqlite3.connect(continued / "dane" / "dane.gpkg")
                ) as connection:
                    tiles = connection.execute(
                        "SELECT zoom_level,tile_column,tile_row,tile_data "
                        f'FROM "{table}" '
                        "ORDER BY zoom_level,tile_column,tile_row"
                    ).fetchall()
                self.assertEqual(tiles, original_tiles)
                self.assertEqual(database.read_bytes(), previous_bytes)

        def change_previous_during_download(*args, **kwargs):
            database.write_bytes(previous_bytes + b"Changed while downloading")
            raise RuntimeError()

        with (
            patch.object(archive_module, "_write_vector", side_effect=RuntimeError()),
            patch.object(
                archive_module,
                "write_rendered_raster",
                side_effect=change_previous_during_download,
            ),
            patch.object(archive_module, "merge_raster") as merge,
            self.assertRaises(ValueError),
        ):
            self.archive(zoom_min=16, zoom_max=17, resume_from=previous)
        merge.assert_not_called()


class ResumeWmsTests(unittest.TestCase):
    setUp = raster_fixtures.LocalWmsTests.setUp
    tearDown = raster_fixtures.LocalWmsTests.tearDown
    start_server = raster_fixtures.LocalWmsTests.start_server
    add_map = adaptive_fixtures.AdaptiveWmsTests.add_map
    capture = adaptive_fixtures.AdaptiveWmsTests.capture

    def test_reopen_original_project_reuses_completed_wms_without_another_worker(self):
        fast = self.add_map(name="Completed map")
        pending = self.add_map(name="Continue after reopening")
        fast_id, pending_id = fast.id(), pending.id()
        pending_job = "layer_" + hashlib.sha256(pending_id.encode()).hexdigest()[:24]
        original_project = self.folder / "original.qgz"
        self.assertTrue(self.project.write(str(original_project)))
        original_bytes = original_project.read_bytes()
        cancelled = Event()
        run = RasterWorkers._run

        def delay_second(workers, folder):
            if folder.name == pending_job:
                if not workers.stop.wait(15):
                    raise RuntimeError("Completed map was not collected")
                raise InterruptedError()
            return run(workers, folder)

        def stop_after_first(record, completed, total):
            if record["id"] == fast_id and record["status"] == "saved":
                cancelled.set()

        with patch.object(RasterWorkers, "_run", delay_second):
            previous, before = self.capture(
                [fast, pending],
                cancelled=cancelled.is_set,
                layer_status=stop_after_first,
            )
        records = {record["id"]: record for record in before["layers"]}
        self.assertTrue(before["cancelled"])
        self.assertEqual(records[fast_id]["status"], "saved")
        self.assertEqual(records[pending_id]["status"], "cancelled")
        self.assertIn("worker_pid", records[fast_id])
        previous_bytes = (previous / "dane" / "dane.gpkg").read_bytes()
        self.project.clear()
        self.assertTrue(self.project.read(str(original_project)))
        current_layers = [
            self.project.mapLayer(fast_id),
            self.project.mapLayer(pending_id),
        ]
        self.assertTrue(all(layer.isValid() for layer in current_layers))
        launched = []

        def observe_run(workers, folder):
            launched.append(folder.name)
            return run(workers, folder)

        with patch.object(RasterWorkers, "_run", observe_run):
            continued, after = self.capture(current_layers, resume_from=previous)
        self.assertEqual(launched, [pending_job])
        current = {record["id"]: record for record in after["layers"]}
        self.assertEqual(current[fast_id]["status"], "saved")
        self.assertEqual(current[pending_id]["status"], "saved")
        self.assertTrue(current[fast_id]["reused"])
        self.assertNotEqual(
            current[fast_id]["worker_pid"], current[pending_id]["worker_pid"]
        )
        self.assertTrue(after["continuation"]["source_settings_verified"])
        self.assertTrue(after["local_layer_audit"]["passed"])
        self.assertFalse(after["cancelled"])
        self.assertFalse((continued / ".workers").exists())
        self.assertEqual((previous / "dane" / "dane.gpkg").read_bytes(), previous_bytes)
        self.assertEqual(original_project.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
