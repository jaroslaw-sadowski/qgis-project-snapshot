# Audyt drugiego obszaru i odbiór 1.4.3

12 września 2026. Analiza nowych `manifest.json` i `diagnostic.jsonl` użytkownika.
Dane źródłowe pozostały poza repozytorium. Raport zawiera tylko zbiorcze pomiary;
zawartość plików traktowano jako dane, nie instrukcje.

## Wynik przebiegu

Log wskazuje **1.4.1**, Windows 11, QGIS 3.40.15, Python 3.12.12, GDAL 3.12.1,
14 logicznych CPU. Zoomy **16–19**, czas **20 min 45,559 s**. To inny obszar
niż w [poprzednim raporcie](validation-1.4.2.md), więc krótszy czas nie mierzy
przyspieszenia nowej wersji wtyczki.

| Wynik | Liczba |
| --- | ---: |
| Wszystkie warstwy | 205 |
| Saved / empty | 76 / 129 |
| Failed / partial / cancelled — warstwy | 0 / 0 / 0 |
| Zakończone procesy mapowe, kod 0 | 166 |
| Pozycje kafelków na wszystkich zoomach | 7304 |
| Niepuste / poprawnie puste kafelki | 1916 / 5388 |
| Naprawione kafelki / końcowe braki | 7 / 0 |

Każda mapa obejmuje 44 pozycje (zoomy 16–19: 1, 4, 9, 30); siedem dodatkowych
prób daje 7311 prób łącznie. 2120 surowych niepustych obrazów pomniejszono o 204
obrazy poza rzeczywistą maską. Wśród warstw `empty` 114 jest całkowicie
przezroczystych, 15 zawiera obraz na innych zoomach. Nie wolno automatycznie
usuwać wszystkich warstw `empty`.

Wystąpiło 14 sygnałów timeout i 32 przejściowe konflikty wymiany pliku Windows
(3 w koordynatorze, 29 w procesach), wszystkie z odpowiadającym odzyskaniem.
Obserwowane podsumowania sieci nie zawierają HTTP 429/5xx. Timeout i ponowienie
kafelka to różne liczniki; pojedynczy kafelek może wymagać kilku żądań sieciowych.
Nie stwierdzono awarii koordynatora ani procesu. Audyt odczytu lokalnych warstw
przeszedł, raport zasobów nie zawiera problemów. Globalny status pozostaje
`partial`; bez wynikowego GeoPackage i projektu nie jest to niezależny odbiór danych.

MSSQL: jedna warstwa zapisała jeden obiekt, **32 wyniki zerowe pozostają
niepotwierdzone**. Źródła mają rekordy, ale sprawdzenie dostępu nie potwierdza
przestrzennego wyniku dla tego obszaru. Nie nazywamy ich ani udowodnioną awarią,
ani potwierdzonym brakiem obiektów. Trzy WFS zakończyły odczyt z potwierdzonym zerem,
bez zgłoszonego błędu. Sprawdzenie znanego obiektu na stanowisku z dostępem do
firmowych danych nadal pozostaje potrzebne; obecne Ubuntu nie ma tego dostępu.
Trzy GeoTIFF mają puste listy piramid; stary log nie zawiera wymiarów.
Wprowadzona w 1.4.2 diagnostyka wymiarów i decyzji o piramidach pozostaje w 1.4.3.

## Komputer i serwery

Budżet osiągnął 9, a rzeczywista liczba procesów **7** (zgodne próbki oraz
zdarzenia start/exit). Aktywne zadania również osiągnęły 7. Budżet jest limitem
startów przy danym pomiarze pamięci, a nie obietnicą stale zajętych miejsc.

