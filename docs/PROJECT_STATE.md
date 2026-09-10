# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 10 września 2026. Wersja **0.9.7** — równoległość według zmierzonego RAM.

## Zmiana 0.9.7

Po potwierdzeniu jednego procesu w przebiegu 0.9.6 użytkownik zlecił pełniejsze
wykorzystanie komputera i równoczesną pracę kilku map jednego serwera.
Zastąpiono rezerwę 2 GiB wartością 768 MiB, a stały koszt procesu 1 GiB pomiarem
po pierwszym renderowaniu. Koszt nowego procesu to max(384 MiB, 1,5 × największy
szczyt RSS z eksportu); 1 GiB pozostaje wartością początkową bez pomiaru.

Aktywne procesy rezerwują wzrost do tej estymaty. Proces w rozruchu bez odczytu
RSS zachowuje pełny budżet startowy. Spadek RSS nie kasuje szczytu ani rezerwy
na ponowny wzrost; zakończone procesy także pozostawiają pomiar szczytu.
Linux odczytuje /proc/self/status, Windows używa GetProcessMemoryInfo przez ctypes,
pozostałe Unix — peak z resource. Bez nowych zależności. Główny QGIS nie służy
do estymacji procesów mapowych. Telemetria jest czytana przed próbką RAM co 5 s.

Wzrost hosta 1→2→3→… nadal wymaga poprawnych pobrań, wolnego RAM i wzrostu
przepustowości; sufit min(32, 2 × CPU), bez arbitralnego limitu czterech na host.
Nowa podpowiedź RAM PL/EN podaje bieżący koszt procesu i pochodzenie estymaty.
Nagły wzrost zużycia może przekroczyć zapas; to adaptacyjna heurystyka.
Nie podmieniono kodu załadowanego w trwającym eksporcie użytkownika.

Źródła: **128/128 testów**, 107,487 s, bez pominięć. Ruff, formatowanie, AST i diff
poprawne. ZIP: **128/128 testów**, 116,790 s, bez pominięć; wykrywanie, ładowanie,
okno PL/EN i wyłączenie poprawne. Paczka 112 229 bajtów / 22 pliki ma zgodne
źródła i jest powtarzalna. SHA-256:
7c0220ddb630cd15231677705a0f6c3e56e145ddb8cc889760939e5b9c4b19c2.

Porównanie 0.9.6→0.9.7: 190,378→80,609 s, jeden→cztery procesy tego samego
lokalnego WMS i cztery równoczesne GetMap; PNG wszystkich sześciu map identyczne.
Obie próby: CPU 4, 2,5 GiB początkowo, dostępny RAM zmniejszany o rzeczywisty
RSS pracowników. Estymata wtyczki pochodzi z natywnych pomiarów. To kontrolowany
scenariusz, nie gwarancja przyspieszenia serwerów użytkownika. Cztery nie są limitem
w kodzie. Raport: [validation-0.9.7.md](validation-0.9.7.md),
[pomiary](benchmark-0.9.7.json).

## Historia: obserwacja trwającej próby 0.9.6 — 21:26

Odczyt bieżącego przebiegu rozpoczętego 10 września o 21:24:09 potwierdził
wersję 0.9.6, CPU 4 i 2,34 GiB wolnego RAM przy starcie. Do chwili odczytu
log zawierał tylko jeden worker_started; z 10 zarejestrowanych map tylko jedna
miała telemetrię (ponad 400 poprawnych kafelków), pozostałe 9 nie wystartowało.
Bieżące próbki sieci miały HTTP 200 / Qt 0. To obserwacja w trakcie, nie odbiór
całego eksportu ani pełne podsumowanie błędów.

Zrzut pokazywał 2,2 GiB wolnego RAM. Próg rezerwy 2 GiB plus szacunek 1 GiB
na dodatkowy proces nie dopuszcza nowego procesu poniżej 3 GiB. To ograniczenie
heurystyki, nie zmierzony sufit serwera ani udowodniony brak pamięci na drugi QGIS.
Odczyt systemowy o 21:26:11: proces mapowy RSS około 305 MiB, główny QGIS około
1,12 GiB RSS. RSS to chwilowy pomiar, nie gwarancja maksymalnego zużycia. Reguła
1 GiB pozostaje konserwatywna mimo naprawy podwójnego liczenia procesów w 0.9.6.
Analiza tylko do odczytu; bieżącego eksportu i kodu wtyczki nie zmieniono.

