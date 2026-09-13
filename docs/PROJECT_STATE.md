# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 13 września 2026. Pierwsze oficjalne wydanie **1.0.0**,
przygotowanie paczki dla QGIS 3/Qt5 i QGIS 4/Qt6. Numery 1.1–1.4 były
rozwojowe; ich raporty zachowano, ale nie oznaczają kolejnych oficjalnych wydań.

## Bieżący etap

Użytkownik zlecił audyt poligonu, a po pozytywnej ocenie gotowości kodu —
utworzenie GitHub Release i upublicznienie repozytorium. Obejmuje to commit,
push i tag wydania. Nie zlecił instalacji w profilu ani zgłoszenia do plugins.qgis.org. Git był czysty na początku tego etapu;
obecne zmiany dotyczą przygotowania oficjalnego wydania.

- Krótkie README i metadane: angielski przed polskim, wymagania i instalacja,
  automatyczna równoległość, licencje źródeł, AI/vibe coding i zakres testów.
- Prywatność opisana precyzyjnie: brak analityki i wysyłania do autora, ale
  wybrane usługi otrzymują niezbędny zasięg, parametry i uwierzytelnienie.
- Metadane 1.0.0, zakres 3.40–4.99, GPL-2.0-only, stable; bez wycofanego
  supportsQt6. Nazwa QGIS Project Snapshot, ID mbtiles_batch_exporter.
- Natywne wspólne API Qt5/Qt6, format enumów i numery błędów sieci.
  Poprawiono różnice XML ustawień projektu: względne ścieżki i usuwanie makr
  z kopii wynikowej oraz plików procesów, z zachowaniem oryginału.
- Obsługiwane stare i nowe natywne klucze proxy. Hasła nadal tylko w pamięci
  i stdin; bez kopiowania bazy uwierzytelniania i wyłączania TLS.
- `.flake8` w repozytorium i ZIP-ie: ta sama konwencja co Ruff, 88 znaków/E203.
  Bez nowych zależności produkcyjnych i bez zmiany algorytmu obciążenia.
- Testy nieoczekiwanych ostrzeżeń okna kończą się błędem zamiast wisieć.

Przed publikacją uzupełniono tagi: 17 EN, potem 13 PL. Sprawdzono metadane
i integralność nowego ZIP-a; porównanie potwierdziło zmianę wyłącznie pola tags.
Kod jest identyczny jak w paczce z pełnym odbiorem. Aktualna suma w raporcie.

**Odbiór kodu: 231/231 testów z ZIP-a w każdym runtime**, bez pominięć,
kody procesów 0. Qt5: 170,064 s; Qt6: 171,448 s. Ruff/format, Flake8, składnia
Python 3.10, linki i diff OK. Sekrety: 0 w kodzie i ZIP-ie. Kontroler Qt6: 0
niezgodności. Bandit: 20 przejrzanych ostrzeżeń, bez high/Critical. Paczka
143 179 bajtów, 23 pliki; powtarzalna budowa i zgodność wszystkich źródeł.
Samodzielny program odbioru zamyka QGIS przez exitQgis(), aby odroczone sprzątanie
OGR nie trafiało na końcowe niszczenie bibliotek.

Wyniki i identyfikacja końcowej paczki: [release-1.0.0.md](release-1.0.0.md).
Historyczny [validation-1.0.0.md](validation-1.0.0.md) dotyczy wcześniejszej
paczki rozwojowej Qt5; nie używać jej sumy jako identyfikacji wydania oficjalnego.

## Środowiska i ograniczenia

Lokalny QGIS 3.40.15/Qt5 na Ubuntu oraz izolowany QGIS 4.0.3/Qt6 6.10.2,
GDAL 3.12.2, Python 3.14.4. Runtime Qt6 rozpakowany z oficjalnych pakietów
QGIS/Ubuntu w ignorowanym dist/test-environments/, bez instalacji systemowej.
Nie zakładaj istnienia wrapperów z /tmp; odtwórz ścieżki według development.md.
Oficjalny kontroler Qt6 uzupełnia testy wykonania, nie zastępuje ich.

