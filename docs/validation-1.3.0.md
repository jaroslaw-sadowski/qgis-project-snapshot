# Wydanie 1.3.0 — pomiary i ciągły dobór obciążenia

Data: 12 września 2026. Użytkownik przekazał nowy manifest i diagnostykę 1.2.0
oraz zlecił optymalizacje na podstawie pomiarów. Surowe dane projektu pozostają
poza repozytorium. Poniższe liczby opisują ten przebieg, a nie test porównawczy
różnych wersji na identycznym projekcie.

## Wnioski z przebiegu 1.2.0

Windows 11, Core Ultra 5 135U, 16 GB RAM, 14 procesorów logicznych,
QGIS 3.40.15. Eksport 13:54:47–14:37:53 trwał 43 min 6 s, zoomy **16–18**.
Nie porównujemy tego czasu wprost z wcześniejszym zakresem 0–20.

| Pomiar | Wynik |
| --- | --- |
| Warstwy | 211: 96 saved, 109 empty, 6 failed; bez partial i anulowania |
| Procesy / aktywne zadania | Maksymalnie 13 / 11 |
| CPU całego systemu | Średnia ważona czasem 29,39%; pierwsze 15 minut 52,44% |
| Minuty 20–40 | 3 procesy przy budżecie około 10; CPU 15,16% |
| Dostępny RAM w minutach 20–40 | Średnio 5,08 GiB |
| Najmniejszy dostępny commit Windows | 325 MiB przy 4,52 GiB dostępnego RAM |
| Scalanie do końcowego GeoPackage | Łącznie 52,7 s; najwyżej jedna mapa w kolejce |
| Zakończenie procesów | Wszystkie 172 z kodem 0; bez awarii koordynatora |

CPU systemu obejmuje wszystkie programy. CPU samej wtyczki nie można utożsamiać
z tą wartością: główny proces QGIS obsługuje też inne zadania. Średnie wyliczono
z długości okresów pomiędzy próbkami, nie przez proste uśrednienie nierównych okien.
Próbki co około 5 s mogą nie ujawniać krótkich skoków.

`mapy.geoportal.gov.pl` osiągnął limit 3, lecz po 431 s wrócił do 2 i pozostał
zamrożony. Kolejka trwała jeszcze 2001 s, w tym przez około 1840 s były wolne
miejsca globalne. Ograniczenie powstało po braku 10% przyspieszenia, bez przerwy
429/503. Szybkość zmieniała się wraz z warstwami, więc pojedynczy pomiar nie
wyznaczał sufitu na cały eksport. Podobne zamrożenie Integracji pozostawiło
kolejkę jeszcze przez około 253 s. To uzasadnia ponowne sprawdzanie wyższego limitu.

Sześć błędnych map jednego serwera leśnego wykonało razem 4320 prób na 1440
kafelkach; 4317 odpowiedzi było HTTP 200 `text/xml` zamiast obrazu. Dokładnego
błędu WMS nie znamy, ponieważ QGIS nie udostępnił treści odpowiedzi. Siódma mapa
tego samego hosta została pobrana poprawnie. Błędy jednej usługi nie uzasadniają
pomijania całego hosta ani uznania wszystkich jego map za puste.

Te błędne mapy spędziły łącznie 1649,71 s w bramce pozwoleń i 653,04 s
w renderowaniu. Oczekiwanie na potwierdzenie każdego zwykłego błędu co 0,5 s
nie zmieniało limitu serwera, a wydłużało przetwarzanie całej kolejki.

Manifest wykazuje 10 517 zapisanych kafelków. **Dziewięć warstw oznaczonych empty
zawiera obrazy na części zoomów** — tego statusu nie wolno utożsamiać z całkowitym
brakiem treści. Wszystkie 36 wektorów zakończyło prawidłowy odczyt zerem obiektów;
taki wynik jest dopuszczalny. Nie potwierdza obecności lub nieobecności obiektów
w oryginalnym projekcie bez jego sprawdzenia. Audyt lokalnych warstw w manifeście
przeszedł, ale dostarczone dwa pliki nie umożliwiają niezależnego odczytu GPKG/QGZ.

## Zmiany