## Historia: zmiana 0.9.6 i wcześniejsza próba użytkownika

Próba 0.9.5 na Ubuntu z 10 września 19:49–20:36 trwała 47 min 35,44 s.
Start: CPU 4, 4,66 GiB dostępnego RAM, dwa procesy globalnie. Po 55,39 s stara
reguła obniżyła budżet do jednego przy 3,60 GiB RAM. Oba hosty pozostały przy
limicie 1 bez zamrożenia i błędów; wszystkie 11601 zarejestrowanych GetMap miały
HTTP 200 / Qt 0. To ograniczenie lokalnego planowania, nie dowód sufitu serwera.

Udostępniony tym razem GeoPackage sprawdzono tylko w odczycie: SQLite i klucze
poprawne, wszystkie cztery sumy manifestu zgodne. 5968 PNG 256², 8-bit RGBA,
poprawne CRC i dekompresja, 10 tabel rastra odczytuje GDAL. Dwa WFS zawierają
696 i 1022 obiekty bez błędów. Spośród dziewięciu empty tylko jedna mapa była
całkowicie przezroczysta; osiem miało treść na części zoomów. Nie ma failed
ani partial warstw. To nie rozstrzyga wcześniejszych trzech pustych firmowych WFS.
Nie kopiowano danych użytkownika do repozytorium ani nie odpytywano jego usług.

0.9.6 używa istniejącej automatyki, bez nowych zależności:

- zamiast sztywnego 2/host sufit min(32, 2 × CPU), w ramach wspólnego budżetu RAM;
- dostępny RAM po rezerwie 2 GiB daje 1 GiB na DODATKOWY proces; już działające
  procesy są doliczane osobno, także podczas rozruchu/przerw. MemAvailable już
  uwzględnia ich zużycie. Każda próbka co 5 s przyznaje skończone launch_slots;
  zakończenie mapy nie odnawia przydziału przed kolejną próbką;
- wzrost o 1 po 15 s pomiaru i 10 sukcesach. Mierzymy tylko okresy, kiedy gotowa jest
  docelowa liczba map. Rozruch następnej mapy wstrzymuje pomiar, zachowując
  poprawne próbki; przerwa między zdarzeniami kafelków nie zeruje okna;
- HTTP 407 kończy bieżącą mapę po pierwszej odmowie, zachowuje ukończone PNG
  i opisuje braki; nie odpytuje wszystkich kolejnych kafelków. Inne kody bez zmian;
- widoczna nazwa QGIS Project Snapshot; techniczny ID i prefiks ZIP bez zmian;
- Warstwy w kolejce / Queued layers: opis nagłówka oraz liczby odnosi się do
  serwera w tym wierszu. Limit procesów komputera wyjaśnia lokalne ograniczenie.

Źródła: **115/115 testów**, 102,161 s, bez pominięć; Ruff i formatowanie OK.
ZIP: **115/115 testów**, 103,852 s, bez pominięć; ładowanie QGIS i PL/EN OK.
Paczka dist/qgis-project-snapshot-0.9.6.zip: 110 549 bajtów, 22 pliki;
powtarzalność i zgodność ze źródłami potwierdzone. SHA-256 w raporcie odbioru.
Benchmark: 174,060 s → 79,786 s, identyczne
PNG sześciu map. Jeden host wzrósł 1→2→3→4, cztery równoczesne GetMap.
Wymuszone zasoby były takie same w obu próbach; to pomiar lokalny, nie gwarancja
szybkości serwerów produkcyjnych. Wyniki: [benchmark-0.9.6.json](benchmark-0.9.6.json).
Szczegóły: [validation-0.9.6.md](validation-0.9.6.md).

## Historia: przebieg 0.9.4 i poprawka 0.9.5

