from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _hash_without(payload: dict[str, Any], field: str) -> str:
    content = {key: value for key, value in payload.items() if key != field}
    return hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _grid_key(row: dict[str, str]) -> tuple[int, str, int, str, int, Decimal]:
    return (
        int(row["n_qubits"]),
        row["topology"],
        int(row["hamiltonian_seed"]),
        row["hamiltonian_profile"],
        int(row["order"]),
        Decimal(row["delta_t"]),
    )


def _condition_key(row: dict[str, str]) -> tuple[int, str, int, str]:
    return (
        int(row["n_qubits"]),
        row["topology"],
        int(row["hamiltonian_seed"]),
        row["hamiltonian_profile"],
    )


def run_audit(output_dir: Path) -> tuple[list[Check], dict[str, Any]]:
    protocol_payload = json.loads((output_dir / "protocol.json").read_text("utf-8"))
    protocol = protocol_payload["protocol"]
    completion = json.loads((output_dir / "completion.json").read_text("utf-8"))
    dataset = json.loads((output_dir / "dataset_manifest.json").read_text("utf-8"))
    cv = json.loads((output_dir / "cv_splits.json").read_text("utf-8"))
    analysis = json.loads((output_dir / "hypothesis_analysis.json").read_text("utf-8"))
    matrix_manifest = json.loads(
        (output_dir / "kernel_stage_manifest.json").read_text("utf-8")
    )
    grid = _read_csv(output_dir / "grid_candidates.csv")
    outer = _read_csv(output_dir / "outer_results.csv")
    checks: list[Check] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append(Check(name, bool(passed), detail))

    computed_protocol_hash = _hash_without(protocol_payload, "protocol_hash")
    record(
        "frozen_protocol_integrity",
        protocol_payload.get("status") == "frozen"
        and protocol_payload.get("protocol_hash") == computed_protocol_hash
        and completion.get("protocol_hash") == computed_protocol_hash,
        f"computed={computed_protocol_hash}",
    )
    record(
        "completion_integrity",
        completion.get("status") == "complete"
        and completion.get("result_hash") == _hash_without(completion, "result_hash"),
        f"result_hash={completion.get('result_hash')}",
    )
    artifact_hashes = completion.get("artifact_hashes", {})
    artifacts_ok = all(
        (output_dir / name).exists() and _file_hash(output_dir / name) == digest
        for name, digest in artifact_hashes.items()
    )
    record(
        "top_level_artifact_hashes",
        artifacts_ok and len(artifact_hashes) >= 6,
        f"artifacts={len(artifact_hashes)}",
    )

    if protocol["profile"] == "full":
        axes_ok = (
            protocol["qubit_counts"] == [2, 3, 4, 5, 6]
            and protocol["trotter_orders"] == [1, 2, 4]
            and protocol["topologies"] == ["chain", "ring", "grid", "all_to_all"]
            and protocol["hamiltonian_profiles"]
            == [
                "ising_zz_x_z",
                "random_k_local",
                "spectral_radius_1",
                "spectral_radius_3",
            ]
            and protocol["hamiltonian_seeds"] == list(range(20))
            and protocol["delta_min"] == 0.01
            and protocol["delta_max"] == 1.0
        )
    else:
        axes_ok = (
            set(protocol["trotter_orders"]) == {1, 2, 4}
            and len(protocol["hamiltonian_seeds"]) >= 2
        )
    record(
        "preregistered_axes",
        axes_ok and Decimal(str(protocol["delta_increment"])) == Decimal("0.01"),
        f"profile={protocol['profile']}, seeds={len(protocol['hamiltonian_seeds'])}",
    )

    start = int(Decimal(str(protocol["delta_min"])) * 100)
    stop = int(Decimal(str(protocol["delta_max"])) * 100)
    expected_deltas = {Decimal(value) / 100 for value in range(start, stop + 1)}
    expected_rows = (
        len(protocol["qubit_counts"])
        * len(protocol["topologies"])
        * len(protocol["hamiltonian_seeds"])
        * len(protocol["hamiltonian_profiles"])
        * len(protocol["trotter_orders"])
        * len(expected_deltas)
    )
    keys = [_grid_key(row) for row in grid]
    grouped_grid: dict[tuple[int, str, int, str, int], set[Decimal]] = {}
    evaluated_grid: dict[tuple[int, str, int, str, int], set[Decimal]] = {}
    for key, row in zip(keys, grid, strict=True):
        grouped_grid.setdefault(key[:-1], set()).add(key[-1])
        if row["numerically_evaluated"] == "True":
            evaluated_grid.setdefault(key[:-1], set()).add(key[-1])
    record(
        "complete_unique_0_01_grid",
        len(grid) == expected_rows
        and len(set(keys)) == expected_rows
        and int(completion["grid_rows"]) == expected_rows
        and all(values == expected_deltas for values in grouped_grid.values()),
        f"rows={len(grid)}, expected={expected_rows}",
    )

    resource_ok = True
    shortlist_ok = True
    for row in grid:
        slices = int(row["slice_count"])
        depth = int(row["transpiled_depth"])
        two_qubit = int(row["transpiled_two_qubit_gates"])
        total = int(row["transpiled_total_gates"])
        resource_ok &= (
            slices >= 1
            and depth >= 1
            and two_qubit >= 0
            and total >= 1
            and (depth - 1) % slices == 0
            and two_qubit % slices == 0
            and total % slices == 0
            and row["transpilation_method"]
            == "qiskit_transpiled_slice_with_frozen_inter_slice_boundaries"
        )
        evaluated = row["numerically_evaluated"] == "True"
        metrics_present = bool(row["mean_state_infidelity"]) and bool(
            row["kernel_relative_frobenius_error"]
        )
        shortlist_ok &= evaluated == metrics_present
    record(
        "transpiled_resource_accounting",
        resource_ok,
        "depth and gate counts are additive integer multiples of transpiled slices",
    )
    anchors = {
        Decimal(str(value))
        for value in protocol["shortlist_anchors"]
        if Decimal(str(protocol["delta_min"]))
        <= Decimal(str(value))
        <= Decimal(str(protocol["delta_max"]))
    }
    anchor_coverage = True
    for condition_order in grouped_grid:
        anchor_coverage &= anchors <= evaluated_grid.get(condition_order, set())
    record(
        "frozen_numerical_shortlist",
        shortlist_ok and anchor_coverage,
        f"anchors={sorted(map(str, anchors))}",
    )

    labels = np.asarray(dataset["labels"], dtype=int)
    cv_ok = cv.get("split_hash") == _hash_without(cv, "split_hash")
    cv_lookup: dict[tuple[int, int], dict[str, Any]] = {}
    all_indices = set(range(len(labels)))
    for split in cv["splits"]:
        train = set(split["train_indices"])
        test = set(split["test_indices"])
        cv_lookup[(int(split["repeat"]), int(split["fold"]))] = split
        cv_ok &= train.isdisjoint(test) and train | test == all_indices
        for inner in split["inner_folds"]:
            inner_train = set(inner["train_indices"])
            inner_validation = set(inner["validation_indices"])
            cv_ok &= (
                inner_train.isdisjoint(inner_validation)
                and inner_train | inner_validation == train
                and inner_train <= train
                and inner_validation <= train
            )
    expected_split_count = protocol["outer_repeats"] * protocol["outer_folds"]
    record(
        "nested_repeated_cv_integrity",
        cv_ok and len(cv["splits"]) == expected_split_count,
        f"outer_splits={len(cv['splits'])}, expected={expected_split_count}",
    )
    balanced = np.bincount(labels).tolist() == [len(labels) // 2, len(labels) // 2]
    record(
        "perfect_annotation_contract",
        dataset["manifest_hash"] == _hash_without(dataset, "manifest_hash")
        and dataset["label_noise"] == 0.0
        and dataset["balanced_classes"] is True
        and balanced
        and dataset["minimum_observed_margin"] >= dataset["minimum_requested_margin"],
        f"class_counts={np.bincount(labels).tolist()}",
    )

    grid_by_key = {_grid_key(row): row for row in grid}
    outer_ok = bool(outer)
    condition_coverage: set[tuple[int, str, int, str]] = set()
    for row in outer:
        condition_coverage.add(_condition_key(row))
        split = cv_lookup[(int(row["outer_repeat"]), int(row["outer_fold"]))]
        train_count = len(split["train_indices"])
        test_count = len(split["test_indices"])
        train_pairs = train_count * (train_count + 1) // 2
        test_pairs = train_count * test_count
        circuits = int(row["candidate_count"]) * train_pairs + test_pairs
        shots = int(row["shots_per_circuit"])
        grid_key = (*_condition_key(row), int(row["order"]), Decimal(row["delta_t"]))
        candidate = grid_by_key.get(grid_key)
        outer_ok &= (
            candidate is not None
            and candidate["numerically_evaluated"] == "True"
            and int(candidate["transpiled_depth"]) == int(row["transpiled_depth"])
            and int(candidate["transpiled_two_qubit_gates"])
            == int(row["transpiled_two_qubit_gates"])
            and int(row["circuit_shots_used"]) == shots * circuits
            and int(row["map_executions_used"]) == 2 * int(row["circuit_shots_used"])
            and int(row["circuit_shots_used"]) <= int(row["circuit_shot_budget"])
            and int(row["two_qubit_gate_shots_used"])
            <= int(row["two_qubit_gate_shot_budget"])
            and int(row["transpiled_depth"]) <= int(row["depth_budget"])
            and row["selection_used_outer_test"] == "False"
            and row["test_kernel_measured_after_selection"] == "True"
            and 0.0 <= float(row["outer_test_balanced_accuracy"]) <= 1.0
            and 0.0 <= float(row["exact_outer_test_balanced_accuracy"]) <= 1.0
            and math.isfinite(float(row["raw_train_min_eigenvalue"]))
            and float(row["raw_train_negative_eigenmass"]) >= 0.0
        )
    expected_conditions = (
        len(protocol["qubit_counts"])
        * len(protocol["topologies"])
        * len(protocol["hamiltonian_seeds"])
        * len(protocol["hamiltonian_profiles"])
    )
    record(
        "budget_and_test_isolation",
        outer_ok
        and len(condition_coverage) == expected_conditions
        and bool(completion["test_isolation_verified"]),
        f"outer_rows={len(outer)}, covered_conditions={len(condition_coverage)}",
    )

    hamiltonian_ok = True
    radii: dict[str, list[float]] = {"spectral_radius_1": [], "spectral_radius_3": []}
    hamiltonian_files = sorted((output_dir / "hamiltonians").rglob("*.json"))
    for path in hamiltonian_files:
        payload = json.loads(path.read_text("utf-8"))
        labels_in_file = [term["label"] for term in payload["terms"]]
        hamiltonian_ok &= (
            payload["hamiltonian_hash"] == _hash_without(payload, "hamiltonian_hash")
            and len(labels_in_file) == len(set(labels_in_file))
            and all(
                len(label) == int(payload["n_qubits"])
                and set(label) <= {"I", "X", "Y", "Z"}
                and 1 <= sum(symbol != "I" for symbol in label) <= 2
                for label in labels_in_file
            )
        )
        if payload["profile"] in radii:
            radii[payload["profile"]].append(
                float(payload["diagnostics"]["calibration_spectral_radius"])
            )
    radius_ok = True
    for profile, target in (("spectral_radius_1", 1.0), ("spectral_radius_3", 3.0)):
        if profile in protocol["hamiltonian_profiles"]:
            radius_ok &= len(radii[profile]) == expected_conditions // len(
                protocol["hamiltonian_profiles"]
            ) and max(abs(value - target) for value in radii[profile]) <= 1e-9
    record(
        "hamiltonian_manifests_and_spectral_controls",
        hamiltonian_ok
        and radius_ok
        and len(hamiltonian_files) == expected_conditions,
        f"manifests={len(hamiltonian_files)}, expected={expected_conditions}",
    )

    matrix_ok = matrix_manifest.get("manifest_hash") == _hash_without(
        matrix_manifest, "manifest_hash"
    )
    matrix_count = 0
    for relative_path, digest in matrix_manifest["artifacts"].items():
        path = output_dir / relative_path
        matrix_ok &= path.exists() and _file_hash(path) == digest
        if not path.exists():
            continue
        matrix_count += 1
        with np.load(path) as payload:
            tiers = sorted({name.split("__", 1)[0] for name in payload.files})
            for tier in tiers:
                required = {
                    f"{tier}__raw_train",
                    f"{tier}__psd_train",
                    f"{tier}__spectral_train",
                    f"{tier}__measured_diagonal",
                    f"{tier}__raw_eigenvalues",
                    f"{tier}__psd_eigenvalues",
                    f"{tier}__spectral_eigenvalues",
                    f"{tier}__metadata_json",
                }
                matrix_ok &= required <= set(payload.files)
                raw = payload[f"{tier}__raw_train"]
                psd = payload[f"{tier}__psd_train"]
                spectral = payload[f"{tier}__spectral_train"]
                matrix_ok &= (
                    raw.shape == psd.shape == spectral.shape
                    and raw.ndim == 2
                    and raw.shape[0] == raw.shape[1]
                    and np.allclose(raw, raw.T, atol=1e-12)
                    and np.allclose(np.diag(raw), payload[f"{tier}__measured_diagonal"])
                    and np.allclose(
                        np.linalg.eigvalsh(raw),
                        payload[f"{tier}__raw_eigenvalues"],
                        atol=1e-9,
                    )
                    and float(np.linalg.eigvalsh(psd)[0]) >= -1e-8
                    and float(np.linalg.eigvalsh(spectral)[0]) >= -1e-8
                    and float(np.min(payload[f"{tier}__psd_eigenvalues"])) >= 0.0
                    and float(np.min(payload[f"{tier}__spectral_eigenvalues"])) >= 0.0
                )
    record(
        "published_raw_psd_spectral_matrices",
        matrix_ok
        and matrix_count == expected_conditions
        and int(completion["kernel_stage_artifact_count"]) == matrix_count,
        f"matrix_archives={matrix_count}, expected={expected_conditions}",
    )

    expected_status = "tested" if protocol["profile"] == "full" else "descriptive_only"
    inference_ok = (
        analysis["status"] == expected_status
        and analysis["causal_claim_allowed"] is False
        and analysis["permutation_method"].startswith("Freedman-Lane")
        and analysis["cluster_level"] == "hamiltonian_seed"
        and set(analysis["primary_terms"])
        == {"n_qubits", "log_depth_budget", "n_qubits_x_log_depth_budget"}
        and 0.0 < float(analysis["permutation_p_value"]) <= 1.0
    )
    record(
        "hierarchical_inference_guardrails",
        inference_ok,
        f"status={analysis['status']}, p={analysis['permutation_p_value']:.6g}",
    )

    summary = {
        "schema": "trotter-scaling-full.independent-audit.v2",
        "status": "pass" if all(check.passed for check in checks) else "fail",
        "checks_passed": sum(check.passed for check in checks),
        "checks_total": len(checks),
        "profile": protocol["profile"],
        "protocol_hash": computed_protocol_hash,
        "grid_rows": len(grid),
        "outer_rows": len(outer),
        "condition_count": expected_conditions,
        "checks": [asdict(check) for check in checks],
    }
    summary["audit_hash"] = _hash_without(summary, "audit_hash")
    return checks, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent audit of full Trotter scaling")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    checks, summary = run_audit(args.output_dir)
    (args.output_dir / "independent_audit.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    lines = ["# Independent audit", ""]
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(f"- **{marker}** `{check.name}`: {check.detail}")
    lines.extend(
        [
            "",
            f"Overall status: **{summary['status'].upper()}** ",
            f"({summary['checks_passed']}/{summary['checks_total']}).",
        ]
    )
    (args.output_dir / "independent_audit.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    if summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
