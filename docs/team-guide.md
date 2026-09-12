# QGIS Project Snapshot — instrukcja / user guide 1.4.3

## Instalacja i uruchomienie

Wymagane: QGIS 3.40 lub nowszy z serii 3.x, z Qt5/PyQt5 i GDAL co najmniej 3.7
z instalacji QGIS. Nie są potrzebne dodatkowe pakiety. Zapewnij dostęp do źródeł
projektu oraz miejsce na archiwum i pliki tymczasowe.

1. W QGIS wybierz **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Wskaż `qgis-project-snapshot-1.4.3.zip`. Po aktualizacji uruchom ponownie QGIS.
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
Błędy lub brak przyspieszenia ograniczają dalszy wzrost. Po okresie poprawnych
pobrań automat ponownie próbuje zwiększyć limit o jedno zadanie. Gdy próba nie
przynosi poprawy, wraca do niższego limitu i dłużej czeka na następną próbę.
Utrzymujący się spadek szybkości również może obniżyć limit. Jest to automatyczny
dobór, a nie gwarancja maksymalnego wykorzystania komputera czy łącza.

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

W Windows dostępny RAM nie jest jedynym ograniczeniem pamięci: system musi też
mieć możliwość przydzielenia jej kolejnemu procesowi. Od 1.3.0 wtyczka uwzględnia
ten dodatkowy limit przed uruchomieniem nowych map. Liczba widoczna przy RAM
nadal oznacza pamięć fizyczną. Podpowiedź RAM pokazuje mniejszy limit przydziału,
a w tabeli może pojawić się **Limit przydziału pamięci Windows**. Szczegóły zapisuje log.
Przy małym zapasie działające mapy są zachowywane, a nowe czekają.

## Połączenie, przerwy i anulowanie

Wtyczka korzysta z ustawień sieciowych aktywnego QGIS, w tym proxy, wyjątków
i dostępnych zapisanych poświadczeń. Nie wpisujesz proxy we wtyczce.
Nietypowe uwierzytelnianie lub certyfikaty mogą wymagać sprawdzenia na danym stanowisku.

Przeciążenie serwera lub powtarzające się przekroczenia czasu mogą uruchomić
przerwę. Wtyczka respektuje termin ponowienia podany przez serwer; inne serwery
mogą pracować dalej. Brakujące kafelki uzupełnia w tym samym archiwum, z ograniczoną
liczbą prób. Poprawnych kafelków nie pobiera ponownie. Odmowa uwierzytelnienia proxy
(HTTP 407) kończy pobieranie danej mapy i jest opisana w raporcie.

**Przerwij** działa również podczas oczekiwania. Zachowuje ukończone wyniki
oraz zapisany postęp map i kończy scalanie gotowych obrazów. Nieukończone pliki
wektorów są usuwane. Poczekaj na koniec zapisu przed zamknięciem QGIS.
Zachowaj cały wynikowy folder, aby później kontynuować.

## Kontynuacja po przerwie

1. Po zakończeniu lub anulowaniu eksportu z brakami wybierz **Kontynuuj to archiwum**.
   Jeśli QGIS był zamknięty, otwórz oryginalny projekt i okno archiwizacji,
   wybierz **Wznów archiwum…**, następnie wskaż folder poprzedniego archiwum.
2. Zapewnij miejsce na kopię danych oraz nowe pobrania. Potrzebny jest cały folder
   z `diagnostyka/manifest.json`, danymi i zasobami; sam JSON lub raport nie wystarcza.
   Starsze archiwa z manifestem bezpośrednio w folderze archiwum są nadal obsługiwane.
3. Poczekaj na sprawdzenie i skopiowanie plików. Powstanie **nowy folder**, który
   zawiera wcześniejsze ukończone wyniki oraz wyniki kontynuacji. Poprzedni folder
   pozostaje bez zmian.
4. Przeczytaj nowy raport i sprawdź kopię bez sieci przed usunięciem starszego archiwum.

