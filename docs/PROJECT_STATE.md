# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 12 września 2026. Wersja **1.4.3**: optymalizacja technicznych
odczytów QGIS i audyt drugiego obszaru.

## Zmiany i odbiór 1.4.3

Nowe manifest.json i diagnostic.jsonl użytkownika nadal pochodzą z **1.4.1**.
Windows, 14 logicznych CPU, zoomy 16–19, czas 20 min 45,559 s. 205 warstw:
76 saved, 129 empty, bez failed/partial/cancelled. 7304 pozycje kafelków,
1916 niepustych, 5388 pustych; siedem napraw i zero końcowych braków.
114 map całkiem przezroczystych, 15 empty zawiera obraz na innych zoomach.
32 przejściowe konflikty plików Windows obsłużone, wszystkie 166 procesów kod 0.
Audyt lokalnych warstw passed, zasoby bez issues; globalny status partial.
MSSQL: jeden obiekt w jednej warstwie, **32 zera niepotwierdzone**; WFS trzy
potwierdzone zera. Nie ma dostępu do firmowych źródeł ani wynikowego GPKG/QGZ
użytkownika; nie deklarować poprawności tych zer bez porównania znanego obiektu.

Budżet do 9, faktycznie maksymalnie 7 procesów i 7 aktywnych zadań. CPU całego
systemu średnio 45,63%, szczyt 84,18%; wolny RAM 4,44–5,97 GiB, commit
0,383–4,466 GiB (minimum około 393 MiB, poniżej rezerwy 768 MiB). Hosty 1–3,
Geoportal zwiększył 1→2→3 i obniżył do 2 przy throughput_drop. Nie dowodzi to
maksymalnego wykorzystania wszystkich zasobów; nie podniesiono limitów arbitralnie.
Inny obszar i zoomy nie są porównaniem szybkości wersji.

Przygotowanie QGIS/sieci/źródeł stanowiło 37,48% sumy etapów procesów. Wybrano
minimalną natywną zmianę: DontStoreOriginalStyles, DontLoadLayouts, DontLoad3DViews
przy odczycie w archive_worker oraz obu kontrolach projektu (archive i resources).
Style renderowania i pełny oryginalny XML w archiwum pozostają. Audyt nadal
otwiera dostawców; DontResolveLayers tylko w dotychczasowej kontroli struktury.
Worker source_opened loguje project_read_flags. Bez zmiany pobierania, PNG,
sterowania obciążeniem, pamięci, wznowienia i jednego zapisującego GeoPackage.
Ponowne użycie procesów nadal wymaga osobnego prototypu/benchmarku, nie jest wdrożone.

Natywny benchmark tests/benchmark_project_read.py: 166 lokalnych rastrów,
po trzy odczyty każdego wariantu, przeplatana kolejność. Końcowe mediany
0,627240→0,555164 s bez układów (11,49%) i 1,420105→0,747252 s z 20 układami
(47,38%); poprawne warstwy i identyczne piksele. To pomiar samego project.read
na Ubuntu, nie całego eksportu ani Windows. Cztery testy zasobów przeszły;
nowy sprawdza zachowanie stylów/układu i wykrycie usuniętego pliku danych.

**Końcowy ZIP: 231/231 testów, 167,453 s, bez pominięć.** Natywne WMS/WFS/proxy,
anulowanie, SIGKILL, wznowienie, PL/EN i piksele wykonane z paczki. Ruff/format,
Flake8 (88, E203 i E402 tylko w plikach startujących QGIS), AST 44 plików,
337 tłumaczeń, linki i diff — OK. Skan sekretów źródeł i ZIP-a: zero. Bandit
20 znanych przejrzanych ostrzeżeń: 15 medium, 5 low, zero high.
ZIP **146 355 bajtów, 22 pliki**, powtarzalny SHA-256:
fe367e14866493f916f78cc198566e30835ccdf9249138aac93f70bd69658247.
Bez publikacji i instalacji w profilu użytkownika. Szczegóły pomiarów i odbioru:
[validation-1.4.3.md](validation-1.4.3.md). Zmiany 1.4.2 i 1.4.3 są nadal
niezatwierdzone w Git; zachować je przy dalszej pracy.

## Zmiany i odbiór 1.4.2

