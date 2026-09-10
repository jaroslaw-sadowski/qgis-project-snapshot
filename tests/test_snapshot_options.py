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
                self.assertIn('lang="en"', (dialog._result / "raport.html").read_text())
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
            self.assertTrue((original / "manifest.json").exists())
            self.assertEqual(dialog._selected_ids(), set())
        finally:
            dialog.close()

    def test_live_memory_budget_and_waiting_status_in_both_languages(self):
        for language, waiting, downloading, unknown in (
            ("pl", "Czeka na wolny proces", "Pobieranie", "nieznany"),
            ("en", "Waiting for a free process", "Downloading", "unknown"),
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
                        self.assertIn("1 GiB", dialog.ram_hint.toolTip())
                        row.update(
                            state="running",
                            active=1,
                            processes=1,
                            budget=3,
                            memory_available=5 * 1024**3,
                        )
                        dialog._server_activity([row])
                        self.assertEqual(
                            dialog._server_items[row["host"]].text(4), downloading
                        )
                        self.assertIn("1/3", dialog.resource_hint.text())
                        self.assertIn("5.0 GiB", dialog.ram_hint.text())
                        row.update(memory_available=None, budget=2)
                        dialog._server_activity([row])
                        self.assertIn(unknown, dialog.ram_hint.text())
                    finally:
                        dialog.close()

    def test_empty_partial_failed_retry_but_saved_and_excluded_do_not(self):
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
                dialog._selected_ids(), {layer.id() for layer in layers[1:5]}
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
        self.assertEqual(recommend(14, 4111540224, True), 1)
        self.assertEqual(recommend(14, 5 * gib, True), 3)
        self.assertEqual(recommend(14, 3 * gib, True), 1)
        self.assertEqual(recommend(14, None, True), 2)
        self.assertEqual(recommend(14, 40 * gib, True), 28)

    def test_budgets_respect_ram_cpu_and_server_capacity(self):
        gb = 1024**3
        self.assertEqual(recommend(32, 3 * gb, True), 1)
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
