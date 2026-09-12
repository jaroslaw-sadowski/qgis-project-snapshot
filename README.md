# <img src="mbtiles_batch_exporter/icon.svg" width="40" height="40" alt=""> QGIS Project Snapshot

Polski · [English](README.en.md) · Wersja **1.4.3**

## Co to jest i co robi

QGIS Project Snapshot tworzy lokalną kopię projektu QGIS do późniejszego odczytu
bez internetu. Pomaga zachować dane i wygląd map, zanim zmienią się źródłowe
bazy lub usługi.

W osobnym folderze zapisuje kopię projektu, wektory z atrybutami, obrazy map,
lokalne rastry i dostępne zasoby oraz raport. Zachowuje grupy, kolejność,
widoczność i style warstw. Mapy PNG zachowują przezroczystość. Wybierasz warstwy,
obszar oraz poziomy szczegółowości; oryginalny projekt pozostaje bez zmian.

## Co jest potrzebne do instalacji

- **QGIS 3.40 lub nowszy z serii 3.x**, z Qt5/PyQt5 i GDAL co najmniej 3.7.
  Wtyczka korzysta z bibliotek dostarczanych z QGIS; nie instalujesz osobno Pythona
  ani dodatkowych pakietów.
- Dostęp do źródeł projektu podczas tworzenia archiwum i miejsce na dysku.
- Uprawnienie do pobierania i przechowywania wybranych danych oraz map.

Interfejs jest po polsku lub angielsku, zgodnie z językiem QGIS.
Sprawdzono QGIS 3.40 na Ubuntu. Inne środowiska, zwłaszcza firmowe bazy
i uwierzytelnianie, wymagają sprawdzenia na własnym stanowisku.

## Jak zainstalować

1. Użyj udostępnionej przez autora paczki wydania **`qgis-project-snapshot-1.4.3.zip`**.
   Użyj instalacyjnego ZIP-a wtyczki, nie ZIP-a całego repozytorium.
2. W QGIS wybierz **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
3. Wskaż paczkę i zainstaluj wtyczkę. Przy aktualizacji uruchom ponownie QGIS.

