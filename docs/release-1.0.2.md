# Odbiór i wydanie 1.0.2

13 września 2026. Poprawka usuwa `.flake8` z paczki QGIS i przyczynę oznaczenia
„Validated (configured)”. Pozostawiono konfigurację developerską w repozytorium.
Jeden zapis przekroju listy uproszczono, a z defusedxml usunięto martwe gałęzie
Pythona 2; cały kod ZIP-a przechodzi standardowy Flake8 portalu bez konfiguracji.
Algorytmy pobierania, obciążenia, wznowienia i jakość danych pozostają bez zmian.

## Porządki

Usunięto 35 plików: powielony README, raporty wersji rozwojowych, zapisane wyniki
benchmarków i zastąpione raporty wydań. Są dostępne w historii Git i tagu v1.0.1.
Zachowano aktualne instrukcje, testy regresji, skrypty benchmarków i audyt
zabezpieczeń. Zaktualizowano indeks dokumentacji oraz odnośniki historyczne.
Nie usuwano danych użytkownika ani stanów wznowienia.

Wszystkie 13 głównych modułów produkcyjnych są osiągalne z punktów wejścia
wtyczki i procesu pomocniczego. `mbtiles_batch_exporter` to stabilny identyfikator
obecnego produktu, nie pozostały dawny eksporter. Portal wymaga zgodności nazwy
folderu z istniejącym zgłoszeniem; zmiana uniemożliwiłaby jego aktualizację.
Widoczna nazwa pozostaje QGIS Project Snapshot.

## Paczka

`dist/qgis-project-snapshot-1.0.2.zip`: **150 754 bajty, 28 plików**,
w tym 17 plików Python, źródła tłumaczeń, instrukcja oraz licencje GPL i PSF.
Prawa 0644, brak konfiguracji skanerów i ukrytych plików.

SHA-256:
`212875e603838513d7f4a3eeaeb758863780186a8aebcb78ea5a4b8c646f5053`.

## Kontrole portalu i kodu

Odtworzono pięć metod oryginalnego skanera QGIS z aktualnego commitu
`487ac16367d4387ab91630149200e3f9b1ee9ff8`, potwierdzonego 13 września.
W loaderze zastąpiono jedynie dwa importy Django/modeli, bez zmian metod skanera.
Uruchomiono go poza repozytorium, aby nie odczytał developerskiego `.flake8`.

| Kontrola | Wynik |
| --- | --- |
| Bandit 1.9.4, wszystkie 75 dostępnych reguł, cały ZIP i vendor | 0 zgłoszeń |
| detect-secrets 1.5.0, kod skanera portalu | 0 zgłoszeń |
| Flake8 7.3.0, wszystkie bezwzględne ścieżki Python, limit 120, bez konfiguracji | 0 zgłoszeń |
| Prawa plików | OK |
| Podejrzane pliki | OK |
| Rozpoznane konfiguracje skanera | Pusta lista |
| Oryginalny walidator ZIP/metadanych, także wymagania nowej wtyczki i publiczne URL | OK |
| Ruff, Ruff format, developerski Flake8, składnia Python 3.10 | OK |
| Oficjalny kontroler Qt6 w trybie dry_run | Brak wymaganych zmian |

Kontroler Qt6 wypisuje ostrzeżenie o obecności PyQt5 w środowisku; nie zgłasza
zmian kodu. Testy wykonania używają oddzielnego runtime Qt6.
[Wynik maszynowy skanera i walidatora](portal-scan-1.0.2.json).
Wycofane B111/B320 nie występują w zainstalowanym Bandit; w kodzie nie ma
`run_as_root` ani `lxml`. Skan surowy `--ignore-nosec` daje 18 znanych miejsc:
11 B608, 5 B405, B404 i B603. Nie dodano nowych wyciszeń; usunięto dwa wraz
z gałęziami Pythona 2. [Uzasadnienia i testy](security-scan-fix.md).

## Testy działania

Gotowy ZIP zainstalowany w tymczasowym profilu, z rzeczywistymi lokalnymi
WMS/WFS/proxy i procesami pomocniczymi:

- QGIS 3.40.15 / Qt5: **236/236**, 188,870 s, kod 0, bez pominięć.
- QGIS 4.0.3 / Qt6 6.10.2: **236/236**, 196,924 s, kod 0, bez pominięć.

Zakres: instalacja/menu/okno/wyłączenie, eksport wektorów i rastrów, maski
poligonów, jakość PNG, integralność GeoPackage, limity serwerów i pamięci,
proxy, błędy, anulowanie, wznowienie po zabiciu procesu oraz zabezpieczenia XML/SQL.
Ponowna budowa dała identyczny ZIP. Sprawdzono odnośniki dokumentacji i diff.
Ubuntu nie ma dostępu do firmowego MSSQL/VPN; nowe wydanie nie było testowane
na Windows/macOS. Testy dostawcy MSSQL są lokalnymi testami kontrolnymi,
nie odbiorem połączenia z firmową bazą.

## Publikacja

Opublikowano stabilny [GitHub Release v1.0.2](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/releases/tag/v1.0.2).
Tag wskazuje `ea088b4b2746ae70fc54297fa0a4d84a00a54fef`. Publiczne pobranie ZIP-a
i SHA bez logowania potwierdziło zgodność z lokalnymi załącznikami; wszystkie
28 plików odpowiada źródłom pod tagiem. Repo jest publiczne.
Starsze tagi i wydania pozostają w historii.
Do plugins.qgis.org należy wysłać ZIP z załączników wydania jako nową wersję
istniejącej wtyczki. Lokalny odbiór nie zastępuje skanu portalu i akceptacji
moderatora. Paczki nie wysłano z tej sesji do plugins.qgis.org.
