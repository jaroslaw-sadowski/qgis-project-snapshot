# Publikacja poprawki 1.0.2

Krótki opis użytkownika: [README](../README.md). Wyniki kontroli i identyfikacja
ZIP-a: [odbiór 1.0.2](release-1.0.2.md). Wersja 1.0.0 została zablokowana
przez skaner portalu; 1.0.1 przeszła skan z oznaczeniem „configured”.
Poprawka **1.0.2** nie zawiera plików konfiguracji skanerów.

## Wymagania katalogu

Sprawdzono dokumentację i kod portalu 13 września 2026:

- ZIP do 25 MB, poprawne ścieżki, jeden katalog Pythona, __init__.py, metadata.txt,
  LICENSE, wymagane pola, UTF-8, prawidłowa nazwa pakietu i nowy numer wersji.
- Krótki opis EN, instrukcja, działające publiczne homepage/repository/tracker,
  kod odpowiadający paczce, licencja GPL i licencje dołączonych komponentów.
- Bandit, detect-secrets, Flake8, prawa plików i podejrzane pliki. Punktowe
  wyjątki dla przejrzanych zastosowań wyjaśniono w [raporcie](security-scan-fix.md).
- Zgodność QGIS 3.40/Qt5 i QGIS 4/Qt6: metadane 3.40–4.99, bez supportsQt6.
  Kontroler statyczny uzupełnia testy wykonania. Nowe Qt6 na Windows/macOS
  pozostaje do sprawdzenia na tych systemach.
- Po skanie potrzebna jest akceptacja opiekunów. Lokalny odbiór nie jest
  akceptacją plugins.qgis.org.

Źródła: [publikacja](https://plugins.qgis.org/docs/publish/),
[zatwierdzanie](https://plugins.qgis.org/docs/approval/),
[narzędzia skanujące](https://plugins.qgis.org/docs/security-scanning/tools/),
[migracja Qt6](https://plugins.qgis.org/docs/migrate-qgis4/).

Nazwa: **QGIS Project Snapshot**. ID pakietu: **mbtiles_batch_exporter**;
aktualizacja zastępuje wcześniejszą instalację. Kod GPL-2.0-only, dołączony
frontend defusedxml na licencji PSF. Nie ma instalacji pip u użytkownika.
ZIP zawiera tylko źródła, zasoby, metadane, instrukcję i licencje; bez danych
użytkownika, konfiguracji skanerów, historii Git, środowisk testowych oraz instrukcji agentów.
Plik .qm jest katalogiem tłumaczeń Qt z dołączonym źródłem .ts.

## Kroki wydania

1. Zatwierdź sprawdzone źródła i wyślij je do publicznego repozytorium.
2. Utwórz nowy tag **v1.0.2** oraz GitHub Release z
   `dist/qgis-project-snapshot-1.0.2.zip` i `.zip.sha256`. Nie przestawiaj wcześniejszych tagów.
3. Pobierz oba załączniki bez logowania i sprawdź ich zgodność z lokalnymi
   plikami oraz źródłami pod tagiem.
4. W plugins.qgis.org otwórz swoją istniejącą wtyczkę i dodaj **nową wersję**.
   Wyślij powyższy ZIP, a nie automatyczne GitHub „Source code (zip)”.
   Nie wyłączaj reguł skanowania w formularzu.
5. Sprawdź nowy wynik skanowania i poczekaj na akceptację. Ponowne skanowanie
   starego, zablokowanego wpisu 1.0.0 nie zmienia jego statusu.
6. Po akceptacji sprawdź instalację przez Menedżer wtyczek QGIS.

Testerzy rozwojowych 1.4.x: zainstalujcie oficjalny ZIP ręcznie i uruchomcie QGIS
ponownie; niższy numer nie zostanie zaproponowany automatycznie. Zachowajcie całe
archiwa do wznowienia. Kontrola danych offline, stylów, relacji i firmowych usług
pozostaje elementem odbioru na stanowisku użytkownika.