Przekazany rzeczywisty przebieg 1.4.1 na Windows: 205 warstw, zoomy 15–17,
30 min 14 s, 87 saved i 118 empty, bez failed/partial/cancelled warstw i bez
brakujących kafelków po czterech naprawach. 21 warstw empty ma obraz na innych
zoomach, 97 jest całkowicie przezroczystych. Lokalny audyt passed, bez issues
zasobów. To nie pełny odbiór danych bez wynikowego GPKG/QGZ i porównania źródeł.
MSSQL zapisał 52 obiekty w 11 warstwach; 20 zerowych odczytów pozostaje
niepotwierdzonych, dwa zera MSSQL i trzy zera WFS potwierdziła ścieżka odczytu.
Nie prosić ponownie o dostęp do niedostępnej obecnie sieci firmowej.

Maksimum pięć procesów, cztery aktywne zadania w próbkach. CPU systemu średnio
31,61%, maksimum 82,65%; wolny RAM 2,73–4,33 GiB, dostępny commit 0,37–3,51 GiB.
Commit spadał poniżej rezerwy 768 MiB, więc wyższe obciążenie nie było bezwarunkowo
bezpieczne. Geoportal zwiększył limit 1→2→3, cofnął do 2 przy braku zysku i ponowił 3.
Uruchamianie QGIS i otwieranie źródeł stanowiło około 30% sumy etapów procesów;
ponowne użycie procesu jest propozycją do benchmarku, nie wdrożoną optymalizacją.
Nie zmieniono algorytmu obciążenia ani jakości danych. Szczegóły i ograniczenia
pomiarów: [validation-1.4.2.md](validation-1.4.2.md).

1.4.2 używa istniejącego katalogu Qt do nazw plików i folderów. Sufiks PL:
`_nie-bylo-obiektow-w-zasiegu`; EN: `_no-features-in-area`. Nazwy źródłowe pozostają.
PL: `<nazwa>_archiwum_<data>`, `.w-trakcie-…`, dane/dane.gpkg, zasoby/,
raport.html, diagnostyka/manifest.json, diagnostyka/diagnostyka.jsonl,
diagnostyka/stan-pobierania/. EN: `_archive_`, `.in-progress-…`, data/data.gpkg,
resources/, report.html, diagnostics/manifest.json, diagnostics/diagnostic.jsonl,
diagnostics/download-state/. Identyfikatory techniczne i rejestr pozostają zgodne.
Schemat manifestu nadal 4; resources_directory i recovery_directory zapisują
położenie niezależne od języka następnego wznowienia. Odczyt stosuje znaną listę
dozwolonych nazw i domyślne stare ścieżki, jeśli pola nie istnieją.

Kontynuacja w obu kierunkach PL/EN zachowuje kafelki, źródłowe rastry, puste
wektory i załączniki. Ich ścieżki są przepisywane także przy anulowaniu końcowego
zapisu już skopiowanych danych. Test odtwarza dawne nazwy 1.4.1 i poprawia stary
dopisek przy wznowieniu bez ponownego pobrania wektora. Nowa diagnostyka GeoTIFF
zawiera raster_size, overview_factors i overview_status w manifeście oraz JSONL;
puste listy piramid trzech wyników 1.4.1 nie miały wymiarów do niezależnej oceny.

Końcowy ZIP: **230/230 testów, 167,283 s, bez pominięć**, z kodu paczki
w izolowanym QGIS na Ubuntu. WMS/WFS/proxy, wznowienie po SIGKILL, oba języki
i starsze układy wykonane. W pierwszym zestawie poprawiono stare oczekiwanie
testu dotyczące angielskiej nazwy folderu przy polskim interfejsie; dodano też
ochronę typu JSON i testy niedozwolonych ścieżek manifestu. Ruff/format,
Flake8/pycodestyle, AST 43 plików, 337 tłumaczeń, odnośniki i diff — OK.
Skan produkcyjnych źródeł i rozpakowanego ZIP-a bez sekretów; Bandit nadal
20 przejrzanych ostrzeżeń (15 medium, 5 low, zero high).
Paczka 145 887 bajtów, 22 pliki; powtarzalna SHA-256:
054daf313028cb653736e947ad4ee911e2771696c1f681a9860ed5d4005a6a1c.
Bez publikacji ani instalacji w profilu użytkownika. Pełny odbiór nowej wersji
na Windows i firmowego MSSQL nadal wymaga próby na dostępnym stanowisku.

