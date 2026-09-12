# Odbiór 1.4.0 — wektory, piramidy i trwałe wznowienie

Data: 12 września 2026. Ubuntu, QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4.
Praca obejmuje trzy problemy zlecone po przygotowaniu 1.3.0. Źródła i logi
użytkownika pozostały poza repozytorium. Nie wykonano publikacji ani instalacji
w jego profilu QGIS.

## Co wykazała diagnoza

W przekazanym przebiegu 1.2.0 wszystkie 36 wektorów miało zero już na wejściu
eksportera, przed maskowaniem i zapisem. To nie dowodzi poprawnego pustego odczytu.
Na rzeczywistym kliencie WFS QGIS odtworzono odpowiedź OWS Exception przy zamkniętym
iteratorze, zanim oczekujący sygnał Qt dotarł do eksportera. Odtworzono też pusty
cache mimo pojawienia się obiektu na serwerze. Poprawka dostarcza oczekujące błędy
aktywnego dostawcy przed oceną wyniku i odświeża WFS poza trybem edycji.

QGIS 3.40 może po błędzie SQL zamknąć iterator MSSQL bez błędu dostępnego w Pythonie.
Pusty odczyt jest dodatkowo sprawdzany natywnym połączeniem dostawcy i ograniczonym
zapytaniem TOP (1), z zachowaniem tabeli oraz filtra. Błąd dostępu nie jest sukcesem
z zerem. Pusta tabela potwierdza zero; obecność obiektów w źródle nie potwierdza
braku obiektów w obszarze. Ten ostatni przypadek zapisuje uwagę w raporcie oraz
`empty_read_verified=null`. `vector_read_version=2` opisuje nową ścieżkę odczytu.
Kontynuacja ponawia niepotwierdzone zero i zerowe WFS/MSSQL ze starszej ścieżki.
Test nie zastępuje odbioru rzeczywistego firmowego MSSQL — sieć jest niedostępna.

Natywne kopiowanie rastra GeoTIFF nie zachowywało piramid. Dodano wewnętrzne
NEAREST/DEFLATE9 z piramidami maski i kontrolą, że pełna rozdzielczość pozostaje
bez zmian. GPKG już przechowuje niezależnie renderowane poziomy. GDAL pomija poziom
bez żadnego PNG, nawet gdy taki poziom jest poprawnie przezroczysty. Jeden
bezstratny przezroczysty PNG na taki poziom przywraca właściwy odczyt; nie jest
liczony jako niepusty kafelek. Nie tworzymy fikcyjnego sukcesu dla błędów ani braków.

## Trwałość i wznowienie

Manifest roboczy powstaje przed pobieraniem w jawnym folderze `.in-progress-…`.
Zapisywany atomowo stan warstw i `download-state` przetrwają wyjątek lub śmierć
procesu. Rejestr SQLite zapisuje ukończone, puste i nieudane kafelki oraz próby.
PNG i rejestr korzystają z trwałych transakcji. Po wznowieniu sprawdzamy zapisane
PNG, w tym granicę między zatwierdzeniem obrazu a zatwierdzeniem rejestru.
Kontynuacja kopiuje dane przez natywny backup SQLite po przerwaniu, z kontrolą
integralności. Cache jest usuwany dopiero po scaleniu i trwałym manifeście.

Pierwsze scalenie i pierwsze utworzenie bazy wektorów są atomowe. QLockFile chroni
aktywnie używany folder. Pliki inicjalizacyjne nie trafiają do danych kontynuacji.
GUI pamięta folder i podpowiada go po ponownym uruchomieniu. Ukończone wektory są
zachowane; przerwany wektor rozpoczyna tylko swoją warstwę od początku.

Test rzeczywistego nowego QGIS ujawnił niestabilny odcisk stylu: Qt zmieniało
kolejność atrybutów XML między procesami. `ElementTree.canonicalize` i wersja
odcisku 2 usuwają tę przyczynę fałszywej odmowy. Stare odciski 1.1–1.3 pozostają
sprawdzane dawną metodą i mogą odmówić kontynuacji po restarcie. Nie można odtworzyć
starej kolejności z samego SHA; gotowy projekt offline ma zmienione źródła i style.
Starsze archiwa nie mają rejestru do odzyskania pojedynczych kafelków 1.4.

Wymuszenie zapisu używa uchwytów plików z prawem zapisu również w Windows.
Synchronizacja katalogu jest wykonywana na Unix. Nie deklarujemy niezawodności
uszkodzonego nośnika ani odbioru odcięcia zasilania. Po awarii może być potrzebne
ponowne pobranie niezakończonego kafelka, ale zachowane, sprawdzone dane pozostają.

## Testy i kontrole

- WFS: rzeczywisty klient QGIS, lokalne Capabilities/GML, transformacja CRS,
  atrybuty, prawidłowy pusty obszar, OWS Exception, odświeżenie cache i kontynuacja
  dawnego zerowego wyniku. Kontrole MSSQL używają atrap natywnego połączenia.
- Rastry: pełne wartości UInt16 i RGBA identyczne przed/po piramidach, maski,
  niezależne zoomy po scaleniu, widoczność piramid w QGIS, brak markerów przy błędach.
