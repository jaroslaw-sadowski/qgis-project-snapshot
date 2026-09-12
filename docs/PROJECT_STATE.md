# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 12 września 2026. Wersja **1.2.0**, diagnostyka wydajności.

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

Automat 0.9.7 pozostaje bez zmian: od jednego zadania na host, wzrost po poprawnych
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
