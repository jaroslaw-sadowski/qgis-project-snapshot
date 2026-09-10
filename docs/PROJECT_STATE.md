# Stan projektu — punkt startowy dla kolejnej sesji

Aktualizacja: 10 września 2026. Wersja **0.9.0**. Gotowa paczka po naprawie proxy,
usunięciu dawnego eksportera i audycie Ruff. Pełny odbiór Windows oraz źródeł
firmowych pozostaje do wykonania. Przed pracą sprawdź git status i historię;
nie zakładaj, że zmiany tej sesji zatwierdzono lub wysłano.

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
- Nazwa produktu: qgis-project-snapshot; klasa: ProjectSnapshotPlugin.
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
Dwa okna bez 10% poprawy cofają limit i kończą wzrost. HTTP 429/503 i trzy kolejne
timeouty zmniejszają limit i rozpoczynają przerwę. Retry-After sekundy/data,
inaczej 30/60/120 s; po przerwie jedna próba rzeczywiście brakującego kafelka.
Trzy nieudane powroty lub oczekiwanie ponad pięć minut odkładają host.

Sufit 8 map/host; globalnie min(32, 2 × CPU, RAM po rezerwie 2 GiB przy
1 GiB/proces), minimum 1. Nieznany RAM ogranicza do 2. RAM sprawdzamy co pięć sekund;
presja pamięci blokuje wzrost i nowe procesy. Czekające procesy też liczą się do RAM.
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

PL/EN: i18n.py + en.ts/en.qm, 273 tłumaczenia. Po zmianach uruchom lrelease.
Szacunek jednej mapy: 0,2–2 s i 10–250 KiB PNG/kafelek; nie jest to gwarancja.
Ikony SVG: archive icon.svg, cpu.svg, ram.svg; inne przyciski używają QStyle.

## Paczka i kontrole

- `dist/qgis-project-snapshot-0.9.0.zip`: 96 880 bajtów, 21 plików.
- SHA-256: `106992555dea5cb46130adb670acf3dd0bef8527e76a429cda0dd24319f0f307`.
- **70/70 testów ZIP-a**, bez pominięć, 59,582 s; pełne źródła: 57,994 s.
- Ubuntu, QGIS 3.40.15, GDAL 3.12.2, Python 3.14.4, PyQt5, Qt offscreen.
- Testy lokalnego proxy: poprawne Basic, wyłączenie, wyjątki, 407, awaria startu,
  brak poświadczeń w archiwum i brak niesprzątniętych katalogów procesu.
- Ruff check i format --check: 23 pliki Python, OK. Składnia, CRC, źródła/ZIP
  i diff --check: OK. Bez nowych zależności wymaganych przez wtyczkę.
- Benchmark 0.8.0 jest historyczny: stały 57,706 s, adaptacyjny 58,323 s,
  identyczne PNG sześciu map. Nie wykonywano nowego pomiaru po audycie.

## Następny krok i pliki

Odbiór ZIP-a 0.9.0 na komputerze użytkownika z już skonfigurowanym proxy QGIS.
MSSQL działa tylko w sieci firmowej, trzy rastry projektu są tu nieobecne.
Nie zgaduj adresów ani nie proś ponownie o poświadczenia. Sprawdzenie wszystkich
warstw, uwierzytelniania, stylów, formularzy, relacji i wydruków wymaga stanowiska
firmowego oraz późniejszej próby offline.

Kod: `mbtiles_batch_exporter/`, wersja: metadata.txt. Szczegóły modułów:
[architecture.md](architecture.md). Budowa/testy/Ruff: [development.md](development.md).
Instrukcja użytkownika: [team-guide.md](team-guide.md), pakowana jako INSTRUKCJA.md.
ZIP-y w ignorowanym dist; dokumenty agentów nie są pakowane. Raportów historycznych
nie nadpisuj. Nie opublikowano GitHub Release ani wydania w katalogu QGIS.
