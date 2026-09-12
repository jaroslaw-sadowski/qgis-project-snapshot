# Odbiór 1.2.0 — diagnostyka wydajności

12 września 2026. Ubuntu, QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4.
Próby używają izolowanych profili, tymczasowych danych i lokalnych serwerów HTTP.
Nie pobierano ponownie danych użytkownika ani źródeł firmowych.

## Wynik funkcjonalny

Nowa diagnostyka zapisuje pomiary CPU, pamięci, I/O, etapów archiwizacji,
przydziału procesów i odpowiedzi usług. Powstaje lokalny `diagnostic.jsonl`;
nie ma automatycznej wysyłki ani dodatkowych żądań testujących przepustowość.
Nie zmieniono algorytmu obciążenia, timeoutów, retry, kontynuacji ani jakości PNG.

- `performance_sample`: próbki co 5 s oraz na starcie/końcu, również podczas
  blokującego odczytu w głównym QGIS. Osobny wątek dotyka tylko natywnych liczników.
- `performance_phase`: czas ścienny i własny CPU etapów, m.in. wektorów, map,
  scalania, zasobów, kontroli integralności i sum plików.
- `scheduler_sample`: budżet CPU/RAM, rezerwa i zapas wzrostu, stan zadań,
  wiek telemetrii, limity/przerwy/zamrożenie i historia ostatniej decyzji hosta.
- `network_interval` i podsumowania: liczby żądań, błędy/timeouty, opóźnienia,
  histogram, dostępne bajty odpowiedzi, oddzielne deklaracje Content-Length
  oraz bajty cache/bez cache/nieznanego pochodzenia.
- `archive_plan` i `layer_summary`: wybrany zakres i końcowe wyniki warstw według
  technicznych identyfikatorów, bez nazw warstw, źródeł i współrzędnych.

Do typowej analizy wydajności wystarczy końcowy log z 1.2.0. Nazwy warstw i pełne
szczegóły archiwum pozostają w manifeście; do kontroli danych i kontynuacji nadal
potrzebny jest cały folder. Żaden skończony zestaw liczników nie gwarantuje diagnozy
wszystkich przyszłych problemów.

## Weryfikacja

Dodano 25 testów względem 1.1.0, w tym:

- Rzeczywisty przyrost CPU i I/O na Linux; niezależne błędy czujników.
- Atrapy natywnych Windows API z kontrolą struktur ctypes i liczników 64-bitowych.
- Znane przyrosty CPU, pierwszy odczyt bez procentu, brak CPU bez utraty RSS/I/O,
  odmowa uruchomienia wątku, błąd odczytu i zamknięcie po wyjątku/anulowaniu.
- Działanie pomiarów podczas oczekiwania bez przetwarzania zdarzeń Qt/postępu.
- Stan 9/9 procesów, 7 aktywnych i 2 oczekujących z budżetem i zapasem RAM.
- Rzeczywisty eksport WMS w procesie oraz świadome anulowanie: log zawiera dane
  głównego QGIS i workerów, fazy, kolejkę, wyniki oraz końcowe podsumowania.
- Natywna odpowiedź HTTP QGIS, rozróżnienie pustego i niedostępnego body,
  cache i deklaracji rozmiaru, sumy czasu oraz ograniczenie pamięci grup.
- Nowe pomiary nie zapisują ścieżek, treści wyjątków, URL z poświadczeniami
  ani zawartości odpowiedzi.

Pierwszy pełny przebieg źródeł wykonał 165 testów w 140,967 s: 164 przeszły,
jeden test miał skończoną listę trzech odczytów zegara. Nowy znacznik czasu
telemetrii zużywał dodatkowy odczyt. Poprawiono zegar testu tak, aby upływ czasu
zależał od oczekiwania, a nie liczby odczytów; zachowano sprawdzenie bezpiecznego
zatrzymania po wygaśnięciu pozwolenia. Następnie wszystkie 15 testów tej polityki
przeszło w 0,109 s. Produkcyjna reguła wygaśnięcia nie została zmieniona.

Ruff 0.16.6, `check` i `format --check` — poprawne. Flake8 7.3.0 / pycodestyle
2.14.0 — poprawne z konwencją repozytorium: 88 znaków i E203 dla formatowania
wycinków. Flake8 wykonano z `--jobs=1`, bez zmiany reguł. Brak osobnego typecheckera.

Bandit 1.9.4 nadal wskazuje 11 przejrzanych ostrzeżeń: 6 medium, 5 low,
te same kategorie co [1.1.0](validation-1.1.0.md). Nie dodano wyciszeń `nosec`.
Skan detect-secrets 1.5.0 wszystkich plików wtyczki, bez internetowej weryfikacji
potencjalnych sekretów: zero trafień. Kontrola AST 36 plików Python — poprawna.
`git diff --check` bez problemów.

## Paczka i pełne testy końcowe

`dist/qgis-project-snapshot-1.2.0.zip`: **127 452 bajty, 22 pliki**.
SHA-256: `e36533b016d0efad0599085a0dc92fb56f239bb8df5c688d2b753cacd35a691a`.
Ponowna budowa w osobnym katalogu daje identyczne bajty; CRC poprawne.
Sprawdzono zgodność pakowanych modułów i zasobów z plikami źródłowymi.

W tymczasowym profilu QGIS sprawdzono metadane, ładowanie, okno i wyłączenie
wtyczki. Następnie **165/165 testów kodu z paczki przeszło w 120,443 s,
bez pominięć**. Osobne procesy map również korzystały z kodu z paczki.
WMS/proxy działały na lokalnych gniazdach; pominięcie z powodu blokady sieci
nie zostało potraktowane jako pozytywny wynik. Znane komunikaty GDAL o braku
pikseli do statystyk pochodzą z testów celowo przezroczystych map.

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -I tests/check_plugin_zip.py dist/qgis-project-snapshot-1.2.0.zip
```

## Prostota i granice pomiarów

Przegląd zgodny z [Ponytail](https://github.com/DietrichGebert/ponytail/blob/main/AGENTS.md):
rozszerzono istniejącą diagnostykę, obsługę zasobów i zdarzenia QGIS. Wykorzystano
standardową bibliotekę i natywne liczniki OS. Nie dodano zależności, konfiguratora,
zewnętrznego profilera ani automatycznej regulacji opartej na nowych pomiarach.

Próba 200 natywnych odczytów na Linux: mediana 0,178 ms dla workera i 0,323 ms
dla pełnej próbki systemowej. To koszt pojedynczego odczytu, bez zapisu JSON
i bez pomiaru narzutu całego eksportu; nie jest wynikiem Windows ani gwarancją.
Log będzie większy niż wcześniej; można ręcznie skompresować go do ZIP-a.

Procesowy CPU 100% oznacza jeden logiczny CPU. Windows I/O obejmuje wszystkie
transfery procesu, a Linux może doliczać I/O odebranych potomków. Dostępne bajty
odpowiedzi QGIS nie mierzą ruchu na całej karcie ani przepustowości Internetu.
Brak dostępnego licznika oznaczony jest null. Pomiary nie obejmują temperatur,
częstotliwości CPU ani procentowej zajętości fizycznego dysku.

Szczegółowe definicje i źródła Windows API są w [architecture.md](architecture.md).
Testy atrap Windows nie zastępują natywnego przebiegu na Windows 11.
Sam ZIP nie oznacza publikacji ani akceptacji przez moderatorów QGIS.

Proponowany commit: `Add native performance and scheduler diagnostics`.
