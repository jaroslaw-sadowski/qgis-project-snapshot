# -*- coding: utf-8 -*-
import json
import math
import time
from html import escape
from pathlib import Path

from qgis.core import (
    QgsCoordinateTransform,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsProject,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from .archive import create_archive, polygon_area
from .i18n import tr
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
        self.setWindowTitle(tr("QGIS Project Snapshot — Archiwizuj projekt"))
        self.setWindowIcon(QIcon(str(Path(__file__).with_name("icon.svg"))))
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(860, 790)
        layout = QVBoxLayout(self)
        notice = QLabel(
            tr(
                (
                    "Zapisz projekt do pracy bez sieci. Najedź na opcję, aby "
                    "zobaczyć objaśnienie."
                )
            )
        )
        notice.setWordWrap(True)
        heading = QHBoxLayout()
        emblem = QLabel()
        emblem.setPixmap(self.windowIcon().pixmap(40, 40))
        heading.addWidget(emblem)
        heading.addWidget(notice, 1)
        layout.addLayout(heading)

        self.options = QWidget()
        options_layout = QVBoxLayout(self.options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.output_edit = QLineEdit()
        output = QHBoxLayout()
        output.addWidget(self.output_edit)
        browse = QPushButton(tr("Wybierz…"))
        browse.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        browse.setToolTip(
            tr(
                (
                    "Wybierz istniejący folder. W nim powstanie nowy katalog "
                    "archiwum z datą."
                )
            )
        )
        browse.clicked.connect(self._browse)
        output.addWidget(browse)
        form.addRow(tr("Folder archiwum:"), output)
        self.area_combo = QComboBox()
        self.area_combo.addItems(
            [tr("Aktualny widok mapy"), tr("Obszar z warstwy poligonowej")]
        )
        self.area_combo.currentIndexChanged.connect(self._update_area)
        form.addRow(tr("Obszar:"), self.area_combo)
        self.polygon_combo = QComboBox()
        for layer in self.project.mapLayers().values():
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.isValid()
                and layer.geometryType() == QgsWkbTypes.PolygonGeometry
            ):
                self.polygon_combo.addItem(layer.name(), layer.id())
        form.addRow(tr("Warstwa obszaru:"), self.polygon_combo)
        self.zoom_min = QComboBox()
        self.zoom_max = QComboBox()
        for combo, default in ((self.zoom_min, 13), (self.zoom_max, 17)):
            for zoom in range(25):
                combo.addItem(f"Zoom {zoom}", zoom)
            combo.setCurrentIndex(default)
            combo.currentIndexChanged.connect(self._ensure_zoom_order)
        form.addRow(tr("Najmniejsze zbliżenie:"), self.zoom_min)
        form.addRow(tr("Największe zbliżenie:"), self.zoom_max)
        self.resource_hint = QLabel(
            tr("Równoległość dobierana automatycznie podczas pobierania.")
        )
        self.resource_hint.setWordWrap(True)
        self.servers = QTreeWidget()
        self.servers.setHeaderLabels(
            [
                tr("Serwer"),
                tr("Aktywne / limit"),
                tr("Warstwy w kolejce"),
                tr("Kafelki/s"),
                tr("Stan"),
                tr("Przerwa"),
            ]
        )
        self.servers.headerItem().setIcon(
            0, self.style().standardIcon(QStyle.SP_ComputerIcon)
        )
        self.servers.headerItem().setToolTip(
            2,
            tr(
                "Liczba warstw czekających na rozpoczęcie pobierania z serwera "
                "w tym wierszu. Nie obejmuje warstw już pobieranych."
            ),
        )
        self.servers.setMaximumHeight(145)
        self.servers.setRootIsDecorated(False)
        for column, width in enumerate((215, 130, 160, 85, 210, 65)):
            self.servers.setColumnWidth(column, width)
        self.servers.setToolTip(
            tr(
                (
                    "Automat zaczyna od 1 zadania na serwer. Po udanych "
                    "pobraniach stopniowo sprawdza wyższe limity, dopóki rośnie "
                    "szybkość i komputer ma wolne zasoby. Pierwszeństwo mają "
                    "serwery z mniejszą liczbą aktywnych procesów. Błędy lub "
                    "brak przyspieszenia zmniejszają obciążenie. Łączny limit "
                    "wynosi maks. 32 procesy i nie więcej niż dwukrotność "
                    "liczby dostępnych CPU. Dalszy wzrost ogranicza wolny RAM. "
                    "Limity dotyczą map, nie dokładnej liczby żądań HTTP."
                )
            )
        )
        self._server_items = {}
        self.zoom_hint = QLabel()
        self.zoom_hint.setWordWrap(True)
        form.addRow(self.zoom_hint)
        self.polygon_combo.currentIndexChanged.connect(self._update_zoom_labels)
        options_layout.addLayout(form)
        selection = QHBoxLayout()
        for label, checked in [
            (tr("Zaznacz wszystko"), True),
            (tr("Odznacz wszystko"), False),
        ]:
            button = QPushButton(label)
            button.setToolTip(
                tr(
                    (
                        "Zmienia wybór warstw do archiwum. Nie zmienia "
                        "widoczności warstw w oryginalnym projekcie."
                    )
                )
            )
            button.clicked.connect(lambda _, value=checked: self._select_all(value))
            selection.addWidget(button)
        selection.addStretch()
        options_layout.addLayout(selection)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Warstwa"), tr("Zapis"), tr("Stan")])
        self._populate_tree(self.project.layerTreeRoot(), self.tree.invisibleRootItem())
        self.tree.expandToDepth(0)
        self.tree.setColumnWidth(0, 290)
        self.tree.setColumnWidth(1, 160)
        layout.addWidget(self.options)
        layout.addWidget(self.tree, 1)
        resources = QHBoxLayout()
        cpu_icon = QLabel()
        cpu_icon.setPixmap(
            QIcon(str(Path(__file__).with_name("cpu.svg"))).pixmap(22, 22)
        )
        cpu_icon.setToolTip(
            tr(
                (
                    "CPU: mapy są przetwarzane w osobnych procesach, które "
                    "mogą korzystać z wielu rdzeni. Licznik pokazuje "
                    "procesy, nie procent użycia procesora."
                )
            )
        )
        resources.addWidget(cpu_icon)
        resources.addWidget(self.resource_hint, 1)
        ram_icon = QLabel()
        ram_icon.setPixmap(
            QIcon(str(Path(__file__).with_name("ram.svg"))).pixmap(22, 22)
        )
        self.ram_hint = QLabel(tr("Rezerwa RAM: 768 MiB"))
        self.ram_hint.setWordWrap(True)
        self.ram_hint.setToolTip(
            tr(
                (
                    "Automat pozostawia 768 MiB wolnej pamięci oraz zapas "
                    "na rozruch i wzrost działających procesów. Po pierwszych "
                    "pobraniach dobiera koszt kolejnego procesu do pomiarów "
                    "zużycia RAM. Sprawdza pamięć co 5 sekund; przy niedoborze "
                    "wstrzymuje uruchamianie nowych procesów."
                )
            )
        )
        ram_icon.setToolTip(self.ram_hint.toolTip())
        resources.addWidget(ram_icon)
        resources.addWidget(self.ram_hint)
        layout.addLayout(resources)
        layout.addWidget(self.servers)
        self.status = QLabel(tr("Gotowe do wyboru obszaru i folderu."))
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.server_warning = QLabel()
        self.server_warning.setTextFormat(Qt.PlainText)
        self.server_warning.setWordWrap(True)
        self.server_warning.setStyleSheet(
            (
                "QLabel { color: #b00020; background-color: #fff0f0; "
                "padding: 6px; font-weight: bold; }"
            )
        )
        self.server_warning.hide()
        self._server_warnings = set()
        layout.addWidget(self.server_warning)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat(tr("Jeszcze nie uruchomiono"))
        layout.addWidget(self.progress)
        self.elapsed = QLabel(tr("Czas: 00:00"))
        layout.addWidget(self.elapsed)
        self.workers_status = QLabel("")
        self.workers_status.setTextFormat(Qt.PlainText)
        self.workers_status.setWordWrap(True)
        self.workers_status.hide()
        layout.addWidget(self.workers_status)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setMinimumHeight(130)
        self.log.setMaximumHeight(180)
        self.log.setPlaceholderText(
            tr("Tutaj pojawią się szczegóły przebiegu archiwizacji.")
        )
        layout.addWidget(self.log)
        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setMinimumHeight(130)
        self.results.setMaximumHeight(210)
        self.results.hide()
        layout.addWidget(self.results)
        self.retry_button = QPushButton(
            tr("Ponów tylko niezapisane i niepełne warstwy")
        )
        self.retry_button.setToolTip(
            tr(
                (
                    "Te warstwy zaznaczono automatycznie. Powstanie osobne "
                    "archiwum tylko z ponowionych warstw. Zachowaj również "
                    "wcześniejszy folder; wyniki nie są automatycznie "
                    "łączone."
                )
            )
        )
        self.retry_button.hide()
        self.retry_button.clicked.connect(self.start)
        layout.addWidget(self.retry_button)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_elapsed)
        buttons = QHBoxLayout()
        self.report_button = QPushButton(tr("Otwórz raport"))
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self._open_report)
        buttons.addWidget(self.report_button)
        self.copy_button = QPushButton(tr("Kopiuj dziennik"))
        self.copy_button.clicked.connect(
            lambda: (
                QCoreApplication.instance().clipboard().setText(self.log.toPlainText())
            )
        )
        buttons.addWidget(self.copy_button)
        buttons.addStretch()
        self.start_button = QPushButton(tr("Utwórz archiwum"))
        self.start_button.clicked.connect(self.start)
        buttons.addWidget(self.start_button)
        self.cancel_button = QPushButton(tr("Przerwij"))
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        buttons.addWidget(self.cancel_button)
        self.close_button = QPushButton(tr("Zamknij"))
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        for button, standard_icon in (
            (self.report_button, QStyle.SP_FileIcon),
            (self.copy_button, QStyle.SP_FileDialogDetailedView),
            (self.cancel_button, QStyle.SP_MediaStop),
            (self.retry_button, QStyle.SP_BrowserReload),
        ):
            button.setIcon(self.style().standardIcon(standard_icon))
        self.start_button.setIcon(self.windowIcon())
        layout.addLayout(buttons)
        tips = {
            notice: tr(
                (
                    "Powstaje osobna kopia projektu, dane lokalne i raport. "
                    "Oryginał nie jest zastępowany. Po eksporcie sprawdź "
                    "raport i otwórz kopię bez internetu oraz sieci "
                    "firmowej."
                )
            ),
            self.output_edit: tr(
                (
                    "Wybierz folder z wolnym miejscem na archiwum i pliki "
                    "tymczasowe. Powstanie osobny katalog z datą. Przenoś "
                    "później cały ten katalog, nie sam plik projektu."
                )
            ),
            self.area_combo: tr(
                (
                    "Widok mapy zapisuje obszar aktualnie widoczny w QGIS. "
                    "Poligony pozwalają wybrać kształt pasa inwestycji. Całe "
                    "obiekty wektorowe przecinające obszar zostaną "
                    "zachowane."
                )
            ),
            self.polygon_combo: tr(
                (
                    "Wskaż warstwę z obszarem opracowania. Jeśli zaznaczono "
                    "w niej obiekty, użyjemy tylko zaznaczonych; w "
                    "przeciwnym razie wszystkich. Mapy będą przycięte do ich "
                    "kształtu."
                )
            ),
            self.zoom_min: tr(
                (
                    "Najmniejsze zbliżenie zapisanych map. Niski numer "
                    "obejmuje większy teren z mniejszą szczegółowością. "
                    "Zapisujemy każdy poziom między minimum i maksimum; "
                    "wektory zachowują pełne dane."
                )
            ),
            self.zoom_max: tr(
                (
                    "Największe zbliżenie zapisanych map. Wyższy numer "
                    "pokazuje więcej szczegółów, ale może mocno zwiększyć "
                    "czas i rozmiar archiwum. Na pierwszą próbę pozostaw 17."
                )
            ),
            self.zoom_hint: tr(
                (
                    "Model dla prostokąta obszaru, jednej mapy i wszystkich "
                    "wybranych zoomów: 0,2–2 s oraz 10–250 KiB "
                    "skompresowanego PNG na kafelek 256 × 256. To założenia, "
                    "nie pomiar łącza ani serwera; wynik może wyjść poza "
                    "podany przedział. Długi pas i puste kafelki zwykle "
                    "zmniejszają rozmiar. Błędy i ponowienia wydłużają czas. "
                    "Szacunek nie obejmuje wektorów, oryginalnych rastrów, "
                    "zasobów projektu, scalania i kontroli plików. Na pliki "
                    "tymczasowe przewidź dodatkowe miejsce. Równoległość "
                    "dotyczy wielu map, nie dzieli czasu jednej mapy. Skale "
                    "obliczono dla środka obszaru przy 96 DPI."
                )
            ),
            self.tree: tr(
                (
                    "Zaznacz warstwy do archiwum. Wyłączone na mapie warstwy "
                    "też można zapisać. Kolumna Stan pokazuje kolejkę, "
                    "pobieranie, zapis lub problem. Najedź na stan, aby "
                    "przeczytać szczegóły."
                )
            ),
            self.progress: tr(
                (
                    "Licznik zakończonych warstw, nie prognoza czasu. "
                    "Warstwy mają różne rozmiary. Po zapisie danych trzeba "
                    "jeszcze sprawdzić pliki i przygotować raport."
                )
            ),
            self.status: tr(
                (
                    "Aktualna czynność głównego QGIS. Postęp równoległych "
                    "map znajdziesz w kolumnie Stan i dzienniku."
                )
            ),
            self.elapsed: tr(
                (
                    "Czas od uruchomienia eksportu. Brak nowego komunikatu "
                    "nie musi oznaczać zatrzymania: niektóre źródła długo "
                    "odpowiadają na zapytanie."
                )
            ),
            self.workers_status: tr(
                (
                    "Podsumowanie procesów mapowych: zadania pracujące, "
                    "oczekujące i gotowe do scalenia. Szczegóły każdej mapy "
                    "są w kolumnie Stan."
                )
            ),
            self.log: tr(
                (
                    "Ostatnie 2000 komunikatów z czasem od startu: etapy, "
                    "warstwy, zoomy, fragmenty, ponowienia i wyniki. Nie "
                    "zawiera pełnych adresów źródeł ani poświadczeń. Pełny "
                    "wynik warstw zapisuje raport."
                )
            ),
            self.copy_button: tr(
                (
                    "Kopiuje widoczny dziennik do schowka, aby można go było "
                    "dołączyć do opisu problemu. Dziennik może zawierać "
                    "nazwy warstw z projektu."
                )
            ),
            self.report_button: tr(
                (
                    "Otwiera raport gotowego archiwum: zapisane i brakujące "
                    "warstwy oraz elementy do sprawdzenia."
                )
            ),
            self.start_button: tr(
                (
                    "Rozpoczyna zapis zaznaczonych warstw i kopii projektu. "
                    "PNG zachowuje przezroczystość i kompresję bezstratną. "
                    "Po zakończeniu sprawdź wynik bez sieci."
                )
            ),
            self.cancel_button: tr(
                (
                    "Zatrzymuje kolejne zadania i przerywa pobieranie. "
                    "Ukończone, scalone warstwy pozostają w archiwum. "
                    "Niektóre operacje mogą potrzebować chwili na "
                    "zakończenie."
                )
            ),
            self.close_button: tr(
                (
                    "Zamyka okno. Podczas eksportu działa jak Przerwij; okno "
                    "pozostanie otwarte do zakończenia zapisu."
                )
            ),
        }
        for widget, text in tips.items():
            widget.setToolTip(f"<p>{escape(text)}</p>")
        for row in range(form.rowCount()):
            label = form.itemAt(row, QFormLayout.LabelRole)
            field = form.itemAt(row, QFormLayout.FieldRole)
            if label and label.widget() and field:
                widget = field.widget() or self.output_edit
                label.widget().setToolTip(widget.toolTip())
        self._update_area()

    def _server_activity(self, rows):
        states = {
            "finished": tr("Zakończono"),
            "failed": tr("Zakończono z błędami"),
            "starting": tr("Rozpoczynanie"),
            "running": tr("Pobieranie"),
            "capacity": tr("Limit procesów komputera"),
            "increasing": tr("Zwiększanie"),
            "stable": tr("Ustalony limit"),
            "cooldown": tr("Przerwa serwera"),
            "memory": tr("Ograniczenie pamięci"),
            "repairing": tr("Uzupełnianie braków"),
            "deferred": tr("Odłożono do późniejszej próby"),
        }
        for row in rows:
            item = self._server_items.get(row["host"])
            if item is None:
                item = QTreeWidgetItem(self.servers)
                self._server_items[row["host"]] = item
            values = [
                row["host"],
                f"{row['active']} / {row['limit']}",
                str(row["queued"]),
                f"{row['rate']:.2f}",
                states[row["state"]],
                tr("{0} s").format(row["pause"]),
            ]
            for column, value in enumerate(values):
                item.setText(column, value)
                item.setToolTip(column, value)
            item.setToolTip(
                2,
                tr("Warstwy czekające na pobranie z serwera {0}: {1}.").format(
                    row["host"], row["queued"]
                ),
            )
        self.resource_hint.setText(
            tr(
                "Procesy map: {0}/{1}; aktywne zadania: {2}. Dobór automatyczny."
            ).format(
                sum(r["processes"] for r in rows),
                rows[0]["budget"] if rows else 0,
                sum(r["active"] for r in rows),
            )
        )
        if rows and "memory_available" in rows[0]:
            memory = rows[0]["memory_available"]
            self.ram_hint.setText(
                tr("Dostępny RAM: {0:.1f} GiB; rezerwa: 768 MiB").format(
                    memory / 1024**3
                )
                if memory is not None
                else tr("Dostępny RAM: nieznany; maks. 2 procesy")
            )
            explanation = tr(
                "Dostępne CPU: {0}. Budżet procesów: {1}. "
                "Planowany RAM kolejnego procesu: {2:.0f} MiB ({3}). "
                "Po pobraniach używamy najwyższego zmierzonego zużycia z zapasem "
                "50%, co najmniej 384 MiB. Pozostawiamy 768 MiB wolnej pamięci "
                "oraz zapas na rozruch i wzrost działających procesów. Odczyt "
                "co 5 sekund. Niedobór pamięci wstrzymuje nowe procesy."
            ).format(
                rows[0].get("cpu", "?"),
                rows[0]["budget"],
                rows[0].get("worker_memory", 1024**3) / 1024**2,
                tr("pomiar z zapasem")
                if rows[0].get("worker_memory_measured")
                else tr("szacunek początkowy"),
            )
            self.resource_hint.setToolTip(explanation)
            self.ram_hint.setToolTip(explanation)

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
                item.setText(
                    1,
                    tr("Dane wektorowe")
                    if isinstance(layer, QgsVectorLayer)
                    else tr("Mapa lub raster"),
                )
                item.setText(2, tr("Gotowa do wyboru"))
                item.setToolTip(
                    1,
                    tr(
                        (
                            "Wektor zachowuje obiekty i atrybuty. Obraz mapy "
                            "zachowuje wygląd. Jeśli nie uda się zapisać danych, "
                            "raport wskaże próbę zastąpienia ich obrazem."
                        )
                    ),
                )
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
                raise ValueError(tr("Podgląd skali wymaga widoku mapy."))
            canvas = self.iface.mapCanvas()
            return QgsGeometry.fromRect(
                canvas.extent()
            ), canvas.mapSettings().destinationCrs()
        layer = self.project.mapLayer(self.polygon_combo.currentData())
        if layer is None or not layer.isValid():
            raise ValueError(tr("Wybierz dostępną warstwę poligonową."))
        if use_geometry:
            area = polygon_area(layer)
        else:
            bounds = (
                layer.boundingBoxOfSelected()
                if layer.selectedFeatureCount()
                else layer.extent()
            )
            area = QgsGeometry.fromRect(bounds)
        return area, layer.crs()

    def _ensure_zoom_order(self):
        if self.zoom_min.currentData() > self.zoom_max.currentData():
            if self.sender() is self.zoom_min:
                self.zoom_max.setCurrentIndex(self.zoom_min.currentIndex())
            else:
                self.zoom_min.setCurrentIndex(self.zoom_max.currentIndex())
        if hasattr(self, "zoom_hint"):
            self._update_zoom_labels()

    def _update_zoom_labels(self):
        try:
            area, crs = self._area(use_geometry=False)
            levels = zoom_levels(self.project, area, crs, 0, 24)
            unit = QgsUnitTypes.toAbbreviatedString(self.project.crs().mapUnits())
            for level in levels:
                label = tr("Zoom {0} ≈ 1:{1:,.0f} ({2:.3g} {3}/piksel)").format(
                    level["zoom"], level["scale"], level["resolution"], unit
                )
                for combo in (self.zoom_min, self.zoom_max):
                    combo.setItemText(level["zoom"], label)
            if crs != self.project.crs():
                area.transform(
                    QgsCoordinateTransform(crs, self.project.crs(), self.project)
                )
            box = area.boundingBox()
            count = sum(
                math.ceil(box.width() / (TILE_SIZE * level["resolution"]))
                * math.ceil(box.height() / (TILE_SIZE * level["resolution"]))
                for level in levels[
                    self.zoom_min.currentData() : self.zoom_max.currentData() + 1
                ]
            )
            # Planning scenarios, not measured throughput or an export ETA.
            # Each process renders one map; do not divide its time by workers.
            seconds = (count * 0.2, count * 2.0)
            if seconds[1] < 120:
                duration = tr("{0}–{1} s").format(
                    math.ceil(seconds[0]), math.ceil(seconds[1])
                )
            elif seconds[1] < 7200:
                duration = tr("{0}–{1} min").format(
                    math.ceil(seconds[0] / 60), math.ceil(seconds[1] / 60)
                )
            else:
                duration = tr("{0:.1f}–{1:.1f} godz.").format(
                    seconds[0] / 3600, seconds[1] / 3600
                )
            mib = (count * 10 / 1024, count * 250 / 1024)
            size = (
                tr("{0:.1f}–{1:.1f} MiB").format(*mib)
                if mib[1] < 1024
                else tr("{0:.1f}–{1:.1f} GiB").format(mib[0] / 1024, mib[1] / 1024)
            )
            self.zoom_hint.setText(
                tr("Szacunkowo do {0:,} kafelków na mapę.").format(count)
                + "\n"
                + tr(
                    "Model na jedną mapę: czas ≈ {0}; rozmiar PNG na dysku ≈ {1}."
                ).format(duration, size)
            )
        except Exception:
            self.zoom_hint.setText(
                tr("Wybierz poprawny obszar, aby zobaczyć skalę dla każdego zoomu.")
            )

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, tr("Folder na archiwum projektu")
        )
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
            QMessageBox.warning(
                self, tr("Folder archiwum"), tr("Wybierz istniejący folder zapisu.")
            )
            return
        selected_ids = self._selected_ids()
        if not selected_ids:
            QMessageBox.warning(
                self, tr("Warstwy"), tr("Zaznacz przynajmniej jedną warstwę.")
            )
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
        self.resource_hint.setText(
            tr("Równoległość dobierana automatycznie podczas pobierania.")
        )
        self.resource_hint.setToolTip("")
        self.ram_hint.setText(tr("Rezerwa RAM: 768 MiB"))
        self.servers.clear()
        self._server_items.clear()
        self._server_warnings.clear()
        self.server_warning.clear()
        self.server_warning.hide()
        self.results.hide()
        self.retry_button.hide()
        self.log.show()
        self.workers_status.clear()
        for layer_id, item in self._items.items():
            item.setText(
                2, tr("W kolejce") if layer_id in selected_ids else tr("Pominięto")
            )
            item.setToolTip(
                2,
                tr("Czeka na rozpoczęcie eksportu.")
                if layer_id in selected_ids
                else tr("Warstwa nie jest zaznaczona do eksportu."),
            )
        # Keep navigation and tooltips available while freezing export selection.
        selection_flags = []
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            selection_flags.append((item, item.flags()))
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            iterator += 1
        self.options.setEnabled(False)
        self.start_button.setEnabled(False)
        self.report_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, len(selected_ids) + 1)
        self.progress.setValue(0)
        self.progress.setFormat(
            tr("Zakończone warstwy: 0/{0}").format(len(selected_ids))
        )
        self.timer.start()
        try:
            self._update_progress(tr("Wyznaczanie obszaru archiwizacji…"))
            area, crs = self._area()
            self._result = create_archive(
                self.project,
                selected_ids,
                area,
                crs,
                folder,
                cancelled=lambda: self._cancelled,
                progress=self._update_progress,
                zoom_min=self.zoom_min.currentData(),
                zoom_max=self.zoom_max.currentData(),
                adaptive=True,
                server_activity=self._server_activity,
                layer_status=self._layer_status,
                worker_activity=self._worker_activity,
            )
            self._finished_at = time.monotonic()
            self.timer.stop()
            manifest = json.loads(
                (self._result / "manifest.json").read_text(encoding="utf-8")
            )
            saved = sum(record["status"] == "saved" for record in manifest["layers"])
            missing = sum(
                record["status"] in ("failed", "cancelled")
                for record in manifest["layers"]
            )
            review = sum(
                record["status"] in ("empty", "partial")
                for record in manifest["layers"]
            )
            self.status.setText(
                tr(
                    (
                        "Archiwum częściowe: zapisano {0} warstw; do "
                        "sprawdzenia: {1}; niezapisanych: {2}.\n{3}"
                    )
                ).format(saved, review, missing, self._result)
            )
            self._append_log(self.status.text())
            self.progress.setValue(self.progress.maximum())
            self.progress.setFormat(
                tr("Przerwano — sprawdź raport")
                if manifest["cancelled"]
                else tr("Zakończono — sprawdź raport")
            )
            self.report_button.setEnabled(True)
            self._show_results(manifest)
        except (ValueError, OSError, RuntimeError) as error:
            self._finished_at = time.monotonic()
            self.timer.stop()
            self.status.setText(
                tr("Nie utworzono archiwum. Oryginalny projekt nie został zastąpiony.")
            )
            self._append_log(self.status.text())
            self._append_log(tr("Błąd: {0}").format(error))
            self.progress.setFormat(tr("Błąd — nie utworzono archiwum"))
            QMessageBox.warning(self, tr("Archiwizacja"), str(error))
        except Exception:
            self._finished_at = time.monotonic()
            self.timer.stop()
            self.status.setText(
                tr("Nie utworzono archiwum z powodu nieoczekiwanego błędu.")
            )
            self._append_log(self.status.text())
            self.progress.setFormat(tr("Błąd — nie utworzono archiwum"))
            QMessageBox.warning(self, tr("Archiwizacja"), self.status.text())
        finally:
            self._running = False
            self.timer.stop()
            self._update_elapsed()
            for item, flags in selection_flags:
                item.setFlags(flags)
            self.options.setEnabled(True)
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)

    def _show_results(self, manifest):
        retry = {
            record["id"]
            for record in manifest["layers"]
            if record["status"] in ("failed", "cancelled", "empty", "partial")
        }
        lines = [self.status.text(), ""]
        for record in manifest["layers"]:
            if record["id"] in retry:
                lines.append(
                    f"{record['name']} — {record.get('reason') or record['status']}"
                )
        if not retry:
            lines.append(
                tr(
                    (
                        "Nie ma warstw wymagających ponownej próby. Sprawdź "
                        "pozostałe uwagi w raporcie."
                    )
                )
            )
        else:
            lines.append(
                tr(
                    (
                        "\nZaznaczono tylko warstwy do ponowienia. Ponowna próba "
                        "utworzy osobny folder; zachowaj oba archiwa."
                    )
                )
            )
        lines.append(
            tr(
                (
                    "Pełne wyniki i diagnostyka: raport.html oraz "
                    "manifest.json w folderze archiwum."
                )
            )
        )
        for layer_id, item in self._items.items():
            item.setCheckState(0, Qt.Checked if layer_id in retry else Qt.Unchecked)
        self.results.setPlainText("\n".join(lines))
        self.log.hide()
        self.results.show()
        self.retry_button.setVisible(bool(retry))

    def _show_server_warning(self, message):
        if (
            message.startswith(("[HTTP 429]", "[HTTP 503]"))
            or message == tr("Koordynator pobierania zakończył pracę z błędem.")
        ) and message not in self._server_warnings:
            self._server_warnings.add(message)
            self.server_warning.setText(message)
            self.server_warning.show()
            self._append_log(message)

    def _update_progress(self, message):
        self._show_server_warning(message)
        if message != self._last_message:
            self._last_message = message
            self._append_log(message)
        self.status.setText((tr("Przerywanie — ") if self._cancelled else "") + message)
        QCoreApplication.processEvents()

    def _append_log(self, message):
        self._last_change = time.monotonic()
        seconds = (
            int(self._last_change - self._started_at)
            if self._started_at is not None
            else 0
        )
        self.log.appendPlainText(f"[{seconds // 60:02d}:{seconds % 60:02d}] {message}")

    def _update_elapsed(self):
        if self._started_at is None:
            return
        seconds = int((self._finished_at or time.monotonic()) - self._started_at)
        quiet = int(time.monotonic() - self._last_change)
        text = tr("Czas: {0:02d}:{1:02d}").format(seconds // 60, seconds % 60)
        if self._running and self._finished_at is None and quiet >= 10:
            text += tr(
                " — ostatni komunikat {0} s temu; trwa powyższa czynność."
            ).format(quiet)
        self.elapsed.setText(text)

    def _layer_status(self, record, completed, total):
        if record.get("worker_error", {}).get("stage") == "coordinator":
            self._show_server_warning(record["reason"])
        for warning in record.get("raster", {}).get("server_warnings", []):
            self._show_server_warning(warning)
        item = self._items.get(record["id"])
        labels = {
            "pending": tr("Przetwarzanie"),
            "saved": tr("Zapisano"),
            "empty": tr("Pusty obraz — sprawdź"),
            "partial": tr("Brak części obrazu"),
            "failed": tr("Błąd"),
            "cancelled": tr("Przerwano"),
        }
        if item is not None:
            item.setText(2, labels.get(record["status"], record["status"]))
            reason = record.get("reason") or tr(
                "Przygotowanie warstwy do archiwizacji."
            )
            item.setToolTip(2, f"<p>{escape(reason)}</p>")
        if record["status"] != "pending":
            self._finished_ids.add(record["id"])
        self.progress.setValue(completed)
        self.progress.setFormat(
            tr("Zakończone warstwy: {0}/{1}").format(completed, total)
            + (tr(" — kontrola plików") if completed == total else "")
        )

    def _worker_activity(self, rows):
        active = sum(row["phase"] == "active" for row in rows)
        queued = sum(row["phase"] == "queued" for row in rows)
        ready = sum(row["phase"] == "ready" for row in rows)
        self.workers_status.setVisible(bool(rows))
        self.workers_status.setText(
            tr("Mapy: pracuje {0} • w kolejce {1} • czeka na scalenie {2}").format(
                active, queued, ready
            )
            if rows
            else ""
        )
        for row in rows:
            for warning in row.get("server_warnings", []):
                self._show_server_warning(warning)
            if row["id"] in self._finished_ids:
                continue
            item = self._items.get(row["id"])
            if item is None:
                continue
            message = (
                row["message"]
                .removeprefix(item.text(0) + ": ")
                .removeprefix(item.text(0) + " — ")
            )
            item.setText(2, message)
            item.setToolTip(2, f"<p>{escape(message)}</p>")
            state = (row["phase"], message)
            if self._worker_messages.get(row["id"]) != state:
                self._worker_messages[row["id"]] = state
                self._append_log(f"{item.text(0)}: {message}")

    def cancel(self):
        self._cancelled = True
        self.cancel_button.setEnabled(False)
        self.status.setText(
            tr(
                (
                    "Przerywanie… Ukończone warstwy zostaną zachowane w "
                    "archiwum częściowym."
                )
            )
        )
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
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._result / "raport.html"))
            )
