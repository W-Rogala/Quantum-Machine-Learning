# Quantum Machine Learning project results

Generated from the local workspace on 2026-07-13.

## Result highlights

### Compact QSVM kernel hypothesis

A compact 4-qubit `ZZFeatureMap` calibrated by kernel-target alignment was compared with a 6-qubit baseline.

- WDBC breast cancer: accuracy changed by +0.019 and macro-F1 by +0.019, while the state dimension dropped from 64 to 16.
- Wine: accuracy changed by +0.004 and macro-F1 by +0.006, again with state dimension 16 instead of 64.
- The paired test supports this mainly as an engineering quality/cost improvement, not as a proof of quantum advantage.

### NISQ robustness test

The original H2-NISQ variant was supported in ideal simulation but was fragile under shot/noise settings. The refined H3-NISQ variant adds validation-based selection of qubit count, angle scale, entanglement, and LS-SVM regularization, with a penalty for train-validation gap and two-qubit gate cost.

Representative balanced accuracy results:

| dataset | scenario | H0 baseline | H3-NISQ | paired delta |
|---|---:|---:|---:|---:|
| OptDigits 3 vs 8 | 512 shots, high noise | 0.892 | 0.980 | +0.088 |
| WDBC breast cancer | 512 shots, high noise | 0.593 | 0.935 | +0.342 |
| Wine class 1 vs 2 | 512 shots, high noise | 0.945 | 0.977 | +0.032 |

The conclusion is that H3 is supported in the tested protocol: it preserves or improves balanced accuracy while reducing the train-test gap, but it remains a simulated NISQ robustness result rather than a hardware quantum-advantage claim.

### VQE SCAR-ring ansatz

The VQE ansatz analysis confirms the dimensional limitation: no shallow, low-parameter ansatz can cover the full n-qubit pure-state space for arbitrary n. The proposed compromise is a SCAR-ring ansatz using `RY/RZ` layers plus a two-qubit `SCAR(theta, delta, phi)` entangler.

For n=4 and 1000 statevector samples:

| ansatz | layers | parameters | 2q gates | KL to Haar | Meyer-Wallach Q |
|---|---:|---:|---:|---:|---:|
| CRX-ring | 2 | 24 | 8 | 0.005970 | 0.6155 |
| SCAR-ring | 2 | 28 | 8 | 0.003168 | 0.6333 |

SCAR-ring improves expressibility versus CRX-ring at the same two-qubit gate count, with two additional parameters per layer.

### H2 reference realization check

A reference NumPy realization was prepared for a small WDBC kernel instance:

- qubits: 4
- state dimension: 16
- angle scale: 0.35
- entanglement: 0.25
- PCA explained variance: 0.7907393059409523
- kernel-target alignment: 0.544278154283432
- minimum kernel eigenvalue: 0.042281973755685195
- maximum kernel eigenvalue: 4.519098876681582

## Prepared artifact package

A local ZIP package was prepared with 59 result/reproducibility files:

- Markdown reports and QML model modules
- CSV/JSON experiment outputs
- reproducibility scripts under `tools/`
- interactive QML graph HTML/JS assets
- H2 QSVM proof PDF and TeX source

Local package metadata:

```text
path: tmp/qml_project_results_2026-07-13.zip
size: 460138 bytes
sha256: D6D22F1F3445AEC9C59CE40FA942A3A9C4C9ED6C1B4D4EB8ACDDAE729FBBFAB6
```

The package intentionally excludes virtual environments, Python caches, temporary render files, raw extracted corpora, and large datasets such as `datasets/qml_benchmarks/mnist_784/mnist_784.arff` (~122 MB).

## Source reports in the local workspace

The summary above is based on these local files:

- `analysis_output/qsvm_hypothesis_report.md`
- `analysis_output/qml_nisq_hypothesis_report.md`
- `analysis_output/vqe_scar_ansatz_report.md`
- `analysis_output/h2_reference_realization_check.json`
- `analysis_output/h2_mathematical_description_proof.md`
- `analysis_output/h2_ibm_xanadu_realization.md`
- `QML_algorithms_critical_analysis.md`
- `qml_relation_metrics.md`
