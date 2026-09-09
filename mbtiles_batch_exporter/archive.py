# -*- coding: utf-8 -*-
"""Project archives with local vector data and raster snapshots."""
from datetime import datetime
from contextlib import closing, ExitStack
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import time
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

from osgeo import gdal, ogr
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    Qgis, QgsCoordinateTransform, QgsFeatureRequest, QgsFeatureSink,
    QgsGeometry, QgsMultiBandColorRenderer, QgsPathResolver, QgsProject,
    QgsRasterLayer, QgsReadWriteContext, QgsVectorFileWriter, QgsVectorLayer,
)

from .raster_archive import write_raster_data, write_rendered_raster, zoom_levels
from .parallel_archive import RasterWorkers
from .archive_resources import ProjectResources, audit_local_layers


ARCHIVE_LIMITATIONS = [
    "Obrazy usług mapowych "
    "odtwarzają tylko wybrany obszar i poziomy zoomu.",
    "Kontrola lokalnych źródeł i znanych zasobów nie zastępuje odbioru wizualnego "
    "na stanowisku bez dostępu do sieci ani kontroli dowolnego kodu i wyrażeń.",
]


def polygon_area(layer):
    """Use the actual polygon union, not its bounding rectangle."""
    features = layer.getSelectedFeatures() if layer.selectedFeatureCount() else layer.getFeatures()
    geometries = []
    for feature in features:
        geometry = feature.geometry()
        if geometry.isNull() or geometry.isEmpty():
            continue
        if not geometry.isGeosValid():
            raise ValueError("Obszar zawiera nieprawidłowy poligon. Popraw geometrię przed eksportem.")
        geometries.append(geometry)
    if not geometries:
        raise ValueError("Warstwa obszaru nie zawiera poligonów do archiwizacji.")
    area = QgsGeometry.unaryUnion(geometries)
    if area.isEmpty() or not area.isGeosValid():
        raise ValueError("Nie udało się połączyć poligonów obszaru.")
    return area


def _write_vector(layer, area, area_crs, project, path, table, cancelled, progress):
    """Stream live features (including the edit buffer) into a single GPKG table."""
    mask = QgsGeometry(area)
    if layer.isSpatial() and layer.crs() != area_crs:
        if not layer.crs().isValid():
            raise ValueError("Warstwa nie ma poprawnego układu współrzędnych.")
        mask.transform(QgsCoordinateTransform(area_crs, layer.crs(), project))
    request = QgsFeatureRequest()
    if layer.isSpatial():
        request.setFilterRect(mask.boundingBox())
        engine = QgsGeometry.createGeometryEngine(mask.constGet())
        engine.prepareGeometry()

    fields = layer.fields()
    # Preserve a source attribute named 'fid', including duplicate business values.
    primary_key = "_archive_fid"
    while primary_key.lower() in {field.name().lower() for field in fields}:
        primary_key += "_"
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = table
    options.fileEncoding = "UTF-8"
    options.layerOptions = ["FID=" + primary_key, "SPATIAL_INDEX=YES"]
    options.actionOnExistingFile = (
        QgsVectorFileWriter.CreateOrOverwriteLayer if path.exists()
        else QgsVectorFileWriter.CreateOrOverwriteFile
    )
    writer = None
    iterator = None
    errors = []
    provider = layer.dataProvider()
    old_errors = list(provider.errors())
    layer.raiseError.connect(errors.append)
    try:
        writer = QgsVectorFileWriter.create(
            str(path), fields, layer.wkbType(), layer.crs(),
            project.transformContext(), options,
        )
        if not writer or writer.hasError() != QgsVectorFileWriter.NoError:
            raise RuntimeError("Nie można utworzyć tabeli GeoPackage.")
        iterator = layer.getFeatures(request)
        if not iterator.isValid():
            raise RuntimeError("Nie udało się rozpocząć odczytu obiektów.")
        count = 0
        last_update = time.monotonic()
        for feature in iterator:
            if cancelled():
                raise InterruptedError("Przerwano zapis warstwy; niepełną tabelę usunięto.")
            if time.monotonic() - last_update >= 0.1:
                progress(count)
                last_update = time.monotonic()
            if layer.isSpatial():
                geometry = feature.geometry()
                if geometry.isNull() or geometry.isEmpty():
                    continue
                if not geometry.isGeosValid():
                    raise ValueError("Napotkano nieprawidłową geometrię w obszarze eksportu.")
                if not engine.intersects(geometry.constGet()):
                    continue
            if not writer.addFeature(feature, QgsFeatureSink.FastInsert):
                raise RuntimeError("Nie udało się zapisać obiektu do GeoPackage.")
            count += 1
        if cancelled():
            raise InterruptedError("Przerwano zapis warstwy; niepełną tabelę usunięto.")
        if errors or list(provider.errors()) != old_errors:
            # Provider messages may contain credentials or a full database URI.
            raise RuntimeError("Dostawca danych zgłosił błąd odczytu; wynik może być niepełny.")
        if not iterator.isClosed():
            raise RuntimeError("Odczyt warstwy nie zakończył się poprawnie.")
        if not writer.flushBuffer() or writer.hasError() != QgsVectorFileWriter.NoError:
            raise RuntimeError("Nie udało się zakończyć zapisu tabeli GeoPackage.")
    finally:
        layer.raiseError.disconnect(errors.append)
        if iterator is not None:
            iterator.close()
        # QGIS 3.22 has no close() on this writer; destruction closes SQLite.
        del writer

    saved = QgsVectorLayer(f"{path}|layername={table}", layer.name(), "ogr")
    if not saved.isValid() or saved.featureCount() != count:
        raise RuntimeError("Kontrola zapisanej tabeli wykazała brak lub niezgodną liczbę obiektów.")
    if any(saved.fields().indexFromName(field.name()) < 0 for field in fields):
        raise RuntimeError("Kontrola zapisanej tabeli wykazała brak atrybutów.")
    return count