## Zmiany i odbiór 1.4.1

Potwierdzone puste wektory otrzymują dokładnie dopisek
`_nie-bylo-obiketow-w-zasiegu` w wynikowym projekcie, drzewie, raporcie
i identyfikatorze GPKG. Warunki: saved/vector/feature_count=0 oraz
empty_read_verified=true. Niepotwierdzone zero, błędy i obraz zastępczy nie
otrzymują dopisku. Oryginalny projekt, nazwy źródeł, ID i techniczne tabele
pozostają; output_name w manifeście opisuje wynik. Wznowienie nie powiela dopisku.

Nowe archiwum: QGZ i raport.html w głównym katalogu, dane/dane.gpkg razem z AUX,
diagnostyka/manifest.json, diagnostic.jsonl i download-state dla nieukończonych
kafelków. Opcjonalne zasoby pozostają w zasoby/. Raport PL/EN opisuje foldery
i składa pełny JSON pod szczegółami diagnostycznymi. Schemat manifestu nadal 4,
data_file wskazuje dane/dane.gpkg. UI i kopiowanie kontynuacji rozpoznają dawny
manifest, GPKG i cache w katalogu głównym. Zachować cały folder do wznowienia.
Natywne próby GDAL/QGIS potwierdzają przenośność GPKG razem z AUX bez regeneracji
statystyk przy otwieraniu. Nowy eksport z kontynuacji nadal odtwarza statystyki,
ponieważ może zastępować tabele częściowych map.

Pierwszy ZIP przeszedł 225/225 testów bez pominięć. Przegląd ujawnił dodatkowo
błędne odzyskiwanie dawnego vector0 jako rastra po nieudanym ponowieniu obu metod.
Test odtworzył przerwanie całego wznowienia. Warunek method=raster_render usuwa
przyczynę; pięć testów nazw i tej regresji przeszło.
Końcowy ZIP: **226/226 testów, 158,736 s, bez pominięć**, w izolowanym profilu;
lokalne WMS, WFS i proxy wykonane. Ruff/format, Flake8/pycodestyle, AST 42 plików,
325 tłumaczeń, lokalne odnośniki i diff — OK. Skan sekretów źródeł i osobno
rozpakowanego ZIP-a bez trafień; Bandit nadal 20 przejrzanych ostrzeżeń,
15 medium i 5 low, zero high. Paczka 144 567 bajtów, 22 pliki, powtarzalna:
9b43991a8e4a3c532e46417caef9dbef86c3012f032e7f3b0413b96a24099921.
Wyniki i ograniczenia:
[validation-1.4.1.md](validation-1.4.1.md). Brak publikacji lub instalacji
w profilu użytkownika.

## Zmiany i odbiór 1.4.0

Użytkownik zlecił diagnozę zerowych WFS/MSSQL, poprawę odczytu rastrów i wznowienie
po awarii QGIS/reboocie. Lokalne testy rzeczywistego dostawcy WFS odtworzyły dwa
błędy: opóźniony sygnał Qt po OWS Exception dawał fałszywe Saved 0, a cache mógł
zachować wcześniejszy pusty wynik. Dostarczamy oczekujące błędy przed oceną odczytu
i odświeżamy cache poza trybem edycji. Prawidłowe puste zasięgi nadal są poprawne.
MSSQL może zamknąć iterator bez błędu dostępnego Pythonowi. Natywne ograniczone
TOP (1) weryfikuje dostęp/tabelę/subset, bez logowania SQL lub poświadczeń.
Nie potwierdza przestrzennego SQL, jeśli tabela ma obiekty: wynik 0 otrzymuje uwagę
i `empty_read_verified=null`. Takie wyniki i starsze remote vector0 są odczytywane
ponownie przy kontynuacji; `vector_read_version=2` rozróżnia nową kontrolę.
Sieć firmowa nadal niedostępna; nie deklarujemy pełnego naprawienia jej MSSQL.

GeoTIFF otrzymuje wewnętrzne piramidy GDAL NEAREST/DEFLATE9 z zachowaniem pełnych
wartości i masek. Mapy GPKG zachowują niezależne zoomy; w pełni poprawny przezroczysty
zoom otrzymuje minimalny pusty PNG, aby GDAL nie pomijał go przy odczycie.

