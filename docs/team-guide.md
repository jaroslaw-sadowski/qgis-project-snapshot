# Archiwum projektu — instrukcja dla zespołu

Paczka jest przeznaczona do odbioru na komputerze służbowym. Testy na Ubuntu
z QGIS 3.40 przeszły; pełny projekt z MSSQL nadal wymaga próby w sieci firmowej.

## Instalacja

1. Uruchom QGIS 3.40. Wymagany jest GDAL co najmniej 3.7 i wersja QGIS z PyQt5.
   Wersje bibliotek można sprawdzić w oknie informacji o QGIS.
2. Wybierz **Wtyczki → Zarządzanie wtyczkami → Zainstaluj z ZIP** i wskaż
   plik `mbtiles_batch_exporter-0.5.0.zip`. ZIP-a nie trzeba rozpakowywać.
3. Włącz **MBTiles Batch Exporter**. Jeżeli zastępujesz wcześniejszą wersję,
   zakończ jej eksport i uruchom ponownie QGIS po instalacji.
4. Nową funkcję znajdziesz w menu wtyczki jako **Archiwizuj projekt…**.
   Dotychczasowa funkcja eksportu MBTiles nadal jest dostępna.

Instalację z ZIP opisuje również
[instrukcja QGIS](https://github.com/qgis/QGIS-Documentation/blob/master/docs/user_manual/plugins/plugins.rst).

## Pierwsza próba

1. Połącz komputer z siecią firmową i otwórz projekt. Sprawdź dostęp do MSSQL,
   usług mapowych i plików na udziałach sieciowych.
2. Przybliż mapę do małego fragmentu inwestycji. Wybierz **Archiwizuj projekt…**.
3. Wskaż folder zapisu, obszar i warstwy. Dla długiej inwestycji wybierz warstwę
   poligonową z pasem opracowania, aby nie pobierać całego prostokąta zasięgu.
   Przy zaznaczonych obiektach używane są tylko zaznaczone poligony.
4. Na początek pozostaw zoom 13–17. Wyższy zoom oznacza więcej szczegółów,
   ale więcej danych. Wektory zachowują geometrię i atrybuty niezależnie od zoomu.
5. Wybierz 1 proces dla próby oszczędnej lub 2–4 dla większego obszaru.
   Więcej procesów wymaga więcej pamięci i miejsca tymczasowego. Równoległość
   obejmuje mapy; wektory z niezapisanymi edycjami pozostają w głównym QGIS.
6. Uruchom eksport. Nie zamykaj QGIS do jego zakończenia. Przycisk przerwania
   zachowuje ukończone, scalone warstwy; nie oznacza to kompletnego archiwum.

Powstanie osobny folder z projektem `.qgz`, `dane.gpkg`, raportem HTML,
`manifest.json` i ewentualnym katalogiem `zasoby`. Oryginalny projekt nie jest
zastępowany. Obrazy PNG zachowują przezroczystość i kompresję bezstratną.

## Odbiór wyniku

1. Otwórz raport. Sprawdź błędy, puste zoomy, częściowe obrazy, brakujące zasoby
   oraz przypadki zastąpienia danych wektorowych obrazem.
2. Skopiuj **cały folder archiwum** do innego miejsca. Sam plik `.qgz` nie zawiera
   wszystkich zapisanych danych.
3. Zamknij projekt źródłowy. Odłącz sieć firmową/VPN i internet, a następnie
   otwórz archiwalny `.qgz`. Nasza wtyczka nie jest wymagana do jego odczytu.
4. Porównaj grupy, kolejność, widoczność warstw, symbole, etykiety i mapy
   przy kilku zapisanych zoomach. Sprawdź atrybuty, formularze, relacje,
   załączniki oraz używane wydruki.
5. Najpierw odbierz mały fragment, następnie reprezentatywny długi pas.
   Dopiero po tych próbach wykonaj archiwum całego wymaganego obszaru.

Status „do kontroli” nie oznacza automatycznie błędu: niektóre usługi poprawnie
zwracają pusty obszar. Wymaga to sprawdzenia. Raport nie gwarantuje działania
dowolnego kodu formularzy, wyrażeń ani zasobów, których nie udało się skopiować.
Daty oznaczają czas pobierania warstw, a nie jeden wspólny moment wszystkich źródeł.

## Co zanotować przy problemie

Zapisz wersję QGIS, nazwę warstwy, wybrany obszar, zoomy, liczbę procesów i
komunikat z raportu. Raport i manifest pomogą znaleźć przyczynę. Przy błędzie
procesu pomocniczego wtyczka próbuje zapisu w głównym QGIS; można też ponowić
małą próbę z jednym procesem. Dane firmowe pozostaw w firmowym środowisku.
