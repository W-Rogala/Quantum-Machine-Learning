# Publication benchmark: resource-aware Hamiltonian kernels

## Status naukowy

Glowna praca porownuje Hamiltonian fidelity kernel i projected kernel jako dwie
rodziny estymatorow tej samej trotterowanej mapy cech. Eksperyment QPU nie jest
osobnym testem skutecznosci. Jest walidacja implementacji modelu wybranego przez
benchmark symulacyjny. Profil `smoke` sprawdza tylko pipeline i nie otwiera bramki
QPU.

Hipoteza pierwotna jest zamrazana przed obliczeniami:

```text
H0: srednia sparowana delta balanced accuracy (projected - fidelity) <= 0
H1: srednia sparowana delta balanced accuracy (projected - fidelity) > 0
```

Test pierwotny dotyczy wyłącznie najwiekszego zamrozonego budzetu. Zbiory danych
sa stalymi warstwami. Przedzial ufnosci jest hierarchicznym bootstrapem poziomow
repeat, fold i realizacja shot noise. Jednostka sign-flip testu to
`dataset-repeat`. Porownania z baseline'ami oraz mniejszy budzet sa wtórne.

## Protokol

Profil `full` zamraza:

- zbiory `moons`, `wdbc`, `wine`;
- 5 powtorzen 5-fold outer CV i 3-fold inner CV;
- 5 realizacji shot noise;
- budzety 200 000 i 1 000 000 circuit-shots;
- 12 konfiguracji hiperparametrow na kazda rodzine;
- 10 000 losowan bootstrap i 100 000 sign flips;
- test, poziom alfa, kontrast, pilot QPU i wszystkie seedy.

Preprocessing jest dopasowywany od nowa wewnatrz kazdego foldu. Kazda z rodzin
`fidelity`, `projected`, `SVM-RBF`, `linear`, `gradient_boosting` i
`random_fourier_features` otrzymuje te same inner splity oraz dokladnie 12 ocen
konfiguracji. Klasyczne baseline'y sa wariantem matched-input po tej samej
fold-local PCA(4); nie sa dowodem przewagi klasycznej ani kwantowej.

## Osie kosztu

Kazdy wynik raportuje osobno:

1. `circuit_shots`: suma shots po ustawieniach pomiarowych;
2. `map_executions`: liczba wywolan mapy cech wazona shots; overlap fidelity ma
   dwie mapy na shot, projected jedna;
3. `two_qubit_gate_shots`: suma liczby bramek 2Q pomnozonej przez shots;
4. `qpu_time_seconds` i `qpu_credits`: tylko dane raportowane przez providera,
   nigdy wartosc domyslna lub estymowana bez oznaczenia.

W symulatorze czas i kredyty QPU pozostaja `null`. Dla IBM 2Q-gate-shots sa
przeliczane po transpilacji ISA, a QPU time pochodzi z `usage_estimation` joba.

## Estymatory i macierze

Fidelity mierzy wszystkie elementy diagonalne. Budzet obejmuje diagonale train i
test. Zapisywane sa surowa macierz landmark/train, surowy cross-kernel, zmierzona
diagonala, macierz po obcieciu ujemnych wartosci wlasnych oraz wspolna mapa
spektralna train/test.

Projected losuje jeden wspolny bitstring na shot i baze X, Y lub Z. Lokalne
obserwable z tego samego shotu zachowuja zatem prawidlowe korelacje. Nie sa juz
losowane niezaleznymi rozkladami dwumianowymi. Dla kazdej realizacji publikowane sa
macierze `raw`, `PSD`, `spectral`, ich widma, sampled Bloch vectors oraz alokacja
shots.

## Uruchomienie

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.publication_benchmark freeze `
  --profile full `
  --output analysis_output\resource_aware_hamiltonian_benchmark\protocol_full.json

.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.publication_benchmark run `
  --protocol analysis_output\resource_aware_hamiltonian_benchmark\protocol_full.json `
  --output-dir analysis_output\resource_aware_hamiltonian_benchmark\full_results

.\.venv_qml\Scripts\python.exe -m audits.resource_aware_benchmark_audit `
  --protocol analysis_output\resource_aware_hamiltonian_benchmark\protocol_full.json `
  --results-dir analysis_output\resource_aware_hamiltonian_benchmark\full_results `
  --output analysis_output\resource_aware_hamiltonian_benchmark\full_audit.json
```

Istniejacy run IBM z 18 sierpnia 2026 jest jawnie oznaczony jako
`exploratory_smoke_only`: nie mierzyl diagonali i nie zapisal ISA/QPY, layoutu,
kalibracji ani seed transpile. Nie moze zostac dolaczony do wyniku potwierdzajacego.

## Reprodukowalnosc IBM

Nowy adapter zapisuje logiczne i ISA circuits jako QPY, SHA-256, layout kazdego
obwodu, wersje Qiskit/QPY, seed transpile, poziom optymalizacji i snapshot
`Backend/Target/properties`. QPY jest rekomendowanym formatem zachowujacym pelny
obiekt obwodu, a IBM wskazuje `seed_transpiler` jako wymagany dla reprodukowalnej
kompilacji:

- [IBM: Save circuits to disk](https://quantum.cloud.ibm.com/docs/en/guides/save-circuits)
- [IBM: Reproducibility of preset transpiler pipelines](https://quantum.cloud.ibm.com/docs/en/api/qiskit/dev/transpiler)
- [IBM: QPU Target and ISA](https://quantum.cloud.ibm.com/docs/en/guides/represent-quantum-computers)

## Ograniczenia

Nested repeated CV ogranicza leakage i wariancje pojedynczego splitu, ale zbiory
danych sa male, a trzy zadania nie reprezentuja calej populacji problemow ML.
Sign-flip wymaga symetrii rozkladu roznic na poziomie klastra. Wynik nie jest
dowodem quantum advantage; n=4 pozostaje latwo symulowalne klasycznie.
