from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

from scar_wine_qnn_benchmark import (  # noqa: E402
    MLP_PARAMETERS,
    N_CLASSES,
    N_QUBITS,
    QNN_PARAMETERS,
    READOUT_PARAMETERS,
    SCAR_LAYERS,
    SCAR_PARAMETERS,
    Adam,
    accuracy,
    cross_entropy,
    initialize_qnn,
    load_wine,
    macro_f1,
    mlp_probabilities,
    prepare_split,
    softmax,
    train_mlp,
)
from vqe_scar_ansatz_experiment import scar  # noqa: E402


DEFAULT_OUTPUT = ANALYSIS / "scar_wine_ibm_qpu_result.json"
DEFAULT_HISTORY = ANALYSIS / "scar_wine_ibm_qpu_history.csv"


@dataclass(frozen=True)
class CompiledScarCircuit:
    circuit: Any
    observables: np.ndarray
    data_parameters: tuple[Any, ...]
    weight_parameters: tuple[Any, ...]
    metadata: dict[str, Any]


def append_scar(
    circuit: Any,
    theta: Any,
    delta: Any,
    phi: Any,
    left: int,
    right: int,
) -> None:
    """Exact SCAR decomposition into standard parametric two-qubit rotations."""

    circuit.rz(-delta, right)
    circuit.rxx(theta, left, right)
    circuit.ryy(theta, left, right)
    circuit.rz(delta, right)
    circuit.rzz(phi, left, right)


def build_parameterized_scar_qnn() -> tuple[Any, tuple[Any, ...], tuple[Any, ...]]:
    from qiskit import QuantumCircuit
    from qiskit.circuit import ParameterVector

    data = ParameterVector("x", N_QUBITS)
    weights = ParameterVector("w", SCAR_PARAMETERS)
    circuit = QuantumCircuit(N_QUBITS, name="scar_wine_qnn")

    for qubit in range(N_QUBITS):
        circuit.ry(data[qubit], qubit)
        circuit.rz(data[qubit], qubit)

    edges = [(qubit, (qubit + 1) % N_QUBITS) for qubit in range(N_QUBITS)]
    offset = 0
    for _ in range(SCAR_LAYERS):
        local_ry = weights[offset : offset + N_QUBITS]
        offset += N_QUBITS
        local_rz = weights[offset : offset + N_QUBITS]
        offset += N_QUBITS
        exchange = weights[offset : offset + N_QUBITS]
        offset += N_QUBITS
        delta = weights[offset]
        phi = weights[offset + 1]
        offset += 2

        for qubit in range(N_QUBITS):
            circuit.ry(local_ry[qubit], qubit)
            circuit.rz(local_rz[qubit], qubit)
        for edge_index, (left, right) in enumerate(edges):
            append_scar(
                circuit,
                exchange[edge_index],
                delta,
                phi,
                left,
                right,
            )

    if offset != SCAR_PARAMETERS:
        raise AssertionError(f"Consumed {offset} of {SCAR_PARAMETERS} SCAR parameters")
    return circuit, tuple(data), tuple(weights)


def validate_scar_decomposition() -> float:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Operator

    theta, delta, phi = 0.37, -0.61, 0.29
    circuit = QuantumCircuit(2)
    append_scar(circuit, theta, delta, phi, 0, 1)
    actual = Operator(circuit).data
    expected = scar(theta, delta, phi)
    overlap = np.vdot(expected.reshape(-1), actual.reshape(-1))
    phase = overlap / abs(overlap)
    error = float(np.max(np.abs(actual - phase * expected)))
    if error > 1e-10:
        raise AssertionError(f"SCAR decomposition error is too large: {error}")
    return error


def _backend_name(backend: Any) -> str:
    value = getattr(backend, "name", str(backend))
    return str(value() if callable(value) else value)


def _processor_type(backend: Any) -> dict[str, Any]:
    try:
        processor = backend.configuration().processor_type
        if isinstance(processor, dict):
            return processor
        return {"value": str(processor)}
    except Exception:
        return {}


