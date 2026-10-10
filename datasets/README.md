# Dane badawcze

Małe historyczne pliki UCI pozostawiono w oryginalnej postaci. Metadane źródeł
sprawdzono 22.09.2026; hashe lokalnych plików są w `docs/audit/inventory.csv`.

| Dane | Lokalna ścieżka | Źródło i atrybucja |
|---|---|---|
| Wine | `qml_benchmarks/wine` | Aeberhard, S. i Forina, M.; [UCI / DOI 10.24432/C5PC7J](https://archive.ics.uci.edu/dataset/109/wine) |
| WDBC | `qml_benchmarks/breast_cancer_wisconsin_diagnostic` | Wolberg, W., Mangasarian, O., Street, N., Street, W.; [UCI / DOI 10.24432/C5DW2B](https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic) |
| OptDigits | `qml_benchmarks/optdigits` | Alpaydin, E., Kaynak, C.; [UCI](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits) |

Strony UCI podają CC BY 4.0; [tekst licencji](https://creativecommons.org/licenses/by/4.0/).
Zachowano pliki `.names` i atrybucję. Przekształcenia danych wykonuje kod w runtime.
Wine binarne 1-vs-2 i wieloklasowe Wine to odrębne zadania. OptDigits 3-vs-8
nie jest równoważne 10-klasowemu benchmarkowi.

MNIST ARFF w `qml_benchmarks/mnist_784/mnist_784.arff` jest lokalnym dużym plikiem
i nie wchodzi do eksportu GitHub. Historyczne uruchomienia MNIST wymagają jego
osobnego dostarczenia i sprawdzenia hasha; nie pobieramy ani nie podmieniamy go
automatycznie. Dokładna wersja OpenML/proweniencja pobrania wymaga uzupełnienia.

Moons, NARMA10 i Mackey–Glass są generowane kodem. Nie są niezależnymi zbiorami
fizycznych pomiarów. Protokół czasu i wersję skalowania MG5 wskazuje audyt QRC.
