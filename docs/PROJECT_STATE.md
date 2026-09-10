# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 10 września 2026. Wersja **1.0.0**, przygotowanie do katalogu QGIS.

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
