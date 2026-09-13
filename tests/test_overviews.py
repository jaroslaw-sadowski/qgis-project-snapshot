# SPDX-License-Identifier: GPL-2.0-only

"""Native pyramids speed display without replacing independently captured maps."""

import sqlite3
import struct
import unittest
from contextlib import closing
from hashlib import sha256
from unittest.mock import patch

import test_raster_archive as fixtures
from osgeo import gdal, ogr
from qgis.core import QgsGeometry, QgsRasterLayer, QgsRectangle
from qgis.PyQt.QtGui import QColor, QImage

from mbtiles_batch_exporter.parallel_archive import merge_raster
from mbtiles_batch_exporter.raster_archive import (
    _empty_zoom_overviews,
    write_raster_data,
    write_rendered_raster,
    zoom_levels,
)


class RasterOverviewTests(unittest.TestCase):
    setUp = fixtures.RasterTests.setUp
    tearDown = fixtures.RasterTests.tearDown

    def test_numerical_overviews_preserve_base_values_and_internal_mask(self):
        source_path = self.folder / "numerical.tif"
        source = gdal.GetDriverByName("GTiff").Create(
            str(source_path), 2048, 2048, 1, gdal.GDT_UInt16
        )
        source.SetProjection(self.crs.toWkt())
        source.SetGeoTransform([500000, 0.25, 0, 500512, 0, -0.25])
        source.GetRasterBand(1).Fill(40000)
        source = None
        layer = QgsRasterLayer(str(source_path), "Numerical", "gdal")
        original = gdal.Dataset.BuildOverviews
        unchanged = []

        def build(dataset, *args, **kwargs):
            before = sha256(dataset.ReadRaster()).hexdigest()
            result = original(dataset, *args, **kwargs)
            unchanged.append(before == sha256(dataset.ReadRaster()).hexdigest())
            return result

        with patch.object(gdal.Dataset, "BuildOverviews", build):
            result = write_raster_data(
                layer,
                self.project,
                self.area,
                self.crs,
                self.folder,
                "numerical",
                lambda: False,
                lambda _: None,
            )
        self.assertEqual(unchanged, [True])
        self.assertEqual(result["overview_factors"], [2, 4, 8])
        target = self.folder / result["local_source"][2:]
        raster = gdal.Open(str(target))
        self.assertEqual(
            result["raster_size"], [raster.RasterXSize, raster.RasterYSize]
        )
        self.assertEqual(result["overview_status"], "built")
        band = raster.GetRasterBand(1)
        mask = band.GetMaskBand()
        self.assertEqual(band.DataType, gdal.GDT_UInt16)
        self.assertEqual(band.GetOverviewCount(), 3)
        self.assertEqual(mask.GetOverviewCount(), 3)
        self.assertEqual(
            raster.GetMetadata("IMAGE_STRUCTURE")["COMPRESSION"], "DEFLATE"
        )
        for factor, index in zip((2, 4, 8), range(3)):
            overview = band.GetOverview(index)
            self.assertEqual((overview.XSize, overview.YSize), (2048 // factor,) * 2)
            self.assertEqual(
                struct.unpack("H", overview.ReadRaster(10, 10, 1, 1))[0], 40000
            )
            # The AOI has a hole around the image center. Its overview stays masked.
            x, y = 1000 // factor, 1000 // factor
            self.assertEqual(mask.GetOverview(index).ReadRaster(x, y, 1, 1)[0], 0)
            self.assertEqual(mask.GetOverview(index).ReadRaster(10, 10, 1, 1)[0], 255)
        raster = None
        layer = None
        self.assertFalse(target.with_suffix(".tif.ovr").exists())
        self.assertFalse(target.with_suffix(".tif.msk").exists())

    def test_rgba_overviews_preserve_color_and_partial_transparency(self):
        path = self.folder / "rgba.tif"
        source = gdal.GetDriverByName("GTiff").Create(
            str(path), 512, 512, 4, gdal.GDT_Byte
        )
        source.SetProjection(self.crs.toWkt())
        source.SetGeoTransform([500000, 1, 0, 500512, 0, -1])
        for index, value in enumerate((20, 80, 130, 128), 1):
            source.GetRasterBand(index).Fill(value)
        source.GetRasterBand(4).SetColorInterpretation(gdal.GCI_AlphaBand)
        source = None
        layer = QgsRasterLayer(str(path), "RGBA", "gdal")
        result = write_raster_data(
            layer,
            self.project,
            self.area,
            self.crs,
            self.folder,
            "rgba",
            lambda: False,
            lambda _: None,
        )
        raster = gdal.Open(str(self.folder / result["local_source"][2:]))
        self.assertEqual(raster.RasterCount, 4)
        self.assertEqual(result["overview_factors"], [2])
        self.assertEqual(
            [
                raster.GetRasterBand(b).GetOverview(0).ReadRaster(10, 10, 1, 1)[0]
                for b in range(1, 5)
            ],
            [20, 80, 130, 128],
        )
        self.assertEqual(
            raster.GetRasterBand(4).GetOverview(0).ReadRaster(125, 125, 1, 1)[0], 0
        )
        raster = None
        layer = None

    def test_cancelling_pyramids_removes_incomplete_raster(self):
        path = self.folder / "cancel_source.tif"
        source = gdal.GetDriverByName("GTiff").Create(
            str(path), 512, 512, 1, gdal.GDT_UInt16
        )
        source.SetProjection(self.crs.toWkt())
        source.SetGeoTransform([500000, 1, 0, 500512, 0, -1])
        source.GetRasterBand(1).Fill(100)
        source = None
        layer = QgsRasterLayer(str(path), "Cancelled", "gdal")
        cancelled = False

        def progress(message):
            nonlocal cancelled
            if "piramid" in message:
                cancelled = True

        with self.assertRaises(InterruptedError):
            write_raster_data(
                layer,
                self.project,
                self.area,
                self.crs,
                self.folder,
                "cancelled",
                lambda: cancelled,
                progress,
            )
        self.assertTrue(cancelled)
        self.assertFalse((self.folder / "zasoby" / "cancelled.tif").exists())
        self.assertFalse(list(self.folder.glob(".cutline-*")))
        self.assertTrue(path.exists())
        layer = None


class MapOverviewTests(unittest.TestCase):
    setUp = fixtures.RasterTests.setUp
    tearDown = fixtures.RasterTests.tearDown

    def capture(self, empty_zoom=None):
        self.area = QgsGeometry.fromRect(QgsRectangle(500000, 500000, 500512, 500512))
        levels = zoom_levels(self.project, self.area, self.crs, 16, 18)
        zoom_by_resolution = {
            round(level["resolution"], 9): level["zoom"] for level in levels
        }

        def render(layer, project, bounds, width, height, cancelled, progress):
            zoom = zoom_by_resolution[round(bounds.width() / width, 9)]
            image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(
                QColor(0, 0, 0, 0)
                if zoom == empty_zoom
                else QColor({16: "red", 17: "green", 18: "blue"}[zoom])
            )
            return image

        with patch(
            "mbtiles_batch_exporter.raster_archive._render_image", side_effect=render
        ):
            return write_rendered_raster(
                self.layer,
                self.project,
                self.area,
                self.crs,
                self.database,
                "map",
                levels,
                lambda: False,
                lambda _: None,
            )

    def test_empty_zoom_is_visible_without_overwriting_scale_specific_images(self):
        result = self.capture(empty_zoom=16)
        stats = result["raster"]
        self.assertEqual(_empty_zoom_overviews(self.database, "map", stats), [16])
        self.assertEqual(_empty_zoom_overviews(self.database, "map", stats), [16])
        with closing(sqlite3.connect(self.database)) as db:
            count = db.execute("SELECT COUNT(*) FROM map").fetchone()[0]
            empty_png = db.execute(
                "SELECT tile_data FROM map WHERE zoom_level=16"
            ).fetchall()
        self.assertEqual(len(empty_png), 1)
        self.assertEqual(count, result["tile_count"] + 1)
        self.assertEqual(result["status"], "empty")
        payload = empty_png[0][0]
        self.assertEqual(payload[25], 6)
        offset = 8
        while payload[offset + 4 : offset + 8] != b"IDAT":
            offset += struct.unpack(">I", payload[offset : offset + 4])[0] + 12
        self.assertEqual(payload[offset + 9] >> 6, 3)

        # Exercise the append branch, not merely copying the first GPKG wholesale.
        target = self.folder / "merged.gpkg"
        vector = ogr.GetDriverByName("GPKG").CreateDataSource(str(target))
        vector.CreateLayer("vector", geom_type=ogr.wkbPoint)
        vector = None
        merge_raster(self.database, target, "map")
        for path in (self.database, target):
            raster = gdal.OpenEx(
                str(path), gdal.OF_RASTER, open_options=["TABLE=map", "ZOOM_LEVEL=18"]
            )
            self.assertEqual(raster.GetRasterBand(1).GetOverviewCount(), 2)
            self.assertEqual(
                [
                    raster.GetRasterBand(b).GetOverview(0).ReadRaster(10, 10, 1, 1)[0]
                    for b in range(1, 5)
                ],
                [0, 128, 0, 255],
            )
            self.assertEqual(
                raster.GetRasterBand(4).GetOverview(1).ReadRaster(10, 10, 1, 1)[0], 0
            )
            self.assertEqual(raster.GetRasterBand(3).ReadRaster(10, 10, 1, 1)[0], 255)
            raster = None
            local = QgsRasterLayer(
                str(path) + "|option:TABLE=map|option:ZOOM_LEVEL=18", "Map", "gdal"
            )
            self.assertTrue(local.isValid())
            self.assertEqual(
                sum(
                    pyramid.exists
                    for pyramid in local.dataProvider().buildPyramidList()
                ),
                2,
            )
            local = None

    def test_failed_and_pending_zooms_do_not_receive_empty_markers(self):
        self.capture()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("DELETE FROM map")
        stats = {
            "levels": [
                {"zoom": 16, "total": 4, "nonempty": 0, "empty": 4, "failed": 0},
                {"zoom": 17, "total": 9, "nonempty": 0, "empty": 8, "failed": 1},
                {
                    "zoom": 18,
                    "total": 36,
                    "nonempty": 0,
                    "empty": 35,
                    "failed": 0,
                    "pending": 1,
                },
            ]
        }
        self.assertEqual(_empty_zoom_overviews(self.database, "map", stats), [16])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(
                db.execute("SELECT zoom_level FROM map").fetchall(), [(16,)]
            )

    def test_missing_fine_tile_remains_missing_despite_valid_coarse_overviews(self):
        result = self.capture()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute(
                "DELETE FROM map WHERE zoom_level=18 AND tile_column=0 AND tile_row=0"
            )
        for level in result["raster"]["levels"]:
            if level["zoom"] == 18:
                level["nonempty"] -= 1
                level["failed"] += 1
        self.assertEqual(
            _empty_zoom_overviews(self.database, "map", result["raster"]), []
        )
        raster = gdal.OpenEx(
            str(self.database),
            gdal.OF_RASTER,
            open_options=["TABLE=map", "ZOOM_LEVEL=18"],
        )
        self.assertEqual(raster.GetRasterBand(4).ReadRaster(10, 10, 1, 1)[0], 0)
        self.assertEqual(
            raster.GetRasterBand(4).GetOverview(1).ReadRaster(10, 10, 1, 1)[0], 255
        )
        raster = None
