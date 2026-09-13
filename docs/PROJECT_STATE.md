# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 13 września 2026. Poprawka **1.0.1** po blokadzie skanu 1.0.0,
wspólna paczka dla QGIS 3/Qt5 i QGIS 4/Qt6. Numery 1.1–1.4 były
rozwojowe; ich raporty zachowano, ale nie oznaczają kolejnych oficjalnych wydań.

## Bieżący etap

Użytkownik wysłał 1.0.0 do plugins.qgis.org. Portal zablokował zgłoszenie
[6293], skan 13 września 2026 o 15:15 CEST: 19 uwag Bandit, pozostałe cztery
kontrole przeszły. Wcześniejsza ocena „bez high/Critical” była błędna w odniesieniu
do portalu: jego kontrola Bandit ma zbiorczą kategorię critical także dla
wykrytych ostrzeżeń. Nie opieraj gotowości publikacji na lokalnej skali HIGH.

Poprawka zabezpieczeń jest gotowa lokalnie: defusedxml w prywatnej paczce,
cytowanie SQL przez QGIS, jawne uruchamianie własnego procesu bez shell,
punktowe udokumentowane nosec tylko dla sprawdzonych zastosowań. Pełny odbiór
236/236 Qt5 (185,951 s) i 236/236 Qt6 (192,549 s), kody 0, bez pominięć.
Końcową konfigurację Flake8 sprawdzono również z listą bezwzględnych ścieżek,
jak w portalu. Skan ZIP-a obejmuje vendor: Bandit 0 po punktowych adnotacjach,
sekrety 0. Bez globalnego wyłączania Bandita lub pomijania vendor w tym skanerze.
Szczegóły: [security-scan-fix.md](security-scan-fix.md).

Użytkownik zatwierdził 1.0.1, ponowne sprawdzenie wymagań i GitHub Release.
Zaktualizowano numer, changelog, README/instrukcję i informację o dołączonym
parserze PSF. Kod jest identyczny z pełnym odbiorem 236 testów.
Finalny ZIP 1.0.1: 150 998 bajtów, 29 plików, SHA-256
`4b1e8842764a9c66e32b976861e2516a443924aa92ec0b5593ac51f82b08ec87`.

Podwójny audyt: dokumentacja QGIS i wykonanie kodu portalu z commitu
487ac16367d4387ab91630149200e3f9b1ee9ff8. Oryginalny walidator paczek/metadanych
przeszedł, również dla nowej wtyczki i z rzeczywistymi publicznymi URL.
Pięć metod skanera upstream: 5/5, zero zgłoszeń, bez ignorowania całych kategorii.
Użyto 75 obsługiwanych reguł Bandit, a dwie wycofane w tej wersji (B111/B320)
sprawdzono osobno. Kontroler Qt6: zero wymaganych zmian. Finalna instalacja/GUI
ZIP-a 1.0.1: po 15/15 testów Qt5 i Qt6, kody 0; pełny identyczny kod wcześniej
po 236/236. Ruff/format i Flake8 również OK.
[Raport 1.0.1](release-1.0.1.md), [wynik skanera](portal-scan-1.0.1.json).

Przygotowano wydanie GitHub v1.0.1; publikacja i weryfikacja załączników w toku.
Tag 1.0.0 pozostaje historyczny. Poprawionej paczki nie wysłano jeszcze do
plugins.qgis.org — należy ją zgłosić jako nową wersję istniejącej wtyczki.
Poniższe sekcje stanowią historię przygotowania 1.0.0, przed poprawką bezpieczeństwa.

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
Wtedy kod był identyczny jak w paczce z pełnym odbiorem. Późniejszą korektę
menu opisano osobno poniżej; aktualna suma znajduje się w raporcie.

