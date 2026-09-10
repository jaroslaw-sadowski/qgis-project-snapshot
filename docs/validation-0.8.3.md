# Odbiór 0.8.3 — 10 września 2026

Lista warstw została przeniesiona poza blokowane ustawienia. Podczas eksportu
pozostają dostępne przewijanie, rozwijanie grup, wybór wierszy i podpowiedzi,
tabela serwerów, dziennik i jego kopiowanie. Zmiana wyboru warstw jest czasowo
zablokowana flagą ItemIsUserCheckable; oryginalne flagi są przywracane w finally.
Parametry eksportu pozostają zablokowane do jego zakończenia.

Rozszerzono istniejący test rzeczywistego eksportu: sprawdza aktywność kontrolek,
rozwijanie grup klawiaturą Qt, brak zmiany wyboru spacją podczas pracy oraz
przywrócenie możliwości zaznaczania po zakończeniu.

Paczka: `dist/qgis-project-snapshot-0.8.3.zip`, 104 979 bajtów, 22 pliki.
SHA-256: `2ebd977fb48b15b306f9f05dbc896f488ec253849c570155e8031893a88990d3`.

**65/65 testów końcowego ZIP-a**, bez pominięć, 47,363 s. Ubuntu, QGIS 3.40.15,
Qt offscreen. Natywne wykrywanie i ładowanie, oba okna, wyłączenie, lokalny WMS:
OK. Składnia, CRC, zgodność źródeł z paczką i git diff --check: OK.
Test docelowy interakcji z listą również przeszedł osobno przed budową.
Oczekiwane komunikaty GDAL o braku pikseli dotyczą celowo pustych danych testowych.

Poprawka usuwa blokadę kontrolek. Nie przenosi wszystkich operacji QGIS poza główny
wątek: długie synchroniczne odczyty dostawców nadal mogą czasowo wstrzymać obsługę
zdarzeń. Nie przeprowadzono nowego odbioru Windows ani źródeł firmowych.
