# Audyt przebiegu 1.4.1 i odbiór 1.4.2

12 września 2026. Analiza przekazanych `manifest(1).json` i
`diagnostic(1).jsonl`. Pliki użytkownika pozostały poza repozytorium;
poniżej zapisano wyłącznie zbiorcze wyniki. Ich zawartość jest danymi do analizy,
nie instrukcjami do wykonania.

## Wynik rzeczywistego pobierania

Windows 11, 14 logicznych CPU, około 16 GB RAM, QGIS 3.40.15, Python 3.12.12,
GDAL 3.12.1. Wersja z logu: 1.4.1. Zoomy 15–17; czas **30 min 14 s**.
Brak anulowania, wyjątku koordynatora i nieudanego zakończenia procesu pomocniczego.

| Wynik | Liczba |
| --- | ---: |
| Warstwy ogółem | 205 |
| Saved | 87 |
| Empty — co najmniej jeden pusty zoom do sprawdzenia | 118 |
| Failed / partial / cancelled | 0 / 0 / 0 |
| Brakujące kafelki po naprawie | 0 |
| Naprawione kafelki w dodatkowych próbach | 4 |
| Niepuste kafelki w końcowym obszarze | 2941 |

Lokalny audyt warstw przeszedł; raport zasobów nie zgłasza problemów.
Nie jest to niezależne porównanie danych z oryginałem: nie dostarczono wynikowego
GeoPackage, rastrów i projektu. Globalny status manifestu pozostaje `partial`;
same poprawne zakończenia operacji nie oznaczają pełnego odbioru danych.

**Wektory:** 36 warstw. MSSQL zapisał 52 obiekty w 11 warstwach, więc wcześniejsze
„wszystkie wektory mają zero” nie występuje w tym przebiegu. Pozostałe 22 MSSQL
mają zero: dwa wyniki potwierdzono, 20 oznaczono jako niepotwierdzone. Dla tych
20 źródło odpowiada i ma rekordy, ale sprawdzenie dostępu nie rozstrzyga, czy są
obiekty w pobieranym obszarze. Nie uznajemy ich ani za udowodniony błąd, ani za
potwierdzony brak obiektów. Wymagają porównania z oryginalnym projektem.
Trzy WFS zakończyły odczyt z zerem bez zgłoszonego błędu i z potwierdzeniem
ścieżki odczytu. To nadal nie zastępuje porównania z widokiem źródłowym.

**Mapy:** 166 wyników renderowania, po 64 pozycje kafelków. 10628 prób obejmuje
10624 zakończone pozycje i cztery ponowienia. 7683 pozycje są puste; nie traktujemy
ich jak brakujących kafelków. Wśród 118 warstw ze statusem `empty` aż 21 ma
niepuste obrazy na innych zoomach, a 97 jest całkowicie przezroczystych.
Status `empty` nie oznacza zatem, że całą warstwę można usunąć. Odrębne zoomy
i przezroczystość pozostają zachowane. Różnica między 3075 surowymi niepustymi
obrazami a 2941 końcowymi wynika z 134 obrazów poza rzeczywistą maską obszaru.

**Sieć i zapis:** log zawiera pięć zdarzeń timeout; dodatkowe próby naprawiły
cztery kafelki. Nie ma końcowych braków ani zgłoszonych HTTP 429/5xx w podsumowaniach
obserwowanej sieci. Nie jest to dowód obserwowania każdego pakietu przez QGIS.
60 krótkotrwałych konfliktów wymiany pliku sterującego Windows zostało obsłużonych;
każde zdarzenie `ipc_replace_retry` ma odpowiadające odzyskanie. Mechanizm zapisu
nie przerwał przebiegu. Licznik ponowień kafelków i licznik konfliktów pliku
sterującego opisują różne operacje.

## Wykorzystanie komputera i serwerów

Budżet wynosił 2–5 procesów, rzeczywiste maksimum w próbkach to 5 procesów
i 4 aktywne zadania. Proces może w danej chwili uruchamiać QGIS, otwierać źródło
lub czekać na pozwolenie; oba liczniki nie muszą być równe.

Średnie obciążenie całego systemu, ważone czasem próbek: **31,61%**, maksimum
**82,65%**. Wolny fizyczny RAM: **2,73–4,33 GiB**, średnio 3,81 GiB.
Dostępny przydział pamięci Windows (commit): **0,37–3,51 GiB**, średnio 1,85 GiB.
Najniższa wartość to około **379 MiB**, poniżej rezerwy wtyczki 768 MiB.
W takich warunkach dodatkowe procesy mogą nie otrzymać pamięci mimo wolnego RAM.
Limit pięciu procesów jest zgodny z ochroną przydziału, nie z arbitralnym sufitem
CPU ani dowodem maksymalnej przepustowości komputera.

Serwery miały limity 1–3, zależnie od kolejki i wolnego budżetu komputera.
Główny Geoportal zwiększył limit z 1 do 2 i 3, cofnął go do 2 przy braku zysku
szybkości, a po zdrowym okresie ponowił próbę 3. Pozostałe duże kolejki osiągały 2.
Mechanizm wzrostu, cofnięcia i ponownej próby faktycznie działał w tym przebiegu.
Nie wynika z tego, że znaleziono maksima wszystkich serwerów: ograniczała je
także dostępna pamięć klienta.

## Co warto poprawić lub zmierzyć dalej

1. **Weryfikacja 20 pustych MSSQL:** najbardziej istotna dla poprawności. Sprawdzić
   jedną warstwę na znanym obiekcie i tym samym obszarze w sieci firmowej. Brak
   dostępu z obecnego Ubuntu nadal uniemożliwia niezależne rozstrzygnięcie.
