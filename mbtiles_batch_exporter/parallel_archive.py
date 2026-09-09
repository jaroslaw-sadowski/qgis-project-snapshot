"""Bounded process workers; threads supervise processes, never QGIS objects."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from threading import Event, Semaphore
import time
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from osgeo import gdal
from qgis.core import Qgis, QgsDataSourceUri, QgsVectorLayer
from qgis.PyQt.QtCore import QCoreApplication, QUrl


def merge_raster(source, destination, table, cancelled=lambda: False):
    """Copy compressed PNG bytes unchanged; only the parent writes the final DB."""
    if not destination.exists():
        try:
            with source.open('rb') as original, destination.open('wb') as target:
                for chunk in iter(lambda: original.read(1024 * 1024), b''):
                    if cancelled():
                        raise InterruptedError()
                    target.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return
    with gdal.ExceptionMgr():
        raster = gdal.OpenEx(str(source), gdal.OF_RASTER, open_options=['TABLE=' + table])
        target = gdal.GetDriverByName('GPKG').Create(
            str(destination), raster.RasterXSize, raster.RasterYSize, 4, gdal.GDT_Byte,
            options=['RASTER_TABLE=' + table, 'APPEND_SUBDATASET=YES', 'TILE_FORMAT=PNG', 'ZLEVEL=9'],
        )
        target.SetProjection(raster.GetProjection())
        target.SetGeoTransform(raster.GetGeoTransform())
        target.FlushCache()
        raster = target = None
    # Names originate exclusively from sha256(layer.id()), never from layer names.
    with closing(sqlite3.connect(destination)) as connection:
        connection.set_progress_handler(lambda: int(cancelled()), 10000)
        connection.execute('ATTACH DATABASE ? AS incoming', (str(source),))
        with connection:
            connection.execute('DELETE FROM gpkg_tile_matrix WHERE table_name=?', (table,))
            connection.execute('INSERT INTO gpkg_tile_matrix SELECT * FROM incoming.gpkg_tile_matrix WHERE table_name=?', (table,))
            connection.execute(f'INSERT INTO "{table}" SELECT * FROM incoming."{table}"')
            bounds = connection.execute('SELECT min_x,min_y,max_x,max_y FROM incoming.gpkg_contents WHERE table_name=?', (table,)).fetchone()
            connection.execute('UPDATE gpkg_contents SET min_x=?,min_y=?,max_x=?,max_y=? WHERE table_name=?', (*bounds, table))
            bounds = connection.execute('SELECT min_x,min_y,max_x,max_y FROM incoming.gpkg_tile_matrix_set WHERE table_name=?', (table,)).fetchone()
            connection.execute('UPDATE gpkg_tile_matrix_set SET min_x=?,min_y=?,max_x=?,max_y=? WHERE table_name=?', (*bounds, table))
        connection.execute('DETACH DATABASE incoming')


class RasterWorkers:
    """Context manager owns process lifetime, private files and cancellation."""
    def __init__(self, snapshot, staging, project, records, area, crs, levels, workers):
        self.folder = staging / '.workers'
        self.folder.mkdir(mode=0o700)
        self.stop = Event()
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='archive-process')
        self.futures = {}
        self.parameters = (snapshot, project, records, area, crs, levels)
        self.server_limits = {}
        self.started = set()
        self.merged = set()

    def __enter__(self):
        try:
            snapshot, project, records, area, crs, levels = self.parameters
            with ZipFile(snapshot) as archive:
                root = ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.qgs'))))
            # Interleave servers so a long queue from one host cannot occupy
            # every supervising thread while other servers remain idle.
            queues = {}
            for record in records:
                layer = project.mapLayer(record['id'])
                # Live vector edits and auth credentials remain in the main process.
                if record['status'] != 'pending' or not layer.isValid() or isinstance(layer, QgsVectorLayer) or layer.providerType() == 'gdal':
                    continue
                if 'authcfg=' in layer.source():
                    continue
                uri = QgsDataSourceUri()
                uri.setEncodedUri(layer.source())
                host = QUrl(uri.param('url')).host() or layer.providerType()
                queues.setdefault(host, deque()).append(record)
            ordered = []
            while any(queues.values()):
                for host, queue in queues.items():
                    if queue:
                        ordered.append((host, queue.popleft()))
            for host, record in ordered:
                layer = project.mapLayer(record['id'])
                table = 'layer_' + sha256(layer.id().encode()).hexdigest()[:24]
                folder = self.folder / table
                folder.mkdir(mode=0o700)
                isolated = deepcopy(root)
                for element in list(isolated.find('projectlayers')):
                    if element.findtext('id') != layer.id():
                        isolated.find('projectlayers').remove(element)
                for parent in isolated.iter():
                    for child in list(parent):
                        if child.tag == 'layer-tree-layer' and child.get('id') != layer.id():
                            parent.remove(child)
                macros = isolated.find('./properties/Macros')
                if macros is not None:
                    isolated.find('properties').remove(macros)
                (folder / 'source.qgs').write_bytes(ET.tostring(isolated, encoding='utf-8'))
                (folder / 'input.json').write_text(json.dumps({
                    'layer_id': layer.id(), 'table': table, 'area': area.asWkt(),
                    'area_crs': crs.toWkt(Qgis.CrsWktVariant.Wkt2_2019), 'levels': levels,
                }), encoding='utf-8')
                limit = self.server_limits.setdefault(host, Semaphore(2))
                self.futures[layer.id()] = (self.pool.submit(self._run, folder, limit), folder)
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def _run(self, folder, limit):
        while not limit.acquire(timeout=0.1):
            if self.stop.is_set():
                raise InterruptedError()
        try:
            if self.stop.is_set():
                raise InterruptedError()
            executable = sys.executable if Path(sys.executable).name.lower().startswith('python') else shutil.which('python3')
            if not executable:
                raise RuntimeError('Brak interpretera Python dla procesów QGIS.')
            environment = os.environ.copy()
            environment['QT_QPA_PLATFORM'] = 'offscreen'
            environment['PYTHONDONTWRITEBYTECODE'] = '1'
            environment['PYTHONPATH'] = os.pathsep.join([str(Path(__file__).resolve().parent.parent), *sys.path])
            environment['GDAL_NUM_THREADS'] = '1'
            self.started.add(folder.name)
            with subprocess.Popen([executable, '-m', 'mbtiles_batch_exporter.archive_worker', str(folder)],
                                  env=environment, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
                stopping = None
                while process.poll() is None:
                    if self.stop.is_set():
                        (folder / 'cancel').touch()
                        stopping = stopping or time.monotonic()
                        if time.monotonic() - stopping > 5:
                            process.kill()
                    time.sleep(0.05)
                if self.stop.is_set():
                    raise InterruptedError()
                if process.returncode or not (folder / 'result.json').exists():
                    raise RuntimeError('Proces nie zapisał obrazu; użyto ponownej próby w QGIS.')
            return json.loads((folder / 'result.json').read_text())
        finally:
            limit.release()

    def take(self, layer_id, destination, cancelled, progress):
        future, folder = self.futures[layer_id]
        while not future.done():
            QCoreApplication.processEvents()
            if cancelled():
                self.stop.set()
                raise InterruptedError()
            progress('Równoległe pobieranie map — oczekiwanie na warstwę…')
            time.sleep(0.05)
        if cancelled():
            self.stop.set()
            raise InterruptedError()
        result = future.result()
        if result.get('local_source'):
            # SQLite/GDAL handles are created in this thread. UI events remain
            # responsive even while copying a large table; no QGIS objects move.
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix='archive-merge') as merger:
                merging = merger.submit(merge_raster, folder / 'raster.gpkg', destination,
                                        result['table'], self.stop.is_set)
                while not merging.done():
                    QCoreApplication.processEvents()
                    if cancelled():
                        self.stop.set()
                    progress('Scalanie gotowej mapy do GeoPackage…')
                    time.sleep(0.05)
                if self.stop.is_set():
                    raise InterruptedError()
                merging.result()
        shutil.rmtree(folder)
        self.merged.add(layer_id)
        return result

    def activity(self):
        """Read disposable worker snapshots on the main thread only."""
        rows = []
        for layer_id, (future, folder) in self.futures.items():
            phase, message = 'queued', 'W kolejce'
            if layer_id in self.merged:
                phase, message = 'merged', 'Wynik przekazano do archiwizacji'
            elif future.done():
                failed = future.cancelled() or future.exception() is not None or future.result().get('status') == 'failed'
                phase, message = ('failed', 'Proces zakończony bez obrazu') if failed else ('ready', 'Zakończono pobieranie — czeka na scalenie')
            elif folder.name in self.started:
                phase, message = 'active', 'Uruchamianie QGIS lub otwieranie źródła…'
                try:
                    state = json.loads((folder / 'progress.json').read_text(encoding='utf-8'))
                    message = state['message']
                    age = int(time.time() - state['updated_at'])
                    if age >= 10:
                        message += f' (ostatni komunikat {age} s temu)'
                except (OSError, ValueError, KeyError):
                    pass
            rows.append({'id': layer_id, 'phase': phase, 'message': message})
        return rows

    def __exit__(self, *args):
        self.stop.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        shutil.rmtree(self.folder, ignore_errors=True)
