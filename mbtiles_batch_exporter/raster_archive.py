# -*- coding: utf-8 -*-
"""Bounded-memory raster capture using QGIS rendering and GDAL GeoPackage."""
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import time

from osgeo import gdal
from qgis.PyQt.QtCore import QCoreApplication, QPointF, QSize, QThread, Qt, QUrl, QUrlQuery
from qgis.PyQt.QtGui import QImage, QPainter, QPainterPath, QPolygonF
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDataSourceUri, QgsExpressionContext,
    QgsExpressionContextUtils, QgsGeometry, QgsMapRendererSequentialJob,
    QgsMapSettings, QgsNetworkAccessManager, QgsNetworkReplyContent, QgsNetworkRequestParameters,
    QgsPointXY, QgsRectangle, QgsScaleCalculator, QgsVectorLayer,
)


TILE_SIZE = 256
PNG_OPTIONS = ['TILE_FORMAT=PNG', 'ZLEVEL=9']
RENDER_TIMEOUT = 60


def zoom_levels(project, area, area_crs, zoom_min, zoom_max):
    """XYZ-equivalent resolution at the AOI center, expressed in project units."""
    if not (isinstance(zoom_min, int) and isinstance(zoom_max, int)
            and 0 <= zoom_min <= zoom_max <= 24):
        raise ValueError('Wybierz zoom od 0 do 24; minimum nie może przekraczać maksimum.')
    crs = project.crs()
    if not crs.isValid() or not area_crs.isValid() or area.isEmpty():
        raise ValueError('Nie można obliczyć skali bez poprawnego obszaru i układu współrzędnych.')
    mercator = QgsCoordinateReferenceSystem('EPSG:3857')
    center = area.boundingBox().center()
    center = QgsCoordinateTransform(area_crs, mercator, project).transform(center)
    if abs(center.y()) > 20037508.342789244:
        raise ValueError('Wybrany obszar znajduje się poza zakresem zoomów XYZ (obszary polarne).')
    transform = QgsCoordinateTransform(mercator, crs, project)
    origin = transform.transform(center)
    east = transform.transform(QgsPointXY(center.x() + 1, center.y()))
    local_factor = math.hypot(east.x() - origin.x(), east.y() - origin.y())
    if not math.isfinite(local_factor) or local_factor <= 0:
        raise ValueError('Nie udało się przeliczyć rozdzielczości do układu projektu.')
    calculator = QgsScaleCalculator(96)
    calculator.setMapUnits(crs.mapUnits())
    levels = []
    for zoom in range(zoom_min, zoom_max + 1):
        resolution = 156543.03392804097 * local_factor / 2 ** zoom
        half = resolution * TILE_SIZE / 2
        rectangle = QgsRectangle(origin.x() - half, origin.y() - half,
                                 origin.x() + half, origin.y() + half)
        levels.append({'zoom': zoom, 'resolution': resolution,
                       'scale': calculator.calculate(rectangle, TILE_SIZE)})
    return levels