Kontynuacja zachowuje ukończone warstwy, również oznaczone jako puste (`empty`),
jeśli mają zapisane dane lokalne. W nieukończonych mapach zachowuje poprawnie
zapisane obrazy i kafelki rozpoznane jako puste. Pobiera tylko brakujące kafelki,
z nowym limitem do trzech prób na kafelek w danym wznowieniu. **Pusty zoom nadal wymaga sprawdzenia**: może
oznaczać brak treści w danej skali lub obszarze. Jeśli chcesz powtórzyć taką
warstwę, zaznacz ją i wybierz **Utwórz archiwum**.

Nieukończona warstwa wektorowa jest pobierana od początku tylko tej warstwy.
Ukończonych wektorów zwykle nie trzeba pobierać ponownie. Wyjątkiem są stare zerowe
wyniki WFS/MSSQL i niepotwierdzone puste odczyty MSSQL — kontynuacja sprawdza je
ponownie. Poprawnie pusty odczyt wektora jest prawidłowym wynikiem: lokalna warstwa
zachowuje pola, ale ma zero obiektów. Jeśli raport prosi o porównanie MSSQL,
sprawdź ten sam obszar w oryginalnym projekcie.

Obszar, zoomy i zestaw warstw pochodzą z poprzedniego manifestu. Otwórz ten sam
oryginalny projekt, z zachowanymi warstwami, źródłami, stylami i CRS. Kontynuacja
odrzuca niezgodne ustawienia oraz niezapisane edycje; do zapisania nowych edycji
użyj zwykłego **Utwórz archiwum**, które zachowuje je bez zatwierdzania w źródle.
Archiwa 1.0.0 można kontynuować, ale nie zapisują informacji pozwalającej potwierdzić
zgodność źródeł i stylów. Wtyczka wyświetla wtedy komunikat o tym ograniczeniu.

Od 1.4.0 postęp map jest zapisywany podczas pobierania. Po nieoczekiwanym zamknięciu
QGIS wybierz **Wznów archiwum…** i folder z nazwą zawierającą `.w-trakcie-`.
Okno proponuje ostatni zachowany folder z manifestem; nie uruchamia wznowienia
samoczynnie. Nie usuwaj żadnych plików z tego folderu przed kontynuacją.
Kontynuacja kafelków wymaga postępu zapisanego od 1.4.0. Starsze archiwa zachowują
ukończone warstwy; nieukończona mapa bez rejestru zaczyna pobieranie warstwy od nowa.
Jeśli ta próba się nie powiedzie, pozostaje wcześniejszy zapisany obraz częściowy.

Przed planowanym zamknięciem programu użyj **Przerwij** i poczekaj na zapis.
Odzyskiwanie wymaga czytelnych plików; uszkodzenie dysku lub plików po utracie
zasilania może uniemożliwić kontynuację.

## Wynik i odczyt bez sieci

Przeczytaj raport przez **Otwórz raport**. Lista warstw i `raport.html` wskazują
wyniki niepełne, puste oraz błędy. `diagnostyka/manifest.json` zawiera szczegółowy
opis archiwum. Od 1.4.2 w folderze głównym pozostają projekt `.qgz`, `raport.html`,
`dane/` i potrzebne `zasoby/`. Dane i ich pomocnicze pliki odczytu są w `dane/`.
Manifest, log i zachowany postęp trafiają do
`diagnostyka/`; pusty katalog postępu jest usuwany. Do pracy otwieraj projekt,
a do przeczytania wyników raport. Pozostałych plików nie trzeba otwierać ręcznie.

Potwierdzone puste wektory w kopii projektu mają końcówkę
`_nie-bylo-obiektow-w-zasiegu`. Zachowują pola i style. Sufiks dotyczy tylko
prawidłowo zapisanej tabeli z zerem obiektów, której pusty wynik został potwierdzony.
Błąd, obraz zastępczy ani niepotwierdzone puste MSSQL nie dostają tej końcówki.
Oryginalny projekt i nazwy jego warstw pozostają bez zmian.
Pusty wynik wymaga porównania ze źródłem — sam w sobie nie potwierdza poprawnego odczytu.

