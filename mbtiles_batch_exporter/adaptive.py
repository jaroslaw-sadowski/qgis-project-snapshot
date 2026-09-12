# SPDX-License-Identifier: GPL-2.0-only

"""Per-host feedback control and disposable, versioned worker IPC (stdlib only)."""

import json
import math
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

from .resources import process_memory

PROTOCOL = 1


def write_state(path, value, *, cancelled=lambda: False, diagnostic=None):
    """Atomically publish IPC, tolerating short Windows sharing/lock conflicts.

    Keep the previous complete file until replacement succeeds. Never fall back
    to truncating it: a worker could otherwise lose its permission/ack state.
    Retries total at most 250 ms, below the 2 s permission lease.
    """
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    delays = (0.01, 0.02, 0.04, 0.08, 0.10)
    for attempt in range(len(delays) + 1):
        try:
            temporary.replace(path)
        except OSError as error:
            # Access denied, sharing violation, lock violation. Other errors
            # (disk full, missing directory, etc.) need their original diagnosis.
            if getattr(error, "winerror", None) not in (5, 32, 33):
                raise
            if diagnostic:
                diagnostic.error(
                    "ipc_replace_retry"
                    if attempt < len(delays)
                    else "ipc_replace_failed",
                    error,
                    file=path.name,
                    attempt=attempt + 1,
                )
            if attempt == len(delays):
                raise
            if cancelled():
                raise InterruptedError() from error
            time.sleep(delays[attempt])
            if cancelled():
                raise InterruptedError() from error
        else:
            if attempt and diagnostic:
                diagnostic.emit(
                    "ipc_replace_recovered", file=path.name, attempts=attempt + 1
                )
            return


def retry_after(value, now=None):
    """Return seconds, preserving server deadlines; malformed values use backoff."""
    try:
        text = str(value).strip()
        if text.isdigit():
            seconds = float(text)
            return seconds if math.isfinite(seconds) else 301.0
        date = parsedate_to_datetime(text)
        if date.tzinfo is None:
            return None
        return max(0.0, date.timestamp() - (time.time() if now is None else now))
    except (ValueError, TypeError, OverflowError):
        return None


class DownloadError(RuntimeError):
    def __init__(self, message, status=None, delay=None):
        super().__init__(message)
        self.status = status
        self.delay = delay


class HostDeferred(RuntimeError):
    """No more network operations for this host during the current archive."""


@dataclass
class HostPolicy:
    host: str
    ceiling: int = 8
    limit: int = 1
    generation: int = 0
    frozen: bool = False
    blocked: bool = False
    recovering: bool = False
    until: float = 0.0
    probe_failures: int = 0
    timeouts: int = 0
    window_started: float = 0.0
    sampled_at: float | None = None
    measured_successes: int = 0
    successes: int = 0
    total_successes: int = 0
    rate: float = 0.0
    baseline: float = 0.0
    poor_windows: int = 0
    history: list = field(default_factory=list)

    def change(self, now, reason):
        self.generation += 1
        self.window_started = now
        self.sampled_at = now
        self.measured_successes = 0
        self.successes = 0
        self.history.append(
            {
                "at": now,
                "limit": self.limit,
                "generation": self.generation,
                "reason": reason,
                "pause_seconds": max(0, self.until - now),
            }
        )

    def success(self, count, now, generation, probe=False):
        self.total_successes += count
        if generation != self.generation:
            return
        self.timeouts = 0
        if probe and self.recovering:
            self.recovering = False
            self.until = 0
            self.probe_failures = 0
            self.change(now, "recovered")
        self.successes += count

    def failure(self, status, delay, now, generation, probe=False):
        if self.blocked:
            return
        if generation != self.generation:
            # Other in-flight requests from the same wave must not count as probes.
            if status in (429, 503) and delay is not None:
                self.until = max(self.until, now + delay)
                if delay > 300:
                    self.blocked = True
                    self.change(now, "retry_after_exceeds_300s")
            return
        if status == "timeout":
            self.timeouts += 1
            if self.timeouts < 3 and not probe:
                return
        elif status not in (429, 503) and not (
            probe and status not in (401, 403, 404, 407)
        ):
            self.timeouts = 0
            # Broken windows cannot justify a concurrency increase.
            self.successes = 0
            self.window_started = now
            self.sampled_at = now
            self.measured_successes = 0
            return
        self.limit = max(1, self.limit - 1)
        self.frozen = True
        if probe:
            self.probe_failures += 1
        self.recovering = True
        pause = (
            delay if delay is not None else (30, 60, 120)[min(self.probe_failures, 2)]
        )
        self.until = max(self.until, now + pause)
        self.blocked = self.probe_failures >= 3 or pause > 300
        self.change(
            now,
            "retry_after_exceeds_300s"
            if pause > 300
            else "recovery_exhausted"
            if self.blocked
            else str(status),
        )

    def evaluate(self, now, backlog, memory_ok=True, active=None):
        previous = self.window_started if self.sampled_at is None else self.sampled_at
        self.sampled_at = now
        if active is not None and active < self.limit:
            # Exclude underfilled intervals, retaining measured work across map
            # handoffs. Frequent short startups must not prevent a full window.
            self.window_started += max(0, now - previous)
            self.successes = self.measured_successes
            return
        self.measured_successes = self.successes
        elapsed = now - self.window_started
        if self.recovering or self.blocked or elapsed < 15 or self.successes < 10:
            return
        self.rate = self.successes / elapsed
        self.successes = 0
        self.measured_successes = 0
        self.window_started = now
        if self.frozen or not memory_ok:
            return
        if self.baseline and self.rate < self.baseline * 1.10:
            self.poor_windows += 1
            if self.poor_windows >= 2:
                self.limit = max(1, self.limit - 1)
                self.frozen = True
                self.change(now, "no_throughput_gain")
            return
        self.poor_windows = 0
        if backlog and self.limit < self.ceiling:
            self.baseline = self.rate
            self.limit += 1
            self.change(now, "increase")


