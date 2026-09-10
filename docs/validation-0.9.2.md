# Weryfikacja 0.9.2 — 10 września 2026

Poprawka dotyczy odmowy atomowej podmiany plików IPC na Windows. Zachowano
GeoPackage, PNG RGBA ZLEVEL=9, konfigurację proxy i ograniczenia hostów.

- Źródła: **80/80 testów**, 63,641 s, bez pominięć, Ubuntu/QGIS 3.40.
- Nowe testy: winerror 5/32/33, zachowanie kompletnego starego JSON do podmiany,
  ograniczony czas prób, anulowanie, brak ponowień innych błędów systemowych,
  brak podwójnego naliczania kafelka podczas ponowienia telemetrii.
- Integracja WMS: mapę zapisano po trzech wymuszonych odmowach podmiany;
  wynik zawiera kafelki w GeoPackage i zdarzenie ipc_replace_recovered.
- Trwała blokada: koordynator zatrzymuje zadania, mapa i kolejka otrzymują
  etap coordinator, prywatne pliki zostają posprzątane.
- Istniejące testy lokalnego WMS/proxy, odczytu offline, PNG/EPSG:2180,
  anulowania, naprawy kafelków i PL/EN przeszły.
- Ruff check, Ruff format --check oraz git diff --check: poprawne.
- Odbiór ZIP: wykrycie, ładowanie, okno i wyłączenie poprawne; **80/80 testów**
  z kodu paczki, 62,452 s, bez pominięć.
- Paczka: `dist/qgis-project-snapshot-0.9.2.zip`.
- SHA-256: `4086edd05c56e7158665dbae55a294969a760313dbef28af1445eef8a296f111`.

Błędy Windows symulowano na Ubuntu na poziomie operacji podmiany. Nie ustalono,
który proces blokował plik na stanowisku użytkownika. Nie wykonano natywnego
odbioru Windows ani testu firmowych WFS. Trwałe ograniczenia dostępu nie są
obchodzone. Dalszy odbiór: mały obszar, 3–5 widocznych WMS/WMTS i jeden WFS,
zoom 16–17, ten sam komputer, lokalny folder; następnie kontrola offline.
