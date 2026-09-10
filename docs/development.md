# Rozwój, testy i przygotowanie paczki

Polecenia wykonuj z katalogu głównego repozytorium. Użyj interpretera z modułami
`qgis` i `osgeo` dostarczonymi z QGIS; zwykłe środowisko Pythona może ich nie mieć.
Zweryfikowano Ubuntu, QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4.

## Testy źródeł

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Testy używają rzeczywistych dostawców QGIS/GDAL i katalogów tymczasowych.
Lokalny WMS wymaga gniazd HTTP na `127.0.0.1`. Przy blokadzie sieci testy WMS
są pomijane; taki wynik nie jest pełnym odbiorem. W środowisku Codexa może być
konieczne uruchomienie polecenia z uprawnieniem do sieci lokalnej.

Konfiguracja Ruff jest w `pyproject.toml`: E/W (pycodestyle), F (Pyflakes),
I (importy), limit 88 znaków zgodny z formatowaniem Ruff. To jawna konwencja
projektu zamiast ścisłego limitu 79 znaków PEP 8. E402 pomijamy wyłącznie
w modułach testowych wymagających ustawienia środowiska przed importem QGIS.
Brak osobnego typecheckera. Wykonuj także `git diff --check` i kontrolę składni.

```bash
python3 -m venv /tmp/snapshot-audit-venv
/tmp/snapshot-audit-venv/bin/pip install ruff==0.16.6
/tmp/snapshot-audit-venv/bin/ruff check .
/tmp/snapshot-audit-venv/bin/ruff format --check .
```

Ruff jest narzędziem developerskim, nie zależnością instalowanej wtyczki. Nie uruchamiaj wielokrotnie pełnego
zestawu bez nowych zmian, błędów lub istotnego powodu do ponownej weryfikacji.

## Budowa ZIP-a

```bash
python3 scripts/build_plugin.py
```

Skrypt korzysta tylko ze standardowej biblioteki Pythona. Wersję odczytuje
z `mbtiles_batch_exporter/metadata.txt`; generuje ZIP i `.zip.sha256` w `dist/`.
Można podać inny katalog przez `--output`. ZIP ma jeden katalog wtyczki,
zawiera moduły Python, ikonę, metadane, README, GPL i instrukcję zespołową.
Nie zawiera repozytorium, testów, danych projektów ani plików dla agentów AI.

Przy tych samych źródłach i środowisku ZIP jest powtarzalny bajt po bajcie.
Zmiana instrukcji zespołowej też zmienia zawartość paczki i jej SHA-256.

## Test gotowej paczki

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -I tests/check_plugin_zip.py dist/qgis-project-snapshot-0.9.7.zip
```

Skrypt rozpakowuje ZIP do tymczasowego profilu QGIS. Sprawdza natywne wykrywanie,
ładowanie, okno archiwizacji i wyłączenie wtyczki z minimalnym interfejsem testowym,
a następnie uruchamia pełne testy z kodu paczki. Weryfikuje ścieżki załadowanych
modułów, także kod używany przez procesy pomocnicze. Pominięte testy oznaczają
błąd odbioru. Profil użytkownika nie jest zmieniany. Test nie publikuje paczki.

Przy zmianie wersji zaktualizuj powyższą nazwę w poleceniu, odnośniki w README
i instrukcję. Raporty historyczne zachowują numery i sumy kontrolne poprzednich prób.

## Opcjonalny benchmark

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 tests/benchmark_archive.py --output /tmp/benchmark.json
```

Wymaga Linuksa (`/proc`) i lokalnych gniazd HTTP. Porównuje 1/2/4 procesy,
czas, sumę RSS, pliki tymczasowe oraz identyczność PNG. Korzysta z dwóch
kontrolowanych WMS i po próbie usuwa wygenerowane archiwa. Uruchamiaj go bez
innych obciążających zadań. Szczegóły i ograniczenia pomiarów opisuje
[raport kroku 4](validation-step4.md).

## Przygotowanie kolejnego wydania

Po zmianach kodu wykonaj odpowiednie testy, zbuduj paczkę i sprawdź jej instalację.
Po zmianach wyłącznie w dokumentacji poza paczką wystarczy kontrola odnośników,
diff i zgodności ZIP-a ze sprawdzoną sumą; identycznego kodu nie trzeba testować od nowa.
Uaktualnij [stan projektu](PROJECT_STATE.md). Testy firmowe prowadź według
[instrukcji zespołowej](team-guide.md), bez dodawania danych i poświadczeń do Git.

## Nazwa i zgodność instalacji

Widoczna nazwa to **QGIS Project Snapshot**. Prefiks ZIP-a pozostaje
`qgis-project-snapshot`, a katalog Pythona/identyfikator QGIS —
`mbtiles_batch_exporter`, aby aktualizacja zastępowała poprzednią instalację.
Nie zmieniaj go razem z etykietami interfejsu
bez osobnego planu migracji. Menu tworzy natywne `iface.addPluginToMenu`.

## Kontrole automatyki 0.9.7