def _coupling_edges(backend: Any) -> list[tuple[int, int]]:
    coupling = getattr(backend, "coupling_map", None)
    if coupling is None:
        return []
    edges = coupling.get_edges() if hasattr(coupling, "get_edges") else coupling
    return [(int(left), int(right)) for left, right in edges]


def _two_qubit_error(backend: Any, left: int, right: int) -> float:
    target = getattr(backend, "target", None)
    if target is None:
        return 1.0
    errors: list[float] = []
    for operation_name in target.operation_names:
        try:
            operation = target.operation_from_name(operation_name)
            if int(operation.num_qubits) != 2:
                continue
            properties = target[operation_name].get((left, right))
            if properties is None:
                properties = target[operation_name].get((right, left))
            error = getattr(properties, "error", None)
            if error is not None:
                errors.append(float(error))
        except Exception:
            continue
    return min(errors) if errors else 1.0


def best_four_cycle(backend: Any) -> tuple[list[int] | None, float | None]:
    undirected: dict[int, set[int]] = {}
    for left, right in _coupling_edges(backend):
        undirected.setdefault(left, set()).add(right)
        undirected.setdefault(right, set()).add(left)

    candidates: dict[tuple[tuple[int, int], ...], list[int]] = {}
    for first, first_neighbors in undirected.items():
        for second in first_neighbors:
            for third in undirected.get(second, set()) - {first}:
                closing = (
                    undirected.get(third, set())
                    & undirected.get(first, set())
                    - {second}
                )
                for fourth in closing:
                    if len({first, second, third, fourth}) != 4:
                        continue
                    cycle = [first, second, third, fourth]
                    edge_key = tuple(
                        sorted(
                            tuple(sorted(edge))
                            for edge in [
                                (first, second),
                                (second, third),
                                (third, fourth),
                                (fourth, first),
                            ]
                        )
                    )
                    candidates.setdefault(edge_key, cycle)

    best_cycle: list[int] | None = None
    best_error: float | None = None
    for cycle in candidates.values():
        error = sum(
            _two_qubit_error(
                backend,
                cycle[index],
                cycle[(index + 1) % len(cycle)],
            )
            for index in range(len(cycle))
        )
        if best_error is None or error < best_error:
            best_cycle = cycle
            best_error = error
    return best_cycle, best_error


def _pending_jobs(backend: Any) -> int:
    try:
        return int(backend.status().pending_jobs)
    except Exception:
        return 10**9


def resolve_backend(service: Any, requested: str) -> tuple[Any, dict[str, Any]]:
    if requested not in {"auto", "least_busy"}:
        backend = service.backend(requested)
        cycle, cycle_error = best_four_cycle(backend)
        return backend, {
            "selection": "explicit",
            "four_cycle": cycle,
            "four_cycle_error_sum": cycle_error,
        }

    candidates = service.backends(
        operational=True,
        simulator=False,
        min_num_qubits=N_QUBITS,
    )
    if not candidates:
        raise RuntimeError("The IBM account has no operational QPU with at least 4 qubits.")

    ranked = []
    for backend in candidates:
        cycle, cycle_error = best_four_cycle(backend)
        ranked.append(
            (
                0 if cycle is not None else 1,
                _pending_jobs(backend),
                cycle_error if cycle_error is not None else float("inf"),
                _backend_name(backend),
                backend,
                cycle,
            )
        )
    ranked.sort(key=lambda item: item[:4])
    _, pending, cycle_error, _, backend, cycle = ranked[0]
    return backend, {
        "selection": "cycle_then_queue",
        "candidate_count": len(candidates),
        "pending_jobs_at_selection": pending,
        "four_cycle": cycle,
        "four_cycle_error_sum": (
            None if not math.isfinite(cycle_error) else cycle_error
        ),
    }


