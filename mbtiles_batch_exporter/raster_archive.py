# SPDX-License-Identifier: GPL-2.0-only

# -*- coding: utf-8 -*-
"""Bounded-memory raster capture using QGIS rendering and GDAL GeoPackage."""

import json
import math
import sqlite3
import time
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from osgeo import gdal
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsGeometry,
    QgsMapRendererSequentialJob,
    QgsMapSettings,
    QgsNetworkAccessManager,
    QgsNetworkReplyContent,
    QgsNetworkRequestParameters,
    QgsPointXY,
    QgsRectangle,
    QgsScaleCalculator,
    QgsSqliteUtils,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QPointF,
    QSize,
    Qt,
    QThread,
    QUrl,
    QUrlQuery,
)
from qgis.PyQt.QtGui import QImage, QPainter, QPainterPath, QPolygonF
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from .adaptive import DownloadError, HostDeferred, retry_after
from .i18n import tr

TILE_SIZE = 256
PNG_OPTIONS = ["TILE_FORMAT=PNG", "ZLEVEL=9"]
RENDER_TIMEOUT = 60


def zoom_levels(project, area, area_crs, zoom_min, zoom_max):
    """XYZ-equivalent resolution at the AOI center, expressed in project units."""
    if not (
        isinstance(zoom_min, int)
        and isinstance(zoom_max, int)
        and 0 <= zoom_min <= zoom_max <= 24
    ):
        raise ValueError(
            tr("Wybierz zoom od 0 do 24; minimum nie może przekraczać maksimum.")
        )
    crs = project.crs()
    if not crs.isValid() or not area_crs.isValid() or area.isEmpty():
        raise ValueError(
            tr(
                (
                    "Nie można obliczyć skali bez poprawnego obszaru i "
                    "układu współrzędnych."
                )
            )
        )
    mercator = QgsCoordinateReferenceSystem("EPSG:3857")
    center = area.boundingBox().center()
    center = QgsCoordinateTransform(area_crs, mercator, project).transform(center)
    if abs(center.y()) > 20037508.342789244:
        raise ValueError(
            tr(
                (
                    "Wybrany obszar znajduje się poza zakresem zoomów XYZ "
                    "(obszary polarne)."
                )
            )
        )
    transform = QgsCoordinateTransform(mercator, crs, project)
    origin = transform.transform(center)
    east = transform.transform(QgsPointXY(center.x() + 1, center.y()))
    local_factor = math.hypot(east.x() - origin.x(), east.y() - origin.y())
    if not math.isfinite(local_factor) or local_factor <= 0:
        raise ValueError(
            tr("Nie udało się przeliczyć rozdzielczości do układu projektu.")
        )
    calculator = QgsScaleCalculator(96)
    calculator.setMapUnits(crs.mapUnits())
    levels = []
    for zoom in range(zoom_min, zoom_max + 1):
        resolution = 156543.03392804097 * local_factor / 2**zoom
        half = resolution * TILE_SIZE / 2
        rectangle = QgsRectangle(
            origin.x() - half, origin.y() - half, origin.x() + half, origin.y() + half
        )
        levels.append(
            {
                "zoom": zoom,
                "resolution": resolution,
                "scale": calculator.calculate(rectangle, TILE_SIZE),
            }
        )
    return levels


def intersecting_tiles(area, x0, y0, resolution, width, height):
    """Prune rectangular grid regions instead of scanning a long corridor's bbox."""
    engine = QgsGeometry.createGeometryEngine(area.constGet())
    engine.prepareGeometry()
    pending = [(0, 0, math.ceil(width / TILE_SIZE), math.ceil(height / TILE_SIZE))]
    while pending:
        left, top, right, bottom = pending.pop()
        bounds = QgsRectangle(
            x0 + left * TILE_SIZE * resolution,
            y0 - bottom * TILE_SIZE * resolution,
            x0 + right * TILE_SIZE * resolution,
            y0 - top * TILE_SIZE * resolution,
        )
        rectangle = QgsGeometry.fromRect(bounds)
        if not engine.intersects(rectangle.constGet()):
            continue
        if right - left == 1 and bottom - top == 1:
            yield left, top
        elif right - left >= bottom - top:
            middle = (left + right) // 2
            pending.extend([(middle, top, right, bottom), (left, top, middle, bottom)])
        else:
            middle = (top + bottom) // 2
            pending.extend([(left, middle, right, bottom), (left, top, right, middle)])


