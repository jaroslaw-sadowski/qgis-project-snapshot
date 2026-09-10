# Odbiór QGIS Project Snapshot 0.9.7

Data: 10 września 2026. Wydanie do instalacji z ZIP-a; bez publikacji GitHub
Release ani w katalogu QGIS. Lokalne testy Ubuntu nie zastępują odbioru firmowego
Windows, MSSQL i zależności projektu bez sieci.

## Przyczyna i poprawka

W obserwowanym przebiegu 0.9.6 działał jeden proces, mimo kolejki dziewięciu map
i poprawnych odpowiedzi serwera. Przy około 2,2 GiB dostępnego RAM stara rezerwa
2 GiB oraz stała estymata 1 GiB blokowały drugi proces. Odczyt systemowy wykazał
około 305 MiB RSS procesu mapowego. To ograniczenie przyjętej polityki pamięci,
nie zmierzony sufit serwera.

0.9.7 pozostawia rezerwę 768 MiB i po renderowaniu mierzy bieżący oraz szczytowy
RSS procesów. Koszt nowego procesu to większa z wartości 384 MiB i szczyt z 50%
zapasem; przed pierwszym pomiarem pozostaje 1 GiB. System odczytuje pamięć
natywnie: Linux przez /proc/self/status, Windows przez GetProcessMemoryInfo,
inne Unix przez resource. Nie dodano zależności.

Oddzielny zapas uwzględnia wzrost pamięci aktywnych procesów oraz rozruch tych,
które jeszcze niczego nie wyrenderowały. Spadek RSS nie kasuje rezerwy na ponowny
wzrost, a szczyt pozostaje znany również po zakończeniu mapy. Główny QGIS nie służy
do szacowania kosztu pracownika. Próbka RAM co 5 s przyznaje skończoną liczbę
nowych startów; presja pamięci wstrzymuje kolejne, pozwalając aktywnym dokończyć.
Nagły wzrost pamięci może przekroczyć zapas — pomiar pozostaje heurystyką.

Automat serwera nadal zaczyna od jednego zadania i zwiększa limit po poprawnych
pobraniach, gdy dostępne zasoby oraz mierzona przepustowość pozwalają na wzrost.
Nie wprowadzono limitu czterech na serwer. Sufit to min(32, 2 × CPU), ograniczony
RAM, kolejką i reakcją serwera. Pojedyncza warstwa nadal zajmuje jeden proces.

Podpowiedź RAM PL/EN pokazuje estymatę procesu i informację, czy pochodzi z pomiaru.
Wydanie zawiera wcześniejsze poprawki nazwy **QGIS Project Snapshot**, kolejki
**Warstwy w kolejce / Queued layers**, pomiaru przepustowości i odmowy proxy 407.
Zachowano jakość PNG RGBA, osobne zoomy, jednego zapisującego GeoPackage,
niezapisane edycje, reguły anulowania i ograniczenia serwerów.

## Kontrole

Ubuntu, QGIS 3.40.15, GDAL 3.12.2, Python 3.14.4, Qt 5.15.18, PyQt 5.15.11.
Izolowane profile i katalogi testowe; bez zmian projektu lub profilu użytkownika.

Źródła: **128/128 testów**, 107,487 s, bez pominięć, w tym WMS i proxy.
Gotowy ZIP: **128/128 testów**, 116,790 s, bez pominięć. Natywne wykrywanie,
ładowanie, okno archiwizacji PL/EN i wyłączenie wtyczki — OK. Testy oraz procesy
mapowe używały modułów z rozpakowanej paczki, bez instalacji w profilu użytkownika.

- Siedem nowych testów odczytu pamięci obejmuje natywny Linux, jednostki Unix,
  błędy odczytu oraz rozmiary struktury i uchwytu Windows. Windows jest tu
  sprawdzony za pomocą atrap API, nie rzeczywistego systemu Windows.
