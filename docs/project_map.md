# Mapa całego projektu QML

Strzałki opisują przepływ danych, implementację albo jawnie podpisaną relację
matematyczną. Nie oznaczają potwierdzonej przewagi kwantowej. Stan: 22.09.2026.

```mermaid
flowchart TB
    Q["QML: badania jakości, kosztu i dynamiki"]
    Q --> T["Teoria: 19 kart algorytmów"]
    Q --> L["Eksperymenty historyczne"]
    Q --> H["Hamiltonian quantum kernels"]
    Q --> R["Quantum reservoir computing"]
    Q --> P["Fotonika CV / GBS"]
    T --> G["Graf taksonomii algorytmów: HTML + JS"]
    D["Dane: Wine, WDBC, OptDigits, MNIST, moons"] --> L
    D --> H
    D --> P
    L --> L1["QSVM: PCA, alignment, H0/H1/H2"]
    L1 --> L2["NISQ: szum efektywny, normalizacja, H3"]
    L --> L3["SCAR: geometria ansatzu i QNN vs MLP"]
    L --> L4["14 ansatzów: profile dostawców i HPO"]
    L4 --> HW["Adaptery IBM / Composer / IonQ / Rigetti"]
    L3 --> HW
    H --> HC["H(x), ewolucja exact / Lie / Suzuki"]
    HC --> HK["Fidelity i projected: estymacja + KRR"]
    HK --> HB["Pilot → grid → benchmark publikacyjny"]
    HC --> TS["Skalowanie Trottera v1 → full v2 → v3"]
    TS --> V3["v3: nested CV, holdout, niezależne budżety"]
    HB --> HW
    V3 --> HW
    B["Szeregi: NARMA10, Mackey–Glass, cele pamięci"] --> R
    R --> RC["Reset wejścia + dynamika + cechy + ridge"]
    RC --> RS["H1/H2: spektrum, kontrakcja, rezonanse, CV"]
    RS --> RM["H3: pamięć, odczyty i washout"]
    RM --> RN["Szum, stacjonarność, diagnostyka"]
    RC --> RH["IBM: historia w oknie i pomiary X/Z"]
    RH --> HW
    P --> PC["TMSV → interferometr → hafnian / PNR"]
    PC --> PK["Histogram, momenty, event/orbit → kernel"]
    PK --> PR["Cutoff, overflow, straty i detektory"]
    PR --> SF["Strawberry Fields / adapter historyczny X8"]
    HK -. "dualność cech i kernela" .-> BR["Porównanie kernel–reservoir"]
    RC -. "historie jako wejścia" .-> BR
    PC -. "osobny model fizyczny" .-> BR
    HW --> E["Artefakty lokalne analysis_output"]
    HB --> E
    V3 --> E
    RN --> E
    PK --> E
    L1 --> E
    E --> A["Testy, audyty, hashe i status wykonania"]
    A --> O["Raporty PDF, prezentacje, notebook QRC"]
    A --> REV["Audyt 22.09: błędy, ograniczenia, plan poprawek"]
    E --> PUB["results: małe zestawienia do repozytorium"]
    REV --> GH["GitHub: kod + dokumentacja + CI"]
    PUB --> GH
    X["SPLOT / personal-project-crm"] -. "projekt sąsiedni, wyłączony z repo QML" .-> Q
```

## Wszystkie gałęzie teorii

```mermaid
flowchart LR
    QML["Teoria QML"] --> K["Metody jądrowe"]
    K --> QSVM
    QML --> V["Obwody wariacyjne"]
    V --> PQC["QNN / PQC"]
    PQC --> VQC
    PQC --> HYB["Hybrid QNN"]
    PQC --> QCNN
    PQC --> AE["Quantum autoencoder"]
    PQC --> QRL
    QML --> GEN["Modele generatywne"]
    GEN --> QGAN
    GEN --> QCBM
    GEN --> QBM
    PQC --> QGAN
    PQC --> QCBM
    QML --> LA["Algorytmy algebry liniowej"]
    LA --> HHL
    LA --> QSVT
    LA --> QPCA["qPCA"]
    QSVT --> QT["Quantum transformer: wybrany model FTQC"]
    QML --> CL["Quantum clustering"]
    K -. "możliwy składnik" .-> CL
    QML --> OPT["Optymalizacja i podprogramy"]
    OPT --> QAOA
    OPT --> VQE
    OPT --> QA["Quantum annealing"]
    OPT --> GAS["Grover adaptive search"]
    V --> QAOA
    V --> VQE
    QA -. "przygotowanie / próbkowanie, z zastrzeżeniami" .-> QBM
```

To taksonomia pojęć; HHL, QSVT, VQE i GAS nie są równorzędnymi klasyfikatorami.
QCNN z redukcją rejestru wymaga opisu kanałami. Quanvolution na klasycznych
patchach jest inną architekturą. HHL nie jest wymaganym etapem każdego qPCA.

## Nawigacja po implementacji

| Gałąź | Punkt wejścia | Wyniki / protokół |
|---|---|---|
| QSVM i iteracje | `experiments/legacy/qml_hypothesis_experiment.py`, `qml_iterative_hypothesis_experiment.py`, `qsvm_hypothesis_experiment.py` | historyczne H0/H1/H2; nie mylić z H1/H2 rezerwuarów |
| Efektywny NISQ | `experiments/legacy/qml_nisq_hypothesis_experiment.py` | historyczne H3 i warianty szumu |
| VQE/SCAR | `experiments/legacy/vqe_scar_ansatz_experiment.py` | eksperyment ekspresyjności, bez minimalizacji energii |
| SCAR-QNN | `experiments/legacy/scar_wine_qnn_benchmark.py`, `tools/scar_*` | symulacja, kompilacja, QPU, mitygacja |
| HPO | `experiments/legacy/ansatz_hardware_dataset_benchmark.py`, `tools/*hpo*`, `tools/ibm_composer_hardware_train.py` | 14 adaptacji ansatzów; scenariusze dostawców |
| Hamiltonian kernels | `hamiltonian_kernel/{core,learning,estimation,protocol,publication_benchmark}.py` | `PUBLICATION_BENCHMARK.md` |
| Trotter | `trotter_scaling.py`, `trotter_scaling_full.py`, `trotter_scaling_v3.py` | `TROTTER_SCALING*.md` |
| QRC | `quantum_reservoir/core.py`, `experiment.py`, `spectral_h1_h2_study.py`, `h3_*` | `RESEARCH_PROTOCOL_H1_H5.md`, `H1_H2_SPECTRAL_ANALYSIS.md` |
| Fotoniczne kernele | `photonic_kernel/{core,experiment,robustness}.py` | `README.md`, `ROBUSTNESS.md` |
| Adaptery sprzętu | `hardware_*`, `ibm_hardware.py`, `xanadu_x8.py`, `tools/`, `scripts/` | odróżniać compile, simulator, QPU |
| Materiały końcowe | `tools/build_*`, `tools/generate_*` | lokalne `output/`; ekstrakcja treści w indeksie audytu |
| Weryfikacja | `tests/`, `audits/`, `tools/audit_*` | [raport audytu](audit/README.md) |

Pełny indeks każdego pliku Python i jego deklaracji: [katalog źródeł](audit/source_catalog.md).
Dokładny graf statycznych importów: [source_imports.mmd](source_imports.mmd).
Każdy plik danych i artefakt ma osobny wpis w [inwentarzu](audit/inventory.csv).
