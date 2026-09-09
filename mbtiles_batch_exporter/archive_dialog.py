# -*- coding: utf-8 -*-
import json
import math
import os
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QTreeWidget,
    QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget,
)
from qgis.core import (
    QgsCoordinateTransform, QgsGeometry, QgsLayerTreeGroup, QgsProject,
    QgsUnitTypes, QgsVectorLayer, QgsWkbTypes,
)

from .archive import create_archive, polygon_area
from .raster_archive import TILE_SIZE, zoom_levels


class ArchiveDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.project = QgsProject.instance()
        self._running = False
        self._cancelled = False
        self._result = None
        self.setWindowTitle('Archiwizuj projekt — dane i obrazy offline')
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(780, 680)
        layout = QVBoxLayout(self)
        notice = QLabel(
            'Zapisujemy dane i obrazy map offline. PNG zachowuje przezroczystość '
            'z maksymalną bezstratną kompresją. Kopiujemy lokalne symbole i załączniki. '
            'Raport wskazuje zależności wymagające kontroli; archiwum wymaga odbioru offline.'
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)

        self.options = QWidget()
        options_layout = QVBoxLayout(self.options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.output_edit = QLineEdit()
        output = QHBoxLayout()
        output.addWidget(self.output_edit)
        browse = QPushButton('Wybierz…')
        browse.clicked.connect(self._browse)
        output.addWidget(browse)
        form.addRow('Folder archiwum:', output)
        self.area_combo = QComboBox()
        self.area_combo.addItems(['Aktualny widok mapy', 'Obszar z warstwy poligonowej'])
        self.area_combo.currentIndexChanged.connect(self._update_area)
        form.addRow('Obszar:', self.area_combo)
        self.polygon_combo = QComboBox()
        for layer in self.project.mapLayers().values():
            if (isinstance(layer, QgsVectorLayer) and layer.isValid()
                    and layer.geometryType() == QgsWkbTypes.PolygonGeometry):
                self.polygon_combo.addItem(layer.name(), layer.id())
        form.addRow('Warstwa obszaru:', self.polygon_combo)
        hint = QLabel('Dla poligonów używamy zaznaczonych obiektów, a przy braku zaznaczenia — wszystkich. '
                      'Zachowujemy całe obiekty wektorowe przecinające obszar.')
        hint.setWordWrap(True)
        form.addRow(hint)
        self.zoom_min = QComboBox()
        self.zoom_max = QComboBox()
        for combo, default in ((self.zoom_min, 13), (self.zoom_max, 17)):
            for zoom in range(25):
                combo.addItem(f'Zoom {zoom}', zoom)
            combo.setCurrentIndex(default)
            combo.currentIndexChanged.connect(self._ensure_zoom_order)
        form.addRow('Obrazy — zoom minimalny:', self.zoom_min)
        form.addRow('Obrazy — zoom maksymalny:', self.zoom_max)
        self.workers = QComboBox()
        for count in range(1, 9):
            self.workers.addItem('1 — oszczędnie' if count == 1 else f'{count} procesy' if count < 5 else f'{count} procesów', count)
        self.workers.setCurrentIndex(min(4, os.cpu_count() or 1) - 1)
        form.addRow('Równoległe pobieranie map:', self.workers)
        self.zoom_hint = QLabel()
        self.zoom_hint.setWordWrap(True)
        form.addRow(self.zoom_hint)
        self.polygon_combo.currentIndexChanged.connect(self._update_zoom_labels)
        options_layout.addLayout(form)
        selection = QHBoxLayout()
        for label, checked in [('Zaznacz wszystko', True), ('Odznacz wszystko', False)]:
            button = QPushButton(label)
            button.clicked.connect(lambda _, value=checked: self._select_all(value))
            selection.addWidget(button)
        selection.addStretch()
        options_layout.addLayout(selection)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Warstwy do archiwizacji', 'Sposób zapisu'])
        self._populate_tree(self.project.layerTreeRoot(), self.tree.invisibleRootItem())
        self.tree.expandToDepth(0)
        self.tree.setColumnWidth(0, 480)
        options_layout.addWidget(self.tree, 1)
        layout.addWidget(self.options, 1)
        self.status = QLabel('Gotowe do wyboru obszaru i folderu.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        buttons = QHBoxLayout()
        self.report_button = QPushButton('Otwórz raport')
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self._open_report)
        buttons.addWidget(self.report_button)
        buttons.addStretch()
        self.start_button = QPushButton('Utwórz archiwum')
        self.start_button.clicked.connect(self.start)
        buttons.addWidget(self.start_button)
        self.cancel_button = QPushButton('Przerwij')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        buttons.addWidget(self.cancel_button)
        self.close_button = QPushButton('Zamknij')
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self._update_area()

    def _populate_tree(self, node, parent):
        for child in node.children():
            item = QTreeWidgetItem(parent, [child.name()])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if isinstance(child, QgsLayerTreeGroup):
                item.setFlags(item.flags() | Qt.ItemIsAutoTristate)
                self._populate_tree(child, item)
            else:
                layer = child.layer()
                item.setData(0, Qt.UserRole, child.layerId())
                item.setText(1, 'Wektor → GeoPackage' if isinstance(layer, QgsVectorLayer)
                             else 'Raster / obraz offline')
            item.setCheckState(0, Qt.Checked)

    def _select_all(self, checked):
        state = Qt.Checked if checked else Qt.Unchecked
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setCheckState(0, state)

    def _update_area(self):
        self.polygon_combo.setEnabled(self.area_combo.currentIndex() == 1)
        self._update_zoom_labels()

    def _area(self, use_geometry=True):
        if self.area_combo.currentIndex() == 0:
            if self.iface is None:
                raise ValueError('Podgląd skali wymaga widoku mapy.')
            canvas = self.iface.mapCanvas()
            return QgsGeometry.fromRect(canvas.extent()), canvas.mapSettings().destinationCrs()
        layer = self.project.mapLayer(self.polygon_combo.currentData())
        if layer is None or not layer.isValid():
            raise ValueError('Wybierz dostępną warstwę poligonową.')
        if use_geometry:
            area = polygon_area(layer)
        else:
            bounds = layer.boundingBoxOfSelected() if layer.selectedFeatureCount() else layer.extent()
            area = QgsGeometry.fromRect(bounds)
        return area, layer.crs()

    def _ensure_zoom_order(self):
        if self.zoom_min.currentData() > self.zoom_max.currentData():
            if self.sender() is self.zoom_min:
                self.zoom_max.setCurrentIndex(self.zoom_min.currentIndex())
            else:
                self.zoom_min.setCurrentIndex(self.zoom_max.currentIndex())
        if hasattr(self, 'zoom_hint'):
            self._update_zoom_labels()

    def _update_zoom_labels(self):
        try:
            area, crs = self._area(use_geometry=False)
            levels = zoom_levels(self.project, area, crs, 0, 24)
            unit = QgsUnitTypes.toAbbreviatedString(self.project.crs().mapUnits())
            for level in levels:
                label = f'Zoom {level["zoom"]} ≈ 1:{level["scale"]:,.0f} ({level["resolution"]:.3g} {unit}/piksel)'
                for combo in (self.zoom_min, self.zoom_max):
                    combo.setItemText(level['zoom'], label)
            if crs != self.project.crs():
                area.transform(QgsCoordinateTransform(crs, self.project.crs(), self.project))
            box = area.boundingBox()
            count = sum(math.ceil(box.width() / (TILE_SIZE * level['resolution']))
                        * math.ceil(box.height() / (TILE_SIZE * level['resolution']))
                        for level in levels[self.zoom_min.currentData():self.zoom_max.currentData() + 1])
            self.zoom_hint.setText(f'Skala przybliżona dla środka obszaru, 96 DPI. Do {count:,} kafelków na mapę '
                                   '(prostokąt zasięgu); dla pasa pobieramy tylko jego kształt. '
                                   'Zoom nie ogranicza szczegółowości zachowanych danych wektorowych.')
        except Exception:
            self.zoom_hint.setText('Wybierz poprawny obszar, aby zobaczyć skalę dla każdego zoomu.')

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, 'Folder na archiwum projektu')
        if folder:
            self.output_edit.setText(folder)

    def _selected_ids(self):
        ids = set()
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            layer_id = item.data(0, Qt.UserRole)
            if layer_id and item.checkState(0) == Qt.Checked:
                ids.add(layer_id)
            iterator += 1
        return ids

    def start(self):
        if self._running:
            return
        folder = self.output_edit.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(self, 'Folder archiwum', 'Wybierz istniejący folder zapisu.')
            return
        selected_ids = self._selected_ids()
        if not selected_ids:
            QMessageBox.warning(self, 'Warstwy', 'Zaznacz przynajmniej jedną warstwę.')
            return
        self._running = True
        self._cancelled = False
        self._result = None
        self.options.setEnabled(False)
        self.start_button.setEnabled(False)
        self.report_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 0)
        try:
            area, crs = self._area()
            self._result = create_archive(
                self.project, selected_ids, area, crs, folder,
                cancelled=lambda: self._cancelled, progress=self._update_progress,
                zoom_min=self.zoom_min.currentData(), zoom_max=self.zoom_max.currentData(),
                workers=self.workers.currentData(),
            )
            manifest = json.loads((self._result / 'manifest.json').read_text(encoding='utf-8'))
            saved = sum(record['status'] == 'saved' for record in manifest['layers'])
            missing = sum(record['status'] in ('failed', 'cancelled') for record in manifest['layers'])
            review = sum(record['status'] in ('empty', 'partial') for record in manifest['layers'])
            self.status.setText(f'Archiwum częściowe: zapisano {saved} warstw; do sprawdzenia: {review}; '
                                f'niezapisanych: {missing}.\n{self._result}')
            self.report_button.setEnabled(True)
            QMessageBox.information(self, 'Archiwum częściowe',
                                    self.status.text() + '\nSzczegóły i przyczyny braków znajdziesz w raporcie.')
        except (ValueError, OSError, RuntimeError) as error:
            self.status.setText('Nie utworzono archiwum. Oryginalny projekt nie został zastąpiony.')
            QMessageBox.warning(self, 'Archiwizacja', str(error))
        except Exception:
            self.status.setText('Nie utworzono archiwum z powodu nieoczekiwanego błędu.')
            QMessageBox.warning(self, 'Archiwizacja', self.status.text())
        finally:
            self._running = False
            self.progress.setRange(0, 1)
            self.progress.setValue(1 if self._result else 0)
            self.options.setEnabled(True)
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)

    def _update_progress(self, message):
        self.status.setText(message)
        QCoreApplication.processEvents()

    def cancel(self):
        self._cancelled = True
        self.cancel_button.setEnabled(False)
        self.status.setText('Przerywanie… Ukończone warstwy zostaną zachowane w archiwum częściowym.')

    def reject(self):
        if self._running:
            self.cancel()
        else:
            super().reject()

    def closeEvent(self, event):
        if self._running:
            self.cancel()
            event.ignore()
        else:
            super().closeEvent(event)

    def _open_report(self):
        if self._result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._result / 'raport.html')))