CPU całego systemu, średnia ważona czasem: **45,63%**, maksimum **84,18%**.
Wolny RAM **4,44–5,97 GiB**, dostępny commit Windows **0,383–4,466 GiB**.
Minimum commit to około **393 MiB**, poniżej rezerwy 768 MiB. RSS głównego QGIS
wynosił 829,5–2213,7 MiB, największy zmierzony szczyt procesu mapowego 315,8 MiB.
CPU nie dowodzi pełnego wykorzystania klienta, a wolny RAM nie upoważnia do
pominięcia ochrony commit. Nie zwiększono arbitralnie limitów pamięci i procesów.

Limity serwerów osiągały 1–3. Geoportal zwiększył 1→2→3, a przy utrzymującym się
spadku przepustowości cofnął do 2 (`throughput_drop`). Dwie inne duże kolejki
osiągnęły 3. Działa wzrost i redukcja obciążenia; nie jest to dowód osiągnięcia
maksimum każdego serwera. Sygnały ograniczenia, Retry-After i pamięć klienta
nadal mają pierwszeństwo przed kolejnym zwiększaniem równoległości.

## Miejsce optymalizacji i zmiana

| Etap | Suma sekund |
| --- | ---: |
| Procesy: uruchamianie QGIS | 322,70 |
| Procesy: konfiguracja sieci | 48,44 |
| Procesy: otwieranie źródła | 1231,27 |
| Procesy: renderowanie i pobieranie | 2669,25 |
| Główny QGIS: scalanie | 124,97 |
| Główny QGIS: zasoby i przygotowanie projektu | 46,11 |
| Główny QGIS: audyt lokalnego odczytu | 74,61 |

Przygotowanie procesów i otwarcie źródeł stanowi **37,48%** sumy ich etapów
(łącznie z zapisem wyników). Etapy procesów zachodzą równolegle; tych sekund
nie można odjąć od czasu całego eksportu jako obiecanego przyspieszenia.

