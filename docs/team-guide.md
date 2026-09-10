# qgis-project-snapshot — instrukcja 0.9.5

## Instalacja i uruchomienie

1. QGIS: **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Wskaż `qgis-project-snapshot-0.9.5.zip`. Po aktualizacji uruchom ponownie QGIS.
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
kafelkach może zwiększyć limit do 2, jeśli są następne mapy do pobrania. Sprawdza,
czy zwiększanie faktycznie poprawia szybkość. Po błędzie przeciążenia albo dwóch
oknach bez poprawy wraca o krok i nie zwiększa już obciążenia w tym eksporcie.
Dalsze problemy mogą je jeszcze zmniejszyć. CPU i dostępny RAM ograniczają
łączną liczbę procesów; nieznany RAM oznacza ostrożny limit. Pierwszeństwo mają
serwery z mniejszą liczbą aktywnych procesów: wolny proces obsłuży najpierw
oczekujący serwer bez pobierania, zanim uruchomi drugą mapę zajętego serwera.

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

Each host starts at one map task. After successful windows, it may grow to two.
Servers with fewer active processes get priority; multiple servers can run together.
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

## Proxy i błędy połączenia (0.9.1)

Nie wpisujesz proxy we wtyczce. Korzystamy z ustawień sieci aktywnego QGIS,
w tym wyjątków i dostępnych zapisanych poświadczeń. Gdy proxy jest wyłączone,
procesy nie włączają własnego proxy. Nie zmieniaj firmowej konfiguracji tylko
na potrzeby archiwizacji.

HTTP 407 oznacza odrzucenie uwierzytelnienia proxy. Inne komunikaty odróżniają
problem połączenia z proxy, weryfikacji TLS i uruchomienia procesu QGIS. Raport
zawiera etap i kody błędów, bez haseł oraz pełnych adresów usług. Nietypowe
logowanie firmowe lub certyfikaty mogą wymagać odbioru na danym stanowisku.

Przy starcie dziennik pokazuje wykryte CPU, dostępny RAM i wybrany limit procesów.
„Rezerwa RAM: 2 GiB” oznacza założony zapas dla głównego QGIS i systemu, nie limit
pamięci całej archiwizacji. Host bez dalszych zadań pokazuje zakończenie lub błędy.
Dawny osobny eksporter MBTiles usunięto; w menu i na pasku jest jedna akcja.

English: the plugin uses the active QGIS proxy configuration and exclusions.
Available saved proxy credentials are transferred in memory, not written into
the archive. HTTP 407 identifies rejected proxy authentication. TLS verification
remains enabled. The startup log shows detected CPU/RAM and the process budget.
The legacy standalone MBTiles exporter has been removed.

## Plik diagnostyczny dla developera (0.9.1)

Każdy rozpoczęty eksport zapisuje `diagnostic.jsonl` obok `raport.html` i
`manifest.json`, również przy wyniku częściowym lub anulowaniu. Jeżeli eksport
zakończy się wyjątkiem przed utworzeniem archiwum, log pozostaje w wybranym
folderze zapisu jako `<nazwa_archiwum>.diagnostic.jsonl`. Błędy walidacji opcji
przed rozpoczęciem eksportu nie tworzą pliku. Brak miejsca lub uprawnień do zapisu
może uniemożliwić zapis diagnostyki.

Do analizy problemu przekaż wszystkie trzy pliki oraz log z okna. Diagnostyka
zawiera czas, wersje środowiska, zasoby, wyniki warstw, zdarzenia procesów,
kody HTTP/Qt i miejsca wyjątków w kodzie. Nie zawiera haseł, loginów, pełnych
adresów usług, treści wyjątków dostawców ani wartości atrybutów obiektów.
Konfiguracja proxy i zaobserwowane żądanie uwierzytelnienia są rozróżniane;
brak żądania uwierzytelnienia nie oznacza, że proxy nie było używane.
Wynik pusty jest oznaczany w diagnostyce, ale nie dowodzi poprawności źródła.

## Próba poprawki Windows 0.9.5

1. Zainstaluj ZIP 0.9.5 przez „Wtyczki → Zarządzanie i instalowanie wtyczek →
   Instaluj z ZIP”, zamknij cały QGIS i uruchom go ponownie. Sprawdź wersję
   w menedżerze wtyczek. Zachowaj firmowe ustawienia proxy.
