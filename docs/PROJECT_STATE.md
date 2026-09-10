# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 10 września 2026. Wersja: **0.8.1**.
Gotowa i automatycznie sprawdzona paczka do testu służbowego. Pełnego odbioru
źródeł firmowych nie wykonano. Sprawdź `git status` i historię przed pracą;
nie zakładaj, że zmiany zostały zatwierdzone lub wysłane.

## Cel i trwałe ustalenia

Zespół archiwizuje stan projektu QGIS na dany dzień: kopia projektu z zachowaną
strukturą, kolejnością, identyfikatorami warstw, stylami i lokalnymi danymi.
Ważne są długie pasy inwestycji, przezroczystość i bezstratna kompresja PNG
(ZLEVEL 9), osobne renderowanie zoomów oraz wykorzystanie wielu CPU.
Oryginalny eksporter MBTiles pozostaje osobną funkcją.

Nie modyfikuj projektu źródłowego ani jego niezapisanych edycji. Nie blokuj sygnału
writeProject QGIS (utrata relacji). Nie przekazuj obiektów QGIS między wątkami
lub procesami; każdy proces tworzy własne środowisko. Końcowy GeoPackage ma
jednego zapisującego. Wyniki częściowe/puste nie są bezwarunkowym sukcesem;
sprawdzenie lokalnych ścieżek nie stanowi pełnej gwarancji działania offline.

## Bieżąca funkcjonalność

Dotychczas: wektory i mapy w GeoPackage, rastry źródłowe w GeoTIFF, maska obszaru,
zasoby projektu, formularze/relacje, szczegółowy postęp i raport HTML, PL/EN
według języka QGIS, szacunkowy czas i rozmiar oraz czerwone ostrzeżenia serwera.

W 0.8.0 okno korzysta wyłącznie z automatyki. Ręczne wybory procesów i limitu
serwera oraz przycisk rekomendacji zastępuje tabela hostów i rzeczywiste
wykorzystanie procesów. Tabela pozostaje dostępna podczas eksportu.

- Start od jednej mapy na host; wzrost o jeden po co najmniej 15 s i 10 sukcesach,
  gdy jest kolejka i miejsce. Dwa okna bez 10% poprawy powodują cofnięcie
  i zatrzymanie wzrostu. Sufit osiem map na host.
- HTTP 429/503 i trzy kolejne timeouty ograniczają host; Retry-After (sekundy/data)
  lub przerwy 30/60/120 s. Po przerwie jedna próba brakującego kafelka.
  Trzy nieudane próby powrotu albo oczekiwanie ponad pięć minut odkładają host.
  Inne hosty pracują dalej; 503 nie przesądza przyczyny niedostępności.
- Globalny budżet: minimum z 32, 2 × CPU i RAM przy rezerwie 2 GiB oraz
  1 GiB/proces; nieznany RAM ogranicza do dwóch. RAM sprawdzany co pięć sekund;
  niska pamięć zatrzymuje wzrost i uruchamianie nowych procesów.
- Dyskowy rejestr SQLite każdej mapy pamięta także poprawne przezroczyste kafelki.
  Początkowe pobranie i najwyżej dwie dodatkowe rundy uzupełniają tylko braki
  w tym samym archiwum. Udane fragmenty nie są pobierane ponownie.
- Manifest ma wersję 4 i historię automatu, przerw, pamięci oraz napraw.
  Nie zapisuj poświadczeń ani pełnych adresów usług w tej diagnostyce.

Sterowanie dotyczy zadań mapowych, nie dokładnej liczby HTTP/s. Automat jest
heurystyką, nie pomiarem przepustowości ani gwarancją maksymalnej szybkości.
Nie testuje serwera dodatkowymi żądaniami. Standardowe ograniczenia OSM obowiązują.

## Punkty wejścia dla implementacji

- `adaptive.py`: HostPolicy, atomowe pliki protokołu 1 i WorkerGate.
- `parallel_archive.py`: istniejąca kolejka, niezależny koordynator co 0,5 s,
  sprawiedliwy przydział hostów, RAM, bramki dla procesów i głównego QGIS.
- `raster_archive.py`: obserwacja błędów HTTP, bramka przed renderowaniem,
  rejestr kafelków i uzupełnianie bez odtwarzania tabeli.
- `archive_worker.py`: izolowane QGIS, statystyki i zamykanie bramki.
- `archive.py`: `create_archive(adaptive=False, server_activity=...)` zachowuje
  zgodny tryb stały API. Okno przekazuje `adaptive=True`.
- `archive_dialog.py`: odczyt stanu hostów, PL/EN, anulowanie, wynik i ostrzeżenia.