def _remove_table(path, table):
    if not path.exists():
        return
    with closing(sqlite3.connect(path)) as connection:
        if not connection.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone():
            return
    database = ogr.Open(str(path), update=1)
    if database is None:
        raise RuntimeError("Nie można usunąć niepełnych danych. Archiwum nie zostanie opublikowane.")
    try:
        # The driver's DROP TABLE also removes tile matrices/metadata for raster tables.
        gdal.ErrorReset()
        database.ExecuteSQL('DROP TABLE "' + table.replace('"', '""') + '"')
        if gdal.GetLastErrorType() >= gdal.CE_Failure:
            raise RuntimeError("Nie udało się usunąć niepełnej tabeli GeoPackage.")
    finally:
        database = None


def _snapshot_project(project, filename):
    """Use QGIS serialization, restoring the live project's path and dirty flag."""
    original_filename = project.fileName()
    original_dirty = project.isDirty()
    original_path_type = project.filePathStorage()
    original_home = project.presetHomePath()
    home = project.homePath()
    try:
        # QGIS serializes relations and other components via writeProject signals.
        # Blocking those signals silently loses parts of the project.
        # Absolute source paths prevent rebasing relative paths into the staging folder.
        project.setFilePathStorage(Qgis.FilePathType.Absolute)
        if home:
            project.setPresetHomePath(home)
        if not project.write(str(filename)):
            raise RuntimeError("Nie udało się utworzyć kopii projektu.")
    finally:
        project.setFileName(original_filename)
        project.setPresetHomePath(original_home)
        project.setFilePathStorage(original_path_type)
        project.setDirty(original_dirty)


