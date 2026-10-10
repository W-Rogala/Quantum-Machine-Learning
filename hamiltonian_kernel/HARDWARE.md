# Uruchomienia sprzętowe Hamiltonian kernel

## Zakres

Implementacja zachowuje ten sam zamrożony model

```text
H(x) = sum_i x_i Z_i + J sum_(i,j) Z_i Z_j + g sum_i X_i
```

i tę samą formułę Trottera na wszystkich bramkowych backendach. `workload.json`
jest niezmiennym kontraktem eksperymentu: zawiera próbki, hiperparametry, topologię,
listę obwodów i liczbę strzałów każdego obwodu. Tokeny i dane uwierzytelniające nie
są zapisywane w artefaktach.

Zależności:

```powershell
.\.venv_qml\Scripts\python.exe -m pip install -r requirements-qml-hardware.txt
```

## Wspólny budżet

Poniższe dwa workloady mają po `20000` circuit-shots. Fidelity wykorzystuje
compute-uncompute i prawdopodobieństwo wyniku samych zer. Projected kernel mierzy
lokalne obserwable w bazach X, Y i Z. Liczba strzałów różni się między obwodami
najwyżej o jeden.

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment prepare `
  --dataset wdbc --seed 0 --kernel fidelity --budget 20000 `
  --output-dir analysis_output\hardware_wdbc_fidelity

.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment prepare `
  --dataset wdbc --seed 0 --kernel projected --budget 20000 `
  --output-dir analysis_output\hardware_wdbc_projected
```

Etykiety są używane do utworzenia małego, zbalansowanego benchmarku sprzętowego.
Taki podzbiór służy do porównania implementacji i nie jest niezależnym oszacowaniem
błędu populacyjnego. Parametry modelu pozostają wybrane wcześniej przez walidację
eksperymentu siatkowego.

## Walidacja lokalna

Każdy adapter można najpierw sprawdzić bez QPU:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider aer --output-dir analysis_output\hardware_wdbc_projected\aer

.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider pennylane --device default.qubit `
  --output-dir analysis_output\hardware_wdbc_projected\pennylane

.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider braket-local `
  --output-dir analysis_output\hardware_wdbc_projected\braket-local
```

Te wyniki mają zawsze `not_a_qpu_execution: true`.

## IBM Quantum

Adapter używa aktualnego Runtime `SamplerV2`. Każdy obwód rozpoczyna się jawnym
resetem, a opcja Runtime `execution.init_qubits` jest ustawiona na `true`. Obwody są
następnie transpilowane do ISA wybranego backendu. Konto można skonfigurować bez
zapisywania klucza w repozytorium:

```powershell
.\.venv_qml\Scripts\python.exe tools\configure_ibm_quantum_account.py
```

Kompilacja bez wysłania zadania:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider ibm --backend least_busy --dry-run `
  --output-dir analysis_output\hardware_wdbc_projected\ibm-compile
```

Faktyczne wysłanie, które może zużyć czas planu lub środki konta:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider ibm --backend least_busy --confirm-submit `
  --output-dir analysis_output\hardware_wdbc_projected\ibm-qpu
```

W eksperymencie publikacyjnym należy zamrozić także fizyczny layout. Skrypt
`scripts/select_ibm_calibration_layout.py` wybiera spójny podgraf wyłącznie z
bieżących metryk kalibracyjnych backendu, bez użycia etykiet ani wyników QPU.
Wybrany layout przekazuje się jawnie, na przykład:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider ibm --backend ibm_kingston --ibm-initial-layout 89,90,91,98 `
  --confirm-submit --output-dir analysis_output\hardware_wdbc_projected\ibm-qpu-fixed-layout
```

Żądany layout, layout wynikowy, seed transpilacji, ustawienia inicjalizacji,
kalibracja i ISA są zapisywane w artefaktach wykonania. Kontrolę stanów bazowych
należy przeprowadzić przed benchmarkiem, lecz jej wyników nie wolno używać do
adaptacyjnego wyboru layoutu raportowanego jako wybór kalibracyjny.

Odzyskanie wyniku:

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment retrieve `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --state analysis_output\hardware_wdbc_projected\ibm-qpu\execution.json --wait
```

