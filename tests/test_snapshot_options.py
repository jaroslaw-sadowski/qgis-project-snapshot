# SPDX-License-Identifier: GPL-2.0-only

"""Locale, retry selection and process scheduling behavior."""

import ast
import os
import unittest
import xml.etree.ElementTree as ET
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from string import Formatter
from threading import Condition, Event
from unittest.mock import patch

import test_archive as fixtures
import test_archive_progress as progress_fixtures

from mbtiles_batch_exporter import i18n
from mbtiles_batch_exporter.archive import read_resume_manifest, resume_manifest_path
from mbtiles_batch_exporter.parallel_archive import RasterWorkers
from mbtiles_batch_exporter.resources import (
    available_memory,
    detect_resources,
    recommend,
)


class LocaleTests(unittest.TestCase):
    def test_qgis_locale_override_and_os_fallback(self):
        from qgis.core import QgsSettings

        settings = QgsSettings()
        keys = ("locale/overrideFlag", "locale/userLocale")
        previous = {key: settings.value(key) for key in keys}
        try:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("QGIS_SNAPSHOT_LANGUAGE", None)
                settings.setValue(keys[0], True)
                for locale, language in [
                    ("en_US", "en"),
                    ("en_GB", "en"),
                    ("en_AU", "en"),
                    ("pl_PL", "pl"),
                ]:
                    settings.setValue(keys[1], locale)
                    self.assertEqual(i18n.language(), language)
                    self.assertEqual(
                        i18n.tr("Zamknij"), "Close" if language == "en" else "Zamknij"
                    )
                settings.setValue(keys[0], False)
                with patch("mbtiles_batch_exporter.i18n.QLocale") as locale:
                    locale.return_value.name.return_value = "pl_PL"
                    self.assertEqual(i18n.language(), "pl")
        finally:
            for key, value in previous.items():
                settings.remove(key) if value is None else settings.setValue(key, value)

    def test_catalog_covers_calls_and_preserves_format_fields(self):
        folder = Path(i18n.__file__).parent
        catalog = {
            m.findtext("source"): m.findtext("translation")
            for m in ET.parse(folder / "en.ts").iter("message")
        }
        with patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE="en"):
            for source, translated in catalog.items():
                self.assertEqual(i18n.tr(source), translated)
            for path in folder.glob("*.py"):
                for node in ast.walk(ast.parse(path.read_text())):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "tr"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                    ):
                        source = node.args[0].value
                        self.assertIn(source, catalog, (path.name, source))
                        # CSS contains literal braces but is never interpolated.
                        if "{0" in source:

                            def fields(text):
                                return sorted(
                                    (f, spec, conv)
                                    for _, f, spec, conv in Formatter().parse(text)
                                    if f is not None
                                )

                            self.assertEqual(fields(source), fields(catalog[source]))


class OptionsTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    tearDown = fixtures.ArchiveTests.tearDown
    add_points = fixtures.ArchiveTests.add_points
    dialog = progress_fixtures.ProgressTests.dialog

    def test_english_dialog_and_real_report(self):
        with patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE="en"):
            dialog = self.dialog()
            try:
                self.assertIn("Archive project", dialog.windowTitle())
                self.assertEqual(dialog.close_button.text(), "Close")
                self.assertFalse(hasattr(dialog, "workers"))
                self.assertFalse(hasattr(dialog, "server_limit"))
                dialog.options.setEnabled(False)
                self.assertTrue(dialog.servers.isEnabled())
                dialog.options.setEnabled(True)
                dialog._server_activity(
                    [
                        {
                            "host": "test",
                            "active": 1,
                            "processes": 2,
                            "limit": 1,
                            "queued": 5,
                            "rate": 0.0,
                            "state": "cooldown",
                            "pause": 30,
                            "budget": 4,
                        }
                    ]
                )
                self.assertEqual(
                    dialog._server_items["test"].text(4), "Server cooldown"
                )
                self.assertIn("2/4", dialog.resource_hint.text())
                dialog.start()
                self.assertIsNotNone(dialog._result, dialog.log.toPlainText())
                self.assertIn("Layer 1/1", dialog.log.toPlainText())
                self.assertIn("Saved", dialog._items[self.layer.id()].text(2))
                self.assertIn('lang="en"', (dialog._result / "report.html").read_text())
                self.assertEqual(dialog._selected_ids(), set())
            finally:
                dialog.close()

    def test_retry_selection_and_new_archive_preserves_previous(self):
        second = self.add_points("Retry me", [(3, 3)])
        dialog = self.dialog()
        status = dialog._layer_status

        def cancel_second(record, done, total):
            status(record, done, total)
            if record["id"] == second.id() and record["status"] == "pending":
                dialog.cancel()

        try:
            with patch.object(dialog, "_layer_status", side_effect=cancel_second):
                dialog.start()
            original = dialog._result
            self.assertEqual(dialog._selected_ids(), {second.id()})
            self.assertIn("Retry me", dialog.results.toPlainText())
            self.assertIn("przerwana", dialog.results.toPlainText())
            self.assertFalse(dialog.retry_button.isHidden())
            dialog.retry_button.click()
            self.assertIsNotNone(dialog._result)
            self.assertNotEqual(original, dialog._result)
            self.assertTrue(resume_manifest_path(original).exists())
            self.assertEqual(dialog._selected_ids(), set())
        finally:
            dialog.close()

    def test_live_memory_budget_and_waiting_status_in_both_languages(self):
        for language, waiting, downloading, unknown, commit, reprobe in (
            (
                "pl",
                "Limit procesów komputera",
                "Pobieranie",
                "nieznany",
                "Limit przydziału pamięci Windows",
                "ponownie sprawdza wyższy limit",
            ),
            (
                "en",
                "Computer process limit",
                "Downloading",
                "unknown",
                "Windows memory allocation limit",
                "tries a higher limit again",
            ),
        ):
            with self.subTest(language=language):
                with patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE=language):
                    dialog = self.dialog()
                    try:
                        row = {
                            "host": "example.invalid",
                            "active": 0,
                            "processes": 0,
                            "limit": 1,
                            "queued": 5,
                            "rate": 0.0,
                            "state": "capacity",
                            "pause": 0,
                            "budget": 1,
                            "memory_available": 4111540224,
                            "cpu": 14,
                        }
                        dialog._server_activity([row])
                        self.assertEqual(
                            dialog._server_items[row["host"]].text(4), waiting
                        )
                        self.assertIn("3.8 GiB", dialog.ram_hint.text())
                        self.assertIn("14", dialog.resource_hint.toolTip())
                        self.assertIn("1024 MiB", dialog.ram_hint.toolTip())
                        self.assertIn("768 MiB", dialog.ram_hint.text())
                        self.assertIn(reprobe, dialog.servers.toolTip())
                        row.update(
                            state="commit", memory_budget_available=320 * 1024**2
                        )
                        dialog._server_activity([row])
                        self.assertEqual(
                            dialog._server_items[row["host"]].text(4), commit
                        )
                        self.assertIn("3.8 GiB", dialog.ram_hint.text())
                        self.assertIn("0.3 GiB", dialog.ram_hint.toolTip())
                        self.assertIn("Windows", dialog.ram_hint.toolTip())
                        self.assertEqual(
                            dialog.ram_hint.toolTip(), dialog.resource_hint.toolTip()
                        )
                        row.update(
                            state="running",
                            active=1,
                            processes=1,
                            budget=3,
                            memory_available=5 * 1024**3,
                            memory_budget_available=5 * 1024**3,
                            worker_memory=450 * 1024**2,
                            worker_memory_measured=True,
                        )
                        dialog._server_activity([row])
                        self.assertEqual(
                            dialog._server_items[row["host"]].text(4), downloading
                        )
                        self.assertIn("1/3", dialog.resource_hint.text())
                        self.assertIn("5.0 GiB", dialog.ram_hint.text())
                        self.assertIn("450 MiB", dialog.ram_hint.toolTip())
                        self.assertNotIn("Windows", dialog.ram_hint.toolTip())
                        row.update(memory_budget_available=None)
                        dialog._server_activity([row])
                        self.assertNotIn("Windows", dialog.ram_hint.toolTip())
                        row.update(memory_available=None, budget=2)
                        dialog._server_activity([row])
                        self.assertIn(unknown, dialog.ram_hint.text())
                    finally:
                        dialog.close()

    def test_resume_from_new_dialog_uses_manifest_area_and_reuses_data(self):
        from qgis.core import QgsSettings

        first = self.dialog()
        try:
            first.start()
            previous = first._result
            self.assertIsNotNone(previous)
            self.assertEqual(
                QgsSettings().value("mbtiles_batch_exporter/last_resume_folder"),
                str(previous),
            )
        finally:
            first.close()
        dialog = self.dialog()
        try:
            with (
                patch(
                    "mbtiles_batch_exporter.archive_dialog."
                    "QFileDialog.getExistingDirectory",
                    return_value=str(previous),
                ) as choose,
                patch.object(
                    dialog, "_area", side_effect=AssertionError("New area used")
                ),
                patch("mbtiles_batch_exporter.archive._write_vector") as write,
                patch(
                    "mbtiles_batch_exporter.archive_dialog.QMessageBox.warning"
                ) as warning,
            ):
                dialog.resume_button.click()
            self.assertEqual(choose.call_args.args[2], str(previous))
            warning.assert_not_called()
            write.assert_not_called()
            self.assertIsNotNone(dialog._result, dialog.log.toPlainText())
            self.assertNotEqual(dialog._result, previous)
            self.assertEqual(
                QgsSettings().value("mbtiles_batch_exporter/last_resume_folder"),
                str(dialog._result),
            )
        finally:
            dialog.close()

    def test_checkpoint_survives_dialog_exception_and_prefills_resume(self):
        checkpoint = self.folder / "archive.in-progress-fixture"
        checkpoint.mkdir()
        (checkpoint / "diagnostyka").mkdir()
        (checkpoint / "diagnostyka" / "manifest.json").write_text("{}")
        for locale, prompt in (("pl", "Wznów archiwum"), ("en", "Resume archive")):
            with (
                self.subTest(locale=locale),
                patch.dict(os.environ, QGIS_SNAPSHOT_LANGUAGE=locale),
            ):
                dialog = self.dialog()

                def interrupted(*args, **kwargs):
                    kwargs["checkpoint_created"](checkpoint)
                    raise RuntimeError("Fixture failure")

                try:
                    with (
                        patch(
                            "mbtiles_batch_exporter.archive_dialog.create_archive",
                            side_effect=interrupted,
                        ),
                        patch(
                            "mbtiles_batch_exporter.archive_dialog.QMessageBox.warning"
                        ),
                    ):
                        dialog.start()
                    self.assertIsNone(dialog._result)
                    self.assertIn(str(checkpoint), dialog.status.text())
                    self.assertIn(prompt, dialog.status.text())
                    self.assertTrue(dialog.resume_button.isEnabled())
                    self.assertFalse(dialog._running)
                finally:
                    dialog.close()
                reopened = self.dialog()
                try:
                    with (
                        patch(
                            "mbtiles_batch_exporter.archive_dialog."
                            "QFileDialog.getExistingDirectory",
                            return_value="",
                        ) as choose,
                        patch.object(reopened, "start") as start,
                    ):
                        reopened.resume_button.click()
                    self.assertEqual(choose.call_args.args[2], str(checkpoint))
                    start.assert_not_called()
                finally:
                    reopened.close()

    def test_remembered_legacy_folder_and_missing_folder_defaults(self):
        from qgis.core import QgsSettings

        QgsSettings().setValue(
            "mbtiles_batch_exporter/last_resume_folder", str(self.folder / "absent")
        )
        dialog = self.dialog()
        try:
            with patch(
                "mbtiles_batch_exporter.archive_dialog."
                "QFileDialog.getExistingDirectory",
                return_value="",
            ) as choose:
                dialog.resume_button.click()
            self.assertEqual(choose.call_args.args[2], dialog.output_edit.text())
            legacy = self.folder / "legacy"
            legacy.mkdir()
            (legacy / "manifest.json").write_text("{}")
            QgsSettings().setValue(
                "mbtiles_batch_exporter/last_resume_folder", str(legacy)
            )
            with patch(
                "mbtiles_batch_exporter.archive_dialog."
                "QFileDialog.getExistingDirectory",
                return_value="",
            ) as choose:
                dialog.resume_button.click()
            self.assertEqual(choose.call_args.args[2], str(legacy))
        finally:
            dialog.close()

    def test_empty_vector_output_name_and_diagnostic_folder_are_shown(self):
        empty = self.add_points("Poza obszarem", [(3000, 3000)])
        original_name = empty.name()
        dialog = self.dialog()
        try:
            dialog.start()
            self.assertIsNotNone(dialog._result, dialog.log.toPlainText())
            manifest = read_resume_manifest(dialog._result)
            record = next(r for r in manifest["layers"] if r["id"] == empty.id())
            expected = original_name + "_nie-bylo-obiektow-w-zasiegu"
            self.assertEqual(record["output_name"], expected)
            self.assertEqual(dialog._items[empty.id()].text(0), expected)
            self.assertIn(expected, dialog.results.toPlainText())
            self.assertIn("diagnostyka", dialog.results.toPlainText())
            self.assertEqual(empty.name(), original_name)
            self.assertEqual(
                resume_manifest_path(dialog._result),
                dialog._result / "diagnostyka" / "manifest.json",
            )
        finally:
            dialog.close()

    def test_continuation_retries_partial_failed_cancelled_and_preserves_empty(self):
        layers = [self.layer] + [self.add_points(str(i), [(3, 3)]) for i in range(5)]
        dialog = self.dialog()
        try:
            statuses = ("saved", "empty", "partial", "failed", "cancelled", "excluded")
            dialog._show_results(
                {
                    "layers": [
                        dict(
                            id=layer.id(),
                            name=layer.name(),
                            status=s,
                            reason="Diagnostic",
                        )
                        for layer, s in zip(layers, statuses)
                    ]
                }
            )
            self.assertEqual(
                dialog._selected_ids(), {layer.id() for layer in layers[2:5]}
            )
        finally:
            dialog.close()


