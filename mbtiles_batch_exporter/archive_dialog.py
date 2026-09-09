# -*- coding: utf-8 -*-
import json
import math
import os
from pathlib import Path
import time
from html import escape

from qgis.PyQt.QtCore import QCoreApplication, Qt, QUrl, QTimer
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QTreeWidget,
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
        self._started_at = None
        self._finished_at = None
        self._last_message = None
        self._worker_messages = {}
        self._finished_ids = set()
        self._items = {}
        self.setWindowTitle('qgis-project-snapshot — Archiwizuj projekt')
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(860, 790)
        layout = QVBoxLayout(self)
        notice = QLabel(
            'Zapisz projekt do pracy bez sieci. Najedź na opcję, aby zobaczyć objaśnienie.'
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
        browse.setToolTip('Wybierz istniejący folder. W nim powstanie nowy katalog archiwum z datą.')
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
        self.zoom_min = QComboBox()
        self.zoom_max = QComboBox()
        for combo, default in ((self.zoom_min, 13), (self.zoom_max, 17)):
            for zoom in range(25):
                combo.addItem(f'Zoom {zoom}', zoom)
            combo.setCurrentIndex(default)
            combo.currentIndexChanged.connect(self._ensure_zoom_order)
        form.addRow('Najmniejsze zbliżenie:', self.zoom_min)
        form.addRow('Największe zbliżenie:', self.zoom_max)
        self.workers = QComboBox()
        for count in range(1, 9):
            self.workers.addItem('1 — oszczędnie' if count == 1 else f'{count} procesy' if count < 5 else f'{count} procesów', count)
        self.workers.setCurrentIndex(min(4, os.cpu_count() or 1) - 1)
        form.addRow('Równoległe zadania:', self.workers)
        self.zoom_hint = QLabel()
        self.zoom_hint.setWordWrap(True)
        form.addRow(self.zoom_hint)
        self.polygon_combo.currentIndexChanged.connect(self._update_zoom_labels)
        options_layout.addLayout(form)
        selection = QHBoxLayout()
        for label, checked in [('Zaznacz wszystko', True), ('Odznacz wszystko', False)]:
            button = QPushButton(label)
            button.setToolTip('Zmienia wybór warstw do archiwum. Nie zmienia widoczności warstw w oryginalnym projekcie.')
            button.clicked.connect(lambda _, value=checked: self._select_all(value))
            selection.addWidget(button)
        selection.addStretch()
        options_layout.addLayout(selection)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Warstwa', 'Zapis', 'Stan'])
        self._populate_tree(self.project.layerTreeRoot(), self.tree.invisibleRootItem())
        self.tree.expandToDepth(0)
        self.tree.setColumnWidth(0, 290)
        self.tree.setColumnWidth(1, 160)
        options_layout.addWidget(self.tree, 1)
        layout.addWidget(self.options, 1)
        self.status = QLabel('Gotowe do wyboru obszaru i folderu.')
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat('Jeszcze nie uruchomiono')
        layout.addWidget(self.progress)
        self.elapsed = QLabel('Czas: 00:00')
        layout.addWidget(self.elapsed)
        self.workers_status = QLabel('')
        self.workers_status.setTextFormat(Qt.PlainText)
        self.workers_status.setWordWrap(True)
        self.workers_status.hide()
        layout.addWidget(self.workers_status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMinimumHeight(130)
        self.log.setMaximumHeight(180)
        self.log.setPlaceholderText('Tutaj pojawią się szczegóły przebiegu archiwizacji.')
        layout.addWidget(self.log)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_elapsed)
        buttons = QHBoxLayout()
        self.report_button = QPushButton('Otwórz raport')
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self._open_report)
        buttons.addWidget(self.report_button)
        self.copy_button = QPushButton('Kopiuj dziennik')
        self.copy_button.clicked.connect(lambda: QCoreApplication.instance().clipboard().setText(self.log.toPlainText()))
        buttons.addWidget(self.copy_button)
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
        tips = {
            notice: 'Powstaje osobna kopia projektu, dane lokalne i raport. Oryginał nie jest zastępowany. '
                    'Po eksporcie sprawdź raport i otwórz kopię bez internetu oraz sieci firmowej.',
            self.output_edit: 'Wybierz folder z wolnym miejscem na archiwum i pliki tymczasowe. '
                              'Powstanie osobny katalog z datą. Przenoś później cały ten katalog, nie sam plik projektu.',
            self.area_combo: 'Widok mapy zapisuje obszar aktualnie widoczny w QGIS. Poligony pozwalają wybrać '
                             'kształt pasa inwestycji. Całe obiekty wektorowe przecinające obszar zostaną zachowane.',
            self.polygon_combo: 'Wskaż warstwę z obszarem opracowania. Jeśli zaznaczono w niej obiekty, użyjemy '
                                'tylko zaznaczonych; w przeciwnym razie wszystkich. Mapy będą przycięte do ich kształtu.',
            self.zoom_min: 'Najmniejsze zbliżenie zapisanych map. Niski numer obejmuje większy teren z mniejszą '
                           'szczegółowością. Zapisujemy każdy poziom między minimum i maksimum; wektory zachowują pełne dane.',
            self.zoom_max: 'Największe zbliżenie zapisanych map. Wyższy numer pokazuje więcej szczegółów, '
                           'ale może mocno zwiększyć czas i rozmiar archiwum. Na pierwszą próbę pozostaw 17.',
            self.workers: 'Liczba map przetwarzanych równocześnie w osobnych procesach. 1 oszczędza pamięć; '
                          '2–4 zwykle pomaga przy większym obszarze. Limit to dwa zadania na serwer. '
                          'Wektory z niezapisanymi edycjami są odczytywane w głównym QGIS.',
            self.zoom_hint: 'To przybliżenie dla prostokąta obszaru, na jedną mapę i cały zakres zoomów. '
                            'Dla pasa pobieramy tylko kafelki przecinające jego kształt. Skale obliczono dla środka obszaru przy 96 DPI.',
            self.tree: 'Zaznacz warstwy do archiwum. Wyłączone na mapie warstwy też można zapisać. '
                       'Kolumna Stan pokazuje kolejkę, pobieranie, zapis lub problem. Najedź na stan, aby przeczytać szczegóły.',
            self.progress: 'Licznik zakończonych warstw, nie prognoza czasu. Warstwy mają różne rozmiary. '
                           'Po zapisie danych trzeba jeszcze sprawdzić pliki i przygotować raport.',
            self.status: 'Aktualna czynność głównego QGIS. Postęp równoległych map znajdziesz w kolumnie Stan i dzienniku.',
            self.elapsed: 'Czas od uruchomienia eksportu. Brak nowego komunikatu nie musi oznaczać zatrzymania: '
                          'niektóre źródła długo odpowiadają na zapytanie.',
            self.workers_status: 'Podsumowanie procesów mapowych: zadania pracujące, oczekujące i gotowe do scalenia. '
                                 'Szczegóły każdej mapy są w kolumnie Stan.',
            self.log: 'Ostatnie 2000 komunikatów z czasem od startu: etapy, warstwy, zoomy, fragmenty, ponowienia '
                      'i wyniki. Nie zawiera pełnych adresów źródeł ani poświadczeń. Pełny wynik warstw zapisuje raport.',
            self.copy_button: 'Kopiuje widoczny dziennik do schowka, aby można go było dołączyć do opisu problemu. '
                              'Dziennik może zawierać nazwy warstw z projektu.',
            self.report_button: 'Otwiera raport gotowego archiwum: zapisane i brakujące warstwy oraz elementy do sprawdzenia.',
            self.start_button: 'Rozpoczyna zapis zaznaczonych warstw i kopii projektu. PNG zachowuje przezroczystość '
                               'i kompresję bezstratną. Po zakończeniu sprawdź wynik bez sieci.',
            self.cancel_button: 'Zatrzymuje kolejne zadania i przerywa pobieranie. Ukończone, scalone warstwy pozostają '
                                'w archiwum. Niektóre operacje mogą potrzebować chwili na zakończenie.',
            self.close_button: 'Zamyka okno. Podczas eksportu działa jak Przerwij; okno pozostanie otwarte do zakończenia zapisu.',
        }
        for widget, text in tips.items():
            widget.setToolTip(f'<p>{escape(text)}</p>')
        for row in range(form.rowCount()):
            label = form.itemAt(row, QFormLayout.LabelRole)
            field = form.itemAt(row, QFormLayout.FieldRole)
            if label and label.widget() and field:
                widget = field.widget() or self.output_edit
                label.widget().setToolTip(widget.toolTip())
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
                self._items[child.layerId()] = item
                item.setText(1, 'Dane wektorowe' if isinstance(layer, QgsVectorLayer)
                             else 'Mapa lub raster')
                item.setText(2, 'Gotowa do wyboru')
                item.setToolTip(1, 'Wektor zachowuje obiekty i atrybuty. Obraz mapy zachowuje wygląd. '
                                  'Jeśli nie uda się zapisać danych, raport wskaże próbę zastąpienia ich obrazem.')
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
            self.zoom_hint.setText(f'Szacunkowo do {count:,} kafelków na mapę.')
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
        self._started_at = time.monotonic()
        self._finished_at = None
        self._last_message = None
        self._last_change = self._started_at
        self._finished_ids.clear()
        self._worker_messages.clear()
        self.log.clear()
        self.workers_status.clear()
        for layer_id, item in self._items.items():
            item.setText(2, 'W kolejce' if layer_id in selected_ids else 'Pominięto')
            item.setToolTip(2, 'Czeka na rozpoczęcie eksportu.' if layer_id in selected_ids else 'Warstwa nie jest zaznaczona do eksportu.')
        self.options.setEnabled(False)
        self.start_button.setEnabled(False)
        self.report_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, len(selected_ids) + 1)
        self.progress.setValue(0)
        self.progress.setFormat(f'Zakończone warstwy: 0/{len(selected_ids)}')
        self.timer.start()
        try:
            self._update_progress('Wyznaczanie obszaru archiwizacji…')
            area, crs = self._area()
            self._result = create_archive(
                self.project, selected_ids, area, crs, folder,
                cancelled=lambda: self._cancelled, progress=self._update_progress,
                zoom_min=self.zoom_min.currentData(), zoom_max=self.zoom_max.currentData(),
                workers=self.workers.currentData(),
                layer_status=self._layer_status, worker_activity=self._worker_activity,
            )
            self._finished_at = time.monotonic()
            self.timer.stop()
            manifest = json.loads((self._result / 'manifest.json').read_text(encoding='utf-8'))
            saved = sum(record['status'] == 'saved' for record in manifest['layers'])
            missing = sum(record['status'] in ('failed', 'cancelled') for record in manifest['layers'])
            review = sum(record['status'] in ('empty', 'partial') for record in manifest['layers'])
            self.status.setText(f'Archiwum częściowe: zapisano {saved} warstw; do sprawdzenia: {review}; '
                                f'niezapisanych: {missing}.\n{self._result}')
            self._append_log(self.status.text())
            self.progress.setValue(self.progress.maximum())
            self.progress.setFormat('Przerwano — sprawdź raport' if manifest['cancelled'] else 'Zakończono — sprawdź raport')
            self.report_button.setEnabled(True)
            QMessageBox.information(self, 'Archiwum częściowe',
                                    self.status.text() + '\nSzczegóły i przyczyny braków znajdziesz w raporcie.')
        except (ValueError, OSError, RuntimeError) as error:
            self._finished_at = time.monotonic()
            self.timer.stop()
            self.status.setText('Nie utworzono archiwum. Oryginalny projekt nie został zastąpiony.')
            self._append_log(self.status.text())
            self._append_log(f'Błąd: {error}')
            self.progress.setFormat('Błąd — nie utworzono archiwum')
            QMessageBox.warning(self, 'Archiwizacja', str(error))
        except Exception:
            self._finished_at = time.monotonic()
            self.timer.stop()
            self.status.setText('Nie utworzono archiwum z powodu nieoczekiwanego błędu.')
            self._append_log(self.status.text())
            self.progress.setFormat('Błąd — nie utworzono archiwum')
            QMessageBox.warning(self, 'Archiwizacja', self.status.text())
        finally:
            self._running = False
            self.timer.stop()
            self._update_elapsed()
            self.options.setEnabled(True)
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)

    def _update_progress(self, message):
        if message != self._last_message:
            self._last_message = message
            self._append_log(message)
        self.status.setText(('Przerywanie — ' if self._cancelled else '') + message)
        QCoreApplication.processEvents()

    def _append_log(self, message):
        self._last_change = time.monotonic()
        seconds = int(self._last_change - self._started_at) if self._started_at is not None else 0
        self.log.appendPlainText(f'[{seconds // 60:02d}:{seconds % 60:02d}] {message}')

    def _update_elapsed(self):
        if self._started_at is None:
            return
        seconds = int((self._finished_at or time.monotonic()) - self._started_at)
        quiet = int(time.monotonic() - self._last_change)
        text = f'Czas: {seconds // 60:02d}:{seconds % 60:02d}'
        if self._running and self._finished_at is None and quiet >= 10:
            text += f' — ostatni komunikat {quiet} s temu; trwa powyższa czynność.'
        self.elapsed.setText(text)

    def _layer_status(self, record, completed, total):
        item = self._items.get(record['id'])
        labels = {'pending': 'Przetwarzanie', 'saved': 'Zapisano', 'empty': 'Pusty obraz — sprawdź',
                  'partial': 'Brak części obrazu', 'failed': 'Błąd', 'cancelled': 'Przerwano'}
        if item is not None:
            item.setText(2, labels.get(record['status'], record['status']))
            item.setToolTip(2, f'<p>{escape(record.get("reason") or "Przygotowanie warstwy do archiwizacji.")}</p>')
        if record['status'] != 'pending':
            self._finished_ids.add(record['id'])
        self.progress.setValue(completed)
        self.progress.setFormat(f'Zakończone warstwy: {completed}/{total}' + (' — kontrola plików' if completed == total else ''))

    def _worker_activity(self, rows):
        active = sum(row['phase'] == 'active' for row in rows)
        queued = sum(row['phase'] == 'queued' for row in rows)
        ready = sum(row['phase'] == 'ready' for row in rows)
        self.workers_status.setVisible(bool(rows))
        self.workers_status.setText(f'Mapy: pracuje {active} • w kolejce {queued} • czeka na scalenie {ready}' if rows else '')
        for row in rows:
            if row['id'] in self._finished_ids:
                continue
            item = self._items.get(row['id'])
            if item is None:
                continue
            message = row['message'].removeprefix(item.text(0) + ': ').removeprefix(item.text(0) + ' — ')
            item.setText(2, message)
            item.setToolTip(2, f'<p>{escape(message)}</p>')
            state = (row['phase'], message)
            if self._worker_messages.get(row['id']) != state:
                self._worker_messages[row['id']] = state
                self._append_log(f'{item.text(0)}: {message}')

    def cancel(self):
        self._cancelled = True
        self.cancel_button.setEnabled(False)
        self.status.setText('Przerywanie… Ukończone warstwy zostaną zachowane w archiwum częściowym.')
        self._append_log(self.status.text())

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