Trwały folder `.in-progress-…` i atomowy manifest istnieją od początku pobierania.
`download-state` zachowuje prywatny GPKG i rejestr kafelków SQLite FULL. Zachowane
PNG są sprawdzane, puste kafelki ponownie używane, braki otrzymują nowy budżet prób.
Backup SQLite odtwarza spójny stan po przerwaniu, a QLockFile chroni aktywne dane.
Cache znika dopiero po scaleniu i trwałym checkpoint. Pierwszy merge i pierwsze
utworzenie GPKG wektorów są atomowe. Wektory restartują wyłącznie niedokończoną
warstwę. GUI zapamiętuje folder; wznowienie wymaga oryginalnego projektu.

Test nowego procesu QGIS wykrył dodatkowo niestabilną kolejność atrybutów XML
w dawnym odcisku stylu. Wersja odcisku 2 używa ElementTree.canonicalize. Stare
odciski 1.1–1.3 pozostają sprawdzane dawną metodą i mogą odmówić wznowienia po
restarcie; nie obchodzimy walidacji. Starsze archiwa nie mają rejestru 1.4 do
wznowienia pojedynczych kafelków. Nowy mechanizm nie odzyskuje już usuniętych danych.

Natywny test zabicia QGIS i wznowienia w innym procesie przeszedł: pierwsza mapa
bez ponownego pobierania, dwa kafelki niedokończonej mapy zachowane identycznie.
Przeszły również dedykowane testy WFS, piramid, blokad i anulowanego workera.
Końcowy ZIP: **219/219 testów w 156,211 s**, bez pominięć, w izolowanym QGIS;
WMS, WFS i proxy wykonane. Pierwszy zestaw wykrył dawne założenia trzech testów
o ścieżkach/markerach oraz regresję retry trybu stałego; poprawiono przyczyny,
sprawdzono dedykowane przypadki i ponownie pełny ZIP. Automatyczny tryb zachowuje
3 próby; techniczne adaptive=False odzyskało dawny podział z zachowaniem postępu.
Ruff/format, Flake8/pycodestyle, AST 41 plików, odnośniki i diff — OK.
Skan sekretów bez trafień; 20 przejrzanych ostrzeżeń Bandit (15 medium, 5 low).
Paczka 141 090 bajtów, 22 pliki; powtarzalna SHA-256:
38200abf7b13714b04d46533c925b7af47225e0cb4172675bed33579891c22c9.
Wyniki i ograniczenia: [validation-1.4.0.md](validation-1.4.0.md).
Nie publikowano ani nie instalowano paczki w profilu użytkownika. Aktualizować
po zakończeniu eksportu i ponownie uruchomić QGIS. Wznowienie pojedynczych kafelków
dotyczy postępu zapisanego w 1.4.0; nie odzyskuje kafelków usuniętych przez starsze wersje.

## Optymalizacje 1.3.0 na podstawie rzeczywistej diagnostyki

Użytkownik przekazał nowy przebieg 1.2.0 i autoryzował wdrożenie optymalizacji.
Windows 11, Core Ultra 5 135U, 16 GB RAM: 43 min 6 s, zoomy 16–18,
211 warstw (96 saved, 109 empty, 6 failed), bez anulowania/partial.
Maksimum 13 procesów i 11 aktywnych zadań; CPU całego systemu średnio 29,39%.
W minutach 20–40 działały 3 procesy przy budżecie około 10 i 5,08 GiB wolnego RAM.
Geoportal pozostał zamrożony przy 2 zadaniach po 431 s, mimo dalszej kolejki.
Najmniejszy Windows commit wyniósł 325 MiB przy 4,52 GiB wolnego RAM; zwiększanie
obciążenia wymagało również poprawy ochrony przydziału pamięci.

Zmiany 1.3: frozen jest okresem stabilizacji, po 60 s zdrowych pełnych okien można
ponowić pojedynczy wzrost; dwa okna bez 10% zysku cofają, kolejne nieudane próby
wydłużają stabilizację 60/120/240/300 s. Dwa pełne okna spadku szybkości >25%
zmniejszają ustalony limit. Zachowano natychmiastową reakcję 429/503, dodano
seryjne 502/504 obok timeoutów. Spóźnione Retry-After obowiązuje także po udanym
probe. Zwykłe błędy WMS nie czekają na każde ACK, lecz pozostają raportowane;
przeciążenie/timeout/probe nadal wymagają potwierdzenia i ważnego pozwolenia.