Eksport firmowy z 10 września, 16:53–17:22, trwał 28 min 49,545 s; nie anulowano
pracy, coordinator_failed=false. 211 warstw: 61 saved, 116 empty, 33 failed,
1 partial. Wszystkie 139 ukończonych procesów zakończyły się kodem 0 i ich mapy
zostały scalone. Zapisano 1867 PNG z treścią. 90 map całkowicie przezroczystych,
26 miało treść na części zoomów; nie utożsamiaj statusu empty z brakiem wszystkich
kafelków. Trzy WFS zapisane jako saved, ale odebrano zero obiektów bez błędu;
przyczyna nadal nieustalona. Same aux.xml to statystyki, nie raster ani dowód
uszkodzenia GPKG. Rzeczywistego GPKG do audytu nie dostarczono.

Bug: po trzech timeoutach kafelek wyczerpywał próby. Następny brakujący fragment
miał attempts=0, więc recoverable=False; koordynator odkładał cały host przez
no_retryable_tiles bez próby powrotu. To wyjaśnia 33 niepobrane mapy i jedną
częściową. 0.9.5 dopuszcza pojedynczą próbę następnego brakującego kafelka/mapy
po przerwie. Limit trzech prób kafelka, trzech nieudanych powrotów i Retry-After
pozostaje. W adaptacji wszystkie błędy renderowania rozlicza rejestr; brak
ukrytych dodatkowych retry/subdivision dla HTTP500/innych błędów.

Dwa procesy działały przez 1323 s (76,5% przebiegu), z tego około 1201 s na
różnych hostach według pierwszych zarejestrowanych odpowiedzi. To nakładanie
życia procesów, nie dokładny pomiar równoczesnych żądań HTTP. Screenshot 1/1
pokazywał chwilowy budżet. Start: CPU14 i 4,36 GiB dostępnego RAM; budżet zmieniał
się 26 razy między 1 i 2 przy granicy 4 GiB. Zachowano ostrożne liczenie RAM.
0.9.5 preferuje kwalifikujące hosty z mniejszą liczbą aktywnych procesów, adaptive
ma sufit 2/host (stałe API bez zmiany). PNG, zoomy i timeout/proxy QGIS bez zmian.
Przy tym obszarze zoom 13–20 oznacza około 55 razy więcej kafelków niż 13–17;
nie obiecuj przyspieszenia równoważącego tak duży wzrost zadania.

Benchmark 0.9.5: identyczne PNG, stały 57,365 s / 4 procesy, adaptacyjny
87,136 s / 2 procesy. Bieżący RAM ograniczył tylko automat; to nie jest
porównanie szybkości przy równych zasobach ani pomiar przyspieszenia poprawki.
Źródła: 108/108 testów w 94,178 s, bez pominięć. Gotowy ZIP: 108/108 w 93,161 s,
bez pominięć, ładowanie QGIS i PL/EN poprawne. Ruff i kontrola formatowania
53 plików Python poprawne. ZIP 109 583 bajty, 22 pliki, SHA-256 i pełny odbiór:
[validation-0.9.5.md](validation-0.9.5.md).
Następna próba: ZIP 0.9.5 na firmowym Windows, mały obszar i kilka widocznych map
z różnych hostów, porównanie offline oraz WFS z widocznymi obiektami w oryginale.

## Historia wcześniejszych awarii

Test firmowy 0.9.0 wykazał niekompletny wynik: zapisano 39/211 warstw,
172 mapy nieudane, wszystkie trzy WFS puste, coordinator_failed=true.
Nie uznawaj wcześniejszych testów Ubuntu za potwierdzenie działania na Windows.
Diagnostyka firmowa 0.9.1 wskazała PermissionError, errno=13, winerror=5
w `_coordinate → write_state → Path.replace`, podczas podmiany control.json.
Następstwem było anulowanie pracownika i kolejki 171 map (CancelledError).
To nie błąd sterownika GeoPackage. Nie ustalono, kto blokował plik na Windows;
konflikt równoczesnego odczytu/podmiany pozostaje hipotezą. Poprawka 0.9.2
ponawia atomową podmianę przy błędach 5/32/33; kolejne logi potwierdziły
198 skutecznych ponowień bez awarii koordynatora.
Trzy WFS nadal puste, bez zgłoszonych błędów dostawcy — przyczyna nieustalona.
Proxy aktywne i przekazane do procesu; sama konfiguracja nie potwierdza trasy.
Po tej analizie ponownie przeszły 3 testy (11,893 s): WMS do GeoPackage i odczyt
po wyłączeniu serwera, scalanie dwóch map w procesach oraz PNG RGBA/EPSG:2180.
Testy wykonano na Ubuntu; nie stanowią odbioru Windows ani osobnego testu WMTS.