Odebrano i zbadano przebieg poligonowy rozwojowej 1.4.3: zgodna siatka
345 pozycji zamiast 4634 prostokąta na mapę, bez błędu geometrii lub zapisu.
52 braki w dwóch WMS zostały prawidłowo oznaczone; archiwum wymaga ponowienia.
Nie blokuje to wydania kodu. [Pełny audyt](audit-polygon-1.4.3.md). Testy lokalne obejmują poligony, zaznaczenie,
otwory, CRS i maski, ale nie zastępują odbioru konkretnego projektu.
Nowej paczki Qt6 nie uruchomiono na Windows/macOS; wcześniejsze testy użytkownika
na Windows dotyczyły rozwojowego 1.4.3. Brak dostępu Ubuntu do firmowej sieci
MSSQL/VPN — nie pytaj ponownie o poświadczenia. Pozostaje odbiór specyficznych
formularzy, relacji i logowania na stanowisku użytkownika.

Ostatni przebieg rozwojowy 1.4.3 z WFS zawierającym znane obiekty potwierdził
77 zapisanych obiektów WFS, bez strat i błędów odczytu; pusta warstwa wiatraków
była poprawnie zweryfikowana. W MSSQL pozostało 28 niepotwierdzonych zer.
Mapa: 12 284 pozycje, 15 napraw, zero końcowych braków, wszystkie 166 procesów
zakończyły się kodem 0. Surowe dane użytkownika pozostały poza repozytorium.
Globalne pole manifest.status nadal ma wartość partial niezależnie od końcowych
statusów warstw; nie traktować go jako dowodu utraty danych ani pełnego sukcesu.

Automat dobiera równoległość na podstawie pomiarów, nie gwarantuje matematycznego
maksimum CPU ani serwera. Sufit min(32, 2 × CPU), ograniczany RAM/commit Windows,
rezerwa 768 MiB, zapas wzrostu RSS. Zachowane Retry-After i redukcje przeciążenia,
PNG RGBA, osobne zoomy, jeden zapisujący GeoPackage i trwały postęp wznowienia.

## Publikacja i dalsza praca

**Wykonano publikację:** repozytorium jest PUBLIC,
[GitHub Release v1.0.0](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/releases/tag/v1.0.0)
jest opublikowany jako stabilny, z ZIP-em i plikiem SHA-256. Tag wskazuje commit
`1c84110aeb54858a2dff05b32f2bc65dd5e60463`. Publiczne źródła, README, GPL,
issues, strona wydania i oba załączniki sprawdzone bez logowania (HTTP 200).
Pobrany publicznie ZIP jest identyczny z lokalnym; SHA-256:
`b6e8d1f17e0b27d313b45d68e99504dd59d68a4b4fd5a98a888408e2fc64ea37`.
Przed zmianą widoczności przejrzano 20 commitów: 444 unikalne obiekty plików,
434 tekstowe przeskanowane, zero trafień sekretów i brak plików projektów/danych.
Bieżące 96 plików źródeł/dokumentacji również bez trafień sekretów.
Binaria historii to własna ikona PNG i katalog tłumaczeń Qt.
**Nie wysłano wtyczki do plugins.qgis.org**; to następny krok użytkownika.
Lokalny odbiór i GitHub Release nie oznaczają akceptacji moderatorów.
Kroki: [publishing.md](publishing.md).
Testerzy z wersją rozwojową 1.4.x muszą ręcznie zainstalować oficjalny ZIP 1.0.0
oraz uruchomić QGIS ponownie — niższy numer nie będzie automatyczną aktualizacją.

Reguły: [AGENTS.md](../AGENTS.md). Architektura: [architecture.md](architecture.md).
Budowa i testy: [development.md](development.md). Instrukcja użytkownika:
[team-guide.md](team-guide.md), pakowana jako INSTRUKCJA.md.
Historia prób: [validation-1.4.3.md](validation-1.4.3.md) i poprzednie raporty.
Paczki i sumy są w ignorowanym dist/. Bez danych użytkownika i sekretów w Git.
