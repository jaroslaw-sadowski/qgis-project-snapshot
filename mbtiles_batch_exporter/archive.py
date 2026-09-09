# -*- coding: utf-8 -*-
"""Step 1: a partial project archive with locally stored vector data."""
from datetime import datetime
from contextlib import closing
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
import time
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

from osgeo import gdal, ogr
from qgis.PyQt.QtCore import QSignalBlocker
from qgis.core import (
    Qgis, QgsCoordinateTransform, QgsFeatureRequest, QgsFeatureSink,
    QgsGeometry, QgsProject, QgsVectorFileWriter, QgsVectorLayer,
)


STEP_ONE_LIMITATIONS = [
    "Krok 1: archiwizowane są dane wektorowe. Zapis obrazów WMS, WMTS, XYZ "
    "i innych rastrów będzie dostępny w kroku 2.",
    "Pełna kontrola dodatkowych zasobów, formularzy, relacji i wyrażeń "
    "projektu będzie dostępna w kroku 3. To archiwum częściowe.",
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
    database = ogr.Open(str(path), update=1)
    if database is None:
        raise RuntimeError("Nie można usunąć niepełnych danych. Archiwum nie zostanie opublikowane.")
    try:
        for index in range(database.GetLayerCount()):
            if database.GetLayerByIndex(index).GetName() == table:
                if database.DeleteLayer(index) != 0:
                    raise RuntimeError("Nie udało się usunąć niepełnej tabeli GeoPackage.")
                break
    finally:
        database = None


def _snapshot_project(project, filename):
    """Use QGIS serialization, restoring the live project's path and dirty flag."""
    original_filename = project.fileName()
    original_dirty = project.isDirty()
    original_path_type = project.filePathStorage()
    original_home = project.presetHomePath()
    home = project.homePath()
    blocker = QSignalBlocker(project)
    try:
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
        del blocker


def _local_project(snapshot, destination, records):
    """Replace sources in XML before QGIS can try opening any remote provider."""
    with ZipFile(snapshot) as archive:
        qgs = next(name for name in archive.namelist() if name.endswith('.qgs'))
        root = ET.fromstring(archive.read(qgs))
    saved = {record['id']: record for record in records if record['status'] == 'saved'}
    project_layers = root.find('projectlayers')
    if project_layers is not None:
        for element in list(project_layers):
            record = saved.get(element.findtext('id'))
            if record is None:
                project_layers.remove(element)
                continue
            element.find('datasource').text = './dane.gpkg|layername=' + record['table']
            element.find('provider').text = 'ogr'
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
                    child.set('source', './dane.gpkg|layername=' + record['table'])
                    child.set('providerKey', 'ogr')
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
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(destination.with_suffix('.qgs').name, ET.tostring(root, encoding='utf-8', xml_declaration=True))

    check = QgsProject()
    try:
        if not check.read(str(destination), QgsProject.FlagDontResolveLayers):
            raise RuntimeError("Nie można ponownie otworzyć projektu archiwalnego.")
        if set(check.mapLayers()) != set(saved):
            raise RuntimeError("Projekt archiwalny ma niezgodną listę warstw.")
        for layer in check.mapLayers().values():
            if layer.providerType() != 'ogr':
                raise RuntimeError("Projekt archiwalny nadal zawiera źródło zdalne.")
    finally:
        check.clear()


def create_archive(project, selected_ids, area, area_crs, output_folder,
                   cancelled=lambda: False, progress=lambda message: None):
    """Create a partial archive; return its published directory.

    Called on the QGIS main thread. The dialog is modal and its progress callback
    handles events at bounded intervals; live layers are never used by a worker.
    """
    output_folder = Path(output_folder)
    if not output_folder.is_dir():
        raise ValueError("Wybierz istniejący folder zapisu.")
    selected_ids = set(selected_ids)
    if not selected_ids:
        raise ValueError("Zaznacz przynajmniej jedną warstwę.")
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

    with TemporaryDirectory(prefix='.archive-', dir=output_folder) as temporary:
        staging = Path(temporary)
        snapshot = staging / '_source.qgz'
        _snapshot_project(project, snapshot)
        database = staging / 'dane.gpkg'
        for record in records:
            if record['status'] == 'excluded':
                continue
            progress(f"Przygotowanie: {record['name']}")
            if cancelled():
                record.update(status='cancelled', reason='Nie zapisano — archiwizacja została przerwana.')
                continue
            layer = project.mapLayer(record['id'])
            record['started_at'] = datetime.now().astimezone().isoformat()
            if not isinstance(layer, QgsVectorLayer):
                record.update(status='unsupported', reason='Zapis obrazu tej warstwy będzie dostępny w kroku 2.')
            elif not layer.isValid():
                record.update(status='failed', reason='Źródło warstwy jest niedostępne lub nieprawidłowe.')
            else:
                table = 'layer_' + sha256(layer.id().encode()).hexdigest()[:24]
                try:
                    count = _write_vector(
                        layer, area, area_crs, project, database, table, cancelled,
                        lambda count: progress(f"{layer.name()}: zapisano {count} obiektów"),
                    )
                    record.update(status='saved', table=table, feature_count=count,
                                  method='vector', crs=layer.crs().authid(),
                                  reason='Zapisano dane i styl.' if count else 'Poprawny odczyt: brak obiektów w obszarze.')
                except (ValueError, RuntimeError, InterruptedError) as error:
                    _remove_table(database, table)
                    record.update(status='cancelled' if isinstance(error, InterruptedError) else 'failed',
                                  reason=str(error))
                except Exception:
                    _remove_table(database, table)
                    record.update(status='failed', reason='Nieoczekiwany błąd eksportu danych tej warstwy.')
            record['finished_at'] = datetime.now().astimezone().isoformat()

        progress('Zapisywanie projektu i raportu…')
        _local_project(snapshot, staging / (name + '.qgz'), records)
        snapshot.unlink()
        if database.exists():
            with closing(sqlite3.connect(database)) as connection:
                if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError("Kontrola integralności GeoPackage nie powiodła się.")
        manifest = {
            'schema_version': 1, 'implementation_step': 1, 'status': 'partial',
            'cancelled': cancelled(), 'started_at': started.isoformat(),
            'finished_at': datetime.now().astimezone().isoformat(),
            'qgis_version': Qgis.QGIS_VERSION, 'gdal_version': gdal.VersionInfo('RELEASE_NAME'),
            'project_crs': project.crs().authid(),
            'area': {'crs': area_crs.authid(), 'wkt': area.asWkt()},
            'limitations': STEP_ONE_LIMITATIONS, 'layers': records, 'sha256': {},
        }
        for path in sorted(staging.iterdir()):
            if path.is_file():
                digest = sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                manifest['sha256'][path.name] = digest.hexdigest()
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        labels = {'saved': 'Zapisano', 'failed': 'Błąd', 'excluded': 'Odznaczono',
                  'unsupported': 'Jeszcze nieobsługiwana', 'cancelled': 'Przerwano'}
        rows = ''.join(
            '<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in (
                ' / '.join(record['groups']), record['name'], labels[record['status']],
                record.get('feature_count', '—'), record['reason'],
            )) + '</tr>' for record in records
        )
        (staging / 'raport.html').write_text(
            '<!doctype html><html lang="pl"><meta charset="utf-8"><title>Raport archiwizacji</title>'
            '<style>body{font-family:sans-serif;margin:2em}table{border-collapse:collapse}'
            'td,th{border:1px solid #aaa;padding:.5em;text-align:left}</style>'
            '<h1>Archiwum częściowe — krok 1</h1>'
            + ''.join(f'<p>{escape(text)}</p>' for text in STEP_ONE_LIMITATIONS)
            + f'<p>Początek: {escape(manifest["started_at"])}<br>Koniec: {escape(manifest["finished_at"])}</p>'
            '<p>Daty oznaczają czas pobierania, a nie wspólny moment stanu wszystkich źródeł. '
            'Przenoś cały folder archiwum.</p>'
            '<table><tr><th>Grupa</th><th>Warstwa</th><th>Wynik</th><th>Obiekty</th><th>Informacja</th></tr>'
            + rows + '</table></html>', encoding='utf-8',
        )
        if destination.exists():
            raise FileExistsError("Folder docelowy już istnieje. Nie nadpisano archiwum.")
        staging.rename(destination)
    return destination
