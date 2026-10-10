# Hamiltonian quantum kernel

> Aktualny protokol publikacyjny, nested repeated CV, baseline'y i bramka QPU sa
> opisane w [`PUBLICATION_BENCHMARK.md`](PUBLICATION_BENCHMARK.md). Starsze moduly
> `experiment` i `grid_experiment` pozostaja analizami eksploracyjnymi.

Framework do testowania zależności optymalnego rzędu i kroku Trottera od liczby
kubitów oraz budżetu głębokości znajduje się w
[`TROTTER_SCALING.md`](TROTTER_SCALING.md).

Moduł realizuje wariant B pracy: quantum kernels generowane przez zależną od danych, trotterowaną dynamikę Hamiltonowską. Celem nie jest trenowanie obwodu wariacyjnego, lecz zbadanie relacji między wiernością symulacji fizycznej, generalizacją modelu i kosztem kwantowym.

## Pytanie badawcze

Jak błąd trotterowania, struktura Hamiltonianu i sposób pomiaru wpływają na generalizację, koncentrację oraz koszt estymacji Hamiltonian quantum kernel?

Hipotezy robocze:

1. Dokładniejsze przybliżenie `exp(-iHt)` nie musi dawać lepszej klasyfikacji.
2. Umiarkowany błąd Trottera może działać jak bias indukcyjny.
3. Fidelity kernel jest bardziej wrażliwy na koszt par próbek i skończoną liczbę pomiarów.
4. Projected kernel ogranicza dostępną informację, ale może mieć lepszą stabilność pomiarową.
5. Zbyt ekspresyjna dynamika prowadzi do koncentracji podobieństw i pogorszenia kondycji problemu.

## Model

Badana mapa cech ma Hamiltonian

```text
H(x) = sum_i x_i Z_i + J sum_(i,j) Z_i Z_j + g sum_i X_i,
```

ze stanem początkowym `|+>^n`. Część diagonalna `A(x)` zawiera dane i oddziaływania `ZZ`, natomiast `B = g sum_i X_i` nie komutuje z `A`. Implementacja obejmuje:

- dokładną ewolucję przez diagonalizację hermitowską;
- formułę Liego-Trottera pierwszego rzędu;
- symetryczną formułę Suzuki drugiego rzędu;
- fidelity kernel;
- projected kernel oparty na lokalnych wektorach Blocha;
- klasyczny RBF jako wymagany punkt odniesienia;
- skończoną liczbę pomiarów i naprawę PSD próbkowanej macierzy Grama fidelity kernel.

## Protokół walidacji

Każdy podział stosuje proporcje 60/20/20. Standaryzacja, PCA i skalowanie są dopasowywane tylko na train. Parametr `gamma` jest wybierany przez centered kernel-target alignment na train, a regularyzacja kernel ridge regression na validation. Test nie uczestniczy w wyborze hiperparametrów.

Domyślne zbiory pełnego profilu:

- `moons`, jako kontrolowany problem nieliniowy;
- `wdbc`, jako binarna klasyfikacja rzeczywistych danych;
- `wine`, jako problem wieloklasowy.

## Uruchomienie

Szybka walidacja:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.experiment --profile smoke
```

Pełny eksperyment z 10 podziałami:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.experiment --profile full
```

Przykład ograniczonego eksperymentu:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.experiment `
  --profile full `
  --datasets moons,wdbc `
  --seeds 0,1,2 `
  --topology ring `
  --evolution-time 1.5
```

Testy:

```powershell
.\.venv_qml\Scripts\python.exe -m unittest tests.test_hamiltonian_kernel -v
.\.venv_qml\Scripts\python.exe -m unittest tests.test_hamiltonian_kernel_grid -v
.\.venv_qml\Scripts\python.exe -m unittest tests.test_hamiltonian_kernel_hardware -v
```

Pełna siatka `t`, `J`, `g`, topologii i porównanie przy równym całkowitym budżecie:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.grid_experiment --profile full
```

Domyślny estymator fidelity wykorzystuje wszystkie próbki treningowe oraz jedną
znormalizowaną mapę spektralną wspólną dla train, validation i test. Dodatnia
wartość `--landmarks` przełącza eksperyment na analizę czułości Nyströma.

Niezależny audyt gotowych artefaktów:

```powershell
.\.venv_qml\Scripts\python.exe -m audits.hamiltonian_kernel_grid_output_audit `
  analysis_output\hamiltonian_kernel_grid_full_spectral
```

