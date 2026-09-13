# Działanie i ograniczenia archiwizacji (1.0.2)

Pierwsze oficjalne wydanie to 1.0.0. Numery 1.1–1.4 poniżej odnoszą się
do wcześniejszych wersji rozwojowych i historii wdrażania funkcji.

Jedna akcja **QGIS Project Snapshot** tworzy osobny katalog projektu z lokalnymi
danymi, raportem HTML i manifestem JSON. Nie zastępuje oryginału. Techniczny
identyfikator `mbtiles_batch_exporter` pozostaje dla aktualizacji istniejących
instalacji; dawny eksporter, jego okno i pomocniczy moduł zostały usunięte.

## Dane i odtworzenie projektu

- Wektory: geometrie i atrybuty w osobnych tabelach jednego `dane/dane.gpkg`,
  z filtrami i niezapisanymi edycjami. Zachowujemy całe obiekty przecinające obszar.
- Obrazy map WMS/WMTS/XYZ/ArcGIS: osobne tabele rastra tego samego GeoPackage,
  w CRS projektu, m.in. EPSG:2180. PNG RGBA, ZLEVEL=9, bez redukcji alfa i kolorów.
- Każdy wybrany zoom renderujemy niezależnie, zgodnie z widocznością zależną
  od skali. Siatka 256 × 256, margines renderowania i maska rzeczywistych poligonów
  z dziurami. Przestrzenne wyszukiwanie kafelków ogranicza koszt długich pasów.
- Rastry GDAL: najpierw oryginalne wartości i maska w bezstratnym GeoTIFF.
  Awaryjne zachowanie obrazu jest jawnie opisane, także dla wektorów.
- Kopia `.qgz` zachowuje ID, grupy, kolejność, widoczność, style i relacje zapisanych
  warstw. Kopiowane są dostępne SVG, obrazy, formularze UI, załączniki i style osadzone.
- Pominięte źródła są usuwane z kopii. Wynik ponownie odczytują dostawcy QGIS.
  Raport opisuje braki, jakość, zależności, czasy i sumy kontrolne.

Przenosi się cały folder archiwum. Nie wszystkie fonty, wyrażenia, kod formularzy
lub zależności są pakowane. Relacje mogą wskazywać obiekty spoza obszaru. Poprawne
lokalne ścieżki nie dowodzą pełnej samodzielności; wymagany jest odbiór bez sieci.
Data oznacza czas pobierania, nie jednoczesny stan wszystkich zewnętrznych źródeł.

Od 1.4.0 `_write_vector` sprawdza poprawność geometrii obszaru i CRS przed
odczytem. Dla WFS odświeża natywny cache tylko poza trybem edycji, aby zachować
identyfikatory niezapisanych zmian. Po iteracji dostarcza oczekujące błędy Qt
wyłącznie aktywnemu dostawcy, zanim uzna pusty wynik za poprawny. Odpowiedź OGC
z błędem nie może zostać zakwalifikowana jako `Saved` z zerem obiektów.

Przy zerowym odczycie MSSQL natywne połączenie dostawcy wykonuje `SELECT TOP(1)`
dla tej samej tabeli i istniejącego filtra, aby sprawdzić dostęp do źródła.
Błąd uniemożliwia potwierdzenie pustego wyniku. Znalezienie obiektu poza obszarem
nie oznacza błędu: poprawny przestrzenny odczyt nadal może dać zero obiektów.
Próba nie weryfikuje całego zapytania przestrzennego i nie zastępuje odbioru
firmowej bazy. Diagnostyka podaje CRS, odświeżenie cache i stan próby
`empty_source_probe`, bez URI, SQL, treści obiektów ani wyjątków z poświadczeniami.

Nowe odczyty wektorów oznacza `vector_read_version=2`. Przy pustym MSSQL sama
dostępność tabeli z obiektami nie potwierdza braku treści w wybranym obszarze:
`empty_read_verified=null` zachowuje uwagę do porównania w oryginalnym projekcie.
Kontynuacja ponawia takie zerowe odczyty oraz stare zerowe WFS/MSSQL bez v2,
zamiast bezwarunkowo kopiować wcześniejszy `saved`. Potwierdzone puste odczyty
pozostają prawidłowym wynikiem i nie wymagają ponownego pobrania.

## Nazwy pustych wektorów i układ folderu (1.4.2)

Nazwy generowane wybiera istniejący katalog Qt według języka wtyczki. Nazwy
źródłowych projektów, warstw i załączników oraz identyfikatory techniczne pozostają.

| Element | Polski | English |
| --- | --- | --- |
| Dopisek pustego wektora | `_nie-bylo-obiektow-w-zasiegu` | `_no-features-in-area` |
| Archiwum/projekt | `<nazwa>_archiwum_<data>` | `<name>_archive_<date>` |
| Folder nieukończony | `.w-trakcie-…` | `.in-progress-…` |
| GeoPackage | `dane/dane.gpkg` | `data/data.gpkg` |
| Zasoby | `zasoby/` | `resources/` |
| Raport | `raport.html` | `report.html` |
| Manifest | `diagnostyka/manifest.json` | `diagnostics/manifest.json` |
| Log | `diagnostyka/diagnostyka.jsonl` | `diagnostics/diagnostic.jsonl` |
| Postęp | `diagnostyka/stan-pobierania/` | `diagnostics/download-state/` |

Schemat manifestu nadal 4. `data_file`, `resources_directory` i
`recovery_directory` zapisują rzeczywiste położenie danych, niezależnie od języka
następnego wznowienia. Odczyt dopuszcza tylko znane ścieżki. Manifesty sprzed 1.4.2
otrzymują w pamięci domyślne stare nazwy; ich pliki nie są przepisywane.
Przy kontynuacji kopiowane dane i ścieżki załączników przechodzą do bieżącego języka.
Prywatne identyfikatory tabel/cache i format rejestru SQLite pozostają zgodne.