def _local_project(snapshot, destination, records, resources=None):
    """Replace sources in XML before QGIS can try opening any remote provider."""
    with ZipFile(snapshot) as archive:
        qgs = next(name for name in archive.namelist() if name.endswith('.qgs'))
        root = ET.fromstring(archive.read(qgs))
    saved = {record['id']: record for record in records if record.get('local_source')}
    project_layers = root.find('projectlayers')
    if project_layers is not None:
        for element in list(project_layers):
            record = saved.get(element.findtext('id'))
            if record is None:
                project_layers.remove(element)
                continue
            if record['method'] == 'raster_render':
                local_source = str(destination.parent / record['local_source'][2:])
                raster = QgsRasterLayer(local_source, record['name'], 'gdal')
                if not raster.isValid():
                    raise RuntimeError('Nie można otworzyć zapisanego obrazu w QGIS.')
                renderer = QgsMultiBandColorRenderer(raster.dataProvider(), 1, 2, 3)
                renderer.setAlphaBand(4)
                raster.setRenderer(renderer)
                document = QDomDocument()
                node = document.createElement('maplayer')
                document.appendChild(node)
                context = QgsReadWriteContext()
                context.setPathResolver(QgsPathResolver(str(destination)))
                if not raster.writeLayerXml(node, document, context):
                    raise RuntimeError('Nie udało się zapisać ustawień obrazu.')
                replacement = ET.fromstring(document.toString())
                replacement.find('id').text = record['id']
                for attribute in ('hasScaleBasedVisibilityFlag', 'minScale', 'maxScale'):
                    if attribute in element.attrib:
                        replacement.set(attribute, element.get(attribute))
                for tag in ('blendMode', 'layerflags'):
                    original = element.find(tag)
                    if original is not None:
                        for child in list(replacement.findall(tag)):
                            replacement.remove(child)
                        replacement.append(original)
                index = list(project_layers).index(element)
                project_layers.remove(element)
                project_layers.insert(index, replacement)
                element = replacement
                raster = None
            element.find('datasource').text = record['local_source']
            element.find('provider').text = record['local_provider']
            if record['method'] == 'raster_data':
                renderer = element.find('./pipe/rasterrenderer')
                if renderer is not None:
                    renderer.set('alphaBand', str(record['alpha_band']))
            # The filter, joined columns and expression fields are already materialized.
            for tag in ('subsetstring', 'vectorjoins', 'expressionfields', 'auxiliaryLayer',
                        'dependencies', 'dataDependencies'):
                for child in list(element.findall(tag)):
                    element.remove(child)
    for parent in root.iter():
        for child in list(parent):
            if child.tag == 'layer-tree-layer':
                record = saved.get(child.get('id'))
                if record is None:
                    parent.remove(child)
                else:
                    child.set('source', record['local_source'])
                    child.set('providerKey', record['local_provider'])
            elif child.tag == 'legendlayer':
                if any(node.get('layerid') not in saved for node in child.iter('legendlayerfile')):
                    parent.remove(child)
            elif parent.tag in ('custom-order', 'layerorder'):
                layer_id = child.get('id') or child.text
                if layer_id not in saved:
                    parent.remove(child)
    home = root.find('homePath')
    if home is not None:
        home.set('path', '')
    paths = root.find('./properties/Paths/Absolute')
    if paths is not None:
        paths.text = 'false'
    # Project macros must not execute on opening an archive.
    macros = root.find('./properties/Macros')
    if macros is not None:
        root.find('properties').remove(macros)
    resource_report = resources.rewrite(root, records) if resources else {'copied_files': 0, 'issues': []}
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(destination.with_suffix('.qgs').name, ET.tostring(root, encoding='utf-8', xml_declaration=True))
        # Preserve QGIS's embedded style database and project attachments.
        with ZipFile(snapshot) as source:
            for name in source.namelist():
                if not name.endswith(('.qgs', '.qgd')):
                    with source.open(name) as original, archive.open(name, 'w') as target:
                        shutil.copyfileobj(original, target, length=1024 * 1024)

    check = QgsProject()
    try:
        if not check.read(str(destination), QgsProject.FlagDontResolveLayers):
            raise RuntimeError("Nie można ponownie otworzyć projektu archiwalnego.")
        if set(check.mapLayers()) != set(saved):
            raise RuntimeError("Projekt archiwalny ma niezgodną listę warstw.")
        for layer in check.mapLayers().values():
            if layer.providerType() not in ('ogr', 'gdal'):
                raise RuntimeError("Projekt archiwalny nadal zawiera źródło zdalne.")
    finally:
        check.clear()
    return resource_report


