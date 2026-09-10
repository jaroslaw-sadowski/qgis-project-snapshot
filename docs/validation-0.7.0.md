# Weryfikacja 0.7.0 — 10 września 2026

Środowisko: Ubuntu, QGIS 3.40.15, PyQt5, GDAL 3.12.2, Python 3.14.4.

- 40 testów źródeł: OK, 19,01 s, bez pominięć WMS.
- Dodatkowy test angielskich procesów QGIS z limitem jednego zadania na serwer:
  OK, 11,39 s. Serwer WMS rzeczywisty, lokalny.
- Gotowy ZIP: natywne wykrywanie, włączenie, otwarcie obu okien i wyłączenie
  w tymczasowym profilu QGIS; 41 testów kodu z ZIP-a: OK, 31,73 s, bez pominięć.
- CRC ZIP-a, zgodność modułów paczki ze źródłami, składnia i git diff --check: OK.
- Katalog Qt: 311 tłumaczeń; kontrola pokrycia wywołań i parametrów szablonów.
- Sprawdzono wybór języka QGIS i systemowego, raport EN, automatyczne zaznaczanie
  problemów oraz ponowienie bez nadpisania wcześniejszego archiwum.
- Sprawdzono dobór limitów według RAM/CPU/serwerów i wybieranie zadań z wolnego
  hosta mimo kolejki do zajętego hosta.

Paczka: `dist/qgis-project-snapshot-0.7.0.zip`, 89,729 bajtów, 19 plików.
SHA-256: `3649a924046009b6e1e71095ecff1dfa0fbd66d8adc979f9ce47663da2729e5e`.

GDAL wypisuje ostrzeżenia o statystykach dla celowo pustych obrazów w teście;
asercje statusu pustego obrazu przechodzą. Testy instalacji używają minimalnego
interfejsu QGIS i Qt offscreen, nie pełnego ręcznego odbioru pulpitu.

Nie zmierzono przepustowości internetu, wydajności 32 procesów ani produkcyjnych
serwerów. Nie odebrano Windows i źródeł firmowych. MSSQL pozostaje dostępny
wyłącznie na stanowisku użytkownika w sieci firmowej.
