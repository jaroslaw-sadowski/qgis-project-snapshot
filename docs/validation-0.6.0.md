# Wersja 0.6.0 — czytelny postęp i nazwa wtyczki

9 września 2026. QGIS 3.40.15, Ubuntu.

## Zmiany

- Nazwa widoczna: `qgis-project-snapshot`. Menu Wtyczki zawiera podmenu tej
  nazwy, z archiwizacją jako pierwszą akcją i eksportem MBTiles jako drugą.
  Techniczny identyfikator instalacji pozostaje bez zmian dla zgodności aktualizacji.
- Pasek liczy zakończone warstwy; kolumna Stan pokazuje kolejkę, bieżącą pracę
  i wynik. Wyświetlane są także czas, aktywność procesów i dziennik.
- Procesy pomocnicze przekazują komunikaty o otwieraniu źródła, zoomach,
  fragmentach i oczekiwaniu. Główny proces opisuje zapis, próby zastępcze,
  kontrolę danych, sumy kontrolne i przygotowanie raportu.
- Ostatnie 2000 komunikatów można skopiować. Powtórzenia nie wypełniają dziennika.
  Licznik czasu zatrzymuje się po pracy, przed oczekiwaniem na zamknięcie komunikatu.
- Instrukcje w oknach i przewodniku skrócono. Pola, przyciski oraz stany mają
  podpowiedzi po najechaniu; dotyczy to również eksportera MBTiles.

## Odbiór

Wszystkie **33 testy przeszły z gotowej paczki**, bez pomijania WMS. Nowe
testy obejmują prawdziwy eksport z okna, etapy i wynik, błąd bez fałszywego
sukcesu, anulowanie, kopiowanie dziennika, brak powtórzeń i zachowanie końcowego
stanu warstwy. Test równoległego WMS sprawdza odczyt komunikatów o fragmentach
lub zoomach podczas pracy. Kontrola instalacji sprawdza nazwę, menu i oba okna.

Obejrzano zrzut natywnego okna Qt/QGIS w trybie offscreen. Skontrolowano też
składnię Pythona, odnośniki dokumentacji i `git diff --check`.

Paczka: `dist/qgis-project-snapshot-0.6.0.zip`.
SHA-256:

```text
e77aa32f3605df001024f307ee346036bd19d46ef73ecd4a3fd756683a8198d6
```

Nie powtarzano benchmarku ani odbioru usług publicznych z kroku 4. Pozostają
testy MSSQL i danych firmowych na komputerze służbowym. Synchroniczny odczyt
w głównym QGIS nadal może blokować odświeżanie okna; widoczna jest ostatnia
wykonywana czynność. Nie dodano pozornej prognozy czasu zakończenia.
