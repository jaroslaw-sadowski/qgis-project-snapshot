# SPDX-License-Identifier: GPL-2.0-only

"""Reproduce Windows replacement failures without relying on the test OS."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mbtiles_batch_exporter.adaptive import WorkerGate, write_state
from mbtiles_batch_exporter.diagnostics import Diagnostics


def windows_lock(code=5):
    error = PermissionError(13, "Access denied")
    error.winerror = code
    return error


class IpcTests(unittest.TestCase):
    def test_transient_windows_locks_keep_old_json_until_atomic_replace(self):
        for code in (5, 32, 33):
            with self.subTest(code=code), TemporaryDirectory() as temporary:
                folder = Path(temporary)
                target = folder / "control.json"
                write_state(target, {"allowed": False, "ack": 4})
                replace = Path.replace
                calls = []

                def locked(source, destination):
                    calls.append(1)
                    self.assertEqual(
                        json.loads(target.read_text()), {"allowed": False, "ack": 4}
                    )
                    if len(calls) < 3:
                        raise windows_lock(code)
                    return replace(source, destination)

                log = Diagnostics(folder / "diagnostic.jsonl")
                with patch.object(Path, "replace", locked):
                    write_state(target, {"allowed": True, "ack": 5}, diagnostic=log)
                self.assertEqual(
                    json.loads(target.read_text()), {"allowed": True, "ack": 5}
                )
                events = [
                    json.loads(line)["event"]
                    for line in log.path.read_text().splitlines()
                ]
                self.assertEqual(
                    events,
                    ["ipc_replace_retry", "ipc_replace_retry", "ipc_replace_recovered"],
                )

    def test_persistent_lock_is_bounded_and_preserves_last_command(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "control.json"
            write_state(target, {"allowed": False})
            with (
                patch.object(Path, "replace", side_effect=windows_lock()) as replace,
                patch("mbtiles_batch_exporter.adaptive.time.sleep") as sleep,
            ):
                with self.assertRaises(PermissionError):
                    write_state(target, {"allowed": True})
            self.assertEqual(replace.call_count, 6)
            self.assertAlmostEqual(sum(c.args[0] for c in sleep.call_args_list), 0.25)
            self.assertEqual(json.loads(target.read_text()), {"allowed": False})

    def test_cancellation_interrupts_retry_without_publishing_permission(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "control.json"
            write_state(target, {"allowed": False})
            with patch.object(Path, "replace", side_effect=windows_lock()) as replace:
                with self.assertRaises(InterruptedError):
                    write_state(target, {"allowed": True}, cancelled=lambda: True)
            self.assertEqual(replace.call_count, 1)
            self.assertEqual(json.loads(target.read_text()), {"allowed": False})

    def test_other_os_errors_are_not_retried(self):
        with TemporaryDirectory() as folder:
            with patch.object(
                Path, "replace", side_effect=OSError(28, "Disk full")
            ) as replace:
                with self.assertRaises(OSError):
                    write_state(Path(folder) / "control.json", {})
            self.assertEqual(replace.call_count, 1)

    def test_telemetry_retry_does_not_count_a_tile_twice(self):
        with TemporaryDirectory() as folder:
            folder = Path(folder)
            gate = WorkerGate(folder, lambda: False)
            replace = Path.replace
            attempts = []

            def locked(source, destination):
                attempts.append(1)
                if len(attempts) == 1:
                    raise windows_lock()
                return replace(source, destination)

            with patch.object(Path, "replace", locked):
                gate.outcome()
            state = json.loads((folder / "telemetry.json").read_text())
            self.assertEqual(state["counts"], {"0": 1})
            gate.close()
