# Poprawka po blokadzie skanera QGIS

13 września 2026. Użytkownik przekazał wynik wersji [6293] 1.0.0:
19 uwag Bandit, pozostałe kontrole przeszły. Nie były to 19 potwierdzonych
luk, ale wynik wymagał poprawy zabezpieczeń i rozpatrzenia każdej uwagi.
Wcześniejsze zapewnienie, że lokalne ostrzeżenia nie zablokują publikacji,
było zbyt mocne i zostało skorygowane.

## Rzeczywista kontrola portalu

[Publiczny kod skanera](https://github.com/qgis/QGIS-Plugins-Website/blob/master/qgis-app/plugins/security_scanner.py)
tworzy kontrolę Bandit z kategorią critical. Uruchamia `bandit -r … -f json
--quiet`, z listą aktywnych reguł; nie używa `--ignore-nosec`. Sama tabela
reguł oznaczająca B314/B405/B608/B603 jako warning nie gwarantuje akceptacji.
Flake8 dostaje jawnie wszystkie ścieżki Python i konfigurację z ZIP-a.
Odtworzono oba sposoby uruchamiania, nie tylko ogólny lint źródeł.

## Zmiany

- XML: parser ElementTree zastąpiono zabezpieczonym frontendem defusedxml 0.7.1
  dla QGS, XML warstw, SVG i UI. Encje wewnętrzne, parametryczne i zewnętrzne
  są odrzucane, zwykły DOCTYPE QGIS i wbudowane encje nadal działają.
  Odrzucone SVG/UI nie pozostają w kopii do późniejszego wczytania przez QGIS;
  usuwane są także odwołania do nich, a raport otrzymuje uwagę.
- Wznowienie: przed kanonizacją stylu sprawdzany jest ten sam tekst XML.
  Format fingerprintu nie zmienia się; test porównuje go z poprzednią wersją.
- SQL: wszystkie dynamiczne nazwy tabel SQLite są cytowane przez natywne
  `QgsSqliteUtils.quotedIdentifier`; wartości używają parametrów. MSSQL zachowuje
  poprawne cytowanie nawiasami i jawny filtr SQL istniejącego dostawcy QGIS.
  Nie przekazujemy do SQL treści odpowiedzi usług ani nazw wyświetlanych warstw.
- Proces: absolutna ścieżka interpretera, stały moduł, lista argumentów,
  jawne `shell=False`. Nie rozwijamy symlinków interpretera, aby zachować venv.
  Poświadczenia pozostają wyłącznie w pamięci/stdin.
- Zależność: do paczki dodano wyłącznie potrzebny frontend defusedxml z licencją
  PSF i pochodzeniem. Nie instaluje się niczego w Pythonie użytkownika.
  Usunięto nieużywane funkcje globalnego monkey patchingu; parser zachowuje kod
  upstream. [Pochodzenie i lokalne różnice](../mbtiles_batch_exporter/vendor/README.md).

## Punktowe adnotacje skanera

Nie dodano `.bandit`, globalnego pomijania reguł ani wykluczenia vendor ze skanu
bezpieczeństwa. Wynik **0 Bandit** uwzględnia 20 adnotacji `nosec` dla konkretnych,
przejrzanych zastosowań. Skan `--ignore-nosec` nadal pokazuje te 20 miejsc:

| Reguła | Liczba | Uzasadnienie |
| --- | --- | --- |
| B608 | 11 | Parametry SQL nie obsługują nazw tabel. Nazwy są cytowane, wartości wiązane. Filtr MSSQL jest istniejącym, jawnym SQL użytkownika w QGIS. |
| B405 | 7 | Sześć importów wewnątrz implementacji defusedxml, która zakłada zabezpieczone procedury parsera; jeden import kanonizacji poprzedzonej walidacją defusedxml. |
| B404/B603 | 2 | Własny proces QGIS uruchamiany listą argumentów, bez powłoki; hasła poza argumentami. |

Ostrzeżenia B314 o niezabezpieczonym parsowaniu zostały usunięte przez zmianę
parsera. Nie są wyłączone. Adnotacje mają wąski zakres i uzasadnienia w kodzie.
Kontrolę należy ponowić po zmianie źródła identyfikatorów, filtrów lub argumentów.

Ruff pomija format upstream. `.flake8` opisuje E501/F811 wyłącznie dla plików
ElementTree.py/common.py biblioteki: oryginalne formatowanie i wzajemnie
wykluczające się importy Python 2/3. Wariant z jawnymi bezwzględnymi ścieżkami
przeszedł zarówno przy limicie 120 portalu, jak i 88 projektu.

## Wyniki odbioru

- QGIS 3.40.15 / Qt5: **236/236**, 185,951 s, bez pominięć, kod 0.
- QGIS 4.0.3 / Qt 6.10.2: **236/236**, 192,549 s, bez pominięć, kod 0.
- W obu przypadkach zainstalowany ZIP w tymczasowym profilu, rzeczywiste lokalne
  WMS/WFS/proxy, wektory, piksele/zoomy, GeoPackage, procesy, awarie i wznowienie.
- Pięć nowych testów bezpieczeństwa: encje XML w UTF-8/UTF-16, poprawny DOCTYPE,
  brak niebezpiecznego SVG w wyniku, zgodność fingerprintów oraz zapis do tabeli
  o nazwie zawierającej cudzysłów i próbę SQL bez naruszenia innej tabeli.
- Bandit 1.9.4: 0 po opisanych adnotacjach, cały ZIP wraz z vendor.
- detect-secrets 1.5.0: 0, cały ZIP, bez sieciowej weryfikacji sekretów.
- Ruff/format, Flake8 (także wywołanie jak portal), składnia Python 3.10: OK.
- Po pełnym odbiorze dopracowano wyłącznie komentarz i konfigurację Flake8;
  kod działania w finalnej paczce jest identyczny ze sprawdzonym.

Przygotowany ZIP 1.0.0: **150 716 bajtów, 29 plików**, SHA-256:
`bc85414dd7abdf605107cf94ae971b63d6e415a354630a0442a41d1518e6aa68`.

## Ponowne zgłoszenie

[Formularz portalu](https://github.com/qgis/QGIS-Plugins-Website/blob/master/qgis-app/plugins/forms.py)
odrzuca już istniejący numer. Ponowne uruchomienie skanu starego wpisu nie zmienia
jego blokady. Użytkownik zatwierdził wydanie 1.0.1 i ponowną kontrolę wymagań portalu.
Powyższy ZIP 1.0.0 był paczką roboczą naprawy; nie jest paczką do ponownego
zgłoszenia. Finalny ZIP, odtworzenie skanera i wydanie: [release-1.0.1.md](release-1.0.1.md).
Lokalne wyniki nie są decyzją moderatora ani wynikiem ponownego skanu portalu.
Propozycja commitu: `Harden XML parsing and resolve reviewed security findings`.
