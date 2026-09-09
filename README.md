# qgis-project-snapshot

Wtyczka QGIS rozwijana w kierunku samodzielnych archiwów projektów offline.
Dotychczasowy eksporter MBTiles pozostaje dostępny.

## Krok 1 — podstawa archiwizacji (0.3.0)

Nowa akcja **Archiwizuj projekt…** w menu wtyczki zapisuje **archiwum częściowe**:

- drzewo wyboru odtwarza grupy i kolejność, domyślnie zaznaczając wszystkie warstwy;
- obszar to widok mapy lub kształt poligonów (zaznaczonych, a przy braku zaznaczenia — wszystkich);
- wektory są zapisywane z atrybutami do oddzielnych tabel jednego `dane.gpkg`;
- zachowywane są całe obiekty przecinające obszar, filtry i niezapisane edycje;
- nowy projekt `.qgz` zachowuje ID warstw, grupy, kolejność, widoczność i style;
- raport HTML oraz manifest JSON opisują wyniki, braki, obszar, czas pobierania i sumy kontrolne;
- kolejne archiwum nie nadpisuje poprzedniego; przerwanie zachowuje ukończone warstwy;
- kopia powstaje w katalogu tymczasowym i jest udostępniana po kontroli zapisu.

**WMS/WMTS/XYZ, kafelki wektorowe, ArcGIS i pozostałe rastry nie są jeszcze
archiwizowane przez nową akcję.** Są wymieniane w raporcie i pomijane w kopii
projektu. Dotyczy to także odznaczonych lub niedostępnych warstw. Pełna kontrola
zewnętrznych symboli, załączników, formularzy i zależności projektu należy do
kroku 3. Na tym etapie nie należy traktować wyniku jako kompletnej kopii całego projektu.

Eksport działa na głównym wątku QGIS, z modalnym oknem i obsługą zdarzeń pomiędzy
porcjami danych. Odczyt blokujący po stronie dostawcy może opóźnić reakcję na
przerwanie. Wykrywane są zgłoszone błędy dostawcy i niezgodność liczby zapisanych
obiektów; niezasygnalizowana przez usługę utrata części danych wymaga dalszej kontroli.

Przenoś cały folder `Nazwa_archive_YYYYMMDD`, a projekt otwieraj przez `.qgz`.
Zapisane tabele wektorowe nie wymagają naszej wtyczki ani połączenia ze źródłem.
Daty raportu oznaczają czas pobierania poszczególnych warstw, nie jednoczesny stan
wszystkich zewnętrznych źródeł.

## Instalacja i testy

Skopiuj katalog `mbtiles_batch_exporter` do katalogu wtyczek profilu QGIS i
włącz wtyczkę w menedżerze. Zmiany sprawdzono na QGIS 3.40.15 z PyQt5;
zgodność nowych funkcji ze starszymi wersjami nie została przetestowana.

Testy integracyjne korzystają z QGIS i GDAL dostarczonych z QGIS oraz standardowego
`unittest`. Nie wymagają usług zewnętrznych ani danych firmowych:

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Uruchom polecenie interpreterem z dostępem do modułów `qgis` i `osgeo`.
Projekt nie ma osobnej konfiguracji lint, typecheck ani procesu build.

## Następne kroki

2. **Obrazy offline:** GeoPackage w CRS projektu (m.in. EPSG:2180), wybór zoomów
   z odpowiednikiem skali, osobne renderowanie każdego zoomu i metody zastępcze.
   PNG z pełną przezroczystością, bezstratnie z `ZLEVEL=9` przy tworzeniu i
   aktualizacji każdego poziomu. Kafelki 256 × 256, pobieranie tylko dla kształtu
   obszaru, maskowanie i pomijanie całkowicie przezroczystych kafelków, praca
   fragmentami. Bez automatycznego zmniejszania rozdzielczości lub palety kolorów.
3. **Samodzielność projektu:** zasoby i zależności stylów, relacje, formularze,
   pełna kontrola offline, dalsza obsługa błędów i komunikatów. Najpierw eksport
   danych, potem właściwe alternatywy QGIS/GDAL i obraz; przy błędach pobierania
   dwa ponowienia i mniejsze fragmenty. Braki zawsze ujawnione w raporcie.
4. **Odbiór na rzeczywistym projekcie:** mały obszar, następnie długi pas,
   stanowisko z dostępem do MSSQL i udziałów sieciowych; na końcu otwarcie
   przeniesionego folderu bez internetu, sieci firmowej i naszej wtyczki.

W miarę możliwości stosujemy [Ponytail](https://github.com/DietrichGebert/ponytail):
najpierw istniejący kod, standardowe funkcje i dostępne mechanizmy QGIS/GDAL,
dopiero potem minimalny potrzebny kod. To zalecenie, nie wymóg bezwzględny;
poprawność, czytelność, obsługa błędów i bezpieczeństwo danych mają pierwszeństwo.

Projektów użytkownika, danych firmowych i wygenerowanych archiwów nie dodajemy do repozytorium.