Starty korzystają z min(RAM, dostępny commit Windows), bez zmiany rezerwy 768 MiB,
estymaty RSS i sufitu 32 / 2 × CPU. Pierwszy przydział następuje po świeżym pomiarze.
Wzrost pozwoleń istniejących procesów wymaga też pokrycia reserved_growth;
odłożone hosty rozliczają wyniki mimo braku RAM lub slotów. GUI odróżnia brak
przydziału Windows od fizycznego RAM. PNG, pojedynczy zapisujący GPKG, anulowanie i kontynuacja pozostają; bez nowych zależności.

Sześć błędnych map zwracało głównie HTTP 200 XML zamiast obrazu; dobra mapa tego samego
hosta działała. Nie pomijamy ich obszarów ani nie uznajemy błędów za puste mapy.
W izolowanym lokalnym benchmarku ACK czas dwóch map 14,704 → 2,633 s, przy identycznych
36 GetMap i bajtach PNG. To nie prognoza przyspieszenia całego projektu.
36 wektorów zwróciło 0 bez zarejestrowanych błędów; badanie 1.4 wykazało, że same
te liczniki nie potwierdzają poprawnego odczytu. 9 warstw empty ma obrazy na części zoomów.
Bez GPKG/QGZ nie wykonano niezależnego odbioru danych użytkownika.

Szczegóły, ograniczenia liczników sieci i wynik odbioru:
[validation-1.3.0.md](validation-1.3.0.md). Gotowy ZIP: 185/185 testów w 132,037 s,
bez pominięć, lokalny WMS i instalacja w QGIS poprawne. Ruff/format,
Flake8/pycodestyle, AST 37 plików, metadane/odnośniki/diff — OK;
zero sekretów, 11 dotychczasowych przejrzanych ostrzeżeń Bandit.
Pierwszy zestaw źródeł przerwano na nieaktualnej atrapie slotów startowych;
po poprawie 5 testów odzyskiwania i pełny zestaw ZIP-a przeszły.
Paczka 129 962 bajty, 22 pliki, powtarzalna SHA-256:
759a9c42a5ca2d7c6785ecc4007541e50daeefb5a01fd78b73c3e2e76a218a6c.
Wydanie przygotowane lokalnie;
bez publikacji, push, commitu lub zmiany widoczności repozytorium.
Instalować po zakończeniu eksportu i ponownie uruchomić QGIS.

## Pomiary 1.2.0

Po pytaniu o 9/9 procesów i 7 aktywnych zadań użytkownik zlecił zbieranie danych
do dalszych optymalizacji. Nie zlecił zmiany algorytmu obciążenia: limit nadal
wynika z CPU/RAM i polityki hostów, a audyt nie oznacza potwierdzenia maksimum
konkretnego komputera lub łącza. Wersja 1.2.0 dodaje obserwację, bez zmiany limitów,
timeoutów, retry, kontynuacji, formatu/PNG oraz zasad izolacji QGIS.

Natywny sampler co 5 s mierzy własny CPU/RSS/peak/I/O głównego QGIS i procesów map,
a główny także CPU/RAM systemu i wolne miejsce. Działa w osobnym wątku bez obiektów
QGIS, również podczas blokującego odczytu. Loguje fazy i kończy wątek przy zamknięciu.
Próbka koordynatora co 5 s zachowuje pełne obliczenie budżetu, stan zadań i hostów,
również bez zmiany limitu. Plan i końcowe podsumowania używają indeksów/zadań
technicznych, bez nazw warstw, źródeł i współrzędnych. Sam diagnostic.jsonl zwykle
wystarczy do analizy wydajności; manifest do nazw i pełniejszej oceny danych.

Sieć: interwały przy postępie i na końcu, rozmiary dostępnych odpowiedzi osobno
od deklaracji Content-Length, cache/unknown, opóźnienia i błędy. Brak odczytu to
null, nie zero. Logi workerów dołączane po ich zakończeniu. Pomiary lokalne,
bez automatycznej wysyłki, nowych zależności lub dodatkowych żądań testowych.