- Wznowienie: SIGKILL po commit PNG przed commit rejestru; SIGKILL całego eksportu
  i kontynuacja w nowym QGIS z lokalnym WMS; identyczne zachowane PNG, brak ponownego
  pobierania ukończonej mapy i jej kafelków. Anulowany worker podczas 429 zachowuje
  dane i kończy po przywróceniu sieci. Aktywna blokada odrzuca drugie wznowienie.
- Pierwszy pełny odbiór ZIP: 216 testów, 155,800 s, 7 niepowodzeń. Dwa stare testy
  wskazywały dawną lokalizację usuwanego manifestu/rejestru, jeden zakładał brak
  przezroczystych markerów. Cztery ujawniły regresję zachowania ręcznego API retry
  po dodaniu rejestru. Przyczyny poprawiono przed końcowym odbiorem. Tryb stały
  odzyskał dotychczasowe retry/podział i zatrzymanie po 429; rejestr nie mnoży prób.
  Dwa poprawione testy ścieżek przeszły; 22 kontrole kafelków i rzeczywistego WMS
  potwierdziły poprawkę retry.

Końcowy odbiór gotowego ZIP-a: **219/219 testów, 156,211 s, bez pominięć**.
Wykrywanie, ładowanie, otwarcie okna i wyłączenie w izolowanym profilu QGIS — OK.
Testy i procesy pomocnicze korzystały z kodu rozpakowanej paczki. WMS, WFS i proxy
działały przez lokalne gniazda. Komunikaty GDAL o niemożności obliczenia statystyk
dotyczą celowo przezroczystych rastrów; kontrole ich pikseli, zoomów i lokalnego
odczytu przeszły. Ostrzeżenia codecs.open pochodzą z QGIS/Processing.

Paczka: `dist/qgis-project-snapshot-1.4.0.zip`, **141 090 bajtów, 22 pliki**.
Ponowna budowa dała identyczne bajty. SHA-256:

```text
38200abf7b13714b04d46533c925b7af47225e0cb4172675bed33579891c22c9
```

Ruff check i format, Flake8/pycodestyle (88 znaków), AST 41 plików Python,
odnośniki dokumentacji i diff — poprawne.
E203 ma jawną konwencję formatowania; E402 dopuszczony wyłącznie przy inicjalizacji
testowego QGIS. Nie dodano typecheckera ani nowej zależności instalowanej wtyczki.
Skan sekretów końcowych źródeł oraz niezależny skan rozpakowanego ZIP-a
`--no-verify`: zero trafień. ZIP nie zawiera danych użytkownika, archiwów, logów,
profili ani plików wykonawczych procesów.

Bandit: 20 ostrzeżeń (15 medium, 5 low), zero high. Przejrzano wszystkie:
dynamiczny SQL używa własnych identyfikatorów SHA lub cytowanych nazw oraz
parametrów wartości; MSSQL używa istniejącego filtra źródła i cytuje identyfikatory.
Nie interpretuje danych obiektów jako SQL. Pozostałe trafienia dotyczą istniejących
parserów XML i uruchamiania ustalonego modułu workera bez powłoki. Nie wyłączono
reguł, nie ukryto wyników i nie uznano skanera za dowód pełnego bezpieczeństwa.
TOP (1) ogranicza liczbę zwróconych rekordów, nie gwarantuje krótkiego czasu
wykonania dowolnego filtra SQL. Filtr jest kodem istniejącego źródła projektu.

Przegląd według Ponytail: wykorzystano istniejący rejestr, SQLite backup/transakcje,
QLockFile, ElementTree i GDAL BuildOverviews. Nie dodano własnego formatu plików,
systemu zadań, zależności ani silnika pobierania. Kontrole integralności pozostały.

## Źródła i granice odbioru

- [Ponytail — zasady minimalnych zmian](https://github.com/dietrichgebert/ponytail).
- [Qt 5.15 QLockFile](https://doc.qt.io/archives/qt-5.15/qlockfile.html) — blokady
  długotrwałych zasobów i wykrywanie nieaktywnych procesów.
- [GDAL GeoTIFF](https://gdal.org/en/stable/drivers/raster/gtiff.html) oraz
  [GeoPackage](https://gdal.org/en/stable/drivers/raster/gpkg.html) — piramidy i kafelki.
- [Windows FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
  wymaga uchwytu z prawem GENERIC_WRITE.

Odbiór dotyczy Ubuntu i kontrolowanych usług. Firmowy MSSQL, rzeczywisty Windows,
wydajność dużego archiwum i utrata zasilania wymagają próby na stanowisku użytkownika.
Nie zmieniano limitów obciążenia 1.3.0 i nie zmierzono nowego maksimum komputera
lub publicznych serwerów. Aktualizacja wymaga zakończenia bieżącego eksportu
i ponownego uruchomienia QGIS. Przy wznowieniu zachowaj cały poprzedni folder.

Propozycja commitu: `Prepare 1.4.0: verify vector reads, build overviews and persist downloads`.
Commit, push i publikacja pozostają niewykonane.
