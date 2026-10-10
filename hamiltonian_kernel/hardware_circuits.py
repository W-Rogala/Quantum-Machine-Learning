from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np

from .core import (
    EvolutionConfig,
    bloch_vectors,
    evolve_batch,
    fidelity_kernel,
    interaction_edges,
    projected_kernel,
)
from .learning import (
    balanced_accuracy,
    fit_kernel_ridge,
    kernel_diagnostics,
    macro_f1,
    predict_kernel_ridge,
)
from .estimation import kernel_stages


MEASUREMENT_BASES = ("x", "y", "z")


@dataclass(frozen=True)
class GateOperation:
    name: str
    qubits: tuple[int, ...]
    angle: float | None = None


@dataclass(frozen=True)
class MeasurementEntry:
    circuit_id: str
    kind: str
    shots: int
    sample_index: int | None = None
    left_index: int | None = None
    right_index: int | None = None
    basis: str | None = None


def config_to_dict(config: EvolutionConfig) -> dict[str, Any]:
    return {
        "n_qubits": config.n_qubits,
        "evolution_time": config.evolution_time,
        "transverse_field": config.transverse_field,
        "interaction_strength": config.interaction_strength,
        "topology": config.topology,
        "method": config.method,
        "trotter_order": config.trotter_order,
        "trotter_steps": config.trotter_steps,
    }


def config_from_dict(values: dict[str, Any]) -> EvolutionConfig:
    config = EvolutionConfig(
        n_qubits=int(values["n_qubits"]),
        evolution_time=float(values["evolution_time"]),
        transverse_field=float(values["transverse_field"]),
        interaction_strength=float(values["interaction_strength"]),
        topology=str(values["topology"]),
        method="trotter",
        trotter_order=int(values.get("trotter_order", 2)),
        trotter_steps=int(values.get("trotter_steps", 2)),
    )
    config.validate()
    return config


def _diagonal_operations(
    x: np.ndarray,
    config: EvolutionConfig,
    duration: float,
) -> list[GateOperation]:
    operations = [
        GateOperation("rz", (qubit,), 2.0 * duration * float(value))
        for qubit, value in enumerate(x)
    ]
    if config.interaction_strength != 0.0:
        angle = 2.0 * duration * config.interaction_strength
        operations.extend(
            GateOperation("rzz", (left, right), angle)
            for left, right in interaction_edges(config.n_qubits, config.topology)
        )
    return operations


def feature_map_operations(x: np.ndarray, config: EvolutionConfig) -> list[GateOperation]:
    """Return gates for the same product formula used by ``evolve_trotter``."""

    config.validate()
    if config.method != "trotter":
        raise ValueError("Hardware circuits require a trotterized configuration")
    values = np.asarray(x, dtype=float)
    if values.shape != (config.n_qubits,):
        raise ValueError(f"Expected x with shape {(config.n_qubits,)}, got {values.shape}")

    operations = [GateOperation("h", (qubit,)) for qubit in range(config.n_qubits)]
    step_time = config.evolution_time / config.trotter_steps
    x_angle = 2.0 * config.transverse_field * step_time
    for _ in range(config.trotter_steps):
        if config.trotter_order == 1:
            operations.extend(_diagonal_operations(values, config, step_time))
            operations.extend(
                GateOperation("rx", (qubit,), x_angle)
                for qubit in range(config.n_qubits)
            )
        else:
            operations.extend(_diagonal_operations(values, config, 0.5 * step_time))
            operations.extend(
                GateOperation("rx", (qubit,), x_angle)
                for qubit in range(config.n_qubits)
            )
            operations.extend(_diagonal_operations(values, config, 0.5 * step_time))
    return operations


def inverse_operations(operations: Iterable[GateOperation]) -> list[GateOperation]:
    result: list[GateOperation] = []
    for operation in reversed(list(operations)):
        angle = None if operation.angle is None else -operation.angle
        result.append(GateOperation(operation.name, operation.qubits, angle))
    return result


