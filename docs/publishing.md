# Pierwsze oficjalne wydanie 1.0.0

Instrukcja opiekuna wydania. Krótki opis użytkownika: [README](../README.md).
Wyniki i suma paczki: [odbiór 1.0.0](release-1.0.0.md).

## Wymagania katalogu

Sprawdzono 13 września 2026:

- [Publikacja](https://plugins.qgis.org/docs/publish/): opis po angielsku,
  dokumentacja, publiczne źródła, licencja zgodna z GPL, działające odnośniki
  i paczka do 25 MB.
- [Migracja QGIS 4](https://plugins.qgis.org/docs/migrate-qgis4): zakres
  `qgisMinimumVersion=3.40`, `qgisMaximumVersion=4.99`. Pole `supportsQt6`
  zostało wycofane. Kontroler Qt6 uzupełnia rzeczywiste testy obu runtime'ów.
- [Reguły skanowania](https://plugins.qgis.org/docs/security-scanning/rules):
  lokalne kontrole nie zastępują skanu przesłanego ZIP-a. Ostrzeżenia Bandit
  opisano w raporcie, bez globalnego wyłączania reguł lub baseline sekretów.
- [Zatwierdzanie](https://plugins.qgis.org/docs/approval): pierwsza publikacja
  wymaga przeglądu opiekunów katalogu.

Nazwa to **QGIS Project Snapshot**, techniczny identyfikator pozostaje
**mbtiles_batch_exporter**, aby zastąpić instalacje rozwojowe. `experimental=False`,
`deprecated=False`, GPL-2.0-only, kontakt autora zatwierdzony. Własna ikona SVG,
menu Wtyczki i pasek narzędzi; kod nie instaluje dodatkowych pakietów.

Podobne narzędzie: [Project Packager](https://plugins.qgis.org/plugins/ProjectPackager/).
Snapshot dodatkowo pobiera mapy dla obszaru i zoomów, automatycznie dobiera
równoległość oraz zachowuje postęp i raport braków.

ZIP zawiera jeden katalog: kod Python, SVG, metadane, krótkie README, instrukcję,
GPL, tłumaczenia `.qm` wraz ze źródłem `.ts` i jawną konfigurację `.flake8`.
Bez danych użytkownika, środowisk testowych, historii Git i instrukcji agentów.
Prawa 0644, powtarzalna budowa. `.flake8` ustala konwencję 88 znaków/E203;
nie jest wyłączeniem kontroli bezpieczeństwa.

## Numeracja i próba ręczna

1.0.0 jest pierwszym oficjalnym wydaniem. Wcześniejsze 1.1–1.4 były numerami
rozwojowymi, zachowanymi w historycznych raportach. QGIS nie uzna 1.0.0 za
aktualizację nowszego numeru: testerzy muszą ręcznie zainstalować oficjalny ZIP
przez Menedżer wtyczek i ponownie uruchomić QGIS. Zachować całe foldery archiwów.

Przed wysłaniem porównaj wynik offline ze źródłem, dla widoku i wybranej warstwy
poligonowej. Sprawdź niezapisane edycje, style, atrybuty i wznowienie po anulowaniu.
Test użytkownika z obszarem z warstwy zakończono: [audyt](audit-polygon-1.4.3.md).
Maska i zapis prawidłowe, dwa WMS wymagają ponowienia braków. Automatyczne testy
obejmują poligony, zaznaczenie, otwory, transformację CRS i maskowanie kafelków.
Nowa paczka Qt6 wymaga także odbioru na stanowisku Windows/macOS, jeśli są używane;
lokalny Ubuntu nie sprawdza firmowego VPN ani wszystkich metod uwierzytelniania.

## Kroki publikacji

1. Zatwierdź sprawdzone źródła i udostępnij je publicznie pod adresami metadanych.
   Wykonano 13 września 2026: repozytorium publiczne, odnośniki bez logowania
   zwracają HTTP 200. Przed upublicznieniem sprawdzono historię i sekrety.
2. Sprawdź bez logowania README, kod, GPL i zgłoszenia błędów. Źródła muszą
   odpowiadać paczce, włącznie z instrukcją i konfiguracją stylu.
3. Utwórz tag `v1.0.0` i GitHub Release; załącz
   `dist/qgis-project-snapshot-1.0.0.zip` oraz `.zip.sha256`.
   Krótki tekst wydania jest w [raporcie](release-1.0.0.md#release-notes).
   Nie nadpisuj istniejącego publicznego tagu; najpierw sprawdź jego obecność.
4. W plugins.qgis.org wybierz **Upload a plugin** i wyślij ZIP wtyczki,
   nie archiwum całego repozytorium. Przeczytaj wynik skanowania i uwagi opiekunów.
5. Po zatwierdzeniu sprawdź instalację przez Menedżer wtyczek QGIS 3 i QGIS 4.

Po audycie poligonu upubliczniono repozytorium i opublikowano
[GitHub Release v1.0.0](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/releases/tag/v1.0.0).
ZIP pobrany bez logowania zgadza się z lokalnym i opublikowaną sumą SHA-256.
Aktualny stan wykonania: [PROJECT_STATE.md](PROJECT_STATE.md).
Zgłoszenie do plugins.qgis.org pozostaje odrębnym krokiem.

## Ponowne zgłoszenie po blokadzie 1.0.0

Użytkownik zgłosił paczkę, ale kontrola Bandit zablokowała wersję [6293].
Naprawa i wyniki: [security-scan-fix.md](security-scan-fix.md). Nie wystarczy
ponowny skan starego wpisu: portal wymaga nowego zgłoszenia, a formularz odrzuca
powtórzony numer wersji. Wymagany jest nowy numer (proponowane 1.0.1) albo
uzgodnienie usunięcia zablokowanej 1.0.0 z opiekunem portalu, jeśli autor chce
zachować numer. Nie deklaruj akceptacji katalogu na podstawie samego lokalnego
wyniku lub GitHub Release. Poprawionej paczki agent nie zgłasza samodzielnie.
