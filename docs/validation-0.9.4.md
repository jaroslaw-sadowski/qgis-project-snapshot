# Audyt i odbiór 0.9.4 — 10 września 2026

## Ustalenia z przebiegu firmowego 0.9.3

- Eksport trwał 3 h 42 min i został anulowany. To nie była kolejna awaria IPC:
  koordynator działał, wszystkie 198 ponowień podmiany plików powiodły się.
- Dziewięć procesów zakończyło mapy. Pętla odbierająca wyniki czekała na wcześniejszą
  mapę w kolejności projektu; osiem zakończonych wyników usunięto przy anulowaniu.
  W tych wynikach było 5422 kafelków z treścią. Cztery mapy miały status saved,
  jedna miała treść na części zoomów, pozostałe były całkowicie przezroczyste.
- Dane sieciowe rzeczywiście pobierano: 27 775 odpowiedzi GetMap HTTP 200.
  Nie stwierdzono globalnej awarii proxy ani braku obsługi rastrów GeoPackage.
- 927 odpowiedzi GIOŚ zakończyło się kodem Qt 5 po około 5 sekundach każda,
  łącznie ponad 77 min oczekiwania. Brakowało korelacji z natywnym timeoutem QGIS,
  więc automat nie rozpoznawał przeciążenia/timeoutów i nie robił przerw.
- Jeden proces odpowiadał regule 3,83 GiB dostępnego RAM minus 2 GiB rezerwy,
  po 1 GiB/proces. Budżet był jednak zamrożony przy starcie eksportu.
- WFS w tym przebiegu nie odczytano — trzy warstwy anulowano przed przetwarzaniem.
  Brak podstaw do przypisania ich wcześniejszych pustych wyników tej samej przyczynie.

## Wdrożenie i testy

- Odbieranie gotowych wyników poza kolejnością z zachowaniem kolejności końcowego
  projektu. Gotowe mapy są scalane także po Cancel; oczekujemy na rozliczenie
  nadzorcy procesu, który mógł już zapisać result.json.
- Globalny budżet przeliczany co 5 s, rzeczywisty limit uruchamianych procesów,
  bez przerywania działających przy spadku RAM. GUI PL/EN pokazuje RAM i przyczynę
  czekania, a manifest początkowy, najwyższy i końcowy budżet.
- Natywny timeout QGIS, także po przekierowaniu, uruchamia istniejące ograniczenia
  i przerwy. Sam kod Qt 5 nie jest dowodem timeoutu. Bez zmiany proxy i timeoutu QGIS.
- Poprawiono licznik postępu, dodano statystyki pustych obrazów przed maską/po niej
  i czasy faz. Zachowano PNG RGBA ZLEVEL=9 i kontrolę jakości pustych map.
- Ograniczono koszt przygotowania prywatnych projektów przez usunięcie wszystkich
  ciężkich warstw raz ze wspólnego szablonu, z obsługą Qt/anulowania podczas przygotowania.

Źródła: **98/98 testów**, 80,347 s, bez pominięć. Po rozpoczęciu pełnej próby dodano
jeszcze regresję oczekiwania na nadzorcę przy Cancel; przeszła w trzech testach
kolejki. Gotowa paczka: wykrycie, instalacja, okno i wyłączenie poprawne,
**99/99 testów kodu ZIP**, 78,994 s, bez pominięć. QGIS 3.40, Ubuntu.

Nowe testy obejmują osiem rzeczywistych WMS ukończonych przed anulowaniem i przed
pierwszym scaleniem, wolną pierwszą i szybką drugą mapę, faktyczne dwa równoległe
zadania po odzyskaniu RAM, brak kończenia aktywnych zadań przy presji pamięci,
WMS przekierowujący 127.0.0.1→localhost i natywny timeout przy kodzie Qt 5,
oraz cofnięcie automatu po trzech timeoutach bez natychmiastowych ponowień/podziałów.
Ruff check, Ruff format --check i git diff --check poprawne.

Paczka: `dist/qgis-project-snapshot-0.9.4.zip`.
SHA-256: `722ea7acb80f0bd30b1d88050d0b413ebd91eede027f7a0db181fbe52b3024bf`.
Kod końcowego ZIP-a jest identyczny z przetestowanym; po odbiorze skorygowano
wyłącznie sformułowanie szacunku liczby kafelków w dołączonej instrukcji.

## Pozostały odbiór

Wymagany mały test na firmowym Windows z 3–5 widocznymi WMS/WMTS i jednym WFS,
zoom 16–17, sprawdzenie offline i osobna próba przerwania po ukończeniu mapy.
Przy stale dostępnych 3,83 GiB RAM może nadal działać jeden proces — poprawka
nie omija rezerwy pamięci. Duży zakres zoomów/duża liczba map nadal wymagają
wielu operacji sieciowych. Nie deklarujemy czasu przyspieszenia na serwerach
produkcyjnych, naprawy wszystkich WFS ani pełnej samodzielności anulowanego
archiwum (np. przerwane kopiowanie dodatkowych symboli nadal wymaga sprawdzenia).