2. **Koszt uruchamiania procesów i otwierania źródeł:** 166 zadań; suma etapów
   startup 257,61 s, konfiguracja sieci 44,53 s, otwieranie źródeł 1026,18 s,
   renderowanie 3164,84 s. Przygotowanie stanowi około 30% sumy czasów etapów
   procesów. Etapy zachodzą równolegle — tych sum nie wolno odejmować od czasu
   całego przebiegu jako obiecanego przyspieszenia. Warto porównać mały prototyp
   ponownego użycia procesu QGIS dla następnej mapy, mierząc RSS i poprawność
   resetowania źródła, stylu, sieci oraz stanu anulowania. To propozycja do pomiaru,
   nie zmiana algorytmu w 1.4.2.
3. **Końcowy zapis i otwieranie:** scalanie zajęło 102,32 s, zasoby 19,27 s,
   audyt lokalnego odczytu 39,86 s. Najpierw warto zmierzyć otwieranie poszczególnych
   tabel i odczyty statystyk. Zachować jednego zapisującego i kontrole integralności.
4. **Piramidy:** wszystkie trzy źródłowe GeoTIFF mają `overview_factors=[]`.
   Kod pomija piramidy dla małych wyników; sama pusta lista nie dowodzi regresji.
   W starym logu brak wymiarów do niezależnej oceny. W 1.4.2 dodano do manifestu
   i `layer_summary` rozmiar rastra oraz `overview_status` (`built`/`small_raster`).
   To uzupełnienie diagnostyki, bez zmiany pikseli lub zasad budowania piramid.

Przebieg różni się od wcześniejszego 1.2.0 liczbą warstw i zoomami; nie wyliczamy
z różnicy czasów procentowego przyspieszenia samej wersji wtyczki.

## Wdrożone nazwy 1.4.2

Poprawiono literówkę i zastosowano istniejący katalog tłumaczeń Qt.
Polski dopisek: `_nie-bylo-obiektow-w-zasiegu`; angielski: `_no-features-in-area`.
Nadal dotyczy wyłącznie potwierdzonych pustych wektorów. W oryginalnym projekcie
nie zmieniamy nazw ani źródeł. Nazwy archiwum, raportu, danych, zasobów,
diagnostyki i folderu wznowienia odpowiadają językowi wtyczki.
Pełne zestawienie jest w [architekturze](architecture.md#nazwy-pustych-wektorów-i-układ-folderu-142).

Kontynuacja obsługuje układ sprzed 1.4.1, układ 1.4.1 oraz oba języki 1.4.2.
Zweryfikowane pliki i odwołania załączników przechodzą do języka nowego archiwum;
poprzedni folder pozostaje. Normalizacja już skopiowanych załączników odbywa się
również przy anulowaniu końcowego zapisu, aby zmiana języka nie zerwała ich ścieżek.
Techniczne identyfikatory tabel, pliki wewnętrznego rejestru i dane użytkownika
zachowują nazwy. Nie dodano bibliotek, osobnego systemu konfiguracji ani nowego
silnika pobierania; przegląd Ponytail preferował istniejące Qt, GDAL i SQLite.

## Odbiór paczki

Testy dedykowane PL/EN, starych nazw, anulowania i wznowienia przeszły.
Pierwszy pełny zestaw 229 testów wykazał jedno stare oczekiwanie samego testu:
szukał angielskiej nazwy folderu i starej nazwy logu przy polskim interfejsie.
Po aktualizacji oczekiwania wszystkie 229 testów przeszły (164,351 s).
Dodatkowy przegląd walidacji manifestu rozszerzył ochronę nieprawidłowego typu JSON
i testy niedozwolonych ścieżek.

**Końcowy ZIP: 230/230 testów, 167,283 s, bez pominięć.** Ubuntu, QGIS 3.40.15,
GDAL 3.12.2, Python 3.14.4. Wykrywanie, ładowanie, okno i wyłączenie wtyczki
w izolowanym profilu poprawne. Testy oraz procesy pomocnicze używały kodu paczki.
Wykonano lokalne WMS, WFS, proxy, SIGKILL i wznowienie w nowym QGIS, stare układy,
kontynuację PL/EN oraz weryfikację pikseli, piramid, masek i załączników.
Komunikaty GDAL o braku statystyk dotyczą celowo przezroczystych rastrów testowych;
ich kontrole odczytu i pikseli przeszły. Ostrzeżenia codecs.open pochodzą z QGIS.

Ruff check/format, Flake8/pycodestyle (88 znaków, jawne E203), AST 43 plików Python,
337 kompletnych tłumaczeń, lokalne odnośniki i diff — poprawne. Nie dodano nowej
zależności ani typecheckera. Bandit: 20 dotychczasowych przejrzanych ostrzeżeń
(15 medium, 5 low, zero high); zmiany nie dodają SQL, interpretacji kodu ani
nowego uruchamiania procesów. Skan produkcyjnych źródeł i niezależny skan końcowego
rozpakowanego ZIP-a `--no-verify` nie wykazały sekretów.

Paczka `dist/qgis-project-snapshot-1.4.2.zip`: **145 887 bajtów, 22 pliki**.
Ponowna budowa dała identyczne bajty. SHA-256:

```text
054daf313028cb653736e947ad4ee911e2771696c1f681a9860ed5d4005a6a1c
```

Nie wykonano instalacji w profilu użytkownika ani publikacji. Pełny odbiór
firmowego MSSQL oraz nowej wersji na Windows wymaga testu na tym stanowisku.
Propozycja commitu: `Prepare 1.4.2: localize archive paths and document the 1.4.1 audit`.