W kopii projektu `output_name` otrzymuje końcówkę `_nie-bylo-obiektow-w-zasiegu`
wyłącznie dla `saved`, metody `vector`, `feature_count=0` i
`empty_read_verified=true`. `name` nadal opisuje oryginalną warstwę; jej nazwa,
ID i źródło nie są zmieniane w projekcie użytkownika. Sufiks nie obejmuje pustych
obrazów, błędów ani niepotwierdzonego zerowego MSSQL. Raport i okno wyników pokazują
nazwę kopii, zachowując informację o oryginale w manifeście.

Pliki techniczne trafiają do `diagnostyka/`: `manifest.json`, `diagnostyka.jsonl`
oraz `stan-pobierania/`, jeśli jest potrzebny do kontynuacji. Pusty katalog postępu
jest usuwany. Projekt `.qgz`, `raport.html`, `dane/` i potrzebne `zasoby/` pozostają
w folderze głównym. `dane/dane.gpkg` przechowuje wektory i mapy; pliki AUX QGIS/GDAL
pozostają obok niego, zachowując statystyki potrzebne do szybkiego odczytu.
`resume_manifest_path(folder)` wybiera manifest z nowego
podfolderu lub dawnej lokalizacji; okno nadal przyjmuje cały folder archiwum.
Nie trzeba ręcznie przenosić plików starszego wyniku przed wznowieniem.

## Procesy i automat

Od 1.4.3 techniczne odczyty projektu (proces mapowy, kontrola XML i audyt
lokalnych warstw) używają natywnych flag QGIS `DontStoreOriginalStyles`,
`DontLoadLayouts`, `DontLoad3DViews`. Nie tworzą kopii stylów dla edytora ani
obiektów nieużywanych układów i widoków 3D. Style do renderowania nadal są
odczytywane; cały źródłowy XML pozostaje podstawą wynikowego projektu. Audyt
lokalnych warstw nadal otwiera dostawców i wykrywa brak danych. Tylko osobna,
wcześniejsza kontrola struktury XML używa `DontResolveLayers`.
Pomiar syntetyczny i ograniczenia: [raport 1.4.3](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/blob/v1.0.1/docs/validation-1.4.3.md).

API `create_archive(..., adaptive=False)` zachowuje zgodny tryb stały. Okno używa
wyłącznie `adaptive=True`. Procesy map mają własne QGIS; do wątków nadzorujących
nie przekazujemy obiektów QGIS. Końcowy GeoPackage ma jednego zapisującego.
Wektory, MSSQL, rastry źródłowe i usługi z authcfg pozostają w głównym QGIS.
Mapy z głównej ścieżki korzystają ze wspólnej bramki hosta.

Opis limitu trzech prób w instrukcji dotyczy standardowego trybu okna.
Techniczne API `adaptive=False` zachowuje wcześniejszą naprawę: po trzech
nieudanych próbach całego kafelka 256 px dzieli go na cztery fragmenty 128 px,
z najwyżej trzema próbami każdego. Ostateczny błąd fragmentu kończy ten kafelek;
rejestr nie powtarza dodatkowo całego cyklu. Dopiero złożony i utrwalony PNG
rodzica jest sukcesem do wznowienia. HTTP 429 lub pięć kolejnych ostatecznych
błędów kończy pobieranie mapy w tym trybie. Opcja nie jest dostępna w GUI.

Start: jedno zadanie mapowe na host, niezależnie od ścieżek usług. Wzrost o jeden
wymaga 15 s, 10 poprawnych kafelków, kolejki i wolnego budżetu. Dwa kolejne okna
bez 10% poprawy przepustowości cofają limit i czasowo wstrzymują wzrost. Pomiar wymaga
15 s pomiaru z docelową liczbą gotowych map. Przerwy na rozruch kolejnej mapy
są wyłączane z czasu i liczby sukcesów, lecz nie kasują wcześniejszych próbek.
Gotowy proces między publikacją wyniku kafelka a zgodą na następny pozostaje
gotowy do pomiaru. Rozruch i kończąca się kolejka nie świadczą o suficie serwera. Sufit hosta to min(32, 2 × CPU), dodatkowo
ograniczany wspólnym budżetem RAM i liczbą map.
HTTP 429/503 natychmiast zmniejszają obciążenie i uruchamiają przerwę;
timeouty oraz HTTP 502/504 robią to po trzech kolejnych niepowodzeniach.
503 oznacza możliwe przeciążenie lub niedostępność, nie dowód jednej przyczyny.

Od 1.3.0 `frozen` oznacza okres stabilizacji, a nie blokadę do końca eksportu.
Po 60 s zdrowych pomiarów przy pełnym bieżącym obciążeniu automat może wykonać
jedną próbę `limit + 1`. Zlicza wyłącznie ukończone okna po co najmniej 15 s
i 10 sukcesów; sam upływ minuty, brak kolejki lub niepełne obsadzenie limitu nie
uprawniają do wzrostu. Błędy zerują zdrowy okres. Nowa próba jest porównywana
z ostatnim pomiarem przy niższym limicie, a nie z szybkością początku eksportu.
Wymaga co najmniej 10% zysku; dwa kolejne słabe pełne okna cofają zwiększenie.
Nieudane ponowne próby wydłużają stabilizację do 120, 240 i najwyżej 300 s.
Po udanej próbie kolejny okres stabilizacji znów może zaczynać się od 60 s.

Automat obserwuje też ustabilizowany limit. Spadek szybkości o ponad 25% względem
szybkości odniesienia przez dwa pełne okna zmniejsza limit o jeden, co najmniej
do jednego. Niepełne okna rozruchu nie są dowodem pogorszenia. Dzięki temu
ograniczanie obciążenia nie wymaga wcześniejszej próby zwiększenia limitu.

Przerwy: Retry-After w sekundach lub dacie HTTP, inaczej 30/60/120 s. Po przerwie
jedna próba rzeczywiście brakującego kafelka; jej sukces odblokowuje host.
Trzy nieudane próby powrotu albo wymagane oczekiwanie ponad pięć minut odkładają
pozostałe dane. Następna mapa może dostarczyć kafelek do próby powrotu, gdy obecna
wyczerpała własne ponowienia. Spóźnione Retry-After obowiązuje również po udanej
próbie: nowa generacja ponownie wstrzymuje host bez wielokrotnego obniżania limitu
za tę samą falę błędów. Inne hosty pracują.

