# qgis-project-snapshot

Wtyczka QGIS rozwijana w kierunku samodzielnych archiwów projektów offline.
Dotychczasowy eksporter MBTiles pozostaje dostępny.

## Kroki 1–3 — dane, obrazy i zasoby offline (0.5.0)

Nowa akcja **Archiwizuj projekt…** w menu wtyczki zapisuje **archiwum częściowe**:

- drzewo wyboru odtwarza grupy i kolejność, domyślnie zaznaczając wszystkie warstwy;
- obszar to widok mapy lub kształt poligonów (zaznaczonych, a przy braku zaznaczenia — wszystkich);
- wektory są zapisywane z atrybutami do oddzielnych tabel jednego `dane.gpkg`;
- zachowywane są całe obiekty przecinające obszar, filtry i niezapisane edycje;
- nowy projekt `.qgz` zachowuje ID warstw, grupy, kolejność, widoczność i style;
- raport HTML oraz manifest JSON opisują wyniki, braki, obszar, czas pobierania i sumy kontrolne;
- kolejne archiwum nie nadpisuje poprzedniego; przerwanie zachowuje ukończone warstwy;
- kopia powstaje w katalogu tymczasowym i jest udostępniana po kontroli zapisu.

**Krok 2 dodaje zapis obrazów WMS/WMTS/XYZ, ArcGIS i innych warstw renderowanych
przez QGIS**, w tym kafelków wektorowych:

- każda mapa jest osobną tabelą rastra w tym samym `dane.gpkg`; warstwy można
  nadal niezależnie włączać i wyłączać;
- rastry mapowe używają CRS projektu, m.in. EPSG:2180;
- wybierasz zoom minimalny i maksymalny (domyślnie 13–17); przy każdej pozycji
  widać przybliżoną skalę przy 96 DPI i rozdzielczość dla środka obszaru;
- każdy zoom jest osobno renderowany, aby zachować treść zależną od skali;
- PNG zachowuje pełny kanał alfa i kolory, z `ZLEVEL=9` przy każdym zapisie;
  nie stosujemy JPEG, redukcji palety ani automatycznego obniżania jakości;
- pobierane są kafelki 256 × 256 przecinające kształt obszaru, z niewielkim
  marginesem renderowania; maska uwzględnia również dziury w poligonach;
- całkowicie przezroczyste kafelki nie zajmują miejsca w tabeli;
- siatka jest przeszukiwana przestrzennie, bez skanowania całego prostokąta
  długiego, ukośnego pasa i bez przechowywania całego obrazu w pamięci;
- raster GDAL (np. plik na udziale sieciowym) jest najpierw zapisywany z
  oryginalnymi wartościami i maską w bezstratnym GeoTIFF w `zasoby/`;
- jeśli eksport danych się nie powiedzie, próbujemy zachować obraz. Dotyczy to
  także wektorów z niezapisanymi edycjami; raport informuje o utracie atrybutów;
- przy zgłoszonym błędzie pobierania wykonujemy dwa ponowienia, potem próbę
  mniejszych fragmentów. Po pięciu kolejnych nieudanych kafelkach kończymy
  próby dla warstwy, aby nie powtarzać bez końca zapytań do niedostępnej usługi.

Puste zoomy otrzymują status „do sprawdzenia”, a obraz z brakującymi fragmentami
jest oznaczony jako częściowy. Jeśli nie udało się pobrać żadnego obrazu, warstwa
jest pomijana. Raport HTML podaje wyniki, a `manifest.json` zawiera dodatkowo
liczby kafelków dla każdego zoomu, ponowienia i do 20 przykładów błędnych fragmentów.
Odznaczone lub niedostępne warstwy nie pozostają aktywnymi źródłami w kopii.

**Krok 3 kopiuje lokalne symbole SVG, obrazy symboli, formularze UI i pliki pól
załączników** do `zasoby/`, przepisując ścieżki w projekcie i lokalnych danych.
Sprawdza odwołania do obrazów wewnątrz SVG/UI, zachowuje bazę stylów i załączniki
osadzone w QGZ. Zachowuje relacje pomiędzy zapisanymi wektorami, usuwa relacje
prowadzące do pominiętych warstw i zastępuje niedziałające pola relacyjne zwykłym
odczytem wartości. Otwiera ponownie lokalne warstwy przez rzeczywistych dostawców QGIS.

