# -*- coding: utf-8 -*-
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction

from .dialog import MBTilesBatchExporterDialog

class MBTilesBatchExporterPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dlg = None

    def tr(self, message):
        return QCoreApplication.translate("MBTilesBatchExporter", message)

    def initGui(self):
        self.action = QAction(
            QIcon(),
            self.tr("MBTiles Batch Exporter…"),
            self.iface.mainWindow(),
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.tr("&MBTiles Batch Exporter"), self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu(self.tr("&MBTiles Batch Exporter"), self.action)
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
