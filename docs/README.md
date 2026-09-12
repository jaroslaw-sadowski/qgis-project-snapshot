# Dokumentacja QGIS Project Snapshot

## Instrukcje i bieżące wydanie 1.1.0

| Dokument | Zawartość |
| --- | --- |
| [README po polsku](../README.md) / [English README](../README.en.md) | Krótkie wprowadzenie, wymagania, instalacja i licencje |
| [Instrukcja użytkownika PL/EN](team-guide.md) | Opcje eksportu, kolejka, anulowanie, kontynuacja i sprawdzenie kopii offline; w ZIP-ie jako INSTRUKCJA.md |
| [Przygotowanie publikacji](publishing.md) | Wymagania plugins.qgis.org i czynności związane z wydaniem |
| [Weryfikacja 1.1.0](validation-1.1.0.md) | Wyniki kontroli bieżącego wydania oraz ograniczenia odbioru |

## Rozwój i utrzymanie

| Dokument | Zawartość |
| --- | --- |
| [Rozwój i testy](development.md) | Budowanie ZIP-a, testy źródeł i paczki, jakość kodu |
| [Architektura](architecture.md) | Format archiwum, moduły, równoległość i granice automatyzacji |
| [Stan projektu](PROJECT_STATE.md) | Bieżący stan prac i punkt startowy dla kolejnych sesji |
| [Instrukcje agentów](../AGENTS.md) | Trwałe zasady pracy z repozytorium |

Źródła wtyczki są w `mbtiles_batch_exporter/`, testy w `tests/`, skrypt pakowania
w `scripts/`. ZIP-y powstają w ignorowanym katalogu `dist/`.

## Historyczne raporty i pomiary

Poniższe dokumenty opisują wcześniejsze wersje i warunki ich sprawdzenia.
Nie są instrukcją bieżącego wydania ani potwierdzeniem publikacji w katalogu QGIS.

| Wersja / etap | Raport | Pomiary |
| --- | --- | --- |
| 1.0.0 | [Przygotowanie do katalogu QGIS](validation-1.0.0.md) | — |
| 0.9.7 | [Równoległość według zmierzonego RAM](validation-0.9.7.md) | [JSON](benchmark-0.9.7.json) |
| 0.9.6 | [Równoległość, nazwa i przegląd wydania](validation-0.9.6.md) | [JSON](benchmark-0.9.6.json) |
| 0.9.5 | [Powrót serwera i praca wielu serwerów](validation-0.9.5.md) | [JSON](benchmark-0.9.5.json) |
| 0.9.4 | [Gotowe mapy, RAM i timeouty](validation-0.9.4.md) | — |
| 0.9.3 | [Diagnostyka sieci i odczytu](validation-0.9.3.md) | — |
| 0.9.2 | [Atomowe pliki sterujące na Windows](validation-0.9.2.md) | — |
| 0.9.1 | [Log diagnostyczny](validation-0.9.1.md) | — |
| 0.9.0 | [Proxy, jedna akcja, Ruff/PEP 8](validation-0.9.0.md) | — |
| 0.8.3 | [Przeglądanie stanów podczas eksportu](validation-0.8.3.md) | — |
| 0.8.2 | [Procesy Windows bez konsoli](validation-0.8.2.md) | — |
| 0.8.1 | [Opisy PL/EN i ikony](validation-0.8.1.md) | — |
| 0.8.0 | [Automat i uzupełnianie kafelków](validation-0.8.0.md) | [JSON](benchmark-0.8.0.json) |
| 0.7.0 | [PL/EN, ponawianie i dobór równoległości](validation-0.7.0.md) | — |
| 0.6.0 | [Postęp i nazwa wtyczki](validation-0.6.0.md) | — |
| Krok 5 | [Paczka instalacyjna](validation-step5.md) | — |
| Krok 4 | [Odbiór i wydajność](validation-step4.md) | [JSON](benchmark-step4.json) |
| Krok 3 | [Zasoby i równoległość](validation-step3.md) | — |
