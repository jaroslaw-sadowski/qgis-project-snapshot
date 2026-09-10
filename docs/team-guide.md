# QGIS Project Snapshot — instrukcja 0.9.7

## Instalacja i uruchomienie

1. QGIS: **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Wskaż `qgis-project-snapshot-0.9.7.zip`. Po aktualizacji uruchom ponownie QGIS.
3. Otwórz **Wtyczki → QGIS Project Snapshot → Archiwizuj projekt…**.

Wymagane: QGIS 3.40, PyQt5 i GDAL 3.7 lub nowszy. Sprawdzono Ubuntu;
Windows i źródła firmowe wymagają próby na stanowisku służbowym.
Wersja 0.9.7 jest paczką do lokalnej instalacji; nie opublikowano jej w katalogu QGIS.
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
**aktywne zadania / limit**, **Warstwy w kolejce**, skuteczne kafelki/s, stan
i pozostałą przerwę. „Warstwy w kolejce” to warstwy czekające na rozpoczęcie
pobierania z serwera w tym wierszu; liczba nie obejmuje już pobieranych warstw.
Nad nią widać wykorzystanie procesów map. Limity dotyczą zadań mapowych, nie dokładnej
liczby żądań HTTP na sekundę — dostawca QGIS może wysyłać kilka żądań dla jednego zadania.

Automat zaczyna od 1 zadania na host. Po co najmniej 15 sekundach i 10 poprawnych
kafelkach może zwiększyć limit o jeden, jeśli są następne mapy do pobrania i wolne
zasoby komputera. Sprawdza, czy zwiększanie poprawia szybkość. Po dwóch pełnych
oknach bez co najmniej 10% przyspieszenia wraca o krok i zatrzymuje dalszy wzrost.
Ocena zaczyna się dopiero, gdy faktycznie działa badana liczba gotowych procesów;
sam start QGIS lub brak wolnych procesów nie oznacza osiągnięcia limitu serwera.
Przejście do następnej mapy wstrzymuje pomiar na czas rozruchu, zachowując
wcześniejsze poprawne próbki.
Błędy przeciążenia także zmniejszają obciążenie i zatrzymują wzrost w tym eksporcie.
Pierwszeństwo mają serwery z mniejszą liczbą aktywnych procesów.

Łączny limit to najwyżej 32 procesy i nie więcej niż dwukrotność dostępnych CPU;
w jego ramach pojedynczy serwer może przekroczyć dwa zadania. Automat pozostawia
768 MiB wolnego RAM. Początkowo zakłada 1 GiB dla nowego procesu, a po pierwszych
pobraniach używa największego zmierzonego zużycia powiększonego o 50%, co najmniej
384 MiB. Pomiar jest wspólny dla map tego eksportu i uwzględnia późniejszy wzrost.

Osobno odkłada zapas na wzrost już działających procesów oraz pełny przewidywany
koszt procesów, które dopiero się uruchamiają. Sprawdza pamięć co 5 sekund;
zakończenie mapy nie pozwala ponownie wykorzystać tej samej próbki pamięci.
Przy 305 MiB na proces oraz około 2,2 GiB wolnego RAM może dopuścić kilka map,
stopniowo sprawdzając wydajność serwera. Podpowiedź przy RAM pokazuje bieżący
szacowany koszt procesu i informuje, czy pochodzi z pomiaru.

Nieznany dostępny RAM ogranicza automat do dwóch procesów. Procesy czekające
na serwer nadal zajmują pamięć. Niedobór blokuje nowe uruchomienia, a działające
mapy są zachowywane. Nagły wzrost zużycia przez inne aplikacje lub źródło danych
może przekroczyć przyjęty zapas; automat nie gwarantuje braku wyczerpania pamięci.

Stan **Limit procesów komputera** oznacza, że zasoby komputera ograniczają dalszy
wzrost; sam odczyt „1 / 1” nie dowodzi osiągnięcia maksymalnej szybkości serwera.

To heurystyka, nie gwarancja najszybszego ustawienia. Krótki eksport może skończyć
się przed zwiększeniem równoległości. Pojedyncza mapa nadal jest obsługiwana przez
jeden proces. Wektory, rastry źródłowe i niezapisane edycje pozostają w głównym QGIS.

## Czerwone ostrzeżenie i uzupełnianie

HTTP 429 oznacza zbyt wiele zapytań. HTTP 503 oznacza niedostępność lub możliwe
przeciążenie; nie dowodzi, że przyczyną jest nasz ruch. Automat wstrzymuje nowe
pobrania tego hosta i respektuje `Retry-After`. Inne hosty mogą pracować dalej.
Bez terminu od serwera stosuje przerwy 30/60/120 sekund. Pierwsza próba po przerwie
dotyczy brakującego kafelka; dopiero sukces pozwala wznowić pozostałe zadania.
Trzy kolejne timeouty również uruchamiają przerwę. Wtyczka korzysta z limitu czasu
QGIS; nie zmienia ustawień proxy ani firmowego timeoutu.

Poprawne kafelki, również przezroczyste, nie są pobierane ponownie. Automat uzupełnia
braki **w tym samym archiwum**, najwyżej dwukrotnie po pierwszym pobraniu kafelka.
Gdy limit prób się wyczerpie albo serwer wymaga czekania ponad 5 minut, pozostawia
wynik niepełny i zapisuje powód. Błędów dostępu 401/403/404 nie ponawia automatycznie.
Po wyczerpaniu prób jednego kafelka powrót serwera może sprawdzić na następnym
brakującym fragmencie, również z kolejnej mapy. Nie odzyskuje w ten sposób
wyczerpanego kafelka, który pozostaje oznaczony jako brak.

