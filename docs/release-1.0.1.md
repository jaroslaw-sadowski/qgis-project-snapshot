# Odbiór i wydanie 1.0.1

13 września 2026. Poprawka po zablokowaniu wersji 1.0.0 w plugins.qgis.org.
Użytkownik zatwierdził numer 1.0.1 i GitHub Release. Naprawa XML, cytowania SQL
oraz uzasadnienia punktowych adnotacji Bandit: [raport](security-scan-fix.md).
Pobieranie, jakość map i wznowienie zachowują dotychczasowy zakres.

## Paczka

`dist/qgis-project-snapshot-1.0.1.zip`: **150 998 bajtów, 29 plików**, w tym
17 Python. Jeden katalog mbtiles_batch_exporter, prawa 0644, GPL, dokumentacja,
metadane i tłumaczenia. Prywatny frontend defusedxml ma licencję PSF i opis
pochodzenia. Użytkownik nie instaluje dodatkowych pakietów.

SHA-256:
`4b1e8842764a9c66e32b976861e2516a443924aa92ec0b5593ac51f82b08ec87`.

## Podwójna weryfikacja wymagań

Przeczytano aktualne [wymagania publikacji](https://plugins.qgis.org/docs/publish/),
[proces zatwierdzania](https://plugins.qgis.org/docs/approval/),
[opis skanerów](https://plugins.qgis.org/docs/security-scanning/tools/)
i [migrację QGIS 4](https://plugins.qgis.org/docs/migrate-qgis4/).
Następnie sprawdzono i uruchomiono kod portalu z commitu
`487ac16367d4387ab91630149200e3f9b1ee9ff8`.

| Warstwa kontroli | Sprawdzenie | Wynik |
| --- | --- | --- |
| ZIP i metadane | Oryginalny validator.py, is_new=True, Django 5.2.17; limit 25 MB, CRC, ścieżki, nazwa pakietu, wymagane pola, ikona, LICENSE, UTF-8 i publiczne linki | OK |
| Bandit | Kod security_scanner.py, 75 obsługiwanych reguł łącznie z blacklistami importów/XML i poziomem LOW | 0 zgłoszeń |
| Sekrety | Kod portalu, detect-secrets 1.5.0, cały ZIP; dodatkowy wcześniejszy skan obejmował również metadata.txt | 0 zgłoszeń |
| Flake8 | Kod portalu, jawne absolutne ścieżki wszystkich plików Python i .flake8 z ZIP-a | 0 zgłoszeń |
| Prawa plików | Kod portalu na centralnym katalogu ZIP | 0 zgłoszeń |
| Podejrzane pliki | Kod portalu, typy wykonywalne i niedozwolone pliki ukryte | 0 zgłoszeń |
| QGIS 4 | Oficjalny kontroler migracji na całej paczce, dry_run | 0 wymaganych zmian |
| Instalacja i GUI finalnego ZIP-a | QGIS 3.40.15/Qt5 oraz QGIS 4.0.3/Qt6, menu, okno, wyłączenie/włączenie, metadane i tłumaczenia | po 15/15 testów, kody 0 |
| Kod działania poprawki | Pełny odbiór z poprzedniego etapu na tym samym kodzie, wektory/WMS/WFS/proxy/SQL/XML/awarie/wznowienie | po 236/236, kody 0, bez pominięć |
| Lokalna jakość | Ruff/format, Flake8, składnia Python 3.10, git diff --check | OK |

Wynik pięciu kontroli upstream: **5/5, critical=0, warnings=0, issues=0**.
[Wynik maszynowy z identyfikacją źródeł](portal-scan-1.0.1.json).

Metody skanera upstream nie zostały zmodyfikowane. Przy lokalnym wczytaniu
zastąpiono dwa importy środowiska Django (tłumaczenie i nieużywany model bazy
reguł); narzędzia i funkcje pięciu kontroli wykonano rzeczywiście. Wybrano
wszystkie reguły dostępnego Bandita 1.9.4 zamiast polegać na jego domyślnym
progu. Tabela portalu zawiera również wycofane w tym Bandicie B111/B320:
osobna kontrola AST potwierdziła brak run_as_root i importów lxml. Nie stosowano
pomijania reguł w formularzu portalu ani .bandit. Wynik zero uwzględnia opisane
w raporcie naprawy 20 punktowych adnotacji nosec; nie oznacza braku tych adnotacji.

Walidator ZIP/metadanych uruchomiono bez zmian, w rzeczywistym Django, także
z żądaniami sprawdzającymi homepage/repository/tracker. Nie odtworzono bazy
użytkowników ani procedury zgłoszenia na serwerze QGIS. Jego wersje narzędzi
lub ustawienia mogą się różnić; końcowy skan i decyzja moderatorów pozostają
po stronie portalu. Kontroler Qt6 sygnalizuje obecność PyQt5 na systemie,
ale testy wykonania korzystają z izolowanego QGIS 4/PyQt6.

Pełne 236 testów: Qt5 185,951 s, Qt6 192,549 s. Finalne 15 testów z ZIP-a 1.0.1:
Qt5 2,291 s, Qt6 2,384 s. Porównanie z odebraną poprawką roboczą 1.0.0 wykazało
zmianę wyłącznie README, instrukcji oraz metadanych (wersja, changelog, opis
biblioteki). Nie powtarzano szerokich testów identycznego kodu. Brak natywnego
odbioru nowego Qt6 na Windows/macOS i firmowego MSSQL/VPN na Ubuntu pozostaje.

## Publikacja

Opublikowano stabilny [GitHub Release v1.0.1](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/releases/tag/v1.0.1),
commit `4eac9847b3db0612e942277037073f58e4400f64`, z ZIP-em i SHA-256.
Pobranie obu plików bez logowania potwierdziło zgodność z lokalną paczką;
każdy plik ZIP-a odpowiada źródłu pod tagiem. Opis 1.0.0 wskazuje poprawkę 1.0.1.
Paczka jest gotowa do ponownego zgłoszenia przez użytkownika do QGIS.
Stary tag v1.0.0 pozostaje historyczny; nowy numer nie nadpisuje jego źródeł.
Publikacja GitHub nie oznacza wysłania lub zatwierdzenia w plugins.qgis.org.
