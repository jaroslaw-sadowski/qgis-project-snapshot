# Działanie i ograniczenia archiwizacji (0.6.0)

Nowa akcja **Archiwizuj projekt…** w menu wtyczki zapisuje **archiwum częściowe**:

- drzewo wyboru odtwarza grupy i kolejność, domyślnie zaznaczając wszystkie warstwy;
- obszar to widok mapy lub kształt poligonów (zaznaczonych, a przy braku zaznaczenia — wszystkich);
- wektory są zapisywane z atrybutami do oddzielnych tabel jednego `dane.gpkg`;
- zachowywane są całe obiekty przecinające obszar, filtry i niezapisane edycje;
- nowy projekt `.qgz` zachowuje ID warstw, grupy, kolejność, widoczność i style;
- raport HTML oraz manifest JSON opisują wyniki, braki, obszar, czas pobierania i sumy kontrolne;
- kolejne archiwum nie nadpisuje poprzedniego; przerwanie zachowuje ukończone warstwy;
- kopia powstaje w katalogu tymczasowym i jest udostępniana po kontroli zapisu.

**Krok 2 dodaje zapis obrazów WMS/WMTS/XYZ, ArcGIS i innych warstw renderowanych
przez QGIS**, w tym kafelków wektorowych:

- każda mapa jest osobną tabelą rastra w tym samym `dane.gpkg`; warstwy można
  nadal niezależnie włączać i wyłączać;
- rastry mapowe używają CRS projektu, m.in. EPSG:2180;
- wybierasz zoom minimalny i maksymalny (domyślnie 13–17); przy każdej pozycji
  widać przybliżoną skalę przy 96 DPI i rozdzielczość dla środka obszaru;
- każdy zoom jest osobno renderowany, aby zachować treść zależną od skali;
- PNG zachowuje pełny kanał alfa i kolory, z `ZLEVEL=9` przy każdym zapisie;
  nie stosujemy JPEG, redukcji palety ani automatycznego obniżania jakości;
- pobierane są kafelki 256 × 256 przecinające kształt obszaru, z niewielkim
  marginesem renderowania; maska uwzględnia również dziury w poligonach;
- całkowicie przezroczyste kafelki nie zajmują miejsca w tabeli;
- siatka jest przeszukiwana przestrzennie, bez skanowania całego prostokąta
  długiego, ukośnego pasa i bez przechowywania całego obrazu w pamięci;
- raster GDAL (np. plik na udziale sieciowym) jest najpierw zapisywany z
  oryginalnymi wartościami i maską w bezstratnym GeoTIFF w `zasoby/`;
- jeśli eksport danych się nie powiedzie, próbujemy zachować obraz. Dotyczy to
  także wektorów z niezapisanymi edycjami; raport informuje o utracie atrybutów;
- przy zgłoszonym błędzie pobierania wykonujemy dwa ponowienia, potem próbę
  mniejszych fragmentów. Po pięciu kolejnych nieudanych kafelkach kończymy
  próby dla warstwy, aby nie powtarzać bez końca zapytań do niedostępnej usługi.

Puste zoomy otrzymują status „do sprawdzenia”, a obraz z brakującymi fragmentami
jest oznaczony jako częściowy. Jeśli nie udało się pobrać żadnego obrazu, warstwa
jest pomijana. Raport HTML podaje wyniki, a `manifest.json` zawiera dodatkowo
liczby kafelków dla każdego zoomu, ponowienia i do 20 przykładów błędnych fragmentów.
Odznaczone lub niedostępne warstwy nie pozostają aktywnymi źródłami w kopii.

**Krok 3 kopiuje lokalne symbole SVG, obrazy symboli, formularze UI i pliki pól
załączników** do `zasoby/`, przepisując ścieżki w projekcie i lokalnych danych.
Sprawdza odwołania do obrazów wewnątrz SVG/UI, zachowuje bazę stylów i załączniki
osadzone w QGZ. Zachowuje relacje pomiędzy zapisanymi wektorami, usuwa relacje
prowadzące do pominiętych warstw i zastępuje niedziałające pola relacyjne zwykłym
odczytem wartości. Otwiera ponownie lokalne warstwy przez rzeczywistych dostawców QGIS.