Limit globalny: min(32, 2 × CPU, budżet pamięci), co najmniej jeden; nieznany dostępny
RAM ogranicza do dwóch. Po renderowaniu każdy proces publikuje bieżący i szczytowy
RSS z natywnego systemu, co 5 s i przy zamknięciu. Koszt następnego procesu E to
max(384 MiB, 1,5 × największy szczyt z tego eksportu), początkowo 1 GiB. Główny
QGIS z local_gate nie uczestniczy w tym pomiarze; jego zużycie jest w MemAvailable.

Od dostępnej pamięci odejmujemy 768 MiB rezerwy i zapas wzrostu każdego aktywnego
procesu max(0, E − bieżący RSS). Nieznany RSS zachowuje pełną rezerwację startową,
co najmniej E. Pozostała pamięć daje miejsca dla nowych procesów po E bajtów.
Zachowujemy największy peak również po końcu procesu. Zwolniony RSS może być
ponownie potrzebny; samo jego obniżenie nie usuwa rezerwy na wzrost.

Od 1.3.0 `available_memory(include_commit=True)` dodatkowo ogranicza dostępne
bajty do mniejszej z wartości fizycznego RAM i dostępnego commit na Windows.
Ta wartość ogranicza starty; domyślne `available_memory()` oraz wyświetlany RAM
nadal oznaczają pamięć fizyczną. Brak odczytu commit pozostawia wcześniejszą
regułę RAM. Zachowano 768 MiB rezerwy i dotychczasowy szacunek procesu z RSS.
To dodatkowy hamulec, nie ścisły model commit każdego procesu: RSS i commit
mają różną semantykę, a inne aplikacje mogą zużyć dostępny zapas między próbkami.
Niskie zasoby ograniczają nowe starty bez usuwania ukończonych danych czy zabijania
działających map. Natywna diagnostyka pokazuje oddzielnie RAM i commit.

Telemetria poprzedza próbkę RAM. `launch_slots` wyznacza skończony przydział startów
na podstawie próbki co 5 s. Zakończenie mapy nie odnawia przydziału. Spadek poniżej
rezerwy blokuje nowe procesy i wzrost, nie przerywa działających map. Przerwy
na danym hoście mogą pozostawić uruchomione, lecz oczekujące procesy. Wzrost może
ponownie dopuścić taki proces bez startu nowego, nawet bez kolejki nowych warstw;
wymaga jednak pokrycia rezerwy 768 MiB oraz zapasu wzrostu wszystkich procesów
(`memory_growth_ok`). Odłożone hosty kończą swoje oczekujące wyniki bez potrzeby
wolnego slotu lub odzyskania pamięci. Przerwy
serwerów także liczą się do aktywnych procesów. GUI pokazuje estymatę i rezerwę;
historia pamięci oraz manifest zapisują też szczyt i zapas wzrostu. To heurystyka; nagły wzrost zużycia pamięci
może przekroczyć zapas. Nie jest to gwarancja maksimum przepustowości ani RAM.

Koordynator co 0,5 s czyta atomowe statystyki i zapisuje polecenia protokołu 1:
generacja, pozwolenie, przerwa/próba powrotu, potwierdzenie zdarzeń i ważność 2 s.
Bramka sprawdza zgodę przed operacją renderowania i ponowieniem; oczekiwanie
obsługuje anulowanie. Brak łączności z koordynatorem odkłada mapę.
Od 1.3.0 zwykły błąd odpowiedzi WMS nie wymaga oczekiwania na osobne potwierdzenie
każdego zdarzenia przed dalszą pracą. Zdarzenia nadal trafiają do koordynatora;
obowiązkowy ACK pozostaje dla przeciążenia, timeoutu i próby powrotu hosta.
Nie zmienia to ważności pozwolenia, przerw serwera ani limitu prób kafelka.

Dyskowy rejestr SQLite zapisuje wynik i liczbę prób każdego kafelka, także poprawnie
przezroczystego. Najwyżej trzy podejścia (początkowe + dwie rundy uzupełniania),
bez ponownego pobierania sukcesów i odtwarzania tabeli. Przy przeciążeniu lub timeout
pomijane są natychmiastowe ponowienia i podziały. HTTP 401/403/404/407 nie są ponawiane.
Mapę scala się po zakończeniu pobierania/naprawy; gotowe PNG są kopiowane bez rekompresji.

Anulowanie zachowuje ukończone, scalone warstwy oraz trwały postęp map.
Nieodpowiadające procesy są kończone po pięciu sekundach od anulowania.
Nieukończone wektory i nietrwałe pliki wykonawcze są usuwane. Wynik oraz zachowany
folder postępu można kontynuować po ponownym otwarciu oryginalnego projektu.
Limitów serwerów nie przenosimy między eksportami.

## Kontynuacja warstw i kafelków (1.4.0)

`create_archive(..., resume_from=folder)` kontynuuje zapisany wynik lub folder
postępu po anulowaniu albo nieoczekiwanym zakończeniu QGIS. `read_resume_manifest`
odczytuje manifest 4 bez otwierania zarchiwizowanego projektu ani źródeł sieciowych.
Okno bierze z manifestu obszar, zoomy i zestaw warstw. Potrzebny jest cały folder
archiwum oraz oryginalny projekt; sam manifest nie zawiera danych do skopiowania.

Kontynuacja wymaga zgodności ID wybranych warstw, dostawców, CRS projektu i obszaru,
geometrii obszaru oraz zoomów. Rekordy od 1.1.0 zawierają `source_fingerprint`:
SHA-256 ustawień źródła, dostawcy, CRS, filtra wektora i stylu. Manifest nie zapisuje
surowego źródła ani poświadczeń. Zmiana odcisku blokuje kontynuację; hash nie dowodzi,
że zawartość zdalnej bazy lub usługi pozostała taka sama. Niezapisane edycje warstw
wybranych do kontynuacji również ją blokują. Zwykły nowy eksport nadal zachowuje
bufor edycji bez zatwierdzania go w źródle.