def _render_image(layer, project, bounds, width, height, cancelled, progress):
    settings = QgsMapSettings()
    settings.setDestinationCrs(project.crs())
    settings.setTransformContext(project.transformContext())
    settings.setLayers([layer])
    settings.setBackgroundColor(Qt.GlobalColor.transparent)
    settings.setOutputDpi(96)
    settings.setOutputSize(QSize(width, height))
    settings.setExtent(bounds)
    settings.setLabelingEngineSettings(project.labelingEngineSettings())
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    # globalProjectLayerScopes normally uses the singleton; archives can use
    # another project.
    context.appendScope(QgsExpressionContextUtils.projectScope(project))
    settings.setExpressionContext(context)
    job = QgsMapRendererSequentialJob(settings)
    # WMS providers may return a transparent image on HTTP errors without adding
    # a renderer error. Observe new requests to this source during this job only.
    source_uri = QgsDataSourceUri()
    source_uri.setEncodedUri(layer.source())
    service = QUrl(source_uri.param("url"))
    network = QgsNetworkAccessManager.instance()
    requests, request_threads, network_errors = set(), set(), []

    def request_created(request):
        # Redirects and tiled services may download from another host. Follow
        # the renderer's network thread after its first source request, without
        # collecting unrelated desktop QGIS requests from other threads.
        thread = request.originatingThreadId()
        if (service.host() and request.request().url().host() == service.host()) or (
            thread and thread in request_threads
        ):
            requests.add(request.requestId())
            if thread:
                request_threads.add(thread)

    def request_timed_out(request):
        if request.requestId() in requests:
            # QGIS aborts timed-out replies, which Qt reports as
            # OperationCanceledError (5), not TimeoutError (4).
            network_errors.append(("timeout", None))

    def reply_finished(reply):
        if reply.requestId() not in requests:
            return
        content_type = (
            bytes(reply.rawHeader(b"Content-Type"))
            .decode("ascii", errors="replace")
            .lower()
        )
        operation = QUrlQuery(reply.request().url()).queryItemValue("REQUEST").lower()
        if reply.error() != QNetworkReply.NetworkError.NoError or (
            operation == "getmap" and "xml" in content_type
        ):
            code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() == QNetworkReply.NetworkError.TimeoutError:
                code = "timeout"
            network_errors.append(
                (
                    code,
                    retry_after(
                        bytes(reply.rawHeader(b"Retry-After")).decode(
                            "ascii", errors="replace"
                        )
                    ),
                )
            )

    network.requestAboutToBeCreated[QgsNetworkRequestParameters].connect(
        request_created
    )
    network.finished[QgsNetworkReplyContent].connect(reply_finished)
    network.requestTimedOut[QgsNetworkRequestParameters].connect(request_timed_out)
    deadline = time.monotonic() + RENDER_TIMEOUT
    timed_out = False
    last_notice = time.monotonic()
    job.start()
    try:
        while job.isActive():
            QCoreApplication.processEvents()
            if time.monotonic() - last_notice >= 5:
                seconds = int(RENDER_TIMEOUT - (deadline - time.monotonic()))
                progress(
                    tr(
                        (
                            "{0}: renderowanie lub oczekiwanie na dane — {1} s "
                            "(limit {2} s)."
                        )
                    ).format(layer.name(), seconds, RENDER_TIMEOUT)
                )
                last_notice = time.monotonic()
            if cancelled() or time.monotonic() > deadline:
                timed_out = not cancelled()
                job.cancelWithoutBlocking()
                # Keep renderer and layer alive until the native job
                # finishes cancellation.
                job.waitForFinished()
                break
            QThread.msleep(10)
        if cancelled():
            raise InterruptedError(tr("Przerwano pobieranie obrazu."))
        if timed_out:
            raise TimeoutError(tr("Przekroczono czas pobierania fragmentu mapy."))
        QCoreApplication.processEvents()
        if network_errors:
            for code in (429, 503):
                if code in [item[0] for item in network_errors]:
                    message = (
                        "[HTTP 429] "
                        + tr(
                            (
                                "Serwer {0}: zbyt wiele zapytań. Potrzebna jest "
                                "przerwa przed ponownym pobieraniem."
                            )
                        ).format(service.host())
                        if code == 429
                        else "[HTTP 503] "
                        + tr(
                            (
                                "Serwer {0}: usługa niedostępna lub przeciążona. HTTP "
                                "503 nie potwierdza, że przyczyną jest liczba zapytań."
                            )
                        ).format(service.host())
                    )
                    progress(message)
                    raise DownloadError(
                        message,
                        code,
                        next(
                            delay for status, delay in network_errors if status == code
                        ),
                    )
            if any(code == "timeout" for code, _ in network_errors):
                raise TimeoutError(tr("Przekroczono czas pobierania fragmentu mapy."))
            code = network_errors[0][0]
            raise DownloadError(
                tr("Usługa mapowa zwróciła błąd sieciowy lub odpowiedź błędu WMS."),
                code,
            )
        if job.errors():
            raise RuntimeError(
                tr("Renderer QGIS zgłosił błąd pobierania lub rysowania warstwy.")
            )
        result = job.renderedImage()
        if result.isNull():
            raise RuntimeError(tr("QGIS nie zwrócił obrazu mapy."))
        return result
    finally:
        if job.isActive():
            job.cancel()
        network.requestAboutToBeCreated[QgsNetworkRequestParameters].disconnect(
            request_created
        )
        network.finished[QgsNetworkReplyContent].disconnect(reply_finished)
        network.requestTimedOut[QgsNetworkRequestParameters].disconnect(
            request_timed_out
        )


def _render_tile(
    layer,
    project,
    bounds,
    resolution,
    size,
    cancelled,
    progress,
    counters,
    gate=None,
    *,
    retry_managed=False,
):
    # A small gutter avoids cutting strokes at tile edges. Output remains 256px.
    gutter = 16
    expanded = QgsRectangle(bounds)
    expanded.grow(gutter * resolution)
    for attempt in range(3):
        if cancelled():
            raise InterruptedError(tr("Przerwano pobieranie obrazu."))
        try:
            if gate:
                started = time.monotonic()
                try:
                    gate.before(retry=gate.retrying)
                finally:
                    counters["timing_seconds"]["gate"] += time.monotonic() - started
            started = time.monotonic()
            try:
                image = _render_image(
                    layer,
                    project,
                    expanded,
                    size + 2 * gutter,
                    size + 2 * gutter,
                    cancelled,
                    progress,
                )
            finally:
                counters["timing_seconds"]["render"] += time.monotonic() - started
            return image.copy(gutter, gutter, size, size)
        except (InterruptedError, HostDeferred):
            raise
        except (RuntimeError, TimeoutError) as error:
            if str(error).startswith(("[HTTP 429]", "[HTTP 503]")):
                warnings = counters.setdefault("server_warnings", [])
                if str(error) not in warnings:
                    warnings.append(str(error))
                if gate or retry_managed or str(error).startswith("[HTTP 429]"):
                    raise  # Do not amplify an explicit rate limit with tile retries.
            if (
                gate
                or retry_managed
                or getattr(error, "status", None) in (401, 403, 404, 407)
            ):
                # Adaptive maps have one disk ledger governing all attempts.
                # Nested immediate retries/subdivision would bypass its budget,
                # especially when a recovery probe fails with a different error.
                raise
            # Some providers cache the empty image produced by a failed request.
            # Invalidate only the disposable clone before trying again.
            if layer.dataProvider() is not None:
                layer.dataProvider().reloadData()
            if attempt < 2:
                counters["retries"] += 1
                progress(
                    tr("{0}: ponowienie pobierania fragmentu ({1}/2)…").format(
                        layer.name(), attempt + 1
                    )
                )
    if size <= 128:
        raise RuntimeError(
            tr(
                (
                    "Pobieranie nie powiodło się także po ponowieniach i "
                    "podziale fragmentu."
                )
            )
        )
    counters["subdivisions"] += 1
    result = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    try:
        half = size // 2
        for row in range(2):
            for column in range(2):
                x = bounds.xMinimum() + column * half * resolution
                y = bounds.yMaximum() - row * half * resolution
                part = QgsRectangle(x, y - half * resolution, x + half * resolution, y)
                image = _render_tile(
                    layer,
                    project,
                    part,
                    resolution,
                    half,
                    cancelled,
                    progress,
                    counters,
                    gate,
                )
                painter.drawImage(column * half, row * half, image)
    finally:
        painter.end()
    return result


def _mask_image(image, area, bounds, resolution, stats=None):
    started = time.monotonic()
    if stats is not None:
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        raw_nonempty = any(rgba.constBits().asstring(rgba.sizeInBytes())[3::4])
        stats["raw_nonempty" if raw_nonempty else "raw_empty"] += 1
    clipped = area.intersection(QgsGeometry.fromRect(bounds))
    if clipped.lastError() or (not clipped.isEmpty() and not clipped.isGeosValid()):
        raise RuntimeError(tr("Nie udało się wyznaczyć maski fragmentu mapy."))
    mask = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    mask.fill(Qt.GlobalColor.transparent)
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    # A tile touching only a boundary may intersect as a line/point, not a polygon.
    if not clipped.isEmpty() and clipped.area() > 0:
        polygons = (
            clipped.asMultiPolygon() if clipped.isMultipart() else [clipped.asPolygon()]
        )
        for polygon in polygons:
            for ring in polygon:
                path.addPolygon(
                    QPolygonF(
                        [
                            QPointF(
                                (point.x() - bounds.xMinimum()) / resolution,
                                (bounds.yMaximum() - point.y()) / resolution,
                            )
                            for point in ring
                        ]
                    )
                )
    painter = QPainter(mask)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillPath(path, Qt.GlobalColor.white)
    painter.end()
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, mask)
    painter.end()
    result = image.convertToFormat(QImage.Format.Format_RGBA8888)
    if stats is not None:
        if raw_nonempty and not any(
            result.constBits().asstring(result.sizeInBytes())[3::4]
        ):
            stats["masked_out"] += 1
        stats["timing_seconds"]["mask"] += time.monotonic() - started
    return result


