# Odbiór 0.8.2 — 10 września 2026

Poprawka dotyczy wyskakujących konsoli procesów pomocniczych na Windows.
`RasterWorkers._run` przekazuje CREATE_NO_WINDOW tylko na win32, a na pozostałych
systemach zero. Jest to natywna opcja [subprocess](https://docs.python.org/3/library/subprocess.html#subprocess.CREATE_NO_WINDOW).
Dotychczasowe przekierowania, komunikacja plikowa i anulowanie pozostają bez zmian.

Paczka: `dist/qgis-project-snapshot-0.8.2.zip`, 104 833 bajty, 22 pliki.
SHA-256: `c09ecbfd5bf03bbcbc4581d2fd71db8c8e5146b5e184fca95d7a4075cbc579ce`.

Odbiór poleceniem z docs/development.md: **65/65 testów kodu z końcowego ZIP-a**,
bez pominięć, 46,971 s. QGIS 3.40.15 na Ubuntu. Natywne ładowanie, oba okna,
wyłączenie i lokalny WMS: OK. Składnia Python, CRC, zgodność plików ZIP-a
ze źródłami i git diff --check: OK. Oczekiwane komunikaty GDAL o braku pikseli
pochodzą z celowo pustych danych testowych.

Nie uruchamiano Windows w tym środowisku. Potwierdzenie, że konsole przestały
się pojawiać podczas rzeczywistego eksportu, pozostaje po stronie użytkownika.
Instalacja: ZIP 0.8.2, restart QGIS, ponowne uruchomienie archiwizacji.
