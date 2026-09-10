# Odbiór 0.8.0 — 10 września 2026

## Paczka

- `dist/qgis-project-snapshot-0.8.0.zip`: 101 521 bajtów, 20 plików.
- SHA-256: `533d58e4de6b0a936a307802665bb91320a96e3eb98e230c2ed3c7dab9810ee6`.
- Identyfikator instalacji: `mbtiles_batch_exporter`, nazwa widoczna: qgis-project-snapshot.
- Środowisko: Ubuntu, QGIS 3.40.15, GDAL 3.12.2, Python 3.14.4, PyQt5.

## Testy końcowej paczki

Polecenie:

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -I tests/check_plugin_zip.py dist/qgis-project-snapshot-0.8.0.zip
```

**65/65 testów przeszło, bez pominięć, w 48,172 s.** Testy uruchomiono na kodzie
z zainstalowanej paczki. QGIS wykrył i załadował wtyczkę, otwarto oba okna
z minimalnym interfejsem testowym i wyłączono wtyczkę. Jest to odbiór automatyczny
Qt offscreen, a nie ręczna próba pełnego pulpitu.

Sprawdzono:

- wzrost po wymaganym czasie i liczbie sukcesów, brak przyspieszenia, cofnięcie,
  blokadę wzrostu, kolejne ograniczenia, generacje zdarzeń i kontrolę RAM;
- lokalny WMS: HTTP 429/503, oba formaty Retry-After, długą przerwę jednego hosta
  przy kontynuowaniu pracy drugiego, ponowne pobranie rzeczywistego braku;
- timeouty i budżet prób powrotu w kontrolowanych testach automatu, w tym
  nieudaną próbę powrotu z HTTP 500;
- brak ponownego pobierania poprawnych i przezroczystych kafelków, uzupełnianie
  w tej samej tabeli, błędy trwałe i wyczerpanie trzech prób kafelka;
- anulowanie, także podczas przerwy i uzupełniania, awarię procesu bez
  nieograniczonego ponowienia w głównym QGIS oraz wspólną kontrolę ścieżki głównej;
- PL/EN, dostępność tabeli podczas eksportu, rzeczywiste liczniki procesów,
  czerwone ostrzeżenia, raporty oraz dotychczasowe testy archiwum i trybu stałego.

Celowo puste obrazy powodują komunikaty GDAL o braku pikseli do statystyk;
sprawdzenia oczekiwanego wyniku przechodzą. Ostrzeżenia Qt offscreen nie są
błędami testów.

## Kontrolowany benchmark

[Surowe wyniki](benchmark-0.8.0.json), skrypt: `tests/benchmark_adaptive.py`.
Sześć map, dwa aliasy hosta lokalnego WMS, kwadrat 1,2 × 1,2 km, zoom 18,
opóźnienie serwera 120 ms. Początkowy budżet zasobów ustalono na 2 CPU / 8 GiB
(cztery procesy), z włączonym późniejszym sprawdzaniem rzeczywistego RAM.

| Tryb | Czas | GetMap | Maksimum procesów |
| --- | ---: | ---: | ---: |
| Stały: 4 globalnie, 2 na host | 57,706 s | 1014 | 4 |
| Adaptacyjny | 58,323 s | 1014 | 4 |

Automat zwiększył limit obu hostów z 1 do 2 po około 15,069 s. Sumy SHA-256 PNG
wszystkich sześciu map są identyczne między trybami; kontrola lokalnych źródeł
przeszła. Nie wystąpiły błędy serwera ani presja RAM w tym pomiarze. Narzut
wyniósł około 0,617 s (1%). Ten pojedynczy pomiar syntetyczny nie dowodzi
przyspieszenia ani optymalnego limitu dla produkcyjnych usług.

## Granice odbioru

Nie sprawdzono Windows ani źródeł w sieci firmowej. MSSQL i trzy nieobecne rastry
z projektu użytkownika wymagają próby na komputerze służbowym. Kontrola lokalnych
źródeł i testy renderowania nie zastępują odbioru wszystkich zależności projektu.

Automatyczne uzupełnianie dotyczy bieżącego eksportu. Nie ma wznawiania po
zamknięciu QGIS ani pamięci limitów między eksportami. Ręczna ponowna próba
z ekranu wyników tworzy nowe archiwum wybranych warstw. Ograniczenia dostawcy
usługi, w tym zakaz masowego pobierania standardowych kafelków OSM, nadal obowiązują.
