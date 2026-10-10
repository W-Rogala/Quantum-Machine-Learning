# Monografia matematyczna QML · 5 października 2026

Rozwinięcie audytu całego projektu: dowody i kontrprzykłady, warunki hipotez,
wyprowadzenia reprezentacji i algorytmów, dokładne odnośniki do aktualnego kodu,
porównania zachowanych eksperymentów oraz typowane transformacje grafowe.

## Czytanie offline

Po wypakowaniu ZIP otwórz **START_RAPORT.html** z głównego katalogu paczki.

Gotowy plik lokalny:
`output/reports/QML_monografia_matematyczna_2026-10-05.html`.
Otwórz go bezpośrednio w przeglądarce. Nie wymaga serwera, instalacji ani internetu.
Pakiet `output/reports/QML_monografia_matematyczna_2026-10-05.zip` zawiera ten sam
HTML, źródła rozdziałów, bibliografię, bazę SQLite, dane, kod i wyniki kontroli.
Duże artefakty w `output/` pozostają poza repozytorium; można udostępnić ZIP jako
osobny asset wydania GitHub. Nie utworzono ani nie opublikowano wydania zdalnego.

Nawigacja obejmuje rozdziały, wykresy, pięć warstw grafu, rejestr hipotez,
słownik, bibliografię, przeglądarkę kodu i cały tekst. Kliknięcie odnośnika kodu
otwiera osadzony snapshot z numerami linii. Definicje działają przez najechanie,
skupienie klawiaturą i kliknięcie do rozwinięcia. Dla szerokich wzorów i grafów
na telefonie przewijaj ich własny obszar poziomo. Zewnętrzne DOI i publikacje
wymagają sieci; cała treść raportu oraz metadane bibliografii pozostają offline.

## Źródła i struktura

- [Rozdziały](chapters/) i [pełny tekst Markdown](QML_MATHEMATICAL_REPORT.md).
- [Rejestr hipotez](hypotheses.json): teza, status, warunki, uzasadnienie, poprawka.
- [Graf transformacji](graph.json): 21 relacji matematycznych; historyczna mapa
  projektu pochodzi z `docs/report/graph_relations.json` i ma oddzielną datę.
- [Bibliografia BibTeX](bibliography/references.bib),
  [CSL JSON](bibliography/references.csl.json),
  [pełne rekordy](bibliography/references.json),
  [baza SQLite](bibliography/report.sqlite).
- [Manifest kodu](source_manifest.json) i [indeks funkcji](source_index.json).
- [Kontrole integralności](build_checks.json) i [kontrole algebraiczne](verification/algebra_and_integrity.json).

Baza ma tabele `sources`, `citations`, `code_refs`, `glossary`, `graph_edges`,
`hypotheses`. Klucze są wspólne z HTML i BibTeX. Pole `verification` ujawnia,
czy sprawdzono metadane, abstrakt czy wskazane części publikacji. Nie oznacza
nieprzeczytanej pracy jako niezależnie zweryfikowanego pełnego dowodu.

## Odtwarzalność

Python 3.12 z NumPy i SciPy oraz lokalny Node; KaTeX 0.16.22 jest zapisany
w `vendor/` z licencją MIT. Generator:

```sh
python tools/build_mathematical_report.py --app output/mathematical_report_app_20261005 --node /absolute/path/to/node --complete
python tools/verify_mathematical_report.py
node tools/verify_math_report_browser.cjs http://127.0.0.1:4188/
```

Budowanie aplikacji i eksport pojedynczego HTML wykonuje zainstalowany plugin
Data Analytics przez `scripts/data-app.mjs build --separate-data` oraz
`export-offline`. Wersja aplikacji i kontrolne hashe są w jej manifeście.
Źródła treści React/CSS zachowano w paczce, a uruchomienie gotowego HTML nie
wymaga tego pluginu. Ścieżka Node/Playwright w narzędziu browser QA jest lokalna
i przy odtwarzaniu na innym komputerze wymaga dostosowania.

Kontrole małych macierzy weryfikują tożsamości i kontrprzykłady. Nie stanowią
nowych treningów, replikacji wszystkich eksperymentów ani wykonania QPU.
Wyniki archiwalne pozostają niezmienione. Każde twierdzenie o przewadze
predykcyjnej wymaga właściwej, niezależnej próby i zadeklarowanego protokołu.

Repozytorium powinno zawierać źródła rozdziałów, bibliografię, manifesty,
rejestry oraz narzędzia. Samodzielny HTML i ZIP są produktami wydania,
utrzymywanymi w ignorowanym `output/reports/`.

## Korekta 9 października 2026

[Rejestr znalezionych problemów, poprawek i przygotowania GitHub](REVIEW_2026-10-09.md).
Autorskie [źródła interaktywnej warstwy](app_content/README.md) są zachowane w repozytorium.
Eksport projektu obejmuje bazę SQLite, BibTeX, fonty i licencję KaTeX oraz pięć
ściśle wskazane pliki archiwalnych danych wymagane przez generator.

Browser QA może użyć standardowego pakietu `playwright` zainstalowanego lokalnie
lub ścieżki podanej w `PLAYWRIGHT_MODULE`. Opcjonalny `REPORT_BROWSER_CHANNEL`
wskazuje kanał przeglądarki. Domyślnie Windows używa Edge, a inne systemy Chromium.

Manifest kodu zachowuje SHA-256 oryginalnych bajtów oraz `sha256_lf` treści
po zamianie CRLF na LF. Pozwala to odróżnić normalizację Git od zmiany kodu.
Pakiet ZIP ma osobne sumy rzeczywistych bajtów plików.