Awaria procesu/brak interpretera w trybie adaptacyjnym nie może powodować
ponowienia w głównym QGIS z pominięciem limitów. Mapy wymagające głównej ścieżki
(np. authcfg) używają wspólnej bramki. Nie zwiększamy równoległości MSSQL,
wektorów z edycjami ani rastrów źródłowych. Czekające procesy liczą się do RAM.
Prywatne rejestry są usuwane po pracy; manifest zachowuje podsumowanie.

Uczenie i automatyczna naprawa dotyczą wyłącznie bieżącego eksportu: brak
pamięci limitów między uruchomieniami i wznawiania po zamknięciu QGIS.
Ręczny przycisk ponowienia na końcowym ekranie zaznacza failed/cancelled/empty/partial,
odznacza saved/excluded i tworzy **nowe** archiwum wybranych warstw.

Tłumaczenia: `i18n.py`, katalog Qt `en.ts` + `en.qm` (345 tłumaczeń).
Po zmianach tekstów uruchom lrelease i testy zgodności szablonów.
Szacunki na jedną mapę nadal używają modelu 0,2–2 s i 10–250 KiB PNG/kafelek;
nie są pomiarem ani gwarantowanymi granicami. Nie dziel czasu jednej mapy przez CPU.

## Opisy i ikony 0.8.1

README PL i osobny README.en.md opisują zastosowanie, obsługę, przepływ danych,
ograniczenia i wykonane kontrole. Metadane QGIS mają opisy PL/EN, autora,
repozytorium, zgłoszenia, tagi i changelog. Wzorem redakcyjnym było repozytorium
`jaroslaw-sadowski/qgis-poprawka-odwzorowawcza`; nie przenosiliśmy deklaracji
jego kontroli bezpieczeństwa ani obsługi QGIS 4 do naszego produktu.

Piktogram mapy w pudełku: `icon.svg` (metadane, pasek, akcja i okno archiwizacji).
Drobne autorskie SVG `cpu.svg` i `ram.svg` oznaczają procesy i rezerwę pamięci;
pozostałe przyciski używają natywnych ikon QStyle. Budowa pakuje SVG, poprzedni
nieużywany icon.png usunięto. Nie potrzeba nowych zależności. RAM w oknie to
wyraźnie opisana rezerwa 2 GiB, nie wskaźnik bieżącego zużycia pamięci.

## Zweryfikowany wynik

- `dist/qgis-project-snapshot-0.8.1.zip`: 104 679 bajty, 22 pliki.
- SHA-256: `8e37c1e8d6fbc6913ed6494de821f81fbdaa93f86499092bf74d0392119bd5c1`.
- **65/65 testów końcowego ZIP-a**, bez pominięć, QGIS 3.40.15,
  GDAL 3.12.2, Python 3.14.4, PyQt5, Ubuntu; testy Qt offscreen.
- Benchmark sześciu map/dwóch lokalnych hostów: stały 57,706 s, automatyczny
  58,323 s; po 1014 żądań, identyczne PNG, maksimum cztery procesy.
  To pomiar syntetyczny, nie dowód przyspieszenia w produkcji.
- Szczegóły: [odbiór 0.8.1](validation-0.8.1.md),
  [benchmark](benchmark-0.8.0.json). Starsze odbiory pozostają historyczne.

Budowa: `python3 scripts/build_plugin.py`; dist jest ignorowany przez Git.
Po zmianie plików pakowanych przebuduj ZIP i ponów odbiór. Źródło prawdy:
`mbtiles_batch_exporter/`, wersja w `metadata.txt`. Identyfikator instalacji
pozostaje `mbtiles_batch_exporter` dla zgodności aktualizacji; nazwa widoczna
to qgis-project-snapshot. Nie opublikowano GitHub Release ani wydania w katalogu QGIS.

## Ograniczenia i następny krok

MSSQL użytkownika działa tylko w sieci firmowej; tutaj nie ma DNS/dostępu,
a trzy rastry projektu są nieobecne. Nie zgaduj adresów i nie proś ponownie
o poświadczenia bez zmiany warunków. Windows nie został odebrany.

Następny krok: test służbowy według [instrukcji zespołu](team-guide.md), obejmujący
MSSQL, lokalne rastry, uwierzytelnianie, wszystkie warstwy, długi pas, style,
etykiety, formularze, relacje i wydruki, a następnie odczyt bez sieci.
Nie wszystkie zależności wyrażeń, fonty i dowolny kod formularzy są pakowane;
relacje mogą wskazywać obiekty spoza obszaru. Anulowanie zachowuje ukończone,
scalone warstwy; prywatne dane nieukończonych map są sprzątane.

Mapa architektury: [architecture.md](architecture.md). Polecenia testów i budowy:
[development.md](development.md). Reguły współpracy: [AGENTS.md](../AGENTS.md).
Przy zgłoszeniu braku postępu analizuj rzeczywisty dziennik i stany procesów;
nie zastępuj ich sztucznym procentem. Nie dodawaj nieuzgodnionych funkcji.
