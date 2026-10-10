# Trotter scaling v3

## Scientific status

The v2 value near `p=0.0001` is exploratory, not confirmation. Its policy
objective included exact-evolution diagnostics, and the reported BA values
`0.593` (shot-limited Trotter) and `0.864` (noiseless exact) mix two effects.
V3 uses fresh dataset seeds (`20261001`, `20261002`), split seed (`20261003`)
and Hamiltonian seeds (`20..39`). The independent holdout fingerprint and
source-file hashes are frozen before analysis.

The full experiment has 5 qubit counts, 4 Hamiltonian profiles, 4 topologies,
20 independent Hamiltonian seeds, 8 independently crossed resource cells,
2 repeated 3-fold outer CV splits and 2 shot replicates. This is 1,600
Hamiltonian conditions and up to 153,600 outer evaluations. A partial run is
not confirmatory, regardless of its nominal p-value.
The inherited `random_k_local` generator used here is at most **2-local**;
the profile name does not imply a sweep over arbitrary `k`.

## Selection boundary

`select_policy` receives only outer-training examples/labels and a known-cost
shortlist. It measures each candidate with the cell's finite-shot allocation,
selects regularization and policy by inner CV balanced accuracy, then breaks
ties by transpiled depth, 2Q gates, order and step. Exact evolution is called
only by `_post_selection_diagnostics`, after a selection JSON is persisted.
The held-out test data are not loaded by `run_holdout` until every final
selection has been saved and hashed.

The step grid is `0.01..1.00` for orders 1, 2 and 4. Every grid point is
recorded in `grid/*.csv`, but a preregistered cost-only screen limits which
points receive complete-circuit transpilation and inner-CV evaluation. This
is **not** an exhaustive 300-candidate numerical search. The actual full
parameterized circuit is transpiled for every evaluated candidate; no
one-slice depth extrapolation is used as a feasibility decision.

## Resources and comparisons

Depth, circuit-shots and 2Q-gate-shots are crossed independently, not bundled
into tier names. `circuit_shots_used`, `map_executions_used` and
`two_qubit_gate_shots_used` report realized counts. Exact is a simulator
oracle and has no ISA-equivalent two-qubit gate cost. Quality is reported for
noiseless Trotter/exact, finite-shot Trotter/exact at the same shots per
circuit, and finite-shot exact using no more than the **actual** total
circuit-shots consumed by the Trotter search plus test. Each finite-shot
model selects regularization on its own sampled training matrix.

The classical controls use the identical outer splits, feature vectors and
held-out examples: SVM-RBF, linear SVM, gradient boosting and RBF random
features. Each evaluates the same number of inner-CV hyperparameter
configurations as quantum `(order, step, regularization)` combinations:
three regularizations times the number of feasible `(order, step)` pairs,
up to 36 trials. They do not consume QPU shots, so
the comparison is about predictive quality and tuning effort, not equal
physical energy or wall time.

`compatible_policies.csv` contains descriptive, paired split-cluster
bootstrap compatibility sets with multiplicity-adjusted lower bounds.
These are more meaningful than counting exact ties when shot replicates
rarely choose the identical `(order, step)`. Confirmatory inference uses
only complete factorial blocks and 20 seed-clustered coefficient estimates
for 14 preregistered effects, with Bonferroni-adjusted intervals.

## Execution

From the repository root, using PowerShell:

```powershell
$py = .\.venv_qml\Scripts\python.exe
$out = "analysis_output/trotter_scaling_v3_preregistered"
& $py -m hamiltonian_kernel.trotter_scaling_v3 freeze --profile full --output-dir $out
& $py -m hamiltonian_kernel.trotter_scaling_v3 run --output-dir $out
& $py -m hamiltonian_kernel.trotter_scaling_v3 holdout --output-dir $out
& $py -m hamiltonian_kernel.trotter_scaling_v3_summary --output-dir $out
```

`run` resumes from conditions listed as complete in `progress.json`.
`--max-conditions N` is a development diagnostic only; any partial run
remains non-confirmatory. The frozen protocol contains the full split
manifest, data fingerprints and source hashes. If source files change,
create a *new* protocol/output directory instead of silently reusing the
old one.

The current frozen full run is
`analysis_output/trotter_scaling_v3_full_release_20260920` with **1/1600**
conditions complete. Its `progress.json`, `v3_summary.json` and
`v3_audit.json` explicitly mark it non-confirmatory. The separate complete
technical smoke is `analysis_output/trotter_scaling_v3_smoke_release_20260920`.
Run the independent artifact audit with:

```powershell
& $py -m audits.trotter_scaling_v3_audit --output-dir $out
```

## IBM pilot gate

Only after full v3 development, holdout, resource/classical summary and
preregistered inference are complete:

```powershell
& $py -m hamiltonian_kernel.trotter_scaling_v3_ibm freeze --output-dir $out
& $py -m hamiltonian_kernel.trotter_scaling_v3_ibm compile --output-dir $out --backend least_busy
```

Use `submit` instead of `compile` for a new pilot directory when real QPU
execution is intended; `retrieve` fetches results for its saved job ID.
Compilation writes logical and complete backend-ISA QPY, layout, seed,
backend Target/calibration snapshot and actual circuit gate counts. QPU
time/credits remain unknown until provider usage is returned. The pilot is
small and fixed without ranking conditions by holdout BA. It validates
feasibility/noise, not the primary scaling hypothesis.
