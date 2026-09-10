# -*- coding: utf-8 -*-
from pathlib import Path
from .i18n import tr
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QStyle

from .dialog import MBTilesBatchExporterDialog
from .archive_dialog import ArchiveDialog

class MBTilesBatchExporterPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None
        self.archive_action = None
        self.archive_dlg = None

    def tr(self, message):
        return tr(message)

    def initGui(self):
        self.action = QAction(
            self.iface.mainWindow().style().standardIcon(QStyle.SP_DriveHDIcon),
            self.tr(tr('Eksportuj MBTiles…')),
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.run)
        self.archive_action = QAction(
            QIcon(str(Path(__file__).with_name('icon.svg'))),
            self.tr(tr('Archiwizuj projekt…')), self.iface.mainWindow(),
        )
        self.archive_action.triggered.connect(self.run_archive)
        self.iface.addPluginToMenu(self.tr("qgis-project-snapshot"), self.archive_action)
        self.iface.addToolBarIcon(self.archive_action)
        self.archive_action.setToolTip(tr('qgis-project-snapshot: zapisz kopię projektu, dane i mapy do pracy bez sieci.'))
        self.iface.addPluginToMenu(self.tr("qgis-project-snapshot"), self.action)
        self.iface.addToolBarIcon(self.action)
        self.action.setToolTip(tr('qgis-project-snapshot: dotychczasowy eksport map do oddzielnych plików MBTiles.'))

    def unload(self):
        if self.archive_dlg:
            self.archive_dlg.reject()
        if self.archive_action:
            self.iface.removePluginMenu(self.tr("qgis-project-snapshot"), self.archive_action)
            self.iface.removeToolBarIcon(self.archive_action)
        self.archive_action = None
        if self.action:
            self.iface.removePluginMenu(self.tr("qgis-project-snapshot"), self.action)
            self.iface.removeToolBarIcon(self.action)
        self.action = None
        self.dlg = None

    def run(self):
        if self.dlg is None:
            self.dlg = MBTilesBatchExporterDialog(self.iface, self.iface.mainWindow())
        # odśwież UI i listy przy każdym otwarciu
        self.dlg.prepare_on_open()
        self.dlg.show()
        self.dlg.raise_()
        self.dlg.activateWindow()

    def run_archive(self):
        if self.archive_dlg is not None:
            self.archive_dlg.raise_()
            return
        self.archive_dlg = ArchiveDialog(self.iface, self.iface.mainWindow())
        try:
            self.archive_dlg.exec_()
        finally:
            self.archive_dlg = None