Po zatwierdzeniu publikacji w [katalogu wtyczek QGIS](https://plugins.qgis.org/)
będzie można wyszukać **QGIS Project Snapshot** bezpośrednio w menedżerze wtyczek.
Samo udostępnienie ZIP-a nie oznacza zatwierdzenia w katalogu.

## Jak używać

1. Otwórz projekt i wybierz **Wtyczki → QGIS Project Snapshot → Archiwizuj projekt…**
   lub ikonę mapy w pudełku na pasku wtyczek.
2. Wskaż folder, obszar (widok mapy lub poligony), warstwy i szczegółowość map.
   Najechanie na opcję wyświetla jej opis.
3. Wybierz **Utwórz archiwum** i po zakończeniu przeczytaj raport.
4. Otwórz kopię projektu bez dostępu do źródłowych usług i baz. Sprawdź dane
   i wygląd map. Przenoś **cały folder archiwum**, nie sam plik `.qgz`.

Raport wskazuje braki, puste wyniki i zależności wymagające sprawdzenia.
Nie wszystkie fonty, formularze i wyrażenia da się przenieść automatycznie.
Data archiwum oznacza czas pobierania, nie jednoczesny stan wszystkich źródeł.
Archiwum i raport mogą zawierać dane poufne — sprawdź je przed udostępnieniem.

Do pracy otwieraj **projekt `.qgz`**, a do sprawdzenia wyniku **`raport.html`**.
`dane/` zawiera GeoPackage i pliki przyspieszające jego odczyt,
`zasoby/` potrzebne zasoby, a `diagnostyka/` manifest,
log i ewentualny postęp do wznowienia. Tych plików nie trzeba otwierać ręcznie.
Przenoś cały folder razem; nie usuwaj jego zawartości przed wznowieniem.
Nazwy te dotyczą polskiego interfejsu. W angielskim powstają `report.html`,
`data/`, `resources/` i `diagnostics/`. Wznowienie obsługuje także zmianę języka.

Potwierdzone puste warstwy wektorowe w kopii projektu otrzymują końcówkę
**`_nie-bylo-obiektow-w-zasiegu`**. Nadal zawierają pola i styl, ale zero obiektów.
Oryginalne nazwy pozostają bez zmian; błąd lub niepotwierdzony pusty odczyt MSSQL
nie otrzymuje tej końcówki.
W angielskim interfejsie końcówka to **`_no-features-in-area`**.

## Jak kontynuować archiwum

Po zakończeniu lub anulowaniu pobierania wybierz **Kontynuuj to archiwum**.
Po ponownym uruchomieniu QGIS otwórz oryginalny projekt, wybierz
**Wznów archiwum…** i wskaż cały folder poprzedniego wyniku.

Wtyczka sprawdzi zapisane pliki i utworzy nowy folder. Zachowa ukończone warstwy,
zasoby oraz poprawnie zapisane i puste kafelki map. Pobierze tylko brakujące kafelki,
z nowym limitem do trzech prób na kafelek. Nieukończony wektor zacznie swoją warstwę
od początku. Poprzedni folder pozostaje dostępny.
Starsze zerowe wyniki WFS/MSSQL oraz niepotwierdzone puste odczyty MSSQL są
sprawdzane ponownie; poprawnie pusty wynik nadal jest prawidłowy.

Od 1.4.0 postęp map jest zapisywany na bieżąco. Po nieoczekiwanym zamknięciu QGIS
użyj **Wznów archiwum…** i wskaż folder z nazwą zawierającą `.w-trakcie-`.
Okno podpowiada ostatni zachowany folder; wybór nadal należy do użytkownika.
Puste zoomy wymagają porównania ze źródłem, ale poprawnie puste kafelki nie są
pobierane ponownie.

Potrzebny jest cały folder archiwum i miejsce na jego kopię; sam raport lub JSON
nie wystarczy. Kontynuacja używa poprzedniego obszaru i zoomów. Zmienione źródła,
style lub niezapisane edycje wymagają nowego archiwum. Archiwa sprzed 1.4.0 zachowują ukończone warstwy,
ale nieukończone mapy bez rejestru kafelków pobierają od początku warstwy.
Dla archiwów 1.0.0 wtyczka nie potwierdzi zgodności źródeł i stylów — użyj tego
samego oryginalnego projektu.
Przed planowanym zamknięciem użyj **Przerwij** i poczekaj na zapis. Odzyskiwanie
korzysta z zachowanych danych; nie naprawi plików uszkodzonych przez dysk lub awarię zasilania.

## Szybszy odczyt rastrów

Archiwalne GeoTIFF-y otrzymują piramidy ułatwiające wyświetlanie przy oddaleniu.
Mapy zachowują osobno pobrane poziomy szczegółowości i ich style, także prawidłowo
puste poziomy. Piramidy nie uzupełniają braków obrazem z innej skali.

## Automatyczne pobieranie równoległe

Wtyczka pobiera mapy w osobnych procesach QGIS. Zaczyna od jednego zadania
na serwer i stopniowo zwiększa ich liczbę, uwzględniając wolny RAM, procesor,
szybkość pobierania i odpowiedzi serwera. Przy błędach ogranicza obciążenie
lub robi przerwę. Po okresie poprawnej pracy ponownie sprawdza, czy więcej zadań
przyspieszy pobieranie; utrwalony spadek szybkości może obniżyć limit. W Windows
uwzględnia też dostępny limit przydzielania pamięci. Nie trzeba ręcznie ustawiać
liczby procesów.

Okno pokazuje aktywne zadania i limity. **Warstwy w kolejce** to warstwy czekające
na pobranie z serwera w tym samym wierszu. Automat pomaga przyspieszyć eksport,
ale nie gwarantuje maksymalnej przepustowości. Korzysta z ustawień sieciowych
aktywnego QGIS. Kontynuacja nie zmienia zasad automatycznego obciążania serwerów.

## Diagnostyka długiego pobierania

Wtyczka automatycznie zapisuje w `diagnostyka.jsonl` pomiary CPU,
pamięci, operacji odczytu i zapisu oraz pracy kolejek i serwerów. Pomiary komputera
powstają co około 5 sekund, również podczas oczekiwania na pobranie. Log pozostaje
lokalnie; od 1.4.2 jest w podfolderze **`diagnostyka/`**, razem z `manifest.json`.
Wtyczka nie wysyła tych plików automatycznie.

Do typowej analizy wydajności zwykle wystarczy **`diagnostyka.jsonl`**. Dołącz
`manifest.json`, gdy trzeba wskazać warstwy po nazwie lub sprawdzić szczegóły braków.
HTML i pliki AUX zwykle nie są potrzebne do tej analizy; do wznowienia zachowaj
cały folder. Dłuższy log możesz ręcznie spakować do ZIP-a przed przekazaniem.
Pomiary pomagają znaleźć przyczynę spowolnienia, ale nie dowodzą maksymalnej
wydajności komputera lub serwera.

## Licencje danych i warunki usług

**Przed eksportem sprawdź i respektuj licencję każdej warstwy oraz regulamin
jej dostawcy.** Dotyczy to pobierania, kopiowania, przechowywania offline,
dalszego udostępniania, wymaganych oznaczeń autorstwa i limitów usług.
Możliwość wyświetlenia mapy w QGIS nie oznacza zgody na jej archiwizację.

Na przykład standardowy serwer **`tile.openstreetmap.org` nie zezwala
na pobieranie map do użytku offline**. Użyj źródła, którego warunki wyraźnie
na to pozwalają; zobacz [zasady OSMF](https://operations.osmfoundation.org/policies/tiles/).

Wtyczka nie przyznaje praw do cudzych treści ani nie sprawdza automatycznie
ich licencji. Za wybór danych i zgodne z prawem korzystanie z nich odpowiada
użytkownik. W zakresie dopuszczalnym przez obowiązujące prawo autor nie ponosi
odpowiedzialności za niedozwolone kopiowanie lub udostępnianie treści przez użytkownika.

## Licencja wtyczki i sposób powstania

Autor: **Jarosław Sadowski**. Wtyczka jest bezpłatna i otwartoźródłowa na licencji
**GNU GPL w wersji 2 (GPL-2.0-only)**; warunki i wyłączenie gwarancji zawiera
[LICENSE](LICENSE). Ta licencja dotyczy wtyczki, a nie pobranych danych.

Projekt powstał metodą **vibe coding z pomocą AI**. Przed wykorzystaniem
archiwum sprawdź jego kompletność i działanie bez sieci.

## Pomoc i zgłoszenia

[Szczegółowa instrukcja](docs/team-guide.md) ·
[Zgłoszenia błędów i propozycje](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/issues) ·
[Dokumentacja rozwoju i budowa ZIP-a](docs/development.md)

W zgłoszeniu podaj wersję QGIS i wtyczki oraz kroki odtworzenia problemu.
Nie publikuj haseł, poufnych projektów ani danych firmowych.