class ResourceTests(unittest.TestCase):
    def test_windows_memory_uses_available_physical_bytes(self):
        def status(output):
            native = output._obj
            self.assertEqual(native.length, 64)
            native.total = 16 * 1024**3
            native.available = 4111540224
            native.virtual_available = 128 * 1024**3
            return 1

        with (
            patch("mbtiles_batch_exporter.resources.sys.platform", "win32"),
            patch("mbtiles_batch_exporter.resources.ctypes.windll", create=True) as dll,
        ):
            dll.kernel32.GlobalMemoryStatusEx.side_effect = status
            self.assertEqual(available_memory(), 4111540224)
            dll.kernel32.GlobalMemoryStatusEx.side_effect = None
            dll.kernel32.GlobalMemoryStatusEx.return_value = 0
            self.assertIsNone(available_memory())

    def test_budget_can_recover_without_exceeding_cpu_or_memory(self):
        gib = 1024**3
        self.assertEqual(recommend(14, 4111540224, True), 3)
        self.assertEqual(recommend(14, 5 * gib, True), 4)
        self.assertEqual(recommend(14, 3 * gib, True), 2)
        self.assertEqual(recommend(14, None, True), 2)
        self.assertEqual(recommend(14, 40 * gib, True), 28)

    def test_available_ram_budgets_only_additional_processes(self):
        gib = 1024**3
        self.assertEqual(recommend(4, 4 * gib, True, active_workers=1), 4)
        self.assertEqual(recommend(4, 3865907200, True, active_workers=2), 4)
        self.assertEqual(recommend(4, gib, True, active_workers=2), 2)
        self.assertEqual(recommend(2, 40 * gib, True, active_workers=3), 4)
        self.assertEqual(recommend(4, None, True, active_workers=3), 2)

    def test_budgets_respect_ram_cpu_and_server_capacity(self):
        gb = 1024**3
        self.assertEqual(recommend(32, 3 * gb, True), 2)
        self.assertEqual(recommend(32, 64 * gb, True), 32)
        self.assertEqual(recommend(2, 64 * gb, True), 4)
        self.assertEqual(recommend(32, None, True), 2)
        self.assertEqual(recommend(32, 64 * gb, True, hosts={"a": 200}), 2)
        self.assertEqual(
            recommend(32, 64 * gb, True, per_server=8, hosts={"a": 200}), 8
        )
        self.assertEqual(recommend(32, 64 * gb, False), 2)
        self.assertGreaterEqual(detect_resources()["cpu"], 1)

    def test_busy_host_does_not_block_another_host(self):
        workers = RasterWorkers.__new__(RasterWorkers)
        workers.diagnostic = None
        workers.adaptive = False
        workers.stop = Event()
        workers.condition = Condition()
        workers.per_server_limit = 1
        workers.active_hosts = {}
        futures = [Future() for _ in range(3)]
        workers.queue = [
            ("a", futures[0], "a1"),
            ("a", futures[1], "a2"),
            ("b", futures[2], "b"),
        ]
        other_host = Event()

        def run(folder):
            if folder == "a1":
                self.assertTrue(
                    other_host.wait(3), "Another server was starved by the busy host"
                )
            elif folder == "b":
                other_host.set()
            return folder

        workers._run = run
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(workers._work_loop) for _ in range(2)]
            for task in tasks:
                task.result(timeout=5)
        self.assertEqual([f.result() for f in futures], ["a1", "a2", "b"])