def compile_for_backend(
    backend: Any,
    optimization_level: int,
    seed: int,
) -> CompiledScarCircuit:
    from qiskit.quantum_info import SparsePauliOp
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    logical, data_parameters, weight_parameters = build_parameterized_scar_qnn()
    cycle, cycle_error = best_four_cycle(backend)
    pass_manager = generate_preset_pass_manager(
        backend=backend,
        optimization_level=optimization_level,
        initial_layout=cycle,
        seed_transpiler=seed,
    )
    isa_circuit = pass_manager.run(logical)
    logical_observables = [
        SparsePauliOp.from_sparse_list([("Z", [qubit], 1.0)], num_qubits=N_QUBITS)
        for qubit in range(N_QUBITS)
    ]
    laid_out_observables = [
        observable.apply_layout(isa_circuit.layout)
        for observable in logical_observables
    ]
    isa_observables = np.empty(len(laid_out_observables), dtype=object)
    for index, observable in enumerate(laid_out_observables):
        isa_observables[index] = observable

    backend_operations = set(getattr(backend, "operation_names", []))
    circuit_operations = set(isa_circuit.count_ops())
    ignored = {"barrier", "delay"}
    unsupported = sorted(circuit_operations - backend_operations - ignored)
    if unsupported:
        raise RuntimeError(f"Transpiled circuit is not ISA-compatible: {unsupported}")

    two_qubit_gates = 0
    for instruction in isa_circuit.data:
        if len(instruction.qubits) == 2:
            two_qubit_gates += 1

    metadata = {
        "backend": _backend_name(backend),
        "processor_type": _processor_type(backend),
        "num_physical_qubits": int(backend.num_qubits),
        "native_operations": sorted(backend_operations),
        "coupling_edge_count": len(_coupling_edges(backend)),
        "selected_physical_cycle": cycle,
        "selected_cycle_error_sum": cycle_error,
        "optimization_level": optimization_level,
        "transpiled_depth": int(isa_circuit.depth()),
        "transpiled_two_qubit_gate_count": int(two_qubit_gates),
        "transpiled_operation_counts": {
            str(name): int(count) for name, count in isa_circuit.count_ops().items()
        },
        "isa_compatible": True,
    }
    return CompiledScarCircuit(
        circuit=isa_circuit,
        observables=isa_observables,
        data_parameters=data_parameters,
        weight_parameters=weight_parameters,
        metadata=metadata,
    )


def fake_backend(name: str) -> Any:
    from qiskit_ibm_runtime.fake_provider import FakeNighthawk, FakeTorino

    if name == "nighthawk":
        return FakeNighthawk()
    if name == "heron":
        return FakeTorino()
    raise ValueError(name)


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_history(path: Path, history: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)


def initialize_service() -> Any:
    from qiskit_ibm_runtime import QiskitRuntimeService

    token = os.getenv("IBM_QUANTUM_TOKEN") or os.getenv("QISKIT_IBM_TOKEN")
    instance = os.getenv("IBM_QUANTUM_INSTANCE") or os.getenv("QISKIT_IBM_INSTANCE")
    kwargs: dict[str, Any] = {"channel": "ibm_quantum_platform"}
    if token:
        kwargs["token"] = token
    if instance:
        kwargs["instance"] = instance
    return QiskitRuntimeService(**kwargs)


