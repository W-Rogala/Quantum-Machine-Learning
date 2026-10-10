from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

import ansatz_hardware_dataset_benchmark as benchmark  # noqa: E402


DEFAULT_RESULTS = ANALYSIS / "ansatz_hardware_dataset_hpo_results.csv"
DEFAULT_BEST = ANALYSIS / "ansatz_hardware_dataset_hpo_best_hyperparameters.csv"
DEFAULT_OUTPUT = ANALYSIS / "best_hpo_tree_tensor_ibm_qpu_result.json"
DEFAULT_SAMPLES = ANALYSIS / "best_hpo_tree_tensor_ibm_qpu_samples.csv"
DEFAULT_REPORT = ANALYSIS / "best_hpo_tree_tensor_ibm_qpu_report.md"
DEFAULT_MODEL = ANALYSIS / "best_hpo_tree_tensor_ibm_local_model.npz"
DEFAULT_PENDING = ANALYSIS / "best_hpo_tree_tensor_ibm_qpu_pending.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def backend_name(backend: Any) -> str:
    name = getattr(backend, "name", str(backend))
    return str(name() if callable(name) else name)


def pending_jobs(backend: Any) -> int:
    try:
        return int(backend.status().pending_jobs)
    except Exception:
        return 10**9


def coupling_edges(backend: Any) -> list[tuple[int, int]]:
    coupling = getattr(backend, "coupling_map", None)
    if coupling is None:
        return []
    edges = coupling.get_edges() if hasattr(coupling, "get_edges") else coupling
    return [(int(left), int(right)) for left, right in edges]


def two_qubit_error(backend: Any, left: int, right: int) -> float:
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


def best_tree_layout(backend: Any) -> tuple[list[int] | None, float | None]:
    neighbors: dict[int, set[int]] = {}
    for left, right in coupling_edges(backend):
        neighbors.setdefault(left, set()).add(right)
        neighbors.setdefault(right, set()).add(left)

    best_layout: list[int] | None = None
    best_error: float | None = None
    # Logical interaction path is q0-q1-q3-q2.
    for p0, adjacent0 in neighbors.items():
        for p1 in adjacent0:
            for p3 in neighbors.get(p1, set()) - {p0}:
                for p2 in neighbors.get(p3, set()) - {p0, p1}:
                    if len({p0, p1, p2, p3}) != 4:
                        continue
                    error = (
                        two_qubit_error(backend, p0, p1)
                        + two_qubit_error(backend, p1, p3)
                        + two_qubit_error(backend, p3, p2)
                    )
                    if best_error is None or error < best_error:
                        best_error = error
                        best_layout = [p0, p1, p2, p3]
    return best_layout, best_error


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


def select_backend(service: Any, requested: str) -> tuple[Any, dict[str, Any]]:
    if requested not in {"auto", "least_busy"}:
        backend = service.backend(requested)
        layout, error = best_tree_layout(backend)
        return backend, {
            "selection": "explicit",
            "tree_layout": layout,
            "tree_layout_error_sum": error,
            "pending_jobs": pending_jobs(backend),
        }

    candidates = service.backends(
        operational=True,
        simulator=False,
        min_num_qubits=benchmark.N_QUBITS,
    )
    if not candidates:
        raise RuntimeError("No operational IBM QPU with at least four qubits.")
    ranked: list[tuple[Any, ...]] = []
    for backend in candidates:
        layout, error = best_tree_layout(backend)
        ranked.append(
            (
                0 if layout is not None else 1,
                error if error is not None else float("inf"),
                pending_jobs(backend),
                backend_name(backend),
                backend,
                layout,
            )
        )
    ranked.sort(key=lambda item: item[:4])
    _, error, queue, _, backend, layout = ranked[0]
    return backend, {
        "selection": "lowest_tree_error_then_queue",
        "candidate_count": len(candidates),
        "tree_layout": layout,
        "tree_layout_error_sum": None if not math.isfinite(error) else error,
        "pending_jobs": queue,
    }


