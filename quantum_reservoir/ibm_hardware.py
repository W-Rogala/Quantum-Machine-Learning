"""IBM Quantum execution path for the reset-injected quantum reservoir.

The dense reference implementation keeps a mixed reservoir state between time
steps.  On hardware the same channel is implemented by actively resetting the
input qubit, preparing ``sqrt(1-u)|0> + sqrt(u)|1>``, and then applying the
selected Suzuki--Trotter product formula.  Since expectation measurements are
destructive, the state at time ``t`` is obtained by replaying an input prefix.
A finite ``history_window`` caps circuit depth and implements a fading-memory
approximation suitable for current noisy hardware.

Runtime Estimator does not support dynamic circuits.  These circuits contain
mid-circuit reset, so the IBM path uses SamplerV2 with two commuting
measurement groups per time point: Z/ZZ and X.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from .core import ReservoirConfig, interaction_edges


@dataclass(frozen=True)
class HardwareExecutionConfig:
    """Execution and transpilation settings for IBM-compatible QRC circuits."""

    shots: int = 4096
    history_window: int | None = 12
    optimization_level: int = 3
    seed_transpiler: int = 1234
    seed_sampler: int = 1234
    max_circuits_per_job: int = 50
    backend_name: str | None = None
    instance: str | None = None

    def validate(self) -> None:
        if self.shots < 1:
            raise ValueError("shots must be positive")
        if self.history_window is not None and self.history_window < 1:
            raise ValueError("history_window must be positive or None")
        if self.optimization_level not in {0, 1, 2, 3}:
            raise ValueError("optimization_level must be one of 0, 1, 2, 3")
        if self.max_circuits_per_job < 1:
            raise ValueError("max_circuits_per_job must be positive")


def _require_trotter(config: ReservoirConfig) -> None:
    config.validate()
    if config.method != "trotter":
        raise ValueError("IBM hardware circuits require method='trotter'")


def _logical_to_qiskit_wire(logical_qubit: int, n_qubits: int) -> int:
    """Map the dense model's big-endian logical index to a Qiskit wire."""

    return n_qubits - 1 - logical_qubit


def _local_fields(config: ReservoirConfig) -> np.ndarray:
    rng = np.random.default_rng(config.disorder_seed)
    return config.local_field_strength * rng.uniform(-1.0, 1.0, size=config.n_qubits)


def _append_diagonal_block(circuit: Any, config: ReservoirConfig, duration: float) -> None:
    fields = _local_fields(config)
    for logical, field in enumerate(fields):
        wire = _logical_to_qiskit_wire(logical, config.n_qubits)
        circuit.rz(2.0 * float(field) * duration, wire)
    for left, right in interaction_edges(config.n_qubits, config.topology):
        left_wire = _logical_to_qiskit_wire(left, config.n_qubits)
        right_wire = _logical_to_qiskit_wire(right, config.n_qubits)
        circuit.rzz(2.0 * config.interaction_strength * duration, left_wire, right_wire)


def _append_transverse_block(circuit: Any, config: ReservoirConfig, duration: float) -> None:
    for logical in range(config.n_qubits):
        wire = _logical_to_qiskit_wire(logical, config.n_qubits)
        circuit.rx(2.0 * config.transverse_field * duration, wire)


def append_trotter_evolution(circuit: Any, config: ReservoirConfig) -> None:
    """Append one optimized product-formula reservoir step to ``circuit``.

    Adjacent diagonal half-steps in the second-order formula are merged.  This
    makes the logical resource count agree with :func:`circuit_resources`.
    """

    _require_trotter(config)
    step_time = config.evolution_time / config.trotter_steps
    if config.trotter_order == 1:
        for _ in range(config.trotter_steps):
            _append_diagonal_block(circuit, config, step_time)
            _append_transverse_block(circuit, config, step_time)
        return

    _append_diagonal_block(circuit, config, 0.5 * step_time)
    for step in range(config.trotter_steps):
        _append_transverse_block(circuit, config, step_time)
        diagonal_duration = 0.5 * step_time if step == config.trotter_steps - 1 else step_time
        _append_diagonal_block(circuit, config, diagonal_duration)


