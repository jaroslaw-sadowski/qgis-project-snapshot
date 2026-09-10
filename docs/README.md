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
- [Wersja 0.7.0 — PL/EN, ponawianie i dobór równoległości](validation-0.7.0.md)
- [Wersja 0.8.0 — automat i uzupełnianie kafelków](validation-0.8.0.md)
- [Benchmark 0.8.0 — surowe pomiary](benchmark-0.8.0.json)

- [Odbiór i audyt 0.9.0 — proxy, jedna akcja, Ruff/PEP 8](validation-0.9.0.md)

Kod nie znajduje się w dokumentacji: źródła wtyczki są w `mbtiles_batch_exporter/`,
testy w `tests/`, a skrypt pakowania w `scripts/`. Paczki są generowane w `dist/`.

- [Odbiór 0.8.1 — opisy PL/EN i ikony](validation-0.8.1.md)

- [Odbiór 0.8.2 — procesy Windows bez konsoli](validation-0.8.2.md)

- [Odbiór 0.8.3 — przeglądanie stanów podczas eksportu](validation-0.8.3.md)
