qgis-project-snapshot 0.9.5

PL: Zachowaj dane i wygląd projektu QGIS, zanim zmienią się źródłowe usługi
lub bazy. Wtyczka tworzy kopię projektu, lokalne wektory i mapy PNG
z przezroczystością oraz raport. Wybierz Wtyczki → qgis-project-snapshot
→ Archiwizuj projekt…, wskaż obszar, warstwy i folder. Pobieranie automatycznie
dobiera obciążenie serwerów i uzupełnia brakujące kafelki podczas eksportu.
Przenoś cały folder archiwum i sprawdź kopię bez sieci. Instrukcja: INSTRUKCJA.md.

EN: Preserve QGIS project data and appearance before the source services or
databases change. Creates a project copy, local vectors, transparent PNG maps
and a report. Choose Plugins → qgis-project-snapshot → Archive project…,
then select an area, layers and folder. Downloads automatically adjust server
concurrency and repair missing tiles during export. Keep the entire archive
folder and check the copy offline. See INSTRUKCJA.md for an English quick start.

QGIS 3.40 / PyQt5, GDAL >= 3.7. Tested on Ubuntu. PL/EN interface.
Connects to project sources to retrieve data; does not replace the original
project. Source terms still apply. Uses QGIS and standard Python libraries.
Developed with AI assistance. Free and open source, GNU GPL v2; see LICENSE.
Author: Jarosław Sadowski
https://github.com/jaroslaw-sadowski/qgis-project-snapshot