def write_rendered_raster(
    layer,
    project,
    area,
    area_crs,
    database,
    table,
    levels,
    cancelled,
    progress,
    gate=None,
    *,
    resume=False,
    ledger_path=None,
    legacy_retries=False,
):
    """One sparse RGBA tile table; each zoom is rendered independently."""
    quoted_table = QgsSqliteUtils.quotedIdentifier(table)
    mask = QgsGeometry(area)
    if area_crs != project.crs():
        mask.transform(QgsCoordinateTransform(area_crs, project.crs(), project))
    bounds = mask.boundingBox()
    finest = levels[-1]["resolution"]
    width = math.ceil(bounds.width() / (finest * TILE_SIZE)) * TILE_SIZE
    height = math.ceil(bounds.height() / (finest * TILE_SIZE)) * TILE_SIZE
    if not (0 < width < 2**31 and 0 < height < 2**31):
        raise ValueError(
            tr(
                (
                    "Rozmiar rastra przekracza limit formatu. Zmniejsz "
                    "obszar lub maksymalny zoom."
                )
            )
        )
    x0, y0 = bounds.xMinimum(), bounds.yMaximum()
    ledger_path = (
        Path(ledger_path)
        if ledger_path is not None
        else gate.folder / (table + ".tiles.sqlite")
        if gate
        else None
    )
    if resume and ledger_path is None:
        raise ValueError(
            tr("Nie można wznowić kafelków: brak poprawnego rejestru lub danych.")
        )
    existing = False
    if resume and Path(database).is_file():
        with closing(sqlite3.connect(database)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError(
                    tr(
                        "Nie można wznowić kafelków: "
                        "brak poprawnego rejestru lub danych."
                    )
                )
            existing = bool(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
            )
    clone = layer.clone()
    if clone is None or not clone.isValid():
        raise RuntimeError(tr("Nie można przygotować warstwy do zapisu obrazu."))
    if isinstance(layer, QgsVectorLayer) and layer.isEditable():
        # clone() copies provider data, but omits unsaved edits. Replay just the
        # edit buffer on the disposable clone; never commit to the real provider.
        edits = layer.editBuffer()
        if not clone.startEditing():
            raise RuntimeError(
                tr("Nie można uwzględnić niezapisanych edycji w obrazie.")
            )
        operations = []
        for index in sorted(edits.deletedAttributeIds(), reverse=True):
            operations.append(clone.deleteAttribute(index))
        for field in edits.addedAttributes():
            operations.append(clone.addAttribute(field))
        for feature_id in edits.deletedFeatureIds():
            operations.append(clone.deleteFeature(feature_id))
        for feature_id, geometry in edits.changedGeometries().items():
            operations.append(clone.changeGeometry(feature_id, geometry))
        for feature_id, values in edits.changedAttributeValues().items():
            for index, value in values.items():
                operations.append(clone.changeAttributeValue(feature_id, index, value))
        for feature in edits.addedFeatures().values():
            operations.append(clone.addFeature(feature))
        if not all(operations):
            raise RuntimeError(
                tr(
                    (
                        "Nie udało się uwzględnić wszystkich niezapisanych "
                        "edycji w obrazie."
                    )
                )
            )
    clone.setScaleBasedVisibility(False)
    # Blend against other layers in the archive, not against a transparent capture
    # canvas.
    clone.setBlendMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    dataset = None
    stats = {
        "retries": 0,
        "subdivisions": 0,
        "levels": [],
        "failures": [],
        "stopped_early": False,
        "raw_empty": 0,
        "raw_nonempty": 0,
        "masked_out": 0,
        "timing_seconds": {"gate": 0.0, "render": 0.0, "mask": 0.0, "write": 0.0},
    }
    initialization = None
    destination_database = Path(database)
    try:
        if ledger_path is not None and not destination_database.exists():
            # A crash during GDAL's multi-step header creation must not publish
            # a malformed checkpoint. No downloads begin until this file moves.
            initialization = TemporaryDirectory(
                prefix=".raster-init-", dir=destination_database.parent
            )
            database = Path(initialization.name) / "raster.gpkg"
        with (
            gdal.ExceptionMgr(),
            gdal.config_options(
                {"OGR_SQLITE_SYNCHRONOUS": "FULL", "OGR_SQLITE_JOURNAL": "DELETE"}
                if ledger_path is not None
                else {}
            ),
        ):
            if existing:
                dataset = gdal.OpenEx(
                    str(database),
                    gdal.OF_RASTER,
                    open_options=[
                        f"TABLE={table}",
                        f"ZOOM_LEVEL={levels[-1]['zoom']}",
                        "BAND_COUNT=4",
                    ],
                )
                if (
                    dataset is None
                    or dataset.RasterCount != 4
                    or dataset.RasterXSize != width
                    or dataset.RasterYSize != height
                    or QgsCoordinateReferenceSystem(dataset.GetProjection())
                    != project.crs()
                    or any(
                        not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9)
                        for actual, expected in zip(
                            dataset.GetGeoTransform(), [x0, finest, 0, y0, 0, -finest]
                        )
                    )
                ):
                    raise ValueError(
                        tr(
                            "Nie można wznowić kafelków: "
                            "niezgodny obszar, CRS lub siatka."
                        )
                    )
                dataset = None
            else:
                dataset = gdal.GetDriverByName("GPKG").Create(
                    str(database),
                    width,
                    height,
                    4,
                    gdal.GDT_Byte,
                    options=[
                        "RASTER_TABLE=" + table,
                        "APPEND_SUBDATASET=YES",
                        "BLOCKSIZE=256",
                    ]
                    + PNG_OPTIONS,
                )
                dataset.SetProjection(project.crs().toWkt(Qgis.CrsWktVariant.Wkt2_2019))
                dataset.SetGeoTransform([x0, finest, 0, y0, 0, -finest])
                dataset.FlushCache()
                dataset = None
            # GDAL creates standard empty tile matrices. Specify only requested zooms,
            # including coarse zooms for tiny AOIs, without scanning a
            # huge empty raster.
            with closing(sqlite3.connect(database)) as connection:
                matrices = [
                    (
                        table,
                        level["zoom"],
                        math.ceil(width * finest / (TILE_SIZE * level["resolution"])),
                        math.ceil(height * finest / (TILE_SIZE * level["resolution"])),
                        TILE_SIZE,
                        TILE_SIZE,
                        level["resolution"],
                        level["resolution"],
                    )
                    for level in levels
                ]
                if existing:
                    actual = connection.execute(
                        "SELECT * FROM gpkg_tile_matrix WHERE table_name=? "
                        "ORDER BY zoom_level",
                        (table,),
                    ).fetchall()
                    if actual != sorted(matrices, key=lambda value: value[1]):
                        raise ValueError(
                            tr(
                                "Nie można wznowić kafelków: "
                                "niezgodny obszar, CRS lub siatka."
                            )
                        )
                with connection:
                    if not existing:
                        connection.execute(
                            "DELETE FROM gpkg_tile_matrix WHERE table_name=?", (table,)
                        )
                        connection.executemany(
                            "INSERT INTO gpkg_tile_matrix VALUES (?,?,?,?,?,?,?,?)",
                            matrices,
                        )
            if initialization is not None:
                Path(database).replace(destination_database)
                database = destination_database
                initialization.cleanup()
                initialization = None
            if ledger_path is not None:
                _capture_adaptive(
                    clone,
                    project,
                    mask,
                    database,
                    table,
                    levels,
                    x0,
                    y0,
                    cancelled,
                    progress,
                    stats,
                    gate,
                    ledger_path,
                    resume,
                    legacy_retries,
                )
            else:
                failures_in_a_row = 0
                for level in reversed(levels):
                    zoom, resolution = level["zoom"], level["resolution"]
                    progress(
                        tr(
                            (
                                "{0}: rozpoczęcie zoomu {1}; rozdzielczość {2:.3g} "
                                "jednostek/piksel."
                            )
                        ).format(layer.name(), zoom, resolution)
                    )
                    level_stats = dict(
                        zoom=zoom, attempted=0, nonempty=0, empty=0, failed=0
                    )
                    stats["levels"].append(level_stats)
                    dataset = gdal.OpenEx(
                        str(database),
                        gdal.OF_RASTER | gdal.OF_UPDATE,
                        open_options=[
                            f"TABLE={table}",
                            f"ZOOM_LEVEL={zoom}",
                            "BAND_COUNT=4",
                        ]
                        + PNG_OPTIONS,
                    )
                    for column, row in intersecting_tiles(
                        mask,
                        x0,
                        y0,
                        resolution,
                        dataset.RasterXSize,
                        dataset.RasterYSize,
                    ):
                        progress(
                            tr("{0} — zoom {1}, fragment {2}").format(
                                layer.name(), zoom, level_stats["attempted"] + 1
                            )
                        )
                        if cancelled():
                            raise InterruptedError(tr("Przerwano pobieranie obrazu."))
                        level_stats["attempted"] += 1
                        x, y = (
                            x0 + column * TILE_SIZE * resolution,
                            y0 - row * TILE_SIZE * resolution,
                        )
                        tile_bounds = QgsRectangle(
                            x, y - TILE_SIZE * resolution, x + TILE_SIZE * resolution, y
                        )
                        try:
                            image = _render_tile(
                                clone,
                                project,
                                tile_bounds,
                                resolution,
                                TILE_SIZE,
                                cancelled,
                                progress,
                                stats,
                            )
                        except InterruptedError:
                            raise
                        except (RuntimeError, TimeoutError) as error:
                            level_stats["failed"] += 1
                            failures_in_a_row += 1
                            if len(stats["failures"]) < 20:
                                stats["failures"].append(
                                    {
                                        "zoom": zoom,
                                        "column": column,
                                        "row": row,
                                        "reason": str(error),
                                    }
                                )
                            if (
                                str(error).startswith("[HTTP 429]")
                                or failures_in_a_row >= 5
                            ):
                                stats["stopped_early"] = True
                                break
                            continue
                        failures_in_a_row = 0
                        image = _mask_image(image, mask, tile_bounds, resolution, stats)
                        # Last overview tiles can be smaller
                        # than 256 pixels at dataset edges.
                        w = min(TILE_SIZE, dataset.RasterXSize - column * TILE_SIZE)
                        h = min(TILE_SIZE, dataset.RasterYSize - row * TILE_SIZE)
                        image = image.copy(0, 0, w, h)
                        pixels = image.constBits().asstring(image.sizeInBytes())
                        if not any(pixels[3::4]):
                            level_stats["empty"] += 1
                            continue
                        started = time.monotonic()
                        dataset.WriteRaster(
                            column * TILE_SIZE,
                            row * TILE_SIZE,
                            w,
                            h,
                            pixels,
                            band_list=[1, 2, 3, 4],
                            buf_pixel_space=4,
                            buf_line_space=image.bytesPerLine(),
                            buf_band_space=1,
                        )
                        stats["timing_seconds"]["write"] += time.monotonic() - started
                        level_stats["nonempty"] += 1
                    started = time.monotonic()
                    dataset.FlushCache()
                    dataset = None
                    stats["timing_seconds"]["write"] += time.monotonic() - started
                    progress(
                        tr(
                            (
                                "{0}: zoom {1} zakończony — zapisane {2}, puste {3}, "
                                "błędne {4} fragmenty."
                            )
                        ).format(
                            layer.name(),
                            zoom,
                            level_stats["nonempty"],
                            level_stats["empty"],
                            level_stats["failed"],
                        )
                    )
                    if stats["stopped_early"]:
                        break
            if cancelled():
                raise InterruptedError(tr("Przerwano pobieranie obrazu."))
            with closing(sqlite3.connect(database)) as connection:
                tiles = connection.execute(
                    # Quoted identifier; values bound.
                    f"SELECT count(*) FROM {quoted_table}"  # nosec B608
                ).fetchone()[0]
            nonempty = sum(level["nonempty"] for level in stats["levels"])
            if tiles != nonempty:
                raise RuntimeError(
                    tr("Kontrola liczby zapisanych kafelków nie powiodła się.")
                )
            _empty_zoom_overviews(database, table, stats)
            for level in levels:
                dataset = gdal.OpenEx(
                    str(database),
                    gdal.OF_RASTER,
                    open_options=[f"TABLE={table}", f"ZOOM_LEVEL={level['zoom']}"],
                )
                if dataset.RasterCount != 4 or not math.isclose(
                    dataset.GetGeoTransform()[1], level["resolution"]
                ):
                    raise RuntimeError(
                        tr("Nieprawidłowa rozdzielczość lub kanały zapisanego obrazu.")
                    )
                dataset = None
    finally:
        dataset = None
        clone = None
        if initialization is not None:
            initialization.cleanup()
    failed = any(level["failed"] for level in stats["levels"]) or stats["stopped_early"]
    blank = any(level["nonempty"] == 0 for level in stats["levels"])
    status = (
        ("partial" if nonempty else "failed")
        if failed
        else "empty"
        if blank
        else "saved"
    )
    result = {
        "status": status,
        "method": "raster_render",
        "crs": project.crs().authid(),
        "local_source": (
            f"./dane.gpkg|option:TABLE={table}|option:ZOOM_LEVEL={levels[-1]['zoom']}"
        ),
        "local_provider": "gdal",
        "table": table,
        "tile_count": nonempty,
        "raster": stats,
        "png": {"format": "PNG", "zlevel": 9, "rgba": True},
        "reason": (
            tr(
                (
                    "Nie udało się pobrać obrazu; ponowienia i mniejsze "
                    "fragmenty również zawiodły."
                )
            )
            if status == "failed"
            else tr("Obraz częściowy: nie wszystkie fragmenty udało się pobrać.")
            if failed
            else tr(
                (
                    "Co najmniej jeden zoom jest całkowicie przezroczysty — "
                    "wymaga sprawdzenia."
                )
            )
            if blank
            else tr("Zapisano obraz z przezroczystością; każdy zoom pobrano osobno.")
        ),
    }
    if stats.get("stop_http_status") == 407:
        result["reason"] += " " + tr(
            "Proxy odrzuciło uwierzytelnianie. Sprawdź konfigurację proxy w QGIS."
        )
    if status == "failed":
        result.pop("local_source")
    return result


