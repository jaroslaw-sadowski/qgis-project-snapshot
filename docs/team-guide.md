# qgis-project-snapshot — krótka instrukcja

## Instalacja

1. W QGIS otwórz **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Wskaż `qgis-project-snapshot-0.7.2.zip` i włącz **qgis-project-snapshot**.
   Jeśli aktualizujesz poprzednią wersję, zakończ eksport i uruchom ponownie QGIS.
3. Wybierz **Wtyczki → qgis-project-snapshot → Archiwizuj projekt…**.

Wymagane: QGIS 3.40 z PyQt5 oraz GDAL 3.7 lub nowszy. Sprawdzono Ubuntu;
pełny projekt z MSSQL trzeba jeszcze odebrać na komputerze służbowym.

Język opcji QGIS wybiera polski (`pl`) lub angielski (wszystkie `en`, np. brytyjski
i amerykański). Bez własnego języka QGIS używany jest język systemu; inne języki
mają angielski interfejs. Po zmianie ustawień otwórz ponownie okno wtyczki.

## Utworzenie archiwum

1. Otwórz projekt z dostępem do jego danych. Pierwszą próbę zrób na małym obszarze.
2. Wybierz folder, obszar i warstwy. Dla pasa inwestycji użyj poligonów obszaru.
3. Na początek pozostaw zbliżenia 13–17. Kliknij **Dobierz do komputera i zaznaczonych warstw**.
   Przy szybkim łączu możesz zwiększyć **Zadania na serwer** i ponownie użyć doboru.
4. Kliknij **Utwórz archiwum**. Szczegóły każdej opcji przeczytasz po najechaniu kursorem.

Pasek pokazuje liczbę zakończonych warstw. Kolumna **Stan** i **dziennik** opisują
pobieranie map, fragmenty, ponowienia, zapis i kontrolę plików. **Kopiuj dziennik**
pozwala zachować komunikaty. Niekiedy źródło długo odpowiada — ostatnia czynność
pozostaje wtedy widoczna. **Przerwij** zachowuje ukończone, scalone warstwy.

## Sprawdzenie wyniku

1. Otwórz raport: sprawdź błędy, puste obrazy i elementy wymagające kontroli.
2. Przenieś **cały folder archiwum**. Zamknij projekt źródłowy, odłącz internet
   i sieć firmową, a następnie otwórz archiwalny `.qgz`.
3. Porównaj mapę, atrybuty, załączniki i używane formularze oraz wydruki.
   Po małej próbie sprawdź reprezentatywny długi pas i dopiero potem cały obszar.

Oryginalny projekt nie jest zastępowany. Archiwum może być częściowe; sam
poprawny zapis nie potwierdza wszystkich zależności. Do odczytu lokalnej kopii
nasza wtyczka nie jest potrzebna. Daty raportu oznaczają czas pobierania warstw.

Przy problemie zanotuj wersję QGIS/systemu, warstwę i opcje eksportu; zachowaj
raport oraz dziennik. Dane i poświadczenia firmowe pozostaw w środowisku służbowym.

## Problemy i ponowna próba

Po eksporcie przewijane pole pokazuje nazwy problematycznych warstw i przyczyny.
Błędne, przerwane, puste i częściowe obrazy są automatycznie zaznaczane;
poprawnie zapisane warstwy są odznaczane. Poprawnie odczytany wektor bez obiektów
jest sukcesem, nie błędem pobierania.

Przycisk **Ponów tylko niezapisane i niepełne warstwy** uruchamia eksport zaznaczonych
warstw. Powstaje osobny folder, bez automatycznego łączenia z poprzednim wynikiem.
**Zachowaj oba foldery.** Szczegółowy raport `raport.html` zawiera też diagnostykę
z `manifest.json`, w tym próby zastępcze i zapisane przykłady błędów kafelków.

## Dobór równoległości

