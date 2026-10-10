# Odtwarzalność

## Środowiska

Podstawowy runtime audytu: Windows, CPython 3.12.14. Wersje bezpośrednich
zależności są zapisane w `requirements-local.txt`; pełna lista lokalnie
zainstalowanych dystrybucji w `docs/audit/environment.json` służy jako metadane,
nie przenośny lockfile. Wersje historycznych runów należy odczytywać z ich
manifestów, nie przypisywać im automatycznie środowiska z dzisiejszego audytu.

Pakiet instaluje trzy główne moduły i `experiments`. Eksperymenty wymagają
checkoutu z danymi i wykonania z jego katalogu głównego; wheel nie zawiera
gigabajtów lokalnych artefaktów. Adaptery w `tools` są skryptami checkoutu.

Strawberry Fields 0.23 / NumPy 1.26 wymaga osobnego środowiska Python 3.10.
Testy czystego kodu fotonicznego nie wymagają tej biblioteki. Brak biblioteki
oznacza brak zweryfikowanego runtime SF, a nie automatyczną poprawność adaptera.

## Kontrole

```sh
python -m unittest discover -s tests -v
python -m audits.project_review_checks
python tools/check_publication.py
python tools/build_source_catalog.py
```

Zachowany wynik bazowy: 107 testów, bez błędów. Cały zestaw powtórzono w czystym
checkoutcie eksportu: 107/107 PASS. Sprawdzono również zgodność starych wejść
i budowę wheel. Oba uruchomienia używały tego samego istniejącego środowiska;
nie jest to test instalacji zależności na nowej maszynie ani wykonanie CI Linux.
Szczegóły: [validation.json](audit/validation.json). `review_checks.json` dokumentuje
wybrane błędy i poprawne kontrprzykłady. Nie jest to test, który ma się
„zazielenić” po naprawie: część sond celowo wymaga odtworzenia starego błędu.
Po zmianie estymatorów przekształć je w właściwe testy regresyjne nowej wersji.

## Nowe eksperymenty

Wybieraj nowy katalog wyników, zapisuj parametry, seedy, wersję kodu, wersje
zależności i identyfikatory danych. Zamrożonego v3 nie należy kontynuować po
zmianie objętych hashem źródeł; utwórz nowy protokół. Seedy liczbowe nie są
datami wykonania. `smoke` sprawdza przepływ, nie potwierdza hipotezy.

Dla nowych badań kontroluj osobno: split i dostępność targetów, preprocessing,
wybór modelu, końcową ocenę, wariancję shot noise, niezależne bloki eksperymentu
oraz koszty wyszukiwania i inferencji. Nie sumuj jako niezależnych obserwacji
foldów, shot replicates i kilku profili tego samego syntetycznego urządzenia.

Pełne artefakty nie są w zwykłym repozytorium. Ich początkowy lokalny inwentarz
to `docs/audit/inventory.csv`. `results/provenance.json` mapuje małe kopie na
lokalne oryginały i hashe. Do odtworzenia historycznych makiet PDF potrzebne
mogą być dodatkowe lokalne fonty i biblioteki raportowe.