## Artefakty

Wyniki trafiają do `analysis_output/hamiltonian_kernel_<profile>/`:

- `runs.csv`: wszystkie wyniki jednostkowe;
- `summary.csv` i `summary.json`: agregaty oraz pełna konfiguracja;
- `report.md`: raport w formie tabelarycznej;
- `performance.png`: jakość predykcji względem wariantu i błędu Trottera;
- `kernel_diagnostics.png`: alignment oraz efektywny rząd macierzy kernela.

## Etapy rozwoju pracy

1. Referencyjna analiza Trottera na symulatorze stanu, obecny etap.
2. Siatka `t`, `J`, `g` i topologii z kontrolą wielokrotnych porównań.
3. Modele szumu bramek oraz pomiarów zgodne z wybranym backendem.
4. Transpilacja obwodów i porównanie rzeczywistych kosztów, nie tylko proxy CX.
5. Eksperyment sprzętowy dla małego, zamrożonego zestawu konfiguracji.
6. Analiza skalowania koncentracji kernela wraz z liczbą kubitów.

## Granice wnioskowania

Kod nie dowodzi przewagi kwantowej. Hamiltonian dla małej liczby kubitów jest klasycznie symulowalny, a wynik zależy od preprocessingu i badanego rozkładu danych. Poprawny wniosek pierwszego etapu dotyczy zasad projektowania i kompromisu jakość-koszt, nie asymptotycznego quantum advantage.

Model finite-shot dla projected kernel przybliża marginalne estymatory lokalnych obserwabli niezależnymi zmiennymi dwumianowymi. Nie modeluje jeszcze kowariancji wynikającej ze współdzielenia tych samych strzałów pomiarowych.

Obecny profil porównuje warianty przy tej samej liczbie strzałów na obwód. Nie jest to porównanie przy równym całkowitym budżecie, ponieważ fidelity kernel wymaga liczby obwodów rosnącej kwadratowo z liczbą próbek treningowych. Eksperyment z budżetem całkowitym jest osobnym etapem pracy.

Moduł `grid_experiment` realizuje ten osobny etap. Budżet oznacza sumę
`circuit-shots` dla finalnej estymacji kernela; koszt symulacyjnego przeszukania
siatki jest raportowany poza tym budżetem. Równość budżetu pomiarowego nie
oznacza równości kosztu bramek, ponieważ pomiar overlapu fidelity wykonuje dwie
mapy cech na circuit-shot.

## IBM, IonQ, Braket i Xanadu

Warstwa `hardware_experiment` zamraża wybrany model i próbki, rozdziela dokładny
całkowity budżet pomiarowy, generuje logiczny OpenQASM 3 oraz zapisuje identyfikatory
zadań potrzebne do wznowienia eksperymentu. Obsługiwane są:

- IBM Quantum przez Runtime `SamplerV2`, jawny reset i `init_qubits`, stały fizyczny
  layout oraz obwody przetranspilowane do ISA;
- IonQ przez `qiskit-ionq`, w zestawie bramek QIS albo native;
- Amazon Braket, w tym dostępne przez tę usługę bramkowe QPU;
- Aer, PennyLane i Braket Local jako trzy niezależne ścieżki symulatorowe.

Xanadu X8 jest urządzeniem fotonicznym GBS i nie wykonuje tej samej kubitowej
ewolucji Isinga. Kod zapisuje tę niezgodność w manifeście i nie oznacza wykonania
`default.qubit` jako wyniku sprzętowego Xanadu. Osobny model CV/GBS, dokładny
symulator hafnianowy, dwa kernele z tych samych próbek PNR i adapter historycznego
kompilatora `Xunitary` znajdują się w
[`photonic_kernel/README.md`](../photonic_kernel/README.md). Publiczna usługa
Xanadu Quantum Cloud nie jest już dostępna, więc artefakty nie zawierają wyniku QPU.
Procedura dla aktywnych backendów bramkowych znajduje się w [`HARDWARE.md`](HARDWARE.md).

Niezależny audyt warstwy sprzętowej:

```powershell
.\.venv_qml\Scripts\python.exe -m audits.hamiltonian_kernel_hardware_audit
```
