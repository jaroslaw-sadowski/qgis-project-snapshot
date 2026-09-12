# SPDX-License-Identifier: GPL-2.0-only

"""Resume complete archives in a fresh native QGIS after process termination."""

import json
import os
import sqlite3
import subprocess
import sys
import time
import unittest
from contextlib import closing
from pathlib import Path
from threading import Event
from unittest.mock import patch

import test_adaptive as fixtures
from qgis.core import QgsCoordinateReferenceSystem, QgsGeometry, QgsProject
from test_resume_archive import legacy_resume_layout

from mbtiles_batch_exporter import archive, raster_archive


def _capture_in_process(folder, resume=False):
    """Test subprocess uses its own QGIS and reopens the original project."""
    folder = Path(folder)
    parameters = json.loads((folder / "parameters.json").read_text())
    project = QgsProject()
    if not project.read(str(folder / "source.qgz")):
        raise RuntimeError("Cannot reopen the test project")
    original = raster_archive._render_image
    calls = 0

    def render(layer, *args):
        nonlocal calls
        if layer.name() == project.mapLayer(parameters["ids"][1]).name() and not resume:
            calls += 1
            if calls == 3:
                (folder / "kill-ready").write_text("Two tiles committed")
                Event().wait(30)
                raise RuntimeError("QGIS was not killed by the test")
        return original(layer, *args)

    def checkpoint(path):
        (folder / "checkpoint.txt").write_text(str(path))

    previous = Path((folder / "checkpoint.txt").read_text()) if resume else None
    with patch.object(raster_archive, "_render_image", side_effect=render):
        result = archive.create_archive(
            project,
            parameters["ids"],
            QgsGeometry.fromWkt(parameters["area"]),
            QgsCoordinateReferenceSystem("EPSG:2180"),
            folder,
            zoom_min=17,
            zoom_max=17,
            workers=1,
            resume_from=previous,
            checkpoint_created=checkpoint,
        )
    (folder / "result.txt").write_text(str(result))
    project.clear()


class CrashResumeTests(unittest.TestCase):
    setUp = fixtures.AdaptiveWmsTests.setUp
    tearDown = fixtures.AdaptiveWmsTests.tearDown
    start_server = fixtures.AdaptiveWmsTests.start_server
    add_map = fixtures.AdaptiveWmsTests.add_map
    capture = fixtures.AdaptiveWmsTests.capture

    def test_killed_archive_resumes_in_another_qgis_without_repeating_saved_tiles(self):
        layers = [self.add_map(name=f"Map {index}") for index in range(2)]
        self.assertTrue(self.project.write(str(self.folder / "source.qgz")))
        (self.folder / "parameters.json").write_text(
            json.dumps(
                {"ids": [layer.id() for layer in layers], "area": self.area.asWkt()}
            )
        )
        environment = os.environ.copy()
        environment["QGIS_CUSTOM_CONFIG_PATH"] = str(self.folder / "child-profile")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(Path(__file__).parent), str(Path(archive.__file__).parent.parent)]
        )
        script = (
            "from test_crash_resume import _capture_in_process; "
            f"_capture_in_process({str(self.folder)!r}, resume=False)"
        )
        with subprocess.Popen(
            [sys.executable, "-c", script],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            try:
                deadline = time.monotonic() + 25
                while not (self.folder / "kill-ready").exists():
                    if process.poll() is not None:
                        failure = process.communicate()[1].decode(errors="replace")
                        for manifest in self.folder.glob("*/diagnostyka/manifest.json"):
                            failure += manifest.read_text()
                        self.fail(failure)
                    self.assertLess(time.monotonic(), deadline, "No crash checkpoint")
                    time.sleep(0.02)
                process.kill()
                process.communicate(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
        previous = Path((self.folder / "checkpoint.txt").read_text())
        checkpoint = archive.read_resume_manifest(previous)
        self.assertTrue(checkpoint["checkpoint"])
        records = {record["id"]: record for record in checkpoint["layers"]}
        self.assertEqual(records[layers[0].id()]["status"], "saved")
        self.assertNotEqual(records[layers[1].id()]["status"], "saved")
        cache = next(
            (previous / "diagnostyka" / "download-state").glob("*/raster.gpkg")
        )
        with closing(sqlite3.connect(cache)) as database:
            table = database.execute("SELECT table_name FROM gpkg_contents").fetchone()[
                0
            ]
            preserved = database.execute(
                f'SELECT zoom_level,tile_column,tile_row,tile_data FROM "{table}"'
            ).fetchall()
        self.assertEqual(len(preserved), 2)
        before = len(self.server.requests)
        completed = subprocess.run(
            [sys.executable, "-c", script.replace("resume=False", "resume=True")],
            env=environment,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            completed.returncode, 0, completed.stderr.decode(errors="replace")
        )
        result = Path((self.folder / "result.txt").read_text())
        manifest = archive.read_resume_manifest(result)
        records = {record["id"]: record for record in manifest["layers"]}
        first, second = (records[layer.id()] for layer in layers)
        self.assertTrue(first["reused"])
        self.assertEqual(second["status"], "saved", second)
        self.assertEqual(second["raster"]["resumed_tiles"], 2)
        self.assertEqual(len(self.server.requests) - before, second["tile_count"] - 2)
        self.assertFalse((result / "_source.qgz").exists())
        self.assertFalse((result / ".workers").exists())
        self.assertFalse((result / "diagnostyka" / "download-state").exists())
        with closing(sqlite3.connect(result / "dane" / "dane.gpkg")) as database:
            self.assertEqual(
                database.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
            for zoom, column, row, png in preserved:
                self.assertEqual(
                    database.execute(
                        f'SELECT tile_data FROM "{table}" WHERE zoom_level=? '
                        "AND tile_column=? AND tile_row=?",
                        (zoom, column, row),
                    ).fetchone()[0],
                    png,
                )

    def test_resume_refuses_archive_still_locked_by_a_qgis_process(self):
        layer = self.add_map()
        previous, _ = self.capture([layer])
        with archive._archive_lock(previous):
            with self.assertRaisesRegex(ValueError, "inny proces QGIS"):
                self.capture([layer], resume_from=previous)

    def test_legacy_cancelled_worker_cache_is_reused_after_network_returns(self):
        layer = self.add_map()
        self.server.scripted_statuses = [None, 429]
        self.server.retry_after = "30"
        cancel = Event()

        def status(rows):
            if any(row["state"] == "cooldown" for row in rows):
                cancel.set()

        previous, first = self.capture(
            [layer], cancelled=cancel.is_set, server_activity=status
        )
        self.assertTrue(first["cancelled"])
        legacy_resume_layout(previous)
        cache = next((previous / "download-state").glob("*/raster.gpkg"))
        with closing(sqlite3.connect(cache)) as database:
            table = database.execute("SELECT table_name FROM gpkg_contents").fetchone()[
                0
            ]
            self.assertEqual(
                database.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0], 1
            )
        self.server.retry_after = "0"
        before = len(self.server.requests)
        result, manifest = self.capture([layer], resume_from=previous)
        record = next(r for r in manifest["layers"] if r["id"] == layer.id())
        self.assertEqual(record["status"], "saved", record)
        self.assertEqual(record["raster"]["resumed_tiles"], 1)
        self.assertEqual(len(self.server.requests) - before, record["tile_count"] - 1)
        self.assertFalse((result / "diagnostyka" / "download-state").exists())


if __name__ == "__main__":
    unittest.main()
