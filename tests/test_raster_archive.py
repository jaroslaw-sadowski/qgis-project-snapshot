"""Real QGIS/GDAL raster tests; WMS uses a disposable loopback HTTP server."""
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import struct
from tempfile import TemporaryDirectory
from threading import Lock, Thread
import time
import tracemalloc
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from osgeo import gdal
from qgis.PyQt.QtCore import QBuffer, QIODevice
from qgis.PyQt.QtGui import QColor, QImage
from qgis.core import (
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsDataSourceUri, QgsFeature, QgsFillSymbol,
    QgsGeometry, QgsProject, QgsRasterLayer, QgsRectangle, QgsVectorLayer,
)

from mbtiles_batch_exporter.archive import create_archive, _remove_table
from mbtiles_batch_exporter.raster_archive import (
    _mask_image, _render_image, intersecting_tiles, write_rendered_raster, zoom_levels,
)


APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()


class RasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.project = QgsProject()
        self.crs = QgsCoordinateReferenceSystem('EPSG:2180')
        self.project.setCrs(self.crs)
        self.area = QgsGeometry.fromWkt(
            'POLYGON((500000 500000,500512 500000,500512 500512,500000 500512,500000 500000),'
            '(500180 500180,500180 500330,500330 500330,500330 500180,500180 500180))')
        self.layer = QgsVectorLayer('Polygon?crs=EPSG:2180', 'Półprzezroczysta', 'memory')
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(499900, 499900, 500600, 500600)))
        self.layer.dataProvider().addFeatures([feature])
        self.layer.updateExtents()
        self.layer.renderer().setSymbol(QgsFillSymbol.createSimple({'color': '30,100,170,128', 'outline_style': 'no'}))
        self.project.addMapLayer(self.layer, False)
        self.group = self.project.layerTreeRoot().addGroup('Ukryta grupa')
        self.group.addLayer(self.layer)
        self.group.setItemVisibilityChecked(False)
        self.database = self.folder / 'dane.gpkg'

    def tearDown(self):
        self.project.clear()
        self.temp.cleanup()

    def render(self, **kwargs):
        return write_rendered_raster(self.layer, self.project, self.area, self.crs,
                                     self.database, 'map', zoom_levels(self.project, self.area, self.crs, 16, 17),
                                     kwargs.get('cancelled', lambda: False), kwargs.get('progress', lambda text: None))

    def test_rgba_mask_holes_compression_and_native_epsg(self):
        self.layer.setScaleBasedVisibility(True)
        self.layer.setMinimumScale(1)
        record = self.render()
        self.assertEqual(record['status'], 'saved')
        self.assertFalse(self.group.itemVisibilityChecked())
        self.assertTrue(self.layer.hasScaleBasedVisibility())
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT srs_id FROM gpkg_contents').fetchone()[0], 2180)
            self.assertEqual([r[0] for r in db.execute('SELECT zoom_level FROM gpkg_tile_matrix ORDER BY zoom_level')], [16, 17])
            tiles = db.execute('SELECT tile_data FROM map').fetchall()
        self.assertTrue(tiles)
        for (payload,) in tiles:
            self.assertEqual(payload[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(payload[25], 6)  # RGBA, no palette quantization.
            index = 8
            while payload[index + 4:index + 8] != b'IDAT':
                index += 12 + struct.unpack('>I', payload[index:index + 4])[0]
            self.assertEqual(payload[index + 9] >> 6, 3)  # zlib maximum-compression FLEVEL.
        ds = gdal.OpenEx(str(self.database), gdal.OF_RASTER, open_options=['TABLE=map', 'ZOOM_LEVEL=17'])
        transform = ds.GetGeoTransform()

        def alpha_at(x, y):
            column, row = int((x - transform[0]) / transform[1]), int((y - transform[3]) / transform[5])
            return ds.GetRasterBand(4).ReadRaster(column, row, 1, 1)[0]

        self.assertEqual(alpha_at(500100, 500100), 128)
        self.assertEqual(alpha_at(500250, 500250), 0)
        ds = None

    def test_zoom_scales_and_small_area_have_every_requested_level(self):
        levels = zoom_levels(self.project, self.area, self.crs, 13, 17)
        for previous, current in zip(levels, levels[1:]):
            self.assertAlmostEqual(previous['resolution'] / current['resolution'], 2)
            self.assertAlmostEqual(previous['scale'] / current['scale'], 2)
            self.assertAlmostEqual(current['scale'], current['resolution'] * 96 / 0.0254, places=5)
        area = QgsGeometry.fromRect(QgsRectangle(500000, 500000, 500001, 500001))
        record = write_rendered_raster(self.layer, self.project, area, self.crs, self.database,
                                       'tiny', levels, lambda: False, lambda _: None)
        self.assertEqual(len(record['raster']['levels']), 5)
        for level in levels:
            ds = gdal.OpenEx(str(self.database), gdal.OF_RASTER,
                             open_options=['TABLE=tiny', f'ZOOM_LEVEL={level["zoom"]}'])
            self.assertIsNotNone(ds)
            self.assertAlmostEqual(ds.GetGeoTransform()[1], level['resolution'])
            ds = None
        with self.assertRaises(ValueError):
            zoom_levels(self.project, area, self.crs, 17, 13)

    def test_sparse_long_diagonal_does_not_scan_or_allocate_full_grid(self):
        area = QgsGeometry.fromWkt('POLYGON((0 0,100000 100000,100002 100000,2 0,0 0))')
        tracemalloc.start()
        count = sum(1 for _ in intersecting_tiles(area, 0, 100000, 1, 100096, 100096))
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        full_grid = math.ceil(100096 / 256) ** 2
        self.assertGreater(full_grid, 150000)
        self.assertLess(count, 1600)
        self.assertLess(peak, 2 * 1024 * 1024)

    def test_tile_touching_only_polygon_boundary_is_transparent(self):
        area = QgsGeometry.fromRect(QgsRectangle(0, 0, 256, 256))
        image = QImage(256, 256, QImage.Format_ARGB32_Premultiplied)
        image.fill(QColor('red'))
        result = _mask_image(image, area, QgsRectangle(256, 0, 512, 256), 1)
        self.assertFalse(any(result.constBits().asstring(result.sizeInBytes())[3::4]))

    def test_independent_zoom_images_not_downsampled(self):
        resolutions = zoom_levels(self.project, self.area, self.crs, 16, 17)
        threshold = sum(level['resolution'] for level in resolutions) / 2

        def render(layer, project, bounds, width, height, cancelled, progress):
            image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
            image.fill(QColor('red' if bounds.width() / width > threshold else 'blue'))
            return image

        with patch('mbtiles_batch_exporter.raster_archive._render_image', side_effect=render):
            self.render()
        for zoom, red in ((16, 255), (17, 0)):
            ds = gdal.OpenEx(str(self.database), gdal.OF_RASTER, open_options=['TABLE=map', f'ZOOM_LEVEL={zoom}'])
            self.assertEqual(ds.GetRasterBand(1).ReadRaster(20, 20, 1, 1)[0], red)
            ds = None

    def test_empty_result_is_reported_and_transparent_tiles_not_stored(self):
        def empty(layer, project, bounds, width, height, cancelled, progress):
            image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
            image.fill(QColor(0, 0, 0, 0))
            return image

        with patch('mbtiles_batch_exporter.raster_archive._render_image', side_effect=empty):
            record = self.render()
        self.assertEqual(record['status'], 'empty')
        self.assertEqual(record['tile_count'], 0)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM map').fetchone()[0], 0)
        uri = str(self.database) + '|option:TABLE=map|option:ZOOM_LEVEL=17'
        layer = QgsRasterLayer(uri, 'Pusty', 'gdal')
        self.assertTrue(layer.isValid(), layer.error().summary())

    def test_retries_then_smaller_fragments_and_partial_failure(self):
        def smaller(layer, project, bounds, width, height, cancelled, progress):
            if width > 160:
                raise RuntimeError('Test: za duży obraz')
            return _render_image(layer, project, bounds, width, height, cancelled, progress)

        with patch('mbtiles_batch_exporter.raster_archive._render_image', side_effect=smaller):
            record = self.render()
        self.assertEqual(record['status'], 'saved')
        self.assertGreater(record['raster']['subdivisions'], 0)
        _remove_table(self.database, 'map')
        with patch('mbtiles_batch_exporter.raster_archive._render_image', side_effect=RuntimeError('Test: brak usługi')):
            record = self.render()
        self.assertEqual(record['status'], 'failed')
        self.assertNotIn('local_source', record)
        self.assertTrue(record['raster']['stopped_early'])
        self.assertGreater(record['raster']['retries'], 0)

    def test_edit_buffer_is_present_in_fallback_rendering(self):
        self.layer.startEditing()
        original = next(self.layer.getFeatures())
        changed = QgsGeometry.fromRect(QgsRectangle(500000, 500000, 500100, 500100))
        self.layer.changeGeometry(original.id(), changed)
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(500400, 500400, 500500, 500500)))
        self.layer.addFeature(feature)
        expected = {f.geometry().asWkt() for f in self.layer.getFeatures()}

        def check_edits(layer, *args):
            self.assertEqual({f.geometry().asWkt() for f in layer.getFeatures()}, expected)
            return _render_image(layer, *args)

        with patch('mbtiles_batch_exporter.raster_archive._render_image', side_effect=check_edits):
            self.render()
        self.assertTrue(self.layer.isModified())

    def test_cancel_removes_unfinished_raster_but_keeps_completed_vector(self):
        second = self.layer.clone()
        self.project.addMapLayer(second, False)
        self.group.addLayer(second)
        stopped = False

        def progress(message):
            nonlocal stopped
            if 'fragment 2' in message:
                stopped = True

        from mbtiles_batch_exporter.archive import _write_vector

        def write(layer, *args):
            if layer.id() == second.id():
                raise RuntimeError('Test: wymuszenie zastępczego obrazu')
            return _write_vector(layer, *args)

        with patch('mbtiles_batch_exporter.archive._write_vector', side_effect=write):
            result = create_archive(self.project, [self.layer.id(), second.id()], self.area, self.crs,
                                    self.folder, cancelled=lambda: stopped, progress=progress,
                                    zoom_min=17, zoom_max=17)
        manifest = json.loads((result / 'manifest.json').read_text())
        statuses = {r['id']: r['status'] for r in manifest['layers']}
        self.assertTrue(manifest['cancelled'])
        self.assertEqual(statuses[self.layer.id()], 'saved')
        self.assertEqual(statuses[second.id()], 'cancelled')
        with closing(sqlite3.connect(result / 'dane.gpkg')) as db:
            self.assertEqual(db.execute('SELECT data_type FROM gpkg_contents').fetchall(), [('features',)])
            self.assertEqual(db.execute('SELECT count(*) FROM gpkg_tile_matrix').fetchone()[0], 0)

    def test_dialog_zoom_range_and_scale_labels(self):
        from mbtiles_batch_exporter.archive_dialog import ArchiveDialog
        with patch('mbtiles_batch_exporter.archive_dialog.QgsProject.instance', return_value=self.project):
            dialog = ArchiveDialog(None)
        try:
            dialog.area_combo.setCurrentIndex(1)
            self.assertEqual(dialog.zoom_min.currentData(), 13)
            self.assertEqual(dialog.zoom_max.currentData(), 17)
            self.assertIn('1:', dialog.zoom_max.currentText())
            self.assertIn('m/piksel', dialog.zoom_max.currentText())
            initial_estimate = dialog.zoom_hint.text()
            self.assertIn('czas ≈', initial_estimate)
            self.assertIn('na dysku ≈', initial_estimate)
            self.assertIn('nie pomiar', dialog.zoom_hint.toolTip())
            dialog.zoom_min.setCurrentIndex(20)
            self.assertEqual(dialog.zoom_max.currentData(), 20)
            self.assertNotEqual(dialog.zoom_hint.text(), initial_estimate)
            dialog.zoom_max.setCurrentIndex(10)
            self.assertEqual(dialog.zoom_min.currentData(), 10)
            self.assertIn(self.layer.id(), dialog._selected_ids())
        finally:
            dialog.close()

    def test_numerical_raster_keeps_values_and_style_after_move(self):
        path = self.folder / 'source.tif'
        ds = gdal.GetDriverByName('GTiff').Create(str(path), 512, 512, 1, gdal.GDT_UInt16)
        ds.SetProjection(self.crs.toWkt(Qgis.CrsWktVariant.Wkt2_2019))
        ds.SetGeoTransform([500000, 1, 0, 500512, 0, -1])
        ds.GetRasterBand(1).Fill(40000)
        ds = None
        raster = QgsRasterLayer(str(path), 'Wartości numeryczne', 'gdal')
        raster.renderer().setOpacity(0.5)
        self.project.addMapLayer(raster)
        result = create_archive(self.project, [raster.id()], self.area, self.crs, self.folder, zoom_min=17, zoom_max=17)
        manifest = json.loads((result / 'manifest.json').read_text())
        record = next(r for r in manifest['layers'] if r['id'] == raster.id())
        self.assertEqual(record['method'], 'raster_data', record)
        local_path = result / record['local_source'][2:]
        ds = gdal.Open(str(local_path))
        self.assertEqual(ds.GetRasterBand(1).DataType, gdal.GDT_UInt16)
        self.assertEqual(struct.unpack('H', ds.GetRasterBand(1).ReadRaster(100, 100, 1, 1))[0], 40000)
        self.assertEqual(ds.GetRasterBand(1).GetMaskBand().ReadRaster(250, 250, 1, 1)[0], 0)
        ds = None
        self.project.removeMapLayer(raster)
        path.unlink()
        moved = self.folder / 'moved'
        shutil.move(result, moved)
        copy = QgsProject()
        try:
            self.assertTrue(copy.read(str(next(moved.glob('*.qgz')))))
            local = copy.mapLayer(record['id'])
            self.assertTrue(local.isValid())
            self.assertEqual(local.renderer().alphaBand(), 2)
            image = _render_image(local, copy, self.area.boundingBox(), 256, 256, lambda: False, lambda _: None)
            self.assertAlmostEqual(image.pixelColor(20, 20).alpha(), 128, delta=1)
        finally:
            copy.clear()


