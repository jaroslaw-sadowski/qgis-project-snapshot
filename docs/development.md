# Rozwój, testy i przygotowanie paczki

Polecenia wykonuj z katalogu głównego repozytorium. Użyj interpretera z modułami
`qgis` i `osgeo` dostarczonymi z QGIS; zwykłe środowisko Pythona może ich nie mieć.
Środowiska odbioru 1.0.0: Ubuntu, QGIS 3.40.15/Qt5 i QGIS 4.0.3/Qt6 6.10.2,
GDAL 3.12.2, Python 3.14.4. Wyniki: [odbiór wydania](release-1.0.0.md).
Numery 1.1–1.4 w dalszych opisach oznaczają historyczne wersje rozwojowe.

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
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -I tests/check_plugin_zip.py dist/qgis-project-snapshot-1.0.0.zip
```

Skrypt rozpakowuje ZIP do tymczasowego profilu QGIS. Sprawdza natywne wykrywanie,
ładowanie, okno archiwizacji i wyłączenie wtyczki z minimalnym interfejsem testowym,
a następnie uruchamia pełne testy z kodu paczki. Weryfikuje ścieżki załadowanych
modułów, także kod używany przez procesy pomocnicze. Pominięte testy oznaczają
błąd odbioru. Dla ograniczonej korekty interfejsu można podać
`--pattern test_snapshot_options.py`; test instalacji i menu nadal jest wykonywany,
a zestaw funkcjonalny ogranicza się wtedy do wskazanego pliku. Profil użytkownika nie jest zmieniany. Test nie publikuje paczki.

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

Koszt technicznego odczytu projektu można zmierzyć osobno:

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 tests/benchmark_project_read.py --output /tmp/project-read.json
```

Test tworzy 166 lokalnych rastrów w projekcie bez układów i z układami wydruku.
Porównuje standardowy odczyt z flagami używanymi od 1.4.3, sprawdza poprawność
warstw i identyczność pikseli. Uruchamiać bez innych obciążających zadań.
To pomiar samego `project.read`, nie obietnica skrócenia całego pobierania.

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
bez osobnego planu migracji. Jedna akcja o pełnej nazwie trafia bezpośrednio do `iface.pluginMenu()`,
bez podmenu. Przy wyłączeniu usuwamy tylko własną akcję.

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
przy anulowaniu. Historia tej poprawki: [odbiór 0.9.7](validation-0.9.7.md).
Bieżące wydanie: [1.0.0](release-1.0.0.md).

## Kontrole adaptacji i budżetu Windows (1.3.0)

Testy polityki muszą obejmować ponowną próbę wzrostu po 60 s zdrowych pełnych okien,
brak wzrostu po samym upływie czasu przy niedostatecznym obciążeniu, porównanie
z aktualną szybkością i cofnięcie dwóch słabych okien. Sprawdź wydłużanie kolejnych
stabilizacji do 120/240/300 s, zerowanie zdrowego okresu po błędach oraz redukcję
utrwalonego spadku ponad 25% również bez wcześniejszej próby zwiększenia limitu.
HTTP 429/503, trzy kolejne timeouty lub 502/504 oraz Retry-After zachowują przerwy.
Testy bramki odróżniają zwykłe błędy WMS od zdarzeń nadal wymagających ACK.

Przypadki pamięci Windows powinny sprawdzać niski dostępny commit przy wolnym RAM,
zachowanie działających map i ograniczenie nowych startów, powrót budżetu po
zwolnieniu pamięci oraz brak odczytu commit. Etykieta RAM nadal pokazuje fizyczną
pamięć. Należy zachować rezerwę 768 MiB, szacunek z RSS, izolację QGIS i jednego
zapisującego końcowy GeoPackage. Kod nie wymaga nowej zależności.

Przy próbie ręcznej porównaj mały dozwolony eksport z 1.2.0 i 1.3.0 na tym samym
obszarze, z tymi samymi warstwami i zoomami. Zachowaj oba końcowe logi i manifesty;
sprawdź wyniki PNG i kompletność, a następnie czasy oraz powody zmian limitów.
Wyniki różnych obszarów lub zoomów nie są porównaniem samej wersji algorytmu.
Nie uznawaj poprawnych testów jednostkowych za pomiar przyspieszenia usług
produkcyjnych ani pełny odbiór Windows. Wyniki wydania zapisuje
[raport 1.3.0](validation-1.3.0.md).