Przed zmianą sprawdzono istniejący kod i natywne możliwości QGIS zgodnie
z [zasadami Ponytail](https://github.com/dietrichgebert/ponytail).
Wersja **1.4.3** używa flag QGIS `DontStoreOriginalStyles`, `DontLoadLayouts`
i `DontLoad3DViews` w tymczasowych procesach renderowania i obu kontrolach
projektu. QGIS pomija kopie stylów potrzebne do późniejszej obsługi w edytorze,
układy wydruku i widoki 3D, których te operacje nie używają. Dokumentuje to
[natywna implementacja QGIS 3.40](https://api.qgis.org/api/3.40/qgsproject_8cpp_source.html).

Właściwe style warstw są nadal wczytywane, a końcowy projekt powstaje z pełnego
oryginalnego XML. Układy, style i widoki nie są usuwane z archiwum ani z oryginału.
Audyt nadal rzeczywiście otwiera lokalnych dostawców danych. Flaga pomijająca
rozwiązywanie źródeł pozostaje wyłącznie w dotychczasowej kontroli struktury XML.
Nie pominięto kontroli integralności, nie zmieniono PNG, niezależnych zoomów,
sterowania serwerami, zasad wznowienia ani jednego zapisującego GeoPackage.

## Pomiar zmiany

`tests/benchmark_project_read.py` tworzy własny TIFF RGBA i projekt ze 166 rastrami.
Drugi wariant dodaje 20 układów po 20 etykiet. Każdy wariant ma po trzy pomiary
obu sposobów odczytu, z przeplataną kolejnością. Mierzony jest tylko `project.read`;
walidacja 166 warstw i porównanie wyrenderowanych pikseli odbywają się poza pomiarem.
Profil QGIS i dane są tymczasowe. To lokalny test syntetyczny, bez usług użytkownika.

Wstępny pomiar przed wdrożeniem: mediany 0,656→0,567 s bez układów (13,65%)
i 1,431→0,776 s z układami (45,76%). Powtórzenie rozszerzone o kontrolę pikseli
współdzieliło CPU z lintem; nie przyjmujemy go jako końcowego pomiaru szybkości.
Końcowy pomiar wykonano osobno (Ubuntu/QGIS 3.40.15/GDAL 3.12.2):

| Projekt | Zwykły odczyt, mediana s | Techniczny odczyt, mediana s | Skrócenie |
| --- | ---: | ---: | ---: |
| plain.qgz | 0.627240 | 0.555164 | 11.49% |
| layouts.qgz | 1.420105 | 0.747252 | 47.38% |

Wszystkie odczyty dały 166 poprawnych warstw i identyczne wyrenderowane piksele.
Nie przenosimy tych procentów na czas pełnego eksportu na Windows.

## Dalsze prace wymagające pomiaru

Ponowne użycie procesu QGIS dla następnej mapy nadal jest kandydatem do osobnego
prototypu i benchmarku. Wymaga kontroli pamięci oczekujących procesów, izolacji
źródeł i poświadczeń, cache dostawców, anulowania oraz zamknięcia prywatnej bazy
przed scaleniem. Nie wdrożono takiej przebudowy bez porównania bezpieczeństwa
i szybkości. Najpierw wybrano małą, zmierzoną optymalizację natywną QGIS.

Do następnego porównania użyć 1.4.3, tego samego obszaru i zoomów oraz zachować
manifest i log. Dotychczasowe dwa przebiegi mają inne obszary i liczbę pozycji
kafelków. Nie wyliczać z ich czasów przyspieszenia nowej wersji.


## Odbiór gotowej paczki

**231/231 testów, 167,453 s, bez pominięć**, z kodu końcowego ZIP-a w izolowanym
QGIS 3.40.15 na Ubuntu (GDAL 3.12.2, Python 3.14.4). Wykrywanie, ładowanie, okno
archiwizacji i wyłączenie poprawne. Wykonano lokalne WMS, WFS, proxy, anulowanie,
SIGKILL i wznowienie, stare układy archiwów, PL/EN oraz kontrole pikseli i piramid.
Nowy test potwierdził zachowanie rzeczywistego układu i stylu w archiwum oraz
wykrycie braku pliku danych przez techniczny audyt. Cztery testy zasobów przed
pełnym odbiorem także przeszły (0,913 s).

Ruff check/format i Flake8/pycodestyle poprawne. Limit 88, E203 jak dotychczas,
E402 pomijane wyłącznie dla trzech plików uruchamiających QGIS przed importami.
Pierwsze wywołanie Flake8 bez tych wyjątków zgłosiło oczekiwane importy testowe
oraz jeden 89-znakowy literał testu; literał podzielono, kontrola z jawną konwencją
projektu przeszła. AST 44 plików, 337 tłumaczeń, lokalne linki i git diff — OK.
Nie ma osobnego typecheckera. Nie dodano zależności instalowanej wtyczki.

Bandit: 20 dotychczasowych przejrzanych ostrzeżeń (15 medium, 5 low, zero high).
Porównanie kodu paczek 1.4.2 i 1.4.3 wykazuje wyłącznie opisaną zmianę flag
w trzech modułach; bez nowego SQL, podprocesów i interpretacji kodu. Osobne skany
sekretów źródeł produkcyjnych i rozpakowanego ZIP-a dały zero trafień (`--no-verify`).
Komunikaty GDAL o niemożliwych statystykach pochodzą z celowo przezroczystych
rastrów testowych; testy ich odczytu przeszły. Ostrzeżenie codecs.open pochodzi z QGIS.

`dist/qgis-project-snapshot-1.4.3.zip`: **146 355 bajtów, 22 pliki**.
Powtórna budowa w osobnym katalogu dała identyczne bajty. SHA-256:

```text
fe367e14866493f916f78cc198566e30835ccdf9249138aac93f70bd69658247
```

Bez publikacji i instalacji w profilu użytkownika. Próba 1.4.3 na Windows oraz
odbiór firmowego MSSQL nadal wymagają stanowiska z właściwym dostępem.
Propozycja wspólnego commitu dla niezatwierdzonych zmian 1.4.2–1.4.3:
`Prepare 1.4.3: localize archive output and reduce QGIS read overhead`.
