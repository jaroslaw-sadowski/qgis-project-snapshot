# QGIS Project Snapshot — instrukcja / user guide 1.0.0

## Instalacja i uruchomienie

Wymagane: QGIS 3.40 lub nowszy z serii 3.x, z Qt5/PyQt5 i GDAL co najmniej 3.7
z instalacji QGIS. Nie są potrzebne dodatkowe pakiety. Zapewnij dostęp do źródeł
projektu oraz miejsce na archiwum i pliki tymczasowe.

1. W QGIS wybierz **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Wskaż `qgis-project-snapshot-1.0.0.zip`. Po aktualizacji uruchom ponownie QGIS.
3. Otwórz projekt, następnie **Wtyczki → QGIS Project Snapshot → Archiwizuj projekt…**
   lub ikonę mapy w pudełku na pasku wtyczek.

Instalacja z katalogu plugins.qgis.org będzie dostępna po zatwierdzeniu publikacji.
Interfejs używa języka QGIS, a bez własnego ustawienia — języka systemu.
Dla polskiego wybiera polski, dla pozostałych języków angielski.

## Wybór danych i obszaru

Przed eksportem upewnij się, że licencje wybranych warstw i warunki usług
pozwalają na pobranie oraz przechowywanie danych offline.

| Opcja | Co wybrać |
| --- | --- |
| Folder archiwum | Istniejący folder z wolnym miejscem. W nim powstanie osobny katalog z datą. |
| Obszar | Aktualny widok mapy albo kształt z warstwy poligonowej. |
| Warstwa obszaru | Przy poligonach używane są zaznaczone obiekty; jeśli nic nie zaznaczono, wszystkie. |
| Najmniejsze / największe zbliżenie | Zakres szczegółowości zapisywanych map. Większe zbliżenie zwiększa czas pobierania i rozmiar archiwum. |
| Lista warstw | Zaznacz dane potrzebne w kopii. Wybór nie zmienia widoczności warstw w oryginale. |

Zacznij od małego obszaru i kilku warstw. Zoomy 13–17 są ustawieniem początkowym;
dobierz je do potrzeb, korzystając z opisanej skali i rozdzielczości.
Szacunek czasu i rozmiaru dotyczy jednej mapy, nie całego projektu.
Najechanie na opcję wyświetla dodatkowe objaśnienia.

Wybierz **Utwórz archiwum**. Oryginalny projekt pozostaje bez zmian. Mapy PNG
są zapisywane bezstratnie z przezroczystością i przycinane do wybranego obszaru.
Wektory zachowują całe obiekty przecinające obszar oraz ich atrybuty.
Jeśli danych nie uda się zapisać i zostaną zastąpione obrazem, raport to wskaże.
Data archiwum oznacza czas pobierania, nie jednoczesny stan wszystkich źródeł.

## Automatyczne pobieranie równoległe

Mapy pobierają osobne procesy QGIS. Nie trzeba ręcznie ustawiać ich liczby.
Automat zaczyna od jednego zadania na serwer i zwiększa obciążenie, gdy są kolejne
mapy, zasoby komputera na to pozwalają i rośnie szybkość pobierania.
Uwzględnia wolny RAM, zmierzone zużycie pamięci procesów oraz odpowiedzi serwerów.
Błędy lub brak przyspieszenia ograniczają dalszy wzrost. Jest to automatyczny dobór,
a nie gwarancja maksymalnego wykorzystania komputera czy łącza.

Tabela pokazuje osobno dla każdego serwera:

- **Aktywne / limit** — liczbę działających zadań i aktualny limit.
- **Warstwy w kolejce** — warstwy czekające na rozpoczęcie pobierania z serwera
  w tym wierszu; bez warstw już pobieranych.
- **Kafelki/s**, **Stan**, **Przerwa** — bieżącą szybkość, etap pracy i czas oczekiwania.

Nad tabelą widać łączne użycie procesów i dostępny RAM. Podpowiedź RAM wyjaśnia
przyjęty zapas pamięci. **Limit procesów komputera** oznacza, że lokalne zasoby
ograniczają dalszy wzrost. Limity dotyczą zadań mapowych, nie dokładnej liczby
żądań HTTP. Jedna mapa jest obsługiwana przez jeden proces; wektory i rastry
źródłowe nie korzystają z tej samej kolejki procesów mapowych.