def intersecting_tiles(area, x0, y0, resolution, width, height):
    """Prune rectangular grid regions instead of scanning a long corridor's bbox."""
    engine = QgsGeometry.createGeometryEngine(area.constGet())
    engine.prepareGeometry()
    pending = [(0, 0, math.ceil(width / TILE_SIZE), math.ceil(height / TILE_SIZE))]
    while pending:
        left, top, right, bottom = pending.pop()
        bounds = QgsRectangle(x0 + left * TILE_SIZE * resolution,
                              y0 - bottom * TILE_SIZE * resolution,
                              x0 + right * TILE_SIZE * resolution,
                              y0 - top * TILE_SIZE * resolution)
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
    settings.setBackgroundColor(Qt.transparent)
    settings.setOutputDpi(96)
    settings.setOutputSize(QSize(width, height))
    settings.setExtent(bounds)
    settings.setLabelingEngineSettings(project.labelingEngineSettings())
    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    # globalProjectLayerScopes normally uses the singleton; archives can use another project.
    context.appendScope(QgsExpressionContextUtils.projectScope(project))
    settings.setExpressionContext(context)
    job = QgsMapRendererSequentialJob(settings)
    # WMS providers may return a transparent image on HTTP errors without adding
    # a renderer error. Observe new requests to this source during this job only.
    source_uri = QgsDataSourceUri()
    source_uri.setEncodedUri(layer.source())
    service = QUrl(source_uri.param('url'))
    network = QgsNetworkAccessManager.instance()
    requests, network_errors = set(), []

    def request_created(request):
        if service.host() and request.request().url().host() == service.host():
            requests.add(request.requestId())

    def reply_finished(reply):
        if reply.requestId() not in requests:
            return
        content_type = bytes(reply.rawHeader(b'Content-Type')).decode('ascii', errors='replace').lower()
        operation = QUrlQuery(reply.request().url()).queryItemValue('REQUEST').lower()
        if reply.error() != QNetworkReply.NoError or (operation == 'getmap' and 'xml' in content_type):
            network_errors.append(reply.attribute(QNetworkRequest.HttpStatusCodeAttribute))

    network.requestAboutToBeCreated[QgsNetworkRequestParameters].connect(request_created)
    network.finished[QgsNetworkReplyContent].connect(reply_finished)
    deadline = time.monotonic() + RENDER_TIMEOUT
    timed_out = False
    job.start()
    try:
        while job.isActive():
            QCoreApplication.processEvents()
            if cancelled() or time.monotonic() > deadline:
                timed_out = not cancelled()
                job.cancelWithoutBlocking()
                # Keep renderer and layer alive until the native job finishes cancellation.
                job.waitForFinished()
                break
            QThread.msleep(10)
        if cancelled():
            raise InterruptedError('Przerwano pobieranie obrazu.')
        if timed_out:
            raise TimeoutError('Przekroczono czas pobierania fragmentu mapy.')
        QCoreApplication.processEvents()
        if network_errors:
            raise RuntimeError('Usługa mapowa zwróciła błąd sieciowy lub odpowiedź błędu WMS.')
        if job.errors():
            raise RuntimeError('Renderer QGIS zgłosił błąd pobierania lub rysowania warstwy.')
        result = job.renderedImage()
        if result.isNull():
            raise RuntimeError('QGIS nie zwrócił obrazu mapy.')
        return result
    finally:
        if job.isActive():
            job.cancel()
        network.requestAboutToBeCreated[QgsNetworkRequestParameters].disconnect(request_created)
        network.finished[QgsNetworkReplyContent].disconnect(reply_finished)


def _render_tile(layer, project, bounds, resolution, size, cancelled, progress, counters):
    # A small gutter avoids cutting strokes at tile edges. Output remains 256px.
    gutter = 16
    expanded = QgsRectangle(bounds)
    expanded.grow(gutter * resolution)
    for attempt in range(3):
        if cancelled():
            raise InterruptedError('Przerwano pobieranie obrazu.')
        try:
            image = _render_image(layer, project, expanded, size + 2 * gutter,
                                  size + 2 * gutter, cancelled, progress)
            return image.copy(gutter, gutter, size, size)
        except InterruptedError:
            raise
        except (RuntimeError, TimeoutError):
            # Some providers cache the empty image produced by a failed request.
            # Invalidate only the disposable clone before trying again.
            if layer.dataProvider() is not None:
                layer.dataProvider().reloadData()
            if attempt < 2:
                counters['retries'] += 1
                progress(f'{layer.name()}: ponowienie pobierania fragmentu ({attempt + 1}/2)…')
    if size <= 128:
        raise RuntimeError('Pobieranie nie powiodło się także po ponowieniach i podziale fragmentu.')
    counters['subdivisions'] += 1
    result = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    try:
        half = size // 2
        for row in range(2):
            for column in range(2):
                x = bounds.xMinimum() + column * half * resolution
                y = bounds.yMaximum() - row * half * resolution
                part = QgsRectangle(x, y - half * resolution, x + half * resolution, y)
                image = _render_tile(layer, project, part, resolution, half, cancelled, progress, counters)
                painter.drawImage(column * half, row * half, image)
    finally:
        painter.end()
    return result


def _mask_image(image, area, bounds, resolution):
    clipped = area.intersection(QgsGeometry.fromRect(bounds))
    if clipped.lastError() or (not clipped.isEmpty() and not clipped.isGeosValid()):
        raise RuntimeError('Nie udało się wyznaczyć maski fragmentu mapy.')
    mask = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
    mask.fill(Qt.transparent)
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    # A tile touching only a boundary may intersect as a line/point, not a polygon.
    if not clipped.isEmpty() and clipped.area() > 0:
        polygons = clipped.asMultiPolygon() if clipped.isMultipart() else [clipped.asPolygon()]
        for polygon in polygons:
            for ring in polygon:
                path.addPolygon(QPolygonF([
                    QPointF((point.x() - bounds.xMinimum()) / resolution,
                            (bounds.yMaximum() - point.y()) / resolution) for point in ring
                ]))
    painter = QPainter(mask)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillPath(path, Qt.white)
    painter.end()
    painter = QPainter(image)
    painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, mask)
    painter.end()
    return image.convertToFormat(QImage.Format_RGBA8888)


