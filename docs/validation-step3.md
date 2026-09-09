# Krok 3 — zasoby i równoległe przetwarzanie

Stan weryfikacji: 9 września 2026, Ubuntu, QGIS 3.40.15, GDAL 3.12.2.

## Wykonane

- 29 testów integracyjnych QGIS/GDAL: zapis danych i wyglądu, PNG RGBA z
  kompresją 9, EPSG:2180, puste wyniki, ponowienia, anulowanie, relacje,
  symbole, formularze i załączniki.
- Test WMS uruchamia lokalny serwer HTTP. Dla dwóch warstw sprawdza dwa różne
  procesy QGIS oraz rzeczywiście nakładające się żądania do serwera.
- Gotowe rastry są scalane do jednego GeoPackage. Po wyłączeniu serwera i
  przeniesieniu folderu projekt ponownie otwiera się i renderuje lokalną mapę.
- Anulowanie podczas pracy procesów zachowuje ukończony wektor i usuwa
  prywatne pliki procesów.
- Po usunięciu źródłowych plików i przeniesieniu archiwum QGIS renderuje SVG,
  odczytuje formularz UI, pliki pól załączników i załącznik osadzony w QGZ.
- Naprawiono blokowanie sygnału zapisu QGIS, które pomijało relacje w kopii.
- Kontrola składni Pythona i `git diff --check`. Brak osobnej konfiguracji
  lint, typecheck lub build.

## Załączony projekt użytkownika

Odczytano strukturę rzeczywistym QGIS z `FlagDontResolveLayers`, bez otwierania
źródeł firmowych. Kopia zachowała 213 identyfikatorów warstw, 37 węzłów grup
(łącznie z korzeniem drzewa) oraz osadzoną bazę stylów.

W źródle występują: 172 warstwy WMS/WMTS/XYZ, 33 MSSQL, 3 WFS, 3 GDAL,
1 warstwa kafelków wektorowych i 1 ArcGIS MapServer. Ten przegląd sprawdza
strukturę projektu; nie potwierdza pobrania danych z tych usług.

## Pozostały odbiór — krok 4

Aktualizacja: wykonane próby dostępnych źródeł oraz pomiary opisuje
[raport kroku 4](validation-step4.md). MSSQL pozostaje do odbioru w sieci firmowej.

1. Na stanowisku z dostępem do MSSQL i udziałów sieciowych wykonać archiwum
   małego obszaru, następnie reprezentatywnego długiego pasa.
2. Porównać warianty 1, 2 i 4 procesów: czas, zużycie RAM, miejsce tymczasowe,
   błędy usług i kompletność. Na razie potwierdzono współbieżność, nie określony
   współczynnik przyspieszenia na danych produkcyjnych.
3. Przenieść folder na stanowisko bez internetu i sieci firmowej. Sprawdzić
   mapy, zoomy, podpisy, wydruki, formularze i pozycje wskazane w raporcie.
4. Osobno zweryfikować źródła wymagające uwierzytelnienia, niedostępne CRS,
   zależności wyrażeń, kod formularzy i relacje do obiektów spoza obszaru.

Projektów źródłowych, poświadczeń i wygenerowanych danych nie umieszczono w repo.