Od 1.4.0 rekord podaje `source_fingerprint_version=2`. Przed obliczeniem odcisku
XML stylu przechodzi przez natywne `ElementTree.canonicalize`, dzięki czemu
kolejność atrybutów zmieniana przez Qt między procesami nie blokuje wznowienia
niezmienionego projektu po restarcie. Archiwa 1.1–1.3 są nadal sprawdzane dawną
metodą: mogą odmówić kontynuacji po restarcie wskutek tej niestabilnej kolejności.
Nie pomijamy weryfikacji takiego wyniku. Zarchiwizowany `.qgz` nie zastępuje
oryginalnej definicji źródła i stylu, ponieważ zapis kopii zmienia ich odwołania.

Archiwa 1.0.0 bez odcisku pozostają obsługiwane. Sprawdzamy ich ID, dostawców,
obszar, CRS i zoomy, lecz nie deklarujemy zgodności źródeł i stylów. Ograniczenie
jest zgłaszane w oknie i jako `continuation.source_settings_verified=false`.

`_copy_resume` kopiuje `dane/dane.gpkg`, pliki `zasoby/` i zachowany
`diagnostyka/stan-pobierania/`
do nowego folderu. Zakończone archiwum weryfikuje przez SHA-256. Dla checkpointu
SQLite backup kopiuje spójny zatwierdzony stan baz, następnie sprawdza ich
integralność. Odrzucane są ścieżki poza archiwum i niezgodne odwołania lokalne.
Poprzedni wynik pozostaje dostępny. Projekt wynikowy powstaje ze źródłowego
projektu QGIS, z zachowaniem obecnych zasad zasobów i relacji. Nowy folder wymaga
miejsca na kopię istniejących danych i nowe wyniki.

`saved` i `empty` z `local_source` są kopiowane z oznaczeniem `reused=true`,
bez powtórnego odczytu dostawcy lub renderowania. Status `empty` nadal oznacza
konieczność sprawdzenia przezroczystych zoomów. Mapy `failed`, `cancelled` i `partial`
z rejestrem 1.4.0 zachowują ukończone kafelki, również prawidłowo puste.
Nieukończony wektor jest pobierany od początku tylko swojej warstwy.
Starsze mapy bez rejestru powtarzają całą warstwę; jeżeli próba nie zakończy się
jako `saved` lub `empty`, zachowujemy wcześniejszy obraz częściowy, z `reused=true`
i `continuation_attempt` opisującym wynik tej próby.

Sekcja `continuation` manifestu podaje czas rozpoczęcia poprzedniego archiwum,
SHA-256 poprzedniego manifestu, liczbę użytych ponownie warstw i stan weryfikacji
ustawień źródeł. Zdarzenie diagnostyczne `layer_reused` opisuje skopiowaną ukończoną
warstwę. `completed_in_workers` pomija rekordy użyte ponownie. Daty skopiowanych
warstw pozostają datami ich wcześniejszego pobrania.

Eksport od początku używa widocznego katalogu `nazwa.w-trakcie-losowy`.
Atomowy trwały `diagnostyka/manifest.json` z `checkpoint=true` jest zapisywany przed
pobieraniem i po ukończeniu warstw. `checkpoint_created` przekazuje jego folder
oknu, które zapisuje go w `QgsSettings` i podpowiada przy następnym wyborze
wznowienia. Po poprawnym zakończeniu folder otrzymuje końcową nazwę, a ustawienie
jest aktualizowane. Natywny `QLockFile` blokuje równoczesne wznowienie danych
używanych przez działający proces. Pliki wykonawcze procesu i migawka źródła nie
są wymagane do wznowienia; odtwarza je oryginalny projekt.

Każda mapa ma prywatny `diagnostyka/stan-pobierania/layer_<hash>/raster.gpkg`
i `tiles.sqlite`.
Rejestr sprawdza obszar, CRS, siatkę i poziomy. Po wznowieniu uzgadnia zatwierdzone
PNG z zapisanymi wynikami oraz ich SHA-256; rozróżnia poprawnie puste kafelki od
brakujących. Udane zapisy oraz puste wyniki nie są ponawiane. Pozostałe kafelki
otrzymują nowy budżet do trzech prób, przy zachowaniu historii liczby podejść.
Rejestr i PNG korzystają z zatwierdzonych transakcji SQLite; obraz jest utrwalany
przed potwierdzeniem sukcesu w rejestrze. Nie wymaga to własnego formatu obrazów
ani nowej zależności. Cache ukończonej mapy jest usuwany dopiero po utrwaleniu
scalonej warstwy i manifestu. Awaria pomiędzy tymi etapami może wymagać ponownego
lokalnego scalenia, bez pobrania ukończonych kafelków.

Odzyskiwanie wymaga zachowanych czytelnych plików; nie gwarantuje naprawy danych
po uszkodzeniu nośnika lub awarii zasilania. Algorytmy obciążenia, timeouty,
PNG RGBA `ZLEVEL=9` i jeden zapisujący końcowy GeoPackage pozostają bez zmian.

## Piramidy rastrów (1.4.0)

`write_raster_data` buduje natywne wewnętrzne piramidy GeoTIFF przez
`BuildOverviews("NEAREST", factors)`, z kompresją DEFLATE poziom 9. Czynniki 2, 4,
8 itd. kończą się, gdy większy wymiar poziomu spadłby poniżej 256 pikseli.
Pełna rozdzielczość zachowuje wartości danych, kanał alfa lub maskę; piramidy nie
zastępują danych źródłowych. Callback GDAL obsługuje postęp i anulowanie.

