# Starsze eksperymenty

Kanoniczne źródła przeniesiono z `analysis_output/` 22.09.2026. W starej lokalizacji
pozostały adaptery. Zmieniono ROOT i importy, zachowując algorytmy i katalog wyników.

Uruchamiaj jako moduły z katalogu projektu, np.:

```sh
python -m experiments.legacy.ansatz_hardware_dataset_benchmark --help
python -m experiments.legacy.scar_wine_qnn_benchmark --help
```

Skrypty bez parsera argumentów uruchamiają całe historyczne badanie i mogą
nadpisać domyślne wyniki. Przed takim wykonaniem wybierz nowy katalog/plik
w konfiguracji lub pracuj w osobnej kopii checkoutu. Audyt nie uruchamiał ich
pełnych procedur treningowych.

Każdy moduł i jego ograniczenia opisano w [raporcie legacy](../../docs/audit/legacy_review.md).
MNIST wymaga dodatkowego lokalnego ARFF. OptDigits w historycznym protokole
łączy oryginalne zbiory train/test; interpretacja tego wyniku różni się od
oficjalnego benchmarku między autorami pisma.
