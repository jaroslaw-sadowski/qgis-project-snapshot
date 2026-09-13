# Odbiór pierwszego oficjalnego wydania 1.0.0

Data: 13 września 2026. Użytkownik zatwierdził publikację GitHub Release
i upublicznienie repozytorium po audycie poligonu; profil użytkownika pozostaje
niezmieniony. Historyczny `validation-1.0.0.md` opisuje wcześniejszy build
rozwojowy; poniższa suma identyfikuje wydanie oficjalne.

## Paczka

`dist/qgis-project-snapshot-1.0.0.zip`: **144 005 bajtów, 23 pliki**.
Jeden katalog `mbtiles_batch_exporter`, prawa 0644, wymagane metadane, GPL,
README, instrukcja, tłumaczenia i `.flake8`; bez danych oraz środowisk testowych.
Powtórna budowa dała identyczny ZIP. Porównano wszystkie pliki paczki ze źródłami;
kontrola odnośników lokalnych i `git diff --check` przeszła.

SHA-256:

```text
74a756dffe1e992455183c588dc7d3d29d22f1fb8d874840feb47e20a3e66bd1
```

## Wskazówka o długim pobieraniu

Dopisano krótką informację EN/PL w README i metadanych oraz na początku
podpowiedzi licznika kafelków: wiele warstw, duży obszar i zoom powyżej 17
mogą oznaczać pobieranie od kilku godzin do kilku dni. Natywna podpowiedź Qt,
bez dodatkowego dialogu, zmian obliczeń, pobierania lub numeru 1.0.0.
Przebudowano katalog QM: 337 gotowych tłumaczeń. Zmienione pliki paczki to tylko
README.txt, metadata.txt, archive_dialog.py i katalogi tłumaczeń en.ts/en.qm.
Gotowa paczka: 15/15 testów Qt5 (1,628 s) i Qt6 (1,503 s), kody 0; kompletność
i odczyt tłumaczeń oraz załadowanie/okno wtyczki OK. Ruff/format, Flake8 i diff OK.
Propozycja commitu: `Explain download duration for large high-zoom archives`.

## Korekta opisów i menu bez zmiany numeru

Na życzenie użytkownika pozostaje 1.0.0. README i metadane przeredagowano
na bardziej naturalny język, zachowując zakres. Akcja „QGIS Project Snapshot”
trafia bezpośrednio do menu Wtyczki przez natywne API QGIS/Qt. Zaktualizowano
ścieżkę w instrukcji. Bez zmian pobierania, zapisu, obciążenia i wznowienia.
Porównanie paczek wykazało różnice tylko w plugin.py, metadata.txt, README.txt
i INSTRUKCJA.md; w metadanych zmieniono tylko description/about.

Bieżący ZIP przeszedł po 15 testów w Qt5 (1,424 s) i Qt6 (1,328 s), oba procesy
z kodem 0. Odbiór obejmuje rzeczywisty QMenu, uruchomienie okna oraz cykl
wyłączenia i włączenia bez pozostawiania akcji lub usuwania cudzych pozycji.
Ruff/format, Flake8 (--jobs 1 z powodu ograniczenia gniazd sandboxa), składnia
Python 3.10 i diff OK. Poniższe 231 testów na runtime opisuje bazowy odbiór
przed tą korektą; nie powtarzano pełnego zestawu bez zmian algorytmów.
Bieżącą sumę podano powyżej. Korekta zastępuje paczkę istniejącego wydania;
propozycja commitu: `Refine release wording and simplify Plugins menu`.

## Aktualizacja tagów przed publikacją

Dodano 17 tagów angielskich, następnie 13 polskich odpowiedników; nazwy
standardów WMS/WMTS/WFS/XYZ pozostają jednokrotne. Zapis rozdzielony przecinkami
i frazy ze spacjami odpowiadają [formatowi metadanych QGIS](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/plugins/plugins.html).
Zweryfikowano UTF-8, unikalność i kolejność tagów, odczyt metadanych oraz ZIP.
Porównanie z paczką po pełnym odbiorze wykazało zmianę wyłącznie pola `tags`
w metadata.txt; kod i pozostałe pliki są identyczne. Wyniki 231 testów na runtime
dotyczą tego samego kodu przed zmianą tagów; nie powtarzano pełnych testów.
Zaktualizowano powyższą wielkość i SHA-256. Propozycja commitu dla tej korekty:
`Add English and Polish discovery tags for official release`.

## Zmiana i uzasadnienie

