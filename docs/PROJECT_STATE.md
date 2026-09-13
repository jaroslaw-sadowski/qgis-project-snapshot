# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 13 września 2026. Opublikowano poprawkę **1.0.2**,
wspólna paczka dla QGIS 3/Qt5 i QGIS 4/Qt6.

## Korekta opisów po wydaniu 1.0.2

README repozytorium, README wtyczki i opisowe pola metadanych przeredagowano
na prostsze, pełne zdania po angielsku i po polsku. Zachowano zakres informacji,
warunki korzystania ze źródeł, informację o AI oraz wymagania instalacji.
Usunięto średniki i długie myślniki z tych tekstów. Numer pozostaje 1.0.2.
Walidator metadanych portalu przeszedł. Sprawdzono zgodność obu README,
odnośniki i diff. Porównanie ZIP-ów potwierdziło zmiany wyłącznie w README.txt
i polach description/about/changelog. Cały kod wykonawczy pozostaje identyczny
z odebranym wydaniem. Nie powtarzano pełnych testów dla samych tekstów.

Zmiany dotyczą bieżących źródeł w repozytorium. Opublikowany tag i załączniki
1.0.2 pozostają niezmienione. Paczka do kontroli tekstów jest osobno
w ignorowanym `dist/editorial-preview/`, nie jest nowym wydaniem.
Przy kolejnym wydaniu należy uwzględnić te opisy i nadać nowy numer.

## Bieżący etap

Użytkownik zlecił usunięcie oznaczenia „Validated (configured)”, porządki i wydanie
1.0.2 na GitHub. Skan 1.0.1 wykrywał `.flake8` w ZIP-ie. Konfiguracja pozostaje
wyłącznie w repo do rozwoju; budowa i kontrola paczki wykluczają ukryte pliki.
Kod przechodzi Flake8 bez konfiguracji z limitem 120 znaków portalu: poprawiono
jeden zapis przekroju listy i usunięto martwe gałęzie Pythona 2 w defusedxml.
Nie zmieniono algorytmów pobierania, obciążenia, jakości map ani wznowienia.

`mbtiles_batch_exporter` jest identyfikatorem aktualnej wtyczki. Dawny eksporter
został wcześniej usunięty. Zmiana identyfikatora zablokowałaby aktualizację tego
samego wpisu na portalu. Widoczna nazwa pozostaje **QGIS Project Snapshot**.
Usunięto 35 nieaktualnych raportów, zapisanych wyników benchmarków i powielone
README; są dostępne w historii Git i tagu v1.0.1. Zachowano testy, skrypty pomiarowe,
aktualną dokumentację oraz audyt zabezpieczeń. Nie usuwano archiwów użytkownika.

Odbiór zakończony: 236/236 Qt5 (188,870 s) i 236/236 Qt6 (196,924 s),
kody 0, bez pominięć. Skaner upstream: 5/5, zero zgłoszeń, `config_files=[]`.
Walidator metadanych, Ruff/format, Flake8 i kontroler Qt6 przeszły.
Stabilny GitHub Release v1.0.2 jest publiczny, tag wskazuje
`ea088b4b2746ae70fc54297fa0a4d84a00a54fef`. Publiczne pobranie ZIP/SHA
potwierdziło zgodność ze sprawdzoną paczką i wszystkimi 28 źródłami tagu.
ZIP 150 754 bajty, SHA-256
`212875e603838513d7f4a3eeaeb758863780186a8aebcb78ea5a4b8c646f5053`.
Nie wysłano z tej sesji paczki do plugins.qgis.org.
Wyniki odbioru i status publikacji: [release-1.0.2.md](release-1.0.2.md).
Nie utożsamiaj lokalnego skanu ani GitHub Release z akceptacją plugins.qgis.org.
Wersja 1.0.0 była zablokowana przez Bandit. 1.0.1 usunęła te trafienia, ale zawierała
konfigurację Flake8. Punktowe adnotacje bezpieczeństwa mają uzasadnienia i testy:
[security-scan-fix.md](security-scan-fix.md).

## Środowiska i ograniczenia

Ubuntu, QGIS 3.40.15/Qt5 oraz izolowany QGIS 4.0.3/Qt6 6.10.2,
GDAL 3.12.2, Python 3.14.4. Runtime Qt6 jest w ignorowanym
`dist/test-environments/`, bez zastępowania QGIS systemowego. Nie zakładaj
istnienia wrapperów z `/tmp`; wskazówki są w [development.md](development.md).
Nowej paczki nie odebrano na Windows/macOS ani na firmowym MSSQL/VPN.
Ubuntu nie ma dostępu do sieci firmowej — nie pytaj ponownie o poświadczenia.

Wcześniejsze próby użytkownika na Windows potwierdzały pobieranie WFS z obiektami
i prawidłową siatkę poligonu; część pustych MSSQL pozostawała niepotwierdzona,
a pojedyncze braki WMS wymagały ponowienia. Globalne `manifest.status=partial`
nie zastępuje oceny statusów poszczególnych warstw. Dane użytkownika są poza Git.

Automat dobiera równoległość na podstawie pomiarów; nie gwarantuje matematycznego
maksimum CPU ani serwera. Sufit min(32, 2 × CPU), ograniczany RAM/commit Windows,
rezerwa 768 MiB, zapas wzrostu RSS. Zachowane Retry-After, redukcje przeciążenia,
PNG RGBA, osobne zoomy, jeden zapisujący GeoPackage i trwały postęp wznowienia.
Nie usuwaj zgodności z archiwami wersji rozwojowych przy porządkowaniu kodu.

## Dalsza praca

Reguły: [AGENTS.md](../AGENTS.md). Architektura: [architecture.md](architecture.md).
Budowa i testy: [development.md](development.md). Instrukcja użytkownika:
[team-guide.md](team-guide.md), pakowana jako INSTRUKCJA.md. Publikacja:
[publishing.md](publishing.md). ZIP-y i środowiska są w ignorowanym `dist/`.
Testerzy rozwojowych 1.4.x instalują oficjalny ZIP ręcznie i restartują QGIS;
niższy numer nie zostanie zaproponowany automatycznie.
