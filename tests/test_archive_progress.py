"""Real dialog/backend checks for progress and understandable terminal states."""

import unittest
from unittest.mock import patch

import test_archive as fixtures

from mbtiles_batch_exporter.archive_dialog import ArchiveDialog


class ProgressTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    tearDown = fixtures.ArchiveTests.tearDown
    add_points = fixtures.ArchiveTests.add_points

    def dialog(self):
        with patch(
            "mbtiles_batch_exporter.archive_dialog.QgsProject.instance",
            return_value=self.project,
        ):
            dialog = ArchiveDialog(None)
        # A real polygon layer for the area; the point data remain selected.
        from qgis.core import QgsFeature, QgsVectorLayer

        polygon = QgsVectorLayer("Polygon?crs=EPSG:2180", "Obszar", "memory")
        feature = QgsFeature()
        feature.setGeometry(self.area)
        polygon.dataProvider().addFeatures([feature])
        polygon.updateExtents()
        self.project.addMapLayer(polygon)
        dialog.polygon_combo.addItem(polygon.name(), polygon.id())
        dialog.area_combo.setCurrentIndex(1)
        dialog.output_edit.setText(str(self.folder))
        return dialog

    def test_real_export_shows_layer_progress_stages_and_result(self):
        dialog = self.dialog()
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtTest import QTest

        original_status = dialog._layer_status
        inspected = []

        def inspect_running(record, completed, total):
            original_status(record, completed, total)
            self.assertTrue(dialog._running)
            self.assertFalse(dialog.output_edit.isEnabled())
            for widget in (dialog.tree, dialog.servers, dialog.log, dialog.copy_button):
                self.assertTrue(widget.isEnabled())
            item = dialog._items[self.layer.id()]
            dialog.tree.setCurrentItem(item)
            selected = dialog._selected_ids()
            QTest.keyClick(dialog.tree, Qt.Key_Space)
            self.assertEqual(dialog._selected_ids(), selected)
            group = dialog.tree.topLevelItem(0)
            dialog.tree.setCurrentItem(group)
            QTest.keyClick(dialog.tree, Qt.Key_Left)
            self.assertFalse(group.isExpanded())
            QTest.keyClick(dialog.tree, Qt.Key_Right)
            self.assertTrue(group.isExpanded())
            inspected.append(True)

        dialog._layer_status = inspect_running
        try:
            with patch(
                "mbtiles_batch_exporter.archive_dialog.QMessageBox.information",
                side_effect=lambda *args: self.assertFalse(dialog.timer.isActive()),
            ):
                dialog.start()
            self.assertIsNotNone(dialog._result, dialog.log.toPlainText())
            self.assertTrue(inspected)
            self.assertTrue(
                dialog._items[self.layer.id()].flags() & Qt.ItemIsUserCheckable
            )
            self.assertEqual(dialog.progress.value(), dialog.progress.maximum())
            self.assertIn("sprawdź raport", dialog.progress.format())
            self.assertEqual(dialog._items[self.layer.id()].text(2), "Zapisano")
            log = dialog.log.toPlainText()
            self.assertIn("Warstwa 1/1", log)
            self.assertIn("Kontrola integralności", log)
            self.assertIn("Zapisywanie manifestu", log)
            self.assertFalse(dialog.timer.isActive())
            self.assertTrue(dialog.report_button.isEnabled())
            for widget in (
                dialog.output_edit,
                dialog.area_combo,
                dialog.polygon_combo,
                dialog.zoom_min,
                dialog.zoom_max,
                dialog.servers,
                dialog.tree,
                dialog.log,
                dialog.progress,
            ):
                self.assertTrue(widget.toolTip())
        finally:
            dialog.close()

    def test_failure_does_not_show_success_and_retains_diagnostic_log(self):
        dialog = self.dialog()
        try:
            with (
                patch(
                    "mbtiles_batch_exporter.archive_dialog.create_archive",
                    side_effect=RuntimeError("Test: brak miejsca"),
                ),
                patch("mbtiles_batch_exporter.archive_dialog.QMessageBox.warning"),
            ):
                dialog.start()
            self.assertIsNone(dialog._result)
            self.assertIn("Błąd", dialog.progress.format())
            self.assertLess(dialog.progress.value(), dialog.progress.maximum())
            self.assertIn("brak miejsca", dialog.log.toPlainText())
            self.assertFalse(dialog.timer.isActive())
            self.assertFalse(dialog.report_button.isEnabled())
        finally:
            dialog.close()

    def test_cancel_in_dialog_keeps_finished_layer_and_reports_interruption(self):
        second = self.add_points("Druga", [(3, 3)])
        dialog = self.dialog()
        original = dialog._layer_status

        def status(record, completed, total):
            original(record, completed, total)
            if record["id"] == second.id() and record["status"] == "pending":
                dialog.cancel()

        try:
            with (
                patch.object(dialog, "_layer_status", side_effect=status),
                patch("mbtiles_batch_exporter.archive_dialog.QMessageBox.information"),
            ):
                dialog.start()
            self.assertIsNotNone(dialog._result)
            self.assertIn("Przerwano", dialog.progress.format())
            self.assertEqual(dialog._items[self.layer.id()].text(2), "Zapisano")
            self.assertEqual(dialog._items[second.id()].text(2), "Przerwano")
            self.assertTrue(dialog.report_button.isEnabled())
            self.assertFalse(dialog.timer.isActive())
        finally:
            dialog.close()

    def test_server_warning_survives_progress_and_finished_worker(self):
        dialog = self.dialog()
        try:
            message = "[HTTP 429] Server test: too many requests"
            dialog._update_progress(message)
            dialog._update_progress("Next operation")
            self.assertEqual(dialog.server_warning.text(), message)
            self.assertFalse(dialog.server_warning.isHidden())
            self.assertIn("#b00020", dialog.server_warning.styleSheet())
            dialog._layer_status({"id": self.layer.id(), "status": "saved"}, 1, 1)
            busy = "[HTTP 503] Server test: unavailable"
            dialog._worker_activity(
                [
                    {
                        "id": self.layer.id(),
                        "phase": "ready",
                        "message": "Done",
                        "server_warnings": [busy],
                    }
                ]
            )
            self.assertEqual(dialog.server_warning.text(), busy)
            dialog._update_progress("HTTP 404")
            self.assertEqual(dialog.server_warning.text(), busy)
            self.assertEqual(dialog._items[self.layer.id()].text(2), "Zapisano")
        finally:
            dialog.close()

    def test_worker_messages_are_deduplicated_and_do_not_overwrite_final_status(self):
        dialog = self.dialog()
        try:
            row = {
                "id": self.layer.id(),
                "phase": "active",
                "message": "zoom 17, fragment 2",
            }
            dialog._worker_activity([row])
            log = dialog.log.toPlainText()
            dialog._worker_activity([row])
            self.assertEqual(dialog.log.toPlainText(), log)
            self.assertIn("fragment 2", dialog._items[self.layer.id()].text(2))
            dialog._layer_status(
                {
                    "id": self.layer.id(),
                    "status": "failed",
                    "reason": "Nie udało się pobrać.",
                },
                1,
                1,
            )
            dialog._worker_activity([row])
            self.assertEqual(dialog._items[self.layer.id()].text(2), "Błąd")
            dialog.copy_button.click()
            from qgis.PyQt.QtWidgets import QApplication

            self.assertEqual(QApplication.clipboard().text(), dialog.log.toPlainText())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
