# Przygotowanie GitHuba

## Wykonane porządki

- Wydzielono 8 modułów źródłowych do `experiments/legacy`, zachowując stare wejścia.
- Dodano README, mapę projektu, raporty audytu i opis odtwarzalności.
- Dodano `pyproject.toml`, snapshot zależności, `.gitignore`, `.gitattributes`
  i workflow testów bez poświadczeń QPU.
- Wyodrębniono niewielkie zestawienia w `results` z hashami oryginałów.
- Dodano checker rozmiaru, składni i wybranych wzorców sekretów oraz eksport
  jawnie zdefiniowanego zakresu publikacji.
- Sprawdzono wypakowaną paczkę: 107/107 testów, importy z jej katalogu i zgodność
  zawartości z listą plików widocznych dla Git. Zbudowano wheel lokalnie.

Aktualny katalog ma pusty `.git` i nie był rozpoznawany jako działające repozytorium.
Nie zastępowano metadanych Git i nie tworzono zdalnego repozytorium. Bezpiecznym
punktem startu jest wyeksportowana paczka lub ta uporządkowana kopia projektu.

## Zakres publikacji

Kod, testy, teoria, dokumentacja, małe dane UCI i małe zestawienia. Wykluczone:
środowiska, cache, pełne wyniki NPZ/QPY, `tmp`, binarne raporty, skany książek,
duży MNIST i aplikacja CRM. Wykluczenie nie usuwa plików z dysku.

```sh
python tools/check_publication.py
python tools/export_publication.py
```

Eksport tworzy ZIP w lokalnym `output/release`. Checker jest ograniczonym
skanem, nie formalnym dowodem braku wszystkich sekretów. Sprawdza jawny zakres
eksportu; przed własnym `git add` należy też sprawdzić listę plików Git, ponieważ
ręczne `git add -f` może obejść `.gitignore`.

## Co pozostaje do decyzji właściciela przed publicznym udostępnieniem

Nazwa i właściciel repozytorium, dane autorów do cytowania oraz licencja własnego
kodu. Nie nadano licencji MIT/Apache bez wskazania właściciela praw i jego wyboru.
Patrz [status licencji](../LICENSE_STATUS.md). Dane UCI mają odrębną atrybucję.
Nie publikować pełnych tekstów książek z `analysis_output` jako własnej dokumentacji.

Naprawy naukowe z rejestru P1 pozostają zadaniami do nowej wersji eksperymentów.
Repo może prezentować aktualne wyniki badawcze, jeśli ich ograniczenia i errata
są widoczne; gotowość techniczna repo nie oznacza zakończenia walidacji naukowej.

## Aktualizacja 9 października 2026

Eksport monografii uzupełniono o SQLite, BibTeX, KaTeX z licencją i fontami,
autorskie JSX/CSS oraz pięć jawnie wskazane pliki źródłowe wykresów.
Szczegóły i instrukcja nałożenia na działającą kopię istniejącego repozytorium:
[rejestr korekty](mathematical_report/REVIEW_2026-10-09.md).
Paczka `output/release/QML-github-ready-2026-10-09.zip` ma zewnętrzny manifest
SHA-256. Wykluczono metadane Git, środowiska i konfigurację kont.

## Aktualizacja istniejącego repozytorium · 10 października 2026

Repozytorium docelowe: https://github.com/W-Rogala/Quantum-Machine-Learning .
Paczka z 9 października została nałożona na istniejącą gałąź `main`, zaczynając
od commitu `d9ba28427f5e5f80648dd49462094aefd122b401`. Zachowano historię
i zastane pliki spoza paczki. Informacje o braku działającego Git powyżej
opisują oryginalny katalog roboczy, nie tę pobraną kopię aktualizacji.
