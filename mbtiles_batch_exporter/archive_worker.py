"""Private process entry point: no live desktop QGIS objects cross processes."""
from .i18n import tr
import json
from datetime import datetime
import os
from pathlib import Path
import sys
import time


def main():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsGeometry, QgsProject
    from mbtiles_batch_exporter.raster_archive import write_rendered_raster

    folder = Path(sys.argv[1])
    last_progress = 0.0
    server_warnings = []
    last_message = ''

    def progress(message):
        nonlocal last_progress, last_message
        warning = message.startswith(('[HTTP 429]', '[HTTP 503]'))
        if warning and message not in server_warnings:
            server_warnings.append(message)
        if not warning:
            last_message = message
            if time.monotonic() - last_progress < 0.25:
                return
            last_progress = time.monotonic()
        # A single atomic snapshot, not an unbounded log or a pipe which can fill.
        try:
            temporary = folder / 'progress.new'
            temporary.write_text(json.dumps({'message': last_message or message, 'updated_at': time.time(), 'server_warnings': server_warnings}), encoding='utf-8')
            temporary.replace(folder / 'progress.json')
        except OSError:
            pass  # Progress reporting must never make a successful export fail.

    progress(tr('Uruchamianie QGIS…'))
    parameters = json.loads((folder / 'input.json').read_text())
    app = QgsApplication([], False)
    app.initQgis()
    app.setMaxThreads(1)
    from .adaptive import WorkerGate
    from qgis.PyQt.QtCore import QCoreApplication
    gate = WorkerGate(folder, lambda: (folder / "cancel").exists(), QCoreApplication.processEvents) if parameters.get("adaptive") else None
    project = QgsProject()
    try:
        started = datetime.now().astimezone().isoformat()
        progress(tr('Otwieranie źródła mapy…'))
        if not project.read(str(folder / 'source.qgs')):
            raise RuntimeError(tr('Nie można odczytać kopii warstwy.'))
        layer = project.mapLayer(parameters['layer_id'])
        if layer is None or not layer.isValid():
            raise RuntimeError(tr('Źródło nie jest dostępne w osobnym procesie.'))
        result = write_rendered_raster(
            layer, project, QgsGeometry.fromWkt(parameters['area']),
            QgsCoordinateReferenceSystem(parameters['area_crs']), folder / 'raster.gpkg',
            parameters['table'], parameters['levels'], lambda: (folder / 'cancel').exists(),
            progress, gate=gate,
        )
        result['worker_pid'] = os.getpid()
        result['started_at'] = started
        result['download_finished_at'] = datetime.now().astimezone().isoformat()
        (folder / 'result.json').write_text(json.dumps(result), encoding='utf-8')
    except InterruptedError:
        return 2
    except Exception:
        # Provider messages can contain credentials; do not return their raw text.
        return 1
    finally:
        if gate:
            gate.close()
        project.clear()
    # Process exit releases providers. exitQgis can race deferred Qt deletion.
    return 0


if __name__ == '__main__':
    sys.exit(main())