Gotowe mapy są scalane na bieżąco, niezależnie od kolejności pobierania. Układ
i kolejność warstw w zapisanym projekcie pozostają takie jak w oryginale.
**Przerwij** działa również podczas oczekiwania. Zachowuje ukończone, scalone mapy;
nieukończone prywatne pliki są usuwane. W razie problemu możesz przerwać i sprawdzić
raport. Końcowe scalanie może jeszcze potrwać. Automat nie wznawia pracy po
zamknięciu QGIS i nie pamięta limitów między eksportami.

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

Open **Plugins → QGIS Project Snapshot → Archive project…**. Choose the folder,
area, layers and zooms, then **Create archive**. Concurrency is automatic. The
server table shows active tasks/limit, successful tiles/s, state and cooldown.
**Queued layers** counts layers waiting to start downloading from the server in
that row, excluding layers already downloading.

Each host starts at one map task. After at least 15 seconds and 10 successful tiles,
its limit may increase by one if more maps are queued and resources are available.
Servers with fewer active processes get priority. Two full windows without at least
10% speed gain reduce the limit and stop growth. A window is assessed only when the
target number of map processes is ready; starting QGIS or waiting for computer
capacity does not indicate the server's speed limit. Map handoffs pause measurement
during startup and retain earlier valid samples. Overload errors also reduce
the load and stop growth for this export.

The total cannot exceed 32 processes or twice the available CPU count; a server
can use more than two. The automatic control keeps 768 MiB available. Initially it
allows 1 GiB for a new process; after downloads it uses the highest measured process
memory plus 50%, with a minimum of 384 MiB. It also reserves room for existing
processes to grow and for unmeasured processes to finish starting. Memory is checked
every 5 seconds. The RAM tooltip shows the estimate and whether it uses measurements.
Unknown available RAM limits the total to two. **Computer process limit** means
computer capacity is blocking growth. This controls map tasks, not HTTP requests/sec.

HTTP 429/503 triggers a host cooldown. Other hosts continue. Retry-After is respected;
otherwise backoff is 30/60/120 seconds. Only missing tiles are repaired in the same
archive, with at most two additional attempts. Successful and transparent tiles are
not fetched again. Long waits, exhausted retries and permanent access errors are
reported as incomplete results. Cancel remains available while waiting.

After export, check the report and open the archived project offline. Move the entire
folder. The final Retry button creates a separate archive of selected layers; keep
both folders. There is no restart/resume after closing QGIS. Service usage policies
still apply. Hover over controls for details.

## Proxy i błędy połączenia

Nie wpisujesz proxy we wtyczce. Korzystamy z ustawień sieci aktywnego QGIS,
w tym wyjątków i dostępnych zapisanych poświadczeń. Gdy proxy jest wyłączone,
procesy nie włączają własnego proxy. Nie zmieniaj firmowej konfiguracji tylko
na potrzeby archiwizacji.

HTTP 407 oznacza odrzucenie uwierzytelnienia proxy. Pobieranie tej mapy kończy się
po pierwszej odmowie, z zachowaniem już pobranych fragmentów i opisem braku
w raporcie. Inne komunikaty odróżniają
problem połączenia z proxy, weryfikacji TLS i uruchomienia procesu QGIS. Raport
zawiera etap i kody błędów, bez haseł oraz pełnych adresów usług. Nietypowe
logowanie firmowe lub certyfikaty mogą wymagać odbioru na danym stanowisku.

Przy starcie dziennik pokazuje wykryte CPU, dostępny RAM i wybrany limit procesów.
„Rezerwa RAM: 768 MiB” oznacza zapas wolnej pamięci. Zużycie głównego QGIS
jest już uwzględnione w pomiarze wolnego RAM. Host bez dalszych zadań pokazuje zakończenie lub błędy.
Dawny osobny eksporter MBTiles usunięto; w menu i na pasku jest jedna akcja.

English: the plugin uses the active QGIS proxy configuration and exclusions.
Available saved proxy credentials are transferred in memory, not written into
the archive. HTTP 407 stops the current map after the first proxy authentication
refusal, preserving completed tiles and reporting missing data. TLS verification
remains enabled. The startup log shows detected CPU/RAM and the process budget.
The legacy standalone MBTiles exporter has been removed.

## Plik diagnostyczny dla developera

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

## Odbiór na Windows 0.9.7

1. Zainstaluj ZIP 0.9.7 przez „Wtyczki → Zarządzanie i instalowanie wtyczek →
   Instaluj z ZIP”, zamknij cały QGIS i uruchom go ponownie. Sprawdź wersję
   w menedżerze wtyczek. Zachowaj firmowe ustawienia proxy.
2. Użyj tego samego komputera. W projekcie źródłowym wybierz mały obszar,
   na którym widać treść 4–6 publicznych WMS/WMTS: przynajmniej trzy mapy
   jednego serwera i jedną z innego. Pozwoli to sprawdzić wzrost obciążenia
   oraz równoczesną pracę serwerów. Nie wybieraj standardowych kafelków OSM
   do tej próby. Ustaw zoom 16–17 i „Aktualny widok mapy”.
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
Wersja 0.9.7 dobiera liczbę procesów na podstawie pomiarów ich pamięci. Zachowuje poprawki
blokad plików sterujących oraz powrotu serwera po przerwie. Nie potwierdza jeszcze
poprawnego odczytu wszystkich firmowych WFS ani przyczyny ich wcześniejszych
pustych wyników.
