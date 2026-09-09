qgis-project-snapshot — archiwizacja projektów QGIS
=================================================

Wersja jest podana w metadata.txt. Wymagane: QGIS 3.40 z PyQt5 i GDAL >= 3.7.

Funkcja „Archiwizuj projekt…” zapisuje lokalne dane, mapy PNG z przezroczystością,
zasoby, kopię projektu oraz raport. Obsługuje równoległe procesy dla map.
Dotychczasowy eksporter MBTiles pozostaje osobną funkcją.

Zainstaluj ZIP w menedżerze wtyczek QGIS. Menu: Wtyczki → qgis-project-snapshot.
Szczegóły opcji zobaczysz po najechaniu kursorem. Postęp pokazują stany warstw i dziennik.
Pełna instrukcja zespołowa znajduje się w dołączonym INSTRUKCJA.md, a w repozytorium
w docs/team-guide.md.

Przenoś cały folder archiwum. Przed uznaniem go za kompletne sprawdź raport
i otwórz projekt bez internetu oraz sieci firmowej. Odbiór MSSQL należy wykonać
na stanowisku z dostępem do firmowej bazy.
