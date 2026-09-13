# Audyt zabezpieczeń XML, SQL i procesów

W 1.0.0 portal wykrył 19 uwag Bandit i zablokował zgłoszenie. Nie były to
19 potwierdzonych luk, ale wymagały zabezpieczenia XML i przeglądu każdego miejsca.
Poprawka 1.0.1 wprowadziła opisane zabezpieczenia. 1.0.2 usuwa konfigurację
skanera z ZIP-a i nieużywane gałęzie Pythona 2 z prywatnej biblioteki XML.

## Zabezpieczenia

- QGS, XML warstw, SVG i UI odczytuje defusedxml 0.7.1. Odrzuca encje wewnętrzne,
  parametryczne i zewnętrzne; dopuszcza zwykły DOCTYPE QGIS i wbudowane encje.
  Niebezpieczne SVG/UI i odwołania do nich są usuwane z kopii; oryginał pozostaje.
- XML stylu jest sprawdzany przed kanonizacją. Dotychczasowy fingerprint pozostaje
  zgodny, aby nie wymuszać ponownego pobierania przy wznowieniu.
- Nazwy tabel SQLite cytuje `QgsSqliteUtils.quotedIdentifier`, wartości są wiązane
  przez parametry. MSSQL zachowuje cytowanie nawiasami i jawny filtr SQL dostawcy
  projektu. Nazwy wyświetlane warstw i odpowiedzi usług nie są kodem SQL.
- Proces QGIS startuje przez absolutną ścieżkę interpretera, stały moduł,
  listę argumentów i `shell=False`. Poświadczenia pozostają w pamięci/stdin.
  Nie rozwijamy symlinku interpretera, aby zachować środowisko venv.
- Dołączono tylko potrzebny frontend defusedxml, opis pochodzenia i licencję PSF.
  Bez pip i globalnego monkey patchingu. Python 3 zachowuje implementację parsera
  upstream. [Lokalne różnice](../mbtiles_batch_exporter/vendor/README.md).

## Punktowe adnotacje Bandit

Cała paczka, także vendor, podlega skanowi. Nie zawiera `.bandit`, `.flake8`
ani `.secrets.baseline`. Pozostaje **18** punktowych adnotacji `nosec`, każda
z uzasadnieniem w kodzie; trzeba je przeglądać także przez `--ignore-nosec`.

| Reguła | Liczba | Uzasadnienie |
| --- | --- | --- |
| B608 | 11 | Parametry SQL nie obsługują nazw tabel. Nazwy są cytowane, wartości wiązane. Filtr MSSQL jest istniejącym, jawnym SQL użytkownika w QGIS. |
| B405 | 5 | Cztery importy wewnątrz zabezpieczonej implementacji defusedxml; jeden import kanonizacji poprzedzonej walidacją defusedxml. |
| B404/B603 | 2 | Własny proces QGIS, argumenty bez powłoki, hasła poza argumentami. |

B314 o niezabezpieczonym parsowaniu usunięto przez zmianę parsera, bez jego
wyłączania. Dwie dawne adnotacje B405 z gałęzi Pythona 2 usunięto wraz z tym kodem.
Zmiana źródła identyfikatorów, filtrów lub argumentów wymaga ponownego przeglądu.

## Weryfikacja

`tests/test_security.py` sprawdza encje w UTF-8/UTF-16, poprawny DOCTYPE QGIS,
odrzucenie SVG i odwołań bez naruszenia oryginału, zgodność fingerprintów oraz
zapis do tabeli z cudzysłowem i próbą SQL w nazwie bez naruszenia drugiej tabeli.
Testy ZIP-a sprawdzają również brak ukrytych plików i konfiguracji skanerów.

[Wyniki bieżącego wydania](release-1.0.2.md).
[Historyczny odbiór poprawki](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/blob/v1.0.1/docs/security-scan-fix.md).
[Publiczny kod skanera](https://github.com/qgis/QGIS-Plugins-Website/blob/master/qgis-app/plugins/security_scanner.py)
klasyfikuje całą kontrolę Bandit jako critical: lokalne LOW/MEDIUM nie gwarantuje
przejścia portalu. Sprawdzaj pięć rzeczywistych kontroli i zawartość ich wyników,
nie tylko kod wyjścia procesu. Akceptacja moderatora jest osobnym etapem.