def measurement_operations(
    entry: MeasurementEntry | dict[str, Any],
    samples: np.ndarray,
    config: EvolutionConfig,
) -> list[GateOperation]:
    values = asdict(entry) if isinstance(entry, MeasurementEntry) else entry
    kind = str(values["kind"])
    if kind == "fidelity":
        left = int(values["left_index"])
        right = int(values["right_index"])
        return feature_map_operations(samples[left], config) + inverse_operations(
            feature_map_operations(samples[right], config)
        )
    if kind != "projected":
        raise ValueError(f"Unsupported measurement kind: {kind}")

    sample_index = int(values["sample_index"])
    basis = str(values["basis"]).lower()
    operations = feature_map_operations(samples[sample_index], config)
    if basis == "x":
        operations.extend(GateOperation("h", (q,)) for q in range(config.n_qubits))
    elif basis == "y":
        # S-dagger followed by H rotates a Y measurement into the Z basis.
        for qubit in range(config.n_qubits):
            operations.append(GateOperation("rz", (qubit,), -0.5 * np.pi))
            operations.append(GateOperation("h", (qubit,)))
    elif basis != "z":
        raise ValueError(f"Unsupported measurement basis: {basis}")
    return operations


def qiskit_circuit_from_operations(
    operations: Iterable[GateOperation],
    n_qubits: int,
    name: str,
    measure: bool,
    initialize_qubits: bool = False,
):
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(n_qubits, n_qubits if measure else 0, name=name)
    if initialize_qubits:
        circuit.reset(range(n_qubits))
    for operation in operations:
        if operation.name == "h":
            circuit.h(operation.qubits[0])
        elif operation.name == "rx":
            circuit.rx(float(operation.angle), operation.qubits[0])
        elif operation.name == "rz":
            circuit.rz(float(operation.angle), operation.qubits[0])
        elif operation.name == "rzz":
            circuit.rzz(float(operation.angle), *operation.qubits)
        else:
            raise ValueError(f"Unsupported gate operation: {operation.name}")
    if measure:
        circuit.measure(range(n_qubits), range(n_qubits))
    return circuit


def build_qiskit_feature_map(x: np.ndarray, config: EvolutionConfig):
    return qiskit_circuit_from_operations(
        feature_map_operations(x, config),
        config.n_qubits,
        "hamiltonian_feature_map",
        measure=False,
    )


def build_qiskit_measurement_circuit(
    entry: MeasurementEntry | dict[str, Any],
    samples: np.ndarray,
    config: EvolutionConfig,
    initialize_qubits: bool = False,
):
    values = asdict(entry) if isinstance(entry, MeasurementEntry) else entry
    return qiskit_circuit_from_operations(
        measurement_operations(values, samples, config),
        config.n_qubits,
        str(values["circuit_id"]),
        measure=True,
        initialize_qubits=initialize_qubits,
    )


def build_braket_measurement_circuit(
    entry: MeasurementEntry | dict[str, Any],
    samples: np.ndarray,
    config: EvolutionConfig,
):
    from braket.circuits import Circuit

    circuit = Circuit()
    for operation in measurement_operations(entry, samples, config):
        if operation.name == "h":
            circuit.h(operation.qubits[0])
        elif operation.name == "rx":
            circuit.rx(operation.qubits[0], float(operation.angle))
        elif operation.name == "rz":
            circuit.rz(operation.qubits[0], float(operation.angle))
        elif operation.name == "rzz":
            left, right = operation.qubits
            circuit.cnot(left, right)
            circuit.rz(right, float(operation.angle))
            circuit.cnot(left, right)
        else:
            raise ValueError(f"Unsupported Braket operation: {operation.name}")
    return circuit


def allocate_exact_shots(
    circuit_count: int,
    total_budget: int,
    seed: int,
) -> np.ndarray:
    if circuit_count < 1:
        raise ValueError("circuit_count must be positive")
    if total_budget < circuit_count:
        raise ValueError(
            f"Budget {total_budget} cannot allocate one shot to {circuit_count} circuits"
        )
    base, remainder = divmod(total_budget, circuit_count)
    shots = np.full(circuit_count, base, dtype=np.int64)
    if remainder:
        rng = np.random.default_rng(seed)
        shots[rng.choice(circuit_count, size=remainder, replace=False)] += 1
    if int(shots.sum()) != total_budget:
        raise AssertionError("Shot allocation is not exact")
    return shots