## Połączenie, przerwy i anulowanie

Wtyczka korzysta z ustawień sieciowych aktywnego QGIS, w tym proxy, wyjątków
i dostępnych zapisanych poświadczeń. Nie wpisujesz proxy we wtyczce.
Nietypowe uwierzytelnianie lub certyfikaty mogą wymagać sprawdzenia na danym stanowisku.

Przeciążenie serwera lub powtarzające się przekroczenia czasu mogą uruchomić
przerwę. Wtyczka respektuje termin ponowienia podany przez serwer; inne serwery
mogą pracować dalej. Brakujące kafelki uzupełnia w tym samym archiwum, z ograniczoną
liczbą prób. Poprawnych kafelków nie pobiera ponownie. Odmowa uwierzytelnienia proxy
(HTTP 407) kończy pobieranie danej mapy i jest opisana w raporcie.

**Przerwij** działa również podczas oczekiwania. Zachowuje ukończone wyniki,
kończy scalanie gotowych map i usuwa nieukończone pliki robocze. Poczekaj na koniec
tego etapu przed zamknięciem QGIS. Eksport nie jest wznawiany po zamknięciu programu.

## Wynik i odczyt bez sieci

Przeczytaj raport przez **Otwórz raport**. Lista warstw i `raport.html` wskazują
wyniki niepełne, puste oraz błędy. `manifest.json` zawiera szczegółowy opis archiwum.
Pusty wynik wymaga porównania ze źródłem — sam w sobie nie potwierdza poprawnego odczytu.

Przycisk **Ponów tylko niezapisane i niepełne warstwy** tworzy **osobne archiwum**
z wybranych warstw. Zachowaj także poprzedni folder; wyniki nie są automatycznie łączone.

Przenieś **cały folder archiwum**, odłącz dostęp do źródłowych usług i baz,
a następnie otwórz kopię `.qgz` w QGIS. Sprawdź mapy przy zapisanych poziomach
szczegółowości, obiekty, atrybuty, załączniki, formularze i wydruki.
Do odczytu kopii ta wtyczka nie jest potrzebna.

Nie wszystkie fonty, zasoby, formularze i zależności wyrażeń mogą zostać przeniesione
automatycznie. Lokalne ścieżki nie wystarczają do potwierdzenia samodzielności
projektu; sprawdź uwagi w raporcie oraz działanie kopii bez sieci.

## Licencje i pomoc