def select_best_ibm_case(
    results_path: Path, best_path: Path
) -> tuple[dict[str, str], dict[str, float | str]]:
    ibm_rows = [row for row in read_csv(results_path) if row["provider"] == "ibm"]
    if not ibm_rows:
        raise RuntimeError("No IBM rows in HPO results.")
    selected = min(
        ibm_rows,
        key=lambda row: (
            -float(row["test_balanced_accuracy_profile_shots"]),
            int(float(row["two_qubit_gates"])),
            int(float(row["estimated_depth"])),
            row["dataset"],
            row["ansatz"],
        ),
    )
    if selected["dataset"] != "wine" or selected["ansatz"] != "tree_tensor":
        raise RuntimeError(
            "The QPU runner implements the current best case, Wine + tree_tensor, "
            f"but the selected row is {selected['dataset']} + {selected['ansatz']}."
        )
    matches = [
        row
        for row in read_csv(best_path)
        if row["dataset"] == selected["dataset"]
        and row["ansatz"] == selected["ansatz"]
        and row["provider"] == "ibm"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one best-hyperparameter row, found {len(matches)}.")
    source = matches[0]
    hyperparameters: dict[str, float | str] = {
        "candidate_id": source["candidate_id"],
        "quantum_learning_rate": float(source["quantum_learning_rate"]),
        "head_learning_rate": float(source["head_learning_rate"]),
        "spsa_perturbation": float(source["spsa_perturbation"]),
        "weight_decay": float(source["weight_decay"]),
        "initialization_scale": float(source["initialization_scale"]),
        "input_scale": float(source["input_scale"]),
    }
    return selected, hyperparameters


def recreate_model(
    selected: dict[str, str],
    hyperparameters: dict[str, float | str],
    seed: int,
    samples_per_class: int,
    shots: int,
    model_output: Path,
) -> tuple[
    benchmark.PreparedDataset,
    dict[str, object],
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    raw = benchmark.load_wine()
    sampled = benchmark.balanced_subsample(raw, samples_per_class, seed)
    dataset = benchmark.prepare_dataset(sampled, seed)
    spec = benchmark.ANSATZE["tree_tensor"]
    profile = benchmark.PROVIDERS["ibm"]
    epochs = int(float(selected["epochs"]))
    local_result, _ = benchmark.train_configuration(
        dataset,
        spec,
        profile,
        epochs,
        shots,
        seed,
        hyperparameters,
        evaluate_test=True,
        model_output_path=model_output,
    )
    expected = float(selected["test_balanced_accuracy_profile_shots"])
    recreated = float(local_result["test_balanced_accuracy_profile_shots"])
    if abs(expected - recreated) > 1e-12:
        raise RuntimeError(
            f"Recreated result {recreated} does not match selected result {expected}."
        )
    model = np.load(model_output)
    return (
        dataset,
        local_result,
        np.asarray(model["theta"], dtype=float),
        np.asarray(model["weights"], dtype=float),
        np.asarray(model["bias"], dtype=float),
    )


def build_tree_tensor_circuit(input_scale: float) -> tuple[Any, tuple[Any, ...], tuple[Any, ...]]:
    from qiskit import QuantumCircuit
    from qiskit.circuit import ParameterVector

    data = ParameterVector("x", benchmark.N_QUBITS)
    theta = ParameterVector("theta", 9)
    circuit = QuantumCircuit(benchmark.N_QUBITS, name="best_hpo_tree_tensor")
    for qubit in range(benchmark.N_QUBITS):
        circuit.ry(input_scale * data[qubit], qubit)
    cursor = 0
    for left, right in [(0, 1), (2, 3), (1, 3)]:
        circuit.ry(theta[cursor], left)
        circuit.ry(theta[cursor + 1], right)
        circuit.cx(left, right)
        circuit.ry(theta[cursor + 2], right)
        cursor += 3
    return circuit, tuple(data), tuple(theta)


def compile_circuit(
    backend: Any,
    input_scale: float,
    optimization_level: int,
    seed: int,
    initial_layout: list[int] | None,
) -> tuple[Any, np.ndarray, tuple[Any, ...], tuple[Any, ...], dict[str, Any]]:
    from qiskit.quantum_info import SparsePauliOp
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    logical, data_parameters, theta_parameters = build_tree_tensor_circuit(input_scale)
    pass_manager = generate_preset_pass_manager(
        backend=backend,
        optimization_level=optimization_level,
        initial_layout=initial_layout,
        seed_transpiler=seed,
    )
    isa_circuit = pass_manager.run(logical)
    logical_observables = [
        SparsePauliOp.from_sparse_list(
            [("Z", [qubit], 1.0)], num_qubits=benchmark.N_QUBITS
        )
        for qubit in range(benchmark.N_QUBITS)
    ]
    observables = np.empty(benchmark.N_QUBITS, dtype=object)
    for index, observable in enumerate(logical_observables):
        observables[index] = observable.apply_layout(isa_circuit.layout)

    backend_operations = set(getattr(backend, "operation_names", []))
    circuit_operations = set(isa_circuit.count_ops())
    unsupported = sorted(circuit_operations - backend_operations - {"barrier", "delay"})
    if unsupported:
        raise RuntimeError(f"Transpiled circuit is not ISA-compatible: {unsupported}")
    two_qubit_count = sum(
        1 for instruction in isa_circuit.data if len(instruction.qubits) == 2
    )
    processor_type: dict[str, Any] = {}
    try:
        raw_processor = backend.configuration().processor_type
        processor_type = (
            raw_processor
            if isinstance(raw_processor, dict)
            else {"value": str(raw_processor)}
        )
    except Exception:
        pass
    metadata = {
        "backend": backend_name(backend),
        "processor_type": processor_type,
        "num_physical_qubits": int(backend.num_qubits),
        "native_operations": sorted(backend_operations),
        "initial_layout": initial_layout,
        "transpiled_depth": int(isa_circuit.depth()),
        "transpiled_two_qubit_gate_count": int(two_qubit_count),
        "transpiled_operation_counts": {
            str(name): int(count) for name, count in isa_circuit.count_ops().items()
        },
        "isa_compatible": True,
    }
    return isa_circuit, observables, data_parameters, theta_parameters, metadata


def confusion_matrix(y: np.ndarray, predicted: np.ndarray, classes: int) -> list[list[int]]:
    matrix = np.zeros((classes, classes), dtype=int)
    for actual, prediction in zip(y, predicted):
        matrix[int(actual), int(prediction)] += 1
    return matrix.tolist()


def evaluate(
    features: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    bias: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    probabilities = benchmark.predictions(features, weights, bias)
    predicted = np.argmax(probabilities, axis=1)
    metrics = benchmark.classification_metrics(y, predicted)
    metrics.update(
        {
            "loss": benchmark.cross_entropy(probabilities, y),
            "confusion": confusion_matrix(y, predicted, probabilities.shape[1]),
            "predictions": predicted.tolist(),
        }
    )
    return metrics, probabilities, predicted


def write_samples(
    path: Path,
    dataset: benchmark.PreparedDataset,
    features: np.ndarray,
    probabilities: np.ndarray,
    predicted: np.ndarray,
) -> None:
    rows: list[dict[str, Any]] = []
    for index in range(len(dataset.y_test)):
        row: dict[str, Any] = {
            "sample": index,
            "true_label": int(dataset.y_test[index]),
            "predicted_label": int(predicted[index]),
            "correct": int(predicted[index] == dataset.y_test[index]),
        }
        for qubit in range(benchmark.N_QUBITS):
            row[f"z_q{qubit}"] = float(features[index, qubit])
        for klass in range(len(dataset.class_names)):
            row[f"probability_class_{klass}"] = float(probabilities[index, klass])
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    local = payload["local_reproduction"]
    architecture = payload["architecture"]
    lines = [
        "# Najlepszy model HPO na IBM Quantum",
        "",
        f"Status: `{payload['execution_status']}`.",
        "",
        "## Wybrany przypadek",
        "",
        "- Dataset: Wine, 3 klasy.",
        "- Ansatz: Tree tensor, 4 kubity, 9 parametrow kwantowych.",
        f"- Hiperparametry: `{payload['selected_case']['candidate_id']}`.",
        f"- Lokalna balanced accuracy: {float(local['test_balanced_accuracy_profile_shots']):.3f}.",
        "",
        "## Kompilacja IBM",
        "",
        f"- Backend: `{architecture['backend']}`.",
        f"- Procesor: `{architecture['processor_type']}`.",
        f"- Glebokosc po transpile: {architecture['transpiled_depth']}.",
        f"- Bramki dwukubitowe po transpile: {architecture['transpiled_two_qubit_gate_count']}.",
        f"- Operacje: `{architecture['transpiled_operation_counts']}`.",
    ]
    if payload["execution_status"] == "completed_on_ibm_qpu":
        qpu = payload["qpu_result"]
        lines.extend(
            [
                "",
                "## Wynik fizycznego QPU",
                "",
                f"- Job ID: `{qpu['job_id']}`.",
                f"- Accuracy: {float(qpu['metrics']['accuracy']):.3f}.",
                f"- Balanced accuracy: {float(qpu['metrics']['balanced_accuracy']):.3f}.",
                f"- Macro F1: {float(qpu['metrics']['macro_f1']):.3f}.",
                f"- Loss: {float(qpu['metrics']['loss']):.3f}.",
                f"- Confusion matrix: `{qpu['metrics']['confusion']}`.",
                "",
                "## Porownanie",
                "",
                f"- Delta QPU - lokalna BA: {float(payload['comparison']['qpu_minus_local_balanced_accuracy']):+.3f}.",
                f"- Liczba probek testowych: {payload['dataset']['test_samples']}.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "To byl test kompilacji. Nie wyslano zadania na fizyczny QPU.",
            ]
        )
    lines.extend(
        [
            "",
            "## Ograniczenia",
            "",
            "- Parametry modelu wytrenowano lokalnie; QPU wykonuje koncowa inferencje.",
            "- Zbior testowy ma 15 probek, wiec pojedynczy blad zmienia accuracy o 0.067.",
            "- Wynik zalezy od kalibracji backendu, mapowania, estymacji observables i bledu odczytu.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the best HPO case, Wine + tree tensor, on an IBM QPU."
    )
    parser.add_argument("--backend", default="auto")
    parser.add_argument("--shots", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--samples-per-class", type=int, default=24)
    parser.add_argument("--optimization-level", type=int, default=3)
    parser.add_argument(
        "--offline-compile-check", choices=["heron", "nighthawk"], default=None
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--best-hyperparameters", type=Path, default=DEFAULT_BEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--samples-output", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--pending-output", type=Path, default=DEFAULT_PENDING)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected, hyperparameters = select_best_ibm_case(
        args.results, args.best_hyperparameters
    )
    dataset, local_result, theta, weights, bias = recreate_model(
        selected,
        hyperparameters,
        args.seed,
        args.samples_per_class,
        args.shots,
        args.model_output,
    )

    if args.offline_compile_check:
        from qiskit_ibm_runtime.fake_provider import FakeNighthawk, FakeTorino

        backend = FakeTorino() if args.offline_compile_check == "heron" else FakeNighthawk()
        layout, layout_error = best_tree_layout(backend)
        selection = {
            "selection": "offline_fake_backend",
            "not_a_qpu_execution": True,
            "tree_layout": layout,
            "tree_layout_error_sum": layout_error,
        }
    else:
        service = initialize_service()
        backend, selection = select_backend(service, args.backend)

    compiled, observables, data_parameters, theta_parameters, architecture = (
        compile_circuit(
            backend,
            float(hyperparameters["input_scale"]),
            args.optimization_level,
            args.seed,
            selection.get("tree_layout"),
        )
    )
    payload: dict[str, Any] = {
        "execution_status": "compiled_only" if args.dry_run else "pending",
        "selected_case": selected,
        "selected_hyperparameters": hyperparameters,
        "dataset": {
            "name": "Wine",
            "classes": len(dataset.class_names),
            "train_samples": len(dataset.y_train),
            "validation_samples": len(dataset.y_val),
            "test_samples": len(dataset.y_test),
            "split_seed": args.seed,
        },
        "local_reproduction": local_result,
        "selection": selection,
        "architecture": architecture,
        "execution_protocol": {
            "task": "final test inference; training and HPO were local",
            "estimator_default_shots": args.shots,
            "measurement_mitigation": True,
            "dynamical_decoupling": "XpXm",
        },
    }

    if args.dry_run:
        write_json(args.output, payload)
        write_report(args.report, payload)
        print(json.dumps(json_ready(payload), indent=2, ensure_ascii=False))
        return
    if args.offline_compile_check:
        raise RuntimeError("Offline compilation cannot submit a physical QPU job.")

    from qiskit_ibm_runtime import EstimatorV2 as Estimator

    bindings = {
        data_parameters: np.asarray(dataset.x_test[:, : benchmark.N_QUBITS])[
            :, None, :
        ],
        theta_parameters: np.repeat(theta[None, None, :], len(dataset.y_test), axis=0),
    }
    publication = (compiled, observables[None, :], bindings)
    estimator = Estimator(mode=backend)
    estimator.options.default_shots = args.shots
    estimator.options.dynamical_decoupling.enable = True
    estimator.options.dynamical_decoupling.sequence_type = "XpXm"
    estimator.options.resilience.measure_mitigation = True
    started = time.perf_counter()
    job = estimator.run([publication])
    pending = {
        "execution_status": "submitted",
        "job_id": job.job_id(),
        "backend": backend_name(backend),
        "submitted_at_unix": time.time(),
        "output": str(args.output),
    }
    write_json(args.pending_output, pending)
    print(f"Submitted IBM Runtime job: {job.job_id()}", flush=True)
    result = job.result()
    wall_seconds = time.perf_counter() - started
    features = np.asarray(result[0].data.evs, dtype=float)
    features = np.clip(np.squeeze(features), -1.0, 1.0)
    if features.ndim == 1:
        features = features[None, :]
    metrics, probabilities, predicted = evaluate(
        features, dataset.y_test, weights, bias
    )
    qpu_result: dict[str, Any] = {
        "job_id": job.job_id(),
        "backend": backend_name(backend),
        "wall_seconds": wall_seconds,
        "features": features,
        "metrics": metrics,
        "pub_metadata": result[0].metadata,
    }
    try:
        qpu_result["job_metrics"] = job.metrics()
    except Exception:
        pass
    payload["execution_status"] = "completed_on_ibm_qpu"
    payload["qpu_result"] = qpu_result
    payload["comparison"] = {
        "qpu_minus_local_balanced_accuracy": float(metrics["balanced_accuracy"])
        - float(local_result["test_balanced_accuracy_profile_shots"]),
        "qpu_minus_local_accuracy": float(metrics["accuracy"])
        - float(local_result["test_accuracy_profile_shots"]),
    }
    write_json(args.output, payload)
    write_samples(
        args.samples_output,
        dataset,
        features,
        probabilities,
        predicted,
    )
    write_report(args.report, payload)
    print(f"Completed on {backend_name(backend)}", flush=True)
    print(f"QPU balanced accuracy: {metrics['balanced_accuracy']:.3f}", flush=True)
    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
