# SPDX-License-Identifier: GPL-2.0-only

"""Private process entry point: no live desktop QGIS objects cross processes."""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .adaptive import write_state
from .diagnostics import (
    Diagnostics,
    NetworkDiagnostics,
    PerformanceDiagnostics,
    network_details,
)
from .i18n import tr


def main():
    folder = Path(sys.argv[1])
    diagnostic = Diagnostics(folder / "diagnostic.jsonl")
    diagnostic.emit("worker_bootstrap")
    performance = PerformanceDiagnostics(diagnostic, "worker")
    performance.__enter__()
    stage = "bootstrap"
    network_error = {}
    project = gate = network_monitor = None
    last_progress = 0.0
    server_warnings = []
    last_message = ""

    def progress(message):
        nonlocal last_progress, last_message
        if network_monitor:
            network_monitor.flush_interval()
        warning = message.startswith(("[HTTP 429]", "[HTTP 503]"))
        if warning and message not in server_warnings:
            server_warnings.append(message)
        if not warning:
            last_message = message
            if time.monotonic() - last_progress < 0.25:
                return
            last_progress = time.monotonic()
        try:
            write_state(
                folder / "progress.json",
                {
                    "message": last_message or message,
                    "stage": stage,
                    "updated_at": time.time(),
                    "server_warnings": server_warnings,
                },
                diagnostic=diagnostic,
            )
        except OSError:
            pass

    try:
        network = json.load(sys.stdin)
        progress(tr("Uruchamianie QGIS…"))
        from qgis.core import (
            Qgis,
            QgsApplication,
            QgsCoordinateReferenceSystem,
            QgsGeometry,
            QgsProject,
        )
        from qgis.PyQt.QtCore import QCoreApplication

        from .adaptive import WorkerGate
        from .raster_archive import write_rendered_raster
        from .worker_network import configure_network

        parameters = json.loads((folder / "input.json").read_text())
        app = QgsApplication([], False)
        app.initQgis()
        app.setMaxThreads(1)
        diagnostic.emit(
            "worker_environment",
            qgis=Qgis.QGIS_VERSION,
            python=".".join(map(str, sys.version_info[:3])),
        )
        stage = "network_setup"
        performance.set_phase(stage)
        configure_network(network, diagnostic)
        diagnostic.emit("worker_network_configuration", **network_details(network))

        network_monitor = NetworkDiagnostics(diagnostic)
        network_monitor.context = parameters["table"]
        network_error = network_monitor.last_error
        gate = (
            WorkerGate(
                folder,
                lambda: (folder / "cancel").exists(),
                QCoreApplication.processEvents,
                diagnostic=diagnostic,
            )
            if parameters.get("adaptive")
            else None
        )
        project = QgsProject()
        started = datetime.now().astimezone().isoformat()
        stage = "source_open"
        performance.set_phase(stage, parameters["table"])
        progress(tr("Otwieranie źródła mapy…"))
        if not project.read(str(folder / "source.qgs")):
            raise RuntimeError()
        layer = project.mapLayer(parameters["layer_id"])
        if layer is None or not layer.isValid():
            raise RuntimeError()
        diagnostic.emit(
            "source_opened",
            valid=layer.isValid(),
            provider=layer.providerType(),
            crs=layer.crs().authid(),
            scale_visibility=layer.hasScaleBasedVisibility(),
            minimum_scale=layer.minimumScale(),
            maximum_scale=layer.maximumScale(),
        )
        stage = "render"
        performance.set_phase(stage, parameters["table"])
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
        raster_stats = result.get("raster", {})
        diagnostic.emit(
            "render_result",
            status=result.get("status"),
            levels=[
                {
                    key: level[key]
                    for key in ("zoom", "nonempty", "empty", "failed", "total")
                    if key in level
                }
                for level in raster_stats.get("levels", [])
            ],
            stopped_early=raster_stats.get("stopped_early"),
            retries=raster_stats.get("retries"),
            raw_empty=raster_stats.get("raw_empty"),
            raw_nonempty=raster_stats.get("raw_nonempty"),
            masked_out=raster_stats.get("masked_out"),
            timing_seconds=raster_stats.get("timing_seconds"),
        )
        result["worker_pid"] = os.getpid()
        result["started_at"] = started
        result["download_finished_at"] = datetime.now().astimezone().isoformat()
        result["worker_network"] = network_error
        stage = "result_write"
        performance.set_phase(stage, parameters["table"])
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
        performance.__exit__(None, None, None)
        if network_monitor:
            network_monitor.close()
        if gate:
            gate.close()
        if project:
            project.clear()
            # Destroy project styles while QgsApplication still owns its models.
            project = None
    return 0


if __name__ == "__main__":
    sys.exit(main())
