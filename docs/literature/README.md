# Biblioteka literatury QML

Stan weryfikacji: **12 października 2026**. Katalog obejmuje **76 pozycji**, wszystkie **42 identyfikatory bibliografii monografii**, jawne cytowania naukowe w dokumentacji i generatorach raportów oraz cztery źródła atlasu teorii. Nie obejmuje rekurencyjnie bibliografii wewnątrz zewnętrznych książek. Pozycja oznacza dzieło, a wersja — konkretny preprint lub wydanie wydawnicze.

- **26 oryginalnych PDF-ów dla 22 prac** jest załączonych w `pdf/`, na potwierdzonych licencjach Creative Commons.
- **51 rekordów arXiv** zawiera sprawdzonych autorów, identyfikatory, wersje, źródła i licencje. Część preprintów ma dodatkową otwartą wersję wydawniczą.
- Lokalnie pobrano **85 plików PDF** (liczba obejmuje różne wersje). Pliki bez potwierdzonej zgody na redystrybucję pozostają poza publicznym repozytorium. Nowy użytkownik może pobrać dostępne teksty poniższym narzędziem.
- Cztery dotąd brakujące pełne teksty pobrano z adresów wskazanych przez użytkownika; dla piątej pracy pobrano **suplement, nie główny artykuł**. Ich kopie pozostają lokalne, ponieważ nie potwierdzono prawa redystrybucji. [Nowe źródła i status](USER_SOURCES_20261012.md). Główny artykuł QuanONet z 2026 nadal nie został pobrany.
- Dołączono oryginalną [migawkę kodu QuanONet](code/QuanONet-d01934380a14.zip) na licencji MIT, commit `d01934380a148c96526261ed99218b22c5097353`. Archiwum nie zostało zainstalowane ani uruchomione.

## Korzystanie offline

Pobierz repozytorium i otwórz [index.html](index.html) bezpośrednio w przeglądarce. Wyszukiwanie, filtrowanie, metadane, miejsca cytowania i dołączone PDF-y działają bez serwera i bez połączenia internetowego. Zewnętrzne odnośniki do wydawców, arXiv i wyszukiwania autorów wymagają internetu. Odnośnik autora jest wyszukiwaniem, a nie potwierdzonym unikalnym profilem osoby.

[JSON katalogu](catalog.json), [BibTeX](references.bib), [baza SQLite](library.sqlite), [manifest plików i licencji](manifest.json), [atrybucja](NOTICE.md), [inwentarz odnośników projektu](source_urls.json).
SQLite zawiera tabele `works`, `versions` i `citations`; pełne metadane wersji znajdują się w polach JSON. Metadane arXiv, Crossref i wydawców są zachowane także w osobnych plikach `*_records.json`.

## Pobieranie dostępnych tekstów na własny użytek

Z katalogu głównego repozytorium, Python 3.12 (biblioteka standardowa):

```sh
python tools/fetch_literature.py
python tools/fetch_literature.py --redistributable-only
python tools/fetch_literature.py --work-id watrous2018
python tools/verify_literature.py
python tools/check_publication.py
```

Pobrane pliki i dziennik trafiają do ignorowanego `output/literature/`. Narzędzie sprawdza SHA-256 ustalonej wersji; nie omija paywalli, nie pobiera nieznanych zamienników i nie nadpisuje pliku o innej sumie. Zmiana pliku u wydawcy wymaga ponownego sprawdzenia wersji i praw. Błędy sieciowe zapisuje w `download_results.json`; sprawdź ich przyczynę przed ponowną próbą. Pozycje bez potwierdzonego publicznego URL PDF pozostają odnośnikami.

## Wersje i prawa

Samo umieszczenie na arXiv nie jest zgodą na ponowne rozpowszechnianie: [zasady ponownego wykorzystania](https://info.arxiv.org/help/license/reuse.html). Licencja każdego załącznika została przypisana do konkretnego pliku. Niektóre pliki mają ograniczenie do użytku niekomercyjnego lub zakaz udostępniania zmienionych wersji. Katalog nie zmienia licencji kodu projektu. Materiały osób trzecich w publikacjach mogą mieć osobne zastrzeżenia.

Preprint nie jest automatycznie identyczny z wersją po recenzji. Katalog zachowuje obie wersje i ich odrębnych autorów/tytuły. W szczególności QuanONet (ICML 2025) nie zastępuje pracy Wang i in. z Nature Machine Intelligence (2026); archiwum kodu Zenodo nie jest pełnym tekstem artykułu. Źródło atlasu Du i in. używało v1, natomiast załącznik arXiv zawiera zweryfikowaną wersję zapisaną w manifeście.

Monografia zachowuje swoją pierwotną bibliografię i migawkę kodu. Ten katalog poszerza zasoby źródłowe; nie oznacza ponownej oceny wszystkich twierdzeń raportu na podstawie późniejszych wersji artykułów. Nowe pliki binarne kontroluje osobno `verify_literature.py`; dotychczasowy `check_publication.py` kontroluje istniejący zakres tekstów i zasobów raportu.