## Audyt przebiegu 0.9.3 i zmiany 0.9.4

Raport firmowy 0.9.3: 3 h 42 min, anulowany. Koordynator działał, wszystkie
198 ponowień blokad IPC zakończyły się powodzeniem. Dziewięć procesów ukończyło
mapy, ale stara pętla scaliła tylko pierwszy wynik. Osiem gotowych map usunięto
przy anulowaniu, mimo 5422 kafelków z treścią w tych wynikach. Cztery mapy były
całkowicie przezroczyste; jedna miała treść tylko na części zoomów. Nie uznawaj
każdego przezroczystego WMS za awarię sieci. Wszystkie trzy WFS anulowano przed
odczytem — ten przebieg nie sprawdza firmowego WFS.

Jeden proces był zgodny z 3,83 GiB dostępnego RAM. Limit pozostawał jednak
zamrożony z chwili startu. Dodatkowo QGIS raportował timeouty po 5 sekundach
jako Qt 5: 927 takich odpowiedzi jednego hosta zajęło łącznie ponad 77 minut.
Brakowało korelacji z natywnym sygnałem timeoutu; automat nie robił przerw.

0.9.4:
- gotowe future są odbierane bez blokowania za wcześniejszą mapą; oryginalna
  kolejność manifestu/drzewa pozostaje zachowana;
- anulowanie kończy nadzorców i scala gotowe mapy, również wynik opublikowany
  przez nadzorcę już po naciśnięciu Przerwij;
- RAM i budżet przeliczane co 5 s, globalny limit nowych procesów, pula
  nadzorców ograniczona min(32,2CPU); spadek RAM nie zabija działających procesów;
- GUI pokazuje RAM, wyjaśnienie budżetu i stany pobierania/czekania;
- native requestTimedOut rozpoznawany także po przekierowaniu i przy Qt 5;
  zwykły Qt 5 bez sygnału timeoutu nie jest automatycznie timeoutem;
- postęp pokazuje fragment/całość, podsumowania zoomów i diagnostykę maski/czasów;
- ciężkie XML warstw usuwane raz ze wspólnego szablonu procesu; przygotowanie
  pompuje Qt i obsługuje anulowanie.

Testy źródeł: 98/98 (80,347 s), bez pominięć. Dodatkowa regresja rozliczenia
kończącego się nadzorcy po Cancel przeszła osobno w zestawie trzech testów kolejki.
Nowe próby potwierdzają zachowanie ośmiu gotowych map, pracę dwóch procesów
po odzyskaniu RAM i timeout lokalnego WMS po przekierowaniu 127.0.0.1→localhost.
Gotowy ZIP: **99/99 testów**, 78,994 s, bez pominięć; ładowanie QGIS poprawne.
Odbiór i szczegóły: [0.9.4](validation-0.9.4.md). Test Windows pozostaje potrzebny.

## Zmiana 0.9.3

- Zachowuje naprawę IPC 0.9.2. Najnowszy ZIP do próby firmowej to 0.9.3.
- NetworkDiagnostics obserwuje istniejące sygnały QGIS, bez dodatkowych zapytań.
  Rejestruje host/rozpoznaną operację/CRS, HTTP/Qt, czas i cache. Trzy próbki
  na grupę i pełne sumy przy zamknięciu; brak startu daje kontekst/czas null.
- XML: ograniczony prefiks, znane kody błędu OGC i liczniki FeatureCollection.
  Nie zapisuj surowych wiadomości ani treści; brak body nie oznacza pustego WFS.
- Wektory: stage, CRS, filtry/edycje (tylko flagi), received/written/empty_geometry/
  outside_mask, stan iteratora, kody zapisu i liczba/zmiana błędów dostawcy.
  Nie zmienia to klasyfikacji pustych wyników ani nie ustala przyczyny firmowego WFS.
