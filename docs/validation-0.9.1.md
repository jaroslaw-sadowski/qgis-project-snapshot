# Weryfikacja diagnostyki 0.9.1 — 10 września 2026

Dodano trwały log diagnostyczny, zbieranie logów procesów przed ich usunięciem,
wyjątki koordynatora, kody błędów sieci oraz bezpieczne podsumowanie proxy.
Nie zmieniano algorytmu pobierania ani nie deklarowano naprawy błędu Windows.

- Pełne testy źródeł na Ubuntu/QGIS 3.40: **73/73**, 59,999 s, bez pominięć.
- Testy obejmują rzeczywisty lokalny WMS i proxy HTTP Basic, błąd 407,
  wyłączone proxy i wyjątki proxy. Log archiwum jest sprawdzany pod kątem
  obecności zdarzenia uwierzytelnienia i braku testowego loginu/hasła.
- Nowe kontrole: zachowanie diagnostyki po awarii, miejsca wyjątków i errno
  bez wiadomości/ścieżek użytkownika, brak wpływu błędu zapisu logu na sprzątanie,
  podsumowanie konfiguracji bez poświadczeń. Integracja sprawdza log końcowy
  i zdarzenia odczytu wektorów.
- Ruff check, Ruff format --check i git diff --check: poprawne.
- Odbiór ZIP: wykrywanie, ładowanie, okno i wyłączenie wtyczki poprawne;
  **73/73 testy z kodu paczki**, 58,796 s, bez pominięć.
- Build: `dist/qgis-project-snapshot-0.9.1.zip`.
- SHA-256: `e8c6c8ddfe6e6b83a27d4b57023587c0123f6cfe7de78307dc43896df4d9717d`.

Wstępna próba w piaskownicy pomijała testy sieciowe; wynik powyżej pochodzi
z pełnej próby z dostępem do lokalnych gniazd. Brak odbioru Windows i sieci
firmowej. Log nie przechwytuje surowego stderr dostawców ani nie potwierdza
rzeczywistej trasy każdego połączenia. Przy błędzie zapisu dysku diagnostyka
może być niepełna. Przy natywnym zakończeniu procesu bez wyjątku Pythona
pozostaje kod wyjścia i ostatnie zapisane zdarzenia.