**Odbiór bazowego kodu: 231/231 testów z ZIP-a w każdym runtime**, bez pominięć,
kody procesów 0. Qt5: 170,064 s; Qt6: 171,448 s. Ruff/format, Flake8, składnia
Python 3.10, linki i diff OK. Sekrety: 0 w kodzie i ZIP-ie. Kontroler Qt6: 0
niezgodności. Bandit: historycznie 20 ostrzeżeń bez HIGH według lokalnej skali; portal
później zablokował wersję (patrz bieżący etap). Aktualna paczka
144 219 bajtów, 23 pliki; powtarzalna budowa i zgodność wszystkich źródeł.
Samodzielny program odbioru zamyka QGIS przez exitQgis(), aby odroczone sprzątanie
OGR nie trafiało na końcowe niszczenie bibliotek.

Wyniki i identyfikacja końcowej paczki: [release-1.0.0.md](release-1.0.0.md).
Historyczny [validation-1.0.0.md](validation-1.0.0.md) dotyczy wcześniejszej
paczki rozwojowej Qt5; nie używać jej sumy jako identyfikacji wydania oficjalnego.

## Korekta opisów i menu w ramach 1.0.0

README repozytorium/paczki i metadane mają bardziej naturalny język, bez nowych
obietnic i tematów. Instrukcja wskazuje Wtyczki → QGIS Project Snapshot.
Menu używa natywnego pluginMenu().addAction/removeAction, jak we wskazanej
wtyczce Poprawka Odwzorowawcza. Jedyna zmiana kodu produkcyjnego to etykieta
i rejestracja/usuwanie akcji menu; algorytmy archiwizacji pozostały identyczne.

ZIP po korekcie menu: po 15/15 testów w QGIS 3.40/Qt5 (1,424 s) i 4.0.3/Qt6 (1,328 s),
kody 0. Sprawdzono bezpośrednią akcję, otwarcie okna, wyłączenie i ponowne
włączenie bez duplikatów oraz zachowanie cudzych pozycji menu. Ruff/format,
Flake8, składnia 3.10 i diff OK. Flake8 uruchomiono z --jobs 1, ponieważ sandbox
blokuje gniazdo forkserver; zakres kontroli bez zmian. Pełne 231 testów jest
wcześniejszą bazą odbioru; nie powtarzano ich dla zmiany tekstów/menu.
W ramach istniejącego wydania podmieniono ZIP i tag v1.0.0, zgodnie z poleceniem
zachowania numeru. Synchronizację potwierdzono poniżej.

## Wskazówka o czasie dużych pobrań w 1.0.0

Dodano po jednym krótkim akapicie EN/PL w README repozytorium/paczki i metadanych:
wiele warstw, duży obszar i zoom powyżej 17 mogą oznaczać ogromną liczbę kafelków
oraz od kilku godzin do kilku dni pobierania. Ten sam tekst rozpoczyna natywną
podpowiedź po najechaniu na szacowaną liczbę kafelków; bez okna blokującego.
Zaktualizowano TS i skompilowano QM (337 kompletnych tłumaczeń). Nie zmieniono
obliczeń szacunku, algorytmów pobierania ani numeru wersji.
Gotowy ZIP: 15/15 testów w Qt5 (1,628 s) i Qt6 (1,503 s), kody 0; obejmują
zgodność katalogu tłumaczeń i ładowanie/okno wtyczki. Ruff/format, Flake8 i diff OK.
Załączniki istniejącego wydania zastąpiono. Publiczne pobranie bez logowania
potwierdziło identyczny ZIP/SHA i zgodność wszystkich plików paczki z tagiem.
Tag po wskazówce o czasie pobierania: `8654be889a8b64314efbc9acf8eb0207a860d413`.
SHA-256 po wskazówce o czasie pobierania: `74a756dffe1e992455183c588dc7d3d29d22f1fb8d874840feb47e20a3e66bd1`.

## Doprecyzowanie pobierania usług mapowych w 1.0.0