Nie mylić procesowego CPU 100% (jeden logiczny CPU) z systemowym CPU 0–100%.
Windows I/O to wszystkie transfery procesu, nie fizyczna zajętość dysku;
Linux I/O rodzica zawiera również odebrane przez wait procesy potomne — nie
sumować main+worker wprost. Bajty odpowiedzi QGIS nie są ruchem na całym łączu.
Windows commit nie oznacza wielkości swap. Szczegóły: [architecture.md](architecture.md).
Wyniki i paczka: [validation-1.2.0.md](validation-1.2.0.md).
Końcowy pełny odbiór ZIP-a: 165/165 testów, 120,443 s, bez pominięć.
Ruff/format, Flake8/pycodestyle, AST 36 plików, zgodność i powtarzalność paczki
poprawne; skan sekretów bez trafień, Bandit nadal 11 przejrzanych ostrzeżeń.
W pierwszym przebiegu źródeł poprawiono tylko test zależny od liczby odczytów
zegara; testy polityki i pełny zestaw z ZIP-a potwierdziły zachowanie reguły.
Paczka 127 452 bajty, 22 pliki; SHA-256:
e36533b016d0efad0599085a0dc92fb56f239bb8df5c688d2b753cacd35a691a.
Nie wykonywano publikacji, push ani zmiany widoczności repozytorium.
Nie instalować aktualizacji podczas trwającego eksportu; do kolejnej próby
zainstalować nowy ZIP i ponownie uruchomić QGIS.

## Kontynuacja 1.1.0 i analiza ponowienia

Użytkownik dostarczył wynik retry 1.0.0, świadomie anulowany po 6 h 11 min 19 s.
158 wybranych warstw: 1 saved, 113 empty, 2 partial, 13 failed, 29 cancelled;
53 wcześniejsze saved wykluczono. Stare pliki z `(1)` nie są już dostępne;
porównanie opiera się na zachowanych wynikach poprzedniej analizy i nazwach warstw.
Z wcześniejszych 11 partial 10 nie ma już braków; braki tej grupy spadły 2352→3.
Z wcześniejszych 37 failed pięć pobrano bez braków, cztery nadal failed, 28 anulowano.
Druga próba pogorszyła dziewięć innych warstw oraz dała nowy partial z 1130 brakami.
Oba archiwa 1.0.0 należy zachować — nie są automatycznie połączone.

W nowym logu maksimum 10 procesów, host PIG doszedł do 7. Budżet RAM 1→10,
na końcu 5; wolna pamięć około 1,53–4,55 GiB. 117 procesów zakończyło się kodem 0,
dwa kodem 2 przy anulowaniu; koordynator bez awarii. To nie jest pomiar CPU ani
wykorzystania całego łącza. Do analizy wystarczają zwykle manifest i diagnostic;
HTML powiela manifest, AUX nie potwierdza danych. Pełny folder jest potrzebny
do wznowienia lub niezależnego sprawdzenia GPKG/QGZ. Zero obiektów wektora przy
poprawnym odczycie bez błędów już jest prawidłowym saved, bez ponowienia.

Użytkownik zlecił obsługę kontynuacji po anulowaniu. Przyjęto prosty etap na poziomie
ukończonych warstw; zapytanie o dokładniejsze zachowanie kafelków pozostało bez odpowiedzi.
API resume_from i przyciski PL/EN kopiują zweryfikowane dane do nowego folderu,
zachowują saved/empty i ponawiają failed/cancelled/partial. Jeśli próba partial
nie zostanie ukończona, zachowują poprzedni partial. Kontynuacja działa również
po ponownym otwarciu oryginalnego projektu. Sprawdza zakres/ID/dostawców oraz
odciski źródeł i stylów od 1.1.0; legacy 1.0.0 bez pełnej weryfikacji ustawień.
Niezapisane edycje blokują kontynuację; zwykły nowy eksport nadal je zachowuje.
Nie odzyskuje usuniętych kafelków ani katalogu roboczego po awarii. Nie zmieniono
algorytmów obciążenia, timeoutów, PNG i zasad izolacji QGIS. Bez nowych zależności.
Wyniki odbioru i paczka: [validation-1.1.0.md](validation-1.1.0.md).
Źródła: 140/140 (120,266 s), zainstalowany ZIP: 140/140 (117,960 s), bez pominięć.
Ruff, format, Flake8/pycodestyle, AST, skan sekretów i powtarzalność ZIP-a — OK.
Bandit nadal 11 przejrzanych ostrzeżeń, bez nowych kategorii. Paczka 119 873 bajty,
22 pliki; SHA-256: 39b16b8afbe4af437b1c452268e59fc08b875ea795302a5e7c34475a700b96bd.
Nie publikowano ani nie zmieniano widoczności repozytorium.

