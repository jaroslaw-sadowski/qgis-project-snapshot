# SPDX-License-Identifier: GPL-2.0-only

"""Check the built ZIP in an isolated QGIS profile and run integration tests from it.

Run with isolation using the command in docs/development.md.
"""

import argparse
import importlib
import os
import re
import stat
import sys
import unittest
from configparser import ConfigParser
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlsplit
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
            assert filename.stat().st_size <= 25_000_000
            assert archive.testzip() is None
            assert len(archive.namelist()) == len(set(archive.namelist()))
            for name in archive.namelist():
                path = Path(name)
                assert not path.is_absolute() and ".." not in path.parts
                assert path.parts[0] == "mbtiles_batch_exporter"
                assert len(path.parts) == 2
                assert not path.name.startswith(".") or path.name == ".flake8"
                assert path.name in {"LICENSE", ".flake8"} or path.suffix in {
                    ".py",
                    ".svg",
                    ".txt",
                    ".qm",
                    ".ts",
                    ".md",
                }
                mode = archive.getinfo(name).external_attr >> 16
                assert stat.S_ISREG(mode) and stat.S_IMODE(mode) == 0o644
            metadata = ConfigParser(interpolation=None)
            metadata.read_string(
                archive.read("mbtiles_batch_exporter/metadata.txt").decode("utf-8")
            )
            general = metadata["general"]
            for field in (
                "name",
                "qgisMinimumVersion",
                "qgisMaximumVersion",
                "description",
                "about",
                "version",
                "author",
                "email",
                "homepage",
                "repository",
                "tracker",
                "license",
                "icon",
                "changelog",
            ):
                assert general.get(field, "").strip(), f"Missing metadata: {field}"
            assert re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", general["email"])
            assert re.fullmatch(r"\d+\.\d+\.\d+", general["version"])
            assert general["qgisMinimumVersion"] == "3.40"
            assert general["qgisMaximumVersion"] == "4.99"
            assert general["license"] == "GPL-2.0-only"
            for field in ("homepage", "repository", "tracker"):
                url = urlsplit(general[field])
                assert url.scheme == "https" and url.hostname
            for field in (
                "experimental",
                "deprecated",
                "server",
                "hasProcessingProvider",
            ):
                assert general[field] == "False"
            for name in (
                "__init__.py",
                "LICENSE",
                "README.txt",
                "en.ts",
                "en.qm",
                general["icon"],
            ):
                assert archive.read("mbtiles_batch_exporter/" + name)
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
        assert interface.menu[0].objectName() == "QgisProjectSnapshotArchive"
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

        def unexpected_warning(parent, title, message, *args, **kwargs):
            raise AssertionError(
                f"Unexpected dialog warning: {title}: {message}"
            ) from sys.exc_info()[1]

        # Unexpected modal warnings must fail CI instead of waiting for a click.
        with patch(
            "qgis.PyQt.QtWidgets.QMessageBox.warning", side_effect=unexpected_warning
        ):
            result = unittest.TextTestRunner(verbosity=2).run(suite)
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
        QgsProject.instance().clear()
        interface.window.close()
        # Standalone QGIS must flush deferred provider cleanup before teardown.
        app.exitQgis()
        if not result.wasSuccessful() or result.skipped:
            raise RuntimeError(
                (
                    "Test paczki nie przeszedł w całości; wymagany jest "
                    "również lokalny WMS."
                )
            )
        print(f"ZIP: {result.testsRun} testów z zainstalowanej paczki — OK", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    check(parser.parse_args().zip.resolve())
