from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from hamiltonian_kernel.protocol import load_frozen_protocol


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _assert_psd(matrix: np.ndarray, label: str, tolerance: float = 1e-8) -> None:
    values = np.asarray(matrix, dtype=float)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise AssertionError(f"{label} is not square")
    if not np.allclose(values, values.T, atol=1e-10):
        raise AssertionError(f"{label} is not symmetric")
    minimum = float(np.linalg.eigvalsh(values)[0])
    if minimum < -tolerance:
        raise AssertionError(f"{label} is not PSD: min eigenvalue={minimum}")


def _expected_two_qubit_gates_per_map(row: dict[str, str], n_qubits: int) -> int:
    if row["family"] not in {"fidelity", "projected"}:
        return 0
    candidate = json.loads(row["configuration_json"])["candidate"]
    if float(candidate["interaction_strength"]) == 0.0:
        return 0
    topology = str(candidate["topology"])
    if topology == "chain":
        edge_count = n_qubits - 1
    elif topology == "ring":
        edge_count = n_qubits if n_qubits >= 3 else n_qubits - 1
    elif topology == "all_to_all":
        edge_count = n_qubits * (n_qubits - 1) // 2
    else:
        raise AssertionError(f"Unknown topology in result row: {topology}")
    # The executed publication map uses second-order Trotterization with two steps:
    # three merged diagonal A blocks, each RZZ decomposing to two logical 2Q gates.
    return 2 * edge_count * 3