Zasoby internetowe, brakujące pliki, dynamiczne wyrażenia, kod formularzy,
akcje i złożone zależności są wskazywane w raporcie. Zapis relacji nie dodaje
automatycznie obiektów spoza wskazanego obszaru. Fonty systemowe, zewnętrzne
biblioteki formularzy, dowolny kod Python i wszystkie możliwe zależności QGIS
nie są automatycznie pakowane. Wynik nadal wymaga odbioru offline; raport
nie deklaruje pełnej samodzielności na podstawie samego poprawnego zapisu.
Obraz zachowuje wygląd dla wybranego obszaru i zoomów, a nie dowolnego późniejszego
powiększenia. Usługa może zwrócić pustą lub niepełną mapę bez zgłoszenia błędu;
w takich przypadkach potrzebne jest również porównanie wizualne.

## Równoległe pobieranie i CPU

Okno pozwala wybrać 1–8 procesów; domyślnie do 4, zależnie od liczby CPU.
Mapy usług są pobierane i kompresowane równolegle w osobnych procesach QGIS,
które mogą używać różnych rdzeni. Wątki Pythona nadzorują procesy; nie dotykają
warstw ani projektu otwartego w interfejsie. Kolejka przeplata serwery i ogranicza
liczbę procesów dla jednego hosta do dwóch. Limit dotyczy zadań warstw, nie
wewnętrznych połączeń HTTP poszczególnych dostawców QGIS.

Każdy proces zapisuje własny tymczasowy GeoPackage. Główny proces scala gotowe
tabele, kopiując skompresowane PNG bez ponownego renderowania czy utraty jakości.
Tylko jeden proces zapisuje końcowy `dane.gpkg`. Liczba procesów ogranicza zużycie
RAM, ale pliki tymczasowe wymagają dodatkowego miejsca na dysku. Dla małych
projektów uruchamianie procesów może być wolniejsze; wtedy wybierz 1.

Wektory (w tym niezapisane edycje), oryginalne rastry GDAL i usługi używające
`authcfg` pozostają w głównym QGIS. Gdy proces pomocniczy nie działa w danym
środowisku, eksport próbuje ponownie w głównym QGIS i odnotowuje to w raporcie.
Procesy wymagają interpretera Python z modułami QGIS; wdrożenie i testy wykonano
na Ubuntu z QGIS 3.40. Inne systemy wymagają osobnego sprawdzenia.

Anulowanie wysyła sygnał do procesów, a po 5 sekundach kończy nieodpowiadające
procesy pomocnicze. Niepełne pliki prywatne są usuwane; ukończone, scalone warstwy
zostają zachowane. Natywny odczyt wektorów w głównym QGIS nadal może opóźnić
reakcję na anulowanie. Próbę renderowania ograniczamy do 60 sekund.

Przenoś cały folder `Nazwa_archive_YYYYMMDD`, a projekt otwieraj przez `.qgz`.
Zapisane tabele wektorowe nie wymagają naszej wtyczki ani połączenia ze źródłem.
Daty raportu oznaczają czas pobierania poszczególnych warstw, nie jednoczesny stan
wszystkich zewnętrznych źródeł.

## Instalacja i testy

Skopiuj katalog `mbtiles_batch_exporter` do katalogu wtyczek profilu QGIS i
włącz wtyczkę w menedżerze. Wymagany jest QGIS 3.40 z PyQt5 i GDAL co najmniej
3.7 (dostarczanym z QGIS). Testowane środowisko: QGIS 3.40.15, GDAL 3.12.2.

Testy integracyjne korzystają z QGIS i GDAL dostarczonych z QGIS oraz standardowego
`unittest`. Nie wymagają usług zewnętrznych ani danych firmowych. Test WMS
uruchamia własny serwer HTTP wyłącznie na `127.0.0.1`; jeśli środowisko blokuje
lokalne gniazda sieciowe, ten test jest pomijany i należy uruchomić go ze zgodą
na loopback:

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Uruchom polecenie interpreterem z dostępem do modułów `qgis` i `osgeo`.
Projekt nie ma osobnej konfiguracji lint, typecheck ani procesu build.

## Następne kroki

4. **Odbiór na rzeczywistym projekcie (pozostaje do wykonania w sieci firmowej):** mały obszar, następnie długi pas,
   stanowisko z dostępem do MSSQL i udziałów sieciowych; na końcu otwarcie
   przeniesionego folderu bez internetu, sieci firmowej i naszej wtyczki.

W miarę możliwości stosujemy [Ponytail](https://github.com/DietrichGebert/ponytail):
najpierw istniejący kod, standardowe funkcje i dostępne mechanizmy QGIS/GDAL,
dopiero potem minimalny potrzebny kod. To zalecenie, nie wymóg bezwzględny;
poprawność, czytelność, obsługa błędów i bezpieczeństwo danych mają pierwszeństwo.

Projektów użytkownika, danych firmowych i wygenerowanych archiwów nie dodajemy do repozytorium.