- layer_start łączy indeks wybranej warstwy z job/table. Nazwy dopasuj z manifestu;
  główny kontekst nie dowodzi pochodzenia równoczesnych żądań innych zadań QGIS.
- Proces: wersje, provider/CRS/skale i liczniki renderowania. Start: wolny dysk;
  nieudany odczyt wolnego miejsca nie przerywa eksportu.
- Testy źródeł: **84/84**, 66,023 s, bez pominięć; ZIP również **84/84**,
  69,539 s, z poprawnym ładowaniem w QGIS. Ruff i kontrola diff poprawne.
- Odbiór i ograniczenia: [0.9.3](validation-0.9.3.md).

## Zmiana 0.9.2

- Polecenia, telemetria i postęp używają `write_state` z maks. sześcioma próbami
  podmiany po winerror 5/32/33; suma przerw 250 ms. Nie stosuj nieatomowego
  nadpisywania ani nie przedłużaj pozwolenia tylko dlatego, że zapis się nie udał.
- Przerwy respektują anulowanie. Ponowienie telemetrii nie powtarza pobierania
  ani naliczania sukcesów. Poprzedni kompletny JSON pozostaje do czasu podmiany.
- Diagnostyka: ipc_replace_retry/recovered/failed. Trwała blokada nadal kończy
  koordynator bez obejścia ograniczeń; anulowane z tego powodu mapy raportują
  etap coordinator i czerwone ostrzeżenie, zamiast ogólnego błędu pobierania.
- Testy źródeł **80/80**, 63,641 s, bez pominięć. Symulacja błędów Windows
  obejmuje krótką/trwałą blokadę, anulowanie, integralność JSON i telemetrii.
  Lokalny WMS potwierdza ukończenie mapy po krótkiej blokadzie oraz bezpieczne
  zatrzymanie i poprawne opisy kolejki po trwałej blokadzie.
- WFS pozostaje do sprawdzenia na danych użytkownika. Nie zmieniono proxy,
  formatu GeoPackage ani algorytmu renderowania.
- ZIP 0.9.2: ładowanie i **80/80 testów z paczki**, 62,452 s, bez pominięć.
  Instrukcja małego testu na tym samym Windows w `docs/team-guide.md`.
  Raport odbioru: [0.9.2](validation-0.9.2.md).

## Zmiana 0.9.1

- Zawsze po rozpoczęciu eksportu powstaje log diagnostyczny JSONL: przy gotowym
  archiwum `diagnostic.jsonl`, przy wyjątku `<nazwa_archiwum>.diagnostic.jsonl`
  w wybranym folderze nadrzędnym. Walidacja opcji poprzedza rozpoczęcie logowania.
- Typy i miejsca wyjątków, errno/winerror, kody HTTP/Qt, start/wyjście procesów,
  konfiguracja proxy bez adresów i poświadczeń, zdarzenia żądania uwierzytelnienia.
- Wektory: liczba obiektów, oznaczenie pustego odczytu i liczba błędów dostawcy.
  Sam brak obiektów nadal nie dowodzi prawidłowego odczytu WFS.
- Prywatne logi procesów zbierane przed sprzątaniem. Brak surowego stderr,
  treści wyjątków, zmiennych lokalnych, pełnych adresów i danych obiektów.
- Główne zdarzenia warstw: numer wybranej warstwy; procesy: techniczna tabela.
  Log nie jest sumowany w manifeście, ponieważ jest dopisywany do końca eksportu.
- Nie potwierdzamy trasy każdego żądania wyłącznie na podstawie ustawień proxy.
- Raport weryfikacji: [0.9.1](validation-0.9.1.md).

## Cel i zasady

Zespół zachowuje stan projektu QGIS i danych do późniejszego odczytu bez sieci.
Oryginał, niezapisane edycje, ID, grupy, kolejność, style i widoczność mają być
zachowane. Ważne są długie pasy inwestycji, przezroczystość PNG, mocna kompresja
bezstratna i wiele rdzeni CPU. Wektory zapisuj z atrybutami; obraz zastępczy
wymaga jawnej informacji. Nie blokuj sygnału writeProject (utrata relacji).

