# Odbiór QGIS Project Snapshot 0.9.6

Data: 10 września 2026. Paczka do instalacji lokalnej; nie opublikowano GitHub
Release ani wydania w katalogu QGIS. Testy Ubuntu nie zastępują odbioru firmowego
Windows, MSSQL i zależności projektu bez sieci.

## Przyczyna i zakres zmian

Próba użytkownika 0.9.5 trwała 47 min 35,44 s. Początkowe CPU 4 i 4,66 GiB
wolnego RAM dawały dwa procesy; po 55,39 s przy 3,60 GiB stara reguła dopuszczała
już tylko jeden. Oba hosty zachowały limit 1, bez zamrożenia i błędów koordynatora.
Wszystkie 11601 zarejestrowanych odpowiedzi GetMap miały HTTP 200 / Qt 0.

MemAvailable już uwzględnia pamięć działających procesów. 0.9.6 przyznaje
z wolnego RAM po rezerwie 2 GiB miejsca dla kolejnych procesów po 1 GiB,
a istniejące procesy dolicza osobno. Każdy start zużywa miejsce przyznane
przez próbkę RAM; nowa próbka co 5 s odnawia przydział. Procesy w rozruchu
oraz czekające na serwer także są liczone. Nieznany RAM nadal ogranicza do 2,
minimum to 1; CPU i globalny sufit 32 pozostają. Presja RAM nie zabija gotowych map.

Usunięto stałe 2/host w automatyce. Host zaczyna od 1 i zwiększa limit o 1 po 15 s
pomiaru oraz 10 sukcesach, jeśli ma kolejkę i wolne zasoby. Pomiar zbiera tylko
okresy z docelową liczbą gotowych map. Rozruch kolejnej mapy wstrzymuje pomiar,
nie kasując wcześniejszych próbek; krótka przerwa pomiędzy publikacjami stanu
kafelków nie oznacza niegotowości. Dwa okna bez 10% zysku cofają limit i zamrażają
wzrost. Ograniczenia hosta przy 429/503/timeoutach i Retry-After zachowano.
Stałe API adaptive=False zachowuje dotychczasowe parametry i zachowanie.

Przegląd wykrył dodatkowo ponawianie odrzuconego dostępu proxy na każdym
następnym kafelku. Teraz pierwszy 407 kończy pobieranie bieżącej mapy,
zachowując ukończone PNG. Wynik to failed albo partial z jawnym powodem,
stop_http_status=407 i stopped_early=true; nie udaje sukcesu ani odłożenia hosta.
401/403/404 zachowują dotychczasowe reguły kafelków.

Widoczna nazwa: **QGIS Project Snapshot**. Techniczny ID mbtiles_batch_exporter
oraz prefiks ZIP pozostają dla zgodności aktualizacji. **Warstwy w kolejce /
Queued layers** i podpowiedzi wskazują serwer danego wiersza. Stan **Limit
procesów komputera / Computer process limit** pokazuje lokalne ograniczenie.
PL/EN skompilowano do en.qm (280 wpisów).

## Testy i kontrole

Ubuntu: QGIS 3.40.15, GDAL 3.12.2, Python 3.14.4, Qt 5.15.18, PyQt 5.15.11.
Izolowane profile QGIS i tryb offscreen; konfiguracja użytkownika bez zmian.

Źródła: **115/115 testów**, 102,161 s, bez pominięć (w tym lokalny WMS i proxy).

Pierwszy pełny przebieg: 115 testów, dwa błędy scenariuszy anulowania.
Wspólna funkcja testów ustalała RAM tylko przy starcie, pozostawiając późniejsze
próbki zależne od pulpitu (około 2,4 GiB dostępnego RAM). Ustalono również próbki
bieżące, zgodnie z zamiarem tych testów. Nie zmieniono ich asercji; presję RAM
sprawdzają osobne testy kontrolujące pamięć i czas.

Gotowy ZIP: **115/115 testów**, 103,852 s, bez pominięć. Natywne wykrywanie,
ładowanie, otwarcie okna PL/EN i wyłączenie wtyczki poprawne. Sprawdzono, że
moduły testów i procesów pochodzą z rozpakowanej paczki.

- Ruff 0.16.6: E/W (pycodestyle), F, I oraz formatowanie całego repozytorium — OK.
  Limit 88 znaków jest jawną konwencją projektu zamiast ścisłego 79 z PEP 8.
- Kontrola AST 31 plików Python, git diff --check, powtarzalność ZIP-a bajt po bajcie, CRC i zgodność każdego
  zapakowanego pliku ze źródłem — OK. Brak skonfigurowanego osobnego typecheckera.
