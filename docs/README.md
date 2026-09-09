# Dokumentacja

| Dokument | Odbiorca i zawartość |
|---|---|
| [Instrukcja zespołowa](team-guide.md) | Instalacja ZIP, archiwizacja i odbiór na stanowisku służbowym; kopia trafia do ZIP-a |
| [Rozwój i testy](development.md) | Polecenia budowy, testów źródeł, testów paczki i benchmarku |
| [Działanie i ograniczenia](architecture.md) | Architektura, formaty, równoległość i granice automatyzacji |
| [Stan projektu](PROJECT_STATE.md) | Aktualny etap, sprawdzone wyniki i następne zadania; punkt startowy dla AI/LLM |
| [Instrukcje agentów](../AGENTS.md) | Trwałe zasady pracy w repozytorium |

## Raporty wykonanych prób

Raporty są zapisem historycznym; aktualne priorytety znajdują się w stanie projektu.

- [Krok 3 — zasoby i równoległość](validation-step3.md)
- [Krok 4 — odbiór i wydajność](validation-step4.md)
- [Surowe pomiary benchmarku](benchmark-step4.json)
- [Krok 5 — paczka instalacyjna](validation-step5.md)
- [Wersja 0.6.0 — postęp i nazwa wtyczki](validation-0.6.0.md)

Kod nie znajduje się w dokumentacji: źródła wtyczki są w `mbtiles_batch_exporter/`,
testy w `tests/`, a skrypt pakowania w `scripts/`. Paczki są generowane w `dist/`.