Numer 1.0.0 rozpoczyna oficjalną numerację. Krótkie opisy EN→PL wyjaśniają
zastosowanie, instalację, lokalne przetwarzanie, automatyczną równoległość,
licencje źródeł i AI/vibe coding. Usługi nadal otrzymują parametry niezbędne
w zapytaniach; nie obiecuje się pracy bez komunikacji sieciowej podczas pobierania.

Zgodnie z kolejnością Ponytail najpierw sprawdzono istniejący kod i natywne API.
Zmieniono import QAction, enumy, `exec()` i lokalny odczyt dostępności interfejsów
sieciowych. Bez zależności produkcyjnych, własnego frameworka zgodności i zmiany
sterowania obciążeniem. Dodatkowe zmiany wynikają z rzeczywistych regresji Qt6:

- Nowy format właściwości XML projektu wymaga osobnej ścieżki odczytu; wynik
  ma względne źródła i daje się przenieść. Makra są usuwane z kopii i plików
  procesów pomocniczych; oryginał pozostaje niezmieniony.
- Nowszy QGIS zmienił klucze proxy. Wykrycie natywnego węzła ustawień pozwala
  przenieść konfigurację z obu wersji, zachowując hasła wyłącznie w pamięci/stdin.
- Diagnostyka zapisuje liczbowy kod błędu także z enumów Qt6.

## Weryfikacja

| Kontrola | Wynik |
|---|---|
| QGIS 3.40.15, Qt5, test zainstalowanego ZIP-a | 231/231, 170,064 s, bez pominięć, kod procesu 0 |
| QGIS 4.0.3, Qt 6.10.2, test zainstalowanego ZIP-a | 231/231, 171,448 s, bez pominięć, kod procesu 0 |
| Ruff 0.16.6 i formatowanie | OK |
| Flake8 7.3.0 / pycodestyle | OK; jawny limit 88, E203; E402 tylko w trzech plikach startujących testy QGIS |
| Składnia Python 3.10 | 44 pliki, OK |
| Skan sekretów 1.5.0 | 0 trafień w kodzie i rozpakowanym ZIP-ie, bez weryfikacji sieciowej |
| Bandit 1.9.4 | 20 przejrzanych ostrzeżeń: 15 medium, 5 low, 0 high |
| Oficjalny kontroler Qt6 | 0 zmian wymaganych w kodzie źródłowym i rozpakowanym ZIP-ie |

Oba runtime'y: Ubuntu, Python 3.14.4, GDAL 3.12.2. QGIS 4 rozpakowany z oficjalnych
pakietów, w izolowanym środowisku, bez zastępowania QGIS 3. Test ZIP-a sprawdza
natywne wykrywanie, uruchomienie, okno i wyłączenie wtyczki oraz pochodzenie
załadowanych modułów i procesów. Lokalny WMS/WFS/proxy był dostępny.

Zakres: prawdziwe wektory i atrybuty, puste odczyty i błędy WFS, maski poligonów
z otworami i zmianą CRS, style, relacje, zasoby, piksele PNG i piramidy, integralność
GeoPackage, limity serwerów, HTTP 429/503/407, proxy z logowaniem, anulowanie,
SIGKILL i kontynuacja w nowym procesie, nazwy oraz tłumaczenia PL/EN.

Program odbioru teraz zamyka samodzielny QGIS przez `exitQgis()`. Debugger
wykazał awarię odroczonego zamykania OGR po końcu testów, gdy wcześniej pomijano
tę procedurę. Nieoczekiwane ostrzeżenia okna powodują błąd testu zamiast czekania
na kliknięcie. Odbiór wymaga również kodu procesu 0, nie samego komunikatu unittest.

