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


EXPECTED_OPTIMIZERS = {
    "grid_reference",
    "quadratic_surrogate",
    "exact_shortlist_qubo",
    "simulated_annealing_shortlist_qubo",
    "qaoa_p1_shortlist_qubo",
}


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


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate_key(row: dict[str, str]) -> tuple[int, int, int, Decimal]:
    return (
        int(row["n_qubits"]),
        int(row["depth_budget"]),
        int(row["order"]),
        Decimal(row["delta_t"]),
    )


def _selection_key(row: dict[str, str]) -> tuple[int, int, str]:
    return int(row["n_qubits"]), int(row["depth_budget"]), row["optimizer"]


def run_audit(output_dir: Path) -> tuple[list[Check], dict[str, Any]]:
    protocol_payload = json.loads((output_dir / "protocol.json").read_text("utf-8"))
    protocol = protocol_payload["protocol"]
    completion = json.loads((output_dir / "completion.json").read_text("utf-8"))
    annotation = json.loads(
        (output_dir / "annotation_manifest.json").read_text("utf-8")
    )
    analysis = json.loads(
        (output_dir / "hypothesis_analysis.json").read_text("utf-8")
    )
    candidates = _load_csv(output_dir / "candidates.csv")
    selections = _load_csv(output_dir / "selections.csv")
    checks: list[Check] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append(Check(name, bool(passed), detail))

    protocol_hash = _hash_without(protocol_payload, "protocol_hash")
    record(
        "frozen_protocol_hash",
        protocol_payload.get("status") == "frozen"
        and protocol_payload.get("protocol_hash") == protocol_hash
        and completion.get("protocol_hash") == protocol_hash,
        f"computed={protocol_hash}",
    )
    record(
        "completion_hash",
        completion.get("result_hash") == _hash_without(completion, "result_hash"),
        "completion manifest is internally hashed",
    )

    start = int(Decimal(str(protocol["delta_min"])) * 100)
    stop = int(Decimal(str(protocol["delta_max"])) * 100)
    expected_delta = {Decimal(value) / Decimal(100) for value in range(start, stop + 1)}
    observed_delta = {Decimal(row["delta_t"]) for row in candidates}
    exact_increment = all(
        right - left == Decimal("0.01")
        for left, right in zip(sorted(observed_delta)[:-1], sorted(observed_delta)[1:])
    )
    record(
        "exact_0_01_grid",
        observed_delta == expected_delta and exact_increment,
        f"observed_points={len(observed_delta)}, expected_points={len(expected_delta)}",
    )

    expected_candidates = (
        len(protocol["qubit_counts"])
        * len(protocol["depth_budgets"])
        * len(protocol["trotter_orders"])
        * len(expected_delta)
    )
    candidate_keys = [_candidate_key(row) for row in candidates]
    record(
        "candidate_table_complete_and_unique",
        len(candidates) == expected_candidates
        and len(set(candidate_keys)) == expected_candidates
        and int(completion["candidate_rows"]) == expected_candidates,
        f"rows={len(candidates)}, expected={expected_candidates}",
    )

    forbidden_columns = {
        column
        for column in (candidates[0] if candidates else {})
        if column.startswith("test_") and column != "test_metric_exposed"
    }
    no_test_values = all(row["test_metric_exposed"] == "False" for row in candidates)
    record(
        "candidate_selection_excludes_test_metrics",
        not forbidden_columns and no_test_values,
        f"forbidden_columns={sorted(forbidden_columns)}",
    )

    objective_errors: list[float] = []
    feasibility_ok = True
    infeasible_blank = True
    weights = (
        float(protocol["prediction_weight"]),
        float(protocol["state_infidelity_weight"]),
        float(protocol["kernel_error_weight"]),
        float(protocol["depth_weight"]),
    )
    for row in candidates:
        feasible = int(row["serial_depth_proxy"]) <= int(row["depth_budget"])
        feasibility_ok &= (row["feasible"] == "True") == feasible
        if not feasible:
            infeasible_blank &= row["objective"] == "" and row["depth_ratio"] == ""
            continue
        depth_ratio = int(row["serial_depth_proxy"]) / int(row["depth_budget"])
        expected = (
            weights[0] * (1.0 - float(row["validation_balanced_accuracy"]))
            + weights[1] * min(max(float(row["mean_state_infidelity"]), 0.0), 1.0)
            + weights[2]
            * min(max(float(row["kernel_relative_frobenius_error"]), 0.0), 1.0)
            + weights[3] * min(max(depth_ratio, 0.0), 1.0)
        )
        objective_errors.append(abs(float(row["objective"]) - expected))
    record(
        "feasibility_and_objective_recomputed",
        feasibility_ok
        and infeasible_blank
        and max(objective_errors, default=math.inf) <= 1e-12,
        f"max_objective_error={max(objective_errors, default=math.inf):.3e}",
    )

    expected_selections = (
        len(protocol["qubit_counts"])
        * len(protocol["depth_budgets"])
        * len(EXPECTED_OPTIMIZERS)
    )
    selection_keys = [_selection_key(row) for row in selections]
    selected_optimizer_sets: dict[tuple[int, int], set[str]] = {}
    for row in selections:
        condition = (int(row["n_qubits"]), int(row["depth_budget"]))
        selected_optimizer_sets.setdefault(condition, set()).add(row["optimizer"])
    record(
        "selection_table_complete_and_unique",
        len(selections) == expected_selections
        and len(set(selection_keys)) == expected_selections
        and all(value == EXPECTED_OPTIMIZERS for value in selected_optimizer_sets.values())
        and int(completion["selection_rows"]) == expected_selections,
        f"rows={len(selections)}, expected={expected_selections}",
    )

    candidates_by_key = {_candidate_key(row): row for row in candidates}
    selected_match = True
    test_isolation = True
    regret_ok = True
    for row in selections:
        key = (
            int(row["n_qubits"]),
            int(row["depth_budget"]),
            int(row["order"]),
            Decimal(row["delta_t"]),
        )
        candidate = candidates_by_key.get(key)
        selected_match &= (
            candidate is not None
            and candidate["feasible"] == "True"
            and abs(float(candidate["objective"]) - float(row["objective"])) <= 1e-12
        )
        test_isolation &= row["selection_used_test"] == "False" and math.isfinite(
            float(row["test_balanced_accuracy"])
        )
        regret_ok &= float(row["objective_regret_vs_grid"]) >= -1e-12
    record(
        "selected_candidates_exist_and_are_feasible",
        selected_match,
        "all selections map to a feasible candidate with the same objective",
    )
    record(
        "post_selection_test_evaluation",
        test_isolation and bool(completion["test_isolation_verified"]),
        "selection_used_test is false and each selected arm has a finite test metric",
    )

    grid_exact = True
    for n_qubits in protocol["qubit_counts"]:
        for depth_budget in protocol["depth_budgets"]:
            condition = [
                row
                for row in candidates
                if int(row["n_qubits"]) == int(n_qubits)
                and int(row["depth_budget"]) == int(depth_budget)
                and row["feasible"] == "True"
            ]
            expected = min(
                condition,
                key=lambda row: (
                    float(row["objective"]),
                    int(row["serial_depth_proxy"]),
                    int(row["order"]),
                    -float(row["delta_t"]),
                ),
            )
            selected = next(
                row
                for row in selections
                if int(row["n_qubits"]) == int(n_qubits)
                and int(row["depth_budget"]) == int(depth_budget)
                and row["optimizer"] == "grid_reference"
            )
            grid_exact &= (
                int(selected["order"]) == int(expected["order"])
                and Decimal(selected["delta_t"]) == Decimal(expected["delta_t"])
                and abs(float(selected["objective_regret_vs_grid"])) <= 1e-12
            )
    record(
        "grid_reference_is_exact_minimum",
        grid_exact and regret_ok,
        "tie-breaking and regret were independently checked",
    )

    optimizer_instances_ok = True
    pilot_reduction_ok = True
    for n_qubits in protocol["qubit_counts"]:
        for depth_budget in protocol["depth_budgets"]:
            path = output_dir / "optimizer_instances" / f"n{n_qubits}_depth{depth_budget}.json"
            payload = json.loads(path.read_text("utf-8"))
            optimizer_instances_ok &= payload.get("instance_hash") == _hash_without(
                payload, "instance_hash"
            )
            optimizer_instances_ok &= payload.get("objective_source") == "train_validation_only"
            variables = payload["variables"]
            normalized = payload["normalized_scores"]
            qubo = payload["qubo"]
            optimizer_instances_ok &= len(variables) == len(normalized)
            optimizer_instances_ok &= qubo["penalty"] == 2.0
            optimizer_instances_ok &= all(
                (int(n_qubits), int(depth_budget), int(value["order"]), Decimal(value["delta_t"]))
                in candidates_by_key
                for value in variables
            )
            condition_count = sum(
                row["feasible"] == "True"
                and int(row["n_qubits"]) == int(n_qubits)
                and int(row["depth_budget"]) == int(depth_budget)
                for row in candidates
            )
            pilot_reduction_ok &= len(payload["surrogate_pilots"]) < condition_count
            optimizer_instances_ok &= (
                payload["solver_results"]["simulated_annealing"]["execution"]
                == "classical_simulated_annealing_not_quantum_annealing"
                and payload["solver_results"]["qaoa_p1"]["execution"]
                == "exact_statevector_simulation_not_qpu"
            )
    record(
        "optimizer_instances_hashed_and_portable",
        optimizer_instances_ok,
        "QUBO manifests, candidate mapping, and solver execution labels checked",
    )
    record(
        "quadratic_surrogate_uses_reduced_pilot",
        pilot_reduction_ok,
        "every condition uses fewer pilot evaluations than feasible grid points",
    )

    hamiltonians_ok = True
    for n_qubits in protocol["qubit_counts"]:
        payload = json.loads(
            (output_dir / "hamiltonians" / f"n{n_qubits}.json").read_text("utf-8")
        )
        labels = [term["label"] for term in payload["terms"]]
        locality_limit = (
            int(n_qubits)
            if protocol["max_locality"] is None
            else int(protocol["max_locality"])
        )
        hamiltonians_ok &= payload.get("hamiltonian_hash") == _hash_without(
            payload, "hamiltonian_hash"
        )
        hamiltonians_ok &= payload["term_count"] == len(labels) == len(set(labels))
        hamiltonians_ok &= all(
            len(label) == int(n_qubits)
            and set(label) <= {"I", "X", "Y", "Z"}
            and 1 <= sum(symbol != "I" for symbol in label) <= locality_limit
            for label in labels
        )
    record(
        "hamiltonian_manifests_valid",
        hamiltonians_ok,
        "hashes, unique Pauli labels, dimensions, and locality checked",
    )

    record(
        "perfect_annotation_contract",
        annotation["label_noise"] == 0.0
        and annotation["balanced_classes"] is True
        and annotation["minimum_observed_margin"]
        >= annotation["minimum_requested_margin"]
        and len(annotation["dataset_sha256"]) == 64,
        (
            f"minimum_margin={annotation['minimum_observed_margin']:.6f}, "
            f"dataset_sha256={annotation['dataset_sha256']}"
        ),
    )
    expected_status = "descriptive_only" if protocol["profile"] == "smoke" else "tested"
    record(
        "inference_guardrail",
        analysis["status"] == expected_status
        and analysis["causal_claim_allowed"] is False,
        f"profile={protocol['profile']}, analysis_status={analysis['status']}",
    )
    record(
        "no_false_hardware_claim",
        "no QPU" in completion["qaoa_status"]
        and "no quantum annealer" in completion["annealing_status"],
        "QAOA and annealing arms are explicitly labeled as simulations",
    )

    required = (
        "report.md",
        "protocol.json",
        "completion.json",
        "candidates.csv",
        "selections.csv",
        "hypothesis_analysis.json",
        "annotation_manifest.json",
    )
    missing = [name for name in required if not (output_dir / name).is_file()]
    empty = [
        name
        for name in required
        if (output_dir / name).is_file() and not (output_dir / name).stat().st_size
    ]
    record(
        "required_artifacts_present",
        not missing and not empty,
        f"missing={missing}, empty={empty}",
    )

    metadata = {
        "profile": protocol["profile"],
        "protocol_hash": protocol_hash,
        "candidate_rows": len(candidates),
        "selection_rows": len(selections),
        "conditions": len(protocol["qubit_counts"]) * len(protocol["depth_budgets"]),
    }
    return checks, metadata


def write_results(
    output_dir: Path,
    checks: list[Check],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    passed = sum(check.passed for check in checks)
    status = "PASS" if passed == len(checks) else "FAIL"
    payload = {
        "status": status,
        "passed": passed,
        "total": len(checks),
        "metadata": metadata,
        "checks": [asdict(check) for check in checks],
    }
    (output_dir / "independent_audit.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Niezależny audyt frameworku skalowania Trottera",
        "",
        f"Status: **{status}** ({passed}/{len(checks)})",
        "",
        "| kontrola | wynik | szczegóły |",
        "|---|---|---|",
    ]
    for check in checks:
        result = "PASS" if check.passed else "FAIL"
        lines.append(
            f"| {check.name} | {result} | {check.detail.replace('|', chr(92) + '|')} |"
        )
    (output_dir / "independent_audit.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Independently audit Trotter-scaling benchmark artifacts"
    )
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    checks, metadata = run_audit(output_dir)
    result = write_results(output_dir, checks, metadata)
    print(
        json.dumps(
            {
                "status": result["status"],
                "passed": result["passed"],
                "total": result["total"],
                "failed": [
                    check.name for check in checks if not check.passed
                ],
            },
            indent=2,
        )
    )
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