## Kontrole diagnostyki wydajności (1.2.0)

`test_performance_resources.py` sprawdza natywne liczniki Linux, rzeczywisty przyrost
CPU i I/O po niewielkiej lokalnej operacji, atrapy API Windows z wartościami 64-bitowymi,
zakres commit i I/O oraz niezależność błędów odczytu. Istniejące testy pamięci
weryfikują niezmienioną semantykę budżetowania. `test_performance_diagnostics.py`
oraz `test_diagnostics.py` obejmują okresowe próbki, zakończenie samplera,
kontekst etapów, pomiary sieci i brak treści poufnych.
Pełny odbiór oraz ograniczenia platform opisuje [raport 1.2.0](validation-1.2.0.md).

W próbie ręcznej wykonaj eksport, poczekaj na kilka próbek i anuluj go zwykłym
przyciskiem. Po zapisaniu wyniku sprawdź `performance_sample` głównego QGIS i map,
`scheduler_sample`, `network_interval` i `layer_summary`. Brak dostępnego odczytu
ma pozostać `null`, a nie zerem. Porównaj CPU i dostępny RAM z systemowym monitorem,
uwzględniając inny okres próbkowania i to, że 100% CPU procesu oznacza jeden
procesor logiczny. W Windows trzeba przeprowadzić rzeczywistą próbę — atrapy API
nie zastępują uruchomienia na tym systemie.