Mapy GPKG nadal renderują każdy wybrany zoom niezależnie. GDAL pomija w odczycie
zoom bez ani jednego fizycznego PNG, nawet gdy istnieje wpis `gpkg_tile_matrix`.
Po pełnym poprawnie pustym odczycie zoomu `_empty_zoom_overviews` zapisuje jeden
przezroczysty PNG RGBA w jego macierzy. Lista `empty_zoom_placeholders` odróżnia
te znaczniki od treści; logiczny `tile_count` nadal liczy wyłącznie niepuste
kafelki. Zoom z błędami lub oczekiwaniem nie dostaje znacznika. Przy wznowieniu
znaczniki są usuwane przed uzgodnieniem rejestru i odtwarzane po zakończeniu.
Dzięki temu poprawnie puste poziomy są widoczne w natywnych piramidach GDAL/QGIS,
także po scaleniu. Nie wywołujemy `BuildOverviews` na mapach: zmieniłoby to style
zależne od skali. Brakujące kafelki nie są wypełniane obrazem z innego zoomu.

Lokalne testy QGIS 3.40/GDAL 3.12 potwierdzają natywny odczyt poziomów przed
scaleniem i po nim, odrębne kolory stylów oraz zachowanie pełnej przezroczystości
pustego poziomu. Dwa całkowicie puste zoomy oznaczają dwa fizyczne znaczniki PNG,
lecz nadal `status=empty` i `tile_count=0`. To dostępność piramid do odczytu,
nie dowód kompletności źródłowej usługi ani pomiar przyspieszenia dużego projektu.

## Proxy i diagnostyka

`worker_network.network_snapshot()` działa na głównym wątku. Odczytuje proxy
aktywnego profilu, wyjątki, tryb systemowy i poświadczenia rozpoznane przez
QgsNetworkAccessManager (także już rozwiązaną konfigurację uwierzytelniania).
Zwykłe dane JSON trafiają przez prywatny stdin procesu, nie przez pliki, argumenty
polecenia czy manifest. Proxy nie jest ustawiane ręcznie w interfejsie wtyczki.

Proces ma izolowany profil przez QGIS_CUSTOM_CONFIG_PATH. Zapisuje wyłącznie
ustawienia bez hasła/loginu/authcfg. Natywny menedżer QGIS obsługuje routing;
callback proxyAuthenticationRequired podaje poświadczenia z pamięci dla zgodnego
hosta i portu. Wyłączone proxy nie powoduje włączenia dodatkowego proxy procesu.
Nie kopiujemy bazy uwierzytelniania i nie wyłączamy weryfikacji TLS.

Złożone metody firmowe, logowanie interaktywne, dodatkowe fabryki proxy i certyfikaty
niestandardowego profilu wymagają osobnego odbioru. Sprawdzono lokalne HTTP Basic,
połączenie bez proxy, wyjątek oraz 407; nie jest to test wszystkich proxy Windows.

WorkerError i error.json przekazują etap oraz kody zakończenia/HTTP/Qt, bez surowych
wyjątków dostawców. HTTP 407, błędy połączenia z proxy i TLS mają czytelne opisy.
Awaria procesu w trybie adaptacyjnym nie uruchamia ponowienia w głównym QGIS
z pominięciem ograniczeń. Windows uruchamia proces przez CREATE_NO_WINDOW;
interpreter jest szukany również w sys.prefix/python.exe.

## Interfejs i moduły

Lista warstw, grupy, tabela hostów i dziennik pozostają dostępne podczas eksportu.
Zmiana wyboru warstw i parametrów jest zablokowana. Host bez zadań pokazuje
zakończenie lub błędy. Licznik procesów obejmuje mapy, nie odczyty WFS/MSSQL.
Natywny synchroniczny odczyt w głównym QGIS nadal może chwilowo zatrzymać obsługę zdarzeń.

Interfejs PL/EN wybiera język QGIS, następnie systemu. Katalog `en.ts`/`en.qm`
jest pakowany. Końcowy ekran zaznacza failed/cancelled/partial. Przycisk
„Kontynuuj to archiwum” używa ostatniego wyniku; „Wznów archiwum…” pozwala
wskazać folder po restarcie. Kontynuacja zachowuje cały poprzedni wybór warstw,
kopiując ukończone wyniki. Zwykły przycisk tworzenia archiwum eksportuje tylko
aktualnie zaznaczone warstwy. Automatyczna naprawa kafelków dotyczy bieżącego
eksportu. Raport HTML zawiera manifest 4, w tym historię automatu, informacje
o kontynuacji, diagnozy i do 20 przykładów błędów kafelków na mapę.

| Moduł | Rola |
| --- | --- |
| plugin.py, __init__.py | Jedna akcja QGIS, cykl życia okna |
| archive_dialog.py, i18n.py | Okno, postęp i język |
| archive.py | Wektory, projekt, raport i manifest |
| archive_resources.py | Zasoby, relacje i kontrola lokalnych źródeł |
| raster_archive.py | Mapy PNG, maska, rejestr kafelków, rastry źródłowe |
| parallel_archive.py, archive_worker.py | Izolacja QGIS, procesy i scalanie |
| adaptive.py, resources.py | Polityka hostów, bramka i budżet zasobów |
| worker_network.py | Proxy QGIS przekazywane do procesów |

## Pomiary wydajności (1.2.0)

Pomiary są obserwacją istniejącego eksportu: nie zmieniają limitów, timeoutów,
algorytmu RAM, retry ani jakości PNG. Wykorzystują standardową bibliotekę Pythona,
natywne liczniki systemu i istniejące sygnały QGIS, bez nowych zależności, dodatkowych
zapytań do źródeł czy testowego ruchu sieciowego. `diagnostyka.jsonl` od 1.2.0 zawiera
zwykle wystarczający kontekst do analizy wydajności. Manifest pozostaje potrzebny
do nazw warstw i szczegółowego odbioru kompletności, a cały folder do kontynuacji
oraz sprawdzenia rzeczywistych danych.

