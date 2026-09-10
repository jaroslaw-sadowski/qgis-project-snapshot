# SPDX-License-Identifier: GPL-2.0-only

"""Bounded process workers; threads supervise processes, never QGIS objects."""

import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from threading import Condition, Event, Thread
from zipfile import ZipFile

from osgeo import gdal
from qgis.core import Qgis, QgsDataSourceUri, QgsVectorLayer
from qgis.PyQt.QtCore import QCoreApplication, QUrl

from .adaptive import PROTOCOL, HostPolicy, WorkerGate, write_state
from .i18n import language, tr
from .resources import (
    MEMORY_PER_WORKER,
    MEMORY_RESERVE,
    MIN_WORKER_MEMORY,
    available_memory,
    recommend,
)
from .worker_network import network_snapshot


def merge_raster(source, destination, table, cancelled=lambda: False):
    """Copy compressed PNG bytes unchanged; only the parent writes the final DB."""
    if not destination.exists():
        try:
            with source.open("rb") as original, destination.open("wb") as target:
                for chunk in iter(lambda: original.read(1024 * 1024), b""):
                    if cancelled():
                        raise InterruptedError()
                    target.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return
    with gdal.ExceptionMgr():
        raster = gdal.OpenEx(
            str(source), gdal.OF_RASTER, open_options=["TABLE=" + table]
        )
        target = gdal.GetDriverByName("GPKG").Create(
            str(destination),
            raster.RasterXSize,
            raster.RasterYSize,
            4,
            gdal.GDT_Byte,
            options=[
                "RASTER_TABLE=" + table,
                "APPEND_SUBDATASET=YES",
                "TILE_FORMAT=PNG",
                "ZLEVEL=9",
            ],
        )
        target.SetProjection(raster.GetProjection())
        target.SetGeoTransform(raster.GetGeoTransform())
        target.FlushCache()
        raster = target = None
    # Names originate exclusively from sha256(layer.id()), never from layer names.
    with closing(sqlite3.connect(destination)) as connection:
        connection.set_progress_handler(lambda: int(cancelled()), 10000)
        connection.execute("ATTACH DATABASE ? AS incoming", (str(source),))
        with connection:
            connection.execute(
                "DELETE FROM gpkg_tile_matrix WHERE table_name=?", (table,)
            )
            connection.execute(
                (
                    "INSERT INTO gpkg_tile_matrix SELECT * FROM "
                    "incoming.gpkg_tile_matrix WHERE table_name=?"
                ),
                (table,),
            )
            connection.execute(
                f'INSERT INTO "{table}" SELECT * FROM incoming."{table}"'
            )
            bounds = connection.execute(
                (
                    "SELECT min_x,min_y,max_x,max_y FROM incoming.gpkg_contents "
                    "WHERE table_name=?"
                ),
                (table,),
            ).fetchone()
            connection.execute(
                (
                    "UPDATE gpkg_contents SET min_x=?,min_y=?,max_x=?,max_y=? "
                    "WHERE table_name=?"
                ),
                (*bounds, table),
            )
            bounds = connection.execute(
                (
                    "SELECT min_x,min_y,max_x,max_y FROM "
                    "incoming.gpkg_tile_matrix_set WHERE table_name=?"
                ),
                (table,),
            ).fetchone()
            connection.execute(
                (
                    "UPDATE gpkg_tile_matrix_set SET "
                    "min_x=?,min_y=?,max_x=?,max_y=? WHERE table_name=?"
                ),
                (*bounds, table),
            )
        connection.execute("DETACH DATABASE incoming")


