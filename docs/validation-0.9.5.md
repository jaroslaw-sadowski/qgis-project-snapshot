# Audyt i odbiór 0.9.5 — 10 września 2026

## Ukończony przebieg firmowy 0.9.4

Przeanalizowano raport HTML, manifest, diagnostykę JSONL, zrzut okna oraz dwa
pliki pomocnicze GDAL aux.xml. Nie dostarczono właściwego GeoPackage; testu
wizualnej zgodności tego archiwum nie wykonano. Dane wejściowe pozostają poza Git.

- Czas 28 min 49,545 s, zoomy 13–17, 66 kafelków/mapę. Eksport nieanulowany,
  bez awarii koordynatora, ale wynik nadal częściowy.
- 211 warstw: 61 saved, 116 empty, 33 failed i 1 partial. Saved obejmuje
  33 MSSQL, 3 WFS, 3 lokalne rastry i 22 mapy.
- Wszystkie 139 procesów zakończyły się kodem 0, a ich wyniki scalono.
  Zapisano 1867 kafelków PNG z treścią. Z map empty 90 było całkiem pustych,
  26 miało treść na części zoomów. Status empty wymaga sprawdzenia także wtedy,
  gdy np. budynki są widoczne tylko na najwyższym zapisanym zoomie.
- 7090 obrazów było pustych przed maską obszaru; 155 maska wycięła całkowicie.
  Większości pustych wyników nie wyjaśnia maskowanie.
- Trzy WFS: received=written=0, bez zgłoszonych błędów, odczyt 0,016–0,063 s,
  brak zaobserwowanych żądań głównego procesu. Nie ustalono, czy to poprawny
  pusty wynik, pamięć podręczna czy problem dostawcy. Wymaga porównania z obiektami
  widocznymi w źródle.
- HTTP 200: 8174 PNG i 208 JPEG ze źródeł; format wyjściowy pozostaje PNG.
  Proxy aktywne w konfiguracji procesów. Brak podstaw do ogólnego stwierdzenia,
  że nic nie pobrano albo że GeoPackage nie może przechować WMS.
- Wszystkie 512 odpowiedzi XML rozpoznano jako GetCapabilities; pięć błędów
  Qt bez HTTP, brak 407/429/503 wskazujących na globalną awarię proxy/usług.
  Brak dowodu trasy każdego żądania wyłącznie na podstawie konfiguracji proxy.