Użyto skryptu QGIS wskazanego przez [pyqgis4-checker](https://github.com/qgis/pyqgis4-checker),
w trybie `--dry_run`, ze sprawdzeniem treści wyniku (sam kod 0 nie wystarcza).
SHA-256 skryptu: `c6734b909bf29d06c1d173ed03f03e4ee87abf29308932a3f0b1833288f837de`.
Współistniejący systemowy PyQt5 powoduje ostrzeżenie startowe kontrolera;
sprawdzenie wykonano z rzeczywistym QGIS 4/PyQt6. Zakres 3.40–4.99 jest zgodny
z [instrukcją migracji QGIS](https://plugins.qgis.org/docs/migrate-qgis4).

## Ostrzeżenia bezpieczeństwa i granice odbioru

Bandit: B608 (11) dotyczy nazw tabel pochodzących z kontrolowanego identyfikatora
lub cytowania identyfikatorów QGIS oraz istniejącego filtra MSSQL. Wartości danych
są parametryzowane. B314 (4) i B405 (3) dotyczą XML projektu i zasobów parsowanych
przez standardowy ElementTree. B603/B404 dotyczą uruchamiania własnego procesu
Pythona listą argumentów, bez powłoki. Przejrzano miejsca użycia; nie ukryto trafień.
Według [aktualnych reguł portalu](https://plugins.qgis.org/docs/security-scanning/rules)
są to ostrzeżenia/informacje, nie reguły Critical. Plik `.qm` to katalog tłumaczeń
Qt, ze źródłem `.ts`, nie wykonywalna biblioteka.

`.flake8` jest [obsługiwanym plikiem konfiguracji portalu](https://plugins.qgis.org/docs/security-scanning/config-files).
Nie dodano `.bandit`, wyłączeń bezpieczeństwa ani baseline sekretów. Wynik lokalny
nie gwarantuje przyszłego wyniku skanera lub decyzji opiekunów QGIS.

Otrzymany [test poligonu na Windows, wersja rozwojowa 1.4.3](audit-polygon-1.4.3.md)
potwierdził zgodność maski i poprawny zapis. Pozostają 52 jawne braki w dwóch WMS;
nie stwierdzono błędu kodu blokującego pierwsze wydanie. Nie wykonano natywnego
odbioru nowego Qt6 na Windows/macOS ani prób firmowego VPN/MSSQL na Ubuntu.
Wznowienie sprawdzono w obrębie każdego runtime'u; przejście z Qt5 do Qt6 w trakcie
jednego archiwum wymaga osobnej próby. Kontrola źródeł/stylów nadal odrzuca
niezgodny projekt. Testy nie są obietnicą maksymalnej przepustowości lub odporności
na fizyczną awarię nośnika.

13 września 2026 upubliczniono repozytorium i opublikowano
[GitHub Release v1.0.0](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/releases/tag/v1.0.0),
pierwotny tag wskazywał commit `1c84110aeb54858a2dff05b32f2bc65dd5e60463`.
Pierwotna paczka miała SHA-256:
`b6e8d1f17e0b27d313b45d68e99504dd59d68a4b4fd5a98a888408e2fc64ea37`. Korekta menu/opisów zastępuje ją w tym samym wydaniu.
Po korekcie menu tag v1.0.0 wskazywał `fd134c45ae7dc615a7decb01b2f8c1ed460f305a`.
Oba załączniki i suma w opisie wydania zostały podmienione; ponowne pobranie
bez logowania potwierdziło zgodność ZIP/SHA z lokalnymi plikami oraz wszystkich
plików paczki ze źródłem pod tagiem. Wydanie nadal jest stabilne i publiczne.
Sprawdzono dostęp do źródeł i załączników bez logowania (HTTP 200), zgodność
pobranego ZIP-a z lokalnym i SHA-256. Historia oraz bieżące źródła bez trafień
sekretów. Spełniono wymóg publicznych źródeł z
[zasad publikacji](https://plugins.qgis.org/docs/publish/).
Nie zgłoszono jeszcze paczki do plugins.qgis.org. Kroki: [publishing.md](publishing.md).
Propozycja commitu: `Prepare official 1.0.0 release with QGIS 4 compatibility`.

## Release notes

**English:** First official release of QGIS Project Snapshot. Save projects for
offline use with vector data, lossless maps and styles. Automatic parallel
downloads, persistent recovery and English/Polish output. QGIS 3.40+ and QGIS 4
support. Respect the licenses of downloaded services. Developed with AI/vibe
coding and tested; see the release audit for scope and limitations.

**Polski:** Pierwsze oficjalne wydanie QGIS Project Snapshot. Zapis projektów
do pracy offline: wektory, bezstratne mapy i style. Automatyczne pobieranie
równoległe, trwałe wznowienie i nazwy PL/EN. Obsługa QGIS 3.40+ oraz QGIS 4.
Przestrzegaj licencji pobieranych usług. Wykorzystano AI/vibe coding i wykonano
testy; zakres i ograniczenia opisuje audyt wydania.

Testerzy wcześniejszych wersji rozwojowych 1.4.x: zainstalujcie ZIP 1.0.0 ręcznie
i uruchomcie QGIS ponownie. Niższy numer nie będzie automatyczną aktualizacją.
