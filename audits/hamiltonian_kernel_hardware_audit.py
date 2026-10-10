from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKLOADS = (
    ROOT / "analysis_output" / "hamiltonian_kernel_hardware_smoke_fidelity",
    ROOT / "analysis_output" / "hamiltonian_kernel_hardware_smoke_projected",
    ROOT / "analysis_output" / "hamiltonian_kernel_hardware_native_compile",
)
DEFAULT_OUTPUT = ROOT / "analysis_output" / "hamiltonian_kernel_hardware_audit"

I2 = np.eye(2, dtype=np.complex128)
X2 = np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
Z2 = np.asarray([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def independent_workload_id(workload: dict[str, Any]) -> str:
    excluded = {"schema", "workload_id", "created_utc", "environment"}
    payload = {key: value for key, value in workload.items() if key not in excluded}
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def independent_edges(n_qubits: int, topology: str) -> tuple[tuple[int, int], ...]:
    if topology == "chain":
        return tuple((index, index + 1) for index in range(n_qubits - 1))
    if topology == "ring":
        chain = tuple((index, index + 1) for index in range(n_qubits - 1))
        return chain if n_qubits < 3 else chain + ((n_qubits - 1, 0),)
    if topology == "all_to_all":
        return tuple(
            (left, right)
            for left in range(n_qubits)
            for right in range(left + 1, n_qubits)
        )
    raise ValueError(f"Unsupported topology: {topology}")


def local_operator(matrix: np.ndarray, qubit: int, n_qubits: int) -> np.ndarray:
    factors = [matrix if index == qubit else I2 for index in reversed(range(n_qubits))]
    result = factors[0]
    for factor in factors[1:]:
        result = np.kron(result, factor)
    return result


def independent_trotter_state(x: np.ndarray, config: dict[str, Any]) -> np.ndarray:
    n_qubits = int(config["n_qubits"])
    z_operators = [local_operator(Z2, index, n_qubits) for index in range(n_qubits)]
    a_term = np.zeros((2**n_qubits, 2**n_qubits), dtype=np.complex128)
    for index, value in enumerate(x):
        a_term += float(value) * z_operators[index]
    coupling = float(config["interaction_strength"])
    for left, right in independent_edges(n_qubits, str(config["topology"])):
        a_term += coupling * (z_operators[left] @ z_operators[right])

    b_term = np.zeros_like(a_term)
    field = float(config["transverse_field"])
    for index in range(n_qubits):
        b_term += field * local_operator(X2, index, n_qubits)

    steps = int(config["trotter_steps"])
    step_time = float(config["evolution_time"]) / steps
    order = int(config["trotter_order"])
    initial = np.ones(2**n_qubits, dtype=np.complex128) / math.sqrt(2**n_qubits)
    if order == 1:
        a_step = expm(-1j * step_time * a_term)
        b_step = expm(-1j * step_time * b_term)
        state = initial
        for _ in range(steps):
            state = b_step @ (a_step @ state)
        return state
    if order == 2:
        half_a = expm(-0.5j * step_time * a_term)
        b_step = expm(-1j * step_time * b_term)
        state = initial
        for _ in range(steps):
            state = half_a @ (b_step @ (half_a @ state))
        return state
    raise ValueError(f"Unsupported Trotter order: {order}")


def state_distance_up_to_phase(reference: np.ndarray, actual: np.ndarray) -> float:
    overlap = np.vdot(reference, actual)
    phase = 1.0 if abs(overlap) < 1e-15 else np.exp(-1j * np.angle(overlap))
    return float(np.linalg.norm(reference - phase * actual))


def validation_binding_matches(workload: dict[str, Any]) -> tuple[bool, str]:
    binding = workload["study_binding"]
    try:
        bound_files = {
            "protocol": (
                Path(str(binding["protocol_path"])),
                str(binding["protocol_sha256"]),
            ),
            "completion": (
                Path(str(binding["benchmark_completion_path"])),
                str(binding["benchmark_completion_sha256"]),
            ),
            "outer_results": (
                Path(str(binding["outer_results_path"])),
                str(binding["outer_results_sha256"]),
            ),
            "outer_split": (
                Path(str(binding["outer_split_path"])),
                str(binding["outer_split_sha256"]),
            ),
        }
        for label, (path, expected_hash) in bound_files.items():
            if not path.is_file() or file_sha256(path) != expected_hash:
                return False, f"{label} file/hash mismatch"

        protocol = read_json(bound_files["protocol"][0])
        completion = read_json(bound_files["completion"][0])
        protocol_hash = str(binding["protocol_hash"])
        if (
            protocol.get("protocol_hash") != protocol_hash
            or completion.get("protocol_hash") != protocol_hash
            or completion.get("status") != "completed"
            or completion.get("qpu_gate")
            != "eligible_for_separate_reproducible_pilot_after_review"
            or completion.get("qpu_executed") is not False
        ):
            return False, "protocol/completion binding mismatch"

        with bound_files["outer_results"][0].open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            rows = [
                row
                for row in csv.DictReader(handle)
                if row["dataset"] == binding["dataset"]
                and int(row["outer_repeat"]) == int(binding["outer_repeat"])
                and int(row["outer_fold"]) == int(binding["outer_fold"])
                and row["family"] == workload["measurement"]["kernel"]
                and row["configuration_id"] == binding["configuration_id"]
            ]
        if not rows:
            return False, "bound selected configuration not found"
        configurations = {row["configuration_json"] for row in rows}
        if len(configurations) != 1:
            return False, "bound rows disagree on selected configuration"
        selected = json.loads(next(iter(configurations)))
        model = workload["model"]
        evolution = model["evolution_config"]
        candidate = selected["candidate"]
        comparisons = (
            selected["candidate_name"] == model["candidate"],
            math.isclose(float(candidate["evolution_time"]), float(evolution["evolution_time"])),
            math.isclose(
                float(candidate["interaction_strength"]),
                float(evolution["interaction_strength"]),
            ),
            math.isclose(
                float(candidate["transverse_field"]),
                float(evolution["transverse_field"]),
            ),
            candidate["topology"] == evolution["topology"],
            math.isclose(float(selected["regularization"]), float(model["regularization"])),
            selected["gamma"] == model["gamma"],
        )
        if not all(comparisons):
            return False, "workload model differs from bound selected configuration"

        with np.load(bound_files["outer_split"][0], allow_pickle=False) as split:
            if str(np.asarray(split["protocol_hash"]).item()) != protocol_hash:
                return False, "outer split protocol hash mismatch"
            for split_name in ("train", "test"):
                source_indices = np.asarray(split[f"{split_name}_indices"], dtype=int)
                source_x = np.asarray(split[f"x_{split_name}"], dtype=float)
                source_y = np.asarray(split[f"y_{split_name}"], dtype=int)
                index_to_position = {
                    int(index): position for position, index in enumerate(source_indices)
                }
                sample = workload["samples"][split_name]
                for original_index, values, label in zip(
                    sample["split_indices"], sample["x"], sample["y"]
                ):
                    position = index_to_position.get(int(original_index))
                    if position is None:
                        return False, f"{split_name} sample is outside bound split"
                    if not np.allclose(source_x[position], values, atol=1e-12):
                        return False, f"{split_name} feature differs from bound split"
                    if int(source_y[position]) != int(label):
                        return False, f"{split_name} label differs from bound split"
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        return False, f"invalid validation binding: {error}"
    return True, f"configuration_id={binding['configuration_id']}"


def selected_model_matches(workload: dict[str, Any]) -> tuple[bool, str]:
    if workload.get("study_binding", {}).get("tier") == "qpu_validation_of_completed_benchmark":
        return validation_binding_matches(workload)
    source = Path(str(workload["model"]["source_selected_results"]))
    if not source.is_file():
        return False, f"missing selected-model table: {source}"
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["dataset"] == workload["dataset"]["name"]
            and int(row["seed"]) == int(workload["dataset"]["seed"])
            and row["kernel"] == workload["measurement"]["kernel"]
        ]
    if len(rows) != 1:
        return False, f"selected rows={len(rows)}"
    row = rows[0]
    model = workload["model"]
    config = model["evolution_config"]
    comparisons = (
        row["candidate"] == model["candidate"],
        math.isclose(float(row["evolution_time"]), float(config["evolution_time"])),
        math.isclose(
            float(row["interaction_strength"]),
            float(config["interaction_strength"]),
        ),
        math.isclose(float(row["transverse_field"]), float(config["transverse_field"])),
        row["topology"] == config["topology"],
        math.isclose(float(row["regularization"]), float(model["regularization"])),
    )
    if model["gamma"] is not None:
        comparisons += (math.isclose(float(row["gamma"]), float(model["gamma"])),)
    return all(comparisons), f"candidate={row['candidate']}"


def expected_circuit_count(workload: dict[str, Any]) -> int:
    train_count = len(workload["samples"]["train"]["y"])
    total_count = train_count + len(workload["samples"]["test"]["y"])
    if workload["measurement"]["kernel"] == "fidelity":
        diagonal_is_measured = any(
            int(entry.get("left_index", -1)) == int(entry.get("right_index", -2))
            for entry in workload["measurement"]["entries"]
        )
        if diagonal_is_measured:
            return (
                train_count * (train_count + 1) // 2
                + (total_count - train_count) * train_count
                + (total_count - train_count)
            )
        return train_count * (train_count - 1) // 2 + (total_count - train_count) * train_count
    return 3 * total_count


def has_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if any(term in normalized for term in ("token", "password", "secret", "api_key")):
                return True
            if has_secret_key(item):
                return True
    elif isinstance(value, list):
        return any(has_secret_key(item) for item in value)
    return False


def execution_state_paths(
    workload_dir: Path,
    execution_name: str | None = None,
) -> list[Path]:
    if execution_name is None:
        return sorted(workload_dir.glob("*/execution.json"))
    candidate = workload_dir / execution_name / "execution.json"
    return [candidate] if candidate.is_file() else []


def validate_local_artifacts(
    workload_dir: Path,
    workload: dict[str, Any],
    execution_name: str | None = None,
) -> tuple[bool, list[str], set[str], list[float]]:
    entries = {
        str(entry["circuit_id"]): entry for entry in workload["measurement"]["entries"]
    }
    n_qubits = int(workload["model"]["evolution_config"]["n_qubits"])
    providers: set[str] = set()
    errors: list[float] = []
    problems: list[str] = []
    for state_path in execution_state_paths(workload_dir, execution_name):
        state = read_json(state_path)
        provider = str(state["provider"])
        providers.add(provider)
        if state["workload_id"] != workload["workload_id"]:
            problems.append(f"{provider}: workload mismatch")
        if state.get("dry_run"):
            if not state.get("not_a_qpu_execution", False):
                problems.append(f"{provider}: dry-run marked as QPU")
            if any(batch.get("job_id") for batch in state.get("batches", [])):
                problems.append(f"{provider}: dry-run contains remote job ID")
            expected_status = "prepared_only" if provider == "braket" else "compiled_only"
            if state.get("status") != expected_status:
                problems.append(
                    f"{provider}: dry-run status={state.get('status')}, expected={expected_status}"
                )
            continue

        if provider in {"aer", "pennylane", "braket-local", "ibm"}:
            if state.get("status") != "completed":
                problems.append(f"{provider}: status={state.get('status')}")
            if provider == "ibm":
                if state.get("not_a_qpu_execution", True):
                    problems.append("ibm: execution is not marked as a physical QPU run")
                if state.get("runtime_options", {}).get("execution", {}).get(
                    "init_qubits"
                ) is not True:
                    problems.append("ibm: runtime init_qubits is not explicit")
                initialization = state.get("qubit_initialization", {})
                if initialization.get("explicit_circuit_reset") is not True:
                    problems.append("ibm: explicit per-circuit reset is missing")
                layout = state.get("requested_initial_layout")
                if not isinstance(layout, list) or len(layout) != n_qubits:
                    problems.append("ibm: fixed physical layout is missing or incomplete")
                for batch in state.get("batches", []):
                    if not batch.get("job_id") or batch.get("status") != "completed":
                        problems.append("ibm: incomplete remote batch")
                    if batch.get("qpu_usage", {}).get("quantum_seconds") is None:
                        problems.append("ibm: QPU time is missing")
                    bundle = batch.get("reproducibility", {})
                    if bundle.get("runtime_options") != state.get("runtime_options"):
                        problems.append("ibm: runtime options differ between state and manifest")
                    if bundle.get("qubit_initialization") != initialization:
                        problems.append("ibm: initialization differs between state and manifest")
                    if bundle.get("requested_initial_layout") != layout:
                        problems.append("ibm: layout differs between state and manifest")
            else:
                if not state.get("not_a_qpu_execution", False):
                    problems.append(f"{provider}: local result marked as QPU")

            counts_path = state_path.with_name("counts.json")
            analysis_path = state_path.with_name("analysis.json")
            if not counts_path.is_file() or not analysis_path.is_file():
                problems.append(f"{provider}: missing counts or analysis")
                continue
            counts_payload = read_json(counts_path)
            counts = counts_payload["counts"]
            if set(counts) != set(entries):
                problems.append(f"{provider}: circuit ID mismatch")
                continue
            for circuit_id, entry in entries.items():
                histogram = counts[circuit_id]
                if sum(int(value) for value in histogram.values()) != int(entry["shots"]):
                    problems.append(f"{provider}/{circuit_id}: shot mismatch")
                if any(
                    len(bitstring) != n_qubits or set(bitstring) - {"0", "1"}
                    for bitstring in histogram
                ):
                    problems.append(f"{provider}/{circuit_id}: invalid canonical bitstring")

            analysis = read_json(analysis_path)
            train = np.asarray(analysis["train_kernel"], dtype=float)
            test = np.asarray(analysis["test_kernel"], dtype=float)
            train_count = len(workload["samples"]["train"]["y"])
            test_count = len(workload["samples"]["test"]["y"])
            if train.shape != (train_count, train_count) or test.shape != (
                test_count,
                train_count,
            ):
                problems.append(f"{provider}: kernel shape mismatch")
            if not np.all(np.isfinite(train)) or not np.all(np.isfinite(test)):
                problems.append(f"{provider}: non-finite kernel")
            if not np.allclose(train, train.T, atol=1e-10):
                problems.append(f"{provider}: asymmetric train kernel")
            if float(np.linalg.eigvalsh(0.5 * (train + train.T)).min()) < -1e-8:
                problems.append(f"{provider}: train kernel is not PSD")

            matrix_stages = analysis.get("kernel_matrices", {})
            required_stage_keys = {
                "raw_train",
                "raw_test",
                "raw_diagonal",
                "psd_train",
                "spectral_train",
                "spectral_test",
                "raw_eigenvalues",
                "psd_eigenvalues",
                "spectral_eigenvalues",
            }
            if not required_stage_keys.issubset(matrix_stages):
                missing = sorted(required_stage_keys - set(matrix_stages))
                problems.append(f"{provider}: missing kernel stages {missing}")
            else:
                if len(matrix_stages["raw_diagonal"]) != train_count + test_count:
                    problems.append(f"{provider}: incomplete measured/raw diagonal")
                if provider == "ibm" and workload["measurement"]["kernel"] == "fidelity":
                    raw_diagonal = np.asarray(matrix_stages["raw_diagonal"], dtype=float)
                    if (
                        not np.all(np.isfinite(raw_diagonal))
                        or float(raw_diagonal.min(initial=1.0)) < 0.9
                    ):
                        problems.append(
                            "ibm: fidelity raw diagonal is inconsistent with identity controls"
                        )
                for stage_name in ("psd_train", "spectral_train"):
                    stage = np.asarray(matrix_stages[stage_name], dtype=float)
                    if float(np.linalg.eigvalsh(0.5 * (stage + stage.T)).min()) < -1e-8:
                        problems.append(f"{provider}: {stage_name} is not PSD")

            ideal_train = np.asarray(analysis["ideal_train_kernel"], dtype=float)
            ideal_test = np.asarray(analysis["ideal_test_kernel"], dtype=float)
            train_error = float(
                np.linalg.norm(train - ideal_train, "fro")
                / max(np.linalg.norm(ideal_train, "fro"), 1e-12)
            )
            test_error = float(
                np.linalg.norm(test - ideal_test, "fro")
                / max(np.linalg.norm(ideal_test, "fro"), 1e-12)
            )
            reported = analysis["kernel_error"]
            if not math.isclose(
                train_error,
                float(reported["train_relative_frobenius"]),
                abs_tol=1e-12,
            ) or not math.isclose(
                test_error,
                float(reported["test_relative_frobenius"]),
                abs_tol=1e-12,
            ):
                problems.append(f"{provider}: kernel error was not reproduced")
            errors.extend((train_error, test_error))

            predictions = np.asarray(analysis["classification"]["predictions"], dtype=int)
            test_y = np.asarray(workload["samples"]["test"]["y"], dtype=int)
            accuracy = float(np.mean(predictions == test_y))
            if not math.isclose(
                accuracy,
                float(analysis["classification"]["test_accuracy"]),
                abs_tol=1e-12,
            ):
                problems.append(f"{provider}: test accuracy was not reproduced")
    return not problems, problems, providers, errors


def compile_for_fake_ibm(workload: dict[str, Any]) -> tuple[bool, str]:
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime.fake_provider import FakeTorino

    from hamiltonian_kernel.hardware_circuits import (
        build_qiskit_measurement_circuit,
        config_from_dict,
    )

    config = config_from_dict(workload["model"]["evolution_config"])
    samples = np.vstack(
        (
            np.asarray(workload["samples"]["train"]["x"], dtype=float),
            np.asarray(workload["samples"]["test"]["x"], dtype=float),
        )
    )
    entries = workload["measurement"]["entries"][:2]
    logical = [build_qiskit_measurement_circuit(row, samples, config) for row in entries]
    backend = FakeTorino()
    compiled = generate_preset_pass_manager(backend=backend, optimization_level=1).run(
        logical
    )
    circuits = compiled if isinstance(compiled, list) else [compiled]
    allowed = set(backend.target.operation_names) | {"barrier"}
    unsupported = sorted(
        {
            instruction.operation.name
            for circuit in circuits
            for instruction in circuit.data
            if instruction.operation.name not in allowed
        }
    )
    two_qubit = sum(
        1
        for circuit in circuits
        for instruction in circuit.data
        if len(instruction.qubits) == 2
    )
    return not unsupported, f"circuits={len(circuits)}, two_qubit={two_qubit}, unsupported={unsupported}"


def run_audit(
    workload_dirs: list[Path],
    execution_name: str | None = None,
) -> tuple[list[Check], dict[str, Any]]:
    workloads = [(path, read_json(path / "workload.json")) for path in workload_dirs]
    checks: list[Check] = []

    def record(name: str, condition: bool, detail: str) -> None:
        checks.append(Check(name, bool(condition), detail))

    identifiers_ok = all(
        workload["workload_id"] == independent_workload_id(workload)
        for _, workload in workloads
    )
    record("independent_workload_hashes", identifiers_ok, f"workloads={len(workloads)}")

    circuit_formula_ok = True
    exact_budget_ok = True
    qasm_ok = True
    balanced_subsets_ok = True
    selected_ok = True
    measured_fidelity_diagonal_ok = True
    selected_details: list[str] = []
    budgets_by_kernel: dict[str, set[int]] = {}
    for workload_dir, workload in workloads:
        measurement = workload["measurement"]
        entries = measurement["entries"]
        expected = expected_circuit_count(workload)
        circuit_formula_ok &= len(entries) == expected == int(measurement["circuit_count"])
        if (
            measurement["kernel"] == "fidelity"
            and workload.get("study_binding", {}).get("tier")
            == "qpu_validation_of_completed_benchmark"
        ):
            total_samples = len(workload["samples"]["train"]["y"]) + len(
                workload["samples"]["test"]["y"]
            )
            diagonal_indices = {
                int(entry["left_index"])
                for entry in entries
                if int(entry.get("left_index", -1))
                == int(entry.get("right_index", -2))
            }
            measured_fidelity_diagonal_ok &= diagonal_indices == set(
                range(total_samples)
            )
        shots = [int(entry["shots"]) for entry in entries]
        exact_budget_ok &= (
            sum(shots) == int(measurement["total_budget"])
            and max(shots) - min(shots) <= 1
            and len({str(entry["circuit_id"]) for entry in entries}) == len(entries)
        )
        budgets_by_kernel.setdefault(str(measurement["kernel"]), set()).add(
            int(measurement["total_budget"])
        )
        for entry in entries:
            relative = entry.get("logical_qasm")
            path = workload_dir / str(relative) if relative else None
            qasm_ok &= bool(
                path
                and path.is_file()
                and path.stat().st_size > 0
                and path.read_text(encoding="utf-8").lstrip().startswith("OPENQASM 3")
            )
        for split in ("train", "test"):
            counts = Counter(workload["samples"][split]["y"])
            balanced_subsets_ok &= len(set(counts.values())) == 1
        match, detail = selected_model_matches(workload)
        selected_ok &= match
        selected_details.append(f"{workload['workload_id']}: {detail}")

    record(
        "measurement_circuit_formulas",
        circuit_formula_ok,
        "fidelity upper triangle/cross/full diagonal; projected 3 per sample",
    )
    record(
        "measured_fidelity_diagonal",
        measured_fidelity_diagonal_ok,
        "every validation sample has an explicit fidelity diagonal circuit",
    )
    record("exact_measurement_budgets", exact_budget_ok, f"budgets={budgets_by_kernel}")
    common_budget = (
        {"fidelity", "projected"}.issubset(budgets_by_kernel)
        and all(len(values) == 1 for values in budgets_by_kernel.values())
        and len({next(iter(values)) for values in budgets_by_kernel.values()}) == 1
    )
    record("equal_fidelity_projected_budget", common_budget, f"budgets={budgets_by_kernel}")
    record("logical_qasm_complete", qasm_ok, "every manifest entry has a non-empty OpenQASM 3 file")
    record("balanced_frozen_subsets", balanced_subsets_ok, "equal class counts in train and test benchmark subsets")
    record("selected_models_frozen_from_grid", selected_ok, "; ".join(selected_details))
    record(
        "manifests_exclude_credentials",
        not any(has_secret_key(workload) for _, workload in workloads),
        "no token/password/secret/API-key fields",
    )

    max_state_distance = 0.0
    max_fidelity_error = 0.0
    from qiskit.quantum_info import Statevector

    from hamiltonian_kernel.hardware_circuits import (
        build_qiskit_feature_map,
        build_qiskit_measurement_circuit,
        config_from_dict,
    )

    for _, workload in workloads:
        config_dict = workload["model"]["evolution_config"]
        config = config_from_dict(config_dict)
        samples = np.vstack(
            (
                np.asarray(workload["samples"]["train"]["x"], dtype=float),
                np.asarray(workload["samples"]["test"]["x"], dtype=float),
            )
        )
        reference = independent_trotter_state(samples[0], config_dict)
        actual = Statevector.from_instruction(build_qiskit_feature_map(samples[0], config)).data
        max_state_distance = max(max_state_distance, state_distance_up_to_phase(reference, actual))
        if workload["measurement"]["kernel"] == "fidelity":
            entry = workload["measurement"]["entries"][0]
            circuit = build_qiskit_measurement_circuit(entry, samples, config)
            circuit.remove_final_measurements(inplace=True)
            observed = float(Statevector.from_instruction(circuit).probabilities()[0])
            left = independent_trotter_state(samples[int(entry["left_index"])], config_dict)
            right = independent_trotter_state(samples[int(entry["right_index"])], config_dict)
            expected = float(abs(np.vdot(right, left)) ** 2)
            max_fidelity_error = max(max_fidelity_error, abs(observed - expected))
    record("independent_trotter_equivalence", max_state_distance <= 1e-10, f"max_phase_aligned_distance={max_state_distance:.3e}")
    record("independent_fidelity_protocol", max_fidelity_error <= 1e-11, f"max_probability_error={max_fidelity_error:.3e}")

    all_providers: set[str] = set()
    all_local_errors: list[float] = []
    artifact_problems: list[str] = []
    native_zz_found = False
    for workload_dir, workload in workloads:
        valid, problems, providers, errors = validate_local_artifacts(
            workload_dir, workload, execution_name
        )
        if not valid:
            artifact_problems.extend(f"{workload_dir.name}: {problem}" for problem in problems)
        all_providers |= providers
        all_local_errors.extend(errors)
        for state_path in execution_state_paths(workload_dir, execution_name):
            state = read_json(state_path)
            if state.get("provider") == "ionq" and state.get("gateset") == "native":
                operations = Counter()
                for batch in state.get("batches", []):
                    operations.update(batch.get("compilation", {}).get("operation_totals", {}))
                native_zz_found |= operations["zz"] > 0
    record(
        "execution_artifact_integrity",
        not artifact_problems,
        "; ".join(artifact_problems) or "all selected execution artifacts consistent",
    )
    validation_mode = all(
        workload.get("study_binding", {}).get("tier")
        == "qpu_validation_of_completed_benchmark"
        for _, workload in workloads
    )
    required_providers = (
        {"ibm"}
        if execution_name is not None
        else {"aer"}
        if validation_mode
        else {"aer", "pennylane", "braket-local", "ionq", "braket"}
    )
    record(
        "provider_paths_exercised",
        required_providers.issubset(all_providers),
        f"required={sorted(required_providers)}, providers={sorted(all_providers)}",
    )
    record(
        "ionq_native_entangling_compile",
        validation_mode or native_zz_found,
        (
            "not applicable to IBM validation workloads"
            if validation_mode
            else "native-gate manifest contains at least one ZZ operation"
        ),
    )

    required_resource_axes = {
        "circuit_shots",
        "map_executions",
        "two_qubit_gate_shots",
        "qpu_time_seconds",
        "qpu_credits",
    }
    resource_axes_ok = True
    for workload_dir, _ in workloads:
        states = [
            read_json(path)
            for path in execution_state_paths(workload_dir, execution_name)
        ]
        resource_axes_ok &= any(
            required_resource_axes.issubset(state.get("resource_axes", {}))
            for state in states
        )
    record(
        "four_resource_axes_persisted",
        resource_axes_ok,
        "at least one execution per workload records shots, maps, 2Q-gate-shots, and QPU time/credits",
    )

    ibm_layouts = []
    for workload_dir, _ in workloads:
        for state_path in execution_state_paths(workload_dir, execution_name):
            state = read_json(state_path)
            if state.get("provider") == "ibm" and not state.get("dry_run"):
                ibm_layouts.append(tuple(state.get("requested_initial_layout") or ()))
    record(
        "ibm_common_physical_layout",
        not ibm_layouts or (len(ibm_layouts) == len(workloads) and len(set(ibm_layouts)) == 1),
        f"layouts={ibm_layouts}" if ibm_layouts else "not applicable",
    )

    interaction_workload = next(
        (
            workload
            for _, workload in workloads
            if float(workload["model"]["evolution_config"]["interaction_strength"]) > 0.0
        ),
        workloads[0][1],
    )
    ibm_ok, ibm_detail = compile_for_fake_ibm(interaction_workload)
    record("ibm_isa_transpilation", ibm_ok, ibm_detail)

    xanadu_ok = all(
        workload["xanadu_compatibility"]["direct_qubit_hamiltonian_kernel_supported"]
        is False
        and workload["xanadu_compatibility"]["software_validation"][
            "is_physical_xanadu_qpu"
        ]
        is False
        for _, workload in workloads
    )
    record("xanadu_model_boundary_explicit", xanadu_ok, "qubit workload is not mislabeled as an X8 execution")

    metadata = {
        "workload_dirs": [str(path) for path, _ in workloads],
        "workload_ids": [workload["workload_id"] for _, workload in workloads],
        "execution_name": execution_name,
        "providers": sorted(all_providers),
        "max_local_kernel_relative_error": max(all_local_errors, default=None),
        "limitations": [
            "No paid physical-QPU task is submitted by this audit.",
            "Balanced test-subset selection uses labels and is a hardware benchmark, not an unbiased population estimate.",
            "Equal circuit-shot budgets do not imply equal two-qubit gate counts or wall-clock cost.",
            "Xanadu X8 requires a separate CV/GBS model and cannot execute the qubit Ising workload directly.",
        ],
    }
    return checks, metadata


def write_results(output_dir: Path, checks: list[Check], metadata: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
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
        "# Niezalezny audyt implementacji sprzetowej",
        "",
        f"Status: **{status}** ({passed}/{len(checks)})",
        "",
        "| kontrola | wynik | szczegoly |",
        "|---|---|---|",
    ]
    for check in checks:
        detail = check.detail.replace("|", "\\|")
        lines.append(f"| {check.name} | {'PASS' if check.passed else 'FAIL'} | {detail} |")
    lines.extend(["", "## Ograniczenia", ""])
    lines.extend(f"- {item}" for item in metadata["limitations"])
    (output_dir / "independent_audit.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently audit Hamiltonian-kernel hardware artifacts"
    )
    parser.add_argument("workload_dirs", nargs="*", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--execution-name",
        help="Audit only the named execution subdirectory in each workload directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workload_dirs = [path.resolve() for path in (args.workload_dirs or DEFAULT_WORKLOADS)]
    missing = [str(path) for path in workload_dirs if not (path / "workload.json").is_file()]
    if missing:
        raise FileNotFoundError(f"Missing workload manifests: {missing}")
    checks, metadata = run_audit(workload_dirs, args.execution_name)
    write_results(args.output_dir.resolve(), checks, metadata)
    failed = [check.name for check in checks if not check.passed]
    print(
        json.dumps(
            {
                "status": "PASS" if not failed else "FAIL",
                "passed": len(checks) - len(failed),
                "total": len(checks),
                "failed": failed,
                "output_dir": str(args.output_dir.resolve()),
            },
            indent=2,
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