Wtyczka odczytuje dostępne CPU, wolny RAM (Linux i Windows) i stan połączenia
sieciowego. Rekomendacja rezerwuje 2 GiB dla głównego QGIS i około 1 GiB na proces,
uwzględnia liczbę map i limit na serwer. To punkt startowy: rzeczywiste zużycie
zależy od źródeł. Można wybrać 1–32 procesy i 1–8 zadań na serwer.

Aktywne połączenie nie potwierdza dostępu do internetu, VPN ani konkretnej usługi.
Wtyczka nie wykonuje publicznego testu szybkości: przepustowość internetu i serwerów
jest oznaczona jako **niezmierzona**. Przy wolnym łączu, błędach lub obciążeniu pamięci
zmniejsz liczbę zadań; przy sprawnym szybkim serwerze zwiększaj stopniowo.
Wektory i niektóre źródła nadal wymagają głównego procesu QGIS.

## English quick start

Open **Plugins → qgis-project-snapshot → Archive project…**. Choose the output
folder, area and layers, then use **Recommend for this computer and selected layers**
and **Create archive**. Hover over controls for explanations. English is selected
for all English QGIS locales; Polish for Polish. Other locales fall back to English.

After export, scroll through the result list. Missing, cancelled, empty and partial
layers are selected for retry; successful layers are deselected. Retrying creates a
**separate archive of the selected layers**. Keep both folders; results are not merged.
Open the report and verify the archived project with network access disconnected.

CPU and available RAM guide the suggested process count (up to 32; 1–8 tasks per
server). Network connection state is detected, but internet throughput is not measured.
More processes may help across several servers, but can exhaust RAM or slow a service.

## Szacunek przed uruchomieniem

Pod liczbą kafelków znajdziesz przedział czasu i rozmiaru skompresowanych PNG
**na jedną mapę**, dla obszaru i całego wybranego zakresu zoomów. To model
przy założeniu 0,2–2 s i 10–250 KiB na kafelek, nie pomiar twojego serwera.
Podpowiedź po najechaniu wyjaśnia ograniczenia. Wektory, rastry źródłowe, zasoby,
scalanie, kontrola i dodatkowe miejsce na pliki tymczasowe nie są w nim ujęte.
Wynik może wyjść poza przedział; przy wąskim pasie prostokąt obszaru zawyża liczbę
kafelków. Równoległość nie skraca modelowego czasu pojedynczej mapy.

The tile estimate also shows a **per-map** time and compressed PNG size range.
This is a planning model (0.2–2 seconds and 10–250 KiB per tile), not a measured
forecast. Hover for assumptions and exclusions; allow extra temporary disk space.

## Czerwone ostrzeżenie serwera

Przy HTTP 429 pojawia się czerwony komunikat „zbyt wiele zapytań”. Przy HTTP 503
komunikat wskazuje niedostępność lub możliwe przeciążenie — nie jest to dowód,
że wysłano za dużo zapytań. Ostrzeżenie pozostaje widoczne do kolejnego eksportu;
szczegóły trafiają do dziennika oraz diagnostyki warstwy w raporcie.

Kliknij **Przerwij**, zmniejsz istniejący osobny parametr **Zadania na serwer**
(np. z 8 do 2, a przy dalszych problemach do 1), odczekaj i ponów próbę. Ten limit dotyczy jednoczesnych zadań map,
nie dokładnej liczby żądań HTTP na sekundę — dostawca QGIS może wysyłać kilka
żądań dla jednego zadania. Przy HTTP 429 wtyczka sama kończy pobieranie bieżącej
mapy bez kolejnych ponowień i podziałów kafelków. Inne zadania działają do przerwania.

A persistent red warning identifies HTTP 429 (too many requests) or HTTP 503
(service unavailable or possibly overloaded). Click **Cancel**, lower **Tasks per
server**, wait and retry. HTTP 429 stops the affected map without tile retries;
other tasks continue until cancelled. The limit controls concurrent map tasks,
not exact HTTP requests per second. Warnings cover map downloads observed by QGIS.