- Regresje obejmują wzrost 1→2→3 mimo 3,60 GiB wolnego RAM, zachowanie działających
  procesów przy presji pamięci, nieużywanie próbki RAM dwukrotnie, rozruch,
  zmianę mapy i stan między publikacjami kafelków, ograniczenie bez przyspieszenia,
  407 od pierwszego kafelka i 407 po zapisanym PNG, prawdziwy WMS oraz proxy.
- Pozostały zestaw sprawdza oryginał i niezapisane edycje, relacje, lokalne zasoby,
  maski, wielopoziomowy PNG RGBA, anulowanie, gotowe mapy, timeouty i blokady IPC.
- Przegląd [Ponytail](https://github.com/dietrichgebert/ponytail/blob/main/AGENTS.md):
  naprawa przyczyny we wspólnym mechanizmie, wykorzystanie istniejącego schedulera,
  Pythona i QGIS, brak nowych zależności oraz warstw abstrakcji. Zachowano
  architekturę i testy projektu; zalecenia stylistyczne nie zastępują kontroli danych.

## Pomiar wydajności

Kontrolowany lokalny WMS, sześć map jednego hosta, kwadrat 1,2 km, EPSG:2180,
zoom 18, opóźnienie odpowiedzi 120 ms. Obie próby mają identyczne wymuszone zasoby:
CPU 4, początkowo 4,66 GiB, kolejne odczyty dostępnego RAM 3,60 GiB. To sprawdzenie
wpływu polityki, nie pomiar przepustowości usług użytkownika ani statystyczny benchmark.

| Wersja | Czas | Maks. procesów / równoczesnych GetMap | Żądania GetMap |
| --- | ---: | ---: | ---: |
| 0.9.5 | 174,060 s | 1 / 1 | 1014 |
| 0.9.6 | 79,786 s | 4 / 4 | 1014 |

PNG wszystkich sześciu map są identyczne bajtowo w obu próbach. Kontrola lokalnych
źródeł przeszła. Wzrost limitu w 0.9.6: 2 po 16,07 s, 3 po 33,61 s, 4 po 50,66 s.
Czas krótszy o 54,2%, stosunek 2,18×. Największy zaobserwowany RSS pojedynczego
procesu wyniósł około 258,2 MiB; suma RSS głównego procesu i pracowników wzrosła
z 519,3 do 1293,1 MiB. Suma liczy współdzielone strony osobno w każdym procesie.

Pierwsza wersja poprawki dawała 106,565 s i 2 procesy. Ten pomiar wykrył zerowanie
okna przy częstych zmianach map; poprawiono przyczynę i dodano regresję przed
pomiarem końcowym. [Wyniki końcowego porównania](benchmark-0.9.6.json).
Pojedyncza warstwa pozostaje jednym procesem; automat zwiększa równoległość
pomiędzy mapami, w granicach zasobów. Nie gwarantuje maksymalnej szybkości
każdego serwera ani konkretnego przyspieszenia w projekcie produkcyjnym.

## Kontrola archiwum użytkownika

Sprawdzono pliki tylko do odczytu, bez odpytywania usług, zmian w projekcie
użytkownika i kopiowania prywatnych danych do repozytorium. SQLite integralny,
brak błędów kluczy obcych i zgodność czterech sum SHA-256 manifestu. 5968 PNG 256²,
8-bit RGBA: poprawne CRC i dekompresja. Wszystkie 10 tabel rastra odczytuje GDAL;
macierze zawierają zoomy 13–20, a liczby obrazów zgadzają się z manifestem.
Dwa WFS zawierają 696 i 1022 obiekty bez błędów odczytu i zapisu.

Dziewięć empty oznacza jedną mapę całkowicie przezroczystą oraz osiem z treścią
na części zoomów. Nie ma failed/partial warstw. XML-e aux to statystyki pasm.
Te wyniki nie potwierdzają wszystkich zależności, zgodności wizualnej ani
przyczyny wcześniejszych trzech pustych WFS z innego przebiegu firmowego.

## Paczka

- dist/qgis-project-snapshot-0.9.6.zip
- 110 549 bajtów, 22 pliki.
- SHA-256: b38eb7c0b21a648e892cf661e7bd984d82e0c6f4c91af1f6180843bce79700c6.
- Instrukcja instalacji i odbioru jest dołączona jako INSTRUKCJA.md.

Pozostaje ręczny odbiór na firmowym Windows z istniejącym proxy i MSSQL
oraz porównanie archiwum bez sieci. Ubuntu nie ma dostępu do sieci firmowej;
nie proszono ponownie o dane dostępowe. Nie obniżono jakości map, nie zmieniono
oryginału i nie dodano zależności wymaganych przez instalowaną wtyczkę.
