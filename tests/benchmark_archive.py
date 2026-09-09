"""Optional Linux acceptance benchmark; real QGIS, two disposable local WMS servers.

Run separately from unittest: python3 tests/benchmark_archive.py --output /tmp/benchmark.json
Results describe a synthetic workload, not production server performance.
"""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time

from test_raster_archive import LocalWmsTests
from qgis.core import QgsDataSourceUri, QgsGeometry, QgsProject, QgsRasterLayer, QgsRectangle
from mbtiles_batch_exporter.archive import create_archive
from mbtiles_batch_exporter.raster_archive import _render_image


def measure_memory_and_disk(folder, stop, samples):
    while not stop.wait(0.1):
        pids = {os.getpid()}
        for task in Path(f'/proc/{os.getpid()}/task').glob('*'):
            try:
                pids.update(int(pid) for pid in (task / 'children').read_text().split())
            except (FileNotFoundError, ProcessLookupError):
                pass
        rss = 0
        for pid in pids:
            try:
                rss += int(Path(f'/proc/{pid}/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
            except (FileNotFoundError, ProcessLookupError):
                pass
        size = 0
        for path in folder.rglob('*'):
            try:
                if path.is_file():
                    size += path.stat().st_size
            except FileNotFoundError:
                pass
        samples['peak_rss_bytes'] = max(samples['peak_rss_bytes'], rss)
        samples['peak_disk_bytes'] = max(samples['peak_disk_bytes'], size)


def benchmark(output):
    first, second = LocalWmsTests(), LocalWmsTests()
    first.setUp()
    second.setUp()
    rows = []
    archived = []
    try:
        project = first.project
        selected = []
        for server in (first.server, second.server):
            server.delay = 0.05
        for index in range(4):
            server = first.server if index % 2 == 0 else second.server
            host = '127.0.0.1' if index % 2 == 0 else 'localhost'
            uri = QgsDataSourceUri()
            for key, value in {'url': f'http://{host}:{server.server_port}/wms', 'layers': 'map',
                               'styles': '', 'format': 'image/png', 'crs': 'EPSG:2180', 'version': '1.3.0'}.items():
                uri.setParam(key, value)
            layer = QgsRasterLayer(bytes(uri.encodedUri()).decode(), f'Mapa {index + 1}', 'wms')
            if not layer.isValid():
                raise RuntimeError('Nie można otworzyć testowego WMS.')
            project.addMapLayer(layer)
            selected.append(layer.id())
        scenarios = {
            'small': QgsGeometry.fromRect(QgsRectangle(500000, 500000, 500512, 500512)),
            'corridor': QgsGeometry.fromWkt('LINESTRING(500000 500000,507071 507071)').buffer(75, 4),
        }
        # The fixture's declared extent must contain the corridor as well.
        with TemporaryDirectory(prefix='qgis-benchmark-') as temporary:
            root = Path(temporary)
            expected = {}
            for scenario, area in scenarios.items():
                for workers in (1, 2, 4):
                    folder = root / f'{scenario}-{workers}'
                    folder.mkdir()
                    before_requests = sum(len(server.requests) for server in (first.server, second.server))
                    for server in (first.server, second.server):
                        server.peak = 0
                    stop = Event()
                    samples = {'peak_rss_bytes': 0, 'peak_disk_bytes': 0}
                    monitor = Thread(target=measure_memory_and_disk, args=(folder, stop, samples), daemon=True)
                    monitor.start()
                    start = time.monotonic()
                    cpu_before = sum(getattr(resource.getrusage(who), field) for who in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN)
                                     for field in ('ru_utime', 'ru_stime'))
                    try:
                        result = create_archive(project, selected, area, first.crs, folder,
                                                zoom_min=17, zoom_max=17, workers=workers)
                    finally:
                        stop.set()
                        monitor.join()
                    cpu_after = sum(getattr(resource.getrusage(who), field) for who in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN)
                                    for field in ('ru_utime', 'ru_stime'))
                    manifest = json.loads((result / 'manifest.json').read_text())
                    records = [r for r in manifest['layers'] if r['id'] in selected]
                    if any(r['status'] != 'saved' for r in records):
                        raise RuntimeError('Niekompletny wynik pomiaru: ' + json.dumps(records))
                    digest = sha256()
                    with closing(sqlite3.connect(result / 'dane.gpkg')) as db:
                        for record in sorted(records, key=lambda r: r['id']):
                            for (png,) in db.execute(f'SELECT tile_data FROM "{record["table"]}" ORDER BY zoom_level,tile_column,tile_row'):
                                digest.update(png)
                    checksum = digest.hexdigest()
                    expected.setdefault(scenario, checksum)
                    if checksum != expected[scenario]:
                        raise RuntimeError('Równoległe warianty mają inne obrazy niż wariant pojedynczy.')
                    row = {'scenario': scenario, 'workers': workers, 'seconds': round(time.monotonic()-start, 3),
                           'cpu_seconds': round(cpu_after-cpu_before, 3), **samples,
                           'archive_bytes': sum(p.stat().st_size for p in result.rglob('*') if p.is_file()),
                           'tile_count': sum(r['tile_count'] for r in records),
                           'requests': sum(len(s.requests) for s in (first.server, second.server))-before_requests,
                           'server_peaks': [s.peak for s in (first.server, second.server)],
                           'identical_png': True, 'worker_processes': len({r['worker_pid'] for r in records if 'worker_pid' in r})}
                    rows.append(row)
                    print(json.dumps(row), flush=True)
                    archived.append((result, area))
            # Both services are stopped before loading/rendering any archive.
            project.clear()
            first.server.shutdown()
            second.server.shutdown()
            first.server.server_close()
            second.server.server_close()
            for result, area in archived:
                moved = result.parent / 'moved'
                shutil.move(result, moved)
                offline = QgsProject()
                try:
                    if not offline.read(str(next(moved.glob('*.qgz')))):
                        raise RuntimeError('Nie można otworzyć archiwum po przeniesieniu.')
                    for layer in offline.mapLayers().values():
                        if not layer.isValid():
                            raise RuntimeError('Nieprawidłowa warstwa offline.')
                        image = _render_image(layer, offline, area.boundingBox(), 512, 512, lambda: False, lambda text: None)
                        if image.isNull() or not any(image.pixelColor(i, i).alpha() for i in range(512)):
                            raise RuntimeError('Pusty obraz offline.')
                finally:
                    offline.clear()
            output.write_text(json.dumps({'rows': rows, 'offline_render_passed': True,
                                          'rss_note': 'RSS sum includes shared pages counted per process.'}, indent=2))
    finally:
        first.tearDown()
        second.tearDown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    benchmark(parser.parse_args().output)
