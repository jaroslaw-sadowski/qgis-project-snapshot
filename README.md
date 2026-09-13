# QGIS Project Snapshot 1.0.2

## English

QGIS Project Snapshot saves a copy of your project for offline use. It downloads
**WMS/WMTS maps and XYZ tiles**, including OpenStreetMap basemaps, and keeps
vector data and layer styles. Maps are saved without loss of image quality.
Choose the area from the map view or a polygon layer. The report shows what
was saved. Keep the whole folder to move the project or resume a download.

**What you need and how to install**

Use QGIS 3.40 or a later 3.x version, or QGIS 4.x, with Python ≥3.10 and GDAL ≥3.7
supplied by QGIS. The plugin includes defusedxml for safer XML reading
(PSF license). No extra Python packages are needed. You need access to your
data sources and enough disk space.

Download `qgis-project-snapshot-1.0.2.zip`. Open
**Plugins → Manage and Install Plugins → Install from ZIP** and select the file.
Restart QGIS, then open **Plugins → QGIS Project Snapshot**.

**Downloading and privacy**

The plugin uses multiple threads and processes to download layers together.
It adjusts the workload to your computer and the servers' responses.
Many layers or a large area can mean a lot of tiles, especially above zoom 17.
Large downloads may take several hours to several days.

It runs locally, without collecting usage statistics or sending your project
or diagnostics to the author. Your chosen services receive the area, layer
settings and login details needed for downloading. Check that the saved project
works without access to those services.

**Licenses and testing**

Follow each service's terms on copying and reusing data, download limits and
crediting the source. The plugin grants no rights to others' content. To the
extent permitted by law, the author is not liable for users' violations.
The code is available under the GPL-2.0-only license.

The plugin was developed with AI through vibe coding. It has been tested
(Bandit, secret scanning, Qt6, Ruff and Flake8, proxy and error handling, archive
integrity and crash recovery). See the [user guide](docs/team-guide.md) and
[release test results](docs/release-1.0.2.md).

## Polski

QGIS Project Snapshot zapisuje kopię projektu do pracy bez internetu.
Pobiera **mapy WMS/WMTS i kafelki XYZ**, w tym podkłady OpenStreetMap,
oraz zachowuje dane wektorowe i wygląd warstw. Obrazy map zapisuje bez utraty
jakości. Obszar wybierasz z widoku mapy lub warstwy poligonowej. W raporcie
sprawdzisz, co udało się zapisać. Zachowaj cały folder, jeśli chcesz przenieść
projekt lub wznowić pobieranie.

**Czego potrzebujesz i jak zainstalować wtyczkę**

Potrzebujesz QGIS 3 w wersji co najmniej 3.40 albo QGIS 4, z Pythonem ≥3.10
i GDAL ≥3.7 dostarczanymi razem z QGIS. Wtyczka zawiera bibliotekę defusedxml
do bezpieczniejszego odczytu XML (licencja PSF). Nie musisz instalować dodatkowych
pakietów Pythona. Potrzebujesz też dostępu do źródeł danych i miejsca na dysku.

Pobierz `qgis-project-snapshot-1.0.2.zip`. Otwórz
**Wtyczki → Zarządzanie wtyczkami → Instaluj z ZIP** i wskaż ten plik.
Uruchom QGIS ponownie, a następnie wybierz **Wtyczki → QGIS Project Snapshot**.

**Pobieranie i prywatność**

Wtyczka korzysta z wielu wątków i procesów, aby pobierać kilka warstw jednocześnie.
Sama dobiera obciążenie do komputera i odpowiedzi serwerów. Wiele warstw lub duży
obszar oznacza dużo kafelków, zwłaszcza przy poziomie przybliżenia powyżej 17.
Duże pobranie może potrwać od kilku godzin do kilku dni.

Wtyczka działa lokalnie. Nie zbiera statystyk użycia ani nie wysyła autorowi
projektu czy diagnostyki. Wybranym usługom przekazuje zasięg, ustawienia warstw
i dane logowania potrzebne do pobrania danych. Sprawdź, czy zapisany projekt
działa bez dostępu do tych usług.

**Licencje i testy**

Przestrzegaj warunków każdej usługi dotyczących kopiowania i używania danych,
limitów pobierania oraz podawania źródła. Wtyczka nie daje praw do cudzych treści.
W granicach prawa autor nie odpowiada za naruszenia użytkowników. Kod wtyczki
jest dostępny na licencji GPL-2.0-only.

Wtyczka powstała z pomocą AI, metodą vibe codingu. Sprawdzono jej bezpieczeństwo
i działanie (Bandit, wykrywanie sekretów w kodzie, Qt6, Ruff i Flake8, obsługa
proxy i błędów, poprawność archiwum oraz wznowienie po awarii).
Więcej znajdziesz w [instrukcji](docs/team-guide.md)
i [wynikach testów wydania](docs/release-1.0.2.md).