def write_rendered_raster(layer, project, area, area_crs, database, table, levels, cancelled, progress):
    """One sparse RGBA tile table; each zoom is rendered independently."""
    mask = QgsGeometry(area)
    if area_crs != project.crs():
        mask.transform(QgsCoordinateTransform(area_crs, project.crs(), project))
    bounds = mask.boundingBox()
    finest = levels[-1]['resolution']
    width = math.ceil(bounds.width() / (finest * TILE_SIZE)) * TILE_SIZE
    height = math.ceil(bounds.height() / (finest * TILE_SIZE)) * TILE_SIZE
    if not (0 < width < 2 ** 31 and 0 < height < 2 ** 31):
        raise ValueError('Rozmiar rastra przekracza limit formatu. Zmniejsz obszar lub maksymalny zoom.')
    x0, y0 = bounds.xMinimum(), bounds.yMaximum()
    clone = layer.clone()
    if clone is None or not clone.isValid():
        raise RuntimeError('Nie można przygotować warstwy do zapisu obrazu.')
    if isinstance(layer, QgsVectorLayer) and layer.isEditable():
        # clone() copies provider data, but omits unsaved edits. Replay just the
        # edit buffer on the disposable clone; never commit to the real provider.
        edits = layer.editBuffer()
        if not clone.startEditing():
            raise RuntimeError('Nie można uwzględnić niezapisanych edycji w obrazie.')
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
            raise RuntimeError('Nie udało się uwzględnić wszystkich niezapisanych edycji w obrazie.')
    clone.setScaleBasedVisibility(False)
    # Blend against other layers in the archive, not against a transparent capture canvas.
    clone.setBlendMode(QPainter.CompositionMode_SourceOver)
    dataset = None
    stats = {'retries': 0, 'subdivisions': 0, 'levels': [], 'failures': [], 'stopped_early': False}
    try:
        with gdal.ExceptionMgr():
            dataset = gdal.GetDriverByName('GPKG').Create(
                str(database), width, height, 4, gdal.GDT_Byte,
                options=['RASTER_TABLE=' + table, 'APPEND_SUBDATASET=YES', 'BLOCKSIZE=256'] + PNG_OPTIONS,
            )
            dataset.SetProjection(project.crs().toWkt(Qgis.CrsWktVariant.Wkt2_2019))
            dataset.SetGeoTransform([x0, finest, 0, y0, 0, -finest])
            dataset.FlushCache()
            dataset = None
            # GDAL creates standard empty tile matrices. Specify only requested zooms,
            # including coarse zooms for tiny AOIs, without scanning a huge empty raster.
            with closing(sqlite3.connect(database)) as connection:
                with connection:
                    connection.execute('DELETE FROM gpkg_tile_matrix WHERE table_name=?', (table,))
                    connection.executemany('INSERT INTO gpkg_tile_matrix VALUES (?,?,?,?,?,?,?,?)', [
                        (table, level['zoom'], math.ceil(width * finest / (TILE_SIZE * level['resolution'])),
                         math.ceil(height * finest / (TILE_SIZE * level['resolution'])),
                         TILE_SIZE, TILE_SIZE, level['resolution'], level['resolution']) for level in levels
                    ])
            failures_in_a_row = 0
            for level in reversed(levels):
                zoom, resolution = level['zoom'], level['resolution']
                level_stats = dict(zoom=zoom, attempted=0, nonempty=0, empty=0, failed=0)
                stats['levels'].append(level_stats)
                dataset = gdal.OpenEx(str(database), gdal.OF_RASTER | gdal.OF_UPDATE,
                                     open_options=[f'TABLE={table}', f'ZOOM_LEVEL={zoom}', 'BAND_COUNT=4'] + PNG_OPTIONS)
                for column, row in intersecting_tiles(mask, x0, y0, resolution, dataset.RasterXSize, dataset.RasterYSize):
                    progress(f'{layer.name()} — zoom {zoom}, fragment {level_stats["attempted"] + 1}')
                    if cancelled():
                        raise InterruptedError('Przerwano pobieranie obrazu.')
                    level_stats['attempted'] += 1
                    x, y = x0 + column * TILE_SIZE * resolution, y0 - row * TILE_SIZE * resolution
                    tile_bounds = QgsRectangle(x, y - TILE_SIZE * resolution, x + TILE_SIZE * resolution, y)
                    try:
                        image = _render_tile(clone, project, tile_bounds, resolution, TILE_SIZE,
                                             cancelled, progress, stats)
                    except InterruptedError:
                        raise
                    except (RuntimeError, TimeoutError) as error:
                        level_stats['failed'] += 1
                        failures_in_a_row += 1
                        if len(stats['failures']) < 20:
                            stats['failures'].append({'zoom': zoom, 'column': column, 'row': row, 'reason': str(error)})
                        if failures_in_a_row >= 5:
                            stats['stopped_early'] = True
                            break
                        continue
                    failures_in_a_row = 0
                    image = _mask_image(image, mask, tile_bounds, resolution)
                    # Last overview tiles can be smaller than 256 pixels at dataset edges.
                    w = min(TILE_SIZE, dataset.RasterXSize - column * TILE_SIZE)
                    h = min(TILE_SIZE, dataset.RasterYSize - row * TILE_SIZE)
                    image = image.copy(0, 0, w, h)
                    pixels = image.constBits().asstring(image.sizeInBytes())
                    if not any(pixels[3::4]):
                        level_stats['empty'] += 1
                        continue
                    dataset.WriteRaster(column * TILE_SIZE, row * TILE_SIZE, w, h, pixels,
                                        band_list=[1, 2, 3, 4], buf_pixel_space=4,
                                        buf_line_space=image.bytesPerLine(), buf_band_space=1)
                    level_stats['nonempty'] += 1
                dataset.FlushCache()
                dataset = None
                if stats['stopped_early']:
                    break
            if cancelled():
                raise InterruptedError('Przerwano pobieranie obrazu.')
            with closing(sqlite3.connect(database)) as connection:
                tiles = connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            nonempty = sum(level['nonempty'] for level in stats['levels'])
            if tiles != nonempty:
                raise RuntimeError('Kontrola liczby zapisanych kafelków nie powiodła się.')
            for level in levels:
                dataset = gdal.OpenEx(str(database), gdal.OF_RASTER,
                                     open_options=[f'TABLE={table}', f'ZOOM_LEVEL={level["zoom"]}'])
                if dataset.RasterCount != 4 or not math.isclose(dataset.GetGeoTransform()[1], level['resolution']):
                    raise RuntimeError('Nieprawidłowa rozdzielczość lub kanały zapisanego obrazu.')
                dataset = None
    finally:
        dataset = None
        clone = None
    failed = any(level['failed'] for level in stats['levels']) or stats['stopped_early']
    blank = any(level['nonempty'] == 0 for level in stats['levels'])
    status = ('partial' if nonempty else 'failed') if failed else 'empty' if blank else 'saved'
    result = {
        'status': status, 'method': 'raster_render', 'crs': project.crs().authid(),
        'local_source': f'./dane.gpkg|option:TABLE={table}|option:ZOOM_LEVEL={levels[-1]["zoom"]}',
        'local_provider': 'gdal', 'table': table, 'tile_count': nonempty,
        'raster': stats, 'png': {'format': 'PNG', 'zlevel': 9, 'rgba': True},
        'reason': ('Nie udało się pobrać obrazu; ponowienia i mniejsze fragmenty również zawiodły.' if status == 'failed' else
                   'Obraz częściowy: nie wszystkie fragmenty udało się pobrać.' if failed else
                   'Co najmniej jeden zoom jest całkowicie przezroczysty — wymaga sprawdzenia.' if blank else
                   'Zapisano obraz z przezroczystością; każdy zoom pobrano osobno.'),
    }
    if status == 'failed':
        result.pop('local_source')
    return result