- Aux.xml zawierają pomocnicze statystyki kanałów, nie kafelki. Statystyki
  przybliżone i różne wartości valid_percent nie dowodzą uszkodzenia bazy.
  [Dokumentacja GDAL PAM](https://gdal.org/en/stable/user/configoptions.html#persistent-auxiliary-metadata-pam-options).

## Przyczyna pozostawienia 33 map

Host mapy.geoportal.gov.pl miał 862 poprawne kafelki. Po timeoutach w 1268,515 s
rozpoczęła się przerwa 30 s. W 1298,875 s koordynator odłożył host z powodem
no_retryable_tiles bez próby powrotu. Jedna mapa została z 4 zapisanymi kafelkami
i 62 brakującymi, a 33 kolejne w ogóle nie zostały pobrane.

Wyczerpany kafelek miał trzy próby. Następny, jeszcze niepobrany fragment miał
attempts=0, więc WorkerGate nie zgłaszał go jako możliwej próby. Poprawka dopuszcza
rzeczywiście brakujący fragment, także z kolejnej mapy, po wymaganej przerwie.
Brak gotowego fragmentu podczas przygotowania rejestru nie odkłada już hosta.
Nie daje to czwartej próby wyczerpanemu kafelkowi ani nie ponawia sukcesów.
Nie gwarantuje też, że niedostępny serwer odzyska sprawność.

W adaptacji wszystkie błędy renderowania wracają do rejestru. Usunięto wewnętrzne
dodatkowe ponowienia/podziały dla HTTP 500 i innych błędów, które mogły przekroczyć
budżet trzech prób. Stały tryb API zachowuje dotychczasowe działanie.

## Równoległość i bezpieczna poprawa przydziału

Dwa procesy pracowały przez 1323,077 s, czyli 76,5% całego eksportu. Jeden przez
359,218 s, zero przez 47,250 s. Według pierwszych odpowiedzi sieciowych procesy
dwóch różnych hostów nakładały się przez 1201,425 s. Są to czasy życia procesów,
obejmujące start i oczekiwanie, nie dokładny pomiar równoczesnych żądań HTTP.
Zrzut 1/1 przedstawia chwilowy stan.

CPU: 14, dostępny RAM przy starcie: 4,36 GiB. Budżet zmieniał się 26 razy między
1 i 2 przy przekraczaniu 4 GiB wolnej pamięci. Zachowano rezerwę 2 GiB i szacunek
1 GiB na proces. Nie dodajemy sumy RSS do wolnego RAM, bo obejmuje ona również
strony współdzielone; nie zmieniamy rezerwy na podstawie niezmierzonego zużycia.

0.9.5 preferuje kwalifikujący się host z najmniejszą liczbą aktywnych procesów,
przy remisie zachowując kolejkę. Maksimum adaptacji to dwie mapy/host.
Wolny proces może więc najpierw rozpocząć pracę z kolejnym serwerem. Wystarczający
RAM pozwala pracować na wielu hostach równocześnie; przy około 4,4 GiB aktualna
ostrożna reguła nadal oznacza najwyżej dwa procesy.

Suma czasów procesów 3005,37 s (czasy nakładają się): renderowanie i sieć 68,3%,
start QGIS/źródła i zakończenie 17,0%, bramka/przerwy 5,1%, zapis 4,1%, maska 0,5%.
Pozostałe około 5% obejmuje operacje poza wymienionymi licznikami.
Nie zmieniono PNG RGBA/ZLEVEL=9, rozmiaru kafelka, masek ani wybranych zoomów.
Zwykły sukces nie wymaga potwierdzenia koordynatora przed kolejnym kafelkiem;
skracanie cyklu 0,5 s zwiększyłoby IPC bez usunięcia głównego kosztu.

Dla tego obszaru około 153 ha zoomy 13–20 to około 3650 kafelków/mapę, wobec 66
przy 13–17. Wzrost ponad 55 razy nie jest równoważony podwojeniem procesów.
Nie deklarujemy konkretnego przyspieszenia usług produkcyjnych.

## Pomiar kontrolowanego WMS

Istniejący benchmark uruchomił sześć map, dwa hosty, zoom 18 i opóźnienie 120 ms.
Stały tryb: 57,365 s, cztery procesy; adaptacyjny: 87,136 s, najwyżej dwa procesy.
Oba wykonały 1014 GetMap i zapisały identyczne bajty PNG; lokalny audyt poprawny.
[Surowy pomiar](benchmark-0.9.5.json).

To nie jest porównanie szybkości przy jednakowym budżecie. Skrypt podstawia RAM
przy starcie, ale pozostawia okresowy pomiar systemowy: dostępne około 4,16 GiB
ograniczyło automat do dwóch procesów, a końcowe 3,97 GiB do jednego. Tryb stały
miał narzucone cztery. Wynik potwierdza zachowanie ostrożnego limitu pamięci
oraz identyczność danych; nie dowodzi przyspieszenia ani regresji nowej kolejki.
Test czterech rzeczywistych hostów osobno sprawdza równoległość przy dostatecznym,
kontrolowanym budżecie RAM. Nie wykonano benchmarku szybkości firmowych serwerów.

## Weryfikacja poprawki

Nowe regresje sprawdzają:

- kontrolowany zegar, trzy timeouty kafelka, przerwę i powrót na następnym braku;
- ostatni wyczerpany kafelek poprzedniej mapy i dalszą kolejkę tego samego hosta;
- pojedynczą próbę, anulowanie, trzy nieudane powroty i limit HTTP 500;
- rzeczywiste procesy WMS: trzy HTTP 503 z Retry-After=0 dla jednego kafelka,
  powrót na następnym, zakończenie kolejnej mapy i pracy innego hosta;
- rejestr z attempts=3 dla błędnego fragmentu, attempts=1 dla pozostałych,
  scalenie trzech wyników i niepusty odczyt nowego projektu po wyłączeniu WMS;
- cztery różne hosty lokalnego WMS i dwie mapy każdego: bariera wymaga czterech
  rzeczywistych równoczesnych żądań przed udzieleniem pierwszej odpowiedzi;
- pierwszeństwo różnych hostów w kolejce z powtórzeniami oraz zgodność stałego API.

Pełne testy źródeł: **108/108**, 94,178 s, bez pominięć. Ruff check,
Ruff format --check (53 pliki Python), składnia kodu paczki i git diff --check
poprawne. Tłumaczenia PL/EN skompilowane: 278 kompletnych wpisów.
Gotowy ZIP: natywne wykrywanie, ładowanie, okno i wyłączenie wtyczki poprawne;
**108/108 testów z kodu paczki**, 93,161 s, bez pominięć. Ubuntu, QGIS 3.40.15,
GDAL 3.12.2, Python 3.14.4, PyQt5. Profile testów izolowane, lokalne gniazda HTTP
dozwolone; testy WMS/proxy rzeczywiście wykonane. Komunikaty GDAL o braku pikseli
do statystyk pochodzą z celowo przezroczystego obrazu w teście pustych wyników.

Paczka: `dist/qgis-project-snapshot-0.9.5.zip`, 109 583 bajty, 22 pliki.
SHA-256: `1bb8cd7ab0bec1fee19de76a22aa749a326d8fc268d5b27cb58e778ab6ce55e0`.
Kontrola CRC i porównanie wszystkich plików ZIP ze źródłami poprawne.
Nie opublikowano GitHub Release ani wydania w katalogu QGIS.

## Następna próba firmowa

Zainstalować ZIP 0.9.5, uruchomić ponownie QGIS i wykonać mały eksport zoomów
13–17 z widocznymi mapami kilku różnych hostów, w tym poprzednio odłożonego.
Pozostawić proxy i timeout skonfigurowane przez firmę. Sprawdzić wynik offline,
szczególnie wcześniej brakujące mapy, oraz WFS z konkretnymi obiektami w źródle.
Zachować raport, manifest i diagnostykę. Dopiero po odbiorze zwiększać zakres.
Nie wykonano testu tej wersji na firmowym Windows ani jego usługach MSSQL.