Nie przekazuj obiektów QGIS z pulpitu do wątków/procesów. Procesy tworzą własne
QGIS, a końcowy GeoPackage ma jednego zapisującego. PNG RGBA ZLEVEL=9, niezależny
render każdego zoomu, rzeczywista maska poligonów. Nie utożsamiaj poprawnego
lokalnego źródła z pełnym odbiorem offline.

## Zmiany 0.9.0 i wynik audytu

- Jedna akcja archiwizacji w menu i na pasku. Usunięto dialog.py, utils.py,
  klasę/akcję dawnego eksportera i jego tłumaczenia. Nie przywracaj starego okna.
- Od 0.9.6 widoczna nazwa produktu: QGIS Project Snapshot; klasa: ProjectSnapshotPlugin.
  Katalog/ID `mbtiles_batch_exporter` pozostaje wyłącznie dla zgodności aktualizacji.
- Proxy: odczyt z aktywnego QGIS i przesłanie zwykłych danych przez stdin procesu.
  Prywatny profil procesu zawiera ustawienia bez hasła/loginu/authcfg. Zapisane,
  rozpoznane poświadczenia są w pamięci, podawane na żądanie Qt dla właściwego proxy.
  Obsługę wyjątków i trybu systemowego pozostawiono natywnemu QGIS/Qt.
- Proxy wyłączone w QGIS nie jest włączane przez proces. Nie wpisujemy adresów
  firmowych w kodzie. Nie kopiujemy bazy auth i nie wyłączamy walidacji TLS.
- WorkerError/error.json: bezpieczny etap, kod wyjścia, HTTP i Qt. Osobne opisy
  407, połączenia z proxy i TLS. Nigdy nie zapisuj surowych wyjątków dostawców.
- HTTP 407 nie uruchamia kolejnych prób kafelka ani zwiększania limitu.
- Windows: CREATE_NO_WINDOW i dodatkowy kandydat sys.prefix/python.exe.
  Brak interpretera/awaria w automatyce nie powodują nieograniczonego zastępstwa
  w głównym QGIS. Projekt procesu niszczymy przed jego QgsApplication.
- Host bez pracy pokazuje zakończenie lub błędy. Log i manifest zawierają
  zasoby wykryte przy starcie i budżet procesów.
- Ruff 0.16.6: E/W/F/I i formatowanie, zero zgłoszeń. Limit 88 znaków jest
  konwencją projektu. E402 wyłączono wyłącznie dla bootstrapu trzech modułów testów.
  Brak typecheckera; nie deklaruj wykonania Bandita/detect-secrets/pip-audit.
- Testy źródeł i paczki używają izolowanych profili QGIS.

Pełny opis: [audyt i odbiór 0.9.0](validation-0.9.0.md).
Nie zweryfikowano firmowego proxy Windows, PAC/SSO/NTLM/Kerberos/Socks5 ani wszystkich
wariantów authcfg. Nie przenosimy niestandardowego magazynu certyfikatów profilu.
To ograniczenia odbioru i zakresu konfiguracji; test HTTP Basic nie dowodzi obsługi
każdej infrastruktury. Użytkownik nie powinien podawać proxy agentowi — wtyczka
ma korzystać z konfiguracji QGIS.

## Bieżące zachowanie

`create_archive(adaptive=False)` zachowuje API stałych limitów; GUI używa wyłącznie
automatyki. Start 1 mapa/host, wzrost po 15 s i 10 sukcesach przy kolejce i zasobach.
Dwa okna bez 10% poprawy cofają limit i kończą wzrost; pomiar obejmuje
tylko czas z docelową liczbą gotowych map, zachowany również przy zmianie mapy. HTTP 429/503 i trzy kolejne
timeouty zmniejszają limit i rozpoczynają przerwę. Retry-After sekundy/data,
inaczej 30/60/120 s; po przerwie jedna próba rzeczywiście brakującego kafelka.
Trzy nieudane powroty lub oczekiwanie ponad pięć minut odkładają host.