def write_raster_data(layer, project, area, area_crs, staging, table, cancelled, progress):
    """Preserve numerical/local GDAL rasters in lossless GeoTIFF, with a cutline."""
    resources = Path(staging) / 'zasoby'
    resources.mkdir(exist_ok=True)
    target = resources / (table + '.tif')
    source = output = None
    try:
        with gdal.ExceptionMgr():
            uri = layer.source().split('|option:')
            source = gdal.OpenEx(uri[0], gdal.OF_RASTER, open_options=uri[1:])
            if source is None:
                raise RuntimeError('GDAL nie może odczytać oryginalnych wartości rastra.')
            numerical = any(source.GetRasterBand(i).DataType != gdal.GDT_Byte for i in range(1, source.RasterCount + 1))
            if numerical and source.GetRasterBand(source.RasterCount).GetColorInterpretation() == gdal.GCI_AlphaBand:
                raise RuntimeError('Wielobitowy kanał przezroczystości wymaga zachowania wyglądu przez renderer QGIS.')
            transform = source.GetGeoTransform()
            if transform[2] or transform[4] or transform[1] <= 0 or transform[5] >= 0:
                raise RuntimeError('Raster ma obróconą lub nietypową siatkę; potrzebny jest zapis obrazu.')
            mask = QgsGeometry(area)
            if layer.crs() != area_crs:
                mask.transform(QgsCoordinateTransform(area_crs, layer.crs(), project))
            box = mask.boundingBox()
            left = max(0, math.floor((box.xMinimum() - transform[0]) / transform[1]))
            right = min(source.RasterXSize, math.ceil((box.xMaximum() - transform[0]) / transform[1]))
            top = max(0, math.floor((box.yMaximum() - transform[3]) / transform[5]))
            bottom = min(source.RasterYSize, math.ceil((box.yMinimum() - transform[3]) / transform[5]))
            if right <= left or bottom <= top:
                raise RuntimeError('Raster nie przecina obszaru archiwizacji.')
            aligned = (transform[0] + left * transform[1], transform[3] + bottom * transform[5],
                       transform[0] + right * transform[1], transform[3] + top * transform[5])
            with TemporaryDirectory(prefix='.cutline-', dir=staging) as temporary:
                cutline = Path(temporary) / 'area.geojson'
                cutline.write_text(json.dumps({
                    'type': 'FeatureCollection',
                    'crs': {'type': 'name', 'properties': {'name': layer.crs().toWkt()}},
                    'features': [{'type': 'Feature', 'properties': {}, 'geometry': json.loads(mask.asJson())}],
                }), encoding='utf-8')

                def callback(fraction, message, data):
                    progress(f'{layer.name()}: zapis wartości rastra {fraction:.0%}')
                    return not cancelled()

                warp_target = Path(temporary) / 'warped.tif' if numerical else target
                output = gdal.Warp(str(warp_target), source, format='GTiff',
                                   srcSRS=layer.crs().toWkt(Qgis.CrsWktVariant.Wkt2_2019),
                                   dstSRS=layer.crs().toWkt(Qgis.CrsWktVariant.Wkt2_2019),
                                   outputBounds=aligned, xRes=transform[1], yRes=-transform[5],
                                   cutlineDSName=str(cutline), dstAlpha=True, resampleAlg='near',
                                   warpOptions=['DST_ALPHA_MAX=255'],
                                   creationOptions=['TILED=YES', 'COMPRESS=DEFLATE', 'ZLEVEL=9',
                                                    'BIGTIFF=IF_SAFER', 'SPARSE_OK=YES'], callback=callback)
                if cancelled():
                    raise InterruptedError('Przerwano zapis rastra.')
                if output is None:
                    raise RuntimeError('Nie udało się zapisać oryginalnych wartości rastra.')
                output.FlushCache()
                band_count = output.RasterCount
                if numerical:
                    # QGIS expects an 8-bit opacity mask even for UInt16/Float32
                    # data. Use GDAL's standard internal mask, keeping values intact.
                    with gdal.config_option('GDAL_TIFF_INTERNAL_MASK', 'YES'):
                        converted = gdal.Translate(
                            str(target), output, bandList=list(range(1, band_count)), maskBand=band_count,
                            creationOptions=['TILED=YES', 'COMPRESS=DEFLATE', 'ZLEVEL=9',
                                             'BIGTIFF=IF_SAFER', 'SPARSE_OK=YES'], callback=callback,
                        )
                        if cancelled():
                            converted = None
                            raise InterruptedError('Przerwano zapis rastra.')
                        if converted is None:
                            raise RuntimeError('Nie udało się zapisać maski lokalnego rastra.')
                        converted.FlushCache()
                        converted = None
                output = None
            output = gdal.Open(str(target))
            if output.RasterXSize != right - left or output.RasterYSize != bottom - top:
                raise RuntimeError('Kontrola wymiarów lokalnego rastra nie powiodła się.')
            return {'status': 'saved', 'method': 'raster_data', 'crs': layer.crs().authid(),
                    'local_source': f'./zasoby/{target.name}', 'local_provider': 'gdal',
                    'alpha_band': band_count, 'reason': 'Zapisano oryginalne wartości rastra i maskę w bezstratnym GeoTIFF.'}
    except Exception:
        output = None
        if target.exists():
            target.unlink()
        raise
    finally:
        source = output = None