Zasoby internetowe, brakujące pliki, dynamiczne wyrażenia, kod formularzy,
akcje i złożone zależności są wskazywane w raporcie. Zapis relacji nie dodaje
automatycznie obiektów spoza wskazanego obszaru. Fonty systemowe, zewnętrzne
biblioteki formularzy, dowolny kod Python i wszystkie możliwe zależności QGIS
nie są automatycznie pakowane. Wynik nadal wymaga odbioru offline; raport
nie deklaruje pełnej samodzielności na podstawie samego poprawnego zapisu.
Obraz zachowuje wygląd dla wybranego obszaru i zoomów, a nie dowolnego późniejszego
powiększenia. Usługa może zwrócić pustą lub niepełną mapę bez zgłoszenia błędu;
w takich przypadkach potrzebne jest również porównanie wizualne.

## Równoległe pobieranie i CPU

Od 0.8.0 okno korzysta z automatu opisanego poniżej. Stałe limity 1–32 procesy
i 1–8 na host pozostają dostępne przez API dla zgodności wcześniejszych wywołań.
Mapy usług są pobierane i kompresowane równolegle w osobnych procesach QGIS,
które mogą używać różnych rdzeni. Wątki Pythona nadzorują procesy; nie dotykają
warstw ani projektu otwartego w interfejsie. Kolejka wybiera wolne serwery i ogranicza
liczbę procesów dla jednego hosta, domyślnie do dwóch (opcjonalnie do ośmiu). Limit dotyczy zadań warstw, nie
wewnętrznych połączeń HTTP poszczególnych dostawców QGIS.

Każdy proces zapisuje własny tymczasowy GeoPackage. Główny proces scala gotowe
tabele, kopiując skompresowane PNG bez ponownego renderowania czy utraty jakości.
Tylko jeden proces zapisuje końcowy `dane.gpkg`. Liczba procesów ogranicza zużycie
RAM, ale pliki tymczasowe wymagają dodatkowego miejsca na dysku. Dla małych
projektów uruchamianie procesów może być wolniejsze; wtedy wybierz 1.

Wektory (w tym niezapisane edycje), oryginalne rastry GDAL i usługi używające
`authcfg` pozostają w głównym QGIS. Gdy proces pomocniczy nie działa w danym
środowisku, eksport próbuje ponownie w głównym QGIS i odnotowuje to w raporcie.
Procesy wymagają interpretera Python z modułami QGIS; wdrożenie i testy wykonano
na Ubuntu z QGIS 3.40. Inne systemy wymagają osobnego sprawdzenia.

Anulowanie wysyła sygnał do procesów, a po 5 sekundach kończy nieodpowiadające
procesy pomocnicze. Niepełne pliki prywatne są usuwane; ukończone, scalone warstwy
zostają zachowane. Natywny odczyt wektorów w głównym QGIS nadal może opóźnić
reakcję na anulowanie. Próbę renderowania ograniczamy do 60 sekund.

Przenoś cały folder `Nazwa_archive_YYYYMMDD`, a projekt otwieraj przez `.qgz`.
Zapisane tabele wektorowe nie wymagają naszej wtyczki ani połączenia ze źródłem.
Daty raportu oznaczają czas pobierania poszczególnych warstw, nie jednoczesny stan
wszystkich zewnętrznych źródeł.


## Postęp i komunikaty

Okno pokazuje liczbę zakończonych warstw, stan każdej pozycji, upływ czasu i
ostatnie 2000 komunikatów. Licznik nie jest prognozą pozostałego czasu; końcowa
kontrola plików ma osobny etap. Błąd i anulowanie mają odrębne komunikaty końcowe.
Dziennik można skopiować do schowka; pełne wyniki warstw pozostają w raporcie.

Backend zachowuje tekstowy callback `progress` i dodatkowo przekazuje `layer_status`
(zakończone/łącznie i rekord warstwy) oraz `worker_activity` (stany procesów).
Proces pomocniczy zapisuje atomowo ostatni komunikat w prywatnym `progress.json`,
nie częściej niż co 250 ms. Główny QGIS odczytuje stany do dwóch razy na sekundę;
GUI pomija powtórzenia. Komunikaty nie zawierają łańcuchów połączeń ani treści błędów
pochodzących bezpośrednio od dostawców. Nazwy warstw nadal mogą być danymi firmowymi.

Renderowanie zgłasza oczekiwanie co 5 sekund, jeśli pętla zadania QGIS może działać.
Synchroniczny odczyt dostawcy w głównym wątku nadal może czasowo blokować interfejs;
wyświetlona pozostaje ostatnia konkretna czynność. Postęp nie oznacza, że cały
backend został przeniesiony do wątków.

