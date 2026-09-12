# SPDX-License-Identifier: GPL-2.0-only

"""Persistent native PNG checkpoints survive cancellation and process death."""

import os
import sqlite3
import subprocess
import sys
import time
import unittest
from collections import Counter
from contextlib import closing
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import test_raster_archive as fixtures

from mbtiles_batch_exporter import raster_archive
from mbtiles_batch_exporter.adaptive import DownloadError
from mbtiles_batch_exporter.parallel_archive import merge_raster


def _killed_capture(folder):
    """Child process: deliberately pause after PNG commit, before ledger commit."""
    folder = Path(folder)
    original_connect = sqlite3.connect

    class Connection(sqlite3.Connection):
        def commit(self):
            filename = self.execute("PRAGMA database_list").fetchone()[2]
            if (
                Path(filename).name == "tiles.sqlite"
                and self.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='tiles'"
                ).fetchone()
                and self.execute(
                    'SELECT count(*) FROM tiles WHERE status="saved"'
                ).fetchone()[0]
                >= 2
            ):
                (folder / "kill-ready").write_text("PNG durable; ledger uncommitted")
                Event().wait(30)
                raise RuntimeError("The test did not kill the worker")
            return super().commit()

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=Connection)

    fixture = TileResumeTests()
    with patch.object(
        fixtures,
        "TemporaryDirectory",
        return_value=SimpleNamespace(name=str(folder), cleanup=lambda: None),
    ):
        fixture.setUp()
    with patch.object(raster_archive.sqlite3, "connect", side_effect=connect):
        fixture.capture()