2. Użyj tego samego komputera. W projekcie źródłowym wybierz mały obszar,
   na którym widać treść 3–5 publicznych WMS/WMTS. Nie wybieraj standardowych
   kafelków OSM do tej próby. Ustaw zoom 16–17 i „Bieżący widok mapy”.
3. Dodaj jeden WFS, na którym w tym obszarze widać konkretne obiekty.
   Zanotuj jego nazwę i przybliżoną liczbę widocznych obiektów. W archiwizacji
   zaznacz tylko te warstwy. Zapisz do nowego lokalnego folderu, poza OneDrive
   i dyskiem sieciowym. Nie kasuj poprzednich wyników.
4. Po zakończeniu zachowaj `diagnostic.jsonl`, `manifest.json` i `raport.html`.
   Zamknij projekt źródłowy i QGIS. Odłącz sieć, uruchom QGIS i otwórz plik
   `_archive_...qgz` z nowego folderu. Sprawdź treść map i obiekty WFS w tym
   samym obszarze i przy skalach odpowiadających zapisanym zoomom. Zrzut ekranu
   wyniku może pomóc, ale same pliki diagnostyczne nie dowodzą zgodności obrazu.
5. Przekaż te trzy pliki oraz informację, które warstwy widać offline,
   które są puste i czy działało „Przerwij”. Na razie nie potrzeba drugiego
   komputera, konkretnego adresu proxy ani wyłączania zabezpieczeń.

Dopiero po poprawnym małym teście zwiększ liczbę warstw i zoom do 20.
Jeśli ponownie wystąpi błąd, najpierw przekaż log z tej wersji. Diagnostyka
rozróżnia `ipc_replace_retry`, `ipc_replace_recovered` i `ipc_replace_failed`.
Wersja 0.9.5 zawiera poprawkę blokad plików sterujących i powrotu serwera po
przerwie. Nie potwierdza jeszcze poprawnego odczytu wszystkich firmowych WFS
ani przyczyny ich wcześniejszych pustych wyników.

## Rozszerzona diagnostyka 0.9.3

Użyj wersji 0.9.5 do opisanej wyżej próby — zawiera także poprawkę blokad Windows.
`diagnostic.jsonl` dodatkowo podaje:

- powiązanie numeru wybranej warstwy z technicznym identyfikatorem procesu;
- etapy odczytu wektorów, CRS, obecność filtra i edycji, liczbę odebranych,
  zapisanych i pominiętych obiektów oraz stan iteratora i zapisu GeoPackage;
- host, rozpoznany rodzaj zapytania, CRS żądania, kod HTTP/Qt, czas, typ odpowiedzi
  i informację o pamięci podręcznej; trzy przykłady i sumy powtarzających się odpowiedzi;
- rozpoznane błędy OGC w XML, także przy HTTP 200, oraz liczniki WFS z początku
  odpowiedzi XML, jeśli QGIS udostępnia jej treść;
- wersję QGIS/Pythona procesu, ograniczenia widoczności warstwy według skali,
  liczniki pustych i niepustych kafelków oraz wolne miejsce przed eksportem.

To obserwacja zwykłego eksportu, bez dodatkowych zapytań testowych. Brak treści
odpowiedzi lub brak licznika WFS oznacza brak informacji, a nie zero obiektów.
Kontekst głównej warstwy oznacza warstwę przetwarzaną w chwili rozpoczęcia
żądania; równoczesne działania QGIS mogą wymagać dodatkowego porównania hostów.
Nie zapisujemy adresów usług ze ścieżką/parametrami, treści odpowiedzi, atrybutów,
haseł ani loginów. Nadal przekazuj również manifest, aby dopasować nazwy warstw.
Żaden log nie gwarantuje wskazania przyczyny po stronie serwera lub zabezpieczeń
komputera; w takim przypadku diagnostyka ma pokazać, czego nie udało się ustalić.

## Pobieranie i przerwanie w 0.9.4