Wzrost limitu hosta wymaga kolejki, wolnych miejsc w budżecie oraz okna co najmniej
15 s i 10 sukcesów. Limit rośnie o jeden, do mniejszej z wartości 32 i `2 × CPU`.
Brak 10% zysku oceniamy wyłącznie w pełnym oknie, podczas którego gotowe procesy
map rzeczywiście osiągały badany limit. Opóźniony start QGIS lub brak wolnych
procesów nie oznacza braku przyspieszenia serwera. Okno zbiera 15 s pracy przy
badanym obciążeniu; przejście do następnej mapy wyłącza tylko czas rozruchu,
bez kasowania poprawnych próbek. Krótka przerwa pomiędzy zapisem wyniku kafelka
a pobraniem następnego pozwolenia nie oznacza niegotowości procesu.

`process_memory()` odczytuje bieżący i szczytowy RSS własnego procesu: Linux
`/proc/self/status`, Windows `GetProcessMemoryInfo`, pozostałe Unix — peak z `resource`.
Brak odczytu daje None, bez dodatkowej zależności. WorkerGate publikuje pomiary
dopiero po renderowaniu, co najwyżej raz na 5 s oraz na końcu. Główny QGIS
(`local_gate`) nie jest używany do szacowania kosztu procesu pomocniczego.

E = max(384 MiB, 1,5 × największy dotychczasowy peak) albo początkowo 1 GiB.
Od MemAvailable odejmujemy 768 MiB oraz sumę zapasów wzrostu aktywnych procesów:
max(0, E − RSS). Proces bez RSS zachowuje pełną rezerwację ze startu (lub E,
jeżeli estymata wzrosła). Nowe miejsca to pozostały RAM podzielony przez E.
Spadek bieżącego RSS nie usuwa zapasu na jego ponowny wzrost. Historyczny peak
pozostaje do końca eksportu, również po zakończeniu procesu, który go zmierzył.

Telemetria jest czytana przed obliczeniem budżetu. Próbka co 5 s przyznaje
`launch_slots = max(0, budget − active)`; każdy start zużywa jedno miejsce.
Zakończenie procesu nie odnawia przydziału. CPU/32, minimum jednego i limit
dwóch przy nieznanym dostępnym RAM pozostają. Niedobór pamięci nie zabija map.
Stałe API `adaptive=False` zachowuje ustawienia liczby procesów.

Regresje obejmują wzrost powyżej dwóch zadań na host, uruchamianie i kończenie
procesów między próbkami RAM, ocenę rzeczywistego obciążenia oraz zachowanie map
przy anulowaniu. Wyniki wydania: [odbiór 0.9.7](validation-0.9.7.md).

## Tłumaczenia

Po zmianie tekstów zaktualizuj `mbtiles_batch_exporter/en.ts`, następnie skompiluj:

```bash
lrelease mbtiles_batch_exporter/en.ts -qm mbtiles_batch_exporter/en.qm
```

To narzędzie Qt używane tylko podczas rozwoju. Użytkownik dostaje gotowy katalog.
Testy sprawdzają zgodność katalogu z wywołaniami `tr`, parametry szablonów i oba języki.
Testy zachowania domyślnie ustawiają polski, niezależnie od lokalnego profilu QGIS.

## Benchmark automatu

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 tests/benchmark_adaptive.py --output /tmp/adaptive-benchmark.json
```

Porównuje sześć map, dwa hosty lokalnego WMS i tryb stały/adaptacyjny. Początkowy
budżet zasobów jest ustalony w teście, bieżąca kontrola RAM pozostaje aktywna.
Sprawdza identyczność PNG i lokalny odczyt. Wynik nie jest obietnicą szybkości usług produkcyjnych.

## Proxy i diagnostyka procesów

`worker_network.py` odczytuje ustawienia aktywnego QGIS i rozwiązaną konfigurację
proxy z jego menedżera sieci. Do procesu trafiają zwykłe dane JSON przez stdin,
a nie obiekty Qt, argumenty polecenia lub wpisy manifestu. Proces używa własnego
profilu (`QGIS_CUSTOM_CONFIG_PATH`), zapisuje jedynie ustawienia proxy bez loginu,
hasła i authcfg; poświadczenia pozostają w pamięci i są podawane na żądanie Qt.
Cały prywatny katalog procesu jest sprzątany. Nie kopiujemy bazy uwierzytelniania.

Testy `test_proxy.py`: proxy HTTP z Basic, wyjątek noProxyUrls, wyłączone proxy,
HTTP 407 i awaria uruchamiania procesu. Źródło `.invalid` jest osiągalne tylko
przez testowe proxy, więc sukces sprawdza rzeczywiste użycie konfiguracji przez
proces, a nie wyłącznie wartości parametrów. Testy używają izolowanych profili.

Pominięte poświadczenia lub logowanie interaktywne nie są zastępowane obchodzeniem
proxy. Nie wyłączamy walidacji TLS. Niestandardowe certyfikaty profilu, zewnętrzne
fabryki proxy i firmowe logowanie interaktywne wymagają osobnego sprawdzenia;
nie deklaruj pełnego odbioru wszystkich metod na podstawie testu HTTP Basic.
