# QRC na komputerach kwantowych IBM

Implementacja sprzętowa odwzorowuje rezerwuar z `core.py` jako obwód Qiskit:

1. kubit wejściowy jest aktywnie resetowany;
2. próbka `u` jest kodowana jako `RY(2 asin(sqrt(u)))`;
3. wykonywana jest wybrana formuła Suzuki–Trottera dla Hamiltonianu Isinga;
4. cechy `X_i`, `Z_i` i `Z_i Z_j` są estymowane z dwóch grup pomiarowych;
5. klasyczny odczyt ridge jest dobierany na zbiorze walidacyjnym i oceniany na późniejszym zbiorze testowym.

Kod był sprawdzony z Qiskit 2.5.0, Qiskit Aer 0.17.2 i
`qiskit-ibm-runtime` 0.48.0. Aktualny wzorzec IBM wymaga transpilacji obwodów
do ISA backendu przed przekazaniem ich do prymitywu. W tej implementacji używany
jest `SamplerV2`, ponieważ IBM `EstimatorV2` nie obsługuje obwodów dynamicznych,
a kanał wejściowy QRC zawiera reset w środku obwodu.

## 1. Test lokalny

```powershell
& '.\.venv_qml\Scripts\python.exe' tools\qrc_ibm_hardware.py `
  --provider aer `
  --benchmark narma10 `
  --length 80 `
  --history-window 12 `
  --shots 4096
```

Powstaną między innymi `features.csv`, `predictions.csv`, `summary.json` oraz
`logical_circuits.qpy` w `analysis_output/qrc_ibm_hardware`.

## 2. Próba kompilacji do ISA IBM bez użycia chmury

```powershell
& '.\.venv_qml\Scripts\python.exe' tools\qrc_ibm_hardware.py `
  --provider fake-ibm `
  --dry-run `
  --length 50 `
  --history-window 4
```

Tryb zapisuje obwody logiczne i przetranspilowane obwody ISA w formacie QPY.
Nie wysyła żadnego zadania.

## 3. Konfiguracja konta IBM Quantum

Klucza API nie należy umieszczać w repozytorium ani w argumentach skryptu.
W zaufanym środowisku można go zapisać w magazynie poświadczeń Qiskit:

```powershell
& '.\.venv_qml\Scripts\python.exe' tools\configure_ibm_quantum_account.py
```

Skrypt pobiera klucz bez wyświetlania go na ekranie. IBM opisuje tę metodę w
[instrukcji zapisywania poświadczeń](https://quantum.cloud.ibm.com/docs/en/guides/save-credentials).

## 4. Kompilacja na rzeczywisty backend bez wysłania zadania

Brak flagi `--submit` oznacza bezpieczny dry-run:

```powershell
& '.\.venv_qml\Scripts\python.exe' tools\qrc_ibm_hardware.py `
  --provider ibm `
  --backend NAZWA_BACKENDU `
  --length 80 `
  --history-window 12
```

Jeżeli `--backend` zostanie pominięty, wybierany jest najmniej obciążony,
operacyjny backend z co najmniej czterema kubitami i obsługą obwodów
dynamicznych.

## 5. Wysłanie zadania na QPU

Wysłanie wymaga jawnej flagi `--submit`:

```powershell
& '.\.venv_qml\Scripts\python.exe' tools\qrc_ibm_hardware.py `
  --provider ibm `
  --submit `
  --backend NAZWA_BACKENDU `
  --benchmark narma10 `
  --length 80 `
  --history-window 12 `
  --shots 4096 `
  --max-circuits-per-job 50 `
  --output-dir analysis_output\qrc_ibm_hardware\ibm_run_01
```

Każdy identyfikator zadania i surowe zliczenia są zapisywane na dysku. IBM
`SamplerV2` przyjmuje obwody ISA i zwraca próbki rejestrów klasycznych; aktualny
interfejs opisuje [dokumentacja Sampler/Estimator i prymitywów](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-runtime-primitives).

## Znaczenie `history-window`

Pomiar niszczy stan rezerwuaru. Aby uzyskać cechy w chwili `t`, sprzęt musi
odtworzyć historię wejść od początku obwodu i wykonać pomiar dopiero na końcu.

- `--history-window 0` odtwarza cały prefiks i jest najwierniejszym odpowiednikiem modelu macierzowego, ale głębokość rośnie liniowo z `t`;
- dodatnia wartość, na przykład `12`, ogranicza obwód do ostatnich 12 próbek i realizuje rezerwuar o skończonej pamięci zanikającej;
- każda próbka wymaga dwóch obwodów pomiarowych, więc seria długości `N` tworzy `2N` obwodów.

Wynik z ograniczonym oknem nie jest matematycznie identyczny z rezerwuarem o
pełnej historii. Parametr ten należy dobrać na walidacji razem z liczbą kroków
Trottera, uwzględniając głębokość ISA, błędy bramek i dostępny budżet QPU.

## Ograniczenia eksperymentalne

- Wyniki z Aer bez modelu szumu nie przewidują jakości konkretnego QPU.
- Liczba natywnych bramek dwukubitowych zależy od backendu, układu i chwili kalibracji.
- `SamplerV2` nie zapewnia automatycznie tego samego zestawu metod mitygacji co `EstimatorV2`; ewentualną korekcję odczytu należy walidować oddzielnie.
- Dla porównania naukowego trzeba zachować QPY, nazwę backendu, job ID, liczbę strzałów, seed transpilera oraz migawkę kalibracji.

Oficjalny przykład IBM pokazujący transpilację do ISA i uruchamianie wielu
eksperymentów znajduje się w [Estimator examples](https://quantum.cloud.ibm.com/docs/en/guides/estimator-examples), natomiast ograniczenia obwodów dynamicznych opisano w
[Execute dynamic circuits](https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits).