Sufit min(32,2CPU) na host i globalnie. Budżet RAM to istniejące procesy plus
miejsca dla nowych po1GiB z dostępnego RAM po rezerwie2GiB, minimum1. Nieznany
RAM ogranicza do2. Co5s nowa próbka przyznaje launch_slots zużywane przez starty;
nie odnawia ich koniec mapy. Presja pamięci blokuje wzrost i nowe procesy.
Czekające procesy też liczą się do budżetu.
To zadania mapowe, nie dokładna liczba HTTP/s, pomiar łącza czy gwarancja maksimum.
WFS, MSSQL, rastry źródłowe i wektory z edycjami nie są zrównoleglane przez automat.

Dyskowy rejestr każdej mapy pamięta również poprawne przezroczyste kafelki.
Początkowy zapis i najwyżej dwie dodatkowe rundy uzupełniają tylko braki w bieżącym
archiwum. Brak wznawiania po zamknięciu QGIS i pamięci limitów między eksportami.
Prywatne rejestry są sprzątane. Manifest 4 zachowuje historię i statystyki.

Podczas pracy można przewijać listy, rozwijać grupy i czytać podpowiedzi.
Zmiana parametrów i checkboxów jest zablokowana; przywracamy flagi w finally.
Nie usuwaj ItemIsEnabled, bo blokuje nawigację. Natywne synchroniczne odczyty
w głównym QGIS nadal mogą na chwilę zatrzymać obsługę zdarzeń.

Końcowy ręczny przycisk ponowienia zaznacza failed/cancelled/empty/partial,
odznacza saved/excluded i tworzy nowe archiwum wybranych warstw. Nie myl go
z automatycznym uzupełnianiem kafelków w bieżącym eksporcie.

PL/EN: i18n.py + en.ts/en.qm, 282 tłumaczenia. Po zmianach uruchom lrelease.
Szacunek jednej mapy: 0,2–2 s i 10–250 KiB PNG/kafelek; nie jest to gwarancja.
Ikony SVG: archive icon.svg, cpu.svg, ram.svg; inne przyciski używają QStyle.

## Historyczna paczka i kontrole 0.9.0

- `dist/qgis-project-snapshot-0.9.0.zip`: 96 880 bajtów, 21 plików.
- SHA-256: `106992555dea5cb46130adb670acf3dd0bef8527e76a429cda0dd24319f0f307`.
- **70/70 testów ZIP-a**, bez pominięć, 59,582 s; pełne źródła: 57,994 s.
- Ubuntu, QGIS 3.40.15, GDAL 3.12.2, Python 3.14.4, PyQt5, Qt offscreen.
- Testy lokalnego proxy: poprawne Basic, wyłączenie, wyjątki, 407, awaria startu,
  brak poświadczeń w archiwum i brak niesprzątniętych katalogów procesu.
- Ruff check i format --check: 23 pliki Python, OK. Składnia, CRC, źródła/ZIP
  i diff --check: OK. Bez nowych zależności wymaganych przez wtyczkę.
- Benchmark 0.8.0 jest historyczny: stały 57,706 s, adaptacyjny 58,323 s,
  identyczne PNG sześciu map. Nowszy pomiar 0.9.5 opisano na początku tego dokumentu.

## Następny krok i pliki

Kod i paczka 0.9.7 przeszły końcowe kontrole lokalne opisane wyżej.
Aktualizacja wymaga instalacji nowego ZIP-a oraz restartu QGIS po zakończeniu
trwającej pracy. Nie podmieniano kodu aktywnego eksportu użytkownika.
Odbiór na firmowym Windows pozostaje po stronie stanowiska z skonfigurowanym QGIS.
MSSQL działa tylko w sieci firmowej, trzy rastry projektu są tu nieobecne.
Nie zgaduj adresów ani nie proś ponownie o poświadczenia. Sprawdzenie wszystkich
warstw, uwierzytelniania, stylów, formularzy, relacji i wydruków wymaga stanowiska
firmowego oraz późniejszej próby offline.

Kod: `mbtiles_batch_exporter/`, wersja: metadata.txt. Szczegóły modułów:
[architecture.md](architecture.md). Budowa/testy/Ruff: [development.md](development.md).
Instrukcja użytkownika: [team-guide.md](team-guide.md), pakowana jako INSTRUKCJA.md.
ZIP-y w ignorowanym dist; dokumenty agentów nie są pakowane. Raportów historycznych
nie nadpisuj. Nie opublikowano GitHub Release ani wydania w katalogu QGIS.
