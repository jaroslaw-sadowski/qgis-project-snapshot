# Rozszerzona diagnostyka 0.9.3 — 10 września 2026

Wersja obejmuje poprawkę blokad IPC 0.9.2 oraz pasywną obserwację sieci,
liczniki odczytu wektorów, etapy zapisu i korelację warstw/procesów.

Nowe testy sprawdzają wykrycie błędu OGC przy HTTP 200, liczniki WFS bez danych
obiektów, brak mylenia nieudostępnionego body z zerem obiektów, trzy próbki
odpowiedzi i kompletne sumy oraz brak haseł/loginów/ścieżek/tokenów w logu.
Rozszerzone istniejące testy sprawdzają czasy rzeczywistych odpowiedzi proxy
oraz liczniki zapisu wektorów. Mock odczytu w teście anulowania dostosowano do
opcjonalnego parametru diagnostic. Odpowiedzi rozpoczęte przed obserwatorem
pozostają bez kontekstu; nie dorabiamy im przypisania do bieżącej warstwy.

- Pełny zestaw źródeł: **84/84**, 66,023 s, bez pominięć, Ubuntu/QGIS 3.40.
- Ruff check, Ruff format --check i git diff --check: poprawne.
- Odbiór ZIP: wykrycie, ładowanie, okno i wyłączenie poprawne; **84/84 testów**
  z kodu paczki, 69,539 s, bez pominięć.
- ZIP: `dist/qgis-project-snapshot-0.9.3.zip`.
- SHA-256: `c188104c96101b4e4f55b92398e18e4d36fb9e6923604d7e326133c98b9e2332`.

Nie jest to odbiór na firmowym Windows ani test firmowego WFS. Obserwator nie
potwierdza trasy każdego żądania przez proxy. XML sprawdza tylko wtedy, gdy QGIS
udostępnia body; prefiks ograniczono do 16 KiB. Nie analizuje treści POST, JSON
FeatureCollection, surowych błędów dostawców ani lokalnych zmiennych wyjątków.
Kontekst głównego QGIS wskazuje aktywną warstwę podczas startu żądania,
a nie gwarantowane pochodzenie każdego żądania innych zadań.
