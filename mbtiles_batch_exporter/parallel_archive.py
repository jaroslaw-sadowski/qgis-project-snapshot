"""Bounded process workers; threads supervise processes, never QGIS objects."""
from .i18n import tr, language
from .adaptive import HostPolicy, WorkerGate, PROTOCOL, write_state
from .resources import available_memory
from concurrent.futures import Future, ThreadPoolExecutor
from collections import deque
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from threading import Condition, Event, Thread
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
    def __init__(self, snapshot, staging, project, records, area, crs, levels, workers, per_server_limit=2, adaptive=False):
        self.folder = staging / '.workers'
        self.folder.mkdir(mode=0o700)
        self.stop = Event()
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='archive-process')
        self.futures = {}
        self.parameters = (snapshot, project, records, area, crs, levels)
        self.active_hosts = {}
        self.queue = []
        self.condition = Condition()
        self.workers = workers
        self.per_server_limit = per_server_limit
        self.language = language()
        self.started = set()
        self.merged = set()
        self.adaptive = adaptive
        self.policies = {}
        self.jobs = {}
        self.coordinator = None
        self.coordinator_failed = False
        self.memory_ok = True
        self.next_memory_check = 0.0
        self.memory_history = []
        self.origin = time.monotonic()
        self.rows = []

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
                    'area_crs': crs.toWkt(Qgis.CrsWktVariant.Wkt2_2019), 'levels': levels, 'adaptive': self.adaptive,
                }), encoding='utf-8')
                if self.adaptive:
                    self._register(host, folder)
                future = Future()
                self.futures[layer.id()] = (future, folder)
                self.queue.append((host, future, folder))
            if self.adaptive:
                self.coordinator = Thread(target=self._coordinate, name='archive-coordinator', daemon=True)
                self.coordinator.start()
            for _ in range(min(self.workers, len(self.queue))):
                self.pool.submit(self._work_loop)
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def _register(self, host, folder):
        self.policies.setdefault(host, HostPolicy(host, self.per_server_limit, window_started=time.monotonic()))
        self.jobs[folder.name] = {'host': host, 'folder': folder, 'active': False,
                                  'ack': 0, 'counts': {}, 'state': {}}
        write_state(folder / 'control.json', {'version': PROTOCOL, 'allowed': False,
                    'generation': 0, 'expires': time.monotonic() + 2, 'ack': 0})

    def _read_job(self, job, now):
        try:
            state = json.loads((job['folder'] / 'telemetry.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        if state.get('version') != PROTOCOL:
            return
        policy = self.policies[job['host']]
        job['state'] = state
        for generation, count in state.get('counts', {}).items():
            delta = count - job['counts'].get(generation, 0)
            if delta > 0:
                policy.success(delta, now, int(generation))
                job['counts'][generation] = count
        for event in state.get('events', []):
            if event['sequence'] <= job['ack']:
                continue
            if event['status'] == 'success':
                policy.success(1, now, event['generation'], probe=event['probe'])
            else:
                policy.failure(event['status'], event['delay'], now, event['generation'], probe=event['probe'])
            job['ack'] = event['sequence']

    def _coordinate(self):
        try:
            while not self.stop.is_set():
                with self.condition:
                    now = time.monotonic()
                    if now >= self.next_memory_check:
                        memory = available_memory()
                        ok = memory is None or memory >= 2 * 1024**3
                        if ok != self.memory_ok:
                            self.memory_history.append({'at': now - self.origin, 'memory_ok': ok})
                        self.memory_ok = ok
                        self.next_memory_check = now + 5
                    for job in self.jobs.values():
                        if job['active']:
                            self._read_job(job, now)
                    rows = []
                    for host, policy in self.policies.items():
                        jobs = [j for j in self.jobs.values() if j['host'] == host and j['active']]
                        queued = sum(h == host for h, _, _ in self.queue)
                        policy.evaluate(now, queued > 0 and sum(self.active_hosts.values()) < self.workers,
                                        self.memory_ok)
                        allowed = jobs[:policy.limit]
                        if policy.recovering:
                            allowed = []
                            if now >= policy.until and not policy.blocked:
                                candidates = [j for j in jobs if j['state'].get('recoverable')]
                                # A current recovery probe has priority over other failed maps.
                                probing = [j for j in candidates if j.get('probing')]
                                allowed = (probing or candidates)[:1]
                                if not allowed and not any(j['state'].get('running') or not j['state'] for j in jobs):
                                    policy.blocked = True
                                    policy.change(now, 'no_retryable_tiles')
                        for job in jobs:
                            job['probing'] = policy.recovering and job in allowed
                            write_state(job['folder'] / 'control.json', {
                                'version': PROTOCOL, 'generation': policy.generation,
                                'allowed': job in allowed and not policy.blocked,
                                'probe': job['probing'], 'blocked': policy.blocked,
                                'ack': job['ack'], 'expires': now + 2,
                            })
                        state = ('deferred' if policy.blocked else 'cooldown' if policy.recovering
                                 else 'memory' if not self.memory_ok else 'repairing'
                                 if any(j['state'].get('repairing') for j in jobs)
                                 else 'stable' if policy.frozen or policy.limit >= policy.ceiling
                                 else 'increasing' if policy.limit > 1 else 'starting')
                        rows.append({'host': host, 'active': sum(bool(j['state'].get('running')) for j in jobs),
                                     'processes': len(jobs), 'limit': policy.limit, 'queued': queued, 'budget': self.workers,
                                     'rate': (policy.successes / max(0.001, now - policy.window_started)
                                              if policy.successes else policy.rate), 'state': state,
                                     'pause': max(0, math.ceil(policy.until - now)),
                                     'generation': policy.generation, 'successes': policy.total_successes})
                    self.rows = rows
                    self.condition.notify_all()
                self.stop.wait(0.5)
        except Exception:
            # A broken coordinator must never leave unrestricted workers running.
            self.coordinator_failed = True
            self.stop.set()
            with self.condition:
                self.condition.notify_all()

    def server_activity(self):
        with self.condition:
            rows = []
            for original in self.rows:
                row = dict(original)
                jobs = [j for j in self.jobs.values() if j['active'] and j['host'] == row['host']]
                row['processes'] = len(jobs)
                row['active'] = sum(bool(j['state'].get('running')) for j in jobs)
                row['queued'] = sum(h == row['host'] for h, _, _ in self.queue)
                if not jobs or row['state'] in ('cooldown', 'deferred'):
                    row['rate'] = 0.0
                rows.append(row)
            return rows

    def adaptive_report(self):
        with self.condition:
            return {'protocol': PROTOCOL, 'coordinator_failed': self.coordinator_failed, 'memory': list(self.memory_history), 'hosts': [
                {'host': p.host, 'limit': p.limit, 'frozen': p.frozen, 'deferred': p.blocked,
                 'successes': p.total_successes, 'history': [dict(event, at=event['at'] - self.origin)
                                                            for event in p.history]}
                for p in self.policies.values()]}

    def local_gate(self, layer, cancelled):
        # Authenticated map providers stay in the main QGIS, but use the same host policy.
        uri = QgsDataSourceUri()
        uri.setEncodedUri(layer.source())
        host = QUrl(uri.param('url')).host() or layer.providerType()
        folder = self.folder / ('local_' + sha256(layer.id().encode()).hexdigest()[:24])
        folder.mkdir(exist_ok=True)
        with self.condition:
            self._register(host, folder)
            self.jobs[folder.name]['active'] = True
        return WorkerGate(folder, cancelled, QCoreApplication.processEvents)

    def finish_local(self, gate):
        gate.close()
        with self.condition:
            job = self.jobs[gate.folder.name]
            self._read_job(job, time.monotonic())
            job['active'] = False

    def _work_loop(self):
        # Claim only a runnable host. A busy server must not occupy a worker
        # while layers on another server are still queued.
        while True:
            with self.condition:
                if self.stop.is_set():
                    for _, future, _ in self.queue:
                        future.cancel()
                    self.queue.clear()
                if not self.queue:
                    return
                index = next((i for i, (host, _, _) in enumerate(self.queue)
                              if self.active_hosts.get(host, 0) < (self.policies[host].limit if self.adaptive else self.per_server_limit)
                              and (not self.adaptive or (self.memory_ok and not self.policies[host].recovering))), None)
                if self.adaptive:
                    for host, future, folder in list(self.queue):
                        if self.policies[host].blocked:
                            future.set_result({'status': 'failed', 'method': 'raster_render',
                                               'reason': tr('Serwer odłożony do późniejszej próby.'),
                                               'raster': {'deferred': True}})
                            self.queue.remove((host, future, folder))
                    if not self.queue:
                        return
                    # Queue may have changed while removing deferred hosts.
                    index = next((i for i, (host, _, _) in enumerate(self.queue)
                                  if self.memory_ok and not self.policies[host].recovering
                                  and self.active_hosts.get(host, 0) < self.policies[host].limit), None)
                if index is None:
                    self.condition.wait(0.1)
                    continue
                host, future, folder = self.queue.pop(index)
                self.active_hosts[host] = self.active_hosts.get(host, 0) + 1
                future.set_running_or_notify_cancel()
                if self.adaptive:
                    self.jobs[folder.name]['active'] = True
            error = None
            result = None
            try:
                result = self._run(folder)
            except Exception as caught:
                error = caught
            finally:
                with self.condition:
                    if self.adaptive:
                        self._read_job(self.jobs[folder.name], time.monotonic())
                        self.jobs[folder.name]['active'] = False
                    self.active_hosts[host] -= 1
                    self.condition.notify_all()
            if error is not None:
                future.set_exception(error)
            else:
                future.set_result(result)

    def _run(self, folder):
        if self.stop.is_set():
            if self.coordinator_failed:
                raise RuntimeError(tr('Koordynator pobierania zakończył pracę z błędem.'))
            raise InterruptedError()
        executable = sys.executable if Path(sys.executable).name.lower().startswith('python') else shutil.which('python3')
        if not executable:
            raise RuntimeError(tr('Brak interpretera Python dla procesów QGIS.'))
        environment = os.environ.copy()
        environment['QT_QPA_PLATFORM'] = 'offscreen'
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        environment['PYTHONPATH'] = os.pathsep.join([str(Path(__file__).resolve().parent.parent), *sys.path])
        environment['GDAL_NUM_THREADS'] = '1'
        environment['QGIS_SNAPSHOT_LANGUAGE'] = self.language
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
                if self.coordinator_failed:
                    raise RuntimeError(tr('Koordynator pobierania zakończył pracę z błędem.'))
                raise InterruptedError()
            if process.returncode or not (folder / 'result.json').exists():
                raise RuntimeError(tr('Proces nie zapisał obrazu; użyto ponownej próby w QGIS.'))
        return json.loads((folder / 'result.json').read_text())


    def take(self, layer_id, destination, cancelled, progress):
        future, folder = self.futures[layer_id]
        while not future.done():
            QCoreApplication.processEvents()
            if cancelled():
                self.stop.set()
                raise InterruptedError()
            progress(tr('Równoległe pobieranie map — oczekiwanie na warstwę…'))
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
                    progress(tr('Scalanie gotowej mapy do GeoPackage…'))
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
            phase, message = 'queued', tr('W kolejce')
            if layer_id in self.merged:
                phase, message = 'merged', tr('Wynik przekazano do archiwizacji')
            elif future.done():
                failed = future.cancelled() or future.exception() is not None or future.result().get('status') == 'failed'
                phase, message = ('failed', tr('Proces zakończony bez obrazu')) if failed else ('ready', tr('Zakończono pobieranie — czeka na scalenie'))
            elif folder.name in self.started:
                phase, message = 'active', tr('Uruchamianie QGIS lub otwieranie źródła…')
                try:
                    state = json.loads((folder / 'progress.json').read_text(encoding='utf-8'))
                    message = state['message']
                    age = int(time.time() - state['updated_at'])
                    if age >= 10:
                        message += tr(' (ostatni komunikat {0} s temu)').format(age)
                except (OSError, ValueError, KeyError):
                    pass
            # Warnings are latched separately from the latest progress message,
            # including workers which have already finished between UI polls.
            warnings = []
            if layer_id not in self.merged:
                try:
                    warnings = json.loads((folder / 'progress.json').read_text(encoding='utf-8')).get('server_warnings', [])
                except (OSError, ValueError):
                    pass
            rows.append({'id': layer_id, 'phase': phase, 'message': message, 'server_warnings': warnings})
        return rows

    def __exit__(self, *args):
        self.stop.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.coordinator:
            self.coordinator.join(timeout=3)
        shutil.rmtree(self.folder, ignore_errors=True)
