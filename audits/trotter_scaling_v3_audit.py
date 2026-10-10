"""Independent artifact audit for the leakage-controlled Trotter v3 run."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from hamiltonian_kernel.trotter_scaling_v3 import load_protocol


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def audit(output_dir: Path) -> dict[str, object]:
    protocol, frozen = load_protocol(output_dir / "protocol.json")
    progress = json.loads((output_dir / "progress.json").read_text(encoding="utf-8"))
    assert progress["protocol_hash"] == frozen["protocol_hash"]
    assert frozen["development_sha256"] != frozen["holdout_sha256"]
    assert len(frozen["cv_manifest"]["splits"]) == protocol.outer_repeats * protocol.outer_folds
    for split in frozen["cv_manifest"]["splits"]:
        assert not set(split["train_indices"]) & set(split["test_indices"])
        for inner in split["inner_folds"]:
            assert not set(inner["train_indices"]) & set(inner["validation_indices"])
            assert set(inner["train_indices"]) | set(inner["validation_indices"]) == set(split["train_indices"])
    baselines = read_csv(output_dir / "classical_baselines.csv")
    baseline_keys = {
        (int(row["repeat"]), int(row["fold"]), int(row["configs_evaluated"]), row["model"])
        for row in baselines
    }
    checks = 0
    rows_seen = 0
    for summary in progress["conditions"]:
        condition_id = summary["condition_id"]
        outer = read_csv(output_dir / "conditions" / f"{condition_id}_outer.csv")
        grid = read_csv(output_dir / "grid" / f"{condition_id}.csv")
        assert len(grid) == 3 * len(protocol.delta_grid())
        assert all(row["grid_interpretation"] == "cost_screened_not_exhaustive_inner_cv" for row in grid)
        resources = read_csv(output_dir / "resources" / f"{condition_id}.csv")
        assert any(row["selected_for_full_transpilation"] == "True" for row in grid)
        assert all(row["method"] == "qiskit_full_parameterized_circuit_opt1" for row in resources)
        checks += 3
        for row in outer:
            rows_seen += 1
            assert row["protocol_hash"] == frozen["protocol_hash"]
            assert row["selection_inputs"] == "inner_cv_and_known_costs_only"
            assert int(row["selected_full_circuit_depth"]) <= int(row["depth"])
            assert int(row["circuit_shots_used"]) <= int(row["circuit_shots"])
            assert int(row["two_qubit_gate_shots_used"]) <= int(row["two_qubit_gate_shots"])
            assert int(row["exact_equal_total_circuit_shots_used"]) <= int(row["trotter_actual_total_circuit_shots_used"])
            assert int(row["quantum_tuning_configs_evaluated"]) == int(row["candidate_count"]) * len(protocol.regularization_grid)
            repeat, fold = (int(part[1:]) for part in row["split_id"].split("_"))
            for model in ("svm_rbf", "linear", "boosting", "random_features"):
                assert (repeat, fold, int(row["quantum_tuning_configs_evaluated"]), model) in baseline_keys
            selection_file = output_dir / "selection" / condition_id / f"{row['split_id']}_{row['cell_id']}_rep{row['replicate']}.json"
            selected = json.loads(selection_file.read_text(encoding="utf-8"))
            assert int(selected["selected_order"]) == int(row["selected_order"])
            assert float(selected["selected_delta_t"]) == float(row["selected_delta_t"])
            assert not any("exact" in key or "test_ba" in key for key in selected)
            checks += 10
        for cell in protocol.budget_cells():
            cell_id = f"d{cell['depth']}_s{cell['circuit_shots']}_q{cell['two_qubit_gate_shots']}"
            matrix_path = output_dir / "matrices" / condition_id / f"{cell_id}.npz"
            if not any(row["cell_id"] == cell_id for row in outer):
                continue
            with np.load(matrix_path) as archive:
                raw, psd, spectral = (archive[name] for name in ("raw", "psd", "spectral"))
            assert raw.shape == psd.shape == spectral.shape
            assert np.max(np.abs(raw - raw.T)) < 1e-10
            assert np.linalg.eigvalsh(psd).min() >= -1e-8
            assert np.linalg.eigvalsh(spectral).min() >= -1e-8
            checks += 4
    holdout_path = output_dir / "holdout_progress.json"
    if holdout_path.exists():
        holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
        final_selection = json.loads((output_dir / "final_selection_before_holdout.json").read_text(encoding="utf-8"))
        assert holdout["selection_hash"] == final_selection["selection_hash"]
        assert final_selection["holdout_sha256"] == frozen["holdout_sha256"]
        assert len(read_csv(output_dir / "holdout_results.csv")) == holdout["holdout_rows"]
        assert read_csv(output_dir / "holdout_classical_baselines.csv")
        checks += 4
    result = {
        "schema": "trotter-scaling.audit.v3",
        "protocol_hash": frozen["protocol_hash"],
        "status": "passed",
        "conditions": len(progress["conditions"]),
        "outer_rows": rows_seen,
        "checks": checks,
        "confirmatory": progress["status"] == "complete" and protocol.profile == "full" and holdout_path.exists(),
    }
    (output_dir / "v3_audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