def build_measurement_entries(
    kernel: str,
    train_count: int,
    total_count: int,
    total_budget: int,
    seed: int,
) -> list[MeasurementEntry]:
    if not 1 <= train_count < total_count:
        raise ValueError("Expected a non-empty train and test split")
    specifications: list[dict[str, Any]] = []
    if kernel == "fidelity":
        for left in range(train_count):
            for right in range(left, train_count):
                specifications.append(
                    {
                        "circuit_id": f"fid_train_{left:03d}_{right:03d}",
                        "kind": "fidelity",
                        "left_index": left,
                        "right_index": right,
                    }
                )
        for test_index in range(train_count, total_count):
            for train_index in range(train_count):
                specifications.append(
                    {
                        "circuit_id": f"fid_test_{test_index - train_count:03d}_{train_index:03d}",
                        "kind": "fidelity",
                        "left_index": test_index,
                        "right_index": train_index,
                    }
                )
            specifications.append(
                {
                    "circuit_id": f"fid_test_diag_{test_index - train_count:03d}",
                    "kind": "fidelity",
                    "left_index": test_index,
                    "right_index": test_index,
                }
            )
    elif kernel == "projected":
        for sample_index in range(total_count):
            for basis in MEASUREMENT_BASES:
                specifications.append(
                    {
                        "circuit_id": f"proj_{sample_index:03d}_{basis}",
                        "kind": "projected",
                        "sample_index": sample_index,
                        "basis": basis,
                    }
                )
    else:
        raise ValueError("kernel must be 'fidelity' or 'projected'")

    shots = allocate_exact_shots(len(specifications), total_budget, seed)
    entries = [
        MeasurementEntry(shots=int(entry_shots), **specification)
        for specification, entry_shots in zip(specifications, shots)
    ]
    if sum(entry.shots for entry in entries) != total_budget:
        raise AssertionError("Measurement entries do not realize the requested budget")
    return entries


