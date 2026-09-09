# qgis-project-snapshot

Wtyczka QGIS zapisująca stan projektu do archiwum offline: lokalne dane,
mapy PNG z przezroczystością, zasoby, kopia projektu i raport.
Dotychczasowy eksporter MBTiles pozostaje dostępny.

## Paczka do testów służbowych

**Wersja 0.6.0** — [ZIP instalacyjny](dist/qgis-project-snapshot-0.6.0.zip)
i [SHA-256](dist/qgis-project-snapshot-0.6.0.zip.sha256).
W QGIS użyj menedżera wtyczek i zakładki **Zainstaluj z ZIP**.
[Instrukcja dla zespołu](docs/team-guide.md) jest też dołączona do paczki.

Wymagane: QGIS 3.40 z PyQt5 oraz GDAL co najmniej 3.7.
Sprawdzono 33 testy z gotowej paczki na Ubuntu/QGIS 3.40.15 oraz próbki
publicznych map i WFS offline. MSSQL, pliki firmowe i cały projekt wymagają
odbioru na komputerze służbowym w sieci firmowej. Windows nie był testowany.

Postęp pokazują licznik warstw, kolumna **Stan**, czas i dziennik. Objaśnienia opcji
są dostępne po najechaniu kursorem. Menu: **Wtyczki → qgis-project-snapshot**.

Archiwum przenoś jako **cały folder**, nie sam plik `.qgz`.
Wyniki niepełne i zależności wymagające kontroli są opisane w raporcie.

## Dokumentacja

- [Instrukcja i odbiór przez zespół](docs/team-guide.md)
- [Budowa paczki, testy i benchmark](docs/development.md)
- [Działanie, moduły i ograniczenia](docs/architecture.md)
- [Aktualny stan i dalsze prace](docs/PROJECT_STATE.md)
- [Spis dokumentacji i raportów](docs/README.md)
- [Instrukcje dla agentów AI / Codexa](AGENTS.md)

## Odtworzenie paczki

```bash
python3 scripts/build_plugin.py
```

ZIP i suma kontrolna powstają w `dist/`, który jest ignorowany przez Git.
Dlatego po świeżym klonowaniu repozytorium trzeba je wygenerować powyższą komendą.
Kod źródłowy, instrukcja i licencja są pakowane bez danych projektów ani testów.

Licencja: [GPL-2.0](LICENSE).
