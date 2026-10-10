from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from hamiltonian_kernel import core as system_under_test


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "analysis_output" / "hamiltonian_kernel_full"
AUDIT_DIR = ROOT / "analysis_output" / "hamiltonian_kernel_stage1_audit"

I2 = np.eye(2, dtype=np.complex128)
X2 = np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
Y2 = np.asarray([[0.0, -1j], [1j, 0.0]], dtype=np.complex128)
Z2 = np.asarray([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)


@dataclass(frozen=True)
class AuditCheck:
    name: str
    passed: bool
    detail: str


def independent_edges(n_qubits: int, topology: str) -> tuple[tuple[int, int], ...]:
    if topology == "chain":
        return tuple((index, index + 1) for index in range(n_qubits - 1))
    if topology == "ring":
        base = tuple((index, index + 1) for index in range(n_qubits - 1))
        return base if n_qubits < 3 else base + ((n_qubits - 1, 0),)
    if topology == "all_to_all":
        return tuple((left, right) for left in range(n_qubits) for right in range(left + 1, n_qubits))
    raise ValueError(topology)


def local_operator(matrix: np.ndarray, qubit: int, n_qubits: int) -> np.ndarray:
    factors = [matrix if index == qubit else I2 for index in reversed(range(n_qubits))]
    result = factors[0]
    for factor in factors[1:]:
        result = np.kron(result, factor)
    return result


def reference_hamiltonians(
    x: np.ndarray,
    interaction_strength: float,
    transverse_field: float,
    topology: str,
) -> tuple[np.ndarray, np.ndarray]:
    n_qubits = len(x)
    z_operators = [local_operator(Z2, qubit, n_qubits) for qubit in range(n_qubits)]
    a_term = sum((float(x[index]) * z_operators[index] for index in range(n_qubits)), start=np.zeros_like(z_operators[0]))
    for left, right in independent_edges(n_qubits, topology):
        a_term += interaction_strength * (z_operators[left] @ z_operators[right])
    b_term = sum(
        (transverse_field * local_operator(X2, qubit, n_qubits) for qubit in range(n_qubits)),
        start=np.zeros_like(a_term),
    )
    return a_term, b_term


def reference_plus_state(n_qubits: int) -> np.ndarray:
    plus = np.asarray([1.0, 1.0], dtype=np.complex128) / math.sqrt(2.0)
    state = plus
    for _ in range(n_qubits - 1):
        state = np.kron(state, plus)
    return state


def reference_evolution(
    x: np.ndarray,
    interaction_strength: float,
    transverse_field: float,
    topology: str,
    evolution_time: float,
    method: str,
    order: int = 2,
    steps: int = 2,
) -> np.ndarray:
    a_term, b_term = reference_hamiltonians(x, interaction_strength, transverse_field, topology)
    initial = reference_plus_state(len(x))
    if method == "exact":
        return expm(-1j * evolution_time * (a_term + b_term)) @ initial

    step_time = evolution_time / steps
    if order == 1:
        step = expm(-1j * step_time * b_term) @ expm(-1j * step_time * a_term)
    else:
        half_a = expm(-1j * 0.5 * step_time * a_term)
        step = half_a @ expm(-1j * step_time * b_term) @ half_a
    state = initial
    for _ in range(steps):
        state = step @ state
    return state


def state_distance_up_to_phase(left: np.ndarray, right: np.ndarray) -> float:
    overlap = np.vdot(left, right)
    if abs(overlap) < 1e-15:
        return float(np.linalg.norm(left - right))
    aligned = right * np.exp(-1j * np.angle(overlap))
    return float(np.linalg.norm(left - aligned))


def audit_quantum_math() -> list[AuditCheck]:
    checks: list[AuditCheck] = []
    rng = np.random.default_rng(71_331)
    max_exact_distance = 0.0
    max_trotter_distance = 0.0
    max_bloch_error = 0.0
    max_fidelity_kernel_error = 0.0
    max_projected_kernel_error = 0.0

    states: list[np.ndarray] = []
    reference_bloch: list[np.ndarray] = []
    for topology in ("chain", "ring", "all_to_all"):
        for _ in range(3):
            x = rng.uniform(-1.0, 1.0, size=3)
            common = {
                "n_qubits": 3,
                "evolution_time": 1.3,
                "transverse_field": 0.45,
                "interaction_strength": 0.8,
                "topology": topology,
            }
            exact_reference = reference_evolution(x, 0.8, 0.45, topology, 1.3, "exact")
            exact_actual = system_under_test.evolve_exact(
                x,
                system_under_test.EvolutionConfig(**common, method="exact"),
            )
            max_exact_distance = max(max_exact_distance, state_distance_up_to_phase(exact_reference, exact_actual))

            for order in (1, 2):
                trotter_reference = reference_evolution(x, 0.8, 0.45, topology, 1.3, "trotter", order, 3)
                trotter_actual = system_under_test.evolve_trotter(
                    x,
                    system_under_test.EvolutionConfig(**common, method="trotter", trotter_order=order, trotter_steps=3),
                )
                max_trotter_distance = max(
                    max_trotter_distance,
                    state_distance_up_to_phase(trotter_reference, trotter_actual),
                )

            states.append(exact_actual)
            local_values = np.empty((3, 3), dtype=float)
            for qubit in range(3):
                for component, pauli in enumerate((X2, Y2, Z2)):
                    operator = local_operator(pauli, qubit, 3)
                    local_values[qubit, component] = float(np.vdot(exact_reference, operator @ exact_reference).real)
            reference_bloch.append(local_values)

    state_matrix = np.vstack(states)
    actual_bloch = system_under_test.bloch_vectors(state_matrix, n_qubits=3)
    reference_bloch_array = np.asarray(reference_bloch)
    max_bloch_error = float(np.max(np.abs(actual_bloch - reference_bloch_array)))

    actual_fidelity = system_under_test.fidelity_kernel(state_matrix, state_matrix)
    reference_fidelity = np.empty_like(actual_fidelity)
    for left in range(len(states)):
        for right in range(len(states)):
            reference_fidelity[left, right] = abs(np.vdot(states[left], states[right])) ** 2
    max_fidelity_kernel_error = float(np.max(np.abs(actual_fidelity - reference_fidelity)))

    gamma = 0.7
    actual_projected = system_under_test.projected_kernel(actual_bloch, actual_bloch, gamma)
    reference_projected = np.empty_like(actual_projected)
    flat = reference_bloch_array.reshape(len(reference_bloch_array), -1)
    for left in range(len(flat)):
        for right in range(len(flat)):
            hs_distance = 0.5 * float(np.sum((flat[left] - flat[right]) ** 2))
            reference_projected[left, right] = math.exp(-gamma * hs_distance)
    max_projected_kernel_error = float(np.max(np.abs(actual_projected - reference_projected)))

    tolerance = 2e-12
    checks.extend(
        [
            AuditCheck("exact_vs_scipy_expm", max_exact_distance < tolerance, f"max phase-aligned distance={max_exact_distance:.3e}"),
            AuditCheck("trotter_vs_independent_matrix_product", max_trotter_distance < tolerance, f"max phase-aligned distance={max_trotter_distance:.3e}"),
            AuditCheck("bloch_vs_explicit_paulis", max_bloch_error < tolerance, f"max absolute error={max_bloch_error:.3e}"),
            AuditCheck("fidelity_kernel_vs_pairwise_definition", max_fidelity_kernel_error < tolerance, f"max absolute error={max_fidelity_kernel_error:.3e}"),
            AuditCheck("projected_kernel_vs_explicit_definition", max_projected_kernel_error < tolerance, f"max absolute error={max_projected_kernel_error:.3e}"),
        ]
    )
    return checks


def read_runs() -> list[dict[str, str]]:
    with (RESULTS_DIR / "runs.csv").open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_artifacts() -> list[AuditCheck]:
    rows = read_runs()
    metadata = json.loads((RESULTS_DIR / "summary.json").read_text(encoding="utf-8"))
    checks: list[AuditCheck] = []

    expected_run_count = len(metadata["datasets"]) * len(metadata["seeds"]) * len(metadata["variants"])
    checks.append(AuditCheck("complete_factorial_results", len(rows) == expected_run_count, f"rows={len(rows)}, expected={expected_run_count}"))

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    cells: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["variant"])].append(row)
        cells[(row["dataset"], int(row["seed"]))].append(row)

    complete_cells = all(len(cell_rows) == len(metadata["variants"]) for cell_rows in cells.values())
    checks.append(AuditCheck("all_variants_share_each_outer_split", complete_cells, f"cells={len(cells)}"))

    invariant_split_metadata = True
    for cell_rows in cells.values():
        signatures = {
            (
                row["n_train"],
                row["n_val"],
                row["n_test"],
                round(float(row["pca_explained_ratio"]), 14),
            )
            for row in cell_rows
        }
        invariant_split_metadata &= len(signatures) == 1
    checks.append(AuditCheck("paired_preprocessing_metadata", invariant_split_metadata, "sample counts and PCA ratio match within every dataset/seed cell"))

    summary_lookup = {(row["dataset"], row["variant"]): row for row in metadata["summary"]}
    max_summary_error = 0.0
    for key, group in grouped.items():
        values = np.asarray([float(row["test_balanced_accuracy"]) for row in group])
        reported = float(summary_lookup[key]["test_balanced_accuracy_mean"])
        max_summary_error = max(max_summary_error, abs(float(np.mean(values)) - reported))
    checks.append(AuditCheck("summary_recomputed_from_raw_csv", max_summary_error < 1e-14, f"max mean error={max_summary_error:.3e}"))

    resource_errors: list[str] = []
    for row in rows:
        n_train = int(row["n_train"])
        n_val = int(row["n_val"])
        n_test = int(row["n_test"])
        if row["kernel"] == "fidelity":
            expected_circuits = n_train * (n_train - 1) // 2 + (n_val + n_test) * n_train
        elif row["kernel"] == "projected":
            expected_circuits = 3 * (n_train + n_val + n_test)
        else:
            expected_circuits = 0
        if int(row["kernel_circuit_evaluations"]) != expected_circuits:
            resource_errors.append(f"{row['dataset']}/{row['variant']}/{row['seed']}")
        shots = 0 if not row["shots"] else int(row["shots"])
        if int(row["total_shots"]) != expected_circuits * shots:
            resource_errors.append(f"shots:{row['dataset']}/{row['variant']}/{row['seed']}")
    checks.append(AuditCheck("measurement_accounting", not resource_errors, "all rows match independent formulas" if not resource_errors else ", ".join(resource_errors[:5])))

    convergence_errors: list[str] = []
    for item in metadata["convergence"]:
        dataset = item["dataset"]
        order = int(item["trotter_order"])
        selected = sorted(
            (
                summary_lookup[(dataset, variant["name"])]
                for variant in metadata["variants"]
                if variant["method"] == "trotter"
                and variant["kernel"] == "fidelity"
                and variant["shots"] is None
                and int(variant["trotter_order"]) == order
            ),
            key=lambda row: int(row["trotter_steps"]),
        )
        slope = float(
            np.polyfit(
                np.log([int(row["trotter_steps"]) for row in selected]),
                np.log([float(row["mean_state_infidelity_mean"]) for row in selected]),
                1,
            )[0]
        )
        if abs(slope - float(item["log_log_slope"])) > 1e-12:
            convergence_errors.append(f"{dataset}/order{order}")
    checks.append(AuditCheck("convergence_recomputed", not convergence_errors, "all slopes reproduced" if not convergence_errors else ", ".join(convergence_errors)))

    return checks