Dokumentacja: [IBM SamplerV2](https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/sampler-v2),
[pierwsze uruchomienie Samplera](https://quantum.cloud.ibm.com/docs/en/guides/get-started-with-sampler).

## IonQ

Klucz jest odczytywany z `IONQ_API_KEY`. Dla QPU zalecany jest gateset native,
ponieważ manifest wtedy raportuje rzeczywiste bramki `GPI`, `GPI2` i `ZZ`.
Adapter prosi o pamięć pojedynczych strzałów, aby uniknąć zmiany całkowitego budżetu
przez zaokrąglanie histogramów prawdopodobieństwa.

```powershell
$env:IONQ_API_KEY = "wartosc-tylko-dla-biezacego-procesu"

.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider ionq --backend offline.forte --ionq-gateset native --dry-run `
  --output-dir analysis_output\hardware_wdbc_projected\ionq-native-compile
```

`offline.forte` jest lokalnym opisem targetu i nigdy nie wysyła zadania. Faktyczne
uruchomienie wymaga zastąpienia go aktualną nazwą QPU, na przykład `qpu.forte-1`,
usunięcia `--dry-run`, dodania `--confirm-submit` i użycia nowego katalogu
wyjściowego. Wynik odzyskuje się tym samym poleceniem `retrieve`; należy dodać
`--ionq-gateset native`. Nazwy dostępnych QPU mogą się zmieniać i powinny zostać
sprawdzone na koncie przed wysłaniem.

Dokumentacja: [IonQ z Qiskit](https://docs.ionq.com/sdks/qiskit),
[native gates](https://docs.ionq.com/sdks/qiskit/native-gates-qiskit).

## Amazon Braket

Braket daje jedną ścieżkę do kilku rodzin bramkowych QPU. Dry-run buduje obwody i
manifest, ale nie nazywa tego kompilacją do konkretnego urządzenia, ponieważ
właściwa walidacja możliwości i kompilacja zachodzą po połączeniu z usługą.

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment run `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --provider braket `
  --backend arn:aws:braket:us-west-1::device/qpu/rigetti/Ankaa-3 `
  --dry-run --output-dir analysis_output\hardware_wdbc_projected\braket-prepare
```

Usunięcie `--dry-run` i dodanie `--confirm-submit` wysyła po jednym zadaniu na
obwód. Opcjonalne argumenty `--s3-bucket` i `--s3-prefix` wskazują lokalizację
wyników.

Dokumentacja: [OpenQASM w Braket](https://docs.aws.amazon.com/braket/latest/developerguide/braket-openqasm.html),
[wysyłanie zadań](https://docs.aws.amazon.com/braket/latest/developerguide/braket-submit-tasks.html).

## Xanadu

Xanadu X8 jest ośmiomodowym urządzeniem fotonicznym Gaussian Boson Sampling, a nie
bramkowym procesorem kubitowym. Nie istnieje wierna translacja bramek `RX`, `RZ` i
`RZZ` tego eksperymentu na X8. `pennylane` w tym repozytorium służy wyłącznie do
niezależnej walidacji software'owej.

```powershell
.\.venv_qml\Scripts\python.exe -m hamiltonian_kernel.hardware_experiment xanadu-plan `
  --workload analysis_output\hardware_wdbc_projected\workload.json `
  --output analysis_output\hardware_wdbc_projected\xanadu_compatibility.json
```

Osobna mapa cech CV/GBS i kernele oparte na zliczeniach fotonów są zaimplementowane
w [`photonic_kernel`](../photonic_kernel/README.md). Jest to nowa hipoteza badawcza,
a nie kolejny backend tej samej ewolucji Hamiltonowskiej. Moduł obejmuje dokładny
rozkład GBS z hafnianów, finite-shot, wspólny budżet PNR, klasyczny baseline,
walidację `Xunitary` i niezależny audyt.

Aktualna dokumentacja Strawberry Fields informuje, że Xanadu Quantum Cloud nie
jest już dostępny. Zdalny adapter jest zachowany tylko jako blokowana domyślnie
ścieżka dla osobno potwierdzonego endpointu prywatnego/historycznego; kompilacja
ani symulacja nie są oznaczane jako wynik QPU.

Dokumentacja: [status Xanadu Quantum Cloud](https://strawberryfields.readthedocs.io/en/latest/introduction/circuits.html#compilation),
[kompilator Xunitary](https://strawberryfields.readthedocs.io/en/stable/_modules/strawberryfields/compilers/xunitary.html).

## Artefakty i audyt

Każde wykonanie zapisuje `execution.json`; zadania zakończone także `counts.json`,
`analysis.json`, macierze CSV i raport. Stan z identyfikatorami zadań pozwala
odzyskać wynik po restarcie procesu.

Jeżeli proces wysyłający zatrzyma się między batchami, to samo polecenie `run` z
`--allow-existing --confirm-submit` pomija zapisane job ID i wysyła tylko brakujące
obwody. Jeżeli proces przerwie się w wąskim przedziale między zaakceptowaniem
zadania przez usługę a zapisaniem jego ID, stan otrzyma `submission_unknown`.
Automatyczne ponowienie jest wtedy blokowane; najpierw trzeba sprawdzić panel
dostawcy, aby nie zapłacić za duplikat.

```powershell
.\.venv_qml\Scripts\python.exe -m unittest tests.test_hamiltonian_kernel_hardware -v
.\.venv_qml\Scripts\python.exe -m audits.hamiltonian_kernel_hardware_audit
```

Audyt nie wysyła płatnych zadań. Sprawdza niezależnie matematykę Trottera,
compute-uncompute, dokładność budżetu, integralność zliczeń, PSD, kompilację do ISA
IBM FakeTorino, IonQ native oraz prawidłowe oznaczenia symulator/QPU.
