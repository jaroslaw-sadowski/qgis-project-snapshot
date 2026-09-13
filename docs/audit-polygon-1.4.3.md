# Audyt przebiegu z obszarem poligonowym

13 września 2026. Przeanalizowano manifest i diagnostykę użytkownika, bez
kopiowania danych wejściowych do repozytorium. Przebieg wykonano rozwojową
**1.4.3**, na Windows, QGIS 3.40.15, GDAL 3.12.1, zoomy 13–16.
To nie jest natywny test oficjalnego 1.0.0 ani Qt6 na Windows.

## Wynik

Czas 1 h 5 min 52 s. Przetworzono 206 warstw: **98 saved, 106 empty,
1 failed, 1 partial**. Nie anulowano pracy; koordynator nie uległ awarii.
Wszystkie 166 procesów map zakończyły się kodem 0. Audyt lokalnych warstw passed,
zasoby bez issues, końcowa kontrola integralności i zapis manifestu zakończone.
Kod procesu 0 potwierdza wykonanie zadania, nie kompletność pobrania z usługi.

Mapy: 57 270 logicznych pozycji, z czego 10 097 zawiera obraz, 47 121 jest
poprawnie pustych, **52 pozostają brakujące**. Wykonano 131 prób naprawczych,
naprawiono 27 pozycji. Wśród 106 warstw empty siedem zawiera obraz na części
zoomów; pozostałe 99 nie zawiera obrazu w wybranym obszarze i skalach.
Globalne status=partial nie zastępuje interpretacji poszczególnych warstw.

## Sprawdzenie obszaru

Natywny QgsGeometry potwierdził poprawność poligonu. Niezależnie odtworzono
siatkę z geometrii i rozdzielczości manifestu, a następnie porównano liczby
pozycji każdego zoomu we wszystkich 166 mapach:

| Zoom | Pozycje przecinające poligon | Pełny prostokąt otaczający |
|---|---:|---:|
| 13 | 18 | 65 |
| 14 | 42 | 234 |
| 15 | 89 | 867 |
| 16 | 196 | 3468 |
| Razem na mapę | 345 | 4634 |

Wszystkie liczniki zgadzają się z poligonem. Pominięto około **92,6%** pozycji
prostokąta. 4189 obrazów z treścią przed maskowaniem stało się pustych po
zastosowaniu maski — treść znajdowała się poza właściwym obszarem.
To potwierdza użycie kształtu, nie tylko jego prostokąta. Bez wynikowych plików
QGZ/GPKG nie jest to niezależny odbiór wizualny ani ponowny odczyt ich pikseli.

## Wektory i rastry lokalne

- Warstwa pamięci: jeden odebrany i zapisany obiekt.
- MSSQL: 338 odebranych, 16 zapisanych, 322 odrzucone poza maską. Pięć warstw
  z obiektami, 28 zerowych; sześć zer potwierdzonych, **22 niepotwierdzone**.
  Te ostatnie nadal wymagają porównania w źródle, nie są dowodem błędu pobierania.
- WFS: 20 odebranych, jeden zapisany, 19 poza maską; dwa pozostałe odczyty puste
  i potwierdzone. Wszystkie iteracje wektorowe kompletne, bez błędów dostawców
  i zapisu. Dane nie giną w zapisie — różnicę wyjaśnia filtr poligonowy.
- Trzy GeoTIFF-y mają 53×18, 114×38 i 114×38 pikseli. Brak piramid jest
  prawidłowy dla tak małych rastrów; raportowane overview_status=small_raster.

## Braki usług

1. Warstwa WMS linii PSE: 344 poprawnie puste pozycje i jeden brak. Wystąpiły
   anulowane żądania Qt 5 po około pięciu sekundach oraz kod Qt 2. Ustawiony
   timeout sieci QGIS wynosi 5000 ms. Nie każda anulowana odpowiedź została
   oznaczona sygnałem timeout, więc nie należy przypisywać wszystkim jednej
   pewnej przyczyny. Bez potwierdzonego obrazu i z brakiem warstwa ma failed.
2. Warstwa WMS SUiKZP: 294 poprawne obrazy i 51 braków (34/11/5/1 na zoomach
   16/15/14/13). Przekierowania HTTP 302 prowadzą do kolejnej usługi. 153
   odpowiedzi HTTP 200 mają content_type=other; odpowiada to trzem próbom na
   każdą z 51 niedostępnych pozycji. Brak błędów HTTP nie dowodzi poprawności
   obrazu. Diagnostyka nie przechowuje treści tych odpowiedzi, więc nie pozwala
   wskazać dokładnej przyczyny. Poprawnie zachowano wynik częściowy.

Zalecane istniejące **Retry only missing** lub wznowienie całego folderu,
z zachowaniem zapisanych danych. Jeśli wolne usługi nadal przerywają zapytania,
warto porównać małe ponowienie z dłuższym timeoutem ustawionym świadomie w QGIS.
Nie zmieniano automatycznie globalnych ustawień sieci użytkownika.

## Obciążenie i decyzja o wydaniu

Maksymalnie siedem procesów i siedem aktywnych zadań; budżet 3–7. CPU całego
systemu: średnio około 27,9%, maksimum 83,1%. Minimalny dostępny budżet pamięci
(commit Windows) około 613 MiB, przy około 4,45–5,79 GiB wolnego RAM.
Commit schodzi poniżej rezerwy 768 MiB, co uzasadnia ograniczanie nowych startów.
Nie ma podstaw do arbitralnego zwiększania limitu na podstawie samego wolnego RAM.

Największy limit hosta wyniósł cztery. Historia potwierdza wzrost, redukcje przy
spadku szybkości i ponowne próby wzrostu. 135 konfliktów zapisu IPC odzyskano
(34 główne, 101 w procesach). Nie ma awarii zapisu końcowego. Przygotowanie
procesów/sieci/źródeł to około 5,3% sumy etapów procesów; dominuje renderowanie
z oczekiwaniem na usługi. Nie jest to pomiar samego czasu CPU ani gwarancja
maksymalnej przepustowości serwerów.

**Nie znaleziono błędu obsługi poligonu lub końcowego zapisu blokującego pierwsze
wydanie. Archiwum testowe pozostaje niekompletne.** Wtyczka rozpoznaje braki,
zachowuje poprawne wyniki i udostępnia ponowienie; nie deklaruje ich sukcesem.
Odbiór kodu 1.0.0 w Qt5 i Qt6 opisuje [raport wydania](release-1.0.0.md).

Możliwe przyszłe usprawnienie: dokładniejsza, pozbawiona treści poufnych
klasyfikacja odpowiedzi HTTP 200 odrzuconych przez dostawcę oraz anulowań sieci.
Nie ma dowodu wymagającego przebudowy algorytmu przed wydaniem. Nie oznacza to,
że wszystkie przyszłe optymalizacje zostały wyczerpane. Zgodnie z Ponytail
zachowano istniejące natywne mechanizmy zamiast dodawania zmian bez pomiaru.