def audit_source_protocol() -> tuple[list[AuditCheck], list[dict[str, str]]]:
    data_source = (ROOT / "hamiltonian_kernel" / "data.py").read_text(encoding="utf-8")
    experiment_source = (ROOT / "hamiltonian_kernel" / "experiment.py").read_text(encoding="utf-8")
    checks = [
        AuditCheck(
            "preprocessing_fit_on_train",
            all(
                marker in data_source
                for marker in (
                    "mean = x_train.mean(axis=0)",
                    "np.linalg.svd(x_train",
                    "minimum = x_train.min(axis=0)",
                )
            ),
            "standardization, PCA and scaling statistics originate from x_train",
        ),
        AuditCheck(
            "regularization_selected_before_test",
            experiment_source.index("select_regularization(") < experiment_source.index("test_prediction ="),
            "validation selection precedes the only test prediction in evaluate_variant",
        ),
        AuditCheck(
            "test_labels_not_used_for_hyperparameters",
            "data.y_test" not in experiment_source[experiment_source.index("def evaluate_variant") : experiment_source.index("test_prediction =")],
            "y_test is not referenced before final test prediction",
        ),
    ]
    findings = [
        {
            "severity": "medium",
            "id": "A1",
            "finding": "Finite-shot fidelity repairs only the training Gram matrix; validation/test cross-kernels do not share an explicit repaired feature map.",
            "required_action": "Treat PSD repair as a sensitivity analysis or replace it with a consistent feature-based estimator before drawing kernel-type conclusions.",
        },
        {
            "severity": "medium",
            "id": "A2",
            "finding": "Previous finite-shot comparisons equalized shots per circuit, not total measurement budget.",
            "required_action": "Allocate one fixed total budget per dataset/split and report realized budget for both kernel families.",
        },
        {
            "severity": "medium",
            "id": "A3",
            "finding": "Each split has one shot-noise realization, so split variability and measurement-noise variability are confounded.",
            "required_action": "Use multiple deterministic noise replicates within each selected outer split.",
        },
        {
            "severity": "medium",
            "id": "A4",
            "finding": "Repeated holdout splits overlap; sign-test p-values are descriptive and not based on independent observations.",
            "required_action": "Label these p-values descriptive; use repeated folds or dataset-level replication for confirmatory inference.",
        },
        {
            "severity": "high",
            "id": "A5",
            "finding": "A t/J/g/topology grid would leak test information if the best row were chosen from reported test scores.",
            "required_action": "Select the Hamiltonian configuration exclusively on train/validation inside each outer split, then evaluate its test kernel once.",
        },
    ]
    return checks, findings


