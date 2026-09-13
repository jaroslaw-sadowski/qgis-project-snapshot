# SPDX-License-Identifier: GPL-2.0-only

"""One project archive action in the QGIS Plugins menu and toolbar."""

from pathlib import Path

from qgis.PyQt.QtGui import QAction, QIcon

from .archive_dialog import ArchiveDialog
from .i18n import tr


class ProjectSnapshotPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.archive_action = None
        self.archive_dlg = None

    def initGui(self):
        self.archive_action = QAction(
            QIcon(str(Path(__file__).with_name("icon.svg"))),
            tr("Archiwizuj projekt…"),
            self.iface.mainWindow(),
        )
        self.archive_action.setObjectName("QgisProjectSnapshotArchive")
        self.archive_action.triggered.connect(self.run_archive)
        self.archive_action.setToolTip(
            tr(
                (
                    "QGIS Project Snapshot: zapisz kopię projektu, dane i mapy do "
                    "pracy bez sieci."
                )
            )
        )
        self.iface.addPluginToMenu("QGIS Project Snapshot", self.archive_action)
        self.iface.addToolBarIcon(self.archive_action)

    def unload(self):
        if self.archive_dlg:
            self.archive_dlg.reject()
        if self.archive_action:
            self.iface.removePluginMenu("QGIS Project Snapshot", self.archive_action)
            self.iface.removeToolBarIcon(self.archive_action)
            self.archive_action.deleteLater()
        self.archive_action = None

    def run_archive(self):
        if self.archive_dlg is not None:
            self.archive_dlg.raise_()
            return
        self.archive_dlg = ArchiveDialog(self.iface, self.iface.mainWindow())
        try:
            self.archive_dlg.exec()
        finally:
            self.archive_dlg = None
