# SPDX-License-Identifier: GPL-2.0-only

# -*- coding: utf-8 -*-
"""Project archives with local vector data and raster snapshots."""

import json
import os
import re
import shutil
import sqlite3
import time
from configparser import ConfigParser
from contextlib import ExitStack, closing, contextmanager
from datetime import datetime
from hashlib import sha256
from html import escape
from pathlib import Path
from tempfile import mkdtemp
from urllib.parse import quote

# Canonicalization only, after defusedxml validation in _source_fingerprint.
from xml.etree.ElementTree import canonicalize  # nosec B405
from zipfile import ZIP_DEFLATED, ZipFile

from osgeo import gdal, ogr
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsDataSourceUri,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsGeometry,
    QgsMapLayerStyle,
    QgsMultiBandColorRenderer,
    QgsPathResolver,
    QgsProject,
    QgsProviderRegistry,
    QgsRasterLayer,
    QgsReadWriteContext,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication, QEvent, QLockFile
from qgis.PyQt.QtXml import QDomDocument

from .adaptive import write_state
from .archive_resources import ProjectResources, audit_local_layers
from .diagnostics import (
    Diagnostics,
    NetworkDiagnostics,
    PerformanceDiagnostics,
    network_details,
)
from .i18n import tr
from .parallel_archive import RasterWorkers, WorkerError, merge_raster
from .raster_archive import write_raster_data, write_rendered_raster, zoom_levels
from .resources import MAX_WORKERS, detect_resources, recommend
from .vendor.defusedxml import ElementTree as ET
from .worker_network import network_snapshot

ARCHIVE_LIMITATIONS = [
    "Obrazy usług mapowych odtwarzają tylko wybrany obszar i poziomy zoomu.",
    (
        "Kontrola lokalnych źródeł i znanych zasobów nie zastępuje "
        "odbioru wizualnego na stanowisku bez dostępu do sieci ani "
        "kontroli dowolnego kodu i wyrażeń."
    ),
]


def polygon_area(layer):
    """Use the actual polygon union, not its bounding rectangle."""
    features = (
        layer.getSelectedFeatures()
        if layer.selectedFeatureCount()
        else layer.getFeatures()
    )
    geometries = []
    for feature in features:
        geometry = feature.geometry()
        if geometry.isNull() or geometry.isEmpty():
            continue
        if not geometry.isGeosValid():
            raise ValueError(
                tr(
                    (
                        "Obszar zawiera nieprawidłowy poligon. Popraw geometrię przed "
                        "eksportem."
                    )
                )
            )
        geometries.append(geometry)
    if not geometries:
        raise ValueError(tr("Warstwa obszaru nie zawiera poligonów do archiwizacji."))
    area = QgsGeometry.unaryUnion(geometries)
    if area.isEmpty() or not area.isGeosValid():
        raise ValueError(tr("Nie udało się połączyć poligonów obszaru."))
    return area


def _write_vector(
    layer,
    area,
    area_crs,
    project,
    path,
    table,
    cancelled,
    progress,
    diagnostic=None,
    read_details=None,
):
    """Stream live features (including the edit buffer) into a single GPKG table."""
    provider = layer.dataProvider()
    if not layer.isValid() or provider is None or not provider.isValid():
        raise RuntimeError(tr("Nie udało się rozpocząć odczytu obiektów."))
    # WFS delivers downloader errors through queued calls to the provider.
    # Drain earlier calls before the baseline, without processing UI events.
    QCoreApplication.sendPostedEvents(provider, QEvent.Type.MetaCall)
    refreshed = layer.providerType() == "WFS" and not layer.isEditable()
    if refreshed:
        # Keep the live layer/edit buffer. Reloading during editing can change
        # transient feature IDs, so that case uses QGIS's existing cached reader.
        provider.reloadData()
    if diagnostic:
        diagnostic.emit(
            "vector_setup",
            job=table,
            source_crs=layer.crs().authid(),
            area_crs=area_crs.authid(),
            spatial=layer.isSpatial(),
            subset_filter=bool(layer.subsetString()),
            editing=layer.isEditable(),
            provider_crs=provider.crs().authid(),
            provider_crs_matches_layer=provider.crs() == layer.crs(),
            area_crs_valid=area_crs.isValid(),
            wfs_cache_refreshed=refreshed,
        )
    mask = QgsGeometry(area)
    if layer.isSpatial():
        if not layer.crs().isValid():
            raise ValueError(tr("Warstwa nie ma poprawnego układu współrzędnych."))
        if (
            not area_crs.isValid()
            or mask.isNull()
            or mask.isEmpty()
            or not mask.isGeosValid()
        ):
            raise ValueError(
                tr(
                    "Obszar eksportu nie ma poprawnej geometrii "
                    "lub układu współrzędnych."
                )
            )
    if layer.isSpatial() and layer.crs() != area_crs:
        result = mask.transform(QgsCoordinateTransform(area_crs, layer.crs(), project))
        if result != Qgis.GeometryOperationResult.Success:
            raise ValueError(
                tr(
                    "Obszar eksportu nie ma poprawnej geometrii "
                    "lub układu współrzędnych."
                )
            )
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
        QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
        if path.exists()
        else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
    )
    writer = None
    iterator = None
    errors = []
    old_errors = list(provider.errors())
    counters = dict(received=0, written=0, empty_geometry=0, outside_mask=0)
    stage = "writer_create"
    read_complete = False
    empty_probe = None
    empty_verified = None
    started_read = time.monotonic()
    layer.raiseError.connect(errors.append)
    try:
        writer = QgsVectorFileWriter.create(
            str(path),
            fields,
            layer.wkbType(),
            layer.crs(),
            project.transformContext(),
            options,
        )
        if not writer or writer.hasError() != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError(tr("Nie można utworzyć tabeli GeoPackage."))
        stage = "iterator_open"
        iterator = layer.getFeatures(request)
        if not iterator.isValid():
            raise RuntimeError(tr("Nie udało się rozpocząć odczytu obiektów."))
        stage = "iterator_read"
        count = 0
        last_update = time.monotonic()
        for feature in iterator:
            counters["received"] += 1
            if cancelled():
                raise InterruptedError(
                    tr("Przerwano zapis warstwy; niepełną tabelę usunięto.")
                )
            if time.monotonic() - last_update >= 0.1:
                progress(count)
                last_update = time.monotonic()
            if layer.isSpatial():
                geometry = feature.geometry()
                if geometry.isNull() or geometry.isEmpty():
                    counters["empty_geometry"] += 1
                    continue
                if not geometry.isGeosValid():
                    raise ValueError(
                        tr("Napotkano nieprawidłową geometrię w obszarze eksportu.")
                    )
                if not engine.intersects(geometry.constGet()):
                    counters["outside_mask"] += 1
                    continue
            stage = "writer_insert"
            if not writer.addFeature(feature, QgsFeatureSink.Flag.FastInsert):
                raise RuntimeError(tr("Nie udało się zapisać obiektu do GeoPackage."))
            count += 1
            counters["written"] = count
            stage = "iterator_read"
        if cancelled():
            raise InterruptedError(
                tr("Przerwano zapis warstwy; niepełną tabelę usunięto.")
            )
        stage = "provider_check"
        # WFS can close its iterator before the GUI thread delivers its error.
        # A closed iterator alone does not prove success.
        QCoreApplication.sendPostedEvents(provider, QEvent.Type.MetaCall)
        if errors or list(provider.errors()) != old_errors:
            # Provider messages may contain credentials or a full database URI.
            raise RuntimeError(
                tr("Dostawca danych zgłosił błąd odczytu; wynik może być niepełny.")
            )
        if not iterator.isClosed():
            raise RuntimeError(tr("Odczyt warstwy nie zakończył się poprawnie."))
        if counters["received"] == 0 and layer.providerType() == "mssql":
            stage = "empty_source_probe"
            empty_probe = "unconfirmed"
            try:
                # QGIS 3.40's MSSQL iterator can silently close on SQL errors.
                # This bounded native query checks connectivity, table access and
                # the existing subset, with exceptions instead of silent EOF.
                uri = QgsDataSourceUri(provider.dataSourceUri())
                connection = (
                    QgsProviderRegistry.instance()
                    .providerMetadata("mssql")
                    .createConnection(uri.uri(), {})
                )
                if connection is None or not uri.table():
                    raise RuntimeError("MSSQL probe unavailable")
                # Identifiers are bracket-escaped; the subset is the explicit SQL
                # filter already used by this QGIS provider, not remote input.
                source = ".".join(
                    "[" + part.replace("]", "]]") + "]"
                    for part in (uri.schema() or "dbo", uri.table())
                )
                sql = "SELECT TOP (1) 1 FROM " + source  # nosec B608
                if layer.subsetString():
                    sql += " WHERE (" + layer.subsetString() + ")"
                result = connection.executeSql(sql)
                empty_probe = "source_has_rows" if result else "source_empty"
            except Exception:
                # SQL/provider exceptions can embed credentials or the URI.
                raise RuntimeError(
                    tr("Nie udało się potwierdzić pustego odczytu MSSQL.")
                ) from None
        if count == 0 and (
            layer.providerType() != "mssql"
            or counters["received"] > 0
            or empty_probe == "source_empty"
        ):
            empty_verified = True
        read_complete = True
        stage = "writer_flush"
        if (
            not writer.flushBuffer()
            or writer.hasError() != QgsVectorFileWriter.WriterError.NoError
        ):
            raise RuntimeError(tr("Nie udało się zakończyć zapisu tabeli GeoPackage."))
    finally:
        if diagnostic:
            diagnostic.emit(
                "vector_iteration",
                job=table,
                stage=stage,
                read_complete=read_complete,
                vector_read_version=2,
                empty_read_verified=empty_verified,
                empty_source_probe=empty_probe,
                seconds=time.monotonic() - started_read,
                raised_errors=len(errors),
                old_provider_errors=len(old_errors),
                provider_errors=len(provider.errors()),
                provider_errors_changed=list(provider.errors()) != old_errors,
                iterator_closed=iterator.isClosed() if iterator is not None else None,
                writer_error=int(writer.hasError()) if writer is not None else None,
                **counters,
            )
        layer.raiseError.disconnect(errors.append)
        if iterator is not None:
            iterator.close()
        # QGIS 3.22 has no close() on this writer; destruction closes SQLite.
        del writer

    saved = QgsVectorLayer(f"{path}|layername={table}", layer.name(), "ogr")
    if not saved.isValid() or saved.featureCount() != count:
        raise RuntimeError(
            tr("Kontrola zapisanej tabeli wykazała brak lub niezgodną liczbę obiektów.")
        )
    if any(saved.fields().indexFromName(field.name()) < 0 for field in fields):
        raise RuntimeError(tr("Kontrola zapisanej tabeli wykazała brak atrybutów."))
    if read_details is not None:
        read_details.update(
            vector_read_version=2,
            empty_read_verified=empty_verified,
        )
    return count


