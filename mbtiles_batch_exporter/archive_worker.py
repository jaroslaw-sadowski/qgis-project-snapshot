"""Private process entry point: no live desktop QGIS objects cross processes."""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .diagnostics import Diagnostics, network_details
from .i18n import tr


def main():
    folder = Path(sys.argv[1])
    diagnostic = Diagnostics(folder / "diagnostic.jsonl")
    diagnostic.emit("worker_bootstrap")
    stage = "bootstrap"
    network_error = {}
    project = gate = None
    last_progress = 0.0
    server_warnings = []
    last_message = ""

    def progress(message):
        nonlocal last_progress, last_message
        warning = message.startswith(("[HTTP 429]", "[HTTP 503]"))
        if warning and message not in server_warnings:
            server_warnings.append(message)
        if not warning:
            last_message = message
            if time.monotonic() - last_progress < 0.25:
                return
            last_progress = time.monotonic()
        try:
            temporary = folder / "progress.new"
            temporary.write_text(
                json.dumps(
                    {
                        "message": last_message or message,
                        "stage": stage,
                        "updated_at": time.time(),
                        "server_warnings": server_warnings,
                    }
                ),
                encoding="utf-8",
            )
            temporary.replace(folder / "progress.json")
        except OSError:
            pass

    try:
        network = json.load(sys.stdin)
        progress(tr("Uruchamianie QGIS…"))
        from qgis.core import (
            QgsApplication,
            QgsCoordinateReferenceSystem,
            QgsGeometry,
            QgsNetworkAccessManager,
            QgsNetworkReplyContent,
            QgsProject,
        )
        from qgis.PyQt.QtCore import QCoreApplication
        from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

        from .adaptive import WorkerGate
        from .raster_archive import write_rendered_raster
        from .worker_network import configure_network

        parameters = json.loads((folder / "input.json").read_text())
        app = QgsApplication([], False)
        app.initQgis()
        app.setMaxThreads(1)
        stage = "network_setup"
        configure_network(network, diagnostic)
        diagnostic.emit("worker_network_configuration", **network_details(network))

        def finished(reply):
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NoError or (status and status >= 400):
                network_error.update(http_status=status, qt_error=int(reply.error()))
                diagnostic.emit("network_error", stage=stage, **network_error)

        QgsNetworkAccessManager.instance().finished[QgsNetworkReplyContent].connect(
            finished
        )
        gate = (
            WorkerGate(
                folder,
                lambda: (folder / "cancel").exists(),
                QCoreApplication.processEvents,
            )
            if parameters.get("adaptive")
            else None
        )
        project = QgsProject()
        started = datetime.now().astimezone().isoformat()
        stage = "source_open"
        progress(tr("Otwieranie źródła mapy…"))
        if not project.read(str(folder / "source.qgs")):
            raise RuntimeError()
        layer = project.mapLayer(parameters["layer_id"])
        if layer is None or not layer.isValid():
            raise RuntimeError()
        diagnostic.emit("source_opened", valid=layer.isValid())
        stage = "render"
        result = write_rendered_raster(
            layer,
            project,
            QgsGeometry.fromWkt(parameters["area"]),
            QgsCoordinateReferenceSystem(parameters["area_crs"]),
            folder / "raster.gpkg",
            parameters["table"],
            parameters["levels"],
            lambda: (folder / "cancel").exists(),
            progress,
            gate=gate,
        )
        result["worker_pid"] = os.getpid()
        result["started_at"] = started
        result["download_finished_at"] = datetime.now().astimezone().isoformat()
        result["worker_network"] = network_error
        stage = "result_write"
        (folder / "result.json").write_text(json.dumps(result), encoding="utf-8")
    except InterruptedError:
        diagnostic.emit("worker_cancelled", stage=stage)
        return 2
    except Exception as error:
        diagnostic.error("worker_exception", error, stage=stage)
        # Codes only: provider exceptions may contain URLs and credentials.
        (folder / "error.json").write_text(
            json.dumps(
                {
                    "stage": stage,
                    **network_error,
                }
            ),
            encoding="utf-8",
        )
        return 1
    finally:
        if gate:
            gate.close()
        if project:
            project.clear()
            # Destroy project styles while QgsApplication still owns its models.
            project = None
    return 0


if __name__ == "__main__":
    sys.exit(main())