def build_replay_circuit(
    inputs: Sequence[float] | np.ndarray,
    time_index: int,
    config: ReservoirConfig,
    history_window: int | None = None,
) -> Any:
    """Build the unmeasured reservoir circuit whose output is the state at ``time_index``."""

    from qiskit import QuantumCircuit

    _require_trotter(config)
    values = np.asarray(inputs, dtype=float).reshape(-1)
    if not 0 <= time_index < len(values):
        raise IndexError("time_index is outside the input sequence")
    if history_window is not None and history_window < 1:
        raise ValueError("history_window must be positive or None")
    if np.any(~np.isfinite(values)):
        raise ValueError("inputs must be finite")

    start = 0 if history_window is None else max(0, time_index + 1 - history_window)
    circuit = QuantumCircuit(config.n_qubits, name=f"qrc_t{time_index:05d}")
    input_wire = _logical_to_qiskit_wire(0, config.n_qubits)
    for value in values[start : time_index + 1]:
        clipped = float(np.clip(value, 0.0, 1.0))
        circuit.reset(input_wire)
        circuit.ry(2.0 * np.arcsin(np.sqrt(clipped)), input_wire)
        append_trotter_evolution(circuit, config)
    circuit.metadata = {
        "time_index": int(time_index),
        "history_start": int(start),
        "history_length": int(time_index + 1 - start),
    }
    return circuit


def _measured_copy(base: Any, basis: str) -> Any:
    from qiskit import ClassicalRegister

    circuit = base.copy()
    if basis == "X":
        circuit.h(range(circuit.num_qubits))
    elif basis != "Z":
        raise ValueError("basis must be X or Z")
    classical = ClassicalRegister(circuit.num_qubits, "meas")
    circuit.add_register(classical)
    circuit.measure(range(circuit.num_qubits), range(circuit.num_qubits))
    circuit.name = f"{base.name}_{basis.lower()}"
    circuit.metadata = {**(base.metadata or {}), "measurement_basis": basis}
    return circuit


