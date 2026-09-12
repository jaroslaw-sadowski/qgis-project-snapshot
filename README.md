# <img src="mbtiles_batch_exporter/icon.svg" width="40" height="40" alt=""> QGIS Project Snapshot

Polski · [English](README.en.md) · Wersja **1.1.0**

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

1. Użyj udostępnionej przez autora paczki wydania **`qgis-project-snapshot-1.1.0.zip`**.
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

## Jak kontynuować archiwum

Po zakończeniu lub anulowaniu pobierania wybierz **Kontynuuj to archiwum**.
Po ponownym uruchomieniu QGIS otwórz oryginalny projekt, wybierz
**Wznów archiwum…** i wskaż cały folder poprzedniego wyniku.

Wtyczka sprawdzi zapisane pliki i utworzy nowy folder: skopiuje ukończone warstwy
oraz zasoby i ponowi brakujące lub częściowe warstwy. Puste zoomy nadal wymagają
sprawdzenia, ale nie są automatycznie pobierane ponownie. Nieukończona warstwa
zaczyna od początku; jeśli ponowienie nie zakończy się poprawnie, wcześniejszy
obraz częściowy pozostaje w wyniku. Poprzedni folder pozostaje bez zmian.

Potrzebny jest cały folder archiwum i miejsce na jego kopię; sam raport lub JSON
nie wystarczy. Kontynuacja używa poprzedniego obszaru i zoomów. Zmienione źródła,
style lub niezapisane edycje wymagają nowego archiwum. Dla archiwów 1.0.0 wtyczka
nie potwierdzi zgodności źródeł i stylów — użyj tego samego oryginalnego projektu.
Wznawianie wymaga zapisanego wyniku; nie odzyskuje eksportu po awarii lub utracie zasilania.

## Automatyczne pobieranie równoległe

Wtyczka pobiera mapy w osobnych procesach QGIS. Zaczyna od jednego zadania
na serwer i stopniowo zwiększa ich liczbę, uwzględniając wolny RAM, procesor,
szybkość pobierania i odpowiedzi serwera. Przy błędach ogranicza obciążenie
lub robi przerwę. Nie trzeba ręcznie ustawiać liczby procesów.

Okno pokazuje aktywne zadania i limity. **Warstwy w kolejce** to warstwy czekające
na pobranie z serwera w tym samym wierszu. Automat pomaga przyspieszyć eksport,
ale nie gwarantuje maksymalnej przepustowości. Korzysta z ustawień sieciowych
aktywnego QGIS. Kontynuacja nie zmienia zasad automatycznego obciążania serwerów.

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
