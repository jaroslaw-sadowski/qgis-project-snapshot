"""Private process entry point: no live desktop QGIS objects cross processes."""
import json
from datetime import datetime
import os
from pathlib import Path
import sys


def main():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsGeometry, QgsProject
    from mbtiles_batch_exporter.raster_archive import write_rendered_raster

    folder = Path(sys.argv[1])
    parameters = json.loads((folder / 'input.json').read_text())
    app = QgsApplication([], False)
    app.initQgis()
    app.setMaxThreads(1)
    project = QgsProject()
    try:
        started = datetime.now().astimezone().isoformat()
        if not project.read(str(folder / 'source.qgs')):
            raise RuntimeError('Nie można odczytać kopii warstwy.')
        layer = project.mapLayer(parameters['layer_id'])
        if layer is None or not layer.isValid():
            raise RuntimeError('Źródło nie jest dostępne w osobnym procesie.')
        result = write_rendered_raster(
            layer, project, QgsGeometry.fromWkt(parameters['area']),
            QgsCoordinateReferenceSystem(parameters['area_crs']), folder / 'raster.gpkg',
            parameters['table'], parameters['levels'], lambda: (folder / 'cancel').exists(),
            lambda message: None,
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
        project.clear()
    # Process exit releases providers. exitQgis can race deferred Qt deletion.
    return 0


if __name__ == '__main__':
    sys.exit(main())