def _capture_adaptive(
    layer,
    project,
    mask,
    database,
    table,
    levels,
    x0,
    y0,
    cancelled,
    progress,
    stats,
    gate,
    ledger_path=None,
    resume=False,
    legacy_retries=False,
):
    """Persist whole tiles; legacy fixed mode owns its retries inside rendering."""
    legacy_retries = legacy_retries and gate is None
    attempt_limit = 1 if legacy_retries else 3
    ledger_path = (
        Path(ledger_path)
        if ledger_path is not None
        else gate.folder / (table + ".tiles.sqlite")
    )
    if ledger_path.exists() and not resume:
        raise ValueError(
            tr("Nie można wznowić kafelków: brak poprawnego rejestru lub danych.")
        )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    settings = json.dumps(
        {
            "version": 1,
            "table": table,
            "mask": mask.asWkt(),
            "crs": project.crs().toWkt(),
            "levels": levels,
            "origin": [x0, y0],
        },
        sort_keys=True,
    )
    # SQLite binds values, not identifiers; use the native QGIS quoting.
    quoted_table = QgsSqliteUtils.quotedIdentifier(table)
    deferred = False
    stop_http_status = None
    stopped_early = False
    failures_in_a_row = 0
    with (
        closing(sqlite3.connect(ledger_path)) as ledger,
        closing(sqlite3.connect(database)) as stored,
    ):
        ledger.execute("PRAGMA journal_mode=DELETE")
        ledger.execute("PRAGMA synchronous=FULL")
        if ledger.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError(
                tr("Nie można wznowić kafelków: brak poprawnego rejestru lub danych.")
            )
        ledger.execute("CREATE TABLE IF NOT EXISTS capture (settings TEXT NOT NULL)")
        recorded = ledger.execute("SELECT settings FROM capture").fetchall()
        if recorded:
            if recorded != [(settings,)]:
                raise ValueError(
                    tr("Nie można wznowić kafelków: niezgodny obszar, CRS lub siatka.")
                )
        else:
            # Quoted identifier.
            if stored.execute(
                f"SELECT count(*) FROM {quoted_table}"  # nosec B608
            ).fetchone()[0]:
                raise ValueError(
                    tr(
                        "Nie można wznowić kafelków: "
                        "brak poprawnego rejestru lub danych."
                    )
                )
            ledger.execute("INSERT INTO capture VALUES (?)", (settings,))
        ledger.execute(
            (
                "CREATE TABLE IF NOT EXISTS tiles (zoom INTEGER, col INTEGER, row "
                "INTEGER, status TEXT, attempts INTEGER DEFAULT 0, "
                'reason TEXT DEFAULT "", total_attempts INTEGER DEFAULT 0, '
                'png_sha256 TEXT DEFAULT "", PRIMARY KEY(zoom,col,row))'
            )
        )
        ledger.commit()
        for level in reversed(levels):
            zoom, resolution = level["zoom"], level["resolution"]
            progress(tr("Przygotowanie rejestru kafelków: zoom {0}…").format(zoom))
            dataset = gdal.OpenEx(
                str(database),
                gdal.OF_RASTER,
                open_options=[f"TABLE={table}", f"ZOOM_LEVEL={zoom}"],
            )
            width, height = dataset.RasterXSize, dataset.RasterYSize
            dataset = None
            for index, (column, row) in enumerate(
                intersecting_tiles(mask, x0, y0, resolution, width, height)
            ):
                if cancelled():
                    raise InterruptedError()
                ledger.execute(
                    "INSERT OR IGNORE INTO tiles(zoom,col,row,status) VALUES(?,?,?,?)",
                    (zoom, column, row, "pending"),
                )
                if index % 500 == 0:
                    ledger.commit()
                    progress(
                        tr("Przygotowanie rejestru kafelków: zoom {0}…").format(zoom)
                    )
            ledger.commit()
        stats.update(
            repair_attempts=0,
            repaired=0,
            deferred=False,
            resumed_tiles=0,
            previous_attempts=ledger.execute(
                "SELECT coalesce(sum(total_attempts),0) FROM tiles"
            ).fetchone()[0],
        )
        if resume:
            progress(tr("Sprawdzanie zachowanych kafelków…"))
            updated = time.monotonic()
            # SQLite recovers interrupted transactions when opening each file.
            # Reconcile both durable stores before opening GDAL for any writes.
            with stored:
                for zoom, column, row, payload in stored.execute(
                    # Quoted identifier; values bound.
                    "SELECT zoom_level,tile_column,tile_row,tile_data "  # nosec B608
                    f"FROM {quoted_table}"
                ):
                    if cancelled():
                        raise InterruptedError()
                    if time.monotonic() - updated > 0.1:
                        progress(tr("Sprawdzanie zachowanych kafelków…"))
                        updated = time.monotonic()
                    old = ledger.execute(
                        "SELECT status,png_sha256 FROM tiles "
                        "WHERE zoom=? AND col=? AND row=?",
                        (zoom, column, row),
                    ).fetchone()
                    checksum = sha256(payload).hexdigest()
                    if old and old[0] == "saved" and old[1] == checksum:
                        continue
                    image = QImage.fromData(payload, "PNG")
                    valid = not image.isNull() and image.size() == QSize(
                        TILE_SIZE, TILE_SIZE
                    )
                    transparent = False
                    if valid:
                        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
                        transparent = not any(
                            rgba.constBits().asstring(rgba.sizeInBytes())[3::4]
                        )
                    if transparent and (old is None or old[0] == "empty"):
                        # Empty-zoom overview markers are derived, not downloads.
                        stored.execute(
                            # Quoted identifier; values bound.
                            f"DELETE FROM {quoted_table} "  # nosec B608
                            "WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                            (zoom, column, row),
                        )
                    elif (
                        old
                        and old[0] not in ("saved", "empty")
                        and valid
                        and not transparent
                    ):
                        # A kill between PNG commit and ledger commit left a
                        # complete native PNG; retain it instead of redrawing it.
                        ledger.execute(
                            'UPDATE tiles SET status="saved",png_sha256=?, '
                            "attempts=attempts+1,total_attempts=total_attempts+1 "
                            "WHERE zoom=? AND col=? AND row=?",
                            (checksum, zoom, column, row),
                        )
                    elif old:
                        stored.execute(
                            # Quoted identifier; values bound.
                            f"DELETE FROM {quoted_table} "  # nosec B608
                            "WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                            (zoom, column, row),
                        )
                        ledger.execute(
                            'UPDATE tiles SET status="pending",png_sha256="" '
                            "WHERE zoom=? AND col=? AND row=?",
                            (zoom, column, row),
                        )
                    else:
                        raise ValueError(
                            tr(
                                "Nie można wznowić kafelków: "
                                "niezgodny obszar, CRS lub siatka."
                            )
                        )
            # A ledger success without its PNG must be requested again.
            for zoom, column, row in ledger.execute(
                'SELECT zoom,col,row FROM tiles WHERE status="saved"'
            ):
                if cancelled():
                    raise InterruptedError()
                if time.monotonic() - updated > 0.1:
                    progress(tr("Sprawdzanie zachowanych kafelków…"))
                    updated = time.monotonic()
                if not stored.execute(
                    # Quoted identifier; values bound.
                    f"SELECT 1 FROM {quoted_table} "  # nosec B608
                    "WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (zoom, column, row),
                ).fetchone():
                    ledger.execute(
                        'UPDATE tiles SET status="pending",png_sha256="" '
                        "WHERE zoom=? AND col=? AND row=?",
                        (zoom, column, row),
                    )
            ledger.execute(
                'UPDATE tiles SET status="pending",attempts=0,reason="" '
                'WHERE status NOT IN ("saved","empty")'
            )
            ledger.commit()
            stats["resumed_tiles"] = ledger.execute(
                'SELECT count(*) FROM tiles WHERE status IN ("saved","empty")'
            ).fetchone()[0]
            stats["previous_attempts"] = ledger.execute(
                "SELECT coalesce(sum(total_attempts),0) FROM tiles"
            ).fetchone()[0]
        for round_number in range(attempt_limit):
            if deferred or stop_http_status or stopped_early:
                break
            for level in reversed(levels):
                if deferred or stop_http_status or stopped_early:
                    break
                zoom, resolution = level["zoom"], level["resolution"]
                total, pending = ledger.execute(
                    'SELECT count(*),sum(status IN ("pending","retry")) '
                    "FROM tiles WHERE zoom=?",
                    (zoom,),
                ).fetchone()
                if not pending:
                    continue
                completed = total - pending
                progress(
                    tr(
                        "{0}: rozpoczęcie zoomu {1}; rozdzielczość {2:.3g} "
                        "jednostek/piksel."
                    ).format(layer.name(), zoom, resolution)
                )
                dataset = gdal.OpenEx(
                    str(database),
                    gdal.OF_RASTER | gdal.OF_UPDATE,
                    open_options=[
                        f"TABLE={table}",
                        f"ZOOM_LEVEL={zoom}",
                        "BAND_COUNT=4",
                    ]
                    + PNG_OPTIONS,
                )
                # Read a cursor, not an in-memory list of an entire corridor.
                cursor = ledger.execute(
                    (
                        "SELECT col,row,attempts FROM tiles WHERE zoom=? AND "
                        'status IN ("pending","retry") AND attempts < ? ORDER BY '
                        "col,row"
                    ),
                    (zoom, attempt_limit),
                )
                try:
                    for column, row, attempts in cursor:
                        if cancelled():
                            raise InterruptedError()
                        # An overload probe retries this
                        # missing tile before requesting a new
                        # one.
                        while attempts < attempt_limit:
                            if gate:
                                gate.retrying = attempts > 0
                            progress(
                                tr(
                                    "{0} — zoom {1}, fragment {2}/{3}, próba {4}"
                                ).format(
                                    layer.name(),
                                    zoom,
                                    completed + 1,
                                    total,
                                    attempts + 1,
                                )
                            )
                            x, y = (
                                x0 + column * TILE_SIZE * resolution,
                                y0 - row * TILE_SIZE * resolution,
                            )
                            bounds = QgsRectangle(
                                x,
                                y - TILE_SIZE * resolution,
                                x + TILE_SIZE * resolution,
                                y,
                            )
                            try:
                                image = _render_tile(
                                    layer,
                                    project,
                                    bounds,
                                    resolution,
                                    TILE_SIZE,
                                    cancelled,
                                    progress,
                                    stats,
                                    gate,
                                    retry_managed=not legacy_retries,
                                )
                                image = _mask_image(
                                    image, mask, bounds, resolution, stats
                                )
                                w = min(
                                    TILE_SIZE, dataset.RasterXSize - column * TILE_SIZE
                                )
                                h = min(
                                    TILE_SIZE, dataset.RasterYSize - row * TILE_SIZE
                                )
                                image = image.copy(0, 0, w, h)
                                pixels = image.constBits().asstring(image.sizeInBytes())
                                empty = not any(pixels[3::4])
                                started = time.monotonic()
                                if not empty:
                                    dataset.WriteRaster(
                                        column * TILE_SIZE,
                                        row * TILE_SIZE,
                                        w,
                                        h,
                                        pixels,
                                        band_list=[1, 2, 3, 4],
                                        buf_pixel_space=4,
                                        buf_line_space=image.bytesPerLine(),
                                        buf_band_space=1,
                                    )
                                dataset.FlushCache()
                                checksum = ""
                                if not empty:
                                    written = stored.execute(
                                        # Quoted identifier; values bound.
                                        "SELECT tile_data "  # nosec B608
                                        f"FROM {quoted_table} "
                                        "WHERE zoom_level=? AND tile_column=? "
                                        "AND tile_row=?",
                                        (zoom, column, row),
                                    ).fetchone()
                                    if written is None:
                                        raise RuntimeError(
                                            tr(
                                                "Kontrola liczby zapisanych "
                                                "kafelków nie powiodła się."
                                            )
                                        )
                                    checksum = sha256(written[0]).hexdigest()
                                attempts += 1
                                if attempts > 1:
                                    stats["repair_attempts"] += 1
                                    stats["repaired"] += 1
                                ledger.execute(
                                    'UPDATE tiles SET status=?,attempts=?,reason="",'
                                    "total_attempts=total_attempts+1,png_sha256=? "
                                    "WHERE zoom=? AND col=? AND row=?",
                                    (
                                        "empty" if empty else "saved",
                                        attempts,
                                        checksum,
                                        zoom,
                                        column,
                                        row,
                                    ),
                                )
                                ledger.commit()
                                stats["timing_seconds"]["write"] += (
                                    time.monotonic() - started
                                )
                                if gate:
                                    gate.outcome()
                                failures_in_a_row = 0
                                break
                            except HostDeferred:
                                deferred = True
                                break
                            except InterruptedError:
                                raise
                            except (RuntimeError, TimeoutError) as error:
                                attempts += 1
                                if attempts > 1:
                                    stats["repair_attempts"] += 1
                                permanent = getattr(error, "status", None) in (
                                    401,
                                    403,
                                    404,
                                    407,
                                )
                                retryable = not permanent and attempts < attempt_limit
                                ledger.execute(
                                    "UPDATE tiles SET status=?,attempts=?,reason=?,"
                                    "total_attempts=total_attempts+1 "
                                    "WHERE zoom=? AND col=? AND row=?",
                                    (
                                        "retry" if retryable else "failed",
                                        attempts,
                                        str(error),
                                        zoom,
                                        column,
                                        row,
                                    ),
                                )
                                ledger.commit()
                                if gate:
                                    gate.outcome(error, recoverable=retryable)
                                if getattr(error, "status", None) == 407:
                                    # Repeating the same rejected proxy credentials
                                    # cannot retrieve another tile of this map.
                                    stop_http_status = 407
                                    break
                                if legacy_retries:
                                    failures_in_a_row += 1
                                    if (
                                        str(error).startswith("[HTTP 429]")
                                        or getattr(error, "status", None) == 429
                                    ):
                                        stop_http_status = 429
                                    stopped_early = failures_in_a_row >= 5
                                    break
                                if layer.dataProvider() is not None:
                                    layer.dataProvider().reloadData()
                                overload = getattr(error, "status", None) in (
                                    429,
                                    503,
                                ) or isinstance(error, TimeoutError)
                                if not overload or not retryable:
                                    break
                        completed += 1
                        if deferred or stop_http_status or stopped_early:
                            break
                finally:
                    cursor.close()
                    started = time.monotonic()
                    dataset.FlushCache()
                    dataset = None
                    stats["timing_seconds"]["write"] += time.monotonic() - started
                counts = dict(
                    ledger.execute(
                        "SELECT status,count(*) FROM tiles "
                        "WHERE zoom=? GROUP BY status",
                        (zoom,),
                    )
                )
                progress(
                    tr(
                        "{0}: zoom {1} zakończony — zapisane {2}, puste {3}, "
                        "błędne {4} fragmenty."
                    ).format(
                        layer.name(),
                        zoom,
                        counts.get("saved", 0),
                        counts.get("empty", 0),
                        sum(
                            v for k, v in counts.items() if k not in ("saved", "empty")
                        ),
                    )
                )
        stats["deferred"] = deferred
        stats["stopped_early"] = (
            deferred or stop_http_status is not None or stopped_early
        )
        if stop_http_status is not None:
            stats["stop_http_status"] = stop_http_status
        for level in reversed(levels):
            zoom = level["zoom"]
            counts = dict(
                ledger.execute(
                    "SELECT status,count(*) FROM tiles WHERE zoom=? GROUP BY status",
                    (zoom,),
                )
            )
            attempted = ledger.execute(
                "SELECT coalesce(sum(total_attempts),0) FROM tiles WHERE zoom=?",
                (zoom,),
            ).fetchone()[0]
            stats["levels"].append(
                {
                    "zoom": zoom,
                    "attempted": attempted,
                    "nonempty": counts.get("saved", 0),
                    "empty": counts.get("empty", 0),
                    "failed": sum(
                        v for k, v in counts.items() if k not in ("saved", "empty")
                    ),
                }
            )
        missing_reason = (
            tr("Proxy odrzuciło uwierzytelnianie. Sprawdź konfigurację proxy w QGIS.")
            if stop_http_status == 407
            else tr("Serwer odłożony do późniejszej próby.")
        )
        stats["failures"] = [
            dict(
                zoom=z,
                column=c,
                row=r,
                reason=reason or missing_reason,
            )
            for z, c, r, reason in ledger.execute(
                (
                    "SELECT zoom,col,row,reason FROM tiles WHERE status NOT "
                    'IN ("saved","empty") LIMIT 20'
                )
            )
        ]


