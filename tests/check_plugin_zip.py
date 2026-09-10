"""Check the built ZIP in an isolated QGIS profile and run integration tests from it.

Run with isolation using the command in docs/development.md.
"""

import argparse
import importlib
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def check(filename):
    os.environ["QGIS_SNAPSHOT_LANGUAGE"] = "pl"
    import qgis.utils
    from qgis.core import (
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRectangle,
    )
    from qgis.gui import QgsMapCanvas
    from qgis.PyQt.QtCore import QTimer
    from qgis.PyQt.QtWidgets import QMainWindow

    with TemporaryDirectory(prefix="qgis-installed-plugin-") as temporary:
        profile = Path(temporary)
        os.environ["QGIS_CUSTOM_CONFIG_PATH"] = str(profile)
        plugins = profile / "python" / "plugins"
        plugins.mkdir(parents=True)
        with ZipFile(filename) as archive:
            assert archive.testzip() is None
            for name in archive.namelist():
                path = Path(name)
                assert not path.is_absolute() and ".." not in path.parts
                assert path.parts[0] == "mbtiles_batch_exporter"
            archive.extractall(plugins)
        sys.path.insert(0, str(plugins))
        app = QgsApplication([], True, str(profile))
        app.initQgis()
        sys.path.append(str(Path(QgsApplication.pkgDataPath()) / "python" / "plugins"))
        from processing.core.Processing import Processing

        Processing.initialize()

        class Interface:
            def __init__(self):
                self.window = QMainWindow()
                self.canvas = QgsMapCanvas(self.window)
                self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:2180"))
                self.canvas.setExtent(QgsRectangle(500000, 500000, 500512, 500512))
                self.menu = []
                self.toolbar = []

            def mainWindow(self):
                return self.window

            def mapCanvas(self):
                return self.canvas

            def addPluginToMenu(self, menu, action):
                assert menu == "QGIS Project Snapshot"
                self.menu.append(action)

            def removePluginMenu(self, menu, action):
                self.menu.remove(action)

            def addToolBarIcon(self, action):
                self.toolbar.append(action)

            def removeToolBarIcon(self, action):
                self.toolbar.remove(action)

        interface = Interface()
        qgis.utils.iface = interface
        qgis.utils.plugin_paths = [str(plugins)]
        qgis.utils.updateAvailablePlugins()
        assert "mbtiles_batch_exporter" in qgis.utils.available_plugins
        assert qgis.utils.loadPlugin("mbtiles_batch_exporter")
        assert qgis.utils.startPlugin("mbtiles_batch_exporter")
        plugin = qgis.utils.plugins["mbtiles_batch_exporter"]
        module = importlib.import_module("mbtiles_batch_exporter")
        assert Path(module.__file__).resolve().is_relative_to(plugins)
        assert len(interface.menu) == len(interface.toolbar) == 1
        assert interface.menu[0].text() == "Archiwizuj projekt…"
        assert (
            qgis.utils.pluginMetadata("mbtiles_batch_exporter", "name")
            == "QGIS Project Snapshot"
        )
        QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:2180"))
        opened = []

        def close_archive():
            dialog = plugin.archive_dlg
            opened.append(dialog is not None and dialog.isVisible())
            if dialog is not None:
                assert dialog.windowTitle().startswith("QGIS Project Snapshot")
                dialog.reject()

        QTimer.singleShot(0, close_archive)
        plugin.archive_action.trigger()
        assert opened == [True] and plugin.archive_dlg is None
        assert qgis.utils.unloadPlugin("mbtiles_batch_exporter")
        assert not interface.menu and not interface.toolbar
        print(
            "ZIP: wykrywanie, ładowanie, okno archiwizacji i wyłączenie wtyczki — OK",
            flush=True,
        )

        # All tests now import the installed package, including its worker entry point.
        tests = Path(__file__).resolve().parent
        suite = unittest.defaultTestLoader.discover(str(tests), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        loaded = [
            m
            for name, m in sys.modules.items()
            if name.startswith("mbtiles_batch_exporter")
        ]
        assert all(
            Path(m.__file__).resolve().is_relative_to(plugins)
            for m in loaded
            if getattr(m, "__file__", None)
        )
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError(
                (
                    "Test paczki nie przeszedł w całości; wymagany jest "
                    "również lokalny WMS."
                )
            )
        QgsProject.instance().clear()
        interface.window.close()
        print(f"ZIP: {result.testsRun} testów z zainstalowanej paczki — OK", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    check(parser.parse_args().zip.resolve())
