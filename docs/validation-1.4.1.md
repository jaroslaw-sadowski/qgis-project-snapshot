# Odbiór 1.4.1 — puste warstwy i porządek w archiwum

12 września 2026. Ubuntu, QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4.

## Zakres

Potwierdzony pusty wektor otrzymuje dokładnie dopisek
`_nie-bylo-obiketow-w-zasiegu`, zgodnie z pisownią zleconą przez użytkownika.
Warunki: poprawnie zapisany wektor, zero obiektów oraz `empty_read_verified=true`.
Błąd odczytu, niepotwierdzone zero MSSQL i obraz zastępczy nie otrzymują dopisku.
Nazwa zmienia się w wynikowym projekcie, drzewie, raporcie i identyfikatorze
GeoPackage. Oryginalny projekt i `name` manifestu pozostają bez zmian;
`output_name` opisuje nazwę wynikową. ID warstw i techniczne nazwy tabel
pozostają stabilne. Ponowne użycie wyniku nie powiela dopisku.
GeoPackage wymaga unikalnych identyfikatorów: powtarzająca się etykieta otrzymuje
krótkie rozróżnienie w nawiasie wyłącznie w identyfikatorze bazy.

Główny folder zawiera projekt QGZ, `raport.html` oraz podfoldery:

- `dane/`: GeoPackage i jego pomocnicze pliki statystyk AUX.
- `diagnostyka/`: manifest, log JSONL i stan kafelków, gdy pobieranie wymaga
  kontynuacji. Ukończony eksport usuwa pusty folder `download-state`.
- `zasoby/`: dodatkowe pliki projektu, tylko gdy są potrzebne.

Raport PL/EN objaśnia te foldery, wskazuje projekt do otwarcia i udostępnia pełny
JSON pod rozwijaną pozycją szczegółów diagnostycznych. Nie dodano kolejnego
pliku instrukcji do każdego archiwum. Zachowano całą dotychczasową diagnostykę.

Manifest ma nadal schemat 4; `data_file` wskazuje `dane/dane.gpkg`.
Starszy manifest w katalogu głównym, GeoPackage w katalogu głównym i dawny
`download-state` są odczytywane i przenoszone do nowego układu podczas kontynuacji.
Ścieżki, sumy kontrolne, atomowe checkpointy i blokady nadal są sprawdzane.
Cały poprzedni folder należy zachować; wynik kontynuacji powstaje osobno.

## Statystyki GDAL

Natywna próba z osobnym procesem QGIS potwierdziła, że przeniesienie GeoPackage
wraz z AUX zachowuje odczyt statystyk bez ich ponownego tworzenia. Bajty i czas
modyfikacji AUX, kafelki PNG, CRS, transformacja i piramidy pozostały niezmienione.
Sprawdzono też dwie tabele rastrowe. Nie pojawiły się AUX w katalogu głównym.

Nie przenosimy samych AUX do folderu diagnostycznego ani nie wyłączamy PAM.
GDAL tworzyłby wtedy statystyki ponownie. Zapisywanie wszystkich statystyk
zoomów jako jednej metadanej bazy nadpisywało wartości różnych poziomów.
Przy kontynuacji w nowym archiwum statystyki nadal są odtwarzane podczas lokalnego
audytu, ponieważ częściowe tabele mogą być zastępowane. Zachowanie gotowych AUX
dotyczy otwierania i przenoszenia całego gotowego archiwum.
Zasady natywnego cache opisuje
[GDAL PAM](https://gdal.org/en/stable/user/configoptions.html#persistent-auxiliary-metadata-pam-options).

## Weryfikacja

Pierwszy pełny odbiór ZIP-a: **225/225 testów, 153,385 s, bez pominięć**.
Obejmował nowe nazwy, odczyt archiwum po przeniesieniu, statystyki przy GeoPackage,
migrację ukończonych danych i anulowanego workera ze starego układu, wznowienie
po zabiciu QGIS w innym procesie oraz dotychczasowe kontrole WMS/WFS/proxy.

Równoległy przegląd wykrył przypadek nieuwzględniony w dotychczasowych testach:
nieudany odczyt i nieudany obraz zastępczy dawnego niepotwierdzonego vector0
uruchamiały odzyskiwanie tabeli wektorowej jak częściowego rastra, przerywając
całe wznowienie. Nowy test odtworzył błąd przed zmianą. Ograniczenie odzyskiwania
obrazu do `method=raster_render` usunęło przyczynę. Pięć testów nazw i tego
przypadku przeszło: tylko wadliwa warstwa ma failed, pozostałe wyniki pozostają
poprawne, a błędny wektor nie otrzymuje dopisku.

Końcowy odbiór po poprawce: **226/226 testów, 158,736 s, bez pominięć**.
Wykrywanie, ładowanie, otwarcie okna i wyłączenie paczki w izolowanym QGIS — OK.
Testy i procesy pomocnicze używały kodu rozpakowanego ZIP-a. Lokalne WMS, WFS
i proxy wykonane. Komunikaty GDAL o braku statystyk dotyczą celowo przezroczystych
obrazów w testach, a ostrzeżenia codecs.open pochodzą z QGIS/Processing.
Kontrole pikseli, zoomów i odczytu tych obrazów przeszły.

Ruff check/format, Flake8/pycodestyle (88 znaków i jawna konwencja E203),
AST 42 plików Python, lokalne odnośniki i diff — poprawne. Flake8 uruchomiono
z `--jobs=1`, ponieważ sandbox blokował gniazdo jego serwera procesów; zakres
reguł pozostał pełny. Katalog PL/EN: 325 kompletnych tłumaczeń, kontrola pól
formatowania i kompletności AST poprawna. Skan sekretów źródeł `--no-verify`
bez trafień. Bandit nadal 20 przejrzanych ostrzeżeń (15 medium, 5 low, zero high),
dotyczących istniejących parserów XML, kontrolowanych identyfikatorów SQL
i ustalonego procesu pomocniczego. Nie wyłączono reguł ani nie dodano zależności.

Paczka: `dist/qgis-project-snapshot-1.4.1.zip`, **144 567 bajtów, 22 pliki**.
Ponowna budowa potwierdziła identyczne bajty. Niezależny skan rozpakowanej paczki
`--no-verify`: zero trafień. Paczka nie zawiera danych użytkownika, logów, profili
ani instrukcji agentów. SHA-256:

```text
9b43991a8e4a3c532e46417caef9dbef86c3012f032e7f3b0413b96a24099921
```

Przegląd Ponytail: wykorzystano istniejące rekordy, natywne nazwy QGIS/GDAL,
podfoldery i HTML `details`. Nie dodano zależności ani odrębnego systemu
diagnostyki. Pozostały kontrole integralności i izolacja procesów QGIS.

## Granice odbioru

Firmowy MSSQL nadal wymaga sprawdzenia w dostępnej sieci, a Windows rzeczywistej
próby na stanowisku użytkownika. Nie zmieniano limitów obciążenia serwerów ani
jakości danych. Szczegółowe ograniczenia odczytu i wznowienia opisuje
[odbiór 1.4.0](validation-1.4.0.md).

Propozycja commitu: `Prepare 1.4.1: label verified empty vectors and simplify archive layout`.
Nie wykonano commitu, push, publikacji ani instalacji w profilu użytkownika.
