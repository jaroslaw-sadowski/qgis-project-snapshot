# qgis-project-snapshot — instrukcja 0.8.1

## Instalacja i uruchomienie

1. QGIS: **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Wskaż `qgis-project-snapshot-0.8.1.zip`. Po aktualizacji uruchom ponownie QGIS.
3. Otwórz **Wtyczki → qgis-project-snapshot → Archiwizuj projekt…**.

Wymagane: QGIS 3.40, PyQt5 i GDAL 3.7 lub nowszy. Sprawdzono Ubuntu;
Windows i źródła firmowe wymagają próby na stanowisku służbowym.
Interfejs wybiera polski dla języka QGIS `pl`, angielski dla wszystkich `en`.
Bez własnego języka QGIS używa języka systemu; pozostałe języki mają wersję angielską.

## Zapis archiwum

1. Otwórz projekt z dostępem do danych, np. w sieci firmowej dla MSSQL.
2. Wybierz folder, obszar i warstwy. Dla pasa inwestycji użyj poligonów.
3. Na początek zostaw zoomy 13–17 i mały obszar testowy.
4. Kliknij **Utwórz archiwum**. Objaśnienia opcji znajdziesz po najechaniu kursorem.

Oryginalny projekt nie jest zastępowany. PNG zachowują przezroczystość i kompresję
bezstratną. Wektory zachowują obiekty i atrybuty; zastąpienie obrazem jest opisane
w raporcie. Daty raportu oznaczają czasy pobierania, nie wspólną chwilę wszystkich źródeł.

## Automatyczna równoległość

Nie trzeba ustawiać liczby procesów ani zapytań. Tabela pokazuje dla każdego hosta:
**aktywne zadania / limit**, kolejkę, skuteczne kafelki/s, stan i pozostałą przerwę.
Nad nią widać wykorzystanie procesów map. Limity dotyczą zadań mapowych, nie dokładnej
liczby żądań HTTP na sekundę — dostawca QGIS może wysyłać kilka żądań dla jednego zadania.

Automat zaczyna od 1 zadania na host. Po co najmniej 15 sekundach i 10 poprawnych
kafelkach może dodać jedno zadanie, jeśli są następne mapy do pobrania. Sprawdza,
czy zwiększanie faktycznie poprawia szybkość. Po błędzie przeciążenia albo dwóch
oknach bez poprawy wraca o krok i nie zwiększa już obciążenia w tym eksporcie.
Dalsze problemy mogą je jeszcze zmniejszyć. CPU i dostępny RAM ograniczają
łączną liczbę procesów; nieznany RAM oznacza ostrożny limit.

To heurystyka, nie gwarancja najszybszego ustawienia. Krótki eksport może skończyć
się przed zwiększeniem równoległości. Pojedyncza mapa nadal jest obsługiwana przez
jeden proces. Wektory, rastry źródłowe i niezapisane edycje pozostają w głównym QGIS.

## Czerwone ostrzeżenie i uzupełnianie

HTTP 429 oznacza zbyt wiele zapytań. HTTP 503 oznacza niedostępność lub możliwe
przeciążenie; nie dowodzi, że przyczyną jest nasz ruch. Automat wstrzymuje nowe
pobrania tego hosta i respektuje `Retry-After`. Inne hosty mogą pracować dalej.
Bez terminu od serwera stosuje przerwy 30/60/120 sekund. Pierwsza próba po przerwie
dotyczy brakującego kafelka; dopiero sukces pozwala wznowić pozostałe zadania.

Poprawne kafelki, również przezroczyste, nie są pobierane ponownie. Automat uzupełnia
braki **w tym samym archiwum**, najwyżej dwukrotnie po pierwszym pobraniu kafelka.
Gdy limit prób się wyczerpie albo serwer wymaga czekania ponad 5 minut, pozostawia
wynik niepełny i zapisuje powód. Błędów dostępu 401/403/404 nie ponawia automatycznie.

**Przerwij** działa również podczas oczekiwania. Zachowuje ukończone, scalone mapy;
nieukończone prywatne pliki są usuwane. W razie problemu możesz przerwać i sprawdzić
raport. Automat nie wznawia pracy po zamknięciu QGIS i nie pamięta limitów między eksportami.

## Wynik i odbiór offline

Po zakończeniu przewijana lista pokazuje problematyczne warstwy. Raport HTML oraz
`manifest.json` zawierają przyczyny, uzupełnianie i historię limitów hostów.
Przycisk ponowienia **po zakończeniu** eksportu tworzy osobny folder wyłącznie
z zaznaczonymi warstwami. Zachowaj oba foldery; ten przycisk nie łączy wyników.

Przenieś **cały folder archiwum**, odłącz internet i sieć firmową, otwórz kopię `.qgz`.
Sprawdź mapę, atrybuty, załączniki, formularze i wydruki. Archiwum nadal wymaga
odbioru: poprawne lokalne ścieżki nie potwierdzają wszystkich zależności projektu.
Do odczytu kopii ta wtyczka nie jest potrzebna.

Szacunek przy kafelkach dotyczy jednej mapy i wszystkich wybranych zoomów.
Model zakłada 0,2–2 s oraz 10–250 KiB PNG na kafelek; to nie pomiar serwera ani
prognoza całego projektu. Nie uwzględnia zasobów, wektorów, rastrów źródłowych,
scalania, kontroli i miejsca tymczasowego. Szczegóły są w podpowiedzi.

Automatyka nie zmienia zasad dostawcy. Standardowe `tile.openstreetmap.org`
nie dopuszcza masowego pobierania obszarów offline; wybierz źródło dopuszczające
archiwizację albo własny serwer.

## English quick start

Open **Plugins → qgis-project-snapshot → Archive project…**. Choose the folder,
area, layers and zooms, then **Create archive**. Concurrency is automatic. The
server table shows active tasks/limit, queue, successful tiles/s, state and cooldown.

Each host starts at one map task. After successful windows, concurrency may grow.
Errors or no speed gain reduce the limit and stop further growth for this export.
CPU/RAM constrain processes. This controls map tasks, not exact HTTP requests/sec.

HTTP 429/503 triggers a host cooldown. Other hosts continue. Retry-After is respected;
otherwise backoff is 30/60/120 seconds. Only missing tiles are repaired in the same
archive, with at most two additional attempts. Successful and transparent tiles are
not fetched again. Long waits, exhausted retries and permanent access errors are
reported as incomplete results. Cancel remains available while waiting.

After export, check the report and open the archived project offline. Move the entire
folder. The final Retry button creates a separate archive of selected layers; keep
both folders. There is no restart/resume after closing QGIS. Service usage policies
still apply. Hover over controls for details.
