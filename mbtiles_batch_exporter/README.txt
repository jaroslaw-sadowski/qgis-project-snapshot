MBTiles Batch Exporter (QGIS plugin) — v0.2.2 (stable + faster)
==============================================================

Dlaczego v0.2.1 mogła działać wolniej niż skrypt?
- Wtyczka musi utrzymywać responsywność UI, więc częściej "przepompowuje" zdarzenia (progress/log).
- Dodatkowo przełączanie widoczności warstw może powodować odświeżanie Map Canvas (rendering), co bywa kosztowne (zwłaszcza WMS/XYZ).

Co zmieniono w v0.2.2:
- Dodano opcję: "Wstrzymaj renderowanie mapy (szybciej)" — domyślnie włączona.
  Dzięki temu przy przełączaniu widoczności warstw QGIS nie renderuje mapy w canvasie, a algorytm i tak renderuje kafle.
- Ograniczono częstotliwość odświeżania UI (processEvents) — throttling ~150ms.

Funkcje:
- Eksportuje wybrane warstwy (wektorowe i rastrowe) osobno do plików .mbtiles (XYZ tiles)
- Wybór folderu zapisu
- Wybór warstw: lista z checkboxami (domyślnie zaznaczone wszystkie) + przyciski Zaznacz/Odznacz wszystko
- Wybór obszaru: map canvas albo extent z warstwy poligonowej (zaznaczenie ma priorytet)
- Wybór formatu kafli: PNG / JPEG
- Wybór zoom min/max
- Log + postęp
- Przycisk „Przerwij”

Instalacja (ręcznie):
Skopiuj folder `mbtiles_batch_exporter` do katalogu plugins profilu (jak wcześniej), restart QGIS, włącz w menedżerze wtyczek.