def _remove_table(path, table):
    if not path.exists():
        return
    with closing(sqlite3.connect(path)) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name=?", (table,)
        ).fetchone():
            return
    database = ogr.Open(str(path), update=1)
    if database is None:
        raise RuntimeError(
            tr(
                (
                    "Nie można usunąć niepełnych danych. Archiwum nie zostanie "
                    "opublikowane."
                )
            )
        )
    try:
        # The driver's DROP TABLE also removes tile matrices/metadata for raster tables.
        gdal.ErrorReset()
        database.ExecuteSQL('DROP TABLE "' + table.replace('"', '""') + '"')
        if gdal.GetLastErrorType() >= gdal.CE_Failure:
            raise RuntimeError(tr("Nie udało się usunąć niepełnej tabeli GeoPackage."))
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
            raise RuntimeError(tr("Nie udało się utworzyć kopii projektu."))
    finally:
        project.setFileName(original_filename)
        project.setPresetHomePath(original_home)
        project.setFilePathStorage(original_path_type)
        project.setDirty(original_dirty)


def _local_project(snapshot, destination, records, resources=None):
    """Replace sources in XML before QGIS can try opening any remote provider."""
    with ZipFile(snapshot) as archive:
        qgs = next(name for name in archive.namelist() if name.endswith(".qgs"))
        root = ET.fromstring(archive.read(qgs))
    saved = {record["id"]: record for record in records if record.get("local_source")}
    empty_vectors = []
    for record in records:
        record.pop("output_name", None)
        if (
            record.get("status") == "saved"
            and record.get("method") == "vector"
            and record.get("feature_count") == 0
            and record.get("empty_read_verified") is True
            and record["id"] in saved
        ):
            record["output_name"] = record["name"] + tr("_nie-bylo-obiektow-w-zasiegu")
            empty_vectors.append(record)
    if empty_vectors:
        database = None
        with gdal.ExceptionMgr():
            try:
                database = gdal.OpenEx(
                    str(
                        destination.parent
                        / empty_vectors[0]["local_source"][2:].split("|", 1)[0]
                    ),
                    gdal.OF_VECTOR | gdal.OF_UPDATE,
                )
                identifiers = {
                    database.GetLayer(index).GetMetadataItem(
                        "IDENTIFIER"
                    ): database.GetLayer(index).GetName()
                    for index in range(database.GetLayerCount())
                }
                for record in empty_vectors:
                    identifier = record["output_name"]
                    counter = 1
                    while (
                        identifiers.get(identifier, record["table"]) != record["table"]
                    ):
                        tail = record["table"][6:14]
                        if counter > 1:
                            tail += f"-{counter}"
                        identifier = f"{record['output_name']} [{tail}]"
                        counter += 1
                    local = database.GetLayerByName(record["table"])
                    if local is None or local.SetMetadataItem("IDENTIFIER", identifier):
                        raise RuntimeError(
                            tr("Nie udało się zapisać nazwy pustej warstwy.")
                        )
                    identifiers[identifier] = record["table"]
                database.FlushCache()
            finally:
                local = database = None
    project_layers = root.find("projectlayers")
    if project_layers is not None:
        for element in list(project_layers):
            record = saved.get(element.findtext("id"))
            if record is None:
                project_layers.remove(element)
                continue
            if record["method"] == "raster_render":
                local_source = str(destination.parent / record["local_source"][2:])
                raster = QgsRasterLayer(local_source, record["name"], "gdal")
                if not raster.isValid():
                    raise RuntimeError(
                        tr("Nie można otworzyć zapisanego obrazu w QGIS.")
                    )
                renderer = QgsMultiBandColorRenderer(raster.dataProvider(), 1, 2, 3)
                renderer.setAlphaBand(4)
                raster.setRenderer(renderer)
                document = QDomDocument()
                node = document.createElement("maplayer")
                document.appendChild(node)
                context = QgsReadWriteContext()
                context.setPathResolver(QgsPathResolver(str(destination)))
                if not raster.writeLayerXml(node, document, context):
                    raise RuntimeError(tr("Nie udało się zapisać ustawień obrazu."))
                replacement = ET.fromstring(document.toString())
                replacement.find("id").text = record["id"]
                for attribute in (
                    "hasScaleBasedVisibilityFlag",
                    "minScale",
                    "maxScale",
                ):
                    if attribute in element.attrib:
                        replacement.set(attribute, element.get(attribute))
                for tag in ("blendMode", "layerflags"):
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
            element.find("datasource").text = record["local_source"]
            element.find("provider").text = record["local_provider"]
            if record.get("output_name"):
                element.find("layername").text = record["output_name"]
            if record["method"] == "raster_data":
                renderer = element.find("./pipe/rasterrenderer")
                if renderer is not None:
                    renderer.set("alphaBand", str(record["alpha_band"]))
            # The filter, joined columns and expression fields are already materialized.
            for tag in (
                "subsetstring",
                "vectorjoins",
                "expressionfields",
                "auxiliaryLayer",
                "dependencies",
                "dataDependencies",
            ):
                for child in list(element.findall(tag)):
                    element.remove(child)
    for parent in root.iter():
        for child in list(parent):
            if child.tag == "layer-tree-layer":
                record = saved.get(child.get("id"))
                if record is None:
                    parent.remove(child)
                else:
                    child.set("source", record["local_source"])
                    child.set("providerKey", record["local_provider"])
                    if record.get("output_name"):
                        child.set("name", record["output_name"])
            elif child.tag == "legendlayer":
                if any(
                    node.get("layerid") not in saved
                    for node in child.iter("legendlayerfile")
                ):
                    parent.remove(child)
                else:
                    for node in child.iter("legendlayerfile"):
                        record = saved.get(node.get("layerid"), {})
                        if record.get("output_name"):
                            child.set("name", record["output_name"])
            elif parent.tag in ("custom-order", "layerorder"):
                layer_id = child.get("id") or child.text
                if layer_id not in saved:
                    parent.remove(child)
    home = root.find("homePath")
    if home is not None:
        home.set("path", "")
    # Qt6 writes project property names as attributes instead of XML tags.
    for paths in root.findall("./properties/Paths/Absolute") + root.findall(
        "./properties/properties[@name='Paths']/properties[@name='Absolute']"
    ):
        paths.text = "false"
    # Project macros must not execute on opening an archive.
    for macros in root.findall("./properties/Macros") + root.findall(
        "./properties/properties[@name='Macros']"
    ):
        root.find("properties").remove(macros)
    resource_report = (
        resources.rewrite(root, records)
        if resources
        else {"copied_files": 0, "issues": []}
    )
    with ZipFile(
        destination, "w", compression=ZIP_DEFLATED, compresslevel=9
    ) as archive:
        archive.writestr(
            destination.with_suffix(".qgs").name,
            ET.tostring(root, encoding="utf-8", xml_declaration=True),
        )
        # Preserve QGIS's embedded style database and project attachments.
        with ZipFile(snapshot) as source:
            for name in source.namelist():
                if not name.endswith((".qgs", ".qgd")):
                    with (
                        source.open(name) as original,
                        archive.open(name, "w") as target,
                    ):
                        shutil.copyfileobj(original, target, length=1024 * 1024)

    check = QgsProject()
    try:
        if not check.read(
            str(destination),
            Qgis.ProjectReadFlag.DontResolveLayers
            | Qgis.ProjectReadFlag.DontStoreOriginalStyles
            | Qgis.ProjectReadFlag.DontLoadLayouts
            | Qgis.ProjectReadFlag.DontLoad3DViews,
        ):
            raise RuntimeError(tr("Nie można ponownie otworzyć projektu archiwalnego."))
        if set(check.mapLayers()) != set(saved):
            raise RuntimeError(tr("Projekt archiwalny ma niezgodną listę warstw."))
        for layer in check.mapLayers().values():
            if layer.providerType() not in ("ogr", "gdal"):
                raise RuntimeError(
                    tr("Projekt archiwalny nadal zawiera źródło zdalne.")
                )
    finally:
        check.clear()
    return resource_report