def create_archive(project, selected_ids, area, area_crs, output_folder,
                   cancelled=lambda: False, progress=lambda message: None,
                   zoom_min=13, zoom_max=17, workers=1,
                   layer_status=lambda record, completed, total: None,
                   worker_activity=lambda rows: None):
    """Create a partial archive; return its published directory.

    Called on the QGIS main thread. The dialog is modal and its progress callback
    handles events at bounded intervals; live layers are never used by a worker.
    """
    output_folder = Path(output_folder)
    if not isinstance(workers, int) or not 1 <= workers <= 8:
        raise ValueError('Wybierz od 1 do 8 równoległych procesów.')
    if not hasattr(gdal, 'ExceptionMgr'):
        raise RuntimeError('Archiwizacja wymaga GDAL 3.7 lub nowszego, dostarczanego z QGIS.')
    if not output_folder.is_dir():
        raise ValueError("Wybierz istniejący folder zapisu.")
    selected_ids = set(selected_ids)
    if not selected_ids:
        raise ValueError("Zaznacz przynajmniej jedną warstwę.")
    if not (isinstance(zoom_min, int) and isinstance(zoom_max, int) and 0 <= zoom_min <= zoom_max <= 24):
        raise ValueError('Wybierz prawidłowy zakres zoomu od 0 do 24.')
    if not area_crs.isValid() or area.isEmpty() or not area.isGeosValid() or area.area() <= 0:
        raise ValueError("Wybierz poprawny, niepusty obszar archiwizacji i układ współrzędnych.")
    started = datetime.now().astimezone()
    stem = Path(project.fileName()).stem or project.title() or 'Projekt'
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', stem).strip(' .')[:120] or 'Projekt'
    name = f"{stem}_archive_{started:%Y%m%d}"
    destination = output_folder / name
    if destination.exists():
        name += f"_{started:%H%M%S_%f}"
        destination = output_folder / name
    if destination.exists():
        raise FileExistsError("Folder archiwum już istnieje. Wybierz inne miejsce zapisu.")

    records = []
    known_ids = set()
    for node in project.layerTreeRoot().findLayers():
        layer = node.layer()
        if layer is None or layer.id() in known_ids:
            continue
        known_ids.add(layer.id())
        groups = []
        parent = node.parent()
        while parent and parent != project.layerTreeRoot():
            groups.insert(0, parent.name())
            parent = parent.parent()
        records.append({
            'id': layer.id(), 'name': layer.name(), 'groups': groups,
            'provider': layer.providerType(), 'status': 'pending' if layer.id() in selected_ids else 'excluded',
            'reason': '' if layer.id() in selected_ids else 'Odznaczona przez użytkownika.',
        })
    if selected_ids - known_ids:
        raise ValueError("Lista warstw zmieniła się. Otwórz ponownie okno archiwizacji.")

    total = len(selected_ids)
    completed = 0
    parallel = None
    notify = progress
    last_activity = 0.0

    def progress(message):
        nonlocal last_activity
        notify(message)
        if parallel and time.monotonic() - last_activity >= 0.5:
            last_activity = time.monotonic()
            worker_activity(parallel.activity())

    with TemporaryDirectory(prefix='.archive-', dir=output_folder) as temporary, ExitStack() as processes:
        staging = Path(temporary)
        snapshot = staging / '_source.qgz'
        progress(f'Przygotowanie kopii projektu. Wybrano {total} warstw; procesy map: {workers}.')
        _snapshot_project(project, snapshot)
        database = staging / 'dane.gpkg'
        levels = None
        parallel = None
        if workers > 1 and any(r['status'] == 'pending' and r['provider'] not in ('gdal', 'memory', 'ogr', 'mssql', 'WFS')
                               for r in records):
            progress('Przygotowanie kolejki map dla osobnych procesów QGIS…')
            levels = zoom_levels(project, area, area_crs, zoom_min, zoom_max)
            parallel = processes.enter_context(RasterWorkers(snapshot, staging, project, records,
                                                              area, area_crs, levels, workers))
        for record in records:
            if record['status'] == 'excluded':
                continue
            layer_status(dict(record), completed, total)
            progress(f"Warstwa {completed + 1}/{total}: {record['name']} — źródło {record['provider']}.")
            if cancelled():
                record.update(status='cancelled', reason='Nie zapisano — archiwizacja została przerwana.')
                completed += 1
                layer_status(dict(record), completed, total)
                continue
            layer = project.mapLayer(record['id'])
            record['started_at'] = datetime.now().astimezone().isoformat()
            if not layer.isValid():
                record.update(status='failed', reason='Źródło warstwy jest niedostępne lub nieprawidłowe.')
            else:
                table = 'layer_' + sha256(layer.id().encode()).hexdigest()[:24]
                record['attempts'] = []
                try:
                    if isinstance(layer, QgsVectorLayer):
                        try:
                            progress(f'{layer.name()}: odczyt danych i zapis geometrii oraz atrybutów…')
                            count = _write_vector(
                                layer, area, area_crs, project, database, table, cancelled,
                                lambda count: progress(f"{layer.name()}: zapisano {count} obiektów"),
                            )
                            record.update(status='saved', table=table, feature_count=count,
                                          method='vector', crs=layer.crs().authid(),
                                          local_source='./dane.gpkg|layername=' + table, local_provider='ogr',
                                          reason='Zapisano dane i styl.' if count else 'Poprawny odczyt: brak obiektów w obszarze.')
                        except InterruptedError:
                            raise
                        except Exception:
                            _remove_table(database, table)
                            record['attempts'].append({'method': 'vector', 'reason': 'Eksport danych wektorowych nie powiódł się; próba zapisu obrazu.'})
                            progress(f'{layer.name()}: zapis wektorów nie powiódł się. Próbuję zapisać wygląd mapy; atrybuty nie zostaną zachowane.')
                    elif isinstance(layer, QgsRasterLayer) and layer.providerType() == 'gdal':
                        try:
                            progress(f'{layer.name()}: odczyt i kopiowanie wartości rastra…')
                            record.update(write_raster_data(layer, project, area, area_crs, staging, table, cancelled, progress))
                        except InterruptedError:
                            raise
                        except Exception:
                            record['attempts'].append({'method': 'raster_data', 'reason': 'Nie udało się zachować oryginalnych wartości rastra; próba zapisu obrazu.'})
                            progress(f'{layer.name()}: nie udało się zachować wartości rastra. Próbuję zapisać wygląd mapy.')
                    if record['status'] != 'saved':
                        if levels is None:
                            levels = zoom_levels(project, area, area_crs, zoom_min, zoom_max)
                        result = None
                        if parallel and layer.id() in parallel.futures:
                            try:
                                result = parallel.take(layer.id(), database, cancelled, progress)
                            except InterruptedError:
                                raise
                            except Exception:
                                _remove_table(database, table)
                                record['attempts'].append({'method': 'parallel', 'reason': 'Proces pomocniczy nie zakończył zapisu; ponowiono w głównym QGIS.'})
                                progress(f'{layer.name()}: proces pomocniczy zawiódł. Ponawiam zapis w głównym QGIS.')
                        record.update(result if result is not None else write_rendered_raster(
                            layer, project, area, area_crs, database, table, levels, cancelled, progress))
                        if record['status'] == 'failed':
                            _remove_table(database, table)
                        if isinstance(layer, QgsVectorLayer):
                            record['reason'] += ' Zapis zastępczy: obraz nie zachowuje obiektów i atrybutów.'
                except InterruptedError:
                    _remove_table(database, table)
                    record.update(status='cancelled', reason='Przerwano zapis warstwy; niepełne dane tej warstwy usunięto.')
                except Exception:
                    _remove_table(database, table)
                    record.update(status='failed', reason='Nie udało się zapisać danych ani obrazu tej warstwy.')
            record['finished_at'] = datetime.now().astimezone().isoformat()
            completed += 1
            layer_status(dict(record), completed, total)
            progress(f'{record["name"]}: {record["reason"]}')

        progress('Kończenie zadań pomocniczych i porządkowanie plików tymczasowych…')
        processes.close()
        parallel = None
        worker_activity([])
        progress('Zapisywanie projektu, lokalnych symboli, formularzy i załączników…')
        resource_report = _local_project(snapshot, staging / (name + '.qgz'), records,
                                         ProjectResources(project, staging, cancelled, progress))
        progress('Otwieranie zapisanych warstw — kontrola dostępności lokalnych danych…')
        local_failures = audit_local_layers(staging / (name + '.qgz'), records)
        snapshot.unlink()
        if database.exists():
            progress('Kontrola integralności GeoPackage…')
            with closing(sqlite3.connect(database)) as connection:
                if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError("Kontrola integralności GeoPackage nie powiodła się.")
        manifest = {
            'schema_version': 3, 'implementation_step': 3, 'status': 'partial',
            'cancelled': cancelled(), 'started_at': started.isoformat(),
            'finished_at': datetime.now().astimezone().isoformat(),
            'qgis_version': Qgis.QGIS_VERSION, 'gdal_version': gdal.VersionInfo('RELEASE_NAME'),
            'project_crs': project.crs().authid(),
            'area': {'crs': area_crs.authid(), 'wkt': area.asWkt()},
            'zoom_min': zoom_min, 'zoom_max': zoom_max, 'raster_levels': levels or [],
            'parallel': {'workers': workers, 'per_server_limit': 2,
                         'completed_in_workers': sum('worker_pid' in r for r in records)},
            'resources': resource_report, 'local_layer_audit': {'passed': not local_failures, 'failures': local_failures},
            'limitations': ARCHIVE_LIMITATIONS, 'layers': records, 'sha256': {},
        }
        for path in sorted(staging.rglob('*')):
            if path.is_file():
                progress(f'Kontrola pliku: {path.relative_to(staging).as_posix()} ({path.stat().st_size / 1048576:.1f} MiB)…')
                digest = sha256()
                with path.open('rb') as stream:
                    last_update = time.monotonic()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                        if time.monotonic() - last_update > 0.1:
                            progress('Kontrola plików archiwum…')
                            last_update = time.monotonic()
                manifest['sha256'][path.relative_to(staging).as_posix()] = digest.hexdigest()
        manifest['cancelled'] = cancelled()
        manifest['finished_at'] = datetime.now().astimezone().isoformat()
        progress('Zapisywanie manifestu i raportu z wynikami…')
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        labels = {'saved': 'Zapisano', 'failed': 'Błąd', 'excluded': 'Odznaczono',
                  'partial': 'Obraz częściowy', 'empty': 'Pusty zoom — do sprawdzenia', 'cancelled': 'Przerwano'}
        rows = ''.join(
            '<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in (
                ' / '.join(record['groups']), record['name'], labels[record['status']],
                record.get('feature_count', record.get('tile_count', '—')), record['reason'],
            )) + '</tr>' for record in records
        )
        (staging / 'raport.html').write_text(
            '<!doctype html><html lang="pl"><meta charset="utf-8"><title>qgis-project-snapshot — raport</title>'
            '<style>body{font-family:sans-serif;margin:2em}table{border-collapse:collapse}'
            'td,th{border:1px solid #aaa;padding:.5em;text-align:left}</style>'
            '<h1>qgis-project-snapshot — wynik archiwizacji</h1><p>Sprawdź archiwum bez dostępu do sieci.</p>'
            + ''.join(f'<p>{escape(text)}</p>' for text in ARCHIVE_LIMITATIONS)
            + f'<p>Zakres obrazów: zoom {zoom_min}–{zoom_max}. PNG: kompresja bezstratna 9, pełna przezroczystość.</p>'
            + f'<p>Procesy: {workers}. Skopiowane zasoby: {resource_report["copied_files"]}. '
              f'Kontrola lokalnych warstw: {"poprawna" if not local_failures else "wykryto problemy"}.</p>'
            + ''.join(f'<p>Do sprawdzenia — {escape(item["owner"])}: {escape(item["reason"])}</p>' for item in resource_report['issues'])
            + ''.join(f'<p>{escape(message)}</p>' for message in local_failures)
            + f'<p>Początek: {escape(manifest["started_at"])}<br>Koniec: {escape(manifest["finished_at"])}</p>'
            '<p>Daty oznaczają czas pobierania, a nie wspólny moment stanu wszystkich źródeł. '
            'Przenoś cały folder archiwum.</p>'
            '<table><tr><th>Grupa</th><th>Warstwa</th><th>Wynik</th><th>Obiekty / kafelki</th><th>Informacja</th></tr>'
            + rows + '</table></html>', encoding='utf-8',
        )
        if destination.exists():
            raise FileExistsError("Folder docelowy już istnieje. Nie nadpisano archiwum.")
        progress('Udostępnianie gotowego folderu archiwum…')
        staging.rename(destination)
    return destination
