# Odbiór QGIS Project Snapshot 1.0.0

Data: 10 września 2026. Przygotowanie do plugins.qgis.org, bez publikacji.
Źródła startowe: commit 41f4d02, wersja 0.9.7; repozytorium było czyste.

## Zmiany wydania

README PL/EN i README w paczce opisują zastosowanie, wymagania, instalację,
obsługę, automatyczne pobieranie równoległe, prawa do danych i vibe coding z AI.
Instrukcja została przepisana dla ogólnego użytkownika; usunięto historię
firmowych prób i szczegóły działania planowania. Indeks dokumentacji uporządkowano,
a PROJECT_STATE skrócono do bieżącego stanu. Raporty historyczne zachowano.

Metadane: 1.0.0, stable, angielski opis, kontakt zatwierdzony przez autora,
GPL-2.0-only, angielskie tagi, changelog, linki oraz wymagania i ograniczenia.
GNU GPL v2 dotyczy wtyczki i własnych zasobów; nie zmieniano jej na „or later”.
README, instrukcja i about podkreślają obowiązek przestrzegania licencji
poszczególnych warstw oraz warunków usług. Nie obiecują skutecznego wyłączenia
odpowiedzialności autora wbrew obowiązującemu prawu.

Dodano SPDX do plików Python i SVG. Usunięto opcjonalne category=Raster,
ponieważ akcja całego projektu jest w menu Wtyczki. Akcja dostała stabilny
objectName do personalizacji interfejsu QGIS. Zachowano nazwę i identyfikator
Pythona, algorytmy pobierania, zapis danych i tłumaczenia.

Istniejący test ZIP-a sprawdza dodatkowo wymagane metadane, wersję, adres autora,
deklarowany zakres QGIS, licencję, flagi, URL, rozmiar do 25 000 000 bajtów,
brak powtórzonych/obcych/ukrytych plików, bezpieczne ścieżki i prawa 0644.
Nie dodano narzędzi ani bibliotek wymaganych przez zainstalowaną wtyczkę.

## Testy działania i jakości

Ubuntu, QGIS 3.40.15, GDAL 3.12.2, Python 3.14.4, Qt5/PyQt5. Testy pracowały
w izolowanych profilach i na wygenerowanych danych. WMS i proxy używały
lokalnych gniazd; nie pominięto ich z powodu ograniczeń środowiska.

- Źródła: **128/128 testów**, 115,662 s, bez pominięć.
- Gotowy ZIP: **128/128 testów**, 110,253 s, bez pominięć; wykrywanie,
  ładowanie, okno archiwizacji i wyłączenie — OK. Moduły oraz procesy mapowe
  używały kodu z rozpakowanej paczki, bez zmian profilu użytkownika.
- Ruff 0.16.6: check oraz format --check całego repozytorium — OK.
- Flake8 7.3.0 / pycodestyle 2.14.0: kod wtyczki czysty z limitem 88 znaków
  i jawnym pominięciem E203. Domyślne E203 zgłasza jeden przekrój formatowany
  przez Ruff. Nie jest to deklaracja ścisłego limitu 79 znaków PEP 8.
- AST: **33 pliki Python**, poprawna składnia. git diff --check — OK.
  Brak osobnego skonfigurowanego typecheckera.
- CRC, zgodność każdego zapakowanego pliku ze źródłem i powtarzalność ZIP-a
  bajt po bajcie — OK.

Przegląd [Ponytail](https://github.com/DietrichGebert/ponytail/blob/main/AGENTS.md):
zachowano istniejące narzędzia i architekturę, rozbudowano istniejącą kontrolę
paczki zamiast tworzyć równoległy walidator, wykorzystano bibliotekę standardową.
Nie przebudowywano działającego pobierania przy porządkach dokumentacji.

## Bezpieczeństwo

Bandit 1.9.4 na kodzie wtyczki: **11 trafień**, 6 Medium i 5 Low, zero High.
Według reguł portalu sprawdzonych w dniu audytu: 10 Warning, 1 Info, zero Critical.
To nie jest wynik „bez ostrzeżeń”; wszystkie konteksty przejrzano:

| Reguły | Kontekst i wynik przeglądu |
| --- | --- |
| B608, 2 trafienia | Nazwy tabel powstają z SHA-256 ID warstwy; wartości zapytań są parametryzowane. |
| B603/B404, 2 trafienia | Start własnego modułu pracownika przez interpreter, lista argumentów, bez powłoki. |
| B314/B405, 7 trafień | ElementTree czyta wygenerowany projekt QGIS lub lokalne SVG/UI. Brak pobierania i parsowania w ten sposób odpowiedzi usług; zasoby projektu wymagają zaufania. |

detect-secrets 1.5.0 na katalogu wtyczki oraz rozpakowanym gotowym ZIP-ie:
**brak trafień**, bez baseline i wyłączeń. Skan śledzonych plików całego
repozytorium wykazał dziewięć trafień:
pięć identyfikatorów/sum w historycznych benchmarkach oraz cztery sztuczne
poświadczenia w testach diagnostyki i proxy. Potwierdzono kontekst; nie są to
rzeczywiste dane dostępowe. Te raporty i testy nie trafiają do paczki.
Sprawdzono też listę ścieżek we wszystkich dostępnych commitach: bez projektów
użytkownika i archiwów danych. To nie jest pełny audyt treści każdego dawnego commitu.

Nie dodano .bandit, .secrets.baseline ani adnotacji nosec wyciszających trafienia.
Skan całego repozytorium i gotowego ZIP-a używa --no-verify, bez wysyłania
kandydatów na hasła do usług zewnętrznych. Narzędzia audytu zainstalowano
wyłącznie w tymczasowym środowisku developerskim.

Portal może zmienić reguły, wersje skanerów i ocenę trafień. Wynik lokalny
nie zastępuje [skanu portalu](https://plugins.qgis.org/docs/security-scanning)
ani [decyzji moderatorów](https://plugins.qgis.org/docs/approval).

## Paczka i stan publikacji

- dist/qgis-project-snapshot-1.0.0.zip: **112 827 bajtów, 22 pliki**.
- SHA-256: **b85dcda24aff10776b0da2f0ee7943f3db02efdbab3224095522f90c2746c22e**.
- LICENSE i instrukcja INSTRUKCJA.md dołączone. Qt en.qm jest katalogiem danych;
  en.ts zawiera źródła tłumaczenia. Brak wykonywalnych binariów i danych testowych.

**GitHub nadal jest prywatny.** Odczyt uwierzytelniony potwierdził PRIVATE;
publiczne homepage/repository/tracker zwracają 404. Przed zgłoszeniem należy
upublicznić źródła odpowiadające ZIP-owi. Nie wykonywano zmiany widoczności,
push, tagu, GitHub Release ani uploadu do QGIS. [Instrukcja publikacji](publishing.md)
opisuje pozostałe kroki i oficjalne źródła wymagań.

QGIS 3.40–3.x z Qt5 pozostaje deklarowanym zakresem. Kod nie obsługuje QGIS4/Qt6.
Pełny odbiór Windows/macOS, MSSQL i nietypowego uwierzytelniania wymaga dostępnego
stanowiska. Te ograniczenia są ujawnione; nie utożsamiano testów Ubuntu z pełnym
odbiorem wszystkich platform i dowolnych projektów.