class WorkerError(RuntimeError):
    """Only locally generated diagnostics, never raw provider exception text."""

    def __init__(self, stage, exit_code=None, http_status=None, qt_error=None):
        self.details = dict(
            stage=stage, exit_code=exit_code, http_status=http_status, qt_error=qt_error
        )
        if stage == "coordinator":
            reason = tr("Koordynator pobierania zakończył pracę z błędem.")
        elif http_status == 407 or qt_error == 105:
            reason = tr(
                "Proxy odrzuciło uwierzytelnianie. Sprawdź konfigurację proxy w QGIS."
            )
        elif qt_error in (101, 102, 103, 104, 199):
            reason = tr("Nie można połączyć się z proxy skonfigurowanym w QGIS.")
        elif qt_error == 6:
            reason = tr(
                (
                    "Nie udało się zweryfikować połączenia TLS. Sprawdź zaufane "
                    "certyfikaty QGIS i systemu."
                )
            )
        else:
            reason = tr(
                (
                    "Proces mapowy nie zakończył pracy. Etap: {0}; kod "
                    "zakończenia: {1}; HTTP: {2}; kod sieci Qt: {3}."
                )
            ).format(stage, exit_code, http_status, qt_error)
        super().__init__(reason)


class RasterWorkers:
    """Context manager owns process lifetime, private files and cancellation."""

    def __init__(
        self,
        snapshot,
        staging,
        project,
        records,
        area,
        crs,
        levels,
        workers,
        per_server_limit=2,
        adaptive=False,
        diagnostic=None,
        cpu=None,
        cancelled=lambda: False,
        progress=lambda message: None,
    ):
        self.diagnostic = diagnostic
        self.cancelled = cancelled
        self.progress = progress
        self.network = network_snapshot()
        self.folder = staging / ".workers"
        self.folder.mkdir(mode=0o700)
        self.stop = Event()
        self.cpu = cpu or max(1, workers)
        self.ceiling = min(32, 2 * self.cpu) if adaptive else workers
        self.peak_workers = workers
        self.memory_available = None
        self.worker_memory = MEMORY_PER_WORKER
        self.worker_peak_memory = 0
        self.reserved_growth = 0
        self.pool = ThreadPoolExecutor(
            max_workers=self.ceiling, thread_name_prefix="archive-process"
        )
        self.futures = {}
        self.parameters = (snapshot, project, records, area, crs, levels)
        self.active_hosts = {}
        self.queue = []
        self.condition = Condition()
        self.workers = workers
        self.launch_slots = workers
        self.per_server_limit = self.ceiling if adaptive else per_server_limit
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
                root = ET.fromstring(
                    archive.read(
                        next(n for n in archive.namelist() if n.endswith(".qgs"))
                    )
                )
            # Strip shared heavy layer XML once, instead of copying every source
            # definition for every worker (quadratic for large projects).
            layer_xml = {
                element.findtext("id"): element
                for element in root.find("projectlayers")
            }
            tree_xml = {
                element.get("id"): element for element in root.iter("layer-tree-layer")
            }
            for element in list(root.find("projectlayers")):
                root.find("projectlayers").remove(element)
            for parent in root.iter():
                for child in list(parent):
                    if child.tag == "layer-tree-layer":
                        parent.remove(child)
            macros = root.find("./properties/Macros")
            if macros is not None:
                root.find("properties").remove(macros)
            # Interleave servers so a long queue from one host cannot occupy
            # every supervising thread while other servers remain idle.
            queues = {}
            for record in records:
                layer = project.mapLayer(record["id"])
                # Live vector edits and auth credentials remain in the main process.
                if (
                    record["status"] != "pending"
                    or not layer.isValid()
                    or isinstance(layer, QgsVectorLayer)
                    or layer.providerType() == "gdal"
                ):
                    continue
                if "authcfg=" in layer.source():
                    continue
                uri = QgsDataSourceUri()
                uri.setEncodedUri(layer.source())
                host = QUrl(uri.param("url")).host() or layer.providerType()
                queues.setdefault(host, deque()).append(record)
            ordered = []
            while any(queues.values()):
                for host, queue in queues.items():
                    if queue:
                        ordered.append((host, queue.popleft()))
            last_pump = 0.0
            for host, record in ordered:
                if self.cancelled():
                    self.stop.set()
                    break
                if time.monotonic() - last_pump >= 0.1:
                    self.progress(
                        tr("Przygotowanie kolejki map dla osobnych procesów QGIS…")
                    )
                    QCoreApplication.processEvents()
                    last_pump = time.monotonic()
                layer = project.mapLayer(record["id"])
                table = "layer_" + sha256(layer.id().encode()).hexdigest()[:24]
                folder = self.folder / table
                folder.mkdir(mode=0o700)
                isolated = deepcopy(root)
                isolated.find("projectlayers").append(deepcopy(layer_xml[layer.id()]))
                if (
                    layer.id() in tree_xml
                    and isolated.find("layer-tree-group") is not None
                ):
                    isolated.find("layer-tree-group").append(
                        deepcopy(tree_xml[layer.id()])
                    )
                (folder / "source.qgs").write_bytes(
                    ET.tostring(isolated, encoding="utf-8")
                )
                (folder / "input.json").write_text(
                    json.dumps(
                        {
                            "layer_id": layer.id(),
                            "table": table,
                            "area": area.asWkt(),
                            "area_crs": crs.toWkt(Qgis.CrsWktVariant.Wkt2_2019),
                            "levels": levels,
                            "adaptive": self.adaptive,
                        }
                    ),
                    encoding="utf-8",
                )
                if self.adaptive:
                    self._register(host, folder)
                future = Future()
                self.futures[layer.id()] = (future, folder)
                self.queue.append((host, future, folder))
            if self.adaptive:
                self.coordinator = Thread(
                    target=self._coordinate, name="archive-coordinator", daemon=True
                )
                self.coordinator.start()
            for _ in range(min(self.ceiling, len(self.queue))):
                self.pool.submit(self._work_loop)
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def _register(self, host, folder):
        self.policies.setdefault(
            host,
            HostPolicy(host, self.per_server_limit, window_started=time.monotonic()),
        )
        self.jobs[folder.name] = {
            "host": host,
            "folder": folder,
            "active": False,
            "ack": 0,
            "counts": {},
            "state": {},
        }
        write_state(
            folder / "control.json",
            {
                "version": PROTOCOL,
                "allowed": False,
                "generation": 0,
                "expires": time.monotonic() + 2,
                "ack": 0,
            },
        )

    def _read_job(self, job, now):
        try:
            state = json.loads(
                (job["folder"] / "telemetry.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return
        if state.get("version") != PROTOCOL:
            return
        policy = self.policies[job["host"]]
        job["state"] = state
        for generation, count in state.get("counts", {}).items():
            delta = count - job["counts"].get(generation, 0)
            if delta > 0:
                policy.success(delta, now, int(generation))
                job["counts"][generation] = count
        for event in state.get("events", []):
            if event["sequence"] <= job["ack"]:
                continue
            if event["status"] == "success":
                policy.success(1, now, event["generation"], probe=event["probe"])
            else:
                policy.failure(
                    event["status"],
                    event["delay"],
                    now,
                    event["generation"],
                    probe=event["probe"],
                )
            job["ack"] = event["sequence"]

    def _coordinate(self):
        try:
            while not self.stop.is_set():
                with self.condition:
                    now = time.monotonic()
                    for job in self.jobs.values():
                        if job["active"]:
                            self._read_job(job, now)
                    if now >= self.next_memory_check:
                        memory = available_memory()
                        self.memory_available = memory
                        process_jobs = [
                            j
                            for name, j in self.jobs.items()
                            if not name.startswith("local_")
                        ]
                        for job in process_jobs:
                            sample = job["state"].get("memory", {})
                            peak = sample.get("peak")
                            if isinstance(peak, int) and peak > 0:
                                self.worker_peak_memory = max(
                                    self.worker_peak_memory, peak
                                )
                        estimate = (
                            max(
                                MIN_WORKER_MEMORY,
                                math.ceil(self.worker_peak_memory * 1.5),
                            )
                            if self.worker_peak_memory
                            else MEMORY_PER_WORKER
                        )
                        self.reserved_growth = 0
                        for job in process_jobs:
                            if not job["active"]:
                                continue
                            rss = job["state"].get("memory", {}).get("rss")
                            # Unknown startup still owns its full launch budget.
                            # A measured worker can release its initial excess,
                            # but reserves room to grow to the learned estimate.
                            self.reserved_growth += (
                                max(0, estimate - rss)
                                if isinstance(rss, int) and rss > 0
                                else max(
                                    estimate,
                                    job.get("memory_budget", MEMORY_PER_WORKER),
                                )
                            )
                        budget = recommend(
                            self.cpu,
                            memory,
                            True,
                            active_workers=sum(self.active_hosts.values()),
                            worker_memory=estimate,
                            reserved_growth=self.reserved_growth,
                        )
                        # A sample grants a finite number of new starts. Do not
                        # reuse the same free RAM until the OS is sampled again.
                        self.launch_slots = max(
                            0, budget - sum(self.active_hosts.values())
                        )
                        ok = memory is None or memory >= MEMORY_RESERVE
                        if (
                            ok != self.memory_ok
                            or budget != self.workers
                            or estimate != self.worker_memory
                        ):
                            self.memory_history.append(
                                {
                                    "at": now - self.origin,
                                    "memory_ok": ok,
                                    "available": memory,
                                    "budget": budget,
                                    "worker_memory": estimate,
                                    "worker_peak_memory": self.worker_peak_memory,
                                    "reserved_growth": self.reserved_growth,
                                }
                            )
                        self.workers = budget
                        self.worker_memory = estimate
                        self.peak_workers = max(
                            getattr(self, "peak_workers", 0), budget
                        )
                        self.memory_ok = ok
                        self.next_memory_check = now + 5
                    rows = []
                    for host, policy in self.policies.items():
                        jobs = [
                            j
                            for j in self.jobs.values()
                            if j["host"] == host and j["active"]
                        ]
                        queued = sum(h == host for h, _, _ in self.queue)
                        policy.evaluate(
                            now,
                            queued > 0
                            and sum(self.active_hosts.values()) < self.workers
                            and self.launch_slots > 0,
                            self.memory_ok,
                            active=sum(
                                bool(
                                    not j["state"].get("done")
                                    and (
                                        j["state"].get("running")
                                        or j["state"].get("waiting")
                                        or j["counts"]
                                    )
                                )
                                for j in jobs
                            ),
                        )
                        allowed = jobs[: policy.limit]
                        if policy.recovering:
                            allowed = []
                            if now >= policy.until and not policy.blocked:
                                candidates = [
                                    j for j in jobs if j["state"].get("recoverable")
                                ]
                                # A current recovery
                                # probe has priority
                                # over other failed
                                # maps.
                                probing = [j for j in candidates if j.get("probing")]
                                allowed = (probing or candidates)[:1]
                                # A worker may still be preparing its ledger or
                                # finishing a map whose last tile exhausted its
                                # attempts. Wait for a real missing tile, possibly
                                # from the next queued map, instead of blocking
                                # unrelated services on the same host.
                        for job in jobs:
                            job["probing"] = policy.recovering and job in allowed
                            write_state(
                                job["folder"] / "control.json",
                                {
                                    "version": PROTOCOL,
                                    "generation": policy.generation,
                                    "allowed": job in allowed and not policy.blocked,
                                    "probe": job["probing"],
                                    "blocked": policy.blocked,
                                    "ack": job["ack"],
                                    "expires": now + 2,
                                },
                                cancelled=self.stop.is_set,
                                diagnostic=self.diagnostic,
                            )
                        state = (
                            "deferred"
                            if policy.blocked
                            else "cooldown"
                            if policy.recovering
                            else "memory"
                            if not self.memory_ok
                            else "repairing"
                            if any(j["state"].get("repairing") for j in jobs)
                            else "capacity"
                            if queued
                            and sum(self.active_hosts.values()) >= self.workers
                            else "stable"
                            if policy.frozen or policy.limit >= policy.ceiling
                            else "increasing"
                            if policy.limit > 1
                            else "running"
                            if jobs and policy.total_successes
                            else "starting"
                        )
                        rows.append(
                            {
                                "host": host,
                                "active": sum(
                                    bool(j["state"].get("running")) for j in jobs
                                ),
                                "processes": len(jobs),
                                "limit": policy.limit,
                                "queued": queued,
                                "budget": self.workers,
                                "memory_available": self.memory_available,
                                "memory_reserve": MEMORY_RESERVE,
                                "worker_memory": self.worker_memory,
                                "worker_memory_measured": bool(self.worker_peak_memory),
                                "reserved_growth": self.reserved_growth,
                                "cpu": self.cpu,
                                "rate": (
                                    policy.successes
                                    / max(0.001, now - policy.window_started)
                                    if policy.successes
                                    else policy.rate
                                ),
                                "state": state,
                                "pause": max(0, math.ceil(policy.until - now)),
                                "generation": policy.generation,
                                "successes": policy.total_successes,
                            }
                        )
                    self.rows = rows
                    self.condition.notify_all()
                self.stop.wait(0.5)
        except InterruptedError:
            # Cancellation during an IPC retry is an ordinary user stop.
            self.stop.set()
        except Exception as error:
            if self.diagnostic:
                self.diagnostic.error("coordinator_exception", error)
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
                jobs = [
                    j
                    for j in self.jobs.values()
                    if j["active"] and j["host"] == row["host"]
                ]
                row["processes"] = len(jobs)
                row["active"] = sum(bool(j["state"].get("running")) for j in jobs)
                row["queued"] = sum(h == row["host"] for h, _, _ in self.queue)
                if not jobs and not row["queued"] and row["state"] != "deferred":
                    failed = any(
                        j.get("failed")
                        for j in self.jobs.values()
                        if j["host"] == row["host"]
                    )
                    row["state"] = "failed" if failed else "finished"
                if not jobs or row["state"] in ("cooldown", "deferred"):
                    row["rate"] = 0.0
                rows.append(row)
            return rows

    def adaptive_report(self):
        with self.condition:
            return {
                "protocol": PROTOCOL,
                "coordinator_failed": self.coordinator_failed,
                "memory": list(self.memory_history),
                "memory_reserve": MEMORY_RESERVE,
                "worker_peak_memory": self.worker_peak_memory,
                "worker_memory": self.worker_memory,
                "hosts": [
                    {
                        "host": p.host,
                        "limit": p.limit,
                        "frozen": p.frozen,
                        "deferred": p.blocked,
                        "successes": p.total_successes,
                        "history": [
                            dict(event, at=event["at"] - self.origin)
                            for event in p.history
                        ],
                    }
                    for p in self.policies.values()
                ],
            }

    def local_gate(self, layer, cancelled):
        # Authenticated map providers stay in the main QGIS, but use the same
        # host policy.
        uri = QgsDataSourceUri()
        uri.setEncodedUri(layer.source())
        host = QUrl(uri.param("url")).host() or layer.providerType()
        folder = self.folder / ("local_" + sha256(layer.id().encode()).hexdigest()[:24])
        folder.mkdir(exist_ok=True)
        with self.condition:
            self._register(host, folder)
            self.jobs[folder.name]["active"] = True
        return WorkerGate(
            folder, cancelled, QCoreApplication.processEvents, self.diagnostic
        )

    def finish_local(self, gate, failed=False):
        gate.close()
        with self.condition:
            job = self.jobs[gate.folder.name]
            self._read_job(job, time.monotonic())
            job["active"] = False
            job["failed"] = failed

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
                if self.adaptive and (
                    not self.memory_ok
                    or sum(self.active_hosts.values()) >= self.workers
                    or not self.launch_slots
                ):
                    self.condition.wait(0.1)
                    continue
                index = next(
                    (
                        i
                        for i, (host, _, _) in enumerate(self.queue)
                        if self.active_hosts.get(host, 0)
                        < (
                            self.policies[host].limit
                            if self.adaptive
                            else self.per_server_limit
                        )
                        and (
                            not self.adaptive
                            or (
                                self.memory_ok
                                and (
                                    not self.policies[host].recovering
                                    or (
                                        time.monotonic() >= self.policies[host].until
                                        and self.active_hosts.get(host, 0) == 0
                                    )
                                )
                            )
                        )
                    ),
                    None,
                )
                if self.adaptive:
                    for host, future, folder in list(self.queue):
                        if self.policies[host].blocked:
                            future.set_result(
                                {
                                    "status": "failed",
                                    "method": "raster_render",
                                    "reason": tr(
                                        "Serwer odłożony do późniejszej próby."
                                    ),
                                    "raster": {"deferred": True},
                                }
                            )
                            self.queue.remove((host, future, folder))
                    if not self.queue:
                        return
                    # Prefer another server before a second task on a busy one.
                    # min preserves queue order when active counts are equal.
                    index = min(
                        (
                            i
                            for i, (host, _, _) in enumerate(self.queue)
                            if self.memory_ok
                            and (
                                not self.policies[host].recovering
                                or (
                                    time.monotonic() >= self.policies[host].until
                                    and self.active_hosts.get(host, 0) == 0
                                )
                            )
                            and self.active_hosts.get(host, 0)
                            < self.policies[host].limit
                        ),
                        key=lambda i: self.active_hosts.get(self.queue[i][0], 0),
                        default=None,
                    )
                if index is None:
                    self.condition.wait(0.1)
                    continue
                host, future, folder = self.queue.pop(index)
                self.active_hosts[host] = self.active_hosts.get(host, 0) + 1
                future.set_running_or_notify_cancel()
                if self.adaptive:
                    self.launch_slots -= 1
                    self.jobs[folder.name]["memory_budget"] = self.worker_memory
                    self.jobs[folder.name]["active"] = True
            error = None
            result = None
            try:
                result = self._run(folder)
            except Exception as caught:
                error = caught
            finally:
                if self.diagnostic:
                    if error is not None:
                        self.diagnostic.error(
                            "worker_exception", error, job=folder.name
                        )
                    worker_log = folder / "diagnostic.jsonl"
                    try:
                        lines = worker_log.read_text(encoding="utf-8").splitlines()
                    except OSError:
                        lines = []
                        self.diagnostic.emit("worker_log_unavailable", job=folder.name)
                    for line in lines:
                        try:
                            self.diagnostic.emit(
                                "worker_event",
                                job=folder.name,
                                details=json.loads(line),
                            )
                        except ValueError:
                            self.diagnostic.emit(
                                "worker_log_incomplete", job=folder.name
                            )
                with self.condition:
                    if self.adaptive:
                        self._read_job(self.jobs[folder.name], time.monotonic())
                        self.jobs[folder.name]["active"] = False
                        self.jobs[folder.name]["failed"] = (
                            error is not None or result.get("status") != "saved"
                        )
                    self.active_hosts[host] -= 1
                    self.condition.notify_all()
            if error is not None:
                future.set_exception(error)
            else:
                future.set_result(result)

    def _run(self, folder):
        if self.stop.is_set():
            if self.coordinator_failed:
                raise WorkerError("coordinator")
            raise InterruptedError()
        executable = (
            sys.executable
            if Path(sys.executable).name.lower().startswith("python")
            else None
        )
        if not executable and sys.platform == "win32":
            candidate = Path(sys.prefix) / "python.exe"
            executable = str(candidate) if candidate.is_file() else None
        executable = executable or shutil.which("python3")
        if not executable:
            raise WorkerError("interpreter_missing")
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["QGIS_CUSTOM_CONFIG_PATH"] = str(folder / "profile")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(Path(__file__).resolve().parent.parent), *sys.path]
        )
        environment["GDAL_NUM_THREADS"] = "1"
        environment["QGIS_SNAPSHOT_LANGUAGE"] = self.language
        self.started.add(folder.name)
        # Redirecting output alone does not prevent a console window on Windows.
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            process = subprocess.Popen(
                [
                    executable,
                    "-m",
                    "mbtiles_batch_exporter.archive_worker",
                    str(folder),
                ],
                env=environment,
                stdin=subprocess.PIPE,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            raise WorkerError("process_start") from None
        if self.diagnostic:
            self.diagnostic.emit(
                "worker_started", job=folder.name, worker_pid=process.pid
            )
        with process:
            try:
                process.stdin.write(json.dumps(self.network).encode("utf-8"))
                process.stdin.close()
            except (BrokenPipeError, OSError):
                raise WorkerError("network_transfer") from None
            stopping = None
            while process.poll() is None:
                if self.stop.is_set():
                    (folder / "cancel").touch()
                    stopping = stopping or time.monotonic()
                    if time.monotonic() - stopping > 5:
                        process.kill()
                time.sleep(0.05)
            if self.diagnostic:
                self.diagnostic.emit(
                    "worker_exit", job=folder.name, exit_code=process.returncode
                )
            if self.stop.is_set() and (
                process.returncode or not (folder / "result.json").exists()
            ):
                if self.coordinator_failed:
                    raise WorkerError("coordinator")
                raise InterruptedError()
            if process.returncode or not (folder / "result.json").exists():
                details = {}
                try:
                    details = json.loads((folder / "error.json").read_text())
                except (OSError, ValueError):
                    pass
                raise WorkerError(
                    details.get("stage", "process_exit"),
                    process.returncode,
                    details.get("http_status"),
                    details.get("qt_error"),
                )
        result = json.loads((folder / "result.json").read_text())
        network_error = result.get("worker_network", {})
        if result.get("status") == "failed" and network_error:
            failure = WorkerError(
                "render",
                0,
                network_error.get("http_status"),
                network_error.get("qt_error"),
            )
            result["reason"] = str(failure)
            result["worker_error"] = failure.details
        return result

    def completed(self, layer_id):
        if layer_id not in self.futures:
            return False
        future = self.futures[layer_id][0]
        return future.done() and not future.cancelled() and future.exception() is None

    def take(
        self, layer_id, destination, cancelled, progress, preserve_completed=False
    ):
        future, folder = self.futures[layer_id]
        while not future.done():
            QCoreApplication.processEvents()
            if cancelled():
                self.stop.set()
                raise InterruptedError()
            progress(tr("Równoległe pobieranie map — oczekiwanie na warstwę…"))
            time.sleep(0.05)
        preserve_completed = preserve_completed and self.completed(layer_id)
        if cancelled():
            self.stop.set()
            if not preserve_completed:
                raise InterruptedError()
        if self.coordinator_failed and future.cancelled():
            raise WorkerError("coordinator")
        result = future.result()
        if result.get("local_source"):
            # SQLite/GDAL handles are created in this thread. UI events remain
            # responsive even while copying a large table; no QGIS objects move.
            with ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="archive-merge"
            ) as merger:
                merging = merger.submit(
                    merge_raster,
                    folder / "raster.gpkg",
                    destination,
                    result["table"],
                    (lambda: False) if preserve_completed else self.stop.is_set,
                )
                while not merging.done():
                    QCoreApplication.processEvents()
                    if cancelled():
                        self.stop.set()
                    progress(tr("Scalanie gotowej mapy do GeoPackage…"))
                    time.sleep(0.05)
                if self.stop.is_set() and not preserve_completed:
                    raise InterruptedError()
                merging.result()
        shutil.rmtree(folder)
        self.merged.add(layer_id)
        return result

    def activity(self):
        """Read disposable worker snapshots on the main thread only."""
        rows = []
        for layer_id, (future, folder) in self.futures.items():
            phase, message = "queued", tr("W kolejce")
            if layer_id in self.merged:
                phase, message = "merged", tr("Wynik przekazano do archiwizacji")
            elif future.done():
                failed = (
                    future.cancelled()
                    or future.exception() is not None
                    or future.result().get("status") == "failed"
                )
                phase, message = (
                    ("failed", tr("Proces zakończony bez obrazu"))
                    if failed
                    else ("ready", tr("Zakończono pobieranie — czeka na scalenie"))
                )
            elif folder.name in self.started:
                phase, message = (
                    "active",
                    tr("Uruchamianie QGIS lub otwieranie źródła…"),
                )
                try:
                    state = json.loads(
                        (folder / "progress.json").read_text(encoding="utf-8")
                    )
                    message = state["message"]
                    age = int(time.time() - state["updated_at"])
                    if age >= 10:
                        message += tr(" (ostatni komunikat {0} s temu)").format(age)
                except (OSError, ValueError, KeyError):
                    pass
            # Warnings are latched separately from the latest progress message,
            # including workers which have already finished between UI polls.
            warnings = []
            if layer_id not in self.merged:
                try:
                    warnings = json.loads(
                        (folder / "progress.json").read_text(encoding="utf-8")
                    ).get("server_warnings", [])
                except (OSError, ValueError):
                    pass
            rows.append(
                {
                    "id": layer_id,
                    "phase": phase,
                    "message": message,
                    "server_warnings": warnings,
                }
            )
        return rows

    def __exit__(self, *args):
        self.stop.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.coordinator:
            self.coordinator.join(timeout=3)
        shutil.rmtree(self.folder, ignore_errors=True)
