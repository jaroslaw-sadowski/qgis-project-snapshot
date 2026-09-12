# Przygotowanie i publikacja 1.1.0

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
zachowuje zgodność aktualizacji. Numer **1.1.0**, experimental=False,
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

1.1.0 dodaje kontynuację zapisanego archiwum na poziomie warstw: sprawdza i kopiuje
wcześniejsze dane do nowego folderu, a następnie pobiera warstwy brakujące lub
częściowe. Obsługuje wybór folderu po restarcie QGIS, z ograniczeniami opisanymi
w instrukcji. Nie deklarujemy odzyskiwania po awarii ani kontynuacji pojedynczego
niedokończonego kafelka. Zasady automatycznego obciążania serwerów pozostają bez zmian.

## Weryfikacja przed wysłaniem

Polecenia budowy, testów QGIS i kontroli statycznych są w
[development.md](development.md). Wyniki konkretnej paczki i jej SHA-256 są
w [raporcie 1.1.0](validation-1.1.0.md). Test ZIP-a sprawdza również wymagane
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
zgodnie z [instrukcją testów](development.md#kontrole-kontynuacji-archiwum-110).
Test Windows/macOS oraz nietypowego uwierzytelniania wymaga
odpowiedniego stanowiska; lokalne Ubuntu nie zastępuje tych prób.

## Kroki na GitHub i w portalu QGIS

1. Zatwierdź sprawdzone źródła 1.1.0 i udostępnij je w publicznym repozytorium
   wskazanym w metadata.txt. Zalecany tag: v1.1.0. Opublikowane źródła muszą
   odpowiadać przesyłanej paczce, włącznie z instrukcją.
2. Bez logowania sprawdź README, kod, LICENSE i zgłoszenia błędów. Zmiana
   repozytorium z prywatnego na publiczne ujawnia również jego historię.
3. Zaloguj się do plugins.qgis.org i wybierz **Upload a plugin**. Prześlij
   **dist/qgis-project-snapshot-1.1.0.zip**, nie ZIP całego repozytorium.
4. Przeczytaj wyniki skanowania i odpowiedz na ewentualne uwagi moderatorów.
   Lokalnie nie wyłączamy reguł bezpieczeństwa przez .bandit ani baseline sekretów.
5. Po zatwierdzeniu sprawdź instalację 1.1.0 przez Menedżer wtyczek QGIS.

W chwili przygotowania wydania repozytorium jest **prywatne** i publiczne linki
zwracają HTTP 404. Upublicznienie źródeł jest obowiązkowym krokiem przed zgłoszeniem.
W tym etapie nie zmieniano widoczności repozytorium ani nie wysyłano wtyczki.