| Zdarzenie | Zakres |
| --- | --- |
| `performance_configuration` | Wersja pomiarów, rola procesu, okres próbkowania i wersja/architektura systemu. |
| `performance_sample` | Własny czas CPU, RSS/peak, I/O, faza i czas próbki; w głównym QGIS także CPU całego systemu, RAM i wolne miejsce na docelowym woluminie. |
| `performance_phase` | Czas rzeczywisty i własny CPU zakończonego etapu, np. przygotowania, renderowania, scalania, zasobów lub sum kontrolnych. |
| `scheduler_sample` | Budżet i sufit CPU, liczba procesów oraz zadań kafelkowych, kolejka i gotowe wyniki do scalenia; dostępny RAM, rezerwa, estymata i zapas wzrostu procesów. |
| `archive_plan` | Liczba i techniczne identyfikatory warstw, dostawcy, użycie poprzednich wyników, CRS oraz rozmiar i złożoność obszaru bez współrzędnych. |
| `layer_summary` | Końcowy status, metoda, liczba obiektów/kafelków, wyniki zoomów, naprawy oraz czasy faz danej warstwy. |
| `network_interval` | Obserwowane rozpoczęcia, odpowiedzi, oczekujące żądania, błędy, timeouty, przedziały czasu odpowiedzi i liczniki bajtów według hosta i kontekstu. |

`PerformanceDiagnostics` uruchamia w każdym procesie własny wątek Pythona.
Wątek co około 5 s odczytuje wyłącznie natywne liczniki i zapisuje zwykły JSON;
nie dotyka żywych obiektów Qt/QGIS. Działa także podczas oczekiwania głównego wątku
na sieć lub zapis. Pierwsza i ostatnia próbka obejmują krótkie procesy.
`performance_counters(include_system=False)` w procesach map pomija powtarzanie
pomiarów całego systemu. Wyjątek pomiaru jest diagnostyczny i nie zatrzymuje eksportu.
Logi procesów map są dołączane do głównego logu po ich zakończeniu; nie stanowią
strumienia ze wszystkich jeszcze działających procesów.

`process_cpu_percent_one_core` wynika z przyrostu `time.process_time()` i czasu
monotonicznego: 100% oznacza jeden zajęty procesor logiczny, więc wartość może
przekraczać 100%. Pomiar obejmuje wszystkie wątki własnego procesu, bez potomków;
w głównym QGIS również inne działające w nim zadania. `system_cpu_percent` ma
zakres 0–100% dla mierzonego zakresu CPU. Linux odczytuje `/proc/stat`, pomija
podwójne doliczenie guest/guest_nice, a idle obejmuje też I/O wait raportowany
oddzielnie. Windows używa [GetSystemTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getsystemtimes):
kernel zawiera już idle, a powyżej
64 procesorów logicznych API mierzy bieżącą grupę procesorów, co opisuje `scope`.
Nie jest to pomiar częstotliwości, temperatury ani ograniczenia mocy CPU.

RSS/peak korzystają z istniejącego `process_memory()`. Dodatkowe dane o RAM
pochodzą z `/proc/meminfo` albo `GlobalMemoryStatusEx`; wspólny odczyt zachowuje
semantykę `available_memory()`. Windows `process_commit_limit_bytes` i
`process_commit_available_bytes` opisują commit ograniczony możliwościami bieżącego
procesu, **nie rozmiar pliku wymiany**, zgodnie z [MEMORYSTATUSEX](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex).
Odczyty niedostępne mają `null`, a nie zero.
Stałe typy struktur ctypes umożliwiają równoczesny odczyt samplera i koordynatora.

`process_io` podaje źródło i zakres licznika. Linux `read_bytes`/`write_bytes`
opisują operacje na poziomie warstwy składowania, natomiast `rchar`/`wchar`
obejmują również cache i inne odczyty/zapisy. Linux dodaje I/O odebranych przez
`wait` procesów potomnych do rodzica (`process_and_reaped_children`): nie sumuj
wprost main + worker, bo policzysz część danych ponownie. Windows
`GetProcessIoCounters` dotyczy własnego procesu (`process_only`) i wszystkich
transferów I/O, nie tylko dysku, zgodnie z [dokumentacją API](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getprocessiocounters).
Liczniki nie mierzą procentowej zajętości
fizycznego dysku ani przepustowości całego łącza.

Próbka koordynatora powstaje przy okresowym przeliczeniu budżetu, także gdy limit
się nie zmienił. `jobs` rozdziela running/waiting/done, gotowość do napraw i wiek
telemetrii; pozwala odróżnić brak próbki od aktualnego oczekiwania. `hosts` zawiera
limit, aktywność, kolejkę, szybkość, przerwę, stan zamrożenia, ostatnią zmianę
polityki i stan okna pomiarowego. Pełna historia zmian nadal jest w podsumowaniu
adaptacji. Liczba procesów i liczba operacji kafelkowych nadal nie oznaczają
liczby faktycznie równoczesnych żądań HTTP.

`network_interval` opróżnia liczniki po upływie 5 s przy kolejnym wywołaniu postępu,
a także przy zapełnieniu bufora grup i na końcu obserwacji. Bez postępu odstęp może być dłuższy;
`interval_seconds` podaje rzeczywisty okres. Obserwacja pozostaje w wątku QGIS.
`observed_body_bytes` oznacza dostępne bajty treści odpowiedzi;
`declared_content_length_bytes` to osobna suma deklaracji nagłówka.
Nie wolno ich dodawać ani uznawać za pomiar bajtów na łączu. Liczniki dostępności,
cache i nieznanego cache pokazują pokrycie obserwacji. Czasy obejmują wyłącznie
odpowiedzi skorelowane z rozpoczęciem żądania. Nowe interwały nie zastępują
dotychczasowych końcowych podsumowań sieci.

Plik pozostaje lokalny i nie jest automatycznie wysyłany. Nowe zdarzenia używają
indeksów/technicznych nazw zadań oraz nazw hostów, bez nazw warstw, pełnych URL,
parametrów zapytań, haseł, treści odpowiedzi i współrzędnych obszaru. Większy log
można ręcznie skompresować do ZIP-a. Do pełnej analizy używaj logu po zakończeniu
lub świadomym anulowaniu, gdy zostały zebrane logi procesów i podsumowania.

## Diagnostyka 0.9.1

