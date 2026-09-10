# Audyt i odbiór 0.9.0 — 10 września 2026

## Wynik i paczka

`dist/qgis-project-snapshot-0.9.0.zip`: **96 880 bajtów, 21 plików**.
SHA-256: `106992555dea5cb46130adb670acf3dd0bef8527e76a429cda0dd24319f0f307`.

- Pełne testy źródeł: **70/70**, 57,994 s.
- Pełne testy końcowego ZIP-a: **70/70**, 59,582 s, bez pominięć WMS/proxy.
- Natywne wykrywanie, ładowanie, jedna akcja menu/paska, okno i wyłączenie: OK.
- CRC, zgodność każdego pliku ZIP-a ze źródłem, składnia i git diff --check: OK.
- Ubuntu, QGIS 3.40.15, GDAL 3.12.2, PyQt5, Python 3.14.4, Qt offscreen.

Nie opublikowano wydania ani nie wykonano odbioru Windows/sieci firmowej.
Komunikaty GDAL o braku pikseli dotyczą celowo pustego rastra testowego.

## Zakres audytu i naprawy

| Obszar | Ustalenie i wynik |
| --- | --- |
| Proxy | Procesy nie miały zapewnionej konfiguracji aktywnego QGIS. Teraz otrzymują ustawienia, wyjątki, tryb systemowy, timeout i dostępne zapisane poświadczenia przez stdin. |
| Dane dostępowe | Login/hasło nie trafiają do CLI, manifestu ani plików konfiguracyjnych procesu. Proces używa własnego profilu i poświadczeń w pamięci. |
| Diagnostyka | Ogólne błędy maskowały przyczynę. Raport zawiera etap, kod wyjścia, HTTP i Qt; osobne komunikaty dla proxy/407/TLS. Surowych wyjątków dostawców nie zapisujemy. |
| Próby | HTTP 407 nie uruchamia napraw kafelków ani zwiększania obciążenia. Awaria procesu nie obchodzi limitera przez automatyczne zastępstwo w głównym QGIS. |
| Windows | Pozostaje CREATE_NO_WINDOW; interpreter sprawdzany również w sys.prefix/python.exe. Rzeczywisty efekt na Windows wymaga odbioru. |
| Postęp | Host bez pracy pokazuje zakończenie lub błędy. Log i manifest zawierają wykryte przy starcie CPU/RAM i wynikowy budżet. |
| Dawny eksporter | Usunięto dialog.py, utils.py, klasę/akcję eksportera i nieużywane tłumaczenia. Pozostaje jeden produkt i jedna akcja. Zachowany identyfikator instalacji służy migracji. |
| Testy | Izolowane profile również dla testów źródeł; nie należy używać profilu pulpitu. Sprawdzono nowe scenariusze i istniejące zachowania danych, anulowania oraz PL/EN. |
| Cykl życia QGIS | Podczas implementacji wykryto błąd kolejności niszczenia stylów projektu. Projekt procesu jest jawnie zwalniany przed QgsApplication; testy ponowiono. |

Przegląd obejmował wszystkie moduły produktu, skrypt pakowania i testy: przepływ
projektu, procesów, konfiguracji sieci, danych i diagnostyki. Nie jest to formalny
certyfikat bezpieczeństwa ani dowód braku wszystkich możliwych błędów.

## Proxy — dowody testowe

Lokalny serwer obsługuje rolę proxy HTTP. Nazwa źródła `.invalid` nie ma publicznego
DNS, więc pobranie mapy przez osobny QGIS wymaga faktycznego użycia proxy.
Sprawdzono:

- poprawny zapis mapy przez proxy z loginem i hasłem Basic oraz lokalny odczyt;
- wyłączone proxy i jawny wyjątek noProxyUrls — pobranie bez proxy;
- odrzucenie danych logowania (407), czytelny kod i brak poświadczeń w wynikach;
- brak starych poświadczeń w konfiguracji przesyłanej przy wyłączonym proxy;
- nieudane uruchomienie procesu — etap process_start bez tekstu wyjątku;
- usunięcie prywatnych katalogów procesu i brak testowych poświadczeń w archiwum.

Implementację oparto na [QgsNetworkAccessManager w QGIS 3.40](https://api.qgis.org/api/3.40/qgsnetworkaccessmanager_8cpp_source.html).
Routing, wyjątki i tryb systemowy obsługuje natywny QGIS/Qt; nie dodano klienta HTTP
ani ręcznych ustawień proxy we wtyczce.

## PEP 8 i Ruff

Ruff **0.16.6**, zainstalowany wyłącznie w tymczasowym środowisku developerskim.
`pyproject.toml` obejmuje reguły E/W (pycodestyle), F (Pyflakes), I (importy).
Oba polecenia końcowe przechodzą:

```bash
ruff check .
ruff format --check .
```

Sprawdzono 23 pliki Python. Pierwszy audyt E/W/F/I jeszcze z dawnym eksporterem
wskazał 681 problemów: 640 długości linii, 29 importów, sześć połączonych instrukcji,
pięć niejasnych nazw zmiennych i przypisanie lambda. Naprawiono styl całego
pozostałego kodu; część ustaleń zniknęła wraz z usuniętym eksporterem.
Długie teksty dzielono na sąsiadujące literały, kontrolując zachowanie wartości AST.

Limit 88 znaków to jawna konwencja formattera projektu, zamiast ścisłego limitu
79 znaków z PEP 8. Wyjątki E402 dotyczą tylko modułów testowych, gdzie konfiguracja
środowiska musi poprzedzać import Qt/QGIS. Nie wyłączono globalnie kontroli długości
linii ani pozostałych reguł. Nie uruchamiano osobnego typecheckera, Bandita,
detect-secrets ani pip-audit; nie deklarujemy wykonania tych kontroli.

## Granice i dalszy odbiór

Testy obejmują standardowe HTTP Basic. Nie zweryfikowano w rzeczywistym Windows
Socks5, systemowego PAC, NTLM/Kerberos/SSO, interaktywnego logowania ani wszystkich
konfiguracji authcfg. Przekazywane są poświadczenia już rozpoznane przez aktywny
menedżer QGIS; blokady jego magazynu uwierzytelniania nie są obchodzone.
Nie kopiujemy niestandardowych certyfikatów i pełnej bazy uwierzytelniania profilu,
a walidacja TLS pozostaje aktywna. Firmowy proxy wymaga próby na stanowisku użytkownika.

MSSQL i trzy rastry projektu są tutaj niedostępne. Długie synchroniczne odczyty
w głównym QGIS mogą nadal czasowo blokować obsługę zdarzeń. Nie dodano wznawiania
po zamknięciu QGIS ani zmiany zasad archiwizacji standardowych kafelków OSM.
Nie powtarzano benchmarku wydajności; pomiar 0.8.0 pozostaje historyczny.

Po uporządkowaniu sprzątania profili testowych powtórzono pięć testów proxy:
5/5, 9,119 s, bez ostrzeżenia o niejawnym usuwaniu TemporaryDirectory.
Zmiana testów nie zmieniła bajtów paczki.