class TileResumeTests(unittest.TestCase):
    setUp = fixtures.RasterTests.setUp
    tearDown = fixtures.RasterTests.tearDown

    def capture(self, **kwargs):
        return raster_archive.write_rendered_raster(
            self.layer,
            self.project,
            self.area,
            self.crs,
            self.database,
            "map",
            raster_archive.zoom_levels(self.project, self.area, self.crs, 16, 17),
            kwargs.pop("cancelled", lambda: False),
            kwargs.pop("progress", lambda message: None),
            ledger_path=self.folder / "tiles.sqlite",
            **kwargs,
        )

    def test_cancel_keeps_successes_and_transparent_tiles_without_gate(self):
        cancelled = Event()
        calls = Counter()
        empty = [None]

        def render(layer, project, bounds, width, height, cancel, progress):
            key = (bounds.asWktCoordinates(), width)
            calls[key] += 1
            if empty[0] is None:
                empty[0] = key
            if sum(calls.values()) == 4:
                cancelled.set()
                raise InterruptedError()
            if key == empty[0]:
                image = fixtures.QImage(width, height, fixtures.QImage.Format_RGBA8888)
                image.fill(0)
                return image
            return fixtures._render_image(
                layer, project, bounds, width, height, cancel, progress
            )

        with patch.object(raster_archive, "_render_image", side_effect=render):
            with self.assertRaises(InterruptedError):
                self.capture(cancelled=cancelled.is_set)
        preserved_calls = dict(calls)
        completed = {
            key for key, count in preserved_calls.items() if key != list(calls)[-1]
        }
        with patch.object(raster_archive, "_render_image", side_effect=render):
            cancelled.clear()
            result = self.capture(resume=True)
        self.assertEqual(result["raster"]["resumed_tiles"], 3)
        self.assertEqual(calls[empty[0]], 1)
        self.assertTrue(all(calls[key] == 1 for key in completed))
        self.assertEqual(result["raster"]["subdivisions"], 0)
        self.assertTrue(
            all(level["failed"] == 0 for level in result["raster"]["levels"])
        )

    def test_failed_tiles_get_three_new_attempts_but_successes_are_reused(self):
        calls = Counter()
        failed = [None]

        def render(layer, project, bounds, width, height, cancelled, progress):
            key = (bounds.asWktCoordinates(), width)
            calls[key] += 1
            if failed[0] is None:
                failed[0] = key
            if key == failed[0]:
                raise DownloadError("Controlled failure", 500, None)
            return fixtures._render_image(
                layer, project, bounds, width, height, cancelled, progress
            )

        with patch.object(raster_archive, "_render_image", side_effect=render):
            first = self.capture()
            second = self.capture(resume=True)
        self.assertEqual(calls[failed[0]], 6)
        self.assertTrue(
            all(count == 1 for key, count in calls.items() if key != failed[0])
        )
        self.assertEqual(first["status"], "partial")
        self.assertEqual(second["status"], "partial")
        self.assertEqual(second["raster"]["subdivisions"], 0)
        self.assertGreater(second["raster"]["previous_attempts"], 0)

    def test_legacy_retry_subdivides_large_requests_and_resumes_whole_tiles(self):
        calls = Counter()

        def render(layer, project, bounds, width, height, cancelled, progress):
            calls[(bounds.asWktCoordinates(), width)] += 1
            if width > 170:
                raise DownloadError("[HTTP 503] Request too large", 503, None)
            return fixtures._render_image(
                layer, project, bounds, width, height, cancelled, progress
            )

        with patch.object(raster_archive, "_render_image", side_effect=render):
            result = self.capture(legacy_retries=True)
        self.assertEqual(result["status"], "saved")
        self.assertGreater(result["raster"]["subdivisions"], 0)
        self.assertTrue(
            all(
                count == (3 if width > 170 else 1)
                for (_, width), count in calls.items()
            )
        )
        with patch.object(raster_archive, "_render_image") as render:
            resumed = self.capture(legacy_retries=True, resume=True)
        render.assert_not_called()
        self.assertEqual(resumed["tile_count"], result["tile_count"])

    def test_legacy_rate_limit_stops_after_first_request(self):
        with patch.object(
            raster_archive,
            "_render_image",
            side_effect=DownloadError("[HTTP 429] Rate limit", 429, None),
        ) as render:
            result = self.capture(legacy_retries=True)
        self.assertEqual(render.call_count, 1)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["raster"]["stopped_early"])
        self.assertEqual(result["raster"]["retries"], 0)
        self.assertEqual(result["raster"]["subdivisions"], 0)

    def test_legacy_ledger_does_not_repeat_exhausted_internal_retries(self):
        with patch.object(
            raster_archive,
            "_render_image",
            side_effect=DownloadError("[HTTP 500] Controlled failure", 500, None),
        ) as render:
            result = self.capture(legacy_retries=True)
        with closing(sqlite3.connect(self.folder / "tiles.sqlite")) as ledger:
            total, attempts = ledger.execute(
                "SELECT count(*),sum(total_attempts) FROM tiles"
            ).fetchone()
        # Three parent requests and three requests for its first failing child.
        expected = min(5, total)
        self.assertEqual(render.call_count, expected * 6)
        self.assertEqual(attempts, expected)
        self.assertEqual(result["raster"]["repair_attempts"], 0)
        self.assertEqual(result["status"], "failed")

    def test_changed_mask_with_same_bounds_is_rejected_before_download(self):
        self.capture()
        before = self.database.read_bytes()
        self.area = fixtures.QgsGeometry.fromRect(self.area.boundingBox())
        with (
            patch.object(raster_archive, "_render_image") as render,
            self.assertRaises(ValueError),
        ):
            self.capture(resume=True)
        render.assert_not_called()
        self.assertEqual(self.database.read_bytes(), before)

    def test_interrupted_grid_initialization_is_completed_on_resume(self):
        cancelled = Event()

        def stop(message):
            if "rejestru kafelków" in message:
                cancelled.set()

        with self.assertRaises(InterruptedError):
            self.capture(cancelled=cancelled.is_set, progress=stop)
        with patch.object(
            raster_archive, "_render_image", wraps=fixtures._render_image
        ) as render:
            result = self.capture(resume=True)
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["raster"]["resumed_tiles"], 0)
        self.assertEqual(
            {level["zoom"] for level in result["raster"]["levels"]}, {16, 17}
        )
        with closing(sqlite3.connect(self.folder / "tiles.sqlite")) as ledger:
            self.assertEqual(
                render.call_count,
                ledger.execute("SELECT count(*) FROM tiles").fetchone()[0],
            )

    def test_changed_geopackage_zoom_matrix_is_rejected(self):
        self.capture()
        with closing(sqlite3.connect(self.database)) as connection:
            with connection:
                connection.execute(
                    "UPDATE gpkg_tile_matrix SET pixel_x_size=pixel_x_size*2 "
                    "WHERE zoom_level=16"
                )
        before = self.database.read_bytes()
        with (
            patch.object(raster_archive, "_render_image") as render,
            self.assertRaises(ValueError),
        ):
            self.capture(resume=True)
        render.assert_not_called()
        self.assertEqual(self.database.read_bytes(), before)

    def test_missing_or_corrupt_png_is_requested_again(self):
        self.capture()
        with closing(sqlite3.connect(self.database)) as connection:
            keys = connection.execute(
                "SELECT zoom_level,tile_column,tile_row FROM map LIMIT 2"
            ).fetchall()
            with connection:
                connection.execute(
                    "DELETE FROM map WHERE zoom_level=? "
                    "AND tile_column=? AND tile_row=?",
                    keys[0],
                )
                connection.execute(
                    "UPDATE map SET tile_data=? WHERE zoom_level=? "
                    "AND tile_column=? AND tile_row=?",
                    (b"corrupt PNG", *keys[1]),
                )
        with patch.object(
            raster_archive, "_render_image", wraps=fixtures._render_image
        ) as render:
            result = self.capture(resume=True)
        self.assertEqual(render.call_count, 2)
        self.assertEqual(result["status"], "saved")

    def test_interrupted_first_merge_never_publishes_an_incomplete_database(self):
        self.capture()
        # Ensure cancellation happens after the first one-MiB chunk was written.
        with closing(sqlite3.connect(self.database)) as connection:
            with connection:
                connection.execute("CREATE TABLE merge_payload (value BLOB)")
                connection.execute(
                    "INSERT INTO merge_payload VALUES (zeroblob(2097152))"
                )
        original = self.database.read_bytes()
        destination = self.folder / "merged.gpkg"
        checks = 0

        def cancel():
            nonlocal checks
            checks += 1
            self.assertFalse(destination.exists())
            return checks > 1

        with self.assertRaises(InterruptedError):
            merge_raster(self.database, destination, "map", cancelled=cancel)
        self.assertGreater(checks, 1)
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.folder.glob(".merge-*")))
        self.assertEqual(self.database.read_bytes(), original)
        merge_raster(self.database, destination, "map")
        self.assertEqual(destination.read_bytes(), original)

    def test_empty_zoom_markers_are_rebuilt_without_redownloading_empty_tiles(self):
        def transparent(layer, project, bounds, width, height, cancelled, progress):
            image = fixtures.QImage(width, height, fixtures.QImage.Format_RGBA8888)
            image.fill(0)
            return image

        with patch.object(raster_archive, "_render_image", side_effect=transparent):
            first = self.capture()
        with patch.object(raster_archive, "_render_image") as render:
            second = self.capture(resume=True)
        render.assert_not_called()
        self.assertEqual(first["tile_count"], 0)
        self.assertEqual(second["tile_count"], 0)
        self.assertEqual(second["status"], "empty")
        self.assertEqual(second["raster"]["empty_zoom_placeholders"], [16, 17])
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM map").fetchone()[0], 2
            )

    def test_killed_qgis_process_preserves_png_committed_before_ledger(self):
        environment = os.environ.copy()
        environment["QGIS_CUSTOM_CONFIG_PATH"] = str(self.folder / "child-profile")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["PYTHONPATH"] = os.pathsep.join(
            [
                str(Path(__file__).parent),
                str(Path(raster_archive.__file__).parent.parent),
            ]
        )
        script = (
            "from test_tile_resume import _killed_capture; _killed_capture("
            + repr(str(self.folder))
            + ")"
        )
        with subprocess.Popen(
            [sys.executable, "-c", script],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            try:
                deadline = time.monotonic() + 15
                while not (self.folder / "kill-ready").exists():
                    if process.poll() is not None:
                        self.fail(process.communicate()[1].decode(errors="replace"))
                    self.assertLess(
                        time.monotonic(),
                        deadline,
                        "QGIS did not publish its checkpoint",
                    )
                    time.sleep(0.02)
                process.kill()
                process.communicate(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)
        with closing(sqlite3.connect(self.database)) as connection:
            preserved = connection.execute(
                "SELECT zoom_level,tile_column,tile_row,tile_data FROM map"
            ).fetchall()
            self.assertEqual(len(preserved), 2)
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
        with closing(sqlite3.connect(self.folder / "tiles.sqlite")) as ledger:
            self.assertEqual(
                ledger.execute(
                    'SELECT count(*) FROM tiles WHERE status="saved"'
                ).fetchone()[0],
                1,
            )
            total = ledger.execute("SELECT count(*) FROM tiles").fetchone()[0]
        with patch.object(
            raster_archive, "_render_image", wraps=fixtures._render_image
        ) as render:
            result = self.capture(resume=True)
        self.assertEqual(result["raster"]["resumed_tiles"], 2)
        self.assertEqual(render.call_count, total - 2)
        with closing(sqlite3.connect(self.database)) as connection:
            for zoom, column, row, payload in preserved:
                self.assertEqual(
                    connection.execute(
                        "SELECT tile_data FROM map WHERE zoom_level=? "
                        "AND tile_column=? AND tile_row=?",
                        (zoom, column, row),
                    ).fetchone()[0],
                    payload,
                )


if __name__ == "__main__":
    unittest.main()
