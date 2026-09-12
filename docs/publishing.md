# Przygotowanie i publikacja 1.4.1

Ten dokument jest dla opiekuna wydania. Instrukcja użytkownika znajduje się
w [README](../README.md) i [przewodniku PL/EN](team-guide.md).

## Wymagania katalogu

Stan sprawdzony 10 września 2026 na podstawie aktualnych stron QGIS:

- [Publikacja](https://plugins.qgis.org/docs/publish): opis po angielsku,
  dokumentacja, licencja zgodna z GPL, publiczne źródła i działające odnośniki.
  Aktualny limit paczki to 25 MB; starsza strona `/publish/` podawała 20 MB.
- [Metadane i struktura](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/plugins/plugins.html):
  poprawne metadata.txt w UTF-8, punkt wejścia classFactory i komplet plików wtyczki.
- [Skanowanie](https://plugins.qgis.org/docs/security-scanning): portal sprawdza
  bezpieczeństwo każdej przesłanej wersji; wynik lokalny nie zastępuje jego kontroli.
- [Zatwierdzanie](https://plugins.qgis.org/docs/approval): nowe zgłoszenie podlega
  przeglądowi opiekunów. Przygotowany ZIP nie oznacza opublikowanej wtyczki.

## Zawartość wydania

Nazwa: **QGIS Project Snapshot**. Identyfikator Pythona **mbtiles_batch_exporter**
zachowuje zgodność aktualizacji. Numer **1.4.1**, experimental=False,
deprecated=False. Obsługiwany zakres: QGIS 3.40–3.x z Qt5/PyQt5 i GDAL >=3.7;
nie deklarujemy QGIS 4/Qt6. Wtyczka nie instaluje dodatkowych bibliotek.

Metadane podają autora i zatwierdzony przez niego adres kontaktowy, opis funkcji,
wymagania, ograniczenia, angielskie tagi, historię wersji i link do licencji.
GPL-2.0-only dotyczy kodu wtyczki oraz dostarczonych własnych zasobów.
Nie daje praw do danych użytkownika lub usług zewnętrznych. README, instrukcja
i opis wtyczki wyjaśniają obowiązek przestrzegania licencji warstw oraz udział AI.

ZIP zawiera jeden katalog, wyłącznie potrzebne moduły, ikony SVG, metadane,
README, LICENSE i instrukcję. Qt używa pliku tłumaczeń en.qm; źródłowy en.ts jest
również dołączony. Nie ma wykonywalnych binariów, zależności, testów, cache,
danych użytkownika, historii Git ani instrukcji agentów. Prawa plików: 0644.
Akcja całego projektu pozostaje w menu Wtyczki i na pasku; opcjonalne
category=Raster usunięto, aby nie wskazywać innego menu.

Zalecenie sprawdzenia podobnych narzędzi uwzględniono: istnieje
[Project Packager](https://plugins.qgis.org/plugins/ProjectPackager/).
Ta wtyczka dodatkowo pobiera usługi mapowe dla wybranego obszaru i poziomów
szczegółowości, dobiera równoległość oraz raportuje brakujące wyniki.
Nie sugeruje zastępowania wszystkich narzędzi pakujących projekty.

Od 1.4.0 wtyczka zachowuje postęp map także po nieoczekiwanym zamknięciu QGIS.
Kontynuacja kopiuje wcześniejsze dane do nowego folderu, zachowuje ukończone warstwy
oraz poprawne i puste kafelki. Tylko brakujące kafelki dostają nowy budżet prób;
nieukończony wektor zaczyna swoją warstwę od początku. Okno podpowiada ostatni
folder wznowienia. Cały poprzedni folder musi pozostać dostępny; nie deklarujemy
odzyskania plików uszkodzonych przez nośnik lub awarię zasilania.
GeoTIFF-y otrzymują natywne piramidy, a mapy udostępniają również poprawnie puste
poziomy bez zastępowania osobno pobranych zoomów przeskalowanym obrazem.
Sprawdzenie pustych wektorów obejmuje oczekujące błędy WFS, odświeżenie jego cache
poza trybem edycji i dodatkową kontrolę dostępu przy zerowym MSSQL. Poprawny brak
obiektów nadal jest prawidłowym wynikiem; firmowy MSSQL wymaga osobnego odbioru.

Od 1.2.0 dostępne są lokalne okresowe pomiary wydajności: CPU, pamięć, operacje I/O,
budżety i kolejki procesów, etapy pracy oraz obserwowane odpowiedzi sieciowe.
Log zawiera też plan eksportu i końcowe podsumowania warstw bez ich nazw oraz
źródłowych adresów i współrzędnych. Zwykle wystarcza do typowej analizy czasu
pobierania; nie zastępuje manifestu ani danych przy odbiorze kompletności.
Nie jest automatycznie wysyłany i nie wymaga nowych pakietów. Sam pomiar nie
gwarantuje osiągnięcia maksimum komputera lub serwera. Szczegóły jego zakresu
opisuje dokumentacja.

1.3.0 zmienia dostosowanie obciążenia: po zdrowym okresie ponawia próbę wyższego
limitu hosta, wycofuje nieskuteczny wzrost i reaguje na utrzymujący się spadek
szybkości. Kolejne nieudane próby wydłużają stabilizację. Windows dodatkowo
uwzględnia dostępny commit przy przydzielaniu nowych procesów. Zwykłe błędy WMS
nie czekają na osobny ACK każdego zdarzenia; zdarzenia sterujące przeciążeniem
i powrotem hosta nadal wymagają potwierdzenia. Zachowano rezerwę 768 MiB,
sufit CPU/32, Retry-After, bezstratny PNG i zasady kontynuacji. Brak nowych
zależności. Kontrole kodu nie stanowią pomiaru przyspieszenia na zewnętrznych
usługach ani pełnego odbioru Windows.

1.4.1 oznacza potwierdzone puste wektory w kopii projektu końcówką
`_nie-bylo-obiketow-w-zasiegu`, bez zmiany nazw oryginału. Manifest, log i zachowany
postęp są w `diagnostyka/`. Projekt, raport i dane pozostają łatwo dostępne;
kontynuacja obsługuje również poprzedni układ folderu. Instrukcja przypomina,
że do przenoszenia i wznowienia potrzebne jest całe archiwum.

## Weryfikacja przed wysłaniem

Polecenia budowy, testów QGIS i kontroli statycznych są w
[development.md](development.md). Wyniki konkretnej paczki i jej SHA-256 są
w [raporcie 1.4.1](validation-1.4.1.md). Test ZIP-a sprawdza również wymagane
metadane, ścieżki, prawa i dozwolone pliki. Testy generują własne niewielkie dane
oraz lokalne WMS/proxy; nie wymagają projektu ani dostępu do usług autora.

Krótka próba ręczna bez zewnętrznych danych:

1. W nowym projekcie QGIS utwórz tymczasową warstwę punktową i dodaj kilka punktów.
2. Włącz edycję i dodaj atrybut tekstowy. Pozostaw ostatnią zmianę niezapisaną.
3. Uruchom archiwizację dla widoku obejmującego punkty i wskaż pusty folder docelowy.
4. Sprawdź raport, otwórz kopię projektu i porównaj punkty oraz atrybuty.
   Źródłowa warstwa powinna nadal zachować niezapisane edycje.

Osobno sprawdź usługę, której warunki pozwalają na pobieranie offline, i porównaj
obraz z oryginałem. Sprawdź też kontynuację po świadomym anulowaniu i restarcie,
zgodnie z [instrukcją testów 1.4.0](development.md#kontrole-postępu-kafelków-i-piramid-140).
Po zakończeniu sprawdź też [nowe pomiary diagnostyczne](development.md#kontrole-diagnostyki-wydajności-120),
w szczególności obecność próbek głównego procesu i procesów map w końcowym logu.
Zachowanie nowych prób wzrostu i ograniczenia pamięci sprawdź zgodnie z
[kontrolami adaptacji 1.3.0](development.md#kontrole-adaptacji-i-budżetu-windows-130).
Test Windows/macOS oraz nietypowego uwierzytelniania wymaga
odpowiedniego stanowiska; lokalne Ubuntu nie zastępuje tych prób.

## Kroki na GitHub i w portalu QGIS

1. Zatwierdź sprawdzone źródła 1.4.1 i udostępnij je w publicznym repozytorium
   wskazanym w metadata.txt. Zalecany tag: v1.4.1. Opublikowane źródła muszą
   odpowiadać przesyłanej paczce, włącznie z instrukcją.
2. Bez logowania sprawdź README, kod, LICENSE i zgłoszenia błędów. Zmiana
   repozytorium z prywatnego na publiczne ujawnia również jego historię.
3. Zaloguj się do plugins.qgis.org i wybierz **Upload a plugin**. Prześlij
   **dist/qgis-project-snapshot-1.4.1.zip**, nie ZIP całego repozytorium.
4. Przeczytaj wyniki skanowania i odpowiedz na ewentualne uwagi moderatorów.
   Lokalnie nie wyłączamy reguł bezpieczeństwa przez .bandit ani baseline sekretów.
5. Po zatwierdzeniu sprawdź instalację 1.4.1 przez Menedżer wtyczek QGIS.

W chwili przygotowania wydania repozytorium jest **prywatne** i publiczne linki
zwracają HTTP 404. Upublicznienie źródeł jest obowiązkowym krokiem przed zgłoszeniem.
W tym etapie nie zmieniano widoczności repozytorium ani nie wysyłano wtyczki.