Przenieś **cały folder archiwum**, odłącz dostęp do źródłowych usług i baz,
a następnie otwórz kopię `.qgz` w QGIS. Sprawdź mapy przy zapisanych poziomach
szczegółowości, obiekty, atrybuty, załączniki, formularze i wydruki.
Do odczytu kopii ta wtyczka nie jest potrzebna. GeoTIFF-y mają wewnętrzne piramidy
przyspieszające wyświetlanie po oddaleniu. Mapy udostępniają pobrane zoomy, również
poprawnie puste, bez zmiany stylu na poszczególnych poziomach. Brakujące kafelki
nie są zastępowane obrazami z innej skali.

Nie wszystkie fonty, zasoby, formularze i zależności wyrażeń mogą zostać przeniesione
automatycznie. Lokalne ścieżki nie wystarczają do potwierdzenia samodzielności
projektu; sprawdź uwagi w raporcie oraz działanie kopii bez sieci.

## Diagnostyka wydajności i pliki do zgłoszenia

Wtyczka automatycznie zapisuje lokalny `diagnostyka.jsonl`: użycie CPU,
dostępny i zajęty RAM, operacje odczytu i zapisu, kolejki, limity procesów,
oczekiwanie oraz obserwowane odpowiedzi serwerów. Pomiary komputera powstają
co około 5 sekund w głównym QGIS i procesach mapowych, również gdy pobieranie
czeka na odpowiedź. Wtyczka zapisuje też etapy pracy i końcowe wyniki warstw.
Nie trzeba włączać dodatkowej opcji ani instalować narzędzia pomiarowego.
Do pełnej analizy użyj logu po zakończeniu lub świadomym anulowaniu eksportu;
poczekaj na zapisanie wyniku i dołączenie logów procesów mapowych.

Od 1.4.2 `diagnostyka.jsonl` i `manifest.json` są w podfolderze `diagnostyka/`.
Wybierając folder do wznowienia, wskaż całe archiwum, nie ten podfolder.

| Cel | Co przekazać |
| --- | --- |
| Typowa analiza czasu pobierania i ograniczeń liczby procesów | Zwykle sam `diagnostyka.jsonl` (w starszych wersjach `diagnostic.jsonl`). |
| Wskazanie warstw po nazwie, szczegółowe sprawdzenie kompletności | Dodatkowo `manifest.json`; HTML przedstawia te same wyniki w czytelnej postaci. |
| Wznowienie albo sprawdzenie rzeczywistych danych w kopii | Cały folder archiwum z danymi, projektem i zasobami. Sam log nie wystarcza. |

Pliki AUX zazwyczaj nie są potrzebne do analizy wydajności. Z długiego przebiegu
powstaje większy log; można ręcznie spakować go do ZIP-a przed przekazaniem.
Wtyczka **nie wysyła diagnostyki automatycznie**. Zapisuje nazwy serwerów;
nowe pomiary nie zapisują nazw warstw, pełnych adresów źródeł, parametrów zapytań,
poświadczeń, treści odpowiedzi ani współrzędnych obszaru. Sprawdź udostępniane pliki,
zwłaszcza dodatkowy manifest i raport.

Log pomoże rozróżnić ograniczenie RAM, zajętość procesora i oczekiwanie na serwer.
Nie mierzy jednak maksymalnej przepustowości łącza lub serwera, temperatury CPU
ani procentowej zajętości fizycznego dysku. Obserwowane bajty odpowiedzi QGIS
nie są pomiarem całego ruchu sieciowego komputera. Brak odczytu czujnika jest
oznaczany jako niedostępny, a nie jako zerowe obciążenie. Sam zapis tych pomiarów
nie uruchamia dodatkowych pobrań ani testów szybkości.

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
podaj wersję QGIS i wtyczki oraz kroki odtworzenia problemu. Dobierz pliki zgodnie
z tabelą powyżej; dziennik z okna może uzupełnić opis. Po nieoczekiwanym zakończeniu
szukaj diagnostyki w podfolderze `diagnostyka/` zachowanego folderu `.w-trakcie-…`.
Sprawdź pliki przed udostępnieniem — mogą zawierać nazwy warstw lub dane poufne.
Nie publikuj haseł, poufnych projektów ani danych firmowych.

