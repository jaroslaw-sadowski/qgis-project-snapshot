# Działanie i ograniczenia archiwizacji (0.9.0)

Jedna akcja **Archiwizuj projekt…** tworzy osobny katalog projektu z lokalnymi
danymi, raportem HTML i manifestem JSON. Nie zastępuje oryginału. Techniczny
identyfikator `mbtiles_batch_exporter` pozostaje dla aktualizacji istniejących
instalacji; dawny eksporter, jego okno i pomocniczy moduł zostały usunięte.

## Dane i odtworzenie projektu

- Wektory: geometrie i atrybuty w osobnych tabelach jednego `dane.gpkg`,
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

## Procesy i automat

API `create_archive(..., adaptive=False)` zachowuje zgodny tryb stały. Okno używa
wyłącznie `adaptive=True`. Procesy map mają własne QGIS; do wątków nadzorujących
nie przekazujemy obiektów QGIS. Końcowy GeoPackage ma jednego zapisującego.
Wektory, MSSQL, rastry źródłowe i usługi z authcfg pozostają w głównym QGIS.
Mapy z głównej ścieżki korzystają ze wspólnej bramki hosta.

Start: jedno zadanie mapowe na host, niezależnie od ścieżek usług. Wzrost o jeden
wymaga 15 s, 10 poprawnych kafelków, kolejki i wolnego budżetu. Dwa kolejne okna
bez 10% poprawy przepustowości cofają limit i blokują wzrost. Sufit osiem map/host.
HTTP 429/503 i trzy kolejne timeouty zmniejszają obciążenie oraz blokują wzrost.
503 oznacza możliwe przeciążenie lub niedostępność, nie dowód jednej przyczyny.

Przerwy: Retry-After w sekundach lub dacie HTTP, inaczej 30/60/120 s. Po przerwie
jedna próba rzeczywiście brakującego kafelka; jej sukces odblokowuje host.
Trzy nieudane próby powrotu, brak kafelków dopuszczonych do ponowienia albo
wymagane oczekiwanie ponad pięć minut odkładają pozostałe dane. Inne hosty pracują.

Limit globalny: min(32, 2 × CPU, dostępny RAM po rezerwie 2 GiB przy 1 GiB/proces),
co najmniej jeden; nieznany RAM ogranicza do dwóch. RAM sprawdzany co pięć sekund;
spadek poniżej rezerwy blokuje wzrost i nowe procesy. Czekające procesy też liczą
się do pamięci. Dziennik i manifest zapisują zasoby wykryte przy starcie.
To heurystyka zadań mapowych, nie dokładny limit HTTP/s ani pomiar przepustowości.

Koordynator co 0,5 s czyta atomowe statystyki i zapisuje polecenia protokołu 1:
generacja, pozwolenie, przerwa/próba powrotu, potwierdzenie zdarzeń i ważność 2 s.
Bramka sprawdza zgodę przed operacją renderowania i ponowieniem; oczekiwanie
obsługuje anulowanie. Brak łączności z koordynatorem odkłada mapę.

Dyskowy rejestr SQLite zapisuje wynik i liczbę prób każdego kafelka, także poprawnie
przezroczystego. Najwyżej trzy podejścia (początkowe + dwie rundy uzupełniania),
bez ponownego pobierania sukcesów i odtwarzania tabeli. Przy przeciążeniu lub timeout
pomijane są natychmiastowe ponowienia i podziały. HTTP 401/403/404/407 nie są ponawiane.
Mapę scala się po zakończeniu pobierania/naprawy; gotowe PNG są kopiowane bez rekompresji.

Anulowanie zachowuje ukończone, scalone warstwy, a nieukończone katalogi usuwa.
Nieodpowiadające procesy są kończone po pięciu sekundach od anulowania.
Brak wznawiania po zamknięciu QGIS i uczenia limitów między eksportami.

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
jest pakowany. Końcowy ekran zaznacza failed/cancelled/empty/partial; ręczne
ponowienie tworzy nowe archiwum wybranych warstw. Automatyczna naprawa kafelków
dotyczy bieżącego eksportu. Raport HTML zawiera manifest 4, w tym historię automatu,
diagnozy i do 20 przykładów błędów kafelków na mapę.

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