def workload_identifier(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def canonical_counts(
    counts: dict[Any, Any],
    n_qubits: int,
    source_order: str,
) -> dict[str, int]:
    """Normalize count keys to strings ordered q0, q1, ..., q(n-1)."""

    normalized: dict[str, int] = {}
    for raw_key, raw_count in counts.items():
        text = str(raw_key).replace(" ", "").replace("_", "")
        if text.startswith("0x"):
            text = format(int(text, 16), f"0{n_qubits}b")
        elif text.startswith("0b"):
            text = text[2:]
        if any(character not in "01" for character in text):
            raise ValueError(f"Unsupported count key: {raw_key!r}")
        text = text.zfill(n_qubits)
        if len(text) != n_qubits:
            raise ValueError(f"Count key {raw_key!r} does not fit {n_qubits} qubits")
        if source_order == "qiskit":
            text = text[::-1]
        elif source_order != "q0_first":
            raise ValueError(f"Unsupported source bit order: {source_order}")
        normalized[text] = normalized.get(text, 0) + int(raw_count)
    return normalized


def zero_probability(counts: dict[str, int]) -> float:
    shots = sum(counts.values())
    if shots < 1:
        raise ValueError("Counts are empty")
    zero_key = "0" * len(next(iter(counts)))
    return counts.get(zero_key, 0) / shots


def local_pauli_expectations(counts: dict[str, int]) -> np.ndarray:
    shots = sum(counts.values())
    if shots < 1:
        raise ValueError("Counts are empty")
    n_qubits = len(next(iter(counts)))
    expectation = np.zeros(n_qubits, dtype=float)
    for bitstring, count in counts.items():
        if len(bitstring) != n_qubits:
            raise ValueError("Inconsistent bitstring lengths")
        expectation += int(count) * np.asarray(
            [1.0 if bit == "0" else -1.0 for bit in bitstring]
        )
    return expectation / shots


def validate_counts(
    entries: list[dict[str, Any]],
    counts_by_circuit: dict[str, dict[str, int]],
) -> None:
    expected_ids = {str(entry["circuit_id"]) for entry in entries}
    observed_ids = set(counts_by_circuit)
    if expected_ids != observed_ids:
        missing = sorted(expected_ids - observed_ids)
        extra = sorted(observed_ids - expected_ids)
        raise ValueError(f"Counts mismatch: missing={missing}, extra={extra}")
    for entry in entries:
        circuit_id = str(entry["circuit_id"])
        observed_shots = sum(int(value) for value in counts_by_circuit[circuit_id].values())
        if observed_shots != int(entry["shots"]):
            raise ValueError(
                f"Circuit {circuit_id} has {observed_shots} counts, expected {entry['shots']}"
            )


def _normalized_spectral_features(
    train_gram: np.ndarray,
    test_cross: np.ndarray,
    test_diagonal: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    stages = kernel_stages(train_gram)
    symmetric = stages.raw
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    negative_eigenmass = float(np.abs(eigenvalues[eigenvalues < 0.0]).sum())
    threshold = stages.spectral_threshold
    keep = eigenvalues > threshold
    if not np.any(keep):
        raise RuntimeError("No positive fidelity-kernel directions survived truncation")

    transform = eigenvectors[:, keep] / np.sqrt(eigenvalues[keep])[None, :]
    all_cross = np.vstack((symmetric, test_cross))
    features = all_cross @ transform
    norms = np.linalg.norm(features, axis=1)
    target_diagonal = np.concatenate(
        (
            np.maximum(np.diag(symmetric), 0.0),
            np.ones(len(test_cross), dtype=float)
            if test_diagonal is None
            else np.maximum(np.asarray(test_diagonal, dtype=float), 0.0),
        )
    )
    valid = norms > 1e-12
    features[valid] *= (np.sqrt(target_diagonal[valid]) / norms[valid])[:, None]
    features[~valid] = 0.0
    train_count = len(train_gram)
    spectral_all = features @ features.T
    return (
        features[:train_count],
        features[train_count:],
        {
            "spectral_rank": int(np.sum(keep)),
            "raw_negative_eigenmass": negative_eigenmass,
            "spectral_threshold": threshold,
            "raw_train": stages.raw.tolist(),
            "raw_test": np.asarray(test_cross, dtype=float).tolist(),
            "raw_diagonal": target_diagonal.tolist(),
            "psd_train": stages.psd.tolist(),
            "spectral_train": spectral_all[:train_count, :train_count].tolist(),
            "spectral_test": spectral_all[train_count:, :train_count].tolist(),
            "raw_eigenvalues": stages.raw_eigenvalues.tolist(),
            "psd_eigenvalues": stages.psd_eigenvalues.tolist(),
            "spectral_eigenvalues": stages.spectral_eigenvalues.tolist(),
        },
    )


def analyze_hardware_counts(
    workload: dict[str, Any],
    counts_by_circuit: dict[str, dict[str, int]],
) -> dict[str, Any]:
    entries = list(workload["measurement"]["entries"])
    validate_counts(entries, counts_by_circuit)
    config = config_from_dict(workload["model"]["evolution_config"])
    train_x = np.asarray(workload["samples"]["train"]["x"], dtype=float)
    test_x = np.asarray(workload["samples"]["test"]["x"], dtype=float)
    train_y = np.asarray(workload["samples"]["train"]["y"], dtype=int)
    test_y = np.asarray(workload["samples"]["test"]["y"], dtype=int)
    all_x = np.vstack((train_x, test_x))
    train_count = len(train_x)
    kernel_name = str(workload["measurement"]["kernel"])
    estimator_metadata: dict[str, Any]

    if kernel_name == "fidelity":
        raw_train = np.full((train_count, train_count), np.nan, dtype=float)
        raw_test = np.empty((len(test_x), train_count), dtype=float)
        test_diagonal = np.full(len(test_x), np.nan, dtype=float)
        for entry in entries:
            probability = zero_probability(counts_by_circuit[str(entry["circuit_id"])])
            left = int(entry["left_index"])
            right = int(entry["right_index"])
            if left < train_count and right < train_count:
                raw_train[left, right] = probability
                raw_train[right, left] = probability
            elif left >= train_count and right < train_count:
                raw_test[left - train_count, right] = probability
            elif left == right and left >= train_count:
                test_diagonal[left - train_count] = probability
            else:
                raise ValueError(f"Unsupported fidelity entry: {entry}")
        if not np.all(np.isfinite(raw_train)) or not np.all(np.isfinite(raw_test)):
            raise ValueError("Fidelity workload does not contain the complete raw train/cross matrix")
        if not np.all(np.isfinite(test_diagonal)):
            raise ValueError("Fidelity workload does not measure every test diagonal")
        train_features, test_features, estimator_metadata = _normalized_spectral_features(
            raw_train,
            raw_test,
            test_diagonal,
        )
        measured_train = train_features @ train_features.T
        measured_test = test_features @ train_features.T
        ideal_states = evolve_batch(all_x, config)
        ideal_train = fidelity_kernel(ideal_states[:train_count], ideal_states[:train_count])
        ideal_test = fidelity_kernel(ideal_states[train_count:], ideal_states[:train_count])
    else:
        estimated_bloch = np.empty((len(all_x), config.n_qubits, 3), dtype=float)
        basis_position = {basis: index for index, basis in enumerate(MEASUREMENT_BASES)}
        for entry in entries:
            sample_index = int(entry["sample_index"])
            basis_index = basis_position[str(entry["basis"])]
            estimated_bloch[sample_index, :, basis_index] = local_pauli_expectations(
                counts_by_circuit[str(entry["circuit_id"])]
            )
        gamma = float(workload["model"]["gamma"])
        measured_train = projected_kernel(
            estimated_bloch[:train_count], estimated_bloch[:train_count], gamma
        )
        measured_test = projected_kernel(
            estimated_bloch[train_count:], estimated_bloch[:train_count], gamma
        )
        ideal_states = evolve_batch(all_x, config)
        ideal_bloch = bloch_vectors(ideal_states, config.n_qubits)
        ideal_train = projected_kernel(
            ideal_bloch[:train_count], ideal_bloch[:train_count], gamma
        )
        ideal_test = projected_kernel(
            ideal_bloch[train_count:], ideal_bloch[:train_count], gamma
        )
        estimator_metadata = {"estimated_bloch": estimated_bloch.tolist()}
        _, _, projected_stages = _normalized_spectral_features(
            measured_train,
            measured_test,
            np.ones(len(test_x), dtype=float),
        )
        estimator_metadata.update(projected_stages)

    regularization = float(workload["model"]["regularization"])
    coefficients, classes = fit_kernel_ridge(measured_train, train_y, regularization)
    prediction = predict_kernel_ridge(measured_test, coefficients, classes)
    ideal_coefficients, ideal_classes = fit_kernel_ridge(ideal_train, train_y, regularization)
    ideal_prediction = predict_kernel_ridge(ideal_test, ideal_coefficients, ideal_classes)

    return {
        "workload_id": workload["workload_id"],
        "kernel": kernel_name,
        "measurement_budget": int(workload["measurement"]["total_budget"]),
        "train_kernel": measured_train.tolist(),
        "test_kernel": measured_test.tolist(),
        "ideal_train_kernel": ideal_train.tolist(),
        "ideal_test_kernel": ideal_test.tolist(),
        "kernel_matrices": {
            "raw_train": estimator_metadata["raw_train"],
            "raw_test": estimator_metadata["raw_test"],
            "raw_diagonal": estimator_metadata["raw_diagonal"],
            "psd_train": estimator_metadata["psd_train"],
            "spectral_train": estimator_metadata["spectral_train"],
            "spectral_test": estimator_metadata["spectral_test"],
            "raw_eigenvalues": estimator_metadata["raw_eigenvalues"],
            "psd_eigenvalues": estimator_metadata["psd_eigenvalues"],
            "spectral_eigenvalues": estimator_metadata["spectral_eigenvalues"],
        },
        "train_kernel_diagnostics": kernel_diagnostics(measured_train, regularization),
        "kernel_error": {
            "train_relative_frobenius": float(
                np.linalg.norm(measured_train - ideal_train, "fro")
                / max(np.linalg.norm(ideal_train, "fro"), 1e-12)
            ),
            "test_relative_frobenius": float(
                np.linalg.norm(measured_test - ideal_test, "fro")
                / max(np.linalg.norm(ideal_test, "fro"), 1e-12)
            ),
        },
        "classification": {
            "predictions": prediction.tolist(),
            "test_accuracy": float(np.mean(prediction == test_y)),
            "test_balanced_accuracy": balanced_accuracy(test_y, prediction, classes),
            "test_macro_f1": macro_f1(test_y, prediction, classes),
            "ideal_predictions": ideal_prediction.tolist(),
            "ideal_test_accuracy": float(np.mean(ideal_prediction == test_y)),
            "ideal_test_balanced_accuracy": balanced_accuracy(
                test_y, ideal_prediction, ideal_classes
            ),
        },
        "estimator": estimator_metadata,
    }