## English guide — installation and export

Requires QGIS 3.40 or a later 3.x release, with Qt5/PyQt5 and GDAL 3.7 or newer
supplied by QGIS. No extra packages are needed. Ensure access to project sources,
enough disk space and permission to download and store the selected data.

1. Choose **Plugins → Manage and Install Plugins → Install from ZIP** and select
   `qgis-project-snapshot-1.4.3.zip`. Restart QGIS when upgrading.
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
After healthy periods, it tries increasing the limit by one task again. If that
does not help, it returns to the lower limit and waits longer before another trial.
Sustained slowdowns may also reduce the limit. No manual process count is needed,
and maximum throughput is not guaranteed.

The server table shows **Active / limit**, **Queued layers**, **Tiles/s**, **Status**
and **Pause**. **Queued layers** counts layers waiting to start downloading from
the server in that row, excluding layers already downloading.
**Computer process limit** means local resources are blocking further growth.
These are map task limits, not exact HTTP request counts. One process handles one
map; vectors and source rasters do not use the same map process queue.

On Windows, available physical RAM is not the only memory constraint: the system
must also be able to commit memory to a new process. From 1.3.0, the plugin checks
this additional limit before starting more maps. The RAM display still shows
physical memory. Its tooltip shows the lower allocation limit, and the table may
show **Windows memory allocation limit**. The log records further details. Existing
maps continue when headroom is low, while new ones wait.

Downloads use the active QGIS network and proxy settings, exclusions and available
saved credentials. There is no separate proxy setup. Unusual authentication or
certificates may need checking on your workstation. Overload or repeated timeouts
may pause one server while others continue. Server retry times are respected.
Only missing tiles are repaired in the same archive, with limited retries.
Proxy authentication refusal (HTTP 407) stops the current map and is reported.

**Cancel** also works during waits. It preserves completed results and saved map
progress, and finishes merging ready images. Incomplete vector files are removed.
Wait for saving to finish before closing QGIS. Keep the entire resulting folder
for later continuation.

## English guide — continuing after a break

1. After an incomplete export finishes or is cancelled, choose **Continue this archive**.
   If QGIS was closed, open the original project and the archive window, choose
   **Resume archive…**, then select the previous archive folder.
2. Allow space for a copy of the data and new downloads. You need the entire folder
   with `diagnostics/manifest.json`, data and resources; a JSON file or report alone is not enough.
   Older archives with their manifest directly in the archive folder remain supported.
3. Wait while files are checked and copied. A **new folder** will contain the earlier
   completed results and the continuation results. The previous folder stays unchanged.
4. Read the new report and check the copy offline before removing the older archive.

Continuation copies completed layers, including those marked `empty`, when they
have saved local data. For unfinished maps, it retains successfully saved images
and tiles confirmed empty. Only missing tiles are downloaded, with up to three
new attempts per tile in that continuation.
**An empty zoom still needs review**: the source may have no content at that scale
or in that area. To download such a layer again, select it and use **Create archive**.

An unfinished vector layer starts that layer again. Completed vector layers are
normally reused. Older zero-feature WFS/MSSQL results and unconfirmed empty MSSQL
reads are checked again during continuation. A correctly empty vector read is a
valid result: the local layer retains its fields and contains zero features.
If the report asks for an MSSQL comparison, check the same area in the original project.