`diagnostics.py` zapisuje strukturalny JSONL bez dodatkowych zależności. Główny
proces zapisuje plik obok katalogu roboczego i przenosi go do końcowego archiwum.
Przy wyjątku plik pozostaje poza usuwanym stagingiem. Procesy mają prywatne logi;
nadzorca zbiera je po zakończeniu procesu przed usunięciem katalogu mapy.
Nie ma równoległego zapisu wielu procesów do wspólnego pliku. Wątki nadzorcy
używają blokady. Błąd zapisu logu nie może zatrzymać sprzątania ani koordynatora.

Wyjątki: typ, errno/winerror, nazwy plików kodu, funkcje i numery linii; bez
wiadomości, źródłowych linii kodu, ścieżek użytkownika i zmiennych lokalnych.
Sieć: konfiguracja proxy bez adresów i poświadczeń, żądania uwierzytelnienia,
kody błędów Qt/HTTP. Nie deklarujemy obserwacji rzeczywistej trasy każdego żądania.
Główne zdarzenia warstw odnoszą się do numeru wybranej warstwy; procesy do
technicznej nazwy tabeli. Log jest dopisywany do końca, nie należy do sha256
manifestu. Nie przechwytujemy surowego stderr GDAL/QGIS ze względu na dane źródeł.

## Blokady plików Windows (0.9.2)

`write_state` zachowuje zapis do `.new` i atomową podmianę. Dla Windows
winerror 5/32/33 ponawia wyłącznie podmianę: maksymalnie sześć prób i łącznie
250 ms oczekiwania (10/20/40/80/100 ms). Poprzedni kompletny JSON zostaje
nienaruszony, aż podmiana się powiedzie; brak nieatomowego nadpisywania.
Sprawdzanie anulowania otacza przerwy. Zamykająca telemetria może być zapisana
również po anulowaniu. Pozostałe błędy systemowe nie są ponawiane.

Ta sama funkcja obsługuje polecenia, telemetrię i postęp procesu. Ponowienie
publikacji nie powtarza operacji pobierania ani nie zwiększa liczników kafelków.
Dzierżawa pozwolenia nadal wygasa po dwóch sekundach. Trwała blokada zatrzymuje
koordynator; nie uruchamiamy pobierania bez kontroli. Kolejka anulowana w wyniku
awarii otrzymuje WorkerError z etapem `coordinator`, widoczny również na czerwono
w oknie. Zwykłe anulowanie podczas ponowienia nie oznacza awarii koordynatora.
Diagnostyka zapisuje kody błędów i wyniki ponowień, bez pełnych ścieżek.

## Obserwacja sieci i odczytu (0.9.3)

NetworkDiagnostics używa sygnałów QgsNetworkAccessManager:
requestAboutToBeCreated(QgsNetworkRequestParameters) i finished(QgsNetworkReplyContent).
Nie przechwytuje żądań ani nie zmienia proxy. Dopasowuje identyfikatory do czasu
startu i bieżącego kontekstu; limit pamięci oczekujących identyfikatorów to 4096.
Odpowiedzi grupuje po kontekście, hoście, operacji i bezpiecznych metadanych;
zapisuje pierwsze trzy przykłady, a przy zamknięciu pełne sumy i czasy.
Brak powiązanego startu daje seconds/context=null. Błąd obserwatora jest logowany,
a nie propagowany z Qt callback do pętli zdarzeń. Proces ma własnego obserwatora;
QGIS przekazuje zdarzenia menedżerów wątków przez swoje sygnały.

XML analizowany jest tylko w dostępnym prefiksie 16 KiB; persystujemy wyłącznie
rozpoznane kody OGC i liczniki numeryczne FeatureCollection. Żadnych wiadomości
ExceptionText ani nagłówków autoryzacji. Zwracane body_available=false i brak
licznika nie dowodzą pustego źródła. Dla POST rodzaj operacji/CRS mogą pozostać
nierozpoznane; nie analizujemy treści zapytania. To diagnostyka, nie walidator
kompletności WFS. Nie traktuj kontekstu warstwy w GUI jako dowodu pochodzenia
każdego żądania, jeśli inne zadania QGIS pracują równocześnie.

_write_vector otrzymuje opcjonalną diagnostykę. Liczniki obiektów pochodzą
z istniejącej iteracji; dodatkowa kontrola pustego MSSQL od 1.4.0 została opisana
wyżej. Stan iteratora logujemy przed jego zamknięciem; read_complete opisuje odczyt,
a stage/writer_error osobno zapis.

## Kolejka, pamięć i timeouty (0.9.4)

`_ready_records` wybiera gotowe future lub warstwę obsługiwaną w głównym QGIS,
bez blokowania za pierwszą niedokończoną mapą. Kolejność listy manifestu i drzewa
pozostaje oryginalna; diagnostyczny layer_index jest stałym indeksem zaznaczenia.
Po anulowaniu kończą się nadzorcy aktywnych procesów, a gotowe wyniki są scalane.
`take(preserve_completed=True)` kończy scalenie ukończonej mapy mimo anulowania.
Nie wznawia pobierania. GeoPackage nadal ma jednego zapisującego w danej chwili.

Pula wątków nadzorujących może obsłużyć min(32, 2×CPU); faktyczne procesy
ogranicza globalny licznik active_hosts i aktualny budżet RAM. Co pięć sekund
budżet przeliczany jest przez recommend na podstawie bieżącego wolnego RAM,
z rezerwą 768 MiB. Od 0.9.7 estymata dodatkowego procesu pochodzi z pomiaru,
z zapasem wzrostu, zgodnie z regułą opisaną wyżej. Budżet może spaść
poniżej liczby istniejących procesów (np. nieznany RAM); blokowane są nowe starty.
Manifest zachowuje workers jako limit początkowy, dodaje peak_worker_budget oraz
final_worker_budget. Historia RAM i wiersze GUI pokazują kolejne limity.