- Limit hosta nadal rośnie o jeden po pełnym oknie minimum 15 s i 10 sukcesów.
  Po cofnięciu wzrostu stabilizacja trwa początkowo 60 s poprawnych pełnych okien,
  następnie można sprawdzić pojedynczy dodatkowy slot. Dwa okna bez 10% zysku
  cofają próbę; kolejne nieudane próby wydłużają stabilizację do 120/240/300 s.
  Porównanie używa aktualnej szybkości niższego limitu.
- Ustalony limit również podlega kontroli: dwa pełne okna ze spadkiem szybkości
  o ponad 25% względem wygładzonego odniesienia powodują redukcję o jeden.
  Niepełna obsada podczas rozruchu nie jest dowodem przeciążenia.
- HTTP 429/503 powoduje zmniejszenie i przerwę; trzy kolejne timeouty lub błędy
  502/504 również uruchamiają tę ochronę. Retry-After obowiązuje także, gdy
  nadejdzie z opóźnieniem po udanej próbie powrotu.
- Zwykłe błędy WMS pozostają w telemetrii bez oczekiwania na każde ACK.
  Przeciążenie, timeout i próby powrotu nadal wymagają potwierdzenia. Każdy
  kafelek wymaga ważnego pozwolenia; utrata koordynatora nadal zatrzymuje pracę.
- Budżet startów na Windows bierze mniejszą wartość RAM i dostępnego commit.
  Zachowano rezerwę 768 MiB i zapas wzrostu. Ponowne dopuszczenie oczekującego
  procesu również wymaga pokrycia tego zapasu. Interfejs rozróżnia fizyczny RAM
  i ograniczenie przydziału pamięci Windows.
- Brak RAM nie blokuje rozliczenia warstw hosta odłożonego do późniejszej próby.
  Pierwsze procesy startują dopiero po aktualnym pomiarze zasobów.

