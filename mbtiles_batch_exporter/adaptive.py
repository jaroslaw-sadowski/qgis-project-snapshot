# SPDX-License-Identifier: GPL-2.0-only

"""Per-host feedback control and disposable, versioned worker IPC (stdlib only)."""

import json
import math
import os
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

from .resources import process_memory

PROTOCOL = 1


def write_state(
    path, value, *, cancelled=lambda: False, diagnostic=None, durable=False
):
    """Atomically publish IPC, tolerating short Windows sharing/lock conflicts.

    Keep the previous complete file until replacement succeeds. Never fall back
    to truncating it: a worker could otherwise lose its permission/ack state.
    Retries total at most 250 ms, below the 2 s permission lease.
    """
    temporary = path.with_suffix(".new")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream)
        if durable:
            stream.flush()
            os.fsync(stream.fileno())
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
            if durable and os.name != "nt":
                descriptor = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
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
    stable_rate: float = 0.0
    healthy_seconds: float = 0.0
    retry_seconds: float = 30.0
    history: list = field(default_factory=list)

    def change(self, now, reason):
        self.generation += 1
        self.window_started = now
        self.sampled_at = now
        self.measured_successes = 0
        self.successes = 0
        self.healthy_seconds = 0.0
        self.history.append(
            {
                "at": now,
                "limit": self.limit,
                "generation": self.generation,
                "reason": reason,
                "pause_seconds": max(0, self.until - now),
                "rate": self.rate,
                "baseline_rate": self.baseline,
                "retry_after_healthy_seconds": self.retry_seconds,
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
                previous = self.until
                self.until = max(self.until, now + delay)
                if delay > 300:
                    self.blocked = True
                    self.change(now, "retry_after_exceeds_300s")
                elif self.until > max(now, previous):
                    # A late deadline still applies after a successful probe.
                    # Invalidate any in-flight probe from the earlier deadline.
                    self.recovering = self.frozen = True
                    self.baseline = self.stable_rate = 0.0
                    self.poor_windows = 0
                    self.retry_seconds = max(60.0, self.retry_seconds)
                    self.change(now, "retry_after_extended")
            return
        # Even a single transient error invalidates a healthy measurement.
        self.successes = 0
        self.window_started = now
        self.sampled_at = now
        self.measured_successes = 0
        self.healthy_seconds = 0.0
        if status in ("timeout", 502, 504):
            self.timeouts += 1
            if self.timeouts < 3 and not probe:
                return
        elif status not in (429, 503) and not (
            probe and status not in (401, 403, 404, 407)
        ):
            self.timeouts = 0
            return
        self.limit = max(1, self.limit - 1)
        self.frozen = True
        self.baseline = self.stable_rate = 0.0
        self.poor_windows = 0
        self.retry_seconds = min(300.0, max(60.0, self.retry_seconds * 2))
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
        self.healthy_seconds += elapsed
        # Compare a trial with the most recent lower-concurrency window, not
        # with an early fast layer for the rest of the archive.
        if self.baseline and self.rate < self.baseline * 1.10:
            self.poor_windows += 1
            if self.poor_windows >= 2:
                self.limit = max(1, self.limit - 1)
                self.frozen = True
                self.baseline = self.stable_rate = 0.0
                self.poor_windows = 0
                self.retry_seconds = min(300.0, max(60.0, self.retry_seconds * 2))
                self.change(now, "no_throughput_gain")
            return
        if self.baseline:
            self.baseline = 0.0
            self.stable_rate = self.rate
            self.retry_seconds = 30.0
        elif (
            self.limit > 1 and self.stable_rate and self.rate < self.stable_rate * 0.75
        ):
            # Keep monitoring an established limit, including periods with no
            # spare computer slots. Two poor full windows justify reducing it.
            self.poor_windows += 1
            if self.poor_windows >= 2:
                self.limit -= 1
                self.frozen = True
                self.stable_rate = 0.0
                self.poor_windows = 0
                self.retry_seconds = min(300.0, max(60.0, self.retry_seconds * 2))
                self.change(now, "throughput_drop")
            return
        self.poor_windows = 0
        self.stable_rate = (
            self.stable_rate * 0.75 + self.rate * 0.25
            if self.stable_rate
            else self.rate
        )
        if self.frozen and self.healthy_seconds < self.retry_seconds:
            return
        if memory_ok and backlog and self.limit < self.ceiling:
            self.baseline = self.rate
            self.limit += 1
            reason = "reprobe" if self.frozen else "increase"
            self.frozen = False
            self.change(now, reason)


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
            status = (
                "success"
                if error is None
                else "timeout"
                if isinstance(error, TimeoutError)
                else getattr(error, "status", None)
            )
            if probe or status in ("timeout", 429, 502, 503, 504):
                # Only feedback which can change permission needs synchronous ACK.
                # Other errors remain queued until the coordinator consumes them.
                self.required_ack = self.sequence
            self.events.append(
                {
                    "sequence": self.sequence,
                    "generation": generation,
                    "probe": probe,
                    "status": status,
                    "delay": getattr(error, "delay", None),
                }
            )
        self.publish()

    def close(self):
        self.state.update(
            waiting=False, running=False, recoverable=False, retry=False, done=True
        )
        self.publish(closing=True)