## Analiza 12 września — bez zmian algorytmów

Użytkownik dostarczył raport, manifest, diagnostykę i AUX z pełnego eksportu
1.0.0 na Windows 11 (Core Ultra 5 135U, 16 GB RAM), wykonanego 11 września
08:58–21:57: 12 h 59 min 22 s, zoomy 0–20. Statusy 211 warstw: 53 saved,
110 empty, 11 partial, 37 failed. Wszystkie 137 procesów zakończyło się kodem 0,
bez awarii koordynatora; 1489 krótkich konfliktów IPC odzyskano. Same AUX nie
potwierdzają danych: nie dostarczono GPKG ani QGZ do niezależnego sprawdzenia.

Wykryto 14 logicznych CPU, sufit 28 procesów, budżet RAM do 13; z par start/exit
wynika maksymalnie 12 uruchomionych procesów i średnio 3,70 (z oczekiwaniem).
Ostatnie około 2 h pracował jeden proces przy budżecie 8–9 i wolnym RAM około
4,5–5 GiB. Pomiar szczytu pracownika 310,7 MiB, estymata 466,1 MiB. Logi nie
mierzą wykorzystania CPU, transferu ani dysku. Po błędach limity hostów pozostają
zamrożone do końca eksportu, również po poprawnym powrocie; to ograniczenie
adaptacji przy długich przebiegach, nie dowód zmierzonego maksimum serwera.

37 failed wynika z odłożenia dwóch hostów, w tym 35 map nie uruchomiono. 11 partial
ma 2352 brakujące kafelki. Automatyczna naprawa odzyskała 4448 kafelków w 4842
próbach. Ręczny retry domyślnie wybiera 158 warstw (failed+partial+empty), tworzy
nowe archiwum całych warstw; 44 ze 110 empty mają treść na części zoomów.

Wszystkie 33 MSSQL i 3 WFS mają saved, ale 0 obiektów. Zapytania źródłowe zwróciły
zero bez błędów, jeszcze przed maskowaniem/zapisem. Użytkownik nie wie, czy w tym
obszarze powinny być obiekty, i sprawdzi to w oryginale. Te warstwy nie są zaznaczane
przez retry. Nie uznawaj tego za rozstrzygnięty błąd ani pełny odbiór wektorów.

Na etapie pierwszej analizy użytkownik prosił wyłącznie o analizę i propozycje.
Poza zleconą później kontynuacją nie wdrażać optymalizacji bez kolejnego zlecenia.
Kandydaci: oddzielić retry failed/partial
od przeglądu empty, zbadać ostrożny powrót do zwiększania limitu po długiej serii
sukcesów oraz porównać natywny timeout QGIS 5 s z dłuższym na małej próbie.
Nie podnosić sufitów ani nie przebudowywać architektury bez pomiaru korzyści.
Archiwum wejściowe i surowe logi pozostały poza repozytorium.

## Zakres zakończonej pracy

Użytkownik potwierdził działanie 0.9.7 i zlecił porządki oraz przygotowanie 1.0.0
zgodnie z wymaganiami plugins.qgis.org. Nie zlecił publikacji ani zmiany widoczności
GitHub. Repozytorium było czyste na commicie 41f4d02 przed rozpoczęciem tego etapu.

- Proste README PL/EN: zastosowanie, wymagania, instalacja, obsługa, automatyczna
  równoległość, prawa do warstw i usług, odpowiedzialność oraz jawny vibe coding.
- Ogólna instrukcja użytkownika PL/EN zamiast historii prób firmowych; uporządkowany
  indeks dokumentacji. Raporty historyczne zachowano jako zapis konkretnych wydań.
- Metadane 1.0.0: angielski opis, zatwierdzony adres autora, GPL-2.0-only,
  angielskie tagi, zwięzły changelog, stable, zakres QGIS 3.40–3.99 (Qt5).
- Usunięto opcjonalne category=Raster: akcja całego projektu pozostaje w Plugins.
  Dodano stabilny objectName akcji; nazwa produktu i techniczny ID bez zmian.