class LocalWmsTests(unittest.TestCase):
    """Also exercise the real QGIS WMS provider without any external services."""
    def setUp(self):
        RasterTests.setUp(self)
        self.start_server()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        RasterTests.tearDown(self)

    def start_server(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                parameters = {key.upper(): value[0] for key, value in parse_qs(urlsplit(self.path).query).items()}
                if parameters.get('REQUEST', '').lower() == 'getcapabilities':
                    body = f'''<?xml version="1.0"?><WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms" xmlns:xlink="http://www.w3.org/1999/xlink">
                    <Service><Name>WMS</Name><Title>Local fixture</Title></Service><Capability><Request>
                    <GetMap><Format>image/png</Format><DCPType><HTTP><Get><OnlineResource xlink:href="http://{self.headers["Host"]}/wms"/></Get></HTTP></DCPType></GetMap>
                    </Request><Exception><Format>XML</Format></Exception><Layer><Title>Test</Title><CRS>EPSG:2180</CRS>
                    <Layer><Name>map</Name><Title>Map</Title><CRS>EPSG:2180</CRS>
                    <EX_GeographicBoundingBox><westBoundLongitude>18</westBoundLongitude><eastBoundLongitude>20</eastBoundLongitude><southBoundLatitude>51</southBoundLatitude><northBoundLatitude>54</northBoundLatitude></EX_GeographicBoundingBox>
                    <BoundingBox CRS="EPSG:2180" minx="499000" miny="499000" maxx="520000" maxy="520000"/></Layer>
                    </Layer></Capability></WMS_Capabilities>'''.encode()
                    content_type = 'text/xml'
                else:
                    self.server.requests.append(parameters)
                    with self.server.lock:
                        self.server.active += 1
                        self.server.peak = max(self.server.peak, self.server.active)
                    time.sleep(self.server.delay)
                    with self.server.lock:
                        self.server.active -= 1
                    width, height = int(parameters.get('WIDTH', 256)), int(parameters.get('HEIGHT', 256))
                    with self.server.lock:
                        scripted = getattr(self.server, 'scripted_statuses', [])
                        status = scripted.pop(0) if scripted else None
                    if status:
                        self.send_response(status)
                        self.send_header('Retry-After', getattr(self.server, 'retry_after', '0'))
                        self.send_header('Content-Length', '0')
                        self.end_headers()
                        return
                    if getattr(self.server, 'forced_status', None):
                        self.send_error(self.server.forced_status)
                        return
                    # QGIS may round the provider's request size by one pixel.
                    if self.server.fail_large and width > 170:
                        self.send_error(503)
                        return
                    image = QImage(width, height, QImage.Format_ARGB32)
                    image.fill(QColor(20, 80, 130, 128))
                    buffer = QBuffer()
                    buffer.open(QIODevice.WriteOnly)
                    image.save(buffer, 'PNG')
                    body = bytes(buffer.data())
                    content_type = 'image/png'
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Expected when the cancellation test closes the client.

        try:
            self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        except PermissionError:
            raise unittest.SkipTest('Loopback HTTP wymaga zezwolenia sieciowego w tym środowisku.')
        self.server.requests = []
        self.server.lock = Lock()
        self.server.active = self.server.peak = 0
        self.server.fail_large = False
        self.server.delay = 0.02
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def test_real_wms_archive_can_open_after_service_is_removed(self):
        self.capture(1)

    def test_parallel_processes_merge_two_wms_layers_and_open_offline(self):
        self.capture(2)

    def test_parallel_workers_use_english_and_respect_server_limit(self):
        with patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE='en'):
            self.capture(2, per_server_limit=1)

    def test_rate_limit_is_reported_by_worker_without_tile_retries(self):
        self.server.forced_status = 429
        uri = QgsDataSourceUri()
        for key, value in {'url': f'http://127.0.0.1:{self.server.server_port}/wms', 'layers': 'map',
                           'styles': '', 'format': 'image/png', 'crs': 'EPSG:2180', 'version': '1.3.0'}.items():
            uri.setParam(key, value)
        layer = QgsRasterLayer(bytes(uri.encodedUri()).decode(), 'Rate limited', 'wms')
        self.project.addMapLayer(layer)
        result = create_archive(self.project, [layer.id()], self.area, self.crs, self.folder,
                                zoom_min=17, zoom_max=17, workers=2)
        manifest = json.loads((result / 'manifest.json').read_text())
        record = next(r for r in manifest['layers'] if r['id'] == layer.id())
        self.assertEqual(record['status'], 'failed')
        self.assertIn('worker_pid', record)
        self.assertTrue(record['raster']['server_warnings'][0].startswith('[HTTP 429]'))
        self.assertTrue(record['raster']['stopped_early'])
        self.assertEqual(record['raster']['retries'], 0)
        self.assertEqual(record['raster']['subdivisions'], 0)
        self.assertIn('[HTTP 429]', (result / 'raport.html').read_text())

    def test_cancel_parallel_workers_keeps_vector_and_removes_private_files(self):
        uri = QgsDataSourceUri()
        for key, value in {'url': f'http://127.0.0.1:{self.server.server_port}/wms', 'layers': 'map',
                           'styles': '', 'format': 'image/png', 'crs': 'EPSG:2180', 'version': '1.3.0'}.items():
            uri.setParam(key, value)
        layer = QgsRasterLayer(bytes(uri.encodedUri()).decode(), 'WMS', 'wms')
        self.project.addMapLayer(layer, False)
        self.group.addLayer(layer)
        cancelled = False

        def progress(message):
            nonlocal cancelled
            if self.server.requests:
                cancelled = True

        result = create_archive(self.project, self.project.mapLayers().keys(), self.area, self.crs, self.folder,
                                zoom_min=17, zoom_max=17, workers=2,
                                cancelled=lambda: cancelled, progress=progress)
        manifest = json.loads((result / 'manifest.json').read_text())
        self.assertTrue(manifest['cancelled'])
        statuses = {r['id']: r['status'] for r in manifest['layers']}
        self.assertEqual(statuses[self.layer.id()], 'saved')
        self.assertEqual(statuses[layer.id()], 'cancelled')
        self.assertFalse((result / '.workers').exists())
        self.assertFalse(list(result.rglob('input.json')))

    def capture(self, workers, per_server_limit=2):
        self.server.fail_large = True
        uri = QgsDataSourceUri()
        for key, value in {'url': f'http://127.0.0.1:{self.server.server_port}/wms', 'layers': 'map',
                           'styles': '', 'format': 'image/png', 'crs': 'EPSG:2180', 'version': '1.3.0'}.items():
            uri.setParam(key, value)
        layer = QgsRasterLayer(bytes(uri.encodedUri()).decode(), 'WMS test', 'wms')
        self.assertTrue(layer.isValid(), layer.error().summary())
        self.project.addMapLayer(layer, False)
        self.group.addLayer(layer)
        if workers > 1:
            second = layer.clone()
            self.project.addMapLayer(second, False)
            self.group.addLayer(second)
        before = len(self.server.requests)
        activities = []
        result = create_archive(self.project, self.project.mapLayers().keys(), self.area, self.crs, self.folder,
                                zoom_min=16, zoom_max=17, workers=workers, per_server_limit=per_server_limit,
                                worker_activity=lambda rows: activities.extend(rows))
        manifest = json.loads((result / 'manifest.json').read_text())
        if workers > 1:
            self.assertTrue(any(r['phase'] == 'active' and ('fragment' in r['message'] or 'zoom' in r['message'])
                                for r in activities), activities)
            self.assertEqual(manifest['parallel']['completed_in_workers'], 2, manifest['layers'])
            self.assertEqual(len({r['worker_pid'] for r in manifest['layers'] if 'worker_pid' in r}), 2)
            self.assertEqual(self.server.peak, min(workers, per_server_limit))
            self.assertTrue(manifest['local_layer_audit']['passed'])
            self.assertFalse((result / '.workers').exists())
        record = next(r for r in manifest['layers'] if r['id'] == layer.id())
        self.assertEqual(record['status'], 'saved', record)
        if os.environ.get('QGIS_SNAPSHOT_LANGUAGE') == 'en':
            self.assertIn('Saved a transparent image', record['reason'])
            self.assertTrue(any('tile' in row['message'] for row in activities), activities)
        self.assertGreater(len(self.server.requests), before)
        self.assertEqual(record['method'], 'raster_render')
        self.assertTrue(record['raster']['server_warnings'][0].startswith('[HTTP 503]'))
        if workers > 1:
            self.assertTrue(any(r.get('server_warnings') for r in activities))
        self.assertGreater(record['raster']['retries'], 0)
        self.assertGreater(record['raster']['subdivisions'], 0)
        self.project.clear()
        self.server.shutdown()
        self.server.server_close()
        moved = self.folder / 'offline'
        shutil.move(result, moved)
        requests_before_open = len(self.server.requests)
        copy = QgsProject()
        try:
            self.assertTrue(copy.read(str(next(moved.glob('*.qgz')))))
            raster = copy.mapLayer(record['id'])
            self.assertTrue(raster.isValid())
            self.assertEqual(raster.providerType(), 'gdal')
            self.assertEqual(raster.crs().authid(), 'EPSG:2180')
            self.assertNotIn('127.0.0.1', raster.source())
            image = _render_image(raster, copy, self.area.boundingBox(), 256, 256,
                                  lambda: False, lambda text: None)
            self.assertFalse(image.isNull())
            self.assertGreater(image.pixelColor(20, 20).alpha(), 0)
            self.assertEqual(len(self.server.requests), requests_before_open)
        finally:
            copy.clear()


if __name__ == '__main__':
    unittest.main()