## Moduły

| Plik w `mbtiles_batch_exporter/` | Odpowiedzialność |
|---|---|
| `plugin.py`, `__init__.py` | Rejestracja wtyczki i obu akcji QGIS |
| `archive_dialog.py` | Opcje archiwizacji, postęp i anulowanie |
| `archive.py` | Eksport wektorów, kopia projektu, raport i manifest |
| `raster_archive.py` | Renderowanie PNG i zachowanie danych rastrów |
| `parallel_archive.py` | Kolejka, nadzór procesów i scalanie GeoPackage |
| `archive_worker.py` | Punkt wejścia osobnego procesu QGIS |
| `archive_resources.py` | Zasoby projektu, relacje i kontrola lokalnych źródeł |
| `dialog.py`, `utils.py` | Dotychczasowy eksporter MBTiles |

## Wersja 0.7: język, ponowienie, dobór zasobów

`i18n.py` wybiera język przez QgsSettings (`locale/overrideFlag`, `locale/userLocale`),
a następnie QLocale. Katalog Qt `en.ts` jest kompilowany do `en.qm`; oba są pakowane.
Szablony tłumaczone są przed interpolacją nazw warstw i innych wartości. Procesy
otrzymują wybrany język w `QGIS_SNAPSHOT_LANGUAGE`. Kody statusów i nazwy plików
pozostają stałe. Komunikaty dostawców QGIS/GDAL mogą zależeć od ich własnego języka.

`resources.py` używa dostępnych CPU (z ograniczeniem affinity), MemAvailable na
Linuksie i GlobalMemoryStatusEx na Windows. Nieznany RAM ogranicza rekomendację
do 2 procesów. Limit: minimum z 32, 2 × CPU, budżetu RAM po rezerwie 2 GiB
(1 GiB/proces) i liczby map dopuszczonych przez limit na serwer. Brak potwierdzonego
połączenia ogranicza sugestię do 2. To heurystyka, nie gwarancja użycia pamięci
ani pomiar przepustowości. Windows nie odebrano na rzeczywistym stanowisku.

Kolejka wybiera następne zadanie z serwera mającego wolny limit. Zadania czekające
na zajęty host nie zajmują procesów. Limit backendu wynosi 1–32 procesy i 1–8 na
serwer; interfejs udostępnia na serwer 1/2/4/6/8. Domyślny limit nadal wynosi 2.
Scalanie końcowego GeoPackage ma jednego zapisującego.

Panel wyniku przewija wszystkie problematyczne rekordy i zaznacza wyłącznie statusy
failed/cancelled/empty/partial. Ponowienie używa zwykłego eksportu wybranych warstw
w nowym folderze. Nie naprawia wcześniejszego archiwum w miejscu. HTML raportu
zawiera cały manifest, w tym istniejący limit 20 przykładów błędów kafelków na mapę.

## Wersja 0.7.1: model kosztu pojedynczej mapy

`ArchiveDialog._update_zoom_labels` przelicza istniejącą liczbę kafelków przez
jawne założenia 0,2–2 s/kafelek oraz 10–250 KiB/kafelek PNG. Formatuje czas
w sekundach/minutach/godzinach, rozmiar w MiB/GiB. Nie odpytuje serwera i nie
zmienia eksportu; nie jest prognozą pozostałego czasu ani wielkości całego projektu.
Podpowiedź opisuje brak pomiaru, wpływ maski/ponowień i wyłączenia z szacunku.

## Wersja 0.7.2: sygnały przeciążenia

Istniejący obserwator QgsNetworkAccessManager w `_render_image` rozpoznaje HTTP
429 i 503 dla żądań bieżącego źródła. Emituje komunikat z trwałym prefiksem
`[HTTP 429]` / `[HTTP 503]`, nazwą hosta (bez URL/poświadczeń) i przetłumaczoną
instrukcją. 503 oznacza możliwość przeciążenia, nie diagnozę jego przyczyny.