- Oznaczenia SPDX w Pythonie i własnych SVG. LICENSE pozostała GNU GPL v2;
  nie zmieniano licencji na wariant „or later”. Licencja nie obejmuje cudzych danych.
- Kontrole metadanych, rozmiaru, ścieżek, praw i zawartości dodano do istniejącego
  testu ZIP-a. Bez nowego frameworka, zależności wtyczki i przebudowy pobierania.

Źródła: **128/128 testów**, 115,662 s, bez pominięć (WMS i proxy wykonane).
ZIP: **128/128 testów**, 110,253 s, bez pominięć; instalacja i metadane poprawne.
Ruff, formatowanie, Flake8/pycodestyle (88 znaków, E203 wyjaśnione), AST,
zgodność plików i powtarzalność paczki — OK. Skan ZIP-a bez sekretów;
11 przejrzanych ostrzeżeń Bandit, zero trafień Critical według obecnych reguł portalu.
Paczka: 112 827 bajtów, 22 pliki. SHA-256:
b85dcda24aff10776b0da2f0ee7943f3db02efdbab3224095522f90c2746c22e.
Szczegóły: [validation-1.0.0.md](validation-1.0.0.md).

## Stan publikacji

GitHub potwierdza **PRIVATE**. Publiczne odnośniki z metadanych zwracają 404.
Źródła odpowiadające paczce muszą być publiczne przed zgłoszeniem do QGIS.
Nie wykonano zmiany widoczności, push, tagu, GitHub Release ani wysłania do portalu.
Upublicznienie repozytorium ujawnia również historię; wymaga decyzji właściciela.
Instrukcja opiekuna wydania i sprawdzone wymagania: [publishing.md](publishing.md).
Sam ZIP i pozytywne testy nie oznaczają zatwierdzenia przez moderatorów.

## Działanie i granice potwierdzonych wyników

Automat zachowuje budżet 0.9.7, z poprawkami reakcji i ponawiania wzrostu z 1.3.0:
od jednego zadania na host, wzrost po poprawnych
pobraniach i pomiarze przepustowości; min(32, 2 × CPU), ograniczany dostępnym RAM.
Zużycie procesu pochodzi z natywnego RSS/peak, z zapasem 50% i minimum 384 MiB;
768 MiB pozostaje rezerwą. Przed pomiarem estymata 1 GiB. To heurystyka, nie dowód
maksimum wydajności komputera albo serwerów. Jedna mapa nadal zajmuje jeden proces.

W kontrolowanym porównaniu 0.9.6→0.9.7 przy ograniczonej pamięci: 190,378→80,609 s,
jeden→cztery procesy jednego hosta, identyczne PNG. Cztery nie są limitem kodu.
[Raport 0.9.7](validation-0.9.7.md), [pomiary](benchmark-0.9.7.json).

Zweryfikowane środowisko: Ubuntu, QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4.
QGIS 4/Qt6 nieobsługiwany. Pełny odbiór Windows/macOS wymaga tych systemów;
testy atrap Windows nie zastępują natywnych prób. Ubuntu nie ma dostępu do sieci
firmowej/MSSQL — nie pytaj ponownie o poświadczenia. Pozostają specyficzne dla
stanowiska próby proxy, danych, formularzy, relacji i wyglądu kopii bez sieci.
Wcześniejsza przyczyna trzech pustych firmowych WFS nie została rozstrzygnięta;
nie myl ich z dwoma poprawnymi WFS z późniejszego archiwum. Szczegóły w raportach
[0.9.5](validation-0.9.5.md) i [0.9.6](validation-0.9.6.md).

## Gdzie szukać szczegółów

Trwałe reguły pracy: [AGENTS.md](../AGENTS.md). Nie zmieniaj oryginału projektu,
nie przekazuj żywych QGIS między wątkami/procesami, zachowaj PNG RGBA i jednego
zapisującego końcowy GeoPackage. Szczegóły: [architecture.md](architecture.md).
Polecenia testów i budowy: [development.md](development.md).
Instrukcja użytkownika: [team-guide.md](team-guide.md), pakowana jako INSTRUKCJA.md.
Kod: mbtiles_batch_exporter/. Paczki i sumy: ignorowany dist/. Bieżące wyniki
zapisuj w raporcie wydania; nie dopisuj tu pełnej historii wcześniejszych prób.
