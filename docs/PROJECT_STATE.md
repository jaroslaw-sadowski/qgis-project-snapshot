# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 9 września 2026. Wersja wtyczki: **0.5.0**.
Stan funkcjonalny: gotowa paczka do testów na komputerze służbowym;
pełny odbiór wszystkich źródeł firmowych nie został wykonany.

## Cel i ustalenia użytkownika

Zespół ma jednym poleceniem zachować stan projektu QGIS na dany dzień i móc
odtworzyć go po latach bez dostępu do MSSQL, WMS, WFS i innych źródeł.
Zachowujemy strukturę, wygląd oraz lokalne dane. Ważne są długie pasy inwestycji,
przezroczystość PNG, mocna kompresja bezstratna i wykorzystanie kilku rdzeni CPU.
Oryginalny eksporter MBTiles pozostaje dostępny jako osobna funkcja.

## Wykonane etapy

1. Wektory i atrybuty w jednym GeoPackage, kopia projektu, raport i manifest.
2. Rastry mapowe PNG w GeoPackage/CRS projektu, zoomy, maska obszaru,
   ponowienia i zachowanie wartości rastrów GDAL w GeoTIFF.
3. Równoległe procesy QGIS, zasoby, formularze, relacje i kontrola lokalnych źródeł.
4. Odbiór dostępnych źródeł publicznych i benchmark; źródła firmowe niedostępne tutaj.
5. ZIP, instrukcja zespołowa, test gotowej paczki w tymczasowym profilu.
6. Uporządkowanie dokumentacji, reguł agentów i niniejszego przekazania stanu.

Wynik eksportu nadal ma status archiwum częściowego/do odbioru. To celowe,
ze względu na nierozstrzygnięte zależności i brak pełnego odbioru firmowego.

## Sprawdzona paczka i wyniki

- `dist/mbtiles_batch_exporter-0.5.0.zip`, 47 162 bajty, 15 plików.
- SHA-256: `c584c1edc5bf5e557c3479dfa657578a4530518785972d2bd963e8b24a980268`.
- Build: `python3 scripts/build_plugin.py`. `dist/` nie jest wersjonowany.
- 29 testów integracyjnych przeszło także z kodu ZIP-a, bez pominięć WMS.
- QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4, Ubuntu; inne systemy nieodebrane.
- ZIP wykryto i załadowano natywnymi mechanizmami QGIS, otwarto oba okna
  z minimalnym interfejsem testowym. Nie był to ręczny odbiór pełnego pulpitu.
- Publiczny Geoportal: ortofotomapa i BDOT10k zapisane i wyrenderowane bez sieci.
- Publiczny WFS GDOŚ: poprawny pusty wynik oraz zapis 2 obiektów z atrybutami;
  odczyt i render offline bez żądań sieciowych.
- Benchmark pasa 10 km, 4 mapy/2 lokalne serwery: 45,13 / 24,20 / 13,26 s
  przy 1/2/4 procesach, identyczne PNG. To pojedynczy pomiar syntetyczny,
  nie gwarancja przyspieszenia dla danych produkcyjnych.

Szczegóły: [spis raportów](README.md). Po zmianie kodu lub plików pakowanych
ponownie zbuduj paczkę i aktualizuj jej bieżące dane; raportów historycznych nie nadpisuj.

## Znane ograniczenia i następne działania

Użytkownik potwierdził, że MSSQL działa wyłącznie z sieci firmowej na komputerze
służbowym. Na tym Ubuntu nazwa serwera nie rozwiązuje się w DNS; trzy rastry
z projektu też są nieobecne. Nie próbuj ponownie zgadywać adresów ani prosić
o poświadczenia bez zmiany warunków.

Następne zadanie: przyjąć wyniki testu służbowego zgodnie z
[instrukcją](team-guide.md), odtworzyć zgłoszony problem i poprawić jego przyczynę.
Potrzebne będą wersje QGIS/systemu, opcje eksportu i komunikaty raportu.
Nie zastępuj tego odbioru dodawaniem nieuzgodnionych funkcji.

Do sprawdzenia w firmie: MSSQL, lokalne rastry, wszystkie warstwy rzeczywistego
projektu, uwierzytelnianie, długi pas, style i etykiety, formularze, relacje i wydruki.
Nie wszystkie zależności wyrażeń, fonty i dowolny kod formularzy są pakowane.
Relacje mogą wskazywać obiekty spoza wybranego obszaru.

Równoległość dotyczy map usług, nie wszystkich operacji. Wektory z edycjami,
rastry GDAL i źródła `authcfg` pozostają w głównym QGIS. Więcej procesów
zużywa więcej pamięci; dla małych obszarów narzut może wydłużyć eksport.
Brak interpretera QGIS dla procesu pomocniczego powoduje próbę w głównym QGIS.

## Organizacja i stan roboczy

Źródło prawdy dla kodu: `mbtiles_batch_exporter/`; dla wersji: `metadata.txt`.
Mapa modułów i ograniczenia: [architecture.md](architecture.md).
Polecenia testów i budowy: [development.md](development.md).
Trwałe reguły współpracy: [AGENTS.md](../AGENTS.md).

Paczka nie została opublikowana jako GitHub Release ani w katalogu wtyczek QGIS.
Przy rozpoczęciu sesji sprawdź `git status` i historię; nie zakładaj, że zmiany
z poprzedniej sesji zostały już zatwierdzone lub wysłane.
Pliki prób w `/tmp/qgis-step4` są przejściowe i nie są wymagane do pracy nad kodem.
