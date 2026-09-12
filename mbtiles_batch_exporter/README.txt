QGIS Project Snapshot 1.1.0
Autor / Author: Jarosław Sadowski

POLSKI

Co robi
Tworzy osobną kopię projektu QGIS do odczytu bez sieci: wektory z atrybutami,
mapy PNG z przezroczystością, lokalne rastry i dostępne zasoby oraz raport.
Zachowuje grupy, kolejność, widoczność i style warstw. Oryginał pozostaje bez zmian.

Wymagania i instalacja
QGIS 3.40 lub nowszy z serii 3.x, Qt5/PyQt5 i GDAL >= 3.7 dostarczane z QGIS.
Bez dodatkowych pakietów. Potrzebny dostęp do źródeł, wolne miejsce na dysku
i prawo do pobierania danych. Sprawdzono QGIS 3.40 na Ubuntu.
W QGIS wybierz Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP i wskaż
qgis-project-snapshot-1.1.0.zip. Przy aktualizacji uruchom ponownie QGIS.
Instalacja z katalogu plugins.qgis.org będzie możliwa po zatwierdzeniu publikacji.

Użycie i automatyka
Wybierz Wtyczki → QGIS Project Snapshot → Archiwizuj projekt….
Wskaż folder, obszar, warstwy i szczegółowość, następnie Utwórz archiwum.
Mapy pobierają osobne procesy QGIS. Ich liczba rośnie automatycznie według
zasobów komputera, szybkości i odpowiedzi serwerów; błędy ograniczają obciążenie.
Nie trzeba ustawiać liczby procesów. Automat nie gwarantuje maksymalnej szybkości.
„Warstwy w kolejce” dotyczą serwera w tym samym wierszu.
Przeczytaj raport, sprawdź kopię bez sieci i przenoś cały folder archiwum.
Nie wszystkie zależności projektu są przenoszone automatycznie.
Po przerwaniu wybierz „Kontynuuj to archiwum”. Po ponownym otwarciu oryginalnego
projektu użyj „Wznów archiwum…” i wskaż cały poprzedni folder. Powstanie nowy
folder z zachowanymi ukończonymi warstwami i ponowieniem brakujących lub częściowych.
Przerwane warstwy są pobierane od początku. Potrzebne jest miejsce na kopię danych;
poprzedni folder pozostaje bez zmian. To nie jest odzyskiwanie po awarii programu.
Instrukcja szczegółowa: INSTRUKCJA.md.

Licencje i odpowiedzialność
Przed eksportem sprawdź i respektuj licencje warstw oraz warunki usług:
pobieranie, kopiowanie, przechowywanie offline, udostępnianie, oznaczenia autorstwa
i limity usług. Sam dostęp do mapy nie daje prawa do jej archiwizacji.
tile.openstreetmap.org nie zezwala na pobieranie map do użytku offline:
https://operations.osmfoundation.org/policies/tiles/
Wtyczka nie przyznaje praw do cudzych treści i nie sprawdza ich licencji.
Za zgodne z prawem użycie odpowiada użytkownik. W zakresie dopuszczalnym przez
prawo autor nie odpowiada za niedozwolone kopiowanie lub udostępnianie treści
przez użytkownika. Przed udostępnieniem archiwum lub raportu sprawdź dane poufne.

ENGLISH

Purpose
Creates a separate QGIS project copy for offline use: vector features with
attributes, transparent PNG maps, local rasters and available resources,
and a report. Preserves layer groups, order, visibility and styles.
The original project stays unchanged.

Requirements and installation
QGIS 3.40 or a later 3.x release, with Qt5/PyQt5 and GDAL >= 3.7 supplied by QGIS.
No additional packages. Requires source access, disk space and permission to
download the data. Tested with QGIS 3.40 on Ubuntu.
Choose Plugins → Manage and Install Plugins → Install from ZIP, then select
qgis-project-snapshot-1.1.0.zip. Restart QGIS when upgrading.
Installation from plugins.qgis.org will be available once publication is approved.

Use and automatic downloads
Choose Plugins → QGIS Project Snapshot → Archive project….
Select a folder, area, layers and detail, then Create archive.
Separate QGIS processes download maps. Concurrency grows automatically using
computer resources, download speed and server responses; errors reduce the load.
No manual process count is needed. Maximum throughput is not guaranteed.
“Queued layers” refers to the server in that row.
Read the report, check the copy offline and keep the entire archive folder.
Not all project dependencies can be transferred automatically.
After cancelling, choose “Continue this archive”. After reopening the original
project, use “Resume archive…” and select the entire previous archive folder.
A new folder retains completed layers and retries missing or partial layers.
Interrupted layers restart from the beginning. Space for a data copy is required;
the previous folder stays unchanged. This does not recover from application crashes.
See INSTRUKCJA.md for an English quick start.

Data licences and responsibility
Before exporting, check and respect layer licences and service terms for
downloading, copying, offline storage, redistribution, attribution and limits.
Access to a map does not grant permission to archive it.
tile.openstreetmap.org does not permit downloading maps for offline use:
https://operations.osmfoundation.org/policies/tiles/
The plugin does not grant rights to third-party content or check its licences.
Users are responsible for lawful use. To the extent permitted by applicable law,
the author accepts no liability for users' unauthorized copying or distribution
of content. Check archives and reports for confidential data before sharing.

LICENCJA WTYCZKI / PLUGIN LICENCE

GNU GPL version 2 (GPL-2.0-only); see LICENSE.
Licencja dotyczy wtyczki, nie pobranych danych. Warunki i brak gwarancji: LICENSE.
The licence covers the plugin, not downloaded data. Terms and no warranty: LICENSE.
Projekt powstał metodą vibe coding z pomocą AI.
Developed through vibe coding with AI assistance.

POMOC I ZGŁOSZENIA / HELP AND FEEDBACK

https://github.com/jaroslaw-sadowski/qgis-project-snapshot
https://github.com/jaroslaw-sadowski/qgis-project-snapshot/issues
Podaj wersje QGIS i wtyczki oraz kroki odtworzenia; nie publikuj danych poufnych.
Include QGIS and plugin versions and reproduction steps; do not share confidential data.
