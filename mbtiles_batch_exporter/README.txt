# QGIS Project Snapshot 1.0.0

## English

Save a QGIS project for offline use: vector data, lossless map images, styles
and a report. Choose the map view or a polygon layer as the area; keep the
whole archive folder to move it or resume interrupted downloads.

**Install:** QGIS 3.40–3.x (Qt5) or QGIS 4.x (Qt6), with Python ≥3.10 and
GDAL ≥3.7 supplied by QGIS. No extra Python packages. You need access to the
source services and enough disk space. In **Plugins → Manage and Install
Plugins → Install from ZIP**, select `qgis-project-snapshot-1.0.0.zip` and
restart QGIS. Open **Plugins → QGIS Project Snapshot → Archive project…**.

**Processing and privacy:** runs locally, using multiple QGIS processes and
supervising threads. Automatically adjusts concurrency to client memory/CPU
and server responses. Projects and diagnostics are not uploaded to the author;
there is no analytics. Download requests do send the necessary area, layer
parameters and authentication to the selected services. Review the result offline.

**Responsibility:** respect service licenses, attribution and download/reuse
restrictions. This plugin grants no rights to third-party data. To the extent
permitted by law, the author is not liable for users' violations. GPL-2.0-only.

Developed with AI and vibe coding; tested (Bandit, secret scanning, Qt6 checks,
Ruff/Flake8, proxy/error handling, archive integrity and crash recovery).
User guide: INSTRUKCJA.md. Release checks: repository docs/release-1.0.0.md.

## Polski

Zapisuje projekt QGIS do pracy offline: dane wektorowe, bezstratne obrazy map,
style i raport. Obszar wybierasz z widoku mapy lub warstwy poligonowej.
Zachowaj cały folder, aby przenieść archiwum lub wznowić przerwane pobieranie.

**Instalacja:** QGIS 3.40–3.x (Qt5) lub QGIS 4.x (Qt6), z Pythonem ≥3.10 i
GDAL ≥3.7 dostarczanymi przez QGIS. Bez dodatkowych pakietów Pythona.
Potrzebujesz dostępu do źródeł i miejsca na dysku. W **Wtyczki → Zarządzanie
wtyczkami → Instaluj z ZIP** wskaż `qgis-project-snapshot-1.0.0.zip` i uruchom
QGIS ponownie. Otwórz **Wtyczki → QGIS Project Snapshot → Archiwizuj projekt…**.

**Działanie i prywatność:** działa lokalnie, korzystając z wielu procesów QGIS
i wątków nadzorujących. Samodzielnie dobiera obciążenie do pamięci/CPU komputera
i odpowiedzi serwerów. Nie wysyła projektu ani diagnostyki do autora i nie
prowadzi analityki. Zapytania o dane przekazują wybranym usługom niezbędny zasięg,
parametry warstw i uwierzytelnienie. Sprawdź wynik bez dostępu do źródeł.

**Odpowiedzialność:** przestrzegaj licencji usług, zasad podawania źródeł oraz
ograniczeń pobierania i wykorzystania danych. Wtyczka nie nadaje praw do cudzych
treści. W granicach prawa autor nie odpowiada za naruszenia użytkownika.
Licencja kodu: GPL-2.0-only.

Powstała z pomocą AI i vibe codingu; wykonano testy (Bandit, skan sekretów,
kontrola Qt6, Ruff/Flake8, obsługa proxy/błędów, integralność archiwum i wznowienie
po awarii). Instrukcja: INSTRUKCJA.md. Kontrole wydania: docs/release-1.0.0.md w repozytorium.