Izolowane projekty procesów powstają z szablonu, z którego ciężkie definicje
warstw usunięto raz. Kopiowana jest tylko definicja potrzebnej warstwy. Ogranicza
to kwadratowy koszt wcześniejszego kopiowania całego projektu dla każdej mapy.
Przygotowanie regularnie obsługuje zdarzenia Qt i anulowanie.

Renderer koreluje natywny requestTimedOut QGIS z identyfikatorem żądania.
OperationCanceledError nie jest sam w sobie dowodem timeoutu. Przekierowania
śledzimy przez originatingThreadId renderera po pierwszym żądaniu źródła.
Timeout trafia do istniejących przerw/napraw zamiast natychmiastowych powtórzeń
oraz podziałów. Diagnostyka zapisuje timeouty i poprawnie dekoduje CRS z URL.
Postęp to licznik zakończonych fragmentów/całość, a nie kolumna/wiersz.

raw_empty/raw_nonempty opisują wyrenderowany obraz przed maską obszaru,
masked_out — utratę całej treści przez maskę. Nie są analizą samych odpowiedzi
HTTP PNG. timing_seconds mierzy fazy oczekiwania/renderowania/maski/zapisu;
nie stanowi pełnego profilu CPU ani całkowitego czasu mapy. Nie zmieniono
kompresji PNG, jakości, reguł pustych map ani formatu GeoPackage.

## Powrót hosta i przydział między serwerami (0.9.5)

`WorkerGate.before` zgłasza gotowość dowolnego rzeczywiście brakującego kafelka,
również z zerową liczbą prób. Brak gotowego fragmentu podczas przygotowania
rejestru lub kończenia mapy nie jest powodem odłożenia hosta. Po przerwie
koordynator dopuszcza jedną próbę; scheduler może uruchomić kolejną mapę,
jeżeli host nie ma już aktywnego procesu. Terminy Retry-After, trzy nieudane
powroty, ack błędów/prób i wygasające pozwolenia pozostają obowiązujące.
W trybie adaptacyjnym każdy błąd renderowania wraca bezpośrednio do rejestru:
nie ma dodatkowych wewnętrznych retry/subdivision poza trzema próbami kafelka.

0.9.5 wprowadziła sufit dwóch map na host; 0.9.6 zastępuje go limitem CPU
i zasobów opisanym wyżej. Przy przydzielaniu wolnego procesu
wybierany jest kwalifikujący się host z najmniejszą liczbą aktywnych procesów;
przy remisie zachowana jest kolejność kolejki. Hosty czekające na termin przerwy
nie kwalifikują się. Wszystkie uruchomione procesy, również czekające, nadal
liczą się do globalnego budżetu RAM. `create_archive(adaptive=False)` zachowuje
parametr stałego limitu oraz kolejność wyboru jak wcześniej.

Nie zmieniono interwału koordynatora 0,5 s. Zwykły sukces już nie wymaga ack
przed kolejnym kafelkiem; potwierdzenia wymagają błędy i próby powrotu. Szybsze
odświeżanie zwiększyłoby operacje IPC bez usunięcia głównego kosztu renderowania.

## Odmowa proxy (0.9.6)

HTTP 407 kończy pobieranie bieżącej mapy po pierwszej odmowie. Nie odpytujemy
pozostałych kafelków i zoomów przy odrzuconym uwierzytelnianiu proxy. Zachowane
PNG dają wynik partial; bez nich mapa ma status failed. Raport wskazuje proxy,
`stop_http_status=407` i `stopped_early=true`; nie jest to odłożenie całego hosta.
Pozostałe kody, w tym 403/404 pojedynczego kafelka, zachowują poprzednie reguły.

## Zgodność QGIS 3 i 4

Importy Qt przechodzą przez `qgis.PyQt`; enumy mają pełne nazwy wspólne dla
Qt5/Qt6. `QAction` pochodzi z QtGui, okna używają `exec()`. Wstępny sygnał
obecności sieci pochodzi z aktywnych interfejsów QNetworkInterface, bez
usuniętego w Qt6 QNetworkConfigurationManager. To nie test dostępu do Internetu
lub VPN; rzeczywiste błędy usług nadal obsługuje mechanizm pobierania.

Qt5 i Qt6 serializują właściwości projektu w różnych strukturach XML. Obie
ścieżki usuwają makra z kopii dla procesów i wynikowego projektu, a wynik
ustawia względne ścieżki. Oryginalny projekt i jego makra pozostają niezmienione.
Kod błędu sieciowego w diagnostyce zachowuje postać liczby także dla enumów Qt6.

QGIS 4 używa kluczy proxy o nazwach z myślnikami. `worker_network` wykrywa
natywny węzeł QgsSettingsTree i mapuje klucze profilu na niezmieniony protokół
przekazywany w stdin. QGIS 3.40 zachowuje stare klucze. Testy sprawdzają
rzeczywiste żądania przez proxy, wyjątki adresów, logowanie, HTTP 407 i brak
poświadczeń w plikach końcowych.

## Zabezpieczenie XML i zapytań po kontroli katalogu

Kopie QGS, XML warstw, SVG i UI czyta prywatna kopia frontendu ElementTree
z defusedxml 0.7.1. Parser zabrania deklaracji encji i odwołań zewnętrznych;
zwykły DOCTYPE QGIS pozostaje obsługiwany. Bez globalnego monkey patchingu.
Styl jest sprawdzany przed dotychczasową kanonizacją, dzięki czemu nie zmieniają
się fingerprinty poprawnych źródeł i zgodność wznowienia. Odrzucony SVG/UI
jest usuwany z kopii i z jej odwołań, z uwagą w raporcie; źródło pozostaje.

SQL SQLite używa QgsSqliteUtils.quotedIdentifier dla nazw oraz parametrów
dla wartości. Kontrola MSSQL zachowuje cytowane nawiasami identyfikatory
i istniejący filtr SQL z dostawcy QGIS. Proces uruchamia się absolutną ścieżką
interpretera, listą argumentów i shell=False; ścieżki symlinków venv nie są
rozwijane. Poświadczenia nadal tylko przez stdin. Uzasadnienia punktowych
adnotacji skanera: [raport naprawy](security-scan-fix.md).
