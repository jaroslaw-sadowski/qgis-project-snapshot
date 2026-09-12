QGIS Project Snapshot 1.4.3
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
qgis-project-snapshot-1.4.3.zip. Przy aktualizacji uruchom ponownie QGIS.
Instalacja z katalogu plugins.qgis.org będzie możliwa po zatwierdzeniu publikacji.

Użycie i automatyka
Wybierz Wtyczki → QGIS Project Snapshot → Archiwizuj projekt….
Wskaż folder, obszar, warstwy i szczegółowość, następnie Utwórz archiwum.
Mapy pobierają osobne procesy QGIS. Ich liczba rośnie automatycznie według
zasobów komputera, szybkości i odpowiedzi serwerów; błędy ograniczają obciążenie.
Po okresie poprawnej pracy automat ponownie próbuje zwiększyć liczbę zadań;
utrwalony spadek szybkości może obniżyć limit. Windows dodatkowo sprawdza,
ile pamięci może jeszcze przydzielić nowym procesom.
Nie trzeba ustawiać liczby procesów. Automat nie gwarantuje maksymalnej szybkości.
„Warstwy w kolejce” dotyczą serwera w tym samym wierszu.
Przeczytaj raport, sprawdź kopię bez sieci i przenoś cały folder archiwum.
Nie wszystkie zależności projektu są przenoszone automatycznie.
Po przerwaniu wybierz „Kontynuuj to archiwum”. Po ponownym otwarciu oryginalnego
projektu użyj „Wznów archiwum…” i wskaż cały poprzedni folder. Powstanie nowy
folder z ukończonymi warstwami i poprawnie zapisanymi lub pustymi kafelkami map.
Tylko brakujące kafelki otrzymają do trzech nowych prób. Nieukończony wektor zacznie
swoją warstwę od początku. Potrzebne jest miejsce na kopię danych i cały folder.
Po nieoczekiwanym zamknięciu QGIS wskaż folder z nazwą zawierającą .w-trakcie-.
Okno podpowiada ostatni zachowany folder. Poprzednie wyniki pozostają dostępne.
Przed planowanym zamknięciem użyj Przerwij i poczekaj na zapis; uszkodzony dysk
lub pliki mogą uniemożliwić odzyskanie postępu.
GeoTIFF-y mają piramidy do szybszego odczytu. Mapy zachowują niezależnie pobrane
zoomy i style, także poprawnie puste poziomy; braki nie są wypełniane inną skalą.
Do pracy otwieraj projekt .qgz, do sprawdzenia wyniku raport.html. Dane są w dane/,
zasoby w zasoby/. Zachowaj je razem z projektem. Manifest, log i postęp są w diagnostyka/;
nie trzeba otwierać ich ręcznie. Przenoś cały folder archiwum.
Potwierdzone puste wektory w kopii mają końcówkę _nie-bylo-obiektow-w-zasiegu.
Pola i styl pozostają. Błędy oraz niepotwierdzone puste MSSQL nie dostają końcówki;
oryginalne nazwy są niezmienione.
Instrukcja szczegółowa: INSTRUKCJA.md.

Diagnostyka
Automatyczny lokalny diagnostyka/diagnostyka.jsonl zawiera pomiary CPU, pamięci, odczytu i zapisu,
kolejek oraz odpowiedzi serwerów. Pomiary komputera powstają co około 5 sekund,
również podczas oczekiwania. Log nie jest wysyłany automatycznie.
Od 1.2.0 zwykle wystarczy on do analizy wydajności. Dołącz manifest.json, gdy
potrzebne są nazwy warstw i szczegóły braków. Do wznowienia zachowaj cały folder.
Duży log można ręcznie spakować do ZIP-a. Pomiary nie dowodzą maksymalnej wydajności.

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
qgis-project-snapshot-1.4.3.zip. Restart QGIS when upgrading.
Installation from plugins.qgis.org will be available once publication is approved.

Use and automatic downloads
Choose Plugins → QGIS Project Snapshot → Archive project….
Select a folder, area, layers and detail, then Create archive.
Separate QGIS processes download maps. Concurrency grows automatically using
computer resources, download speed and server responses; errors reduce the load.
After healthy periods, it retests higher concurrency and reduces the limit when
slowdowns persist. Windows also checks how much more memory it can allocate.
No manual process count is needed. Maximum throughput is not guaranteed.
“Queued layers” refers to the server in that row.
Read the report, check the copy offline and keep the entire archive folder.
Not all project dependencies can be transferred automatically.
After cancelling, choose “Continue this archive”. After reopening the original
project, use “Resume archive…” and select the entire previous archive folder.
A new folder retains completed layers and successfully saved or empty map tiles.
Only missing tiles receive up to three new attempts. An unfinished vector layer
starts that layer again. Keep the entire folder and allow space for a data copy.
After an unexpected QGIS exit, select the folder whose name contains .in-progress-.
The dialog suggests the last available folder. Previous results remain available.
Before a planned shutdown, use Cancel and wait for saving; damaged storage or
files can prevent progress recovery.
GeoTIFFs include overviews for faster display. Maps retain separately downloaded
zooms and styles, including correctly empty levels; missing tiles are not filled
using another scale.
Open the .qgz project to work with the archive, or report.html to review results.
Keep data/ (data) and resources/ (resources) with the project. The manifest, log and saved progress
are in diagnostics/; there is no need to open them manually. Move the whole folder.
Confirmed empty vector layers in the copy receive _no-features-in-area.
Fields and styles remain. Errors and unconfirmed empty MSSQL reads do not receive
this suffix; original names remain unchanged.
See INSTRUKCJA.md for an English quick start.

Diagnostics
The automatic local diagnostics/diagnostic.jsonl records CPU, memory, read/write operations,
queues and server responses. Computer samples are taken about every 5 seconds,
including during waits. The log is not sent automatically.
From 1.2.0, it is usually enough for performance analysis. Include manifest.json
when layer names or details of missing results are needed. Keep the entire folder
for resuming. You can manually ZIP a large log. Measurements do not prove maximum
computer or server throughput.

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
