# Rozwój, testy i przygotowanie paczki

Polecenia wykonuj z katalogu głównego repozytorium. Użyj interpretera z modułami
`qgis` i `osgeo` dostarczonymi z QGIS; zwykłe środowisko Pythona może ich nie mieć.
Zweryfikowano Ubuntu, QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4.

## Testy źródeł

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Testy używają rzeczywistych dostawców QGIS/GDAL i katalogów tymczasowych.
Lokalny WMS wymaga gniazd HTTP na `127.0.0.1`. Przy blokadzie sieci testy WMS
są pomijane; taki wynik nie jest pełnym odbiorem. W środowisku Codexa może być
konieczne uruchomienie polecenia z uprawnieniem do sieci lokalnej.

Brak osobnej konfiguracji lint i typecheck. Dla zmian wykonaj również
`git diff --check` i kontrolę składni Pythona. Nie uruchamiaj wielokrotnie pełnego
zestawu bez nowych zmian, błędów lub istotnego powodu do ponownej weryfikacji.

## Budowa ZIP-a

```bash
python3 scripts/build_plugin.py
```

Skrypt korzysta tylko ze standardowej biblioteki Pythona. Wersję odczytuje
z `mbtiles_batch_exporter/metadata.txt`; generuje ZIP i `.zip.sha256` w `dist/`.
Można podać inny katalog przez `--output`. ZIP ma jeden katalog wtyczki,
zawiera moduły Python, ikonę, metadane, README, GPL i instrukcję zespołową.
Nie zawiera repozytorium, testów, danych projektów ani plików dla agentów AI.

Przy tych samych źródłach i środowisku ZIP jest powtarzalny bajt po bajcie.
Zmiana instrukcji zespołowej też zmienia zawartość paczki i jej SHA-256.

## Test gotowej paczki

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -I tests/check_plugin_zip.py dist/qgis-project-snapshot-0.7.2.zip
```

Skrypt rozpakowuje ZIP do tymczasowego profilu QGIS. Sprawdza natywne wykrywanie,
ładowanie, oba okna i wyłączenie wtyczki z minimalnym interfejsem testowym,
a następnie uruchamia pełne testy z kodu paczki. Weryfikuje ścieżki załadowanych
modułów, także kod używany przez procesy pomocnicze. Pominięte testy oznaczają
błąd odbioru. Profil użytkownika nie jest zmieniany. Test nie publikuje paczki.

Przy zmianie wersji zaktualizuj powyższą nazwę w poleceniu, odnośniki w README
i instrukcję. Raporty historyczne zachowują numery i sumy kontrolne poprzednich prób.

## Opcjonalny benchmark

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 tests/benchmark_archive.py --output /tmp/benchmark.json
```

Wymaga Linuksa (`/proc`) i lokalnych gniazd HTTP. Porównuje 1/2/4 procesy,
czas, sumę RSS, pliki tymczasowe oraz identyczność PNG. Korzysta z dwóch
kontrolowanych WMS i po próbie usuwa wygenerowane archiwa. Uruchamiaj go bez
innych obciążających zadań. Szczegóły i ograniczenia pomiarów opisuje
[raport kroku 4](validation-step4.md).

## Przygotowanie kolejnego wydania

Po zmianach kodu wykonaj odpowiednie testy, zbuduj paczkę i sprawdź jej instalację.
Po zmianach wyłącznie w dokumentacji poza paczką wystarczy kontrola odnośników,
diff i zgodności ZIP-a ze sprawdzoną sumą; identycznego kodu nie trzeba testować od nowa.
Uaktualnij [stan projektu](PROJECT_STATE.md). Testy firmowe prowadź według
[instrukcji zespołowej](team-guide.md), bez dodawania danych i poświadczeń do Git.

## Nazwa i zgodność instalacji

Widoczna nazwa oraz prefiks ZIP-a to `qgis-project-snapshot`. Techniczny katalog
Pythona/identyfikator QGIS pozostaje `mbtiles_batch_exporter`, aby aktualizacja
zastępowała poprzednią instalację. Nie zmieniaj go razem z etykietami interfejsu
bez osobnego planu migracji. Menu tworzy natywne `iface.addPluginToMenu`.

## Tłumaczenia

Po zmianie tekstów zaktualizuj `mbtiles_batch_exporter/en.ts`, następnie skompiluj:

```bash
lrelease mbtiles_batch_exporter/en.ts -qm mbtiles_batch_exporter/en.qm
```

To narzędzie Qt używane tylko podczas rozwoju. Użytkownik dostaje gotowy katalog.
Testy sprawdzają zgodność katalogu z wywołaniami `tr`, parametry szablonów i oba języki.
Testy zachowania domyślnie ustawiają polski, niezależnie od lokalnego profilu QGIS.