Orientacyjny koszt samego `performance_counters` zmierzono na lokalnym Linux
w 200 kolejnych odczytach dla każdego wariantu: mediana 0,178 ms dla własnego
procesu oraz 0,323 ms z danymi systemowymi. To pomiar pojedynczego odczytu,
bez zapisu logu i bez reprezentatywnego eksportu; nie jest benchmarkiem całej
wtyczki ani pomiarem kosztu na Windows. `probe_seconds` w nowych logach pozwala
ocenić czas odczytu podczas właściwego przebiegu. Interpretacja liczników
i ich ograniczenia: [architektura](architecture.md#pomiary-wydajności-120).

## Kontrole kontynuacji archiwum (1.1.0)

`tests/test_resume_archive.py` sprawdza kontynuację po anulowaniu, kopiowanie
ukończonych i pustych wyników bez ponownego pobierania, integralność plików,
zgodność ustawień, odrzucenie niezapisanych edycji i obsługę manifestu bez odcisku
źródła. Obejmuje też zasoby użyte ponownie oraz zachowanie poprzedniego częściowego
obrazu po nieskutecznym lub anulowanym ponowieniu. Testy okna sprawdzają przyciski
kontynuacji i wybór archiwum w obu językach.

Przy odbiorze ręcznym anuluj niewielki eksport po zapisaniu pierwszej warstwy,
poczekaj na wynik, a następnie zamknij QGIS. Otwórz oryginalny projekt, wybierz
„Wznów archiwum…” i wskaż cały poprzedni folder. Sprawdź nowy wynik i niezmienione
sumy plików starego archiwum. `continuation` oraz `reused` w manifeście i zdarzenia
`layer_reused` w diagnostyce pozwalają odróżnić skopiowane warstwy od nowego pobrania.
Próba nie potwierdza odzyskiwania danych po awarii programu lub utracie zasilania.

## Kontrole postępu kafelków i piramid (1.4.0)

`tests/test_tile_resume.py` sprawdza zachowanie PNG i poprawnie pustych kafelków,
uzgodnienie rejestru z GPKG, ponowienia braków z nowym budżetem oraz odrzucanie
niezgodnego obszaru lub siatki. Natywne lokalne WMS mają zliczać faktyczne żądania:
ukończone kafelki nie mogą być pobierane ponownie. Sumy PNG, liczniki logiczne
i `PRAGMA integrity_check` potwierdzają zachowanie danych.

`tests/test_overviews.py` porównuje pełną rozdzielczość UInt16 przed budową piramid
i po niej, maskę oraz RGBA, anulowanie zapisu, niezależne kolory zoomów i natywny
odczyt GDAL/QGIS przed scaleniem i po nim. Sprawdza też całkowicie pusty poziom
oraz brak zastępowania brakujących kafelków obrazem z innego zoomu.
`tests/test_snapshot_options.py` weryfikuje zapamiętanie widocznego folderu postępu,
końcowej nazwy i wybór wznowienia po wyjątku, w obu językach.

Test w nowym procesie musi też potwierdzić stabilność odcisku tego samego stylu
po ponownym zapisie XML przez Qt. Odcisk v2 z 1.4.0 używa `ElementTree.canonicalize`;
zmieniony styl lub źródło nadal mają blokować wznowienie. Dla archiwów 1.1–1.3
pozostaje dawne porównanie surowego XML, które może odmówić po restarcie wskutek
innej kolejności atrybutów. Test nie powinien omijać tej weryfikacji ani zastępować
oryginału przebudowanym projektem offline.

`tests/test_vector_archive.py` porównuje lokalny WFS z danymi, poprawnie pustą
odpowiedzią oraz błędem OGC. Sprawdza odświeżenie cache i zachowanie edycji,
pola pustego wyniku, geometrię obszaru i dodatkową kontrolę zerowego MSSQL.
Atrapa połączenia MSSQL nie zastępuje rzeczywistej próby w sieci firmowej.
Kontynuacja musi ponownie sprawdzić stare zerowe WFS/MSSQL bez
`vector_read_version=2` oraz nowe zerowe MSSQL z `empty_read_verified=null`.
Potwierdzony pusty odczyt nadal ma być zachowany bez ponowienia.

W odrębnej próbie z małymi lokalnymi danymi przerwij proces QGIS po zapisaniu
części mapy, następnie wznowienie uruchom w nowym procesie z oryginalnego projektu.
Sprawdź folder `.w-trakcie-`, kopię wyników, liczbę żądań tylko dla braków,
całe PNG i końcową integralność. Nie używaj do testu niezapisanej pracy użytkownika.
Zakończenie procesu nie symuluje wszystkich skutków awarii dysku lub zasilania;
nie jest podstawą deklaracji odporności na fizyczne uszkodzenie danych.
Wyniki tego etapu zapisuje [raport 1.4.0](validation-1.4.0.md).

## Kontrole nazw i układu folderu (1.4.2)

`test_output_language.py` sprawdza PL→EN→PL na natywnych wektorach, GeoTIFF
i załącznikach, także po usunięciu źródłowego załącznika i anulowaniu końcowego
zapisu. Drugi przypadek odtwarza nazwy i pola manifestu 1.4.1.
`test_crash_resume.py` sprawdza także zmianę języka niedokończonej mapy:
zapisany kafelek nie jest pobierany ponownie. Kontroluj raport, okno, ścieżki
QGZ i metadane GPKG, nie tylko same ciągi znaków. Wielkość GeoTIFF i decyzja
o piramidach muszą zgadzać się z natywnie odczytanym wynikiem.

Sprawdź sufiks `_nie-bylo-obiektow-w-zasiegu` tylko dla potwierdzonego pustego
wektora, zachowanie pól i stylu oraz niezmienioną nazwę oryginału. Błąd, raster
pusty i niepotwierdzone MSSQL nie mogą otrzymać tego oznaczenia.
Testy okna mają odczytać nowy manifest przez `read_resume_manifest`, wyświetlić
`output_name` i pamiętać cały folder archiwum. Kontynuacja musi przyjmować
również starszy manifest z folderu głównego. Sprawdź nowy zapis w `diagnostyka/`
i brak pustego `stan-pobierania/`, bez usuwania postępu potrzebnego do wznowienia.
Wyniki i paczkę opisuje [raport 1.4.2](validation-1.4.2.md).

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

## Kontrole katalogu QGIS

Aktualne wymagania i ręczne kroki publikacji: [publishing.md](publishing.md).
Metadane wydania wskazują zakres QGIS 3.40–4.99. Ten sam ZIP sprawdzaj
osobno interpreterem QGIS 3/Qt5 i QGIS 4/Qt6; jeden runtime nie zastępuje drugiego.
Test ZIP-a kontroluje wymagane pola, wersję, adres autora, licencję, HTTPS,
rozmiar do 25 000 000 bajtów, prawa 0644 i brak obcych plików. Nie potwierdza
publicznej dostępności GitHub — sprawdź ją osobno, bez logowania.

Dodatkowe narzędzia są wyłącznie do rozwoju, w osobnym środowisku:

```bash
/tmp/snapshot-audit-venv/bin/pip install bandit==1.9.4 detect-secrets==1.5.0 flake8==7.3.0
/tmp/snapshot-audit-venv/bin/bandit -r mbtiles_batch_exporter -f json -o /tmp/snapshot-bandit.json
/tmp/snapshot-audit-venv/bin/detect-secrets scan --all-files --no-verify mbtiles_batch_exporter > /tmp/snapshot-secrets.json
/tmp/snapshot-audit-venv/bin/flake8 mbtiles_batch_exporter --max-line-length=88 --extend-ignore=E203 --jobs=1
```

Bandit może zakończyć się kodem 1 dla ostrzeżeń wymagających przeglądu; nie uznawaj
ich automatycznie za błąd ani za fałszywy alarm. Reguły krytyczne określa portal.
Nie ukrywaj trafień wyłączeniami bez ustalenia przyczyny. detect-secrets zapisuje
wynik JSON, którego pole results należy sprawdzić; sam kod wyjścia nie wystarcza.
Opcja --no-verify zapobiega weryfikacji kandydatów przez sieć. Przy Pythonie 3.14
skaner może wymagać dostępu do lokalnych gniazd dla procesów pomocniczych.

Flake8/pycodestyle E203 dotyczące spacji w przekrojach koliduje z formatem Ruff;
pominięcie jest jawne. Limit 88 znaków oraz E203 to konwencja projektu, nie deklaracja
ścisłego zastosowania każdej reguły PEP 8. Kod produkcyjny nie wymaga wyłączenia E402.
Pliki .qm to dane Qt, a dołączone .ts są ich źródłem; nie są bibliotekami binarnymi.

## Odbiór Qt6 i kontroler katalogu

Używaj `qgis.PyQt`, pełnych nazw enumów i `QDialog.exec()`. Qt6 zapisuje
właściwości projektu przez elementy `properties name="..."`; Qt5 używa nazw
w tagach. Usuwanie makr i ustawienie ścieżek względnych musi obsługiwać oba
formaty. Testy przenoszą archiwum, otwierają je offline i sprawdzają brak makr
w projekcie wynikowym oraz plikach procesów pomocniczych.

Do sprawdzenia gotowej paczki użyj tego samego polecenia `check_plugin_zip.py`
z interpreterem QGIS 4. Na tym stanowisku runtime jest rozpakowany w ignorowanym
`dist/test-environments/`, bez zastępowania systemowego QGIS 3. Środowisko musi
wskazywać własne `QGIS_PREFIX_PATH`, biblioteki Qt6, pluginy Qt6 i moduły Pythona.
Nie kopiuj tych ścieżek do kodu ani paczki. Test tworzy własny profil i działa
z `QT_QPA_PLATFORM=offscreen`; nieoczekiwane okna ostrzeżeń kończą test błędem. Na koniec samodzielny program
wywołuje `exitQgis()`, aby zamknąć dostawców przed niszczeniem bibliotek.

Uruchom również oficjalny [pyqgis4-checker](https://github.com/qgis/pyqgis4-checker).
Używa skryptu `scripts/pyqt5_to_pyqt6/pyqt5_to_pyqt6.py` z QGIS; parametr
`--dry_run` kontroluje kod bez jego przepisywania. Wymaga środowiska Qt6 i
zależności developerskich podanych przez narzędzie. Przypnij sprawdzoną rewizję
przy odtwarzaniu audytu. Sam kontroler nie wykrywa wszystkich zmian zachowania.

Konfiguracja `.flake8` w repozytorium i ZIP-ie ustala ten sam limit 88 znaków
oraz E203 co Ruff. Nie wyłącza kontroli bezpieczeństwa. Bandit i skan sekretów
uruchamiaj także na rozpakowanej paczce. Zmiana zakresu na 4.99 jest zgodna z
[aktualną instrukcją QGIS](https://plugins.qgis.org/docs/migrate-qgis4);
nie dodawaj wycofanego pola `supportsQt6`.