Respektuj licencje każdej warstwy i warunki dostawców: pobieranie, kopiowanie,
przechowywanie offline, dalsze udostępnianie, oznaczenia autorstwa i limity usług.
Możliwość wyświetlenia mapy nie oznacza zgody na jej archiwizację.
Standardowy serwer `tile.openstreetmap.org` nie zezwala na pobieranie offline;
wybierz inne źródło dopuszczające taki użytek. Zobacz
[zasady OSMF](https://operations.osmfoundation.org/policies/tiles/).

Wtyczka nie przyznaje praw do cudzych treści i nie sprawdza automatycznie ich licencji.
Za zgodne z prawem użycie odpowiada użytkownik. W zakresie dopuszczalnym przez prawo
autor nie odpowiada za niedozwolone kopiowanie lub udostępnianie treści przez użytkownika.

Autorem jest Jarosław Sadowski. Wtyczka powstała metodą **vibe coding z pomocą AI**.
Licencja samej wtyczki: **GNU GPL v2 (GPL-2.0-only)**, warunki i brak gwarancji
w pliku `LICENSE` dołączonym do paczki. Licencja wtyczki nie obejmuje pobranych danych.

[Zgłoszenia błędów i propozycje](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/issues):
podaj wersję QGIS i wtyczki oraz kroki odtworzenia problemu. Pomocne są raport,
`manifest.json`, `diagnostic.jsonl` i dziennik z okna. Jeśli eksport zakończy się
błędem przed utworzeniem folderu archiwum, diagnostyka może pozostać w folderze
zapisu jako `<nazwa_archiwum>.diagnostic.jsonl`.
Sprawdź pliki przed udostępnieniem — mogą zawierać nazwy warstw lub dane poufne.
Nie publikuj haseł, poufnych projektów ani danych firmowych.

## English guide — installation and export

Requires QGIS 3.40 or a later 3.x release, with Qt5/PyQt5 and GDAL 3.7 or newer
supplied by QGIS. No extra packages are needed. Ensure access to project sources,
enough disk space and permission to download and store the selected data.

1. Choose **Plugins → Manage and Install Plugins → Install from ZIP** and select
   `qgis-project-snapshot-1.0.0.zip`. Restart QGIS when upgrading.
2. Open the project, then **Plugins → QGIS Project Snapshot → Archive project…**
   or the map-in-an-archive-box toolbar icon.
3. Choose a folder, area, layers and zoom range, then **Create archive**.

Installation from plugins.qgis.org will be available once publication is approved.
The interface follows the QGIS language, or the system language when no QGIS
language is set. Polish uses Polish; other languages use English.

The area can be the current map view or a polygon layer. Selected polygons are
used when there is a selection; otherwise all polygons are used. Vector features
intersecting the area are kept whole, with their attributes. PNG maps retain
transparency and are clipped to the area. The report identifies any vector data
that had to be replaced by an image.

The original project stays unchanged. Higher maximum zooms increase download time
and disk usage. Start with a small area and a few layers; adjust the initial 13–17
zoom range using the displayed scale and resolution. Estimates refer to one map,
not the entire project. Hover over controls for explanations.

## English guide — automatic downloads and cancellation

Separate QGIS processes download maps. Each server starts with one task;
concurrency grows using available computer resources, measured process memory,
download speed and server responses. Errors or lack of improvement limit growth.
No manual process count is needed, and maximum throughput is not guaranteed.

The server table shows **Active / limit**, **Queued layers**, **Tiles/s**, **Status**
and **Pause**. **Queued layers** counts layers waiting to start downloading from
the server in that row, excluding layers already downloading.
**Computer process limit** means local resources are blocking further growth.
These are map task limits, not exact HTTP request counts. One process handles one
map; vectors and source rasters do not use the same map process queue.

Downloads use the active QGIS network and proxy settings, exclusions and available
saved credentials. There is no separate proxy setup. Unusual authentication or
certificates may need checking on your workstation. Overload or repeated timeouts
may pause one server while others continue. Server retry times are respected.
Only missing tiles are repaired in the same archive, with limited retries.
Proxy authentication refusal (HTTP 407) stops the current map and is reported.

**Cancel** also works during waits. It preserves completed results, finishes
merging ready maps and removes incomplete working files. Wait for this to finish
before closing QGIS. Exports cannot resume after closing the application.

## English guide — results, rights and help

Read the report using **Open report**. Check incomplete and empty results against
the source. The final retry button creates a **separate archive** of selected
layers; keep both folders because results are not merged automatically.

Keep the **entire archive folder**. Disconnect from source services and databases,
then open the copied `.qgz` in QGIS. Check map detail, features, attributes,
attachments, forms and layouts. The plugin is not needed to open the copy.
Not all fonts, resources, forms and expression dependencies can be transferred.
Local paths alone do not prove a project is self-contained. Archive dates describe
acquisition times, not a simultaneous state of all sources.

Respect each layer's licence and provider's terms for downloading, copying,
offline storage, redistribution, attribution and service limits. Being able to
view a map does not grant permission to archive it. The standard
`tile.openstreetmap.org` service does not permit offline downloading; choose
a source that allows it. See the
[OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/).

The plugin does not grant rights to third-party content or check its licences.
Users are responsible for lawful use. To the extent permitted by applicable law,
the author accepts no liability for users' unauthorized copying or distribution
of content. The plugin itself is licensed under **GNU GPL v2 (GPL-2.0-only)**;
see the supplied `LICENSE` for terms and the warranty disclaimer. This licence
does not cover downloaded data. Author: Jarosław Sadowski. Developed through
**vibe coding with AI assistance**.

[Report a problem or suggestion](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/issues)
with your QGIS and plugin versions and reproduction steps. The report,
`manifest.json`, `diagnostic.jsonl` and window log can help. If export fails before
creating an archive folder, diagnostics may remain as `<archive_name>.diagnostic.jsonl`
in the chosen output folder. Inspect files before sharing; they may include
layer names or confidential data. Do not publish passwords, private projects
or company data.
