# Odbiór 0.8.1 — 10 września 2026

Zmiana obejmuje opisy i wygląd interfejsu; algorytm archiwizacji i automatyki
pozostaje taki jak w 0.8.0.

## Zakres

- README po polsku i angielsku, opisy metadanych PL/EN, autor, odnośniki i tagi.
- Wzór redakcyjny: [README](https://github.com/jaroslaw-sadowski/qgis-poprawka-odwzorowawcza)
  i [metadane](https://github.com/jaroslaw-sadowski/qgis-poprawka-odwzorowawcza/blob/main/metadata.txt)
  wskazane przez użytkownika. Opisane kontrole i możliwości dotyczą naszego kodu.
- Własny piktogram SVG mapy w pudełku, ikony CPU i RAM, natywne ikony przycisków Qt.
- RAM opisany jako rezerwa planowania, bez sugerowania pomiaru bieżącego zużycia.
- Poprawne położenie flag metadanych w sekcji general; jawna zgodność QGIS 3.x.

## Wynik

`dist/qgis-project-snapshot-0.8.1.zip`: **104 679 bajty, 22 pliki**.
SHA-256: `8e37c1e8d6fbc6913ed6494de821f81fbdaa93f86499092bf74d0392119bd5c1`.

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -I tests/check_plugin_zip.py dist/qgis-project-snapshot-0.8.1.zip
```

**65/65 testów z końcowej paczki, bez pominięć, 47,762 s.** Natywne wykrywanie,
ładowanie, oba okna i wyłączenie wtyczki: OK. QGIS 3.40.15 na Ubuntu.
Lokalny WMS był dostępny. Komunikaty GDAL o braku pikseli pochodzą z celowo
pustych danych testowych i nie spowodowały błędu testów.

Dodatkowo otwarto okno PL i EN w Qt offscreen, zapisano podglądy i obejrzano układ
PL i EN. Sprawdzono renderowanie wszystkich trzech SVG, obecność ikony akcji i tekst
rezerwy RAM w obu językach. Katalog Qt zawiera 345 gotowych tłumaczeń.
Kontrola składni Python, metadanych, CRC ZIP-a, zgodności każdego pliku paczki
ze źródłem i `git diff --check`: OK. Bez dodatkowych bibliotek.

Nie powtarzano benchmarku, ponieważ nie zmieniono mechanizmu pobierania.
[Pomiar 0.8.0](benchmark-0.8.0.json) pozostaje historycznym punktem odniesienia.
Odbiór Windows i źródeł firmowych nadal należy przeprowadzić na stanowisku
użytkownika. Nie opublikowano wydania na GitHub ani w katalogu QGIS.