The previous manifest supplies the area, zooms and layer selection. Use the same
original project, with matching layers, sources, styles and CRS. Continuation
rejects incompatible settings and unsaved edits. Use the ordinary **Create archive**
to include new edits without committing them to the source.
Archives from 1.0.0 can be continued, but they lack the information needed to
confirm source and style compatibility. The plugin reports that limitation.

From 1.4.0, map progress is saved during downloads. After an unexpected QGIS exit,
choose **Resume archive…** and the folder whose name contains `.in-progress-`.
The dialog suggests the last available folder with a manifest; it does not resume
automatically. Keep all files in that folder until continuation finishes.
Tile continuation requires progress saved from 1.4.0 onward. Older archives retain
completed layers; an unfinished map without a tile record restarts that layer.
If the retry fails, its previously saved partial image is retained.

Before a planned shutdown, use **Cancel** and wait for saving. Recovery requires
readable files; damaged storage or files after power loss may prevent continuation.
GeoTIFF overviews help display rasters when zoomed out. Maps retain downloaded
zooms and their separate styles, including correctly empty levels. Missing tiles
are not replaced with images from another scale.

## English guide — performance diagnostics and files to share

From 1.2.0, the plugin automatically saves a local `diagnostic.jsonl` with CPU,
available and resident memory, read/write operations, queues, process limits,
waiting states and observed server responses. Computer samples are taken about
every 5 seconds in the main QGIS process and map processes, including while
downloads wait for replies. Work phases and final layer results are also recorded.
No additional option or measurement tool is required.
For a complete review, use the log after the export finishes or is deliberately
cancelled; wait for the result and map process logs to be saved.

From 1.4.2, `diagnostic.jsonl` and `manifest.json` are in `diagnostics/`.
When resuming, select the entire archive folder, not that subfolder.

| Purpose | Files to provide |
| --- | --- |
| Typical review of download time and process limits | Usually just `diagnostic.jsonl` from 1.2.0 or later. |
| Identifying layers by name or examining completeness in detail | Also include `manifest.json`; HTML presents the same results in readable form. |
| Resuming or checking the actual saved data | The entire archive folder, including data, project and resources. A log alone is not enough. |

AUX files are usually unnecessary for performance analysis. Longer exports create
larger logs; you can manually ZIP a log before sharing. The plugin **does not send
diagnostics automatically**. Server names are recorded; new measurements do not
save layer names, complete source URLs, query parameters, credentials, response
contents or area coordinates. Check files before sharing, especially any additional
manifest or report.

The log helps distinguish memory limits, CPU use and waits for servers. It does
not measure maximum link or server throughput, CPU temperature or physical disk
busy percentage. Observed QGIS response bytes are not all network traffic on the
computer. Unavailable sensor readings are recorded as unavailable, not as zero
load. Recording these measurements does not start extra downloads or speed tests.

## English guide — results, rights and help

Open the `.qgz` project to work with the archive, or `report.html` to review results.
From 1.4.2, the main folder contains the project, report, `data/` and required
`resources/`. Data and their supporting read files are in `data/`.
The manifest, log and saved progress are grouped under `diagnostics/`;
an empty progress folder is removed. You do not need to open those files manually.
Keep and move the entire archive folder.

Confirmed empty vector layers in the project copy receive the exact suffix
`_no-features-in-area`. Fields and styles remain. It applies only to
successfully saved zero-feature tables whose empty read was confirmed. Errors,
fallback images and unconfirmed empty MSSQL reads do not receive this suffix.
The original project and its layer names remain unchanged.

Read the report using **Open report**. Check incomplete and empty results against
the source. A continued archive includes copied results and newly downloaded
layers. Keep the previous folder until you have checked the new result.

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
with your QGIS and plugin versions and reproduction steps. Choose files using the
table above; the window log can add context. After an unexpected exit, look in
`diagnostics/` inside the retained `.in-progress-…` folder. Inspect files before sharing; they may include
layer names or confidential data. Do not publish passwords, private projects
or company data.