def _ready_records(records, parallel, cancelled, progress):
    """Consume ready work without blocking other layers behind one slow host."""
    pending = [r for r in records if r["status"] != "excluded"]
    while pending:
        if cancelled() and parallel:
            parallel.stop.set()
        index = next(
            (
                i
                for i, record in enumerate(pending)
                if not parallel
                or record["id"] not in parallel.futures
                or parallel.futures[record["id"]][0].done()
            ),
            None,
        )
        if index is not None:
            yield pending.pop(index)
        elif cancelled() and not any(
            parallel.futures[r["id"]][0].running()
            for r in pending
            if parallel and r["id"] in parallel.futures
        ):
            # Supervisors settle first: a process may already have written its
            # completed result while its Future is still being finalized.
            yield pending.pop(0)
        else:
            QCoreApplication.processEvents()
            progress(tr("Równoległe pobieranie map — oczekiwanie na warstwę…"))
            time.sleep(0.05)


def resume_manifest_path(folder):
    """Find current manifests while retaining archives written before 1.4.1."""
    folder = Path(folder)
    for directory in ("diagnostyka", "diagnostics", ""):
        candidate = folder / directory / "manifest.json"
        if candidate.is_file():
            return candidate
    return folder / "manifest.json"


def read_resume_manifest(folder):
    """Read archive settings without opening its project or remote sources."""
    try:
        manifest_path = resume_manifest_path(folder)
        manifest = json.loads(manifest_path.read_text("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError()
        manifest.setdefault("resources_directory", "zasoby")
        manifest.setdefault(
            "recovery_directory",
            (manifest_path.parent.relative_to(folder) / "download-state").as_posix(),
        )
        if (
            manifest["schema_version"] != 4
            or not isinstance(manifest["layers"], list)
            or not isinstance(manifest["sha256"], dict)
            or manifest.get("data_file", "dane.gpkg")
            not in ("dane.gpkg", "dane/dane.gpkg", "data/data.gpkg")
            or manifest["resources_directory"] not in ("zasoby", "resources")
            or manifest["recovery_directory"]
            not in (
                "download-state",
                "diagnostyka/download-state",
                "diagnostyka/stan-pobierania",
                "diagnostics/download-state",
            )
            or not manifest["area"]["wkt"]
            or not manifest["area"]["crs"]
            or not 0 <= manifest["zoom_min"] <= manifest["zoom_max"] <= 24
        ):
            raise ValueError()
        ids = [record["id"] for record in manifest["layers"]]
        if len(set(ids)) != len(ids):
            raise ValueError()
        return manifest
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            tr("Nieprawidłowy manifest archiwum do wznowienia.")
        ) from error


@contextmanager
def _archive_lock(folder):
    """Native process lock, including stale-lock recovery after a process dies."""
    if folder is None:
        yield None
        return
    lock = QLockFile(str(Path(folder) / ".archive.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise ValueError(
            tr("To archiwum jest używane przez inny proces QGIS. Spróbuj później.")
        )
    try:
        yield lock
    finally:
        lock.unlock()


@contextmanager
def _archive_workspace(destination):
    """Keep recovery data on exceptions; dispose only runtime source snapshots."""
    staging = Path(
        mkdtemp(prefix=destination.name + tr(".w-trakcie-"), dir=destination.parent)
    )
    (staging / tr("diagnostyka")).mkdir(mode=0o700)
    (staging / tr("dane")).mkdir(mode=0o700)
    with _archive_lock(staging) as lock:
        try:
            yield staging, lock
        finally:
            if staging.exists():
                shutil.rmtree(staging / ".workers", ignore_errors=True)
                (staging / "_source.qgz").unlink(missing_ok=True)


def _source_fingerprint(layer, *, canonical=True):
    """Keep a digest of source and rendering settings, never source credentials."""
    style = QgsMapLayerStyle()
    style.readFromLayer(layer)
    style_xml = style.xmlData()
    ET.fromstring(style_xml)  # Reject entities before canonicalize uses its parser.
    settings = [
        layer.source(),
        layer.providerType(),
        layer.crs().toWkt(),
        layer.subsetString() if isinstance(layer, QgsVectorLayer) else "",
        canonicalize(style_xml) if canonical else style_xml,
    ]
    return sha256(json.dumps(settings, ensure_ascii=False).encode()).hexdigest()


def _copy_resume(folder, manifest, staging, progress, cancelled):
    """Verify and copy only archive data; never use paths outside its folder."""
    folder = Path(folder).resolve()
    checkpoint = manifest.get("checkpoint") is True
    data_file = manifest.get("data_file", "dane.gpkg")
    resources_directory = manifest["resources_directory"]
    recovery_path = Path(manifest["recovery_directory"])
    files = dict(manifest["sha256"])
    if checkpoint:
        # An interrupted writer cannot hash a changing database. SQLite backup
        # recovers its journal and copies a consistent committed snapshot.
        files = {
            path.relative_to(folder).as_posix(): None
            for path in [folder / data_file, *(folder / resources_directory).rglob("*")]
            if path.is_file()
        }
        for record in manifest["layers"]:
            table = "layer_" + sha256(record["id"].encode()).hexdigest()[:24]
            cache = folder / recovery_path / table
            for name in ("raster.gpkg", "tiles.sqlite"):
                if (cache / name).is_file():
                    files[(cache / name).relative_to(folder).as_posix()] = None
    for relative, expected in files.items():
        path = Path(relative)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in relative
            or ":" in relative
            or not (folder / path).resolve().is_relative_to(folder)
        ):
            raise ValueError(tr("Manifest zawiera ścieżkę poza folderem archiwum."))
        is_cache = path.is_relative_to(recovery_path)
        is_resource = path.parts[:1] == (resources_directory,)
        if relative != data_file and not is_resource and not is_cache:
            continue
        if is_cache:
            cache_path = path.relative_to(recovery_path)
            if (
                len(cache_path.parts) != 2
                or not re.fullmatch(r"layer_[0-9a-f]{24}", cache_path.parts[0])
                or cache_path.name
                not in {
                    name + suffix
                    for name in ("raster.gpkg", "tiles.sqlite")
                    for suffix in ("", "-journal", "-wal", "-shm")
                }
            ):
                raise ValueError(tr("Nieprawidłowy manifest archiwum do wznowienia."))
            target = staging / tr("diagnostyka") / tr("stan-pobierania") / cache_path
        elif relative == data_file:
            target = staging / tr("dane/dane.gpkg")
        else:
            target = staging / tr("zasoby") / path.relative_to(resources_directory)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256()
        progress(tr("Sprawdzanie i kopiowanie danych poprzedniego archiwum…"))
        updated = time.monotonic()
        with _archive_lock((folder / path).parent if is_cache else None):
            if checkpoint and path.suffix in (".gpkg", ".sqlite"):

                def copying(status, remaining, total):
                    if cancelled():
                        raise InterruptedError()
                    progress(
                        tr("Sprawdzanie i kopiowanie danych poprzedniego archiwum…")
                    )

                with (
                    closing(
                        sqlite3.connect((folder / path).as_uri() + "?mode=rw", uri=True)
                    ) as source_db,
                    closing(sqlite3.connect(target)) as target_db,
                ):
                    source_db.backup(target_db, pages=256, progress=copying)
                    if (
                        target_db.execute("PRAGMA integrity_check").fetchone()[0]
                        != "ok"
                    ):
                        raise ValueError(
                            tr(
                                "Dane poprzedniego archiwum zmieniły się "
                                "lub są uszkodzone."
                            )
                        )
                with (folder / path).open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        if cancelled():
                            raise InterruptedError()
                        digest.update(chunk)
                with target.open("r+b") as output:
                    os.fsync(output.fileno())
            else:
                with (folder / path).open("rb") as source, target.open("wb") as output:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        if cancelled():
                            raise InterruptedError()
                        digest.update(chunk)
                        output.write(chunk)
                        if time.monotonic() - updated >= 0.1:
                            progress(
                                tr(
                                    "Sprawdzanie i kopiowanie danych "
                                    "poprzedniego archiwum…"
                                )
                            )
                            updated = time.monotonic()
                    output.flush()
                    os.fsync(output.fileno())
        if expected is not None and digest.hexdigest() != expected:
            raise ValueError(
                tr("Dane poprzedniego archiwum zmieniły się lub są uszkodzone.")
            )
        if checkpoint:
            manifest["sha256"][relative] = digest.hexdigest()
    for record in manifest["layers"]:
        if not record.get("local_source"):
            continue
        table = "layer_" + sha256(record["id"].encode()).hexdigest()[:24]
        method = record.get("method")
        if method == "vector":
            source = "./" + data_file + "|layername=" + table
            provider = "ogr"
        elif method == "raster_render":
            source = (
                "./"
                + data_file
                + "|option:TABLE="
                + table
                + "|option:ZOOM_LEVEL="
                + str(manifest["zoom_max"])
            )
            provider = "gdal"
        elif method == "raster_data":
            source = "./" + resources_directory + "/" + table + ".tif"
            provider = "gdal"
        else:
            raise ValueError(tr("Nieprawidłowy manifest archiwum do wznowienia."))
        filename = source[2:].split("|", 1)[0]
        if (
            (method != "raster_data" and record.get("table") != table)
            or record["local_source"] != source
            or record.get("local_provider") != provider
            or filename not in manifest["sha256"]
            or not (
                staging / tr("dane/dane.gpkg")
                if filename == data_file
                else staging
                / tr("zasoby")
                / Path(filename).relative_to(resources_directory)
            ).is_file()
        ):
            raise ValueError(tr("Brak poprawnych danych warstwy do wznowienia."))


def create_archive(
    project,
    selected_ids,
    area,
    area_crs,
    output_folder,
    cancelled=lambda: False,
    progress=lambda message: None,
    zoom_min=13,
    zoom_max=17,
    workers=1,
    per_server_limit=2,
    layer_status=lambda record, completed, total: None,
    worker_activity=lambda rows: None,
    adaptive=False,
    server_activity=lambda rows: None,
    resume_from=None,
    checkpoint_created=lambda folder: None,
):
    """Create a partial archive; return its published directory.

    Called on the QGIS main thread. The dialog is modal and its progress callback
    handles events at bounded intervals; live layers are never used by a worker.
    """
    resources = None
    if adaptive:
        resources = detect_resources()
        workers = recommend(resources["cpu"], resources["memory"], True)
        per_server_limit = min(MAX_WORKERS, max(1, 2 * resources["cpu"]))
        memory_text = (
            f"{resources['memory'] / 1024**3:.1f} GiB"
            if resources["memory"] is not None
            else tr("nie rozpoznano")
        )
        progress(
            tr(
                (
                    "Zasoby przy starcie: CPU {0}; dostępny RAM {1}; limit procesów "
                    "map {2}. Rezerwa RAM: 768 MiB."
                )
            ).format(resources["cpu"], memory_text, workers)
        )
    output_folder = Path(output_folder)
    if not adaptive and (
        not isinstance(per_server_limit, int) or not 1 <= per_server_limit <= 8
    ):
        raise ValueError(tr("Limit zadań na serwer musi wynosić od 1 do 8."))
    if not isinstance(workers, int) or not 1 <= workers <= 32:
        raise ValueError(tr("Wybierz od 1 do 32 równoległych procesów."))
    if not hasattr(gdal, "ExceptionMgr"):
        raise RuntimeError(
            tr("Archiwizacja wymaga GDAL 3.7 lub nowszego, dostarczanego z QGIS.")
        )
    if not output_folder.is_dir():
        raise ValueError(tr("Wybierz istniejący folder zapisu."))
    selected_ids = set(selected_ids)
    if not selected_ids:
        raise ValueError(tr("Zaznacz przynajmniej jedną warstwę."))
    if not (
        isinstance(zoom_min, int)
        and isinstance(zoom_max, int)
        and 0 <= zoom_min <= zoom_max <= 24
    ):
        raise ValueError(tr("Wybierz prawidłowy zakres zoomu od 0 do 24."))
    if (
        not area_crs.isValid()
        or area.isEmpty()
        or not area.isGeosValid()
        or area.area() <= 0
    ):
        raise ValueError(
            tr("Wybierz poprawny, niepusty obszar archiwizacji i układ współrzędnych.")
        )
    started = datetime.now().astimezone()
    stem = Path(project.fileName()).stem or project.title() or tr("Projekt")
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")[:120] or tr(
        "Projekt"
    )
    name = tr("{0}_archiwum_{1}").format(stem, started.strftime("%Y%m%d"))
    destination = output_folder / name
    if destination.exists():
        name += f"_{started:%H%M%S_%f}"
        destination = output_folder / name
    if destination.exists():
        raise FileExistsError(
            tr("Folder archiwum już istnieje. Wybierz inne miejsce zapisu.")
        )

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
        records.append(
            {
                "id": layer.id(),
                "name": layer.name(),
                "groups": groups,
                "provider": layer.providerType(),
                "status": "pending" if layer.id() in selected_ids else "excluded",
                "reason": ""
                if layer.id() in selected_ids
                else tr("Odznaczona przez użytkownika."),
            }
        )
    if selected_ids - known_ids:
        raise ValueError(
            tr("Lista warstw zmieniła się. Otwórz ponownie okno archiwizacji.")
        )

    previous = {}
    resume_manifest = None
    for record in records:
        if record["status"] != "excluded":
            record["source_fingerprint"] = _source_fingerprint(
                project.mapLayer(record["id"])
            )
            record["source_fingerprint_version"] = 2
    if resume_from is not None:
        resume_manifest = read_resume_manifest(resume_from)
        previous = {
            record["id"]: record
            for record in resume_manifest["layers"]
            if record["status"] != "excluded"
        }
        if (
            set(previous) != selected_ids
            or resume_manifest["project_crs"] != project.crs().authid()
            or resume_manifest["area"]["crs"] != area_crs.authid()
            or not area.isGeosEqual(QgsGeometry.fromWkt(resume_manifest["area"]["wkt"]))
            or resume_manifest["zoom_min"] != zoom_min
            or resume_manifest["zoom_max"] != zoom_max
        ):
            raise ValueError(
                tr("Wznawianie wymaga tych samych warstw, obszaru, CRS i zoomów.")
            )
        for record in records:
            old = previous.get(record["id"])
            if old is None:
                continue
            layer = project.mapLayer(record["id"])
            if isinstance(layer, QgsVectorLayer) and layer.isModified():
                raise ValueError(
                    tr(
                        "Warstwa ma niezapisane edycje. Utwórz nowe archiwum, "
                        "aby je zachować."
                    )
                )
            if old["provider"] != record["provider"] or (
                old.get("source_fingerprint")
                and old["source_fingerprint"]
                != (
                    record["source_fingerprint"]
                    if old.get("source_fingerprint_version") == 2
                    else _source_fingerprint(layer, canonical=False)
                )
            ):
                raise ValueError(
                    tr("Źródło lub styl warstwy zmieniły się. Utwórz nowe archiwum.")
                )
            recheck_empty = (
                old["provider"] in ("WFS", "mssql")
                and old.get("method") == "vector"
                and old.get("feature_count") == 0
                and (
                    old.get("vector_read_version") != 2
                    or old.get("empty_read_verified") is not True
                )
            )
            if (
                old["status"] in ("saved", "empty")
                and old.get("local_source")
                and not recheck_empty
            ):
                record.update(
                    old,
                    reused=True,
                    source_fingerprint=record["source_fingerprint"]
                    if old.get("source_fingerprint")
                    else None,
                    source_fingerprint_version=2,
                )
        if any(not record.get("source_fingerprint") for record in previous.values()):
            progress(
                tr(
                    "Starsze archiwum: sprawdzono ID warstw i zakres. "
                    "Zgodności źródeł i stylów nie można potwierdzić."
                )
            )

    total = len(selected_ids)
    completed = 0
    parallel = None
    notify = progress
    last_activity = 0.0
    network_monitor = None

    def progress(message):
        nonlocal last_activity
        notify(message)
        if network_monitor is not None:
            network_monitor.flush_interval()
        if parallel and time.monotonic() - last_activity >= 0.5:
            last_activity = time.monotonic()
            worker_activity(parallel.activity())
            if adaptive:
                server_activity(parallel.server_activity())

    with (
        _archive_lock(resume_from),
        _archive_workspace(destination) as (staging, workspace_lock),
        Diagnostics(
            staging / tr("diagnostyka") / tr("diagnostyka.jsonl")
        ) as diagnostic,
        PerformanceDiagnostics(diagnostic, "main", output_folder) as performance,
        ExitStack() as processes,
    ):
        if resume_manifest is not None:
            performance.set_phase("copy_previous")
            _copy_resume(resume_from, resume_manifest, staging, progress, cancelled)
        recovery_folder = staging / tr("diagnostyka") / tr("stan-pobierania")
        recovery_folder.mkdir(exist_ok=True, mode=0o700)
        checkpoint = {
            "schema_version": 4,
            "checkpoint": True,
            "data_file": tr("dane/dane.gpkg"),
            "resources_directory": tr("zasoby"),
            "recovery_directory": recovery_folder.relative_to(staging).as_posix(),
            "started_at": started.isoformat(),
            "project_crs": project.crs().authid(),
            "area": {"crs": area_crs.authid(), "wkt": area.asWkt()},
            "zoom_min": zoom_min,
            "zoom_max": zoom_max,
            "layers": records,
            "sha256": {},
        }

        def save_checkpoint(record=None):
            for entry in records:
                local_source = entry.get("local_source", "")
                for old_data in ("dane.gpkg", "dane/dane.gpkg", "data/data.gpkg"):
                    if local_source.startswith("./" + old_data + "|"):
                        entry["local_source"] = local_source.replace(
                            "./" + old_data + "|", "./" + tr("dane/dane.gpkg") + "|", 1
                        )
                        break
                for old_resources in ("zasoby", "resources"):
                    if local_source.startswith("./" + old_resources + "/"):
                        entry["local_source"] = local_source.replace(
                            "./" + old_resources + "/", "./" + tr("zasoby") + "/", 1
                        )
                        break
            # Workers write private cache databases. The final GPKG has one
            # writer, and it has closed its current operation at this boundary.
            if (staging / tr("dane/dane.gpkg")).exists():
                with (staging / tr("dane/dane.gpkg")).open("r+b") as stream:
                    os.fsync(stream.fileno())
            if (
                record
                and record.get("method") == "raster_data"
                and record.get("local_source")
            ):
                with (staging / record["local_source"][2:]).open("r+b") as stream:
                    os.fsync(stream.fileno())
            checkpoint["updated_at"] = datetime.now().astimezone().isoformat()
            write_state(
                staging / tr("diagnostyka") / "manifest.json",
                checkpoint,
                durable=True,
                diagnostic=diagnostic,
            )

        save_checkpoint()
        checkpoint_created(staging)
        progress(tr("Stan pobierania do wznowienia: {0}").format(staging))
        metadata = ConfigParser()
        metadata.read(Path(__file__).with_name("metadata.txt"), encoding="utf-8")
        diagnostic.emit(
            "configuration",
            plugin_version=metadata.get("general", "version"),
            project_crs=project.crs().authid(),
            zoom_min=zoom_min,
            zoom_max=zoom_max,
            qgis=Qgis.QGIS_VERSION,
            gdal=gdal.VersionInfo(),
            adaptive=adaptive,
            workers=workers,
            resources=resources,
            network=network_details(network_snapshot()),
            resumed=resume_from is not None,
        )

        network_monitor = NetworkDiagnostics(diagnostic)
        processes.callback(network_monitor.close)
        bounds = area.boundingBox()
        diagnostic.emit(
            "archive_plan",
            selected_layers=len(selected_ids),
            area_crs=area_crs.authid(),
            area_size=area.area(),
            bounding_width=bounds.width(),
            bounding_height=bounds.height(),
            area_vertices=area.constGet().nCoordinates(),
            layers=[
                {
                    "index": index,
                    "job": "layer_" + sha256(record["id"].encode()).hexdigest()[:24],
                    "provider": record["provider"],
                    "reused": bool(record.get("reused")),
                }
                for index, record in enumerate(
                    (r for r in records if r["status"] != "excluded"), 1
                )
            ],
        )
        try:
            diagnostic.emit("storage", free_bytes=shutil.disk_usage(staging).free)
        except OSError as error:
            diagnostic.error("storage_probe_error", error)
        snapshot = staging / "_source.qgz"
        progress(
            tr(
                "Przygotowanie kopii projektu. Wybrano {0} warstw; procesy map: {1}."
            ).format(total, workers)
        )
        performance.set_phase("snapshot")
        _snapshot_project(project, snapshot)
        database = staging / tr("dane/dane.gpkg")
        levels = None
        parallel = None
        if (adaptive or workers > 1) and any(
            r["status"] == "pending"
            and r["provider"] not in ("gdal", "memory", "ogr", "mssql", "WFS")
            for r in records
        ):
            progress(tr("Przygotowanie kolejki map dla osobnych procesów QGIS…"))
            performance.set_phase("prepare_workers")
            levels = zoom_levels(project, area, area_crs, zoom_min, zoom_max)
            parallel = processes.enter_context(
                RasterWorkers(
                    snapshot,
                    staging,
                    project,
                    records,
                    area,
                    area_crs,
                    levels,
                    workers,
                    per_server_limit,
                    adaptive,
                    diagnostic=diagnostic,
                    cpu=resources["cpu"] if resources else None,
                    cancelled=cancelled,
                    progress=progress,
                    recovery_folder=recovery_folder,
                )
            )
        indices = {
            r["id"]: i + 1
            for i, r in enumerate(r for r in records if r["status"] != "excluded")
        }
        performance.set_phase("waiting")
        for record in _ready_records(records, parallel, cancelled, progress):
            layer_index = indices[record["id"]]
            if record["status"] == "excluded":
                continue
            if record.get("reused"):
                completed += 1
                layer_status(dict(record), completed, total)
                progress(
                    tr("{0}: zachowano dane z poprzedniego archiwum.").format(
                        record["name"]
                    )
                )
                diagnostic.emit(
                    "layer_reused", layer_index=layer_index, status=record["status"]
                )
                continue
            job = "layer_" + sha256(record["id"].encode()).hexdigest()[:24]
            network_monitor.context = job
            diagnostic.emit(
                "layer_start",
                layer_index=layer_index,
                job=job,
                provider=record["provider"],
            )
            layer_status(dict(record), completed, total)
            progress(
                tr("Warstwa {0}/{1}: {2} — źródło {3}.").format(
                    completed + 1, total, record["name"], record["provider"]
                )
            )
            completed_map = parallel and parallel.completed(record["id"])
            if cancelled() and not completed_map:
                old = previous.get(record["id"], {})
                if old.get("local_source"):
                    record.update(old, reused=True, continuation_attempt="cancelled")
                else:
                    record.update(
                        status="cancelled",
                        reason=tr("Nie zapisano — archiwizacja została przerwana."),
                    )
                completed += 1
                layer_status(dict(record), completed, total)
                save_checkpoint()
                continue
            layer = project.mapLayer(record["id"])
            record["started_at"] = datetime.now().astimezone().isoformat()
            if not layer.isValid():
                record.update(
                    status="failed",
                    reason=tr("Źródło warstwy jest niedostępne lub nieprawidłowe."),
                )
            else:
                table = "layer_" + sha256(layer.id().encode()).hexdigest()[:24]
                record["attempts"] = []
                try:
                    if record["id"] in previous:
                        _remove_table(database, table)
                    if isinstance(layer, QgsVectorLayer):
                        try:
                            performance.set_phase("vector_write", job)
                            progress(
                                tr(
                                    (
                                        "{0}: odczyt danych i zapis geometrii oraz "
                                        "atrybutów…"
                                    )
                                ).format(layer.name())
                            )
                            if not database.exists():
                                initial = staging / ".vector-init.gpkg"
                                try:
                                    with gdal.config_option(
                                        "OGR_SQLITE_SYNCHRONOUS", "FULL"
                                    ):
                                        blank = ogr.GetDriverByName(
                                            "GPKG"
                                        ).CreateDataSource(str(initial))
                                        if blank is None:
                                            raise RuntimeError(
                                                tr(
                                                    "Nie można utworzyć "
                                                    "tabeli GeoPackage."
                                                )
                                            )
                                        blank = None
                                    with initial.open("r+b") as stream:
                                        os.fsync(stream.fileno())
                                    initial.replace(database)
                                finally:
                                    initial.unlink(missing_ok=True)
                            read_details = {}
                            count = _write_vector(
                                layer,
                                area,
                                area_crs,
                                project,
                                database,
                                table,
                                cancelled,
                                lambda count: progress(
                                    tr("{0}: zapisano {1} obiektów").format(
                                        layer.name(), count
                                    )
                                ),
                                diagnostic=diagnostic,
                                read_details=read_details,
                            )
                            diagnostic.emit(
                                "vector_read",
                                layer_index=layer_index,
                                provider=record["provider"],
                                features=count,
                                empty=count == 0,
                                provider_error_count=len(layer.dataProvider().errors()),
                            )
                            record.update(
                                status="saved",
                                table=table,
                                feature_count=count,
                                method="vector",
                                crs=layer.crs().authid(),
                                local_source="./"
                                + tr("dane/dane.gpkg")
                                + "|layername="
                                + table,
                                local_provider="ogr",
                                reason=tr("Zapisano dane i styl.")
                                if count
                                else tr("Poprawny odczyt: brak obiektów w obszarze."),
                                **read_details,
                            )
                            if (
                                count == 0
                                and layer.providerType() == "mssql"
                                and read_details.get("empty_read_verified") is not True
                            ):
                                record["reason"] = tr(
                                    "Zapisano pustą tabelę. MSSQL odpowiada, "
                                    "ale brak obiektów w obszarze wymaga "
                                    "sprawdzenia w oryginalnym projekcie."
                                )
                        except InterruptedError:
                            raise
                        except Exception as error:
                            diagnostic.error(
                                "layer_attempt_exception",
                                error,
                                layer_index=layer_index,
                                provider=record["provider"],
                            )
                            _remove_table(database, table)
                            record["attempts"].append(
                                {
                                    "method": "vector",
                                    "reason": tr(
                                        (
                                            "Eksport danych wektorowych nie "
                                            "powiódł się; próba zapisu obrazu."
                                        )
                                    ),
                                }
                            )
                            progress(
                                tr(
                                    (
                                        "{0}: zapis wektorów nie powiódł się. "
                                        "Próbuję zapisać wygląd mapy; atrybuty "
                                        "nie zostaną zachowane."
                                    )
                                ).format(layer.name())
                            )
                    elif (
                        isinstance(layer, QgsRasterLayer)
                        and layer.providerType() == "gdal"
                    ):
                        try:
                            performance.set_phase("raster_data", job)
                            progress(
                                tr("{0}: odczyt i kopiowanie wartości rastra…").format(
                                    layer.name()
                                )
                            )
                            record.update(
                                write_raster_data(
                                    layer,
                                    project,
                                    area,
                                    area_crs,
                                    staging,
                                    table,
                                    cancelled,
                                    progress,
                                )
                            )
                        except InterruptedError:
                            raise
                        except Exception as error:
                            diagnostic.error(
                                "layer_attempt_exception",
                                error,
                                layer_index=layer_index,
                                provider=record["provider"],
                            )
                            record["attempts"].append(
                                {
                                    "method": "raster_data",
                                    "reason": tr(
                                        (
                                            "Nie udało się zachować oryginalnych "
                                            "wartości rastra; próba zapisu "
                                            "obrazu."
                                        )
                                    ),
                                }
                            )
                            progress(
                                tr(
                                    (
                                        "{0}: nie udało się zachować wartości "
                                        "rastra. Próbuję zapisać wygląd mapy."
                                    )
                                ).format(layer.name())
                            )
                    if record["status"] != "saved":
                        if levels is None:
                            levels = zoom_levels(
                                project, area, area_crs, zoom_min, zoom_max
                            )
                        result = None
                        if parallel and layer.id() in parallel.futures:
                            try:
                                performance.set_phase("merge", job)
                                result = parallel.take(
                                    layer.id(),
                                    database,
                                    cancelled,
                                    progress,
                                    preserve_completed=True,
                                )
                            except InterruptedError:
                                raise
                            except Exception as error:
                                diagnostic.error(
                                    "layer_attempt_exception",
                                    error,
                                    layer_index=layer_index,
                                    provider=record["provider"],
                                )
                                if adaptive:
                                    # Never bypass host policy with a main-thread retry.
                                    raise
                                _remove_table(database, table)
                                record["attempts"].append(
                                    {
                                        "method": "parallel",
                                        "reason": tr(
                                            (
                                                "Proces pomocniczy nie zakończył "
                                                "zapisu; ponowiono w głównym "
                                                "QGIS."
                                            )
                                        ),
                                    }
                                )
                                progress(
                                    tr(
                                        (
                                            "{0}: proces pomocniczy zawiódł. "
                                            "Ponawiam zapis w głównym QGIS."
                                        )
                                    ).format(layer.name())
                                )
                        gate = None
                        try:
                            if result is None:
                                performance.set_phase("render_main", job)
                            if (
                                adaptive
                                and parallel
                                and result is None
                                and not isinstance(layer, QgsVectorLayer)
                            ):
                                gate = parallel.local_gate(layer, cancelled)
                            if result is None:
                                cache = recovery_folder / table
                                cache.mkdir(parents=True, exist_ok=True, mode=0o700)
                                with _archive_lock(cache):
                                    result = write_rendered_raster(
                                        layer,
                                        project,
                                        area,
                                        area_crs,
                                        cache / "raster.gpkg",
                                        table,
                                        levels,
                                        cancelled,
                                        progress,
                                        gate=gate,
                                        resume=(cache / "raster.gpkg").exists()
                                        or (cache / "tiles.sqlite").exists(),
                                        ledger_path=cache / "tiles.sqlite",
                                        legacy_retries=not adaptive,
                                    )
                                if result.get("local_source"):
                                    performance.set_phase("merge", job)
                                    merge_raster(
                                        cache / "raster.gpkg",
                                        database,
                                        table,
                                        cancelled,
                                    )
                            record.update(result)
                        finally:
                            if gate:
                                parallel.finish_local(
                                    gate, failed=record["status"] != "saved"
                                )
                        if record["status"] == "failed":
                            _remove_table(database, table)
                        if isinstance(layer, QgsVectorLayer):
                            record["reason"] += tr(
                                (
                                    " Zapis zastępczy: obraz nie zachowuje obiektów i "
                                    "atrybutów."
                                )
                            )
                except InterruptedError:
                    _remove_table(database, table)
                    record.update(
                        status="cancelled",
                        reason=tr(
                            (
                                "Przerwano zapis warstwy. Zapisane kafelki map "
                                "pozostają dostępne do wznowienia."
                            )
                        ),
                    )
                except WorkerError as error:
                    diagnostic.emit(
                        "worker_failure",
                        layer_index=layer_index,
                        details=error.details,
                    )
                    _remove_table(database, table)
                    record.update(
                        status="failed", reason=str(error), worker_error=error.details
                    )
                except Exception as error:
                    diagnostic.error("layer_exception", error, layer_index=layer_index)
                    _remove_table(database, table)
                    record.update(
                        status="failed",
                        reason=tr(
                            "Nie udało się zapisać danych ani obrazu tej warstwy."
                        ),
                    )
            old = previous.get(record["id"], {})
            if (
                old.get("method") == "raster_render"
                and old.get("local_source")
                and record["status"] not in ("saved", "empty")
            ):
                # A failed continuation must not replace a useful partial image.
                attempt = record["status"]
                digest = sha256()
                previous_data = resume_manifest.get("data_file", "dane.gpkg")
                with (Path(resume_from) / previous_data).open("rb") as source:
                    updated = time.monotonic()
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                        if time.monotonic() - updated >= 0.1:
                            progress(
                                tr("Sprawdzanie wcześniejszego obrazu częściowego…")
                            )
                            updated = time.monotonic()
                if digest.hexdigest() != resume_manifest["sha256"][previous_data]:
                    raise ValueError(
                        tr("Dane poprzedniego archiwum zmieniły się lub są uszkodzone.")
                    )
                _remove_table(database, old["table"])
                merge_raster(Path(resume_from) / previous_data, database, old["table"])
                record.clear()
                record.update(old, reused=True, continuation_attempt=attempt)
                record["reason"] += " " + tr(
                    "Kontynuacja nie ukończyła warstwy; zachowano wcześniejszy "
                    "obraz częściowy."
                )
            diagnostic.emit(
                "layer_result",
                layer_index=layer_index,
                provider=record["provider"],
                status=record["status"],
                feature_count=record.get("feature_count"),
            )
            if not record.get("reused"):
                record["finished_at"] = datetime.now().astimezone().isoformat()
            completed += 1
            save_checkpoint(record)
            if record["status"] in ("saved", "empty") and record.get("local_source"):
                # Keep the cache until the merged result and its checkpoint
                # are durable. A crash in between can only repeat a local merge.
                shutil.rmtree(recovery_folder / job, ignore_errors=True)
            layer_status(dict(record), completed, total)
            progress(f"{record['name']}: {record['reason']}")
            performance.set_phase("waiting")

        progress(
            tr("Kończenie zadań pomocniczych i porządkowanie plików tymczasowych…")
        )
        adaptive_report = parallel.adaptive_report() if adaptive and parallel else None
        diagnostic.emit("adaptive_summary", details=adaptive_report)
        if adaptive and parallel:
            server_activity(parallel.server_activity())
        peak_workers = parallel.peak_workers if parallel else workers
        final_workers = parallel.workers if parallel else workers
        processes.close()
        parallel = None
        network_monitor = None
        if not any(recovery_folder.iterdir()):
            recovery_folder.rmdir()
        save_checkpoint()
        worker_activity([])
        progress(
            tr("Zapisywanie projektu, lokalnych symboli, formularzy i załączników…")
        )
        performance.set_phase("resources")
        resource_report = _local_project(
            snapshot,
            staging / (name + ".qgz"),
            records,
            ProjectResources(project, staging, cancelled, progress),
        )
        progress(
            tr("Otwieranie zapisanych warstw — kontrola dostępności lokalnych danych…")
        )
        performance.set_phase("local_audit")
        local_failures = audit_local_layers(staging / (name + ".qgz"), records)
        snapshot.unlink()
        if database.exists():
            performance.set_phase("integrity_check")
            progress(tr("Kontrola integralności GeoPackage…"))
            with closing(sqlite3.connect(database)) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError(
                        tr("Kontrola integralności GeoPackage nie powiodła się.")
                    )
        manifest = {
            "schema_version": 4,
            "implementation_step": 3,
            "data_file": tr("dane/dane.gpkg"),
            "resources_directory": tr("zasoby"),
            "recovery_directory": recovery_folder.relative_to(staging).as_posix(),
            "status": "partial",
            "cancelled": cancelled(),
            "started_at": started.isoformat(),
            "finished_at": datetime.now().astimezone().isoformat(),
            "qgis_version": Qgis.QGIS_VERSION,
            "gdal_version": gdal.VersionInfo("RELEASE_NAME"),
            "project_crs": project.crs().authid(),
            "area": {"crs": area_crs.authid(), "wkt": area.asWkt()},
            "zoom_min": zoom_min,
            "zoom_max": zoom_max,
            "raster_levels": levels
            or (resume_manifest.get("raster_levels", []) if resume_manifest else []),
            "adaptive": adaptive_report,
            "parallel": {
                "mode": "adaptive" if adaptive else "fixed",
                "detected_resources": resources,
                "workers": workers,
                "peak_worker_budget": peak_workers,
                "final_worker_budget": final_workers,
                "per_server_limit": per_server_limit,
                "completed_in_workers": sum(
                    "worker_pid" in r and not r.get("reused") for r in records
                ),
            },
            "resources": resource_report,
            "local_layer_audit": {
                "passed": not local_failures,
                "failures": local_failures,
            },
            "limitations": [tr(text) for text in ARCHIVE_LIMITATIONS],
            "layers": records,
            "sha256": {},
        }
        if resume_manifest is not None:
            manifest["continuation"] = {
                "previous_started_at": resume_manifest["started_at"],
                "previous_manifest_sha256": sha256(
                    resume_manifest_path(resume_from).read_bytes()
                ).hexdigest(),
                "reused_layers": sum(bool(r.get("reused")) for r in records),
                "source_settings_verified": all(
                    r.get("source_fingerprint") for r in previous.values()
                ),
            }
        performance.set_phase("checksums")
        for path in sorted(staging.rglob("*")):
            relative = path.relative_to(staging)
            if relative.parts[:2] == (tr("diagnostyka"), tr("stan-pobierania")) and (
                len(relative.parts) != 4
                or path.name
                not in {
                    name + suffix
                    for name in ("raster.gpkg", "tiles.sqlite")
                    for suffix in ("", "-journal", "-wal", "-shm")
                }
            ):
                continue
            if path.is_file() and path.name not in (
                "manifest.json",
                tr("diagnostyka.jsonl"),
                ".archive.lock",
            ):
                progress(
                    tr("Kontrola pliku: {0} ({1:.1f} MiB)…").format(
                        path.relative_to(staging).as_posix(),
                        path.stat().st_size / 1048576,
                    )
                )
                digest = sha256()
                with path.open("rb") as stream:
                    last_update = time.monotonic()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        if time.monotonic() - last_update > 0.1:
                            progress(tr("Kontrola plików archiwum…"))
                            last_update = time.monotonic()
                manifest["sha256"][path.relative_to(staging).as_posix()] = (
                    digest.hexdigest()
                )
        manifest["cancelled"] = cancelled()
        manifest["finished_at"] = datetime.now().astimezone().isoformat()
        progress(tr("Zapisywanie manifestu i raportu z wynikami…"))
        performance.set_phase("report")
        write_state(
            staging / tr("diagnostyka") / "manifest.json",
            manifest,
            durable=True,
            diagnostic=diagnostic,
        )
        labels = {
            "saved": tr("Zapisano"),
            "failed": tr("Błąd"),
            "excluded": tr("Odznaczono"),
            "partial": tr("Obraz częściowy"),
            "empty": tr("Pusty zoom — do sprawdzenia"),
            "cancelled": tr("Przerwano"),
        }
        rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{escape(str(value))}</td>"
                for value in (
                    " / ".join(record["groups"]),
                    record.get("output_name", record["name"]),
                    labels[record["status"]],
                    record.get("feature_count", record.get("tile_count", "—")),
                    record["reason"],
                )
            )
            + "</tr>"
            for record in records
        )
        (staging / tr("raport.html")).write_text(
            tr(
                (
                    '<!doctype html><html lang="pl"><meta '
                    'charset="utf-8"><title>QGIS Project Snapshot — '
                    "raport</title><style>body{font-family:sans-serif;margin:2em}"
                    "table{border-collapse:collapse}td,th{border:1px solid "
                    "#aaa;padding:.5em;text-align:left}</style><h1>QGIS Project "
                    "Snapshot — wynik archiwizacji</h1><p>Sprawdź archiwum bez "
                    "dostępu do sieci.</p>"
                )
            )
            + tr(
                '<p>Otwórz <a href="{0}">projekt .qgz</a> w QGIS. '
                "Folder <b>dane</b> zawiera GeoPackage i pliki przyspieszające "
                "wyświetlanie. Folder <b>zasoby</b> zawiera dodatkowe pliki "
                "projektu, jeśli były potrzebne. Folder <b>diagnostyka</b> "
                "przechowuje szczegółowy raport techniczny, log i postęp "
                "do wznowienia. Zachowaj i przenoś cały folder archiwum.</p>"
            ).format(quote(name + ".qgz"))
            + "".join(f"<p>{escape(tr(text))}</p>" for text in ARCHIVE_LIMITATIONS)
            + (
                tr(
                    "<p>Kontynuacja: zachowano wcześniejsze dane {0} warstw. "
                    "Pozostałe wyniki pochodzą z bieżącego pobierania.</p>"
                ).format(manifest["continuation"]["reused_layers"])
                if resume_manifest is not None
                else ""
            )
            + tr(
                (
                    "<p>Zakres obrazów: zoom {0}–{1}. PNG: kompresja bezstratna "
                    "9, pełna przezroczystość.</p>"
                )
            ).format(zoom_min, zoom_max)
            + tr(
                (
                    "<p>Procesy: {0}. Skopiowane zasoby: {1}. Kontrola lokalnych "
                    "warstw: {2}.</p>"
                )
            ).format(
                workers,
                resource_report["copied_files"],
                tr("poprawna") if not local_failures else tr("wykryto problemy"),
            )
            + "".join(
                tr("<p>Do sprawdzenia — {0}: {1}</p>").format(
                    escape(item["owner"]), escape(item["reason"])
                )
                for item in resource_report["issues"]
            )
            + "".join(f"<p>{escape(message)}</p>" for message in local_failures)
            + tr(
                (
                    "<p>Początek: {0}<br>Koniec: {1}</p><p>Daty oznaczają czas "
                    "pobierania, a nie wspólny moment stanu wszystkich źródeł. "
                    "Przenoś cały folder "
                    "archiwum.</p><table><tr><th>Grupa</th><th>Warstwa</th><th>Wy"
                    "nik</th><th>Obiekty / kafelki</th><th>Informacja</th></tr>"
                )
            ).format(escape(manifest["started_at"]), escape(manifest["finished_at"]))
            + rows
            + tr("</table><details><summary>Szczegóły diagnostyczne</summary><pre>")
            + escape(json.dumps(manifest, ensure_ascii=False, indent=2))
            + "</pre></details></html>",
            encoding="utf-8",
        )
        if destination.exists():
            raise FileExistsError(
                tr("Folder docelowy już istnieje. Nie nadpisano archiwum.")
            )
        progress(tr("Udostępnianie gotowego folderu archiwum…"))
        for index, record in enumerate(
            (r for r in records if r["status"] != "excluded"), 1
        ):
            raster = record.get("raster", {})
            diagnostic.emit(
                "layer_summary",
                layer_index=index,
                job="layer_" + sha256(record["id"].encode()).hexdigest()[:24],
                status=record["status"],
                method=record.get("method"),
                reused=bool(record.get("reused")),
                feature_count=record.get("feature_count"),
                tile_count=record.get("tile_count"),
                raster_size=record.get("raster_size"),
                overview_factors=record.get("overview_factors"),
                overview_status=record.get("overview_status"),
                levels=[
                    {
                        key: level[key]
                        for key in ("zoom", "total", "nonempty", "empty", "failed")
                        if key in level
                    }
                    for level in raster.get("levels", [])
                ],
                stopped_early=raster.get("stopped_early"),
                deferred=raster.get("deferred"),
                repair_attempts=raster.get("repair_attempts"),
                repaired=raster.get("repaired"),
                raw_empty=raster.get("raw_empty"),
                raw_nonempty=raster.get("raw_nonempty"),
                masked_out=raster.get("masked_out"),
                timing_seconds=raster.get("timing_seconds"),
            )
        performance.set_phase("publish")
        diagnostic.emit(
            "archive_result", status=manifest["status"], cancelled=manifest["cancelled"]
        )
        with diagnostic.lock:
            workspace_lock.unlock()
            staging.rename(destination)
            diagnostic.path = destination / tr("diagnostyka") / tr("diagnostyka.jsonl")
    return destination
