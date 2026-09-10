# <img src="mbtiles_batch_exporter/icon.svg" width="40" height="40" alt=""> QGIS Project Snapshot

Polski · [English](README.en.md)

Wtyczka QGIS do zachowania danych i wyglądu projektu na potrzeby późniejszego
odczytu bez sieci. Pomaga udokumentować, na jakich mapach i danych oparto analizę,
studium wykonalności lub projekt inwestycji, zanim zmienią się źródłowe usługi i bazy.

Tworzy osobną kopię projektu z grupami, kolejnością, widocznością i stylami warstw.
Wektory z atrybutami oraz obrazy map zapisuje w GeoPackage; rastry źródłowe
i dostępne zasoby projektu kopiuje do plików lokalnych. PNG zachowuje przezroczystość
przy mocnej kompresji bezstratnej. Mapy mogą pozostać w układzie projektu, np. EPSG:2180.

Wtyczka jest bezpłatna i otwartoźródłowa (GNU GPL v2): kod można sprawdzić,
modyfikować i udostępniać na warunkach [licencji](LICENSE).

## Jak używać

Wymaga QGIS 3.40 z PyQt5 oraz GDAL co najmniej 3.7. Interfejs wybiera polski
lub angielski według języka QGIS. Aktualna paczka do lokalnej instalacji: **0.9.7**.

1. Zainstaluj paczkę przez **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Otwórz projekt i wybierz **Wtyczki → QGIS Project Snapshot → Archiwizuj projekt…**
   lub ikonę mapy w pudełku na pasku wtyczek.
3. Wskaż folder, obszar (widok mapy lub poligony), warstwy i szczegółowość map.
   Wybierz **Utwórz archiwum**. Podpowiedzi opcji są dostępne po najechaniu kursorem.
4. Sprawdź raport, a następnie otwórz kopię projektu bez internetu i sieci firmowej.
   Przenoś **cały folder archiwum**, nie sam plik `.qgz`.

Pobieranie korzysta z proxy skonfigurowanego w aktywnym QGIS, jego wyjątków
i dostępnych zapisanych poświadczeń. Nie trzeba wpisywać ich we wtyczce.
Automatycznie dobiera liczbę zadań do CPU, RAM i odpowiedzi każdego serwera.
Po pierwszych pobraniach mierzy pamięć procesów i dobiera dalszą równoległość
z zapasem na rozruch oraz wzrost zużycia, pozostawiając 768 MiB wolnego RAM.
Zaczyna od jednego zadania na serwer i stopniowo zwiększa obciążenie, jeśli
przyspiesza to pobieranie i pozwalają zasoby komputera. Preferuje równoczesną pracę
różnych serwerów. Okno pokazuje aktywne zadania, limity, przerwy i dziennik;
„Warstwy w kolejce” to warstwy czekające na pobranie z serwera w danym wierszu.
Podczas eksportu uzupełnia tylko brakujące kafelki w tym samym archiwum.
Ręczne ponowienie z końcowego ekranu tworzy nowe archiwum wybranych warstw.

[Instrukcja dla zespołu](docs/team-guide.md) opisuje opcje, wyniki i odbiór archiwum.
Jest również dołączona do ZIP-a.

## Dane i ograniczenia

Wtyczka łączy się z bazami i usługami wskazanymi w projekcie, aby pobrać dane.
Nie zastępuje projektu źródłowego. Korzysta z bibliotek dostarczanych z QGIS
oraz standardowego Pythona; nie wymaga dodatkowych instalacji.
Archiwum i raport mogą zawierać dane firmowe oraz nazwy warstw.

Data archiwum oznacza czas pobierania, a nie jednoczesny stan wszystkich źródeł.
Obrazy map zachowują wybrany obszar i poziomy szczegółowości. Brakujące warstwy,
puste obrazy oraz zależności wymagające sprawdzenia są opisane w raporcie.
Fonty, kod formularzy i wszystkie zależności wyrażeń nie są automatycznie pakowane.
Nie ma wznawiania po zamknięciu QGIS. Warunki korzystania ze źródeł nadal obowiązują,
w tym ograniczenia masowego pobierania standardowych kafelków OSM.

Projekt powstaje metodą vibe coding z pomocą AI. Przed wykorzystaniem archiwum
sprawdź jego kompletność, wygląd i odczyt bez sieci. Warunki udostępniania
oprogramowania i brak gwarancji opisuje [licencja](LICENSE).

## Wykonane kontrole

- 128 testów QGIS w wersji 0.9.7: zapis i odczyt danych, mapy, raport, PL/EN, anulowanie,
  ograniczenia serwerów i uzupełnianie braków.
- Test instalacyjnego ZIP-a: natywne wykrywanie i ładowanie w QGIS, okno archiwizacji,
  wyłączenie wtyczki oraz uruchomienie testów na kodzie z paczki.
- Ruff: reguły PEP 8/pycodestyle (E/W), Pyflakes (F), importy (I) i formatowanie
  według konfiguracji projektu (88 znaków).
- Kontrola składni, integralności ZIP-a i zgodności jego zawartości ze źródłami.

Środowisko testowe: Ubuntu, QGIS 3.40.15. Windows, MSSQL i kompletny projekt
firmowy wymagają odbioru na stanowisku użytkownika. To kontrole lokalne,
nie certyfikat QGIS ani gwarancja poprawności dowolnego projektu.
[Odbiór 0.9.7](docs/validation-0.9.7.md) · [Raporty i dokumentacja](docs/README.md).

## Paczka i rozwój

Repozytorium zawiera źródła. Aby przygotować ZIP **0.9.7**, uruchom:

```bash
python3 scripts/build_plugin.py
```

Paczka `qgis-project-snapshot-0.9.7.zip` i suma SHA-256 powstaną w `dist/`.
Ten katalog nie jest przechowywany w Git. Samo przygotowanie ZIP-a nie oznacza
publikacji w katalogu wtyczek QGIS.

[Budowa i testy](docs/development.md) · [Architektura](docs/architecture.md) ·
[Stan dla kolejnych sesji](docs/PROJECT_STATE.md) · [Instrukcje agentów](AGENTS.md)

Autor: Jarosław Sadowski · Licencja: GNU GPL v2 ·
[Zgłoszenia](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/issues)
