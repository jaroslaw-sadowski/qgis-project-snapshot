# -*- coding: utf-8 -*-
from .i18n import tr
import re
from datetime import date

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsMapLayer,
    QgsCoordinateTransform,
    QgsRectangle,
)

ALGORITHM_CANDIDATES = ("native:tilesxyzmbtiles", "qgis:tilesxyzmbtiles")

def get_algorithm_id() -> str:
    for candidate in ALGORITHM_CANDIDATES:
        if QgsApplication.processingRegistry().algorithmById(candidate):
            return candidate
    raise RuntimeError(
        tr("Nie znaleziono algorytmu 'Generate XYZ tiles (MBTiles)' w Processing. Sprawdź czy w QGIS dostępny jest algorytm tilesxyzmbtiles.")
    )

def sanitize_layer_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "_", name)

def build_output_file(output_folder, layer_name: str) -> str:
    safe_name = sanitize_layer_name(layer_name)
    today = date.today().strftime("%Y%m%d")
    return str(output_folder / f"{safe_name}_{today}.mbtiles")

def iter_target_layer_nodes():
    root = QgsProject.instance().layerTreeRoot()
    all_layer_nodes = root.findLayers()
    target_nodes = []
    for node in all_layer_nodes:
        layer = node.layer()
        if not layer or not layer.isValid():
            continue
        if layer.type() in (QgsMapLayer.VectorLayer, QgsMapLayer.RasterLayer):
            target_nodes.append(node)
    if not target_nodes:
        raise RuntimeError(tr('Nie znaleziono żadnych warstw wektorowych ani rastrowych do przetworzenia.'))
    return all_layer_nodes, target_nodes

def extent_to_processing_string(extent: QgsRectangle, crs_authid: str) -> str:
    return f"{extent.xMinimum()},{extent.xMaximum()},{extent.yMinimum()},{extent.yMaximum()} [{crs_authid}]"

def canvas_extent_string(iface) -> str:
    canvas = iface.mapCanvas()
    extent = canvas.extent()
    crs = canvas.mapSettings().destinationCrs()
    return extent_to_processing_string(extent, crs.authid())

def polygon_layer_extent_string(layer) -> str:
    if layer.selectedFeatureCount() > 0:
        ext = None
        for f in layer.getSelectedFeatures():
            bb = f.geometry().boundingBox()
            if ext is None:
                ext = bb
            else:
                ext.combineExtentWith(bb)
        extent = ext if ext is not None else layer.extent()
    else:
        extent = layer.extent()

    project_crs = QgsProject.instance().crs()
    if layer.crs() != project_crs:
        tr = QgsCoordinateTransform(layer.crs(), project_crs, QgsProject.instance())
        extent = tr.transformBoundingBox(extent)

    return extent_to_processing_string(extent, project_crs.authid())