def audit(
    protocol_path: Path,
    results_dir: Path,
    outer_results_path: Path | None = None,
) -> dict[str, Any]:
    protocol, frozen = load_frozen_protocol(protocol_path)
    completion = json.loads((results_dir / "completion.json").read_text(encoding="utf-8"))
    if completion.get("status") != "completed":
        raise AssertionError("Benchmark is not marked completed")
    if completion.get("protocol_hash") != frozen["protocol_hash"]:
        raise AssertionError("Completion protocol hash mismatch")
    if completion.get("qpu_executed") is not False:
        raise AssertionError("Simulator benchmark must not claim QPU execution")

    audited_outer_results = outer_results_path or (results_dir / "outer_results.csv")
    rows = _read_csv(audited_outer_results)
    tuning = _read_csv(results_dir / "inner_tuning.csv")
    deltas = _read_csv(results_dir / "primary_paired_deltas.csv")
    outer_splits = len(protocol.datasets) * protocol.outer_repeats * protocol.outer_folds
    expected_result_rows = outer_splits * (
        4
        + 2
        + 2 * len(protocol.circuit_shot_budgets) * protocol.noise_replicates
    )
    expected_tuning_rows = (
        outer_splits * 6 * protocol.tuning_configurations_per_family
    )
    expected_deltas = outer_splits * protocol.noise_replicates
    if len(rows) != expected_result_rows:
        raise AssertionError(f"Result row count {len(rows)} != {expected_result_rows}")
    if len(tuning) != expected_tuning_rows:
        raise AssertionError(f"Tuning row count {len(tuning)} != {expected_tuning_rows}")
    if len(deltas) != expected_deltas:
        raise AssertionError(f"Paired delta count {len(deltas)} != {expected_deltas}")

    expected_families = {
        "fidelity",
        "projected",
        "svm_rbf",
        "linear",
        "gradient_boosting",
        "random_fourier_features",
    }
    if {row["family"] for row in rows} != expected_families:
        raise AssertionError("Missing or extra model family")
    required_resource_columns = {
        "circuit_shots",
        "map_executions",
        "two_qubit_gate_shots",
        "qpu_time_seconds",
        "qpu_credits",
        "qpu_cost_status",
    }
    if rows and not required_resource_columns.issubset(rows[0]):
        missing = sorted(required_resource_columns - set(rows[0]))
        raise AssertionError(f"Missing resource-cost columns: {missing}")
    tuning_by_split: dict[tuple[str, int, int, str], list[dict[str, str]]] = defaultdict(list)
    for row in tuning:
        key = (
            row["dataset"],
            int(row["outer_repeat"]),
            int(row["outer_fold"]),
            row["family"],
        )
        tuning_by_split[key].append(row)
    if len(tuning_by_split) != outer_splits * 6:
        raise AssertionError("Incomplete tuning groups")
    for key, group in tuning_by_split.items():
        if len(group) != protocol.tuning_configurations_per_family:
            raise AssertionError(f"Unequal tuning budget for {key}")
        if sum(row["selected"].lower() == "true" for row in group) != 1:
            raise AssertionError(f"Expected one selected configuration for {key}")
        if any(len(json.loads(row["inner_fold_scores_json"])) != protocol.inner_folds for row in group):
            raise AssertionError(f"Wrong inner-fold count for {key}")

    artifact_paths: set[Path] = set()
    split_paths: set[Path] = set()
    for row in rows:
        if row["protocol_hash"] != frozen["protocol_hash"]:
            raise AssertionError("Result row protocol hash mismatch")
        if int(row["tuning_configurations_evaluated"]) != protocol.tuning_configurations_per_family:
            raise AssertionError("Result row has a different tuning budget")
        split_paths.add(Path(row["split_artifact"]))
        regime = row["evaluation_regime"]
        family = row["family"]
        circuit_shots = int(row["circuit_shots"])
        if family in {"fidelity", "projected"}:
            expected_gates_per_map = _expected_two_qubit_gates_per_map(
                row, protocol.n_qubits
            )
            if int(row["two_qubit_gates_per_map"]) != expected_gates_per_map:
                raise AssertionError(
                    "Logical 2Q-gate count disagrees with J/topology/Trotter map"
                )
        if row["qpu_time_seconds"] or row["qpu_credits"]:
            raise AssertionError("Simulator/classical row claims provider QPU cost")
        if row["qpu_cost_status"] != "not_available_for_simulation":
            raise AssertionError("Unexpected QPU-cost status outside hardware execution")
        if regime == "finite_shot_simulator":
            budget = int(row["circuit_shot_budget"])
            if circuit_shots != budget:
                raise AssertionError("Circuit-shot budget mismatch")
            expected_maps = budget * (2 if family == "fidelity" else 1)
            if int(row["map_executions"]) != expected_maps:
                raise AssertionError("Map-execution accounting mismatch")
            expected_two_qubit = expected_maps * int(row["two_qubit_gates_per_map"])
            if int(row["two_qubit_gate_shots"]) != expected_two_qubit:
                raise AssertionError("2Q-gate-shot accounting mismatch")
            artifact_paths.add(Path(row["matrix_artifact"]))
        elif circuit_shots != 0 or int(row["map_executions"]) != 0:
            raise AssertionError("Non-QPU row has nonzero quantum execution cost")

    if len(split_paths) != outer_splits:
        raise AssertionError("Wrong number of outer-split artifacts")
    for path in split_paths:
        with np.load(path, allow_pickle=False) as split:
            if str(np.asarray(split["protocol_hash"]).item()) != frozen["protocol_hash"]:
                raise AssertionError(f"Split protocol hash mismatch: {path}")
            train = set(np.asarray(split["train_indices"], dtype=int).tolist())
            test = set(np.asarray(split["test_indices"], dtype=int).tolist())
            if train & test:
                raise AssertionError(f"Outer train/test overlap: {path}")
            if len(train) != len(split["y_train"]) or len(test) != len(split["y_test"]):
                raise AssertionError(f"Outer split index/data mismatch: {path}")

    expected_artifacts = (
        outer_splits * 2 * len(protocol.circuit_shot_budgets) * protocol.noise_replicates
    )
    if len(artifact_paths) != expected_artifacts:
        raise AssertionError("Wrong number of kernel-matrix artifacts")
    artifact_families = Counter()
    independently_diagonalized_groups: set[tuple[str, str, int]] = set()
    for path in artifact_paths:
        with np.load(path, allow_pickle=False) as matrices:
            if str(np.asarray(matrices["protocol_hash"]).item()) != frozen["protocol_hash"]:
                raise AssertionError(f"Matrix protocol hash mismatch: {path}")
            keys = set(matrices.files)
            if "raw_measured_diagonal" in keys:
                family = "fidelity"
                required = {
                    "raw_landmark_kernel",
                    "raw_sample_landmark",
                    "raw_measured_diagonal",
                    "psd_landmark_kernel",
                    "spectral_kernel_all",
                    "raw_eigenvalues",
                    "psd_eigenvalues",
                    "spectral_eigenvalues",
                }
                psd_matrix = matrices["psd_landmark_kernel"]
                spectral_matrix = matrices["spectral_kernel_all"]
                if len(matrices["raw_measured_diagonal"]) != len(matrices["spectral_kernel_all"]):
                    raise AssertionError(f"Measured fidelity diagonal is incomplete: {path}")
            else:
                family = "projected"
                required = {
                    "raw_kernel_all",
                    "psd_kernel_all",
                    "spectral_kernel_all",
                    "raw_eigenvalues",
                    "psd_eigenvalues",
                    "spectral_eigenvalues",
                    "sampled_bloch",
                    "shots_by_setting",
                }
                psd_matrix = matrices["psd_kernel_all"]
                spectral_matrix = matrices["spectral_kernel_all"]
            if not required.issubset(keys):
                raise AssertionError(f"Missing matrix stages in {path}: {sorted(required - keys)}")
            if float(np.min(matrices["psd_eigenvalues"])) < -1e-12:
                raise AssertionError(f"Saved PSD spectrum contains a negative value: {path}")
            if float(np.min(matrices["spectral_eigenvalues"])) < -1e-12:
                raise AssertionError(f"Saved spectral spectrum contains a negative value: {path}")
            budget_match = re.search(r"_budget(\d+)_", path.stem)
            if budget_match is None:
                raise AssertionError(f"Cannot recover budget from matrix artifact name: {path}")
            audit_group = (path.parent.name, family, int(budget_match.group(1)))
            if audit_group not in independently_diagonalized_groups:
                _assert_psd(psd_matrix, f"{path}: independently checked PSD")
                _assert_psd(spectral_matrix, f"{path}: independently checked spectral")
                independently_diagonalized_groups.add(audit_group)
            artifact_families[family] += 1

    primary = completion["primary_inference"]
    if int(primary["circuit_shot_budget"]) != max(protocol.circuit_shot_budgets):
        raise AssertionError("Primary test uses a non-frozen budget")
    if int(primary["test"]["cluster_count"]) != len(protocol.datasets) * protocol.outer_repeats:
        raise AssertionError("Primary sign-flip cluster count mismatch")
    expected_gate = (
        "eligible_for_separate_reproducible_pilot_after_review"
        if protocol.profile == "full"
        else "blocked_smoke_profile_is_not_confirmatory"
    )
    if completion.get("qpu_gate") != expected_gate:
        raise AssertionError("QPU gate does not match protocol profile")

    return {
        "status": "PASS",
        "protocol_hash": frozen["protocol_hash"],
        "profile": protocol.profile,
        "outer_results": str(audited_outer_results.resolve()),
        "outer_splits": outer_splits,
        "result_rows": len(rows),
        "tuning_rows": len(tuning),
        "paired_deltas": len(deltas),
        "split_artifacts": len(split_paths),
        "matrix_artifacts": len(artifact_paths),
        "matrix_artifacts_by_family": dict(artifact_families),
        "independently_diagonalized_matrix_groups": len(
            independently_diagonalized_groups
        ),
        "qpu_gate": completion["qpu_gate"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent audit of the frozen benchmark")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--outer-results", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(
        args.protocol.resolve(),
        args.results_dir.resolve(),
        None if args.outer_results is None else args.outer_results.resolve(),
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
