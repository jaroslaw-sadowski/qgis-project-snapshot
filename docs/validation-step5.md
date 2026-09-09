# Krok 5 — paczka instalacyjna do odbioru zespołowego

9 września 2026. Wersja 0.5.0, QGIS 3.40.15, Ubuntu.

## Dostarczone

- `dist/mbtiles_batch_exporter-0.5.0.zip` — 47 162 bajty, 15 plików,
  jeden katalog wtyczki wymagany przez instalację QGIS.
- Plik `.zip.sha256` z sumą kontrolną.
- [Instrukcja dla zespołu](team-guide.md), dołączona również jako `INSTRUKCJA.md`
  wewnątrz paczki; obejmuje instalację, pierwszą próbę i odbiór bez sieci.
- `scripts/build_plugin.py` — budowa przy użyciu standardowej biblioteki Pythona.
- `tests/check_plugin_zip.py` — kontrola gotowej paczki w odizolowanym profilu.

SHA-256 paczki z tego odbioru:

```text
c584c1edc5bf5e557c3479dfa657578a4530518785972d2bd963e8b24a980268
```

## Weryfikacja

Paczka została rozpakowana do tymczasowego profilu. Natywne mechanizmy QGIS
wykryły wtyczkę, odczytały metadane, załadowały ją i uruchomiły. Sprawdzono
obie akcje, otwarcie obu okien oraz usunięcie akcji po wyłączeniu wtyczki.
Test korzystał z natywnych widżetów QGIS/Qt i minimalnego zastępczego interfejsu
aplikacji; nie był ręcznym testem klikania pełnego pulpitu QGIS.

Następnie wykonano **29 testów integracyjnych z kodu rozpakowanego ZIP-a**.
Wszystkie przeszły, bez pomijania testów WMS. Dotyczy to również osobnych
procesów QGIS, scalania GeoPackage, odczytu offline, zasobów i anulowania.
Sprawdzono pochodzenie załadowanych modułów, aby wykluczyć przypadkowe testowanie
kodu z katalogu roboczego zamiast paczki. Profil użytkownika nie był zmieniany.

Kontrola CRC ZIP-a nie wykazała błędów. Dwie niezależne budowy w tym samym
środowisku dały pliki identyczne bajt po bajcie. Kontrola składni nowych skryptów
oraz `git diff --check` przeszły. Nie dodano zależności ani nie zmieniono
mechanizmu eksportu.

## Zakres wydania

Paczka jest gotowa do instalacji i odbioru na komputerze służbowym.
Nie została opublikowana w repozytorium wtyczek QGIS ani jako GitHub Release.
Katalog `dist/` jest ignorowany przez Git; ZIP można odtworzyć skryptem.

Pozostają ograniczenia opisane w [kroku 4](validation-step4.md), szczególnie
MSSQL i pliki firmowe dostępne wyłącznie w sieci służbowej. Nie oznaczamy tego
wydania jako potwierdzonego odbiorem całego projektu ani na systemie Windows.
