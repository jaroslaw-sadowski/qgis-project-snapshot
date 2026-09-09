# Krok 4 — odbiór na dostępnych źródłach i pomiar wydajności

9 września 2026. Ubuntu, QGIS 3.40.15, GDAL 3.12.2, Python 3.14.4,
4 procesory logiczne widoczne dla systemu.

## Wynik

Odbiór dostępnego zakresu zakończył się poprawnie. Potwierdzono eksport
rzeczywistych map i WFS, odczyt bez sieci oraz identyczne PNG przy pracy
równoległej. Nie wykonano pełnego archiwum wszystkich 213 warstw.

## Rzeczywiste źródła z załączonego projektu

| Próba | Zakres | Wynik |
|---|---|---|
| Geoportal: ortofotomapa standardowa i BDOT10k | Oryginalne konfiguracje dwóch warstw, obszar 256 × 256 m w Warszawie, zoom 16, 2 procesy | Dwa poprawne rastry, po jednym kafelku, bez ponowień i bez zastępczego trybu zapisu; około 4,6 s łącznie z otwarciem źródeł |
| GDOŚ: elektrownie wiatrowe, WFS | Obszar 2 × 2 km bez obiektów | Poprawny pusty wynik, bez błędu i bez zastępowania danych obrazem |
| Ten sam WFS, obszar wokół istniejącego obiektu | Odczyt jednego obiektu do ustalenia obszaru, następnie eksport z buforem 128 m | Zapisano 2 obiekty jako wektory, około 4,1 s łącznie z otwarciem źródła i wyznaczeniem obszaru |
| MSSQL | Jedyny serwer wskazany w projekcie | Nazwa nierozpoznawana w DNS; bez logowania i zapytań do bazy |
| Trzy lokalne rastry GDAL | Ścieżki zapisane w projekcie | Pliki nie istnieją na tym Ubuntu |

Użytkownik potwierdził, że MSSQL jest dostępny z komputera służbowego w sieci
firmowej i nie będzie dostępny w obecnym środowisku. Nie zmieniano konfiguracji
połączenia ani oryginalnego projektu.

## Kontrola offline

Archiwum map przeniesiono do innego folderu i otwarto w nowym procesie QGIS
w środowisku blokującym tworzenie gniazd internetowych. Obie warstwy zostały
wyrenderowane. Licznik żądań sieciowych QGIS pozostał równy **0**. Obejrzano
podglądy ortofotomapy i BDOT10k; obszar poza maską jest przezroczysty.

Archiwum WFS otwarto również bez sieci: **2 obiekty, 15 pól** w warstwie lokalnej
(w tym pola techniczne eksportu), poprawne geometrie, dostępne wartości
atrybutów i niepusty render. Licznik żądań sieciowych: **0**.

Pliki tych prób pozostawiono roboczo w `/tmp/qgis-step4`; nie są częścią repo
i mogą zostać usunięte przez system. Ten odbiór potwierdza małe próbki,
nie kompletność wszystkich danych usług ani całego projektu.

## Pomiar 1, 2 i 4 procesów

Powtarzalny skrypt: `tests/benchmark_archive.py`.
Pełne pomiary: [benchmark-step4.json](benchmark-step4.json).

Warunki: cztery warstwy z dwóch lokalnych serwerów WMS, każdy odpowiada po
50 ms, bufor HTTP wyłączony, EPSG:2180, zoom 17, PNG RGBA. Mały obszar ma
512 × 512 m. Pas ma około 10 km długości i 150 m szerokości. Dla każdego
wariantu wykonano jeden przebieg, w kolejności 1, 2, 4; nie są to średnie
z wielu powtórzeń.

| Obszar | Procesy | Czas | Suma szczytowego RSS | Kafelki | Żądania map |
|---|---:|---:|---:|---:|---:|
| Mały | 1 | 3,85 s | 286 MB | 36 | 36 |
| Mały | 2 | 4,64 s | 817 MB | 36 | 36 |
| Mały | 4 | 3,58 s | 1341 MB | 36 | 36 |
| Pas 10 km | 1 | 45,13 s | 331 MB | 460 | 460 |
| Pas 10 km | 2 | 24,20 s | 924 MB | 460 | 460 |
| Pas 10 km | 4 | 13,26 s | 1522 MB | 460 | 460 |

Dla pasa cztery procesy były około **3,4 raza szybsze** niż jeden. Dla małego
obszaru narzut uruchamiania procesów ogranicza korzyść; dwa procesy były
wolniejsze od jednego. Obserwowano do dwóch jednoczesnych żądań na serwer.

RSS obejmuje aplikację testową i procesy potomne; współdzielone strony pamięci
są liczone osobno dla każdego procesu. Odczyt co 100 ms jest przybliżeniem,
a nie dokładnym pomiarem unikalnego wykorzystania RAM. Wartości MB są dziesiętne.

Zawartość PNG porównano skrótem SHA-256 w stałej kolejności warstw i kafelków:
**obrazy były identyczne we wszystkich wariantach danego obszaru**. Wszystkie
sześć archiwów przeniesiono i wyrenderowano po zatrzymaniu obu serwerów.

Serwery testowe zwracają proste, jednobarwne obrazy. Pomiar sprawdza kolejkę,
opóźnienia sieciowe, narzut procesów i zgodność wyników; nie odwzorowuje kosztu
kompresji ortofotomapy ani rozmiarów produkcyjnego archiwum. Szczytowe miejsce
na dysku zapisano w JSON, ale nie należy przeliczać go na zapotrzebowanie dla
rzeczywistych map. Cztery warstwy nie zastępują testu całych 213 warstw.

## Regresja i pozostały odbiór

Wszystkie **29 testów integracyjnych przeszło**, podobnie jak kontrola składni
Pythona i `git diff --check`. Nie dodano zależności ani nie zmieniono działania
eksportera w tym kroku; rozszerzono narzędzia testowe i dokumentację.

Na komputerze służbowym pozostaje eksport MSSQL i trzech plików lokalnych,
pełny projekt oraz wizualne porównanie symboliki, etykiet, formularzy i wydruków.
Nie zweryfikowano wszystkich dostawców, konfiguracji uwierzytelniania,
alternatywnych CRS, kodu formularzy i dowolnych zależności wyrażeń.
Do zakończenia tego odbioru zachowujemy oznaczenie archiwum wymagającego kontroli.
