# qgis-project-snapshot — krótka instrukcja

## Instalacja

1. W QGIS otwórz **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP**.
2. Wskaż `qgis-project-snapshot-0.6.0.zip` i włącz **qgis-project-snapshot**.
   Jeśli aktualizujesz poprzednią wersję, zakończ eksport i uruchom ponownie QGIS.
3. Wybierz **Wtyczki → qgis-project-snapshot → Archiwizuj projekt…**.

Wymagane: QGIS 3.40 z PyQt5 oraz GDAL 3.7 lub nowszy. Sprawdzono Ubuntu;
pełny projekt z MSSQL trzeba jeszcze odebrać na komputerze służbowym.

## Utworzenie archiwum

1. Otwórz projekt z dostępem do jego danych. Pierwszą próbę zrób na małym obszarze.
2. Wybierz folder, obszar i warstwy. Dla pasa inwestycji użyj poligonów obszaru.
3. Na początek pozostaw zbliżenia 13–17. Jeden proces zużywa mniej pamięci;
   2–4 mogą skrócić pracę nad większym obszarem.
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