Wstęp README EN/PL i metadane wprost wskazują pobieranie WMS/WMTS oraz
kafelków XYZ, np. podkładów OpenStreetMap. Tagi zawierają dodatkowo openstreetmap,
osm, wms download, wmts download, tile services i polskie odpowiedniki
pobieranie wms, pobieranie wmts, usługi kafelkowe. Wspólne nazwy standardów
oraz OpenStreetMap nie są dublowane: 22 tagi EN/wspólne, potem 16 PL.
Sprawdzono odczyt metadanych, kompletność obu języków, unikalność i kolejność
tagów, integralność ZIP-a i zgodność ze źródłami. W paczce zmieniły się tylko
README.txt oraz pola description/about/tags w metadata.txt. Cały kod i katalogi
tłumaczeń są identyczne z poprzednim wydaniem; nie powtarzano testów wykonania
ani lintowania kodu dla samego tekstu. Wersja pozostaje 1.0.0.
Załączniki istniejącego wydania zaktualizowano. Publiczne pobranie ZIP/SHA
bez logowania potwierdziło zgodność z lokalną paczką i wszystkimi źródłami tagu.
Aktualny tag v1.0.0: `e23a433d73136f5ca5f2334b59c15d1ab7a8c779`.
Aktualny SHA-256: `744729baf9df0843f9701500d3caba2c3a0cbd60aeb9922afb06f5550447832a`.

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
jest opublikowany jako stabilny, z ZIP-em i plikiem SHA-256. Pierwotny tag wskazywał commit
`1c84110aeb54858a2dff05b32f2bc65dd5e60463`. Publiczne źródła, README, GPL,
issues, strona wydania i oba załączniki sprawdzone bez logowania (HTTP 200).
Pierwotnie pobrany publicznie ZIP był identyczny z lokalnym; poprzedni SHA-256:
`b6e8d1f17e0b27d313b45d68e99504dd59d68a4b4fd5a98a888408e2fc64ea37`.
Poprzednia paczka po korekcie opisów/menu: `fb36f7a64cd005d9ef3fb505abe5349fd65983a553481b570b88da50b9dbdae4`.
Po korekcie menu tag v1.0.0 wskazywał commit `fd134c45ae7dc615a7decb01b2f8c1ed460f305a`.
Podmieniono oba załączniki i sumę w opisie istniejącego wydania. Pobrano je
publicznie bez logowania: ZIP i SHA są identyczne z lokalnymi. Każdy plik ZIP-a
jest zgodny ze źródłem pod tagiem. Repo pozostaje publiczne, wydanie stabilne.
Przed zmianą widoczności przejrzano 20 commitów: 444 unikalne obiekty plików,
434 tekstowe przeskanowane, zero trafień sekretów i brak plików projektów/danych.
Bieżące 96 plików źródeł/dokumentacji również bez trafień sekretów.
Binaria historii to własna ikona PNG i katalog tłumaczeń Qt.
**Użytkownik wysłał wtyczkę do plugins.qgis.org; zgłoszenie zablokowane.**
Nie wysłano jeszcze poprawionej paczki; patrz bieżący etap.
Lokalny odbiór i GitHub Release nie oznaczają akceptacji moderatorów.
Kroki: [publishing.md](publishing.md).
Testerzy z wersją rozwojową 1.4.x muszą ręcznie zainstalować oficjalny ZIP 1.0.0
oraz uruchomić QGIS ponownie — niższy numer nie będzie automatyczną aktualizacją.

Reguły: [AGENTS.md](../AGENTS.md). Architektura: [architecture.md](architecture.md).
Budowa i testy: [development.md](development.md). Instrukcja użytkownika:
[team-guide.md](team-guide.md), pakowana jako INSTRUKCJA.md.
Historia prób: [validation-1.4.3.md](validation-1.4.3.md) i poprzednie raporty.
Paczki i sumy są w ignorowanym dist/. Bez danych użytkownika i sekretów w Git.