Proces zachowuje ostrzeżenia oddzielnie od ostatniego komunikatu w progress.json;
nie są pomijane przez ograniczanie częstotliwości aktualizacji. Kolejka przekazuje
je również dla ukończonych procesów. UI odczytuje je przed filtrowaniem ukończonych
warstw i ponownie z końcowego rekordu. Czerwona etykieta pozostaje do nowego eksportu.
`raster.server_warnings` zachowuje diagnostykę w manifeście i HTML. Przy 429
zatrzymujemy bieżącą mapę na pierwszym błędnym kafelku, bez ponowień/podziałów.
Pozostałe zadania nie są automatycznie pauzowane. Przy 503 zachowujemy dotychczasowe
ponowienia, ponieważ przyczyna może być inna niż obciążenie.

Nie dodano limitera HTTP na sekundę. Istniejący osobny parametr `per_server_limit`
pozostaje limitem równoległych map; wykrywanie dotyczy obserwowanych żądań renderera
map, nie dowolnych błędów MSSQL, WFS, uwierzytelniania lub eksportera legacy.

## Wersja 0.8.0: automat i uzupełnianie kafelków

`adaptive.py` zawiera maszynę stanów HostPolicy i WorkerGate bez obiektów QGIS.
Koordynator w kolejce procesów co 0,5 s czyta atomowe telemetry.json i zapisuje
control.json (protokół 1, generacja, zgoda, próba powrotu, potwierdzenie zdarzeń,
ważność 2 s). Sukcesy są licznikami na generację; błędy i wyniki prób powrotu są
potwierdzanymi zdarzeniami. Brak aktualnego polecenia blokuje pobieranie; brak
łączności z koordynatorem przez 10 s odkłada mapę. Czekanie obsługuje anulowanie.

Polityka hosta startuje z limitem 1. Okno wymaga 15 s i 10 poprawnych kafelków.
Zwiększenie +1 wymaga kolejki i globalnego miejsca. Dwa okna bez poprawy szybkości
co najmniej 10% cofają limit i blokują wzrost. HTTP 429/503 lub trzy kolejne timeouty
cofają limit i rozpoczynają przerwę. Zdarzenia z poprzedniej generacji nie liczą się
jako kolejne nieudane próby powrotu; ich dłuższy Retry-After jest nadal respektowany.
Przerwy: nagłówek w sekundach/dacie HTTP albo 30/60/120 s. Jedna brakująca porcja
jest próbą powrotu. Trzy nieudane próby powrotu, wyczerpane kafelki do ponowienia
lub wymagane oczekiwanie >300 s odkładają host do następnego eksportu.

RAM jest odczytywany co 5 s. Poniżej 2 GiB dostępnej pamięci koordynator wstrzymuje
nowe procesy i wzrost; istniejące mogą kończyć pracę. Limit początkowy wynika z
minimum 32, 2 × CPU i (dostępny RAM − 2 GiB) / 1 GiB, co najmniej 1; nieznany RAM: 2.
Jednostka sterowania to proces/zadanie mapy, nie pojedyncze żądanie dostawcy QGIS.

W adaptacyjnym renderowaniu rejestr `<table>.tiles.sqlite` w prywatnym katalogu
zawiera współrzędne, status, liczbę prób i przyczynę błędu. Zapis PNG jest opróżniany
na dysk przed zatwierdzeniem sukcesu w rejestrze. Puste poprawne kafelki również
są rejestrowane. Maksymalnie trzy podejścia do kafelka; przy przeciążeniu lub timeout
pomijamy natychmiastowe ponowienia/podziały. Próba powrotu ma pierwszeństwo dla
bieżącego brakującego kafelka. Inne błędy używają dotychczasowego renderera i dwóch
rund uzupełniania. 401/403/404 są trwałe i nie są ponawiane.

Gotowe tabele są scalane raz przez jednego zapisującego. Procesy mapowe są izolowane;
źródła authcfg pozostają w głównym QGIS, korzystając z tej samej kontroli hosta.
Awaria procesu w trybie adaptacyjnym nie uruchamia niekontrolowanego zastępstwa
w głównym QGIS. Brak restart-resume; rejestry prywatne są sprzątane po eksporcie.

API: `create_archive(..., adaptive=False, server_activity=callback)` zachowuje
stały tryb domyślny; przy `adaptive=True` workers/per_server_limit zastępuje dobór
zasobów i sufit 8 na host. Okno używa tego trybu. `server_activity` otrzymuje wiersze
host/active/processes/budget/limit/queued/rate/state/pause/generation/successes. Manifest 4
zawiera tryb parallel oraz raport adaptive z historią limitów, pauz i zdarzeń pamięci;
raster zawiera liczby podejść naprawczych i uzupełnionych kafelków. Bez URL/poświadczeń.
