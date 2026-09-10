# Działanie i ograniczenia archiwizacji (1.0.0)

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
bez 10% poprawy przepustowości cofają limit i blokują wzrost. Pomiar wymaga
15 s pomiaru z docelową liczbą gotowych map. Przerwy na rozruch kolejnej mapy
są wyłączane z czasu i liczby sukcesów, lecz nie kasują wcześniejszych próbek.
Gotowy proces między publikacją wyniku kafelka a zgodą na następny pozostaje
gotowy do pomiaru. Rozruch i kończąca się kolejka nie świadczą o suficie serwera. Sufit hosta to min(32, 2 × CPU), dodatkowo
ograniczany wspólnym budżetem RAM i liczbą map.
HTTP 429/503 i trzy kolejne timeouty zmniejszają obciążenie oraz blokują wzrost.
503 oznacza możliwe przeciążenie lub niedostępność, nie dowód jednej przyczyny.

Przerwy: Retry-After w sekundach lub dacie HTTP, inaczej 30/60/120 s. Po przerwie
jedna próba rzeczywiście brakującego kafelka; jej sukces odblokowuje host.
Trzy nieudane próby powrotu, brak kafelków dopuszczonych do ponowienia albo
wymagane oczekiwanie ponad pięć minut odkładają pozostałe dane. Inne hosty pracują.

Limit globalny: min(32, 2 × CPU, budżet RAM), co najmniej jeden; nieznany dostępny
RAM ogranicza do dwóch. Po renderowaniu każdy proces publikuje bieżący i szczytowy
RSS z natywnego systemu, co 5 s i przy zamknięciu. Koszt następnego procesu E to
max(384 MiB, 1,5 × największy szczyt z tego eksportu), początkowo 1 GiB. Główny
QGIS z local_gate nie uczestniczy w tym pomiarze; jego zużycie jest w MemAvailable.

Od dostępnej pamięci odejmujemy 768 MiB rezerwy i zapas wzrostu każdego aktywnego
procesu max(0, E − bieżący RSS). Nieznany RSS zachowuje pełną rezerwację startową,
co najmniej E. Pozostała pamięć daje miejsca dla nowych procesów po E bajtów.
Zachowujemy największy peak również po końcu procesu. Zwolniony RSS może być
ponownie potrzebny; samo jego obniżenie nie usuwa rezerwy na wzrost.

Telemetria poprzedza próbkę RAM. `launch_slots` wyznacza skończony przydział startów
na podstawie próbki co 5 s. Zakończenie mapy nie odnawia przydziału. Spadek poniżej
rezerwy blokuje nowe procesy i wzrost, nie przerywa działających map. Przerwy
serwerów także liczą się do aktywnych procesów. GUI pokazuje estymatę i rezerwę;
historia pamięci oraz manifest zapisują też szczyt i zapas wzrostu. To heurystyka; nagły wzrost zużycia pamięci
może przekroczyć zapas. Nie jest to gwarancja maksimum przepustowości ani RAM.

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

_write_vector otrzymuje opcjonalną diagnostykę. Liczniki pochodzą z istniejącej
iteracji, bez dodatkowego odczytu źródła. Stan iteratora logujemy przed jego
zamknięciem; read_complete opisuje odczyt, a stage/writer_error osobno zapis.

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