class WorkerGate:
    """Worker-owned telemetry and a fail-closed permission check before rendering."""

    def __init__(self, folder, cancelled, pump=lambda: None, diagnostic=None):
        self.diagnostic = diagnostic
        self.folder = folder
        self.cancelled = cancelled
        self.pump = pump
        self.command = {}
        self.sequence = 0
        self.required_ack = 0
        self.events = []
        self.counts = {}
        self.state = {
            "version": PROTOCOL,
            "waiting": False,
            "running": False,
            "retry": False,
            "repairing": False,
            "recoverable": False,
            "seconds": 0.0,
        }
        self.started = 0.0
        self.next_memory_check = 0.0
        self.publish()

    def publish(self, closing=False):
        self.state["sampled_at"] = time.monotonic()
        if self.state["seconds"] > 0:
            now = time.monotonic()
            if closing or now >= self.next_memory_check:
                self.state["memory"] = process_memory()
                self.next_memory_check = now + 5
        write_state(
            self.folder / "telemetry.json",
            dict(self.state, counts=self.counts, events=self.events),
            cancelled=(lambda: False) if closing else self.cancelled,
            diagnostic=self.diagnostic,
        )

    def before(self, retry=False):
        self.state.update(
            waiting=True, running=False, retry=retry, repairing=retry, recoverable=True
        )
        # The caller requests only missing ledger tiles. A tile that has never
        # been attempted is also a valid recovery probe when a previous tile
        # has exhausted its own retry budget.
        self.publish()
        last_live = time.monotonic()
        while True:
            if self.cancelled():
                raise InterruptedError()
            try:
                command = json.loads(
                    (self.folder / "control.json").read_text(encoding="utf-8")
                )
                if command.get("version") != PROTOCOL:
                    raise HostDeferred("IPC version mismatch")
                if command.get("blocked"):
                    raise HostDeferred("Host deferred")
                if command.get("expires", 0) >= time.monotonic():
                    last_live = time.monotonic()
                    ack = command.get("ack", 0)
                    self.events = [
                        event for event in self.events if event["sequence"] > ack
                    ]
                    if command.get("allowed") and ack >= self.required_ack:
                        self.command = command
                        self.state.update(waiting=False, running=True)
                        self.started = time.monotonic()
                        self.publish()
                        return
            except (OSError, ValueError):
                pass
            if time.monotonic() - last_live > 10:
                raise HostDeferred("Coordinator unavailable")
            self.pump()
            time.sleep(0.05)

    def outcome(self, error=None, recoverable=True):
        generation = self.command.get("generation", 0)
        probe = self.command.get("probe", False)
        self.state.update(
            running=False,
            recoverable=bool(error and recoverable),
            retry=bool(error and recoverable),
        )
        self.state["seconds"] += max(0, time.monotonic() - self.started)
        if error is None and not probe:
            key = str(generation)
            self.counts[key] = self.counts.get(key, 0) + 1
        else:
            self.sequence += 1
            self.required_ack = self.sequence
            self.events.append(
                {
                    "sequence": self.sequence,
                    "generation": generation,
                    "probe": probe,
                    "status": (
                        "success"
                        if error is None
                        else "timeout"
                        if isinstance(error, TimeoutError)
                        else getattr(error, "status", None)
                    ),
                    "delay": getattr(error, "delay", None),
                }
            )
        self.publish()

    def close(self):
        self.state.update(
            waiting=False, running=False, recoverable=False, retry=False, done=True
        )
        self.publish(closing=True)