def build_feature_circuits(
    inputs: Sequence[float] | np.ndarray,
    config: ReservoirConfig,
    history_window: int | None,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Return Z and X measurement circuits for every input time point."""

    values = np.asarray(inputs, dtype=float).reshape(-1)
    circuits: list[Any] = []
    records: list[dict[str, Any]] = []
    for time_index in range(len(values)):
        base = build_replay_circuit(values, time_index, config, history_window)
        for basis in ("Z", "X"):
            circuits.append(_measured_copy(base, basis))
            records.append({"time_index": time_index, "basis": basis})
    return circuits, records


def observable_names(config: ReservoirConfig) -> tuple[str, ...]:
    names: list[str] = []
    for qubit in range(config.n_qubits):
        names.extend((f"X{qubit}", f"Z{qubit}"))
    for left, right in interaction_edges(config.n_qubits, config.topology):
        names.append(f"Z{left}Z{right}")
    return tuple(names)


def _canonical_bitstring(key: Any, n_qubits: int) -> str:
    if isinstance(key, (int, np.integer)):
        return format(int(key), f"0{n_qubits}b")
    text = str(key).replace(" ", "").replace("_", "")
    if text.startswith("0x"):
        return format(int(text, 16), f"0{n_qubits}b")
    if text.startswith("0b"):
        text = text[2:]
    if set(text) <= {"0", "1"}:
        return text.zfill(n_qubits)[-n_qubits:]
    raise ValueError(f"Unsupported count key: {key!r}")


def _expectation(counts: dict[Any, int], logical_qubits: Iterable[int], n_qubits: int) -> tuple[float, float]:
    indices = tuple(int(index) for index in logical_qubits)
    shots = int(sum(int(count) for count in counts.values()))
    if shots < 1:
        raise ValueError("counts contain no shots")
    weighted = 0
    for key, count in counts.items():
        bits = _canonical_bitstring(key, n_qubits)
        parity = sum(int(bits[index]) for index in indices) % 2
        weighted += (-1 if parity else 1) * int(count)
    value = float(weighted / shots)
    standard_error = float(np.sqrt(max(1.0 - value * value, 0.0) / shots))
    return value, standard_error


def decode_feature_counts(
    counts_by_circuit: Sequence[dict[Any, int]],
    records: Sequence[dict[str, Any]],
    config: ReservoirConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Decode Sampler counts into features ordered like the dense QRC implementation."""

    if len(counts_by_circuit) != len(records):
        raise ValueError("counts and circuit records must have the same length")
    if len(records) % 2:
        raise ValueError("each time point requires one Z and one X circuit")
    n_times = len(records) // 2
    names = observable_names(config)
    features = np.empty((n_times, len(names)), dtype=float)
    errors = np.empty_like(features)
    grouped: dict[tuple[int, str], dict[Any, int]] = {}
    for counts, record in zip(counts_by_circuit, records, strict=True):
        grouped[(int(record["time_index"]), str(record["basis"]))] = counts

    for time_index in range(n_times):
        z_counts = grouped[(time_index, "Z")]
        x_counts = grouped[(time_index, "X")]
        column = 0
        for qubit in range(config.n_qubits):
            features[time_index, column], errors[time_index, column] = _expectation(
                x_counts, (qubit,), config.n_qubits
            )
            column += 1
            features[time_index, column], errors[time_index, column] = _expectation(
                z_counts, (qubit,), config.n_qubits
            )
            column += 1
        for left, right in interaction_edges(config.n_qubits, config.topology):
            features[time_index, column], errors[time_index, column] = _expectation(
                z_counts, (left, right), config.n_qubits
            )
            column += 1
    return features, errors


def _counts_from_pub_result(pub_result: Any) -> dict[Any, int]:
    data = getattr(pub_result, "data", None)
    if data is None:
        raise RuntimeError("Sampler result has no data field")
    for name in ("meas", "c", "cr", "classical"):
        register = getattr(data, name, None)
        if register is not None and hasattr(register, "get_counts"):
            return dict(register.get_counts())
    for name in dir(data):
        if name.startswith("_"):
            continue
        register = getattr(data, name)
        if hasattr(register, "get_counts"):
            return dict(register.get_counts())
    raise RuntimeError("No classical register with get_counts() in Sampler result")


def run_local_sampler(circuits: Sequence[Any], shots: int, seed: int = 1234) -> list[dict[Any, int]]:
    """Execute measured QRC circuits with Qiskit Aer SamplerV2."""

    from qiskit_aer.primitives import SamplerV2

    sampler = SamplerV2(default_shots=shots, seed=seed)
    result = sampler.run(list(circuits), shots=shots).result()
    return [_counts_from_pub_result(pub_result) for pub_result in result]


def compile_for_backend(
    circuits: Sequence[Any],
    backend: Any,
    optimization_level: int = 3,
    seed_transpiler: int = 1234,
) -> list[Any]:
    """Transpile logical circuits into backend ISA circuits."""

    from qiskit.transpiler import generate_preset_pass_manager

    operation_names = set(str(name) for name in getattr(backend, "operation_names", ()))
    missing = {"reset", "measure"} - operation_names
    if missing:
        raise ValueError(f"Backend {getattr(backend, 'name', backend)} lacks {sorted(missing)}")
    pass_manager = generate_preset_pass_manager(
        backend=backend,
        optimization_level=optimization_level,
        seed_transpiler=seed_transpiler,
    )
    return list(pass_manager.run(list(circuits)))


def _chunks(values: Sequence[Any], size: int) -> Iterable[tuple[int, Sequence[Any]]]:
    for start in range(0, len(values), size):
        yield start // size, values[start : start + size]


def _write_qpy(path: Path, circuits: Sequence[Any]) -> None:
    from qiskit import qpy

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        qpy.dump(list(circuits), handle)


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compilation_summary(circuits: Sequence[Any]) -> dict[str, Any]:
    depths = [int(circuit.depth() or 0) for circuit in circuits]
    two_qubit = [
        sum(1 for instruction in circuit.data if len(instruction.qubits) == 2)
        for circuit in circuits
    ]
    return {
        "circuit_count": len(circuits),
        "depth_min": min(depths, default=0),
        "depth_max": max(depths, default=0),
        "depth_mean": float(np.mean(depths)) if depths else 0.0,
        "two_qubit_gates_min": min(two_qubit, default=0),
        "two_qubit_gates_max": max(two_qubit, default=0),
        "two_qubit_gates_mean": float(np.mean(two_qubit)) if two_qubit else 0.0,
    }


def select_ibm_backend(execution: HardwareExecutionConfig) -> tuple[Any, Any]:
    """Create the IBM service and select an explicitly named or least-busy QPU."""

    from qiskit_ibm_runtime import QiskitRuntimeService

    kwargs: dict[str, Any] = {"channel": "ibm_quantum_platform"}
    if execution.instance:
        kwargs["instance"] = execution.instance
    service = QiskitRuntimeService(**kwargs)
    if execution.backend_name:
        backend = service.backend(execution.backend_name)
    else:
        backend = service.least_busy(
            operational=True,
            simulator=False,
            min_num_qubits=4,
            dynamic_circuits=True,
        )
    return service, backend


def run_ibm_sampler(
    compiled_circuits: Sequence[Any],
    backend: Any,
    execution: HardwareExecutionConfig,
    output_dir: Path,
) -> tuple[list[dict[Any, int]], list[str]]:
    """Submit ISA circuits to IBM SamplerV2 in bounded jobs and persist raw counts."""

    from qiskit_ibm_runtime import SamplerV2

    output_dir.mkdir(parents=True, exist_ok=True)
    all_counts: list[dict[Any, int]] = []
    job_ids: list[str] = []
    for batch_index, batch in _chunks(compiled_circuits, execution.max_circuits_per_job):
        batch = list(batch)
        sampler = SamplerV2(mode=backend)
        job = sampler.run(batch, shots=execution.shots)
        job_id = str(job.job_id())
        job_ids.append(job_id)
        result = job.result()
        counts = [_counts_from_pub_result(pub_result) for pub_result in result]
        all_counts.extend(counts)
        write_json(
            output_dir / f"batch_{batch_index:04d}_counts.json",
            {"job_id": job_id, "shots": execution.shots, "counts": counts},
        )
    return all_counts, job_ids


def ridge_readout(
    inputs: Sequence[float] | np.ndarray,
    features: np.ndarray,
    targets: Sequence[float] | np.ndarray,
    split: tuple[int, int, int, int],
    alphas: tuple[float, ...] = (1e-8, 1e-6, 1e-4, 1e-2, 1.0, 10.0),
) -> tuple[dict[str, float], np.ndarray]:
    """Fit the temporal ridge readout without leaking the held-out test segment."""

    values = np.asarray(inputs, dtype=float).reshape(-1)
    target = np.asarray(targets, dtype=float).reshape(-1)
    feature_matrix = np.asarray(features, dtype=float)
    if feature_matrix.shape[0] != len(values) or len(target) != len(values):
        raise ValueError("inputs, features, and targets must have aligned rows")
    washout, train, validation, test = map(int, split)
    if min(washout, train, validation, test) < 1 or sum(split) > len(values):
        raise ValueError("invalid temporal split")
    design = np.column_stack((values, feature_matrix))
    train_start = washout
    train_end = train_start + train
    validation_end = train_end + validation
    test_end = validation_end + test

    def fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mean = x.mean(axis=0)
        scale = x.std(axis=0)
        scale[scale < 1e-12] = 1.0
        normalized = (x - mean) / scale
        augmented = np.column_stack((np.ones(len(normalized)), normalized))
        penalty = np.eye(augmented.shape[1])
        penalty[0, 0] = 0.0
        weights = np.linalg.solve(augmented.T @ augmented + alpha * penalty, augmented.T @ y)
        return mean, scale, weights

    def predict(x: np.ndarray, model: tuple[np.ndarray, np.ndarray, np.ndarray]) -> np.ndarray:
        mean, scale, weights = model
        return np.column_stack((np.ones(len(x)), (x - mean) / scale)) @ weights

    def nrmse(y: np.ndarray, prediction: np.ndarray) -> float:
        denominator = float(np.std(y))
        return float(np.sqrt(np.mean((y - prediction) ** 2)) / denominator)

    x_train = design[train_start:train_end]
    y_train = target[train_start:train_end]
    x_validation = design[train_end:validation_end]
    y_validation = target[train_end:validation_end]
    candidates = []
    for alpha in alphas:
        model = fit(x_train, y_train, alpha)
        candidates.append((nrmse(y_validation, predict(x_validation, model)), float(alpha)))
    validation_nrmse, selected_alpha = min(candidates)
    x_refit = design[train_start:validation_end]
    y_refit = target[train_start:validation_end]
    model = fit(x_refit, y_refit, selected_alpha)
    prediction = predict(design[validation_end:test_end], model)
    y_test = target[validation_end:test_end]
    residual = y_test - prediction
    ss_total = float(np.sum((y_test - np.mean(y_test)) ** 2))
    metrics = {
        "ridge_alpha": selected_alpha,
        "validation_nrmse": validation_nrmse,
        "test_nrmse": nrmse(y_test, prediction),
        "test_mae": float(np.mean(np.abs(residual))),
        "test_r2": float(1.0 - np.sum(residual**2) / ss_total) if ss_total > 0 else 0.0,
    }
    return metrics, prediction


def save_feature_artifacts(
    output_dir: Path,
    inputs: np.ndarray,
    targets: np.ndarray,
    features: np.ndarray,
    standard_errors: np.ndarray,
    config: ReservoirConfig,
    execution: HardwareExecutionConfig,
    metadata: dict[str, Any],
    prediction: np.ndarray | None = None,
    test_targets: np.ndarray | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "inputs.npy", inputs)
    np.save(output_dir / "targets.npy", targets)
    np.save(output_dir / "features.npy", features)
    np.save(output_dir / "feature_standard_errors.npy", standard_errors)
    names = observable_names(config)
    with (output_dir / "features.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_index", *names, *(f"se_{name}" for name in names)])
        for index, (row, errors) in enumerate(zip(features, standard_errors, strict=True)):
            writer.writerow([index, *map(float, row), *map(float, errors)])
    if prediction is not None and test_targets is not None:
        with (output_dir / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["test_index", "actual", "prediction"])
            for index, (actual, predicted) in enumerate(zip(test_targets, prediction, strict=True)):
                writer.writerow([index, float(actual), float(predicted)])
    write_json(
        output_dir / "summary.json",
        {
            "reservoir": asdict(config),
            "execution": asdict(execution),
            "observable_names": names,
            **metadata,
        },
    )

