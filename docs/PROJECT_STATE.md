# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 10 września 2026. Wersja wtyczki: **0.7.2**.
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
7. Wersja 0.6.0: szczegółowy postęp, stany warstw i procesów, dziennik, podpowiedzi
   oraz nazwa qgis-project-snapshot w menedżerze, menu i oknach.
8. Wersja 0.7.0: PL/EN według języka QGIS, przewijany wynik i zaznaczanie warstw
   do ponowienia, diagnostyka w HTML, dobór CPU/RAM/sieci, do 32 procesów
   i konfigurowalny limit na serwer; kolejka nie blokuje innych hostów.
9. Wersja 0.7.1: obok kafelków przedział czasu i rozmiaru PNG na jedną mapę,
   aktualizowany po zmianie obszaru/zoomów, PL i EN.
10. Wersja 0.7.2: trwałe czerwone ostrzeżenia HTTP 429/503 z procesów map,
    zapis diagnostyki i możliwość ograniczenia do 1 zadania na serwer.

Wynik eksportu nadal ma status archiwum częściowego/do odbioru. To celowe,
ze względu na nierozstrzygnięte zależności i brak pełnego odbioru firmowego.

## Sprawdzona paczka i wyniki

- `dist/qgis-project-snapshot-0.7.2.zip`, 93,789 bajtów, 19 plików.
- SHA-256: `3afbda686256ba325205da1ad696146dda2015d432b151675f874f21f6fb448b`.
- Build: `python3 scripts/build_plugin.py`. `dist/` nie jest wersjonowany.
- 43 testy integracyjne przeszły z kodu ZIP-a, bez pominięć WMS (32,00 s).
  Sprawdzono warianty en_US/en_GB/en_AU i pl_PL, angielski raport oraz procesy,
  ponowienie po anulowaniu, limity CPU/RAM i brak blokowania wolnych serwerów.
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

Identyfikator instalacji pozostaje `mbtiles_batch_exporter` dla zgodności aktualizacji.
Przy komunikatach użytkownika o braku postępu sprawdź dziennik i stany z procesów;
nie zastępuj rzeczywistych informacji sztucznym procentem lub prognozą czasu.

## Ustalenia wersji 0.7.0 dla następnego agenta

- Tłumaczenia: `i18n.py`, natywny katalog Qt `en.ts` + `en.qm`. Po zmianach
  uruchom `lrelease` i sprawdź zgodność szablonów. Katalog trafia do ZIP-a.
- Ponowienie: zaznaczane są failed/cancelled/empty/partial, saved i excluded
  są odznaczane. Przycisk uruchamia zaznaczone warstwy w nowym archiwum;
  brak łączenia lub naprawy poprzedniego folderu. Jest to opisane w interfejsie.
- Rekomendacja zasobów jest heurystyką. RAM dostępny: Linux/Windows; inne systemy
  zachowawczo. Stan sieci nie oznacza testu internetu ani VPN. **Przepustowość
  nie jest mierzona**; nie opisuj tego jako automatycznego speedtestu lub gwarancji
  optymalnej szybkości. Dla jednego serwera domyślnie maksymalnie 2 procesy,
  chyba że użytkownik zwiększy limit i ponowi dobór.
- Nie wykonywano nowego benchmarku 32 procesów ani odbioru w Windows/sieci firmowej.
  Poprzednie wyniki benchmarku nie są pomiarem nowej wersji.
- Test ZIP-a wykrywa i otwiera oba okna; ekran EN sprawdzono dodatkowo na zrzucie
  z Qt offscreen. Nie zastępuje to ręcznej próby na komputerze użytkownika.

## Szacunek 0.7.1

Użytkownik poprosił o czas i rozmiar obok liczby kafelków. Dodano model planowania
na jedną mapę, cały zakres zoomów i prostokąt obszaru: 0,2–2 s oraz 10–250 KiB
PNG na kafelek. To jawne założenia, nie pomiar lub gwarantowane granice; pełne
ograniczenia w podpowiedzi. Nie dziel czasu jednej mapy przez liczbę procesów.
Nie obejmuje wektorów, rastrów źródłowych, zasobów, scalania, kontroli i miejsca
tymczasowego. Zakres może zawyżać ilość dla pasa i pustych kafelków.

Test ZIP-a 0.7.1: 41/41, bez pominięć WMS; istniejący test UI sprawdza też zmianę
szacunku przy zmianie zoomu. Katalog Qt 317 tłumaczeń. Sprawdzono wysokość etykiety
w Qt offscreen (50 px, pełny tekst). Nie wykonano pomiaru kalibrującego model.

## Ostrzeżenia serwera 0.7.2

- HTTP 429: czerwone ostrzeżenie i zakończenie bieżącej mapy bez ponowień kafelka.
  HTTP 503: ostrzeżenie o niedostępności/możliwym przeciążeniu, bez przypisywania
  przyczyny wyłącznie liczbie zapytań. Pozostałe zadania czekają na ręczne Przerwij.
- Osobny istniejący parametr Zadania na serwer ma wartości 1/2/4/6/8 (domyślnie 2).
  Nie jest dokładnym limiterem HTTP na sekundę.
- Ostrzeżenia mają trwały prefiks [HTTP 429]/[HTTP 503], tłumaczoną treść i host,
  bez URL/poświadczeń. Są zachowywane w progress.json niezależnie od ostatniego
  postępu oraz w raster.server_warnings manifestu/HTML. Baner pozostaje do nowego eksportu.
- Testy wykryły zagłuszanie normalnego postępu przez częste 503; poprawiono zapis
  ostrzeżeń tak, aby nie resetował zegara ograniczającego zwykłe aktualizacje.
- Odbiór finalnego ZIP-a: 43/43, 32,00 s, bez pominięć. WMS rzeczywisty lokalny:
  HTTP 429, brak powtarzania kafelka, raport; HTTP 503 z poprawnym odzyskaniem obrazu,
  postęp oraz ostrzeżenia w procesach PL/EN. UI: trwałość czerwonego ostrzeżenia
  po zwykłym postępie i ukończeniu procesu. Nie testowano serwerów firmowych.
- Katalog Qt: 319 tłumaczeń. ZIP CRC, zgodność źródeł, składnia i diff: OK.