Gotowe mapy są scalane na bieżąco, niezależnie od kolejności źródeł w projekcie.
Wolna mapa nie zatrzymuje odbioru innych map ani późniejszych warstw wektorowych.
„Przerwij” zatrzymuje dalsze pobieranie i zachowuje ukończone wyniki; końcowe
scalanie może jeszcze potrwać. Układ i kolejność warstw w zapisanym projekcie
pozostają takie jak w oryginale.

Budżet procesów jest sprawdzany co pięć sekund. Przy 3,83 GiB dostępnego RAM,
rezerwie 2 GiB i szacunku 1 GiB/proces nadal wynosi jeden. Po odzyskaniu pamięci
może wzrosnąć. Okno pokazuje dostępny RAM, limit i czekanie na wolny proces;
szczegóły są w podpowiedzi. Spadek budżetu nie przerywa działających procesów.

Limit czasu QGIS bywa raportowany jako kod Qt 5. Wtyczka rozpoznaje teraz natywny
sygnał timeoutu, także po przekierowaniu usługi; automat robi przerwę i ogranicza
obciążenie. Nie zwiększamy samodzielnie firmowego timeoutu ani nie zmieniamy proxy.
Zwykłe anulowanie żądania nie jest bezwarunkowo uznawane za timeout.

Najpierw wykonaj mały test 3–5 WMS/WMTS i jednego WFS, zoom 16–17, zachowując
raport, manifest i diagnostykę. Sprawdź mapy offline. W oddzielnej próbie przerwij
eksport, gdy co najmniej jedna mapa ma status zakończony, i sprawdź zachowany wynik.
Dopiero później zwiększ obszar i zoom. Dla obszaru z dostarczonego raportu zoom
16–20 oznaczał 3644 kafelki na mapę, a dla 172 map szacunkowo do 626 768 operacji.
Pobieranie dużego projektu nadal może długo trwać; czas zależy od serwerów i RAM.

## Powrót po przerwie i tempo w 0.9.5

Po wyczerpaniu trzech prób jednego kafelka automat może sprawdzić powrót serwera
na następnym brakującym fragmencie, również z kolejnej mapy. Odczekuje wymaganą
przerwę i dopuszcza jedną próbę. Udanych fragmentów nie pobiera ponownie;
wyczerpany kafelek pozostaje oznaczony jako brak. Naprawia to przedwczesne
odkładanie całej kolejki serwera w poprzedniej wersji.

Kilka różnych serwerów może pracować równocześnie. Przy dostępnych około
4,4 GiB RAM obecna ostrożna reguła pozwala na dwa procesy; poniżej 4 GiB budżet
spada do jednego. Przy 6 GiB dostępnego RAM wynosi cztery, jeśli pozwala CPU
i kolejka. Chodzi o pamięć dostępną w danej chwili, nie zainstalowaną w komputerze.
Zamknięcie niepotrzebnych aplikacji może zwolnić RAM. Wtyczka zachowuje rezerwę
2 GiB i szacunek 1 GiB na proces, także gdy inne serwery czekają.

Przykładowy obszar około 153 ha miał 66 kafelków na mapę przy zoomie 13–17,
a około 3650 przy 13–20. To ponad 55 razy więcej pracy. Ustaw szczegółowość
potrzebną do dokumentowania projektu; wtyczka nie obniża jej automatycznie.
Nie obiecujemy konkretnego przyspieszenia na usługach produkcyjnych.

Do próby 0.9.5 wybierz kilka widocznych map z co najmniej trzech różnych hostów,
w tym mapy serwera, który poprzednio zgłosił błąd. Zacznij od tego samego małego
obszaru i zoomów 13–17. Sprawdź raport i treść archiwum bez sieci, a następnie
przekaż `diagnostic.jsonl`, `manifest.json` i `raport.html`. WFS sprawdź na obszarze,
gdzie w oryginalnej warstwie rzeczywiście widać obiekty.

English: 0.9.5 can use the next missing tile to recover a server after another tile
exhausts its three attempts. Scheduling favors idle servers before a second task
on a busy server, with at most two tasks per host. The global CPU/RAM budget remains
conservative. Test several visible maps on different hosts at zooms 13–17, check
them offline, and keep the report, manifest and diagnostic log. Empty WFS output
still requires comparison with known visible source features.