def write_report(checks: list[AuditCheck], findings: list[dict[str, str]]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    failed = [check for check in checks if not check.passed]
    status = "FAIL" if failed else "PASS_WITH_REQUIRED_REMEDIATIONS"
    payload = {
        "status": status,
        "checks": [asdict(check) for check in checks],
        "findings": findings,
        "gate": {
            "may_continue": not failed,
            "condition": "Implement A1-A3 and A5 before running the next grid experiment; keep A4 explicit as a statistical limitation.",
        },
    }
    (AUDIT_DIR / "audit.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Niezależny audyt etapu bazowego Hamiltonian quantum kernel",
        "",
        f"Status: **{status}**",
        "",
        "## Kontrole niezależne",
        "",
        "| kontrola | wynik | szczegóły |",
        "|---|---|---|",
    ]
    for check in checks:
        lines.append(f"| {check.name} | {'PASS' if check.passed else 'FAIL'} | {check.detail} |")
    lines.extend(["", "## Ustalenia", ""])
    for finding in findings:
        lines.append(
            f"- **{finding['severity'].upper()} {finding['id']}**: {finding['finding']} "
            + f"Działanie: {finding['required_action']}"
        )
    lines.extend(
        [
            "",
            "## Decyzja bramkowa",
            "",
            "Matematyka i zapis artefaktów pozwalają kontynuować, ale eksperyment siatkowy może zostać uruchomiony dopiero po wdrożeniu A1-A3 i A5. A4 pozostaje jawnym ograniczeniem inferencji.",
        ]
    )
    (AUDIT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "checks": len(checks), "failed": len(failed), "findings": len(findings)}, indent=2))


def main() -> None:
    math_checks = audit_quantum_math()
    artifact_checks = audit_artifacts()
    protocol_checks, findings = audit_source_protocol()
    write_report(math_checks + artifact_checks + protocol_checks, findings)


if __name__ == "__main__":
    main()