def write_raster_data(
    layer, project, area, area_crs, staging, table, cancelled, progress
):
    """Preserve numerical/local GDAL rasters in lossless GeoTIFF, with a cutline."""
    resources = Path(staging) / tr("zasoby")
    resources.mkdir(exist_ok=True)
    target = resources / (table + ".tif")
    source = output = None
    try:
        with gdal.ExceptionMgr():
            uri = layer.source().split("|option:")
            source = gdal.OpenEx(uri[0], gdal.OF_RASTER, open_options=uri[1:])
            if source is None:
                raise RuntimeError(
                    tr("GDAL nie może odczytać oryginalnych wartości rastra.")
                )
            numerical = any(
                source.GetRasterBand(i).DataType != gdal.GDT_Byte
                for i in range(1, source.RasterCount + 1)
            )
            if (
                numerical
                and source.GetRasterBand(source.RasterCount).GetColorInterpretation()
                == gdal.GCI_AlphaBand
            ):
                raise RuntimeError(
                    tr(
                        (
                            "Wielobitowy kanał przezroczystości wymaga zachowania "
                            "wyglądu przez renderer QGIS."
                        )
                    )
                )
            transform = source.GetGeoTransform()
            if transform[2] or transform[4] or transform[1] <= 0 or transform[5] >= 0:
                raise RuntimeError(
                    tr(
                        (
                            "Raster ma obróconą lub nietypową siatkę; potrzebny jest "
                            "zapis obrazu."
                        )
                    )
                )
            mask = QgsGeometry(area)
            if layer.crs() != area_crs:
                mask.transform(QgsCoordinateTransform(area_crs, layer.crs(), project))
            box = mask.boundingBox()
            left = max(0, math.floor((box.xMinimum() - transform[0]) / transform[1]))
            right = min(
                source.RasterXSize,
                math.ceil((box.xMaximum() - transform[0]) / transform[1]),
            )
            top = max(0, math.floor((box.yMaximum() - transform[3]) / transform[5]))
            bottom = min(
                source.RasterYSize,
                math.ceil((box.yMinimum() - transform[3]) / transform[5]),
            )
            if right <= left or bottom <= top:
                raise RuntimeError(tr("Raster nie przecina obszaru archiwizacji."))
            aligned = (
                transform[0] + left * transform[1],
                transform[3] + bottom * transform[5],
                transform[0] + right * transform[1],
                transform[3] + top * transform[5],
            )
            with TemporaryDirectory(prefix=".cutline-", dir=staging) as temporary:
                cutline = Path(temporary) / "area.geojson"
                cutline.write_text(
                    json.dumps(
                        {
                            "type": "FeatureCollection",
                            "crs": {
                                "type": "name",
                                "properties": {"name": layer.crs().toWkt()},
                            },
                            "features": [
                                {
                                    "type": "Feature",
                                    "properties": {},
                                    "geometry": json.loads(mask.asJson()),
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

                def callback(fraction, message, data):
                    progress(
                        tr("{0}: zapis wartości rastra {1:.0%}").format(
                            layer.name(), fraction
                        )
                    )
                    return not cancelled()

                warp_target = Path(temporary) / "warped.tif" if numerical else target
                output = gdal.Warp(
                    str(warp_target),
                    source,
                    format="GTiff",
                    srcSRS=layer.crs().toWkt(Qgis.CrsWktVariant.Wkt2_2019),
                    dstSRS=layer.crs().toWkt(Qgis.CrsWktVariant.Wkt2_2019),
                    outputBounds=aligned,
                    xRes=transform[1],
                    yRes=-transform[5],
                    cutlineDSName=str(cutline),
                    dstAlpha=True,
                    resampleAlg="near",
                    warpOptions=["DST_ALPHA_MAX=255"],
                    creationOptions=[
                        "TILED=YES",
                        "COMPRESS=DEFLATE",
                        "ZLEVEL=9",
                        "BIGTIFF=IF_SAFER",
                        "SPARSE_OK=YES",
                    ],
                    callback=callback,
                )
                if cancelled():
                    raise InterruptedError(tr("Przerwano zapis rastra."))
                if output is None:
                    raise RuntimeError(
                        tr("Nie udało się zapisać oryginalnych wartości rastra.")
                    )
                output.FlushCache()
                band_count = output.RasterCount
                if numerical:
                    # QGIS expects an 8-bit opacity mask even for UInt16/Float32
                    # data. Use GDAL's standard internal mask, keeping values intact.
                    with gdal.config_option("GDAL_TIFF_INTERNAL_MASK", "YES"):
                        converted = gdal.Translate(
                            str(target),
                            output,
                            bandList=list(range(1, band_count)),
                            maskBand=band_count,
                            creationOptions=[
                                "TILED=YES",
                                "COMPRESS=DEFLATE",
                                "ZLEVEL=9",
                                "BIGTIFF=IF_SAFER",
                                "SPARSE_OK=YES",
                            ],
                            callback=callback,
                        )
                        if cancelled():
                            converted = None
                            raise InterruptedError(tr("Przerwano zapis rastra."))
                        if converted is None:
                            raise RuntimeError(
                                tr("Nie udało się zapisać maski lokalnego rastra.")
                            )
                        converted.FlushCache()
                        converted = None
                output = None
            output = gdal.Open(str(target), gdal.GA_Update)
            if output.RasterXSize != right - left or output.RasterYSize != bottom - top:
                raise RuntimeError(
                    tr("Kontrola wymiarów lokalnego rastra nie powiodła się.")
                )
            overview_factors = []
            factor = 2
            while (
                math.ceil(max(output.RasterXSize, output.RasterYSize) / factor)
                >= TILE_SIZE
            ):
                overview_factors.append(factor)
                factor *= 2

            def overview_progress(fraction, message, data):
                progress(
                    tr("{0}: budowanie piramid rastra {1:.0%}").format(
                        layer.name(), fraction
                    )
                )
                return not cancelled()

            if overview_factors:
                try:
                    with gdal.config_options(
                        {"COMPRESS_OVERVIEW": "DEFLATE", "ZLEVEL_OVERVIEW": "9"}
                    ):
                        result = output.BuildOverviews(
                            "NEAREST", overview_factors, callback=overview_progress
                        )
                except RuntimeError:
                    if cancelled():
                        raise InterruptedError(tr("Przerwano zapis rastra.")) from None
                    raise
                if cancelled():
                    raise InterruptedError(tr("Przerwano zapis rastra."))
                if result != 0:
                    raise RuntimeError(tr("Nie udało się zbudować piramid rastra."))
                output.FlushCache()
            return {
                "status": "saved",
                "method": "raster_data",
                "crs": layer.crs().authid(),
                "local_source": "./" + tr("zasoby") + "/" + target.name,
                "local_provider": "gdal",
                "alpha_band": band_count,
                "raster_size": [output.RasterXSize, output.RasterYSize],
                "overview_factors": overview_factors,
                "overview_status": "built" if overview_factors else "small_raster",
                "reason": tr(
                    "Zapisano oryginalne wartości rastra i maskę w bezstratnym GeoTIFF."
                ),
            }
    except Exception:
        output = None
        if target.exists():
            target.unlink()
        raise
    finally:
        source = output = None


def _empty_zoom_overviews(database, table, stats):
    """Expose successfully empty zooms to GDAL without resampling another zoom."""
    quoted_table = QgsSqliteUtils.quotedIdentifier(table)
    previous = set(stats.get("empty_zoom_placeholders", []))
    placeholders = []
    empty_zooms = [
        level["zoom"]
        for level in stats["levels"]
        if level["nonempty"] == 0
        and level["empty"] > 0
        and level["failed"] == 0
        and not level.get("pending", 0)
        and level.get("total", level["empty"]) == level["empty"]
    ]
    if empty_zooms:
        with closing(sqlite3.connect(database)) as connection:
            missing = []
            for zoom in empty_zooms:
                exists = connection.execute(
                    # Quoted identifier; values bound.
                    f"SELECT 1 FROM {quoted_table} "  # nosec B608
                    "WHERE zoom_level=? LIMIT 1",
                    (zoom,),
                ).fetchone()
                if not exists:
                    missing.append(zoom)
                elif zoom in previous:
                    placeholders.append(zoom)
            if missing:
                # MEM -> PNG uses native GDAL encoding and keeps exact RGBA/DEFLATE9.
                with TemporaryDirectory(
                    prefix=".empty-zoom-", dir=Path(database).parent
                ) as temporary:
                    path = Path(temporary) / "empty.png"
                    image = gdal.GetDriverByName("MEM").Create(
                        "", TILE_SIZE, TILE_SIZE, 4, gdal.GDT_Byte
                    )
                    for band, interpretation in enumerate(
                        (
                            gdal.GCI_RedBand,
                            gdal.GCI_GreenBand,
                            gdal.GCI_BlueBand,
                            gdal.GCI_AlphaBand,
                        ),
                        1,
                    ):
                        image.GetRasterBand(band).SetColorInterpretation(interpretation)
                    png = gdal.GetDriverByName("PNG").CreateCopy(
                        str(path), image, options=["ZLEVEL=9"]
                    )
                    png.FlushCache()
                    png = image = None
                    payload = path.read_bytes()
                with connection:
                    for zoom in missing:
                        connection.execute(
                            # Quoted identifier; values bound.
                            f"INSERT INTO {quoted_table} "  # nosec B608
                            "(zoom_level,tile_column,tile_row,tile_data) "
                            "VALUES (?,0,0,?)",
                            (zoom, payload),
                        )
                placeholders.extend(missing)
    stats["empty_zoom_placeholders"] = sorted(placeholders)
    return stats["empty_zoom_placeholders"]