def estimator_features(
    estimator: Any,
    compiled: CompiledScarCircuit,
    x: np.ndarray,
    circuit_weights: np.ndarray,
    precision: float | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    if circuit_weights.ndim == 1:
        circuit_weights = np.repeat(circuit_weights[None, :], len(x), axis=0)
    if circuit_weights.shape != (len(x), SCAR_PARAMETERS):
        raise ValueError(
            f"Expected circuit weights {(len(x), SCAR_PARAMETERS)}, "
            f"got {circuit_weights.shape}"
        )

    bindings = {
        compiled.data_parameters: np.asarray(x, dtype=float)[:, None, :],
        compiled.weight_parameters: np.asarray(circuit_weights, dtype=float)[
            :, None, :
        ],
    }
    observables = compiled.observables[None, :]
    publication = (compiled.circuit, observables, bindings)
    started = time.perf_counter()
    if precision is None:
        job = estimator.run([publication])
    else:
        job = estimator.run([publication], precision=precision)
    print(f"Submitted IBM Runtime job: {job.job_id()}", flush=True)
    result = job.result()
    elapsed = time.perf_counter() - started
    values = np.asarray(result[0].data.evs, dtype=float)
    values = np.clip(np.squeeze(values), -1.0, 1.0)
    if values.ndim == 1:
        values = values[None, :]
    metadata: dict[str, Any] = {
        "job_id": job.job_id(),
        "wall_seconds": elapsed,
        "pub_metadata": _json_ready(result[0].metadata),
    }
    try:
        metadata["job_metrics"] = _json_ready(job.metrics())
    except Exception:
        pass
    return values, metadata


def classifier_loss(
    features: np.ndarray,
    labels: np.ndarray,
    readout: np.ndarray,
    bias: np.ndarray,
) -> tuple[float, np.ndarray]:
    probabilities = softmax(features @ readout + bias)
    return cross_entropy(probabilities, labels), probabilities


def head_gradient(
    features: np.ndarray,
    labels: np.ndarray,
    readout: np.ndarray,
    bias: np.ndarray,
    weight_decay: float,
) -> np.ndarray:
    probabilities = softmax(features @ readout + bias)
    targets = np.zeros_like(probabilities)
    targets[np.arange(len(labels)), labels] = 1.0
    d_logits = (probabilities - targets) / len(labels)
    readout_gradient = features.T @ d_logits + weight_decay * readout
    bias_gradient = d_logits.sum(axis=0)
    return np.concatenate([readout_gradient.reshape(-1), bias_gradient])


def unpack_head(head: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    readout_count = N_QUBITS * N_CLASSES
    return (
        head[:readout_count].reshape(N_QUBITS, N_CLASSES),
        head[readout_count:],
    )


def model_metrics(
    features: np.ndarray,
    labels: np.ndarray,
    readout: np.ndarray,
    bias: np.ndarray,
) -> dict[str, Any]:
    loss, probabilities = classifier_loss(features, labels, readout, bias)
    prediction = np.argmax(probabilities, axis=1)
    confusion = np.zeros((N_CLASSES, N_CLASSES), dtype=int)
    for actual, predicted in zip(labels, prediction, strict=True):
        confusion[int(actual), int(predicted)] += 1
    return {
        "loss": loss,
        "accuracy": accuracy(probabilities, labels),
        "macro_f1": macro_f1(labels, prediction),
        "confusion": confusion.tolist(),
        "predictions": prediction.tolist(),
    }


def train_on_ibm_qpu(
    split: Any,
    compiled: CompiledScarCircuit,
    backend: Any,
    epochs: int,
    shots: int,
    seed: int,
    spsa_a: float,
    spsa_c: float,
    head_learning_rate: float,
    weight_decay: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from qiskit_ibm_runtime import Batch, EstimatorV2 as Estimator

    rng = np.random.default_rng(seed + 30_000)
    initialized = initialize_qnn(rng)
    circuit_weights = initialized[:SCAR_PARAMETERS].copy()
    readout_start = SCAR_PARAMETERS
    readout_end = readout_start + N_QUBITS * N_CLASSES
    head = np.concatenate([initialized[readout_start:readout_end], initialized[-N_CLASSES:]])
    head_optimizer = Adam.for_parameters(head)

    best_validation_loss = float("inf")
    best_epoch = 0
    best_circuit = circuit_weights.copy()
    best_head = head.copy()
    history: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []

    started = time.perf_counter()
    with Batch(backend=backend, max_time="10m") as batch:
        estimator = Estimator(mode=batch)
        estimator.options.default_shots = shots
        estimator.options.dynamical_decoupling.enable = True
        estimator.options.dynamical_decoupling.sequence_type = "XpXm"
        estimator.options.resilience.measure_mitigation = True

        for epoch in range(epochs):
            gain = spsa_a / (epoch + 1 + 0.1 * epochs) ** 0.602
            perturbation_size = spsa_c / (epoch + 1) ** 0.101
            direction = rng.choice(np.asarray([-1.0, 1.0]), size=SCAR_PARAMETERS)
            plus = circuit_weights + perturbation_size * direction
            minus = circuit_weights - perturbation_size * direction

            train_count = len(split.x_train)
            validation_count = len(split.x_val)
            all_x = np.concatenate(
                [split.x_train, split.x_train, split.x_val],
                axis=0,
            )
            all_weights = np.concatenate(
                [
                    np.repeat(plus[None, :], train_count, axis=0),
                    np.repeat(minus[None, :], train_count, axis=0),
                    np.repeat(circuit_weights[None, :], validation_count, axis=0),
                ],
                axis=0,
            )
            features, job_metadata = estimator_features(
                estimator,
                compiled,
                all_x,
                all_weights,
                precision=None,
            )
            job_metadata["epoch"] = epoch
            job_metadata["purpose"] = "spsa_plus_minus_and_validation"
            jobs.append(job_metadata)

            plus_features = features[:train_count]
            minus_features = features[train_count : 2 * train_count]
            validation_features = features[2 * train_count :]
            readout, bias = unpack_head(head)
            plus_loss, _ = classifier_loss(
                plus_features, split.y_train, readout, bias
            )
            minus_loss, _ = classifier_loss(
                minus_features, split.y_train, readout, bias
            )
            validation_loss, validation_probabilities = classifier_loss(
                validation_features, split.y_val, readout, bias
            )

            midpoint_features = 0.5 * (plus_features + minus_features)
            midpoint_loss, midpoint_probabilities = classifier_loss(
                midpoint_features, split.y_train, readout, bias
            )
            if validation_loss < best_validation_loss:
                best_validation_loss = validation_loss
                best_epoch = epoch
                best_circuit = circuit_weights.copy()
                best_head = head.copy()

            scalar_gradient = (plus_loss - minus_loss) / (
                2.0 * perturbation_size
            )
            circuit_gradient = scalar_gradient * direction
            circuit_gradient += weight_decay * circuit_weights
            circuit_weights -= gain * circuit_gradient

            head_grad = head_gradient(
                midpoint_features,
                split.y_train,
                readout,
                bias,
                weight_decay,
            )
            head = head_optimizer.update(head, head_grad, head_learning_rate)

            history.append(
                {
                    "epoch": epoch,
                    "train_loss": midpoint_loss,
                    "train_accuracy": accuracy(
                        midpoint_probabilities, split.y_train
                    ),
                    "validation_loss": validation_loss,
                    "validation_accuracy": accuracy(
                        validation_probabilities, split.y_val
                    ),
                    "spsa_gain": gain,
                    "spsa_perturbation": perturbation_size,
                    "job_id": job_metadata["job_id"],
                    "job_wall_seconds": job_metadata["wall_seconds"],
                }
            )

        combined_x = np.concatenate(
            [split.x_train, split.x_val, split.x_test],
            axis=0,
        )
        final_features, final_job = estimator_features(
            estimator,
            compiled,
            combined_x,
            best_circuit,
            precision=None,
        )
        final_job["epoch"] = best_epoch
        final_job["purpose"] = "best_checkpoint_evaluation"
        jobs.append(final_job)
    wall_seconds = time.perf_counter() - started

    train_end = len(split.x_train)
    validation_end = train_end + len(split.x_val)
    train_features = final_features[:train_end]
    validation_features = final_features[train_end:validation_end]
    test_features = final_features[validation_end:]
    best_readout, best_bias = unpack_head(best_head)

    result = {
        "model": "scar_qnn_ibm_qpu",
        "seed": seed,
        "epochs": epochs,
        "shots": shots,
        "parameters": QNN_PARAMETERS,
        "scar_parameters": SCAR_PARAMETERS,
        "readout_parameters": READOUT_PARAMETERS,
        "best_epoch": best_epoch,
        "wall_seconds": wall_seconds,
        "pca_explained": split.pca_explained,
        "train": model_metrics(
            train_features, split.y_train, best_readout, best_bias
        ),
        "validation": model_metrics(
            validation_features, split.y_val, best_readout, best_bias
        ),
        "test": model_metrics(
            test_features, split.y_test, best_readout, best_bias
        ),
        "job_count": len(jobs),
        "jobs": jobs,
    }
    return result, history


def run_classical_reference(split: Any, seed: int) -> dict[str, Any]:
    result, _ = train_mlp(
        split,
        seed=seed,
        epochs=160,
        learning_rate=0.035,
        weight_decay=1e-4,
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Architecture-aware SCAR-QNN training on an IBM Quantum QPU."
    )
    parser.add_argument("--backend", default="auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--shots", type=int, default=256)
    parser.add_argument("--optimization-level", type=int, default=3)
    parser.add_argument("--spsa-a", type=float, default=0.12)
    parser.add_argument("--spsa-c", type=float, default=0.15)
    parser.add_argument("--head-learning-rate", type=float, default=0.04)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument(
        "--offline-compile-check",
        choices=["nighthawk", "heron"],
        default=None,
        help="Compile against a frozen IBM fake backend; never submits a QPU job.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    decomposition_error = validate_scar_decomposition()
    x, y = load_wine()
    split = prepare_split(x, y, args.seed)

    if args.offline_compile_check:
        backend = fake_backend(args.offline_compile_check)
        selection = {
            "selection": "offline_frozen_backend",
            "not_a_qpu_execution": True,
        }
    else:
        service = initialize_service()
        backend, selection = resolve_backend(service, args.backend)

    compiled = compile_for_backend(
        backend,
        optimization_level=args.optimization_level,
        seed=args.seed,
    )
    payload: dict[str, Any] = {
        "execution_status": "compiled_only" if args.dry_run else "pending",
        "decomposition_max_error": decomposition_error,
        "dataset": {
            "name": "UCI Wine",
            "samples": int(len(x)),
            "features": int(x.shape[1]),
            "classes": int(len(np.unique(y))),
            "split_seed": args.seed,
            "train_samples": int(len(split.x_train)),
            "validation_samples": int(len(split.x_val)),
            "test_samples": int(len(split.x_test)),
            "pca_explained": split.pca_explained,
        },
        "selection": selection,
        "architecture": compiled.metadata,
        "training_protocol": {
            "optimizer": "SPSA circuit + Adam classical readout",
            "epochs": args.epochs,
            "shots": args.shots,
            "spsa_a": args.spsa_a,
            "spsa_c": args.spsa_c,
            "head_learning_rate": args.head_learning_rate,
            "estimated_parameterized_circuit_configurations": (
                args.epochs
                * (2 * len(split.x_train) + len(split.x_val))
                + len(split.x_train)
                + len(split.x_val)
                + len(split.x_test)
            ),
        },
    }

    if args.dry_run:
        write_json(args.output, payload)
        print(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False))
        return

    if args.offline_compile_check:
        raise RuntimeError(
            "--offline-compile-check can validate compilation only. "
            "Use an authenticated IBM backend for a QPU execution."
        )

    print(
        "Starting IBM QPU training on "
        f"{compiled.metadata['backend']} "
        f"({compiled.metadata['processor_type']}); "
        f"depth={compiled.metadata['transpiled_depth']}, "
        f"two_qubit_gates={compiled.metadata['transpiled_two_qubit_gate_count']}",
        flush=True,
    )
    qpu_result, history = train_on_ibm_qpu(
        split,
        compiled,
        backend,
        epochs=args.epochs,
        shots=args.shots,
        seed=args.seed,
        spsa_a=args.spsa_a,
        spsa_c=args.spsa_c,
        head_learning_rate=args.head_learning_rate,
        weight_decay=args.weight_decay,
    )
    classical = run_classical_reference(split, args.seed)
    payload["execution_status"] = "completed_on_ibm_qpu"
    payload["qpu_result"] = qpu_result
    payload["classical_reference"] = classical
    payload["comparison"] = {
        "test_accuracy_qpu_minus_mlp": (
            qpu_result["test"]["accuracy"] - classical["test_accuracy"]
        ),
        "test_macro_f1_qpu_minus_mlp": (
            qpu_result["test"]["macro_f1"] - classical["test_macro_f1"]
        ),
    }
    write_json(args.output, payload)
    write_history(args.history, history)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.history}")
    print(f"IBM backend: {compiled.metadata['backend']}")
    print(f"QPU test accuracy: {qpu_result['test']['accuracy']:.3f}")
    print(f"MLP test accuracy: {classical['test_accuracy']:.3f}")


if __name__ == "__main__":
    main()
