# Odbiór 1.1.0 — kontynuacja po anulowaniu

Data: 12 września 2026. Środowisko: Ubuntu, QGIS 3.40.15, PyQt5,
GDAL 3.12.2, Python 3.14.4. Testy używają tymczasowych projektów i profili QGIS.
Źródła firmowe oraz dane użytkownika nie były pobierane podczas tych testów.

## Zakres

Kontynuacja tworzy nowy folder, kopiuje zweryfikowane dane i zasoby wcześniejszego
archiwum, zachowuje ukończone warstwy i ponawia niezapisane lub częściowe.
Obejmuje zapisany wynik po świadomym anulowaniu i ponownym otwarciu oryginalnego
projektu. Nie zachowuje kafelków warstwy przerwanej w trakcie ani nie odzyskuje
katalogu roboczego po awarii. Starszy folder pozostaje niezmieniony.

Sprawdzane są ID warstw, dostawcy, zakres, CRS, zoomy, sumy plików i odciski
źródeł/stylów od 1.1.0. Starsze archiwa 1.0.0 nie umożliwiają pełnej weryfikacji
ustawień; ten brak pozostaje jawny również przy kolejnej kontynuacji.
Niezapisane edycje blokują kontynuację. Nowy eksport nadal je zachowuje.

Nie zmieniano limitów CPU/RAM, polityki hostów, timeoutów, izolacji procesów,
jakości PNG ani pojedynczego zapisu końcowego GeoPackage. Wersję i instrukcje
PL/EN zaktualizowano. Pakiet nie dodaje zależności.

## Testy źródeł

**140/140, 120,266 s, bez pominięć.** WMS i proxy uruchomione na lokalnych
gniazdach HTTP; nie potraktowano pominiętych testów jako powodzenia.

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Nowe sprawdzenia potwierdzają:

- Zachowanie zapisanych wektorów, atrybutów, stylów, ID, drzewa i załączników,
  również gdy oryginalny załącznik przestał być dostępny.
- Poprawne zero obiektów pozostaje `saved`; ukończona przezroczysta mapa pozostaje
  `empty` i nie jest automatycznie pobierana drugi raz.
- Rzeczywisty WMS w osobnym procesie: jedna mapa ukończona, druga anulowana;
  po wyczyszczeniu projektu i ponownym odczycie QGZ uruchamia się wyłącznie proces
  brakującej mapy. Odcisk WMS pozostaje stabilny po odczycie projektu.
- Nowe okno wznawia archiwum z wybranego folderu, używając obszaru z manifestu.
- Niezgodne źródła, parametry, niezapisane edycje, zmieniony/brakujący GeoPackage
  i ścieżki wychodzące poza archiwum są odrzucane przed pobieraniem.
- Wcześniejszy obraz częściowy zostaje zachowany po błędzie lub ponownym anulowaniu.
  Zmiana poprzedniego GeoPackage podczas kontynuacji blokuje jego przywrócenie.
- Starszy folder i źródłowy projekt pozostają niezmienione bajtowo.

## Jakość kodu

Ruff 0.16.6: `check` i `format --check`. Flake8 7.3.0 / pycodestyle 2.14.0:
kod wtyczki bez naruszeń, limit 88 znaków i E203 zgodnie z konwencją repozytorium.
Flake8 uruchomiono z `--jobs=1`, ponieważ sandbox blokował gniazdo jego puli
procesów; zakres reguł pozostał taki sam. Projekt nie ma osobnego typecheckera.

Przegląd [Ponytail](https://github.com/DietrichGebert/ponytail/blob/main/AGENTS.md):
wykorzystano istniejący zapis projektu, scalanie GeoPackage, obsługę zasobów,
sumy SHA-256 i natywny styl QGIS. Bez nowego modułu konfiguracji, frameworka,
zależności lub przebudowy harmonogramu. Rejestr niedokończonych kafelków wymagałby
większej zmiany; obecny zakres jawnie kończy się na ukończonych warstwach.

Bandit 1.9.4: nadal 11 wcześniej przejrzanych ostrzeżeń (6 medium, 5 low),
bez nowych kategorii względem [1.0.0](validation-1.0.0.md). XML dotyczy
serializacji QGIS i lokalnych zasobów; nazwy tabel SQL są wyprowadzane z ID
i sprawdzane przed ponownym użyciem; proces uruchamia własny moduł bez powłoki.
Nie dodano wyciszeń `nosec` ani nowych zależności tylko w celu wyciszenia skanera.

Skan detect-secrets 1.5.0 wszystkich plików katalogu wtyczki, bez kontaktowania
usług w celu weryfikacji potencjalnych sekretów: zero trafień. Kontrola AST:
34 pliki Python w repozytorium. `git diff --check` bez problemów.

## Gotowa paczka

`dist/qgis-project-snapshot-1.1.0.zip`: **119 873 bajty, 22 pliki**.
SHA-256: `39b16b8afbe4af437b1c452268e59fc08b875ea795302a5e7c34475a700b96bd`.
Ponowna budowa w osobnym katalogu daje identyczne bajty. Kontrola CRC poprawna.

Test instalacji w tymczasowym profilu QGIS potwierdził wykrywanie metadanych,
ładowanie, otwarcie okna i wyłączenie wtyczki. Kod z rozpakowanego ZIP-a:
**140/140 testów, 117,960 s, bez pominięć**; procesy również korzystały z paczki.
Oczekiwane komunikaty GDAL o braku pikseli do statystyk pochodzą z testów
celowo przezroczystych obrazów; ich stan `empty` został sprawdzony.

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -I tests/check_plugin_zip.py dist/qgis-project-snapshot-1.1.0.zip
```

## Granice odbioru

Testy źródeł i paczki na Ubuntu nie zastępują próby na docelowym Windows.
Nie wykonywano firmowych zapytań MSSQL z Ubuntu. Pomyślny pusty odczyt jest
prawidłowym wynikiem, ale log nie rozstrzyga, czy źródło powinno zawierać obiekty.
Archiwum po kontynuacji może zawierać dane pobrane w różnych terminach.

Przygotowanie ZIP-a nie oznacza publikacji ani akceptacji moderatorów QGIS.
Nie wykonywano push, tagowania, zmiany widoczności GitHub ani wysłania do portalu.

Proponowany commit: `Add archive continuation after cancellation`.