Nie dodano zależności. Zachowano pojedynczego zapisującego końcowy GPKG,
PNG RGBA/ZLEVEL=9, próby wszystkich kafelków, anulowanie i kontynuację warstw.
Przegląd według [Ponytail](https://github.com/dietrichgebert/ponytail) polegał na
wykorzystaniu istniejących HostPolicy, WorkerGate i natywnych pomiarów.
Ponytail jest zasadą przeglądu, nie automatycznym certyfikatem jakości.

## Kontrolowany pomiar oczekiwania na ACK

QGIS 3.40.15 na Ubuntu, lokalny WMS i rzeczywisty koordynator z `local_gate`.
Badano dwie warstwy tego samego hosta: dziewięć kafelków zawsze zwracających XML
oraz dziewięć poprawnych obrazów. Wariant A podstawiał jedynie metodę
`WorkerGate.outcome` z 1.2.0, commit
`af1088e495686acac9612458661be54cfe6d0984`; wariant B używał nowej metody.
Pozostały kod i dane były takie same. Kolejność A/B/B/A, średnie z dwóch prób:

| Pomiar | ACK 1.2.0 | ACK 1.3.0 |
| --- | --- | --- |
| Czas obu warstw | 14,704 s | 2,633 s |
| Oczekiwanie bramki błędnej warstwy | 12,306 s | 0,526 s |

W tym scenariuszu oszczędność wyniosła 82,1%. Każdy wariant wykonał identyczne
36 GetMap: dziewięć błędnych obszarów po trzy próby oraz dziewięć poprawnych
po jednej. Błędna warstwa pozostała failed, bez zapisanych PNG i bez pominięcia
BBOX; dobra miała dziewięć PNG. Bajty wszystkich PNG oraz zestawy żądań były
identyczne. Osiem kontroli SQLite zakończyło się `ok`.
SHA-256 połączonych PNG:
`99fffc6dae27cdcad2f7683b0e1daea1d877bc6b35e96574c49d0e24d1a18622`.

To izolowany pomiar kosztu ACK, bez narzutu startu osobnych procesów QGIS,
a nie prognoza 82% przyspieszenia całego eksportu użytkownika. Regresja natywnego
WMS jest w `tests/test_gate_feedback.py`; reguły ciągłego limitu sprawdzają
testy polityki i rzeczywiste wątki koordynatora z kontrolowanymi próbkami RAM.

## Odbiór

Gotowy ZIP sprawdzono w tymczasowym profilu QGIS 3.40.15 na Ubuntu:
natywne wykrywanie, ładowanie, otwarcie okna i wyłączenie wtyczki poprawne.
**185/185 testów z zainstalowanej paczki przeszło w 132,037 s, bez pominięć.**
Obejmują rzeczywisty WMS, izolowane procesy QGIS, PNG i lokalny odczyt,
anulowanie, naprawy, kontynuację, proxy, nową politykę, IPC i diagnostykę.
Testy korzystały z lokalnych gniazd; nie pominięto WMS wskutek ograniczeń sandboxa.

Pierwszy szeroki przebieg źródeł przerwano na starej atrapie, która wyłączała
próbkowanie RAM, zakładając wcześniej przyznane sloty. Produkcja od 1.3.0 czeka
na pierwszy pomiar. Atrapa jawnie przyznaje teraz swój kontrolowany budżet;
5/5 testów odzyskiwania oraz późniejszy pełny odbiór ZIP-a przeszły.
Wcześniejszy test liczby odczytów RAM zaktualizowano dla dwóch odczytów:
fizyczny RAM oraz limit uwzględniający commit. Kontrole zachowania obejmują
rzeczywiste wstrzymanie i odblokowanie nowych startów, nie tylko liczbę wywołań.

Ruff 0.16.6 check/format oraz Flake8/pycodestyle przeszły. Konwencja projektu:
88 znaków, jawne E203 dla zgodności z formatterem, bez wyłączeń E402 w produkcji.
AST: 37 plików Python poprawnych. Brak osobnego typecheckera w repozytorium.
Kontrole odnośników, metadanych i `git diff --check` poprawne.
detect-secrets: zero trafień, weryfikacja sieciowa wyłączona. Bandit: nadal
11 przejrzanych ostrzeżeń (6 medium, 5 low), dotyczących XML, użycia subprocess
i SQL z technicznymi identyfikatorami. Nie dodano wyłączeń ani nowych kategorii;
ocena tych istniejących miejsc jest opisana w [odbiorze 1.0.0](validation-1.0.0.md).

Paczka: `dist/qgis-project-snapshot-1.3.0.zip`, **129 962 bajty, 22 pliki**.
Ponowna budowa dała identyczną sumę SHA-256:
`759a9c42a5ca2d7c6785ecc4007541e50daeefb5a01fd78b73c3e2e76a218a6c`.
Testy, dane projektu i instrukcje agentów nie należą do paczki.
Zaktualizowano metadane, instrukcje PL/EN i katalog 305 tłumaczeń Qt.

## Ograniczenia i następna próba

W dostarczonym logu treść wszystkich 48 962 odpowiedzi była niedostępna;
Content-Length występował tylko dla 32,4%. Nie można wyliczyć rzeczywistego
transferu z zerowego licznika obserwowanych bajtów. Na Windows sygnały timeout
przychodziły po finished: 14 timeoutów jest osobnymi zdarzeniami, chociaż wcześniejsze
network_reply ma qgis_timeout=False. Analiza musi uwzględniać oba typy zdarzeń.
Ta zmiana nie przebudowuje obserwatora sieci.

RSS i commit nie są tym samym kosztem procesu. Ochrona commit ogranicza starty,
ale nie gwarantuje uniknięcia braku pamięci przy nagłym wzroście lub obciążeniu
innymi aplikacjami. Nie podniesiono sufitu 32 / 2 × CPU ani nie zmniejszono rezerw.
Jedna warstwa nadal korzysta z jednego procesu mapowego; liczba map nie jest
liczbą równoczesnych żądań HTTP. Nie deklarujemy maksymalnego wykorzystania
komputera ani serwerów.

Nową paczkę należy instalować po zakończeniu bieżącego eksportu i zrestartować
QGIS. Kolejna próba na Windows powinna używać tego samego obszaru, warstw i zoomów,
z kompletnym poprzednim folderem do kontynuacji. Do analizy pomiarów potrzebne są
diagnostic.jsonl i manifest.json. Dostęp do firmowego MSSQL nadal wymaga próby
w środowisku użytkownika. Publikacji ani zmiany widoczności repozytorium nie wykonano.

Propozycja commitu: `Improve adaptive server retries and Windows memory budgeting`.
