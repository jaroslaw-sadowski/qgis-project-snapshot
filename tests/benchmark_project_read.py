# SPDX-License-Identifier: GPL-2.0-only

"""Optional native QGIS benchmark of temporary project reads, not download speed."""

import argparse
import json
import statistics
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import test_raster_archive as fixtures
from osgeo import gdal
from qgis.core import (
    Qgis,
    QgsLayoutItemLabel,
    QgsPrintLayout,
    QgsProject,
    QgsRasterLayer,
)


def benchmark(output):
    rows = []
    with TemporaryDirectory(prefix="snapshot-project-read-") as temporary:
        folder = Path(temporary)
        source = folder / "map.tif"
        with gdal.ExceptionMgr():
            raster = gdal.GetDriverByName("GTiff").Create(str(source), 256, 256, 4)
            raster.SetGeoTransform([0, 1, 0, 256, 0, -1])
            raster.SetProjection(
                fixtures.QgsCoordinateReferenceSystem("EPSG:3857").toWkt()
            )
            for band in range(1, 5):
                raster.GetRasterBand(band).Fill(band * 50)
            raster = None
        project = QgsProject()
        try:
            for index in range(166):
                layer = QgsRasterLayer(str(source), f"Layer {index}", "gdal")
                project.addMapLayer(layer)
            assert project.write(str(folder / "plain.qgz"))
            for index in range(20):
                layout = QgsPrintLayout(project)
                layout.initializeDefaults()
                layout.setName(f"Layout {index}")
                for item in range(20):
                    label = QgsLayoutItemLabel(layout)
                    label.setText(f"Label {item}")
                    layout.addLayoutItem(label)
                project.layoutManager().addLayout(layout)
            assert project.write(str(folder / "layouts.qgz"))
        finally:
            project.clear()
        flags = (
            Qgis.ProjectReadFlag.DontStoreOriginalStyles
            | Qgis.ProjectReadFlag.DontLoadLayouts
            | Qgis.ProjectReadFlag.DontLoad3DViews
        )
        for name in ("plain.qgz", "layouts.qgz"):
            samples = {"default": [], "technical": []}
            expected = None
            # Alternate order to avoid giving only one variant a warmed file cache.
            for optimized in (False, True, True, False, False, True):
                project = QgsProject()
                try:
                    started = time.perf_counter()
                    assert project.read(
                        str(folder / name),
                        flags if optimized else Qgis.ProjectReadFlags(),
                    )
                    seconds = time.perf_counter() - started
                    samples["technical" if optimized else "default"].append(seconds)
                    layers = list(project.mapLayers().values())
                    assert len(layers) == 166 and all(x.isValid() for x in layers)
                    assert len(project.layoutManager().layouts()) == (
                        20 if name == "layouts.qgz" and not optimized else 0
                    )
                    image = fixtures._render_image(
                        layers[0],
                        project,
                        layers[0].extent(),
                        256,
                        256,
                        lambda: False,
                        lambda _: None,
                    )
                    assert not image.isNull() and image.pixelColor(100, 100).alpha()
                    if expected is None:
                        expected = image.copy()
                    assert image == expected
                finally:
                    project.clear()
            rows.append(
                {
                    "scenario": name,
                    "seconds": samples,
                    "median_seconds": {
                        k: statistics.median(v) for k, v in samples.items()
                    },
                    "identical_pixels": True,
                }
            )
            print(json.dumps(rows[-1]), flush=True)
    output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    benchmark(parser.parse_args().output)