- Sześć nowych testów koordynatora i rzeczywistych plików IPC obejmuje trzy
  zadania jednego hosta przy 2,2 GiB i procesach 305 MiB, wolny rozruch,
  utrzymanie rezerwy po spadku RSS, wyłączenie głównego QGIS z estymacji,
  brak odczytu RAM oraz wzrost kosztu procesu podczas pracy.
- Pozostały zestaw sprawdza dane, relacje, zasoby, zapis i odczyt QGIS/GDAL,
  PNG RGBA, timeouty, ograniczenia serwera, proxy, anulowanie i tłumaczenia.
- Ruff 0.16.6: reguły E/W, F, I i formatowanie — OK, 57 plików według Ruff.
  Limit 88 znaków jest jawnym odstępstwem od ścisłych 79 znaków PEP 8.
- Kontrola AST: 33 pliki Python — OK. git diff --check — OK.
  Brak skonfigurowanego osobnego typecheckera.
- Przegląd według [Ponytail](https://github.com/dietrichgebert/ponytail/blob/main/AGENTS.md):
  poprawa istniejącego planowania i pomiaru zasobów, natywne API, brak nowych
  bibliotek, dodatkowego systemu konfiguracji i niepowiązanej przebudowy.

## Pomiar przy ograniczonej pamięci

Sześć map jednego lokalnego WMS, obszar 1,2 km × 1,2 km w EPSG:2180, zoom 18,
opóźnienie odpowiedzi 120 ms, CPU 4. W obu próbach startowo dostępne 2,5 GiB.
Każdy późniejszy odczyt dostępnego RAM odejmuje rzeczywisty RSS uruchomionych
procesów od tej samej wartości początkowej. Monitor odczytuje /proc co 0,1 s.
Pomiar procesu we wtyczce jest natywny, bez podstawiania wartości RSS lub szczytu.
To kontrolowany model dostępnej pamięci, nie pomiar całego pulpitu użytkownika.

| Wersja | Czas | Maks. procesów / równoczesnych GetMap | GetMap |
| --- | ---: | ---: | ---: |
| 0.9.6 | 190,378 s | 1 / 1 | 1014 |
| 0.9.7 | 80,609 s | 4 / 4 | 1014 |

Identyczne bajtowo PNG wszystkich sześciu map, poprawny lokalny odczyt,
brak awarii koordynatora. Wzrost hosta: dwa procesy po 16,06 s, trzy po 33,60 s,
cztery po 51,15 s. Czas krótszy o 57,66%, stosunek 2,36×. Suma RSS głównego
procesu i pracowników wzrosła z około 520 do 1294 MiB; współdzielone strony
są liczone osobno dla każdego procesu. Największy zmierzony szczyt pracownika
w 0.9.7 wyniósł około 258 MiB, a estymata z zapasem około 387 MiB.

Jedna próba na wersję, identyczny scenariusz. Wynik potwierdza rzeczywistą
równoległość przy ograniczonym RAM; nie gwarantuje takiego przyspieszenia usług
użytkownika. Cztery to zaobserwowane maksimum w tej próbie, nie stały limit.
[Pełne wyniki porównania](benchmark-0.9.7.json).

## Paczka i odbiór

- dist/qgis-project-snapshot-0.9.7.zip: 112 229 bajtów, 22 pliki.
- SHA-256: 7c0220ddb630cd15231677705a0f6c3e56e145ddb8cc889760939e5b9c4b19c2.
- CRC i zgodność każdego pliku ZIP-a ze źródłem — OK.
- Ponowna budowa w katalogu tymczasowym dała identyczny ZIP bajt po bajcie.
- Instrukcja instalacji i odbioru jest w paczce jako INSTRUKCJA.md.

Przed użyciem poprawki należy zainstalować nowy ZIP i ponownie uruchomić QGIS.
Trwający eksport używa wcześniej załadowanej wersji; nie podmieniano go w locie.
Pozostaje ręczny odbiór na firmowym Windows z istniejącym proxy i MSSQL,
porównanie wyglądu oraz pełnych zależności kopii bez sieci. Ubuntu nie ma dostępu
do sieci firmowej; nie proszono ponownie o poświadczenia.
