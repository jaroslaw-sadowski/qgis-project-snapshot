# -*- coding: utf-8 -*-
from pathlib import Path
import time

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QCoreApplication
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QLabel, QComboBox, QSpinBox,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QGroupBox,
    QCheckBox
)

from qgis.core import (
    QgsProject,
    QgsMapLayer,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsMessageLog,
    Qgis,
)

import processing

from .utils import (
    get_algorithm_id,
    iter_target_layer_nodes,
    build_output_file,
    canvas_extent_string,
    polygon_layer_extent_string,
)

class _SignalFeedback(QgsProcessingFeedback, QObject):
    progressChanged = pyqtSignal(float)
    textWritten = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)
        QgsProcessingFeedback.__init__(self)

    def setProgress(self, progress):
        super().setProgress(progress)
        try:
            self.progressChanged.emit(float(progress))
        except Exception:
            pass

    def pushInfo(self, info):
        super().pushInfo(info)
        self.textWritten.emit(str(info))

    def pushCommandInfo(self, info):
        super().pushCommandInfo(info)
        self.textWritten.emit(str(info))

    def pushDebugInfo(self, info):
        super().pushDebugInfo(info)
        self.textWritten.emit(str(info))

    def reportError(self, error, fatalError=False):
        super().reportError(error, fatalError)
        self.textWritten.emit(str(error))

class MBTilesBatchExporterDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle("qgis-project-snapshot — Eksport MBTiles")
        self.resize(760, 640)

        self.alg_id = None
        self.all_layer_nodes = None
        self.target_nodes = None
        self._original_visibility = None

        self._queue = []
        self._current_index = -1

        self._current_feedback = None
        self._cancel_requested = False
        self._failed_layers = []

        self._canvas_render_flag = None
        self._ui_last_pump = 0.0

        self._build_ui()
        self._populate_layer_list(default_check_all=True)
        self._populate_polygon_layers()
        self._update_extent_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Output folder
        out_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_browse = QPushButton("Wybierz…")
        self.output_browse.clicked.connect(self._browse_output)
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(self.output_browse)

        form = QFormLayout()
        form.addRow("Folder zapisu:", out_row)

        self.extent_combo = QComboBox()
        self.extent_combo.addItems(["Aktualny widok mapy", "Obszar z warstwy poligonowej"])
        self.extent_combo.currentIndexChanged.connect(self._update_extent_ui)

        self.poly_layer_combo = QComboBox()
        self.poly_layer_hint = QLabel("Użyj zaznaczonych poligonów lub całej warstwy.")
        self.poly_layer_hint.setWordWrap(True)

        form.addRow("Obszar:", self.extent_combo)
        form.addRow("Warstwa poligonowa:", self.poly_layer_combo)
        form.addRow("", self.poly_layer_hint)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG"])
        form.addRow("Format kafli:", self.format_combo)

        zoom_row = QHBoxLayout()
        self.zoom_min = QSpinBox(); self.zoom_min.setRange(0, 24); self.zoom_min.setValue(13)
        self.zoom_max = QSpinBox(); self.zoom_max.setRange(0, 24); self.zoom_max.setValue(17)
        self.zoom_min.valueChanged.connect(self._ensure_zoom_order)
        self.zoom_max.valueChanged.connect(self._ensure_zoom_order)
        zoom_row.addWidget(QLabel("min"))
        zoom_row.addWidget(self.zoom_min)
        zoom_row.addSpacing(12)
        zoom_row.addWidget(QLabel("max"))
        zoom_row.addWidget(self.zoom_max)
        zoom_row.addStretch(1)
        form.addRow("Zoom:", zoom_row)

        self.jpeg_quality = QSpinBox(); self.jpeg_quality.setRange(1, 100); self.jpeg_quality.setValue(75)
        form.addRow("Jakość JPEG:", self.jpeg_quality)

        self.chk_pause_render = QCheckBox("Wstrzymaj odświeżanie mapy")
        self.chk_pause_render.setChecked(True)
        form.addRow("", self.chk_pause_render)

        layout.addLayout(form)

        # Layer selection group
        grp = QGroupBox("Warstwy do eksportu")
        grp_layout = QVBoxLayout(grp)

        top = QHBoxLayout()
        self.btn_select_all = QPushButton("Zaznacz wszystko")
        self.btn_select_none = QPushButton("Odznacz wszystko")
        self.btn_refresh_layers = QPushButton("Odśwież listę")
        self.btn_select_all.clicked.connect(lambda: self._set_all_layers_checked(True))
        self.btn_select_none.clicked.connect(lambda: self._set_all_layers_checked(False))
        self.btn_refresh_layers.clicked.connect(lambda: self._populate_layer_list(default_check_all=True))
        top.addWidget(self.btn_select_all)
        top.addWidget(self.btn_select_none)
        top.addStretch(1)
        top.addWidget(self.btn_refresh_layers)

        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.layer_list.setAlternatingRowColors(True)
        self.layer_list.setMinimumHeight(160)

        grp_layout.addLayout(top)
        grp_layout.addWidget(self.layer_list)
        layout.addWidget(grp)

        # Progress + log
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(QLabel("Postęp:"))
        layout.addWidget(self.progress)
        layout.addWidget(QLabel("Dziennik:"))
        layout.addWidget(self.log, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.cancel_btn = QPushButton("Przerwij")
        self.close_btn = QPushButton("Zamknij")

        self.run_btn.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self.cancel)
        self.close_btn.clicked.connect(self.close)

        self.cancel_btn.setEnabled(False)

        btn_row.addStretch(1)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.close_btn)

        layout.addLayout(btn_row)

        tips = {
            self.output_edit: 'Wskaż folder na pliki MBTiles. Ten tryb zapisuje osobny plik dla każdej mapy, bez kopii całego projektu.',
            self.output_browse: 'Otwiera wybór folderu zapisu.',
            self.extent_combo: 'Widok mapy używa aktualnego zasięgu QGIS. Warstwa poligonowa wyznacza prostokąt '
                               'obejmujący zaznaczone obiekty, a bez zaznaczenia wszystkie. Przycinanie do kształtu pasa jest dostępne w Archiwizuj projekt.',
            self.poly_layer_combo: 'Wybierz poligony wyznaczające zasięg. Zaznaczenie obiektów ma pierwszeństwo przed całą warstwą.',
            self.poly_layer_hint: 'Ten eksporter używa prostokąta otaczającego poligony. Nie wycina ich dokładnego kształtu.',
            self.format_combo: 'PNG zachowuje przezroczystość. JPEG tworzy obraz bez przezroczystości i może tracić szczegóły.',
            self.zoom_min: 'Najmniejszy zapisany zoom: widok większego obszaru z mniejszą szczegółowością.',
            self.zoom_max: 'Największy zapisany zoom: więcej szczegółów, ale zwykle większy plik i dłuższy eksport.',
            self.jpeg_quality: 'Dotyczy tylko JPEG. Wyższa wartość oznacza mniej strat i większy plik; nie zmienia jakości PNG.',
            self.chk_pause_render: 'Podczas eksportu nie odświeżaj mapy głównej. Ogranicza dodatkową pracę QGIS; stan zostanie przywrócony po eksporcie.',
            self.layer_list: 'Zaznacz mapy do zapisania jako MBTiles. Do archiwum całego projektu użyj osobnej akcji Archiwizuj projekt.',
            self.btn_select_all: 'Zaznacza wszystkie warstwy z listy do eksportu.',
            self.btn_select_none: 'Odznacza wszystkie warstwy z listy.',
            self.btn_refresh_layers: 'Wczytuje ponownie warstwy projektu i zaznacza je wszystkie.',
            self.progress: 'Postęp eksportu bieżącej warstwy zgłaszany przez algorytm QGIS.',
            self.log: 'Komunikaty algorytmu, kolejne warstwy i błędy eksportu.',
            self.run_btn: 'Rozpoczyna eksport zaznaczonych map do plików MBTiles.',
            self.cancel_btn: 'Prosi algorytm o przerwanie eksportu. Zakończenie bieżącej operacji może chwilę potrwać.',
            self.close_btn: 'Zamyka okno eksportera MBTiles.',
        }
        for widget, text in tips.items():
            widget.setToolTip(f'<p>{text}</p>')


    def prepare_on_open(self):
        """Wywoływane przy każdym otwarciu okna z menu: odświeża listy i czyści UI."""
        # 1) wyczyść UI
        self.progress.setValue(0)
        self.log.clear()

        # 2) odśwież listę warstw i zaznacz wszystkie
        self._populate_layer_list(default_check_all=True)

        # 3) odśwież listę warstw poligonowych (extent)
        self._populate_polygon_layers()
        self._update_extent_ui()

    def _pump_ui(self, force: bool = False):
        now = time.monotonic()
        if force or (now - self._ui_last_pump) > 0.15:
            QCoreApplication.processEvents()
            self._ui_last_pump = now

    def _log(self, msg: str):
        self.log.append(msg)
        self._pump_ui()

    def _populate_layer_list(self, default_check_all: bool = True):
        self.layer_list.clear()
        layers = []
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr and lyr.isValid() and lyr.type() in (QgsMapLayer.VectorLayer, QgsMapLayer.RasterLayer):
                layers.append(lyr)
        layers.sort(key=lambda l: (l.name() or "").lower())

        for lyr in layers:
            item = QListWidgetItem(f"{lyr.name()}  —  {lyr.providerType()}")
            item.setData(Qt.UserRole, lyr.id())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if default_check_all else Qt.Unchecked)
            self.layer_list.addItem(item)

        if not layers:
            item = QListWidgetItem("— brak warstw wektorowych/rastrowych —")
            item.setFlags(Qt.NoItemFlags)
            self.layer_list.addItem(item)

    def _set_all_layers_checked(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(state)

    def _selected_layer_ids(self):
        ids = []
        for i in range(self.layer_list.count()):
            item = self.layer_list.item(i)
            if not (item.flags() & Qt.ItemIsUserCheckable):
                continue
            if item.checkState() == Qt.Checked:
                layer_id = item.data(Qt.UserRole)
                if layer_id:
                    ids.append(layer_id)
        return ids

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder na pliki MBTiles", "")
        if folder:
            self.output_edit.setText(folder)

    def _populate_polygon_layers(self):
        self.poly_layer_combo.clear()
        self._poly_layers = []
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.isValid() and layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                self._poly_layers.append(layer)
                self.poly_layer_combo.addItem(layer.name(), layer.id())
        if not self._poly_layers:
            self.poly_layer_combo.addItem("— brak warstw poligonowych —", None)

    def _update_extent_ui(self):
        use_poly = (self.extent_combo.currentIndex() == 1)
        self.poly_layer_combo.setEnabled(use_poly and bool(self._poly_layers))
        self.poly_layer_hint.setEnabled(use_poly and bool(self._poly_layers))

    def _ensure_zoom_order(self):
        if self.zoom_min.value() > self.zoom_max.value():
            sender = self.sender()
            if sender is self.zoom_min:
                self.zoom_max.setValue(self.zoom_min.value())
            else:
                self.zoom_min.setValue(self.zoom_max.value())

    def _get_extent_string(self) -> str:
        if self.extent_combo.currentIndex() == 0:
            return canvas_extent_string(self.iface)

        layer_id = self.poly_layer_combo.currentData()
        if not layer_id:
            raise RuntimeError("Nie wybrano warstwy poligonowej (lub brak warstw poligonowych w projekcie).")
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer or not layer.isValid():
            raise RuntimeError("Wybrana warstwa poligonowa jest nieprawidłowa.")
        return polygon_layer_extent_string(layer)

    def _tile_format_value(self) -> int:
        return 0 if self.format_combo.currentText() == "PNG" else 1

    def start(self):
        out = self.output_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "Brak folderu", "Wybierz folder zapisu.")
            return
        out_path = Path(out)
        if not out_path.exists() or not out_path.is_dir():
            QMessageBox.warning(self, "Błędny folder", f"Katalog nie istnieje: {out}")
            return

        selected_ids = self._selected_layer_ids()
        if not selected_ids:
            QMessageBox.warning(self, "Brak warstw", "Zaznacz przynajmniej jedną warstwę do eksportu.")
            return

        try:
            self.alg_id = get_algorithm_id()
        except Exception as e:
            QMessageBox.critical(self, "Brak algorytmu", str(e))
            return

        try:
            self.all_layer_nodes, all_targets = iter_target_layer_nodes()
            self.target_nodes = [n for n in all_targets if (n.layer() and n.layer().id() in selected_ids)]
        except Exception as e:
            QMessageBox.critical(self, "Brak warstw", str(e))
            return

        if not self.target_nodes:
            QMessageBox.warning(self, "Brak warstw", "Żadna z wybranych warstw nie jest dostępna w drzewie projektu.")
            return

        try:
            extent_str = self._get_extent_string()
        except Exception as e:
            QMessageBox.critical(self, "Extent", str(e))
            return

        self._cancel_requested = False
        self._failed_layers = []
        self._queue = list(self.target_nodes)
        self._failed_layers = []
        self._current_index = -1
        self._extent_str = extent_str
        self._output_folder = out_path

        self._original_visibility = {node: node.isVisible() for node in self.all_layer_nodes}

        # Performance: stop rendering map canvas during export
        if self.chk_pause_render.isChecked():
            canvas = self.iface.mapCanvas()
            self._canvas_render_flag = canvas.renderFlag()
            canvas.setRenderFlag(False)

        self.log.clear()
        self._log(f"Algorytm: {self.alg_id}")
        self._log(f"Warstw do przetworzenia: {len(self._queue)} (zaznaczone w oknie)")
        self._log(f"EXTENT: {extent_str}")
        self.progress.setValue(0)

        self.run_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        QTimer.singleShot(0, self._start_next)

    def cancel(self):
        self._cancel_requested = True
        if self._current_feedback is not None:
            self._current_feedback.cancel()
        self._log("⏹ Przerywam… (po zakończeniu bieżącego kroku)")

    def _start_next(self):
        if self._cancel_requested:
            remaining = self._queue[self._current_index:]
            for n in remaining:
                if n.layer():
                    self._failed_layers.append(n.layer().name())
            self._finish(cancelled=True)
            return

        self._current_index += 1
        total = len(self._queue)
        if self._current_index >= total:
            self._finish(cancelled=False)
            return

        node = self._queue[self._current_index]
        layer = node.layer()
        if not layer:
            self._log(f"[{self._current_index+1}/{total}] Pomijam pusty węzeł warstwy.")
            QTimer.singleShot(0, self._start_next)
            return

        layer_name = layer.name()
        self._log(f"\n[{self._current_index+1}/{total}] {layer_name} ({layer.providerType()})")

        # set visibility for rendering algorithm
        for n in self.all_layer_nodes:
            n.setItemVisibilityChecked(False)
        node.setItemVisibilityChecked(True)
        self._pump_ui(force=True)

        out_file = Path(build_output_file(self._output_folder, layer_name))
        if out_file.exists():
            try:
                out_file.unlink()
                self._log(f"  • Nadpisuję istniejący plik: {out_file.name}")
            except Exception as e:
                self._log(f"  ⚠ Nie mogę usunąć istniejącego pliku ({out_file}): {e}")

        params = {
            "ANTIALIAS": True,
            "BACKGROUND_COLOR": None,
            "DPI": 96,
            "EXTENT": self._extent_str,
            "METATILESIZE": 4,
            "QUALITY": int(self.jpeg_quality.value()),
            "TILE_FORMAT": self._tile_format_value(),
            "ZOOM_MAX": int(self.zoom_max.value()),
            "ZOOM_MIN": int(self.zoom_min.value()),
            "OUTPUT_FILE": str(out_file),
        }

        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())

        feedback = _SignalFeedback()
        self._current_feedback = feedback
        feedback.progressChanged.connect(self._on_layer_progress)
        feedback.textWritten.connect(lambda t: self._log("  • " + t))

        self._layer_progress = 0.0
        self._update_overall_progress()

        try:
            processing.run(self.alg_id, params, context=context, feedback=feedback)
            if self._cancel_requested or feedback.isCanceled():
                self._finish(cancelled=True)
                return
            self._log(f"  ✅ OK → {out_file.name}")
        except Exception as e:
            self._failed_layers.append(layer_name)
            self._log(f"  ❌ Błąd podczas eksportu warstwy '{layer_name}': {e}")
            QgsMessageLog.logMessage(
                f"qgis-project-snapshot: błąd dla warstwy '{layer_name}': {e}",
                "qgis-project-snapshot",
                Qgis.Critical,
            )

        self._current_feedback = None
        QTimer.singleShot(0, self._start_next)

    def _on_layer_progress(self, p: float):
        self._layer_progress = max(0.0, min(100.0, float(p)))
        self._update_overall_progress()
        self._pump_ui()

    def _update_overall_progress(self):
        total = max(1, len(self._queue))
        base = (max(0, self._current_index) / total) * 100.0
        incr = (self._layer_progress / total)
        overall = base + incr
        self.progress.setValue(int(max(0.0, min(100.0, overall))))

    def _finish(self, cancelled: bool):
        # restore visibility
        if self._original_visibility:
            for node, vis in self._original_visibility.items():
                node.setItemVisibilityChecked(vis)

        # restore canvas rendering
        if self._canvas_render_flag is not None:
            canvas = self.iface.mapCanvas()
            canvas.setRenderFlag(self._canvas_render_flag)
            self._canvas_render_flag = None

        if cancelled:
            self._log("\n⛔ Przerwano.")
        else:
            self._log("\n✅ Gotowe.")
        # Podsumowanie
        if self._failed_layers:
            self._log("\n⚠️ Nieprzetworzone warstwy:")
            for name in sorted(set(self._failed_layers)):
                self._log(f"  • {name}")
        else:
            self._log("\n🎉 Wszystkie warstwy przetworzone pomyślnie.")


        self.progress.setValue(100 if not cancelled else self.progress.value())

        self.run_btn.setEnabled(True)
        self.close_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self._current_feedback = None
