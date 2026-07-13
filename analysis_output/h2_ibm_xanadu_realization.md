# Realizacja dowodu H2 na IBM Quantum i w PennyLane/Xanadu

## Cel

Dowod H2 mowi, ze model QSVM-like moze zachowac jakosc klasyfikacji przy mniejszym koszcie, jezeli:

- feature map pozostaje typu `ZZFeatureMap`,
- liczba kubitow ma dolny limit `q >= 4`,
- parametry skali katow i sprzezenia sa wybierane przez kernel-target alignment,
- jadro jest liczone jako

```math
K_{ij} = |\langle \psi_i | \psi_j \rangle|^2.
```

Ta realizacja zamienia powyzszy wzor na obwody wykonywalne:

- w Qiskit lokalnie przez `Statevector` albo na IBM Quantum przez `SamplerV2`,
- w PennyLane przez `qml.probs` i `qml.adjoint`, czyli przez pomiar prawdopodobienstwa powrotu do stanu `|00...0>`.

## Pliki

- `requirements-qml-hardware.txt` - minimalne zaleznosci.
- `tools/h2_hardware_common.py` - wspolne przygotowanie danych i konfiguracji H2.
- `tools/h2_qiskit_ibm.py` - wariant Qiskit oraz IBM Quantum Runtime.
- `tools/h2_pennylane_xanadu.py` - wariant PennyLane.
- `analysis_output/h2_qiskit_ibm_realization.json` - wynik po uruchomieniu Qiskit.
- `analysis_output/h2_pennylane_xanadu_realization.json` - wynik po uruchomieniu PennyLane.

## Instalacja bibliotek

```powershell
py -m venv .venv_qml
.\.venv_qml\Scripts\python.exe -m pip install --upgrade pip
.\.venv_qml\Scripts\python.exe -m pip install -r requirements-qml-hardware.txt
```

## Test lokalny Qiskit

```powershell
.\.venv_qml\Scripts\python.exe tools\h2_qiskit_ibm.py --mode statevector --dataset wdbc --samples-per-class 3
```

Ten tryb liczy dokladna macierz jadra dla malej, zbalansowanej probki. Jest to kontrola zgodnosci z dowodem matematycznym, bo bez szumu i bez strzalow powinna dawac dodatnio polokreslona macierz jadra.

## Uruchomienie na IBM Quantum

Najpierw ustaw token:

```powershell
$env:IBM_QUANTUM_TOKEN = "TU_WKLEJ_TOKEN"
```

Potem mozna wykonac suchy przebieg, bez wysylania zadania:

```powershell
.\.venv_qml\Scripts\python.exe tools\h2_qiskit_ibm.py --mode ibm --dry-run --dataset wdbc --samples-per-class 3
```

Wlasciwe wyslanie zadania:

```powershell
.\.venv_qml\Scripts\python.exe tools\h2_qiskit_ibm.py --mode ibm --backend least_busy --shots 4096 --dataset wdbc --samples-per-class 3
```

Dla `samples-per-class 3` powstaje 6 probek, czyli 15 obwodow overlap dla elementow pozadiagonalnych macierzy jadra.

## Test lokalny PennyLane

```powershell
.\.venv_qml\Scripts\python.exe tools\h2_pennylane_xanadu.py --device default.qubit --dataset wdbc --samples-per-class 3
```

Tryb ze skonczona liczba strzalow:

```powershell
.\.venv_qml\Scripts\python.exe tools\h2_pennylane_xanadu.py --device default.qubit --shots 4096 --dataset wdbc --samples-per-class 3
```

## Uwaga o Xanadu

PennyLane jest interfejsem rozwijanym przez Xanadu, ale hipoteza H2 zostala udowodniona dla kubitowej mapy `ZZFeatureMap`. Dlatego skrypt PennyLane realizuje dowod na urzadzeniach kubitowych zgodnych z interfejsem PennyLane, np. `default.qubit` albo odpowiedni plugin kubitowy.

Fizyczne fotoniczne uklady Xanadu pracuja w innym modelu kodowania. Przeniesienie H2 na prawdziwe urzadzenie fotoniczne wymagaloby nowej fotonicznej mapy cech oraz nowego dowodu dodatniej polokreslonosci i porownania kosztu.

## Kryterium potwierdzenia

Po uruchomieniu sprawdzamy w pliku JSON:

- `measured_diagnostics.alignment` - zgodnosc jadra z etykietami,
- `measured_diagnostics.min_eigenvalue` - czy macierz jadra pozostaje dodatnio polokreslona w granicach bledu numerycznego lub szumu strzalow,
- `config.state_dimension` - dla H2 powinno byc `16`, czyli czterokrotnie mniej niz bazowe `64` dla szesciu kubitow.
