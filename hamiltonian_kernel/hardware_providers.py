from __future__ import annotations

import json
import hashlib
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .hardware_circuits import (
    build_braket_measurement_circuit,
    build_qiskit_measurement_circuit,
    canonical_counts,
    config_from_dict,
    measurement_operations,
)


REMOTE_PROVIDERS = {"ibm", "ionq", "braket"}
LOCAL_PROVIDERS = {"aer", "pennylane", "braket-local"}
IBM_SAMPLER_RUNTIME_OPTIONS = {"execution": {"init_qubits": True}}
IBM_QUBIT_INITIALIZATION = {
    "runtime_init_qubits": True,
    "explicit_circuit_reset": True,
}


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, (datetime,)):
        return value.isoformat()
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


def _samples_and_config(workload: dict[str, Any]) -> tuple[np.ndarray, Any]:
    train = np.asarray(workload["samples"]["train"]["x"], dtype=float)
    test = np.asarray(workload["samples"]["test"]["x"], dtype=float)
    return np.vstack((train, test)), config_from_dict(
        workload["model"]["evolution_config"]
    )


def _entries(workload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(workload["measurement"]["entries"])


def _groups_by_shots(
    entries: list[dict[str, Any]],
    max_circuits_per_job: int,
) -> list[tuple[int, list[dict[str, Any]]]]:
    if max_circuits_per_job < 1:
        raise ValueError("max_circuits_per_job must be positive")
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[int(entry["shots"])].append(entry)
    batches: list[tuple[int, list[dict[str, Any]]]] = []
    for shots, rows in sorted(grouped.items()):
        for start in range(0, len(rows), max_circuits_per_job):
            batches.append((shots, rows[start : start + max_circuits_per_job]))
    return batches


def _qiskit_counts_from_pub_result(pub_result: Any) -> dict[Any, int]:
    data = getattr(pub_result, "data", None)
    if data is None:
        raise RuntimeError("Sampler result has no data field")
    for attribute in ("meas", "c", "cr", "classical"):
        register = getattr(data, attribute, None)
        if register is not None and hasattr(register, "get_counts"):
            return register.get_counts()
    for attribute in dir(data):
        if attribute.startswith("_"):
            continue
        register = getattr(data, attribute)
        if hasattr(register, "get_counts"):
            return register.get_counts()
    raise RuntimeError("No classical register with get_counts() found in Sampler result")


def _backend_name(backend: Any) -> str:
    value = getattr(backend, "name", None)
    if callable(value):
        value = value()
    return str(value if value is not None else backend)


def _compilation_metadata(circuits: list[Any]) -> dict[str, Any]:
    depths = [int(circuit.depth() or 0) for circuit in circuits]
    two_qubit = [
        sum(1 for instruction in circuit.data if len(instruction.qubits) == 2)
        for circuit in circuits
    ]
    operation_totals: dict[str, int] = defaultdict(int)
    for circuit in circuits:
        for name, count in circuit.count_ops().items():
            operation_totals[str(name)] += int(count)
    return {
        "circuit_count": len(circuits),
        "depth_min": min(depths, default=0),
        "depth_max": max(depths, default=0),
        "depth_mean": float(np.mean(depths)) if depths else 0.0,
        "two_qubit_gates_min": min(two_qubit, default=0),
        "two_qubit_gates_max": max(two_qubit, default=0),
        "two_qubit_gates_mean": float(np.mean(two_qubit)) if two_qubit else 0.0,
        "two_qubit_gates_by_circuit": two_qubit,
        "operation_totals": dict(sorted(operation_totals.items())),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _layout_metadata(circuit: Any) -> dict[str, Any]:
    layout = getattr(circuit, "layout", None)
    if layout is None:
        return {"present": False}

    def pairs(value: Any) -> list[dict[str, Any]] | None:
        if value is None or not hasattr(value, "get_virtual_bits"):
            return None
        return [
            {"virtual_qubit": repr(qubit), "physical_qubit": int(physical)}
            for qubit, physical in value.get_virtual_bits().items()
            if getattr(getattr(qubit, "_register", None), "name", None) != "ancilla"
        ]

    final_indices: list[int] | None = None
    if hasattr(layout, "final_index_layout"):
        try:
            final_indices = [
                int(value)
                for value in layout.final_index_layout(filter_ancillas=True)
            ]
        except Exception:
            final_indices = None
    input_mapping = getattr(layout, "input_qubit_mapping", None)
    return {
        "present": True,
        "initial_layout": pairs(getattr(layout, "initial_layout", None)),
        "final_layout": pairs(getattr(layout, "final_layout", None)),
        "input_qubit_mapping": (
            [
                {"virtual_qubit": repr(qubit), "input_index": int(index)}
                for qubit, index in input_mapping.items()
            ]
            if isinstance(input_mapping, dict)
            else None
        ),
        "final_index_layout": final_indices,
    }


def _target_snapshot(target: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "num_qubits": int(getattr(target, "num_qubits", 0) or 0),
        "dt": getattr(target, "dt", None),
        "operation_names": sorted(str(value) for value in target.operation_names),
        "instructions": [],
    }
    try:
        coupling = target.build_coupling_map()
        snapshot["coupling_map"] = (
            None if coupling is None else [list(map(int, edge)) for edge in coupling.get_edges()]
        )
    except Exception as error:
        snapshot["coupling_map_error"] = repr(error)
    for operation_name in snapshot["operation_names"]:
        try:
            properties_by_qargs = target[operation_name]
            for qargs, properties in properties_by_qargs.items():
                snapshot["instructions"].append(
                    {
                        "operation": operation_name,
                        "qubits": None if qargs is None else [int(value) for value in qargs],
                        "duration_seconds": (
                            None if properties is None else getattr(properties, "duration", None)
                        ),
                        "error": None if properties is None else getattr(properties, "error", None),
                    }
                )
        except Exception as error:
            snapshot["instructions"].append(
                {"operation": operation_name, "snapshot_error": repr(error)}
            )
    return snapshot


def _backend_snapshot(backend: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "backend": _backend_name(backend),
    }
    for name in ("configuration", "status"):
        try:
            value = getattr(backend, name)()
            snapshot[name] = value.to_dict() if hasattr(value, "to_dict") else repr(value)
        except Exception as error:
            snapshot[f"{name}_error"] = repr(error)
    try:
        properties = backend.properties(refresh=True)
        snapshot["properties"] = (
            None
            if properties is None
            else properties.to_dict()
            if hasattr(properties, "to_dict")
            else repr(properties)
        )
    except Exception as error:
        snapshot["properties_error"] = repr(error)
    try:
        snapshot["target"] = _target_snapshot(backend.target)
    except Exception as error:
        snapshot["target_error"] = repr(error)
    return snapshot


def _save_qiskit_reproducibility_bundle(
    output_dir: Path,
    batch_index: int,
    circuit_ids: list[str],
    logical: list[Any],
    compiled: list[Any],
    transpile_seed: int,
    optimization_level: int,
    runtime_options: dict[str, Any] | None = None,
    qubit_initialization: dict[str, Any] | None = None,
    initial_layout: list[int] | None = None,
) -> dict[str, Any]:
    from qiskit import __version__ as qiskit_version
    from qiskit import qpy

    output_dir.mkdir(parents=True, exist_ok=True)
    logical_path = output_dir / f"batch_{batch_index:04d}_logical.qpy"
    isa_path = output_dir / f"batch_{batch_index:04d}_isa.qpy"
    with logical_path.open("wb") as handle:
        qpy.dump(logical, handle)
    with isa_path.open("wb") as handle:
        qpy.dump(compiled, handle)
    payload = {
        "schema": "hamiltonian-kernel.ibm-reproducibility.v1",
        "batch_index": batch_index,
        "circuit_ids": circuit_ids,
        "qiskit_version": qiskit_version,
        "qpy_version": int(qpy.QPY_VERSION),
        "transpile_seed": transpile_seed,
        "optimization_level": optimization_level,
        "runtime_options": runtime_options or {},
        "qubit_initialization": qubit_initialization or {},
        "requested_initial_layout": initial_layout,
        "logical_qpy": str(logical_path),
        "logical_qpy_sha256": _sha256_file(logical_path),
        "isa_qpy": str(isa_path),
        "isa_qpy_sha256": _sha256_file(isa_path),
        "isa_layouts": [_layout_metadata(circuit) for circuit in compiled],
        "isa_compilation": _compilation_metadata(compiled),
    }
    manifest_path = output_dir / f"batch_{batch_index:04d}_manifest.json"
    write_json(manifest_path, payload)
    payload["manifest"] = str(manifest_path)
    payload["manifest_sha256"] = _sha256_file(manifest_path)
    return payload


def _update_state_resource_axes(state: dict[str, Any], workload: dict[str, Any]) -> None:
    circuit_shots = sum(
        int(batch["shots"]) * len(batch["circuit_ids"])
        for batch in state.get("batches", [])
    )
    maps_per_shot = 2 if workload["measurement"].get("kernel") == "fidelity" else 1
    two_qubit_gate_shots = 0
    for batch in state.get("batches", []):
        gate_counts = batch.get("compilation", {}).get("two_qubit_gates_by_circuit", [])
        two_qubit_gate_shots += int(batch.get("shots", 0)) * sum(
            int(value) for value in gate_counts
        )
    quantum_seconds = [
        float(batch["qpu_usage"]["quantum_seconds"])
        for batch in state.get("batches", [])
        if batch.get("qpu_usage", {}).get("quantum_seconds") is not None
    ]
    state["resource_axes"] = {
        "circuit_shots": circuit_shots,
        "map_executions": circuit_shots * maps_per_shot,
        "two_qubit_gate_shots": two_qubit_gate_shots,
        "qpu_time_seconds": sum(quantum_seconds) if quantum_seconds else None,
        "qpu_credits": None,
        "qpu_credit_status": "not_reported_by_runtime_job",
    }


def execute_aer(
    workload: dict[str, Any],
    seed: int,
    optimization_level: int,
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    samples, config = _samples_and_config(workload)
    entries = _entries(workload)
    backend = AerSimulator(seed_simulator=seed)
    counts_by_circuit: dict[str, dict[str, int]] = {}
    compilation: list[dict[str, Any]] = []
    two_qubit_gate_shots = 0
    started = time.perf_counter()
    for batch_index, (shots, batch_entries) in enumerate(
        _groups_by_shots(entries, max_circuits_per_job=len(entries))
    ):
        logical = [
            build_qiskit_measurement_circuit(entry, samples, config)
            for entry in batch_entries
        ]
        compiled = transpile(
            logical,
            backend=backend,
            optimization_level=optimization_level,
            seed_transpiler=seed,
        )
        if not isinstance(compiled, list):
            compiled = [compiled]
        result = backend.run(compiled, shots=shots, seed_simulator=seed + batch_index).result()
        for index, entry in enumerate(batch_entries):
            counts_by_circuit[str(entry["circuit_id"])] = canonical_counts(
                result.get_counts(index), config.n_qubits, "qiskit"
            )
        compilation_metadata = _compilation_metadata(compiled)
        compilation.append(compilation_metadata)
        two_qubit_gate_shots += shots * sum(
            int(value)
            for value in compilation_metadata["two_qubit_gates_by_circuit"]
        )

    circuit_shots = sum(int(entry["shots"]) for entry in entries)
    maps_per_shot = 2 if workload["measurement"].get("kernel") == "fidelity" else 1

    state = {
        "schema": "hamiltonian-kernel-execution-v1",
        "workload_id": workload["workload_id"],
        "provider": "aer",
        "backend": "AerSimulator",
        "status": "completed",
        "not_a_qpu_execution": True,
        "runtime_seconds": time.perf_counter() - started,
        "optimization_level": optimization_level,
        "compilation_batches": compilation,
        "resource_axes": {
            "circuit_shots": circuit_shots,
            "map_executions": circuit_shots * maps_per_shot,
            "two_qubit_gate_shots": two_qubit_gate_shots,
            "qpu_time_seconds": None,
            "qpu_credits": None,
            "qpu_cost_status": "not_available_for_simulation",
        },
    }
    return state, counts_by_circuit


def _apply_pennylane_operations(operations: list[Any]) -> None:
    import pennylane as qml

    for operation in operations:
        if operation.name == "h":
            qml.Hadamard(wires=operation.qubits[0])
        elif operation.name == "rx":
            qml.RX(float(operation.angle), wires=operation.qubits[0])
        elif operation.name == "rz":
            qml.RZ(float(operation.angle), wires=operation.qubits[0])
        elif operation.name == "rzz":
            qml.IsingZZ(float(operation.angle), wires=list(operation.qubits))
        else:
            raise ValueError(f"Unsupported PennyLane operation: {operation.name}")


def execute_pennylane(
    workload: dict[str, Any],
    device_name: str,
    seed: int | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    import pennylane as qml

    samples, config = _samples_and_config(workload)
    entries = _entries(workload)
    counts_by_circuit: dict[str, dict[str, int]] = {}
    started = time.perf_counter()
    for shots, batch_entries in _groups_by_shots(entries, len(entries)):
        device_kwargs: dict[str, Any] = {"wires": config.n_qubits}
        if seed is not None and device_name.startswith(("default.", "lightning.")):
            device_kwargs["seed"] = seed
        device = qml.device(device_name, **device_kwargs)
        for entry in batch_entries:
            operations = measurement_operations(entry, samples, config)

            def execute_one():
                _apply_pennylane_operations(operations)
                return qml.counts(wires=range(config.n_qubits))

            qnode = qml.QNode(execute_one, device, shots=shots)
            raw_counts = qnode()
            counts_by_circuit[str(entry["circuit_id"])] = canonical_counts(
                dict(raw_counts), config.n_qubits, "q0_first"
            )

    state = {
        "schema": "hamiltonian-kernel-execution-v1",
        "workload_id": workload["workload_id"],
        "provider": "pennylane",
        "backend": device_name,
        "status": "completed",
        # This adapter is a cross-framework validation path. Physical providers
        # need a dedicated submission adapter with persisted remote job IDs.
        "not_a_qpu_execution": True,
        "runtime_seconds": time.perf_counter() - started,
        "seed": seed,
        "warning": "PennyLane software validation; this is not Xanadu photonic hardware.",
    }
    return state, counts_by_circuit


def execute_braket_local(
    workload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    from braket.devices import LocalSimulator

    samples, config = _samples_and_config(workload)
    entries = _entries(workload)
    device = LocalSimulator()
    counts_by_circuit: dict[str, dict[str, int]] = {}
    started = time.perf_counter()
    for entry in entries:
        circuit = build_braket_measurement_circuit(entry, samples, config)
        result = device.run(circuit, shots=int(entry["shots"])).result()
        counts_by_circuit[str(entry["circuit_id"])] = canonical_counts(
            dict(result.measurement_counts), config.n_qubits, "q0_first"
        )
    state = {
        "schema": "hamiltonian-kernel-execution-v1",
        "workload_id": workload["workload_id"],
        "provider": "braket-local",
        "backend": str(device),
        "status": "completed",
        "not_a_qpu_execution": True,
        "runtime_seconds": time.perf_counter() - started,
    }
    return state, counts_by_circuit


def _new_remote_state(
    workload: dict[str, Any],
    provider: str,
    backend: str,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "schema": "hamiltonian-kernel-execution-v1",
        "workload_id": workload["workload_id"],
        "provider": provider,
        "backend": backend,
        "status": "compiled_only" if dry_run else "submitted",
        "dry_run": dry_run,
        "not_a_qpu_execution": dry_run,
        "submitted_at_unix": None if dry_run else time.time(),
        "batches": [],
    }


def _load_resumable_state(
    state_path: Path,
    workload: dict[str, Any],
    provider: str,
    dry_run: bool,
) -> dict[str, Any] | None:
    if dry_run or not state_path.exists():
        return None
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("workload_id") != workload["workload_id"]:
        raise ValueError("Existing execution state belongs to a different workload")
    if state.get("provider") != provider:
        raise ValueError("Existing execution state belongs to a different provider")
    if state.get("dry_run"):
        raise ValueError("Cannot resume a dry-run state as a physical submission")
    return state


def _submitted_circuit_ids(state: dict[str, Any]) -> set[str]:
    submitted: set[str] = set()
    for batch in state.get("batches", []):
        circuit_ids = {str(value) for value in batch.get("circuit_ids", [])}
        duplicate = submitted & circuit_ids
        if duplicate:
            raise ValueError(f"Execution state repeats circuit IDs: {sorted(duplicate)}")
        if not batch.get("job_id"):
            raise RuntimeError(
                "A previous submission stopped before its job ID was persisted. "
                "Inspect the provider dashboard before deciding whether to resubmit: "
                f"circuits={sorted(circuit_ids)}"
            )
        submitted |= circuit_ids
    return submitted


def _pending_entries(
    workload: dict[str, Any],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    submitted = _submitted_circuit_ids(state)
    expected = {str(entry["circuit_id"]) for entry in _entries(workload)}
    extra = submitted - expected
    if extra:
        raise ValueError(f"Execution state contains unknown circuit IDs: {sorted(extra)}")
    return [
        entry
        for entry in _entries(workload)
        if str(entry["circuit_id"]) not in submitted
    ]


def _record_submission_start(
    state: dict[str, Any],
    state_path: Path,
    batch: dict[str, Any],
) -> None:
    state["status"] = "submitting"
    state["batches"].append(batch)
    write_json(state_path, state)


def _record_submission_failure(
    state: dict[str, Any],
    state_path: Path,
    batch: dict[str, Any],
) -> None:
    batch["status"] = "submission_unknown"
    state["status"] = "submission_unknown"
    write_json(state_path, state)


def submit_ibm(
    workload: dict[str, Any],
    backend_name: str,
    channel: str,
    optimization_level: int,
    max_circuits_per_job: int,
    dry_run: bool,
    state_path: Path,
    transpile_seed: int = 20260819,
    initial_layout: list[int] | None = None,
) -> dict[str, Any]:
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    token = os.getenv("IBM_QUANTUM_TOKEN")
    service = (
        QiskitRuntimeService(channel=channel, token=token)
        if token
        else QiskitRuntimeService(channel=channel)
    )
    config = config_from_dict(workload["model"]["evolution_config"])
    if initial_layout is not None:
        initial_layout = [int(value) for value in initial_layout]
        if len(initial_layout) != config.n_qubits:
            raise ValueError("IBM initial layout must contain one physical qubit per logical qubit")
        if len(set(initial_layout)) != len(initial_layout):
            raise ValueError("IBM initial layout cannot contain duplicate physical qubits")
        if min(initial_layout, default=0) < 0:
            raise ValueError("IBM initial layout cannot contain negative physical qubits")
    existing = _load_resumable_state(state_path, workload, "ibm", dry_run)
    if existing is not None and existing.get("backend_request") != backend_name:
        raise ValueError("Resume requires the same IBM --backend request")
    if existing is not None:
        backend = service.backend(str(existing["backend"]))
    else:
        backend = (
            service.least_busy(
                operational=True,
                simulator=False,
                min_num_qubits=config.n_qubits,
            )
            if backend_name == "least_busy"
            else service.backend(backend_name)
        )
    state = existing or _new_remote_state(
        workload, "ibm", _backend_name(backend), dry_run
    )
    state["backend_request"] = backend_name
    if existing is not None and existing.get("runtime_options") != IBM_SAMPLER_RUNTIME_OPTIONS:
        raise ValueError(
            "Resume requires explicit IBM qubit initialization; use a new output directory"
        )
    if existing is not None and existing.get("qubit_initialization") != IBM_QUBIT_INITIALIZATION:
        raise ValueError(
            "Resume requires explicit reset gates in every IBM circuit; use a new output directory"
        )
    if existing is not None and existing.get("requested_initial_layout") != initial_layout:
        raise ValueError("Resume requires the same IBM initial layout")
    state["runtime_options"] = IBM_SAMPLER_RUNTIME_OPTIONS
    state["qubit_initialization"] = IBM_QUBIT_INITIALIZATION
    state["requested_initial_layout"] = initial_layout
    if existing is not None and int(existing.get("transpile_seed", transpile_seed)) != transpile_seed:
        raise ValueError("Resume requires the same IBM transpile seed")
    state["transpile_seed"] = transpile_seed
    state["optimization_level"] = optimization_level
    try:
        state["not_a_qpu_execution"] = bool(backend.configuration().simulator) or dry_run
    except Exception:
        pass
    samples, _ = _samples_and_config(workload)
    reproducibility_dir = state_path.parent / "reproducibility"
    snapshot_path = reproducibility_dir / "backend_calibration_snapshot.json"
    if not snapshot_path.exists():
        snapshot = _backend_snapshot(backend)
        write_json(snapshot_path, snapshot)
    state["backend_calibration_snapshot"] = str(snapshot_path)
    state["backend_calibration_snapshot_sha256"] = _sha256_file(snapshot_path)
    pass_manager = generate_preset_pass_manager(
        backend=backend,
        optimization_level=optimization_level,
        seed_transpiler=transpile_seed,
        initial_layout=initial_layout,
    )
    sampler = (
        None
        if dry_run
        else SamplerV2(mode=backend, options=IBM_SAMPLER_RUNTIME_OPTIONS)
    )
    pending_entries = _entries(workload) if dry_run else _pending_entries(workload, state)
    for shots, batch_entries in _groups_by_shots(
        pending_entries, max_circuits_per_job
    ):
        batch_index = len(state["batches"])
        logical = [
            build_qiskit_measurement_circuit(
                entry,
                samples,
                config,
                initialize_qubits=True,
            )
            for entry in batch_entries
        ]
        compiled = pass_manager.run(logical)
        if not isinstance(compiled, list):
            compiled = [compiled]
        circuit_ids = [str(entry["circuit_id"]) for entry in batch_entries]
        reproducibility = _save_qiskit_reproducibility_bundle(
            reproducibility_dir,
            batch_index,
            circuit_ids,
            logical,
            compiled,
            transpile_seed,
            optimization_level,
            IBM_SAMPLER_RUNTIME_OPTIONS,
            IBM_QUBIT_INITIALIZATION,
            initial_layout,
        )
        batch = {
            "batch_index": batch_index,
            "shots": shots,
            "circuit_ids": circuit_ids,
            "status": "compiled_only" if dry_run else "pending",
            "job_id": None,
            "compilation": _compilation_metadata(compiled),
            "reproducibility": reproducibility,
        }
        if not dry_run:
            _record_submission_start(state, state_path, batch)
            try:
                job = sampler.run(compiled, shots=shots)
                batch["job_id"] = job.job_id()
            except Exception:
                _record_submission_failure(state, state_path, batch)
                raise
            batch["status"] = "pending"
            state["status"] = "submitted"
            write_json(state_path, state)
        else:
            state["batches"].append(batch)
            _update_state_resource_axes(state, workload)
            write_json(state_path, state)
    _update_state_resource_axes(state, workload)
    write_json(state_path, state)
    return state


def _resolve_ionq_backend(provider: Any, backend_name: str, gateset: str) -> Any:
    candidates = [backend_name]
    if backend_name.startswith("ionq_"):
        candidates.append(backend_name.removeprefix("ionq_"))
    else:
        candidates.append(f"ionq_{backend_name}")
    errors: list[str] = []
    for candidate in dict.fromkeys(candidates):
        try:
            return provider.get_backend(candidate, gateset=gateset)
        except Exception as exc:  # Provider error types vary by release.
            errors.append(f"{candidate}: {exc}")
    raise RuntimeError("Cannot resolve IonQ backend. " + "; ".join(errors))


def _offline_ionq_backend(backend_name: str, gateset: str, n_qubits: int) -> Any:
    from qiskit_ionq.ionq_backend import IonQBackend

    aliases = {
        "offline.forte": "ionq_qpu.forte-1",
        "offline.aria": "ionq_qpu.aria-1",
    }
    if backend_name not in aliases:
        raise ValueError(
            "Offline IonQ target must be 'offline.forte' or 'offline.aria'"
        )
    return IonQBackend(
        provider=None,
        name=aliases[backend_name],
        description="Offline qiskit-ionq compilation target",
        gateset=gateset,
        num_qubits=n_qubits,
        simulator=False,
    )


def submit_ionq(
    workload: dict[str, Any],
    backend_name: str,
    gateset: str,
    optimization_level: int,
    max_circuits_per_job: int,
    dry_run: bool,
    state_path: Path,
) -> dict[str, Any]:
    from qiskit import transpile
    from qiskit_ionq import IonQProvider

    samples, config = _samples_and_config(workload)
    offline_target = backend_name.startswith("offline.")
    if offline_target:
        if not dry_run:
            raise ValueError("Offline IonQ targets can only be used with --dry-run")
        backend = _offline_ionq_backend(backend_name, gateset, config.n_qubits)
    else:
        token = os.getenv("IONQ_API_KEY")
        provider = IonQProvider(token=token) if token else IonQProvider()
        backend = _resolve_ionq_backend(provider, backend_name, gateset)
    existing = _load_resumable_state(state_path, workload, "ionq", dry_run)
    if existing is not None:
        if existing.get("backend_request") != backend_name:
            raise ValueError("Resume requires the same IonQ --backend request")
        if existing.get("gateset") != gateset:
            raise ValueError("Resume requires the same IonQ gateset")
    state = existing or _new_remote_state(
        workload, "ionq", _backend_name(backend), dry_run
    )
    state["backend_request"] = backend_name
    state["not_a_qpu_execution"] = dry_run or "simulator" in backend_name.lower()
    state["gateset"] = gateset
    state["offline_target"] = offline_target
    pending_entries = _entries(workload) if dry_run else _pending_entries(workload, state)
    for shots, batch_entries in _groups_by_shots(
        pending_entries, max_circuits_per_job
    ):
        batch_index = len(state["batches"])
        logical = [
            build_qiskit_measurement_circuit(entry, samples, config)
            for entry in batch_entries
        ]
        compiled = transpile(
            logical,
            backend=backend,
            optimization_level=optimization_level,
        )
        if not isinstance(compiled, list):
            compiled = [compiled]
        batch = {
            "batch_index": batch_index,
            "shots": shots,
            "circuit_ids": [str(entry["circuit_id"]) for entry in batch_entries],
            "status": "compiled_only" if dry_run else "pending",
            "job_id": None,
            "compilation": _compilation_metadata(compiled),
        }
        if not dry_run:
            _record_submission_start(state, state_path, batch)
            try:
                job = backend.run(
                    compiled,
                    shots=shots,
                    memory=True,
                    name=f"hk_{workload['workload_id']}_{batch_index:03d}",
                )
                batch["job_id"] = job.job_id()
            except Exception:
                _record_submission_failure(state, state_path, batch)
                raise
            batch["status"] = "pending"
            state["status"] = "submitted"
            write_json(state_path, state)
        else:
            state["batches"].append(batch)
            write_json(state_path, state)
    return state


def submit_braket(
    workload: dict[str, Any],
    device_arn: str,
    s3_bucket: str | None,
    s3_prefix: str,
    dry_run: bool,
    state_path: Path,
) -> dict[str, Any]:
    samples, config = _samples_and_config(workload)
    existing = _load_resumable_state(state_path, workload, "braket", dry_run)
    if existing is not None and existing.get("backend") != device_arn:
        raise ValueError("Resume requires the same Braket device ARN")
    state = existing or _new_remote_state(workload, "braket", device_arn, dry_run)
    if dry_run:
        state["status"] = "prepared_only"
    state["not_a_qpu_execution"] = dry_run or "quantum-simulator" in device_arn.lower()
    device = None
    if not dry_run:
        from braket.aws import AwsDevice

        device = AwsDevice(device_arn)
    pending_entries = _entries(workload) if dry_run else _pending_entries(workload, state)
    for entry in pending_entries:
        index = len(state["batches"])
        circuit = build_braket_measurement_circuit(entry, samples, config)
        batch = {
            "batch_index": index,
            "shots": int(entry["shots"]),
            "circuit_ids": [str(entry["circuit_id"])],
            "status": "prepared_only" if dry_run else "pending",
            "job_id": None,
            "logical_depth": int(circuit.depth),
        }
        if not dry_run:
            kwargs: dict[str, Any] = {"shots": int(entry["shots"])}
            if s3_bucket:
                kwargs["s3_destination_folder"] = (s3_bucket, s3_prefix)
            _record_submission_start(state, state_path, batch)
            try:
                task = device.run(circuit, **kwargs)
                batch["job_id"] = task.id
            except Exception:
                _record_submission_failure(state, state_path, batch)
                raise
            batch["status"] = "pending"
            state["status"] = "submitted"
            write_json(state_path, state)
        else:
            state["batches"].append(batch)
            write_json(state_path, state)
    return state


def _ionq_result_counts(result: Any, index: int, batch_size: int) -> dict[Any, int]:
    # qiskit-ionq may reconstruct QPU counts by rounding returned
    # probabilities. Per-shot memory preserves the exact submitted budget.
    try:
        memory = result.get_memory(index)
        if isinstance(memory, str):
            memory = [memory]
        if memory:
            return dict(Counter(str(bitstring).replace(" ", "") for bitstring in memory))
    except Exception:
        pass
    try:
        return result.get_counts(index)
    except Exception:
        raw = result.get_counts()
        if isinstance(raw, list):
            return raw[index]
        if batch_size == 1:
            return raw
        raise


def retrieve_remote(
    workload: dict[str, Any],
    state: dict[str, Any],
    wait: bool,
    state_path: Path,
    ionq_gateset: str = "qis",
    ibm_channel: str = "ibm_quantum_platform",
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    if state["workload_id"] != workload["workload_id"]:
        raise ValueError("Execution state belongs to a different workload")
    provider_name = str(state["provider"])
    if provider_name not in REMOTE_PROVIDERS:
        raise ValueError(f"Cannot retrieve provider {provider_name}")
    if state.get("dry_run"):
        raise ValueError("A dry-run execution has no remote results")

    config = config_from_dict(workload["model"]["evolution_config"])
    counts_by_circuit: dict[str, dict[str, int]] = {}
    existing_counts_path = state_path.with_name("counts.json")
    if existing_counts_path.exists():
        existing = json.loads(existing_counts_path.read_text(encoding="utf-8"))
        counts_by_circuit.update(existing.get("counts", {}))

    if provider_name == "ibm":
        from qiskit_ibm_runtime import QiskitRuntimeService

        token = os.getenv("IBM_QUANTUM_TOKEN")
        client = (
            QiskitRuntimeService(channel=ibm_channel, token=token)
            if token
            else QiskitRuntimeService(channel=ibm_channel)
        )

        def retrieve_job(job_id: str):
            return client.job(job_id)

    elif provider_name == "ionq":
        from qiskit_ionq import IonQProvider

        token = os.getenv("IONQ_API_KEY")
        ionq_provider = IonQProvider(token=token) if token else IonQProvider()
        backend = _resolve_ionq_backend(
            ionq_provider,
            str(state.get("backend_request", state["backend"])),
            str(state.get("gateset", ionq_gateset)),
        )

        def retrieve_job(job_id: str):
            return backend.retrieve_job(job_id)

    else:
        from braket.aws import AwsQuantumTask

        retrieve_job = AwsQuantumTask

    for batch in state["batches"]:
        circuit_ids = [str(value) for value in batch["circuit_ids"]]
        if all(circuit_id in counts_by_circuit for circuit_id in circuit_ids):
            batch["status"] = "completed"
            continue
        job = retrieve_job(str(batch["job_id"]))
        if provider_name == "braket":
            status = str(job.state())
            complete = status == "COMPLETED"
        else:
            status = str(job.status())
            complete = status.upper().endswith("DONE")
        batch["remote_status"] = status
        terminal_failure = status.upper().endswith(
            ("ERROR", "FAILED", "CANCELLED", "CANCELED")
        )
        if terminal_failure:
            batch["status"] = "failed"
            write_json(state_path, state)
            continue
        if not complete and not wait:
            continue
        result = job.result()
        if provider_name == "ibm":
            try:
                raw_usage = getattr(job, "usage_estimation")
                usage = dict(raw_usage() if callable(raw_usage) else raw_usage)
            except Exception as error:
                usage = {"quantum_seconds": None, "usage_error": repr(error)}
                try:
                    usage["runtime_usage_seconds"] = float(job.usage())
                except Exception:
                    pass
            batch["qpu_usage"] = usage
            for pub_result, circuit_id in zip(result, circuit_ids):
                counts_by_circuit[circuit_id] = canonical_counts(
                    _qiskit_counts_from_pub_result(pub_result),
                    config.n_qubits,
                    "qiskit",
                )
        elif provider_name == "ionq":
            for index, circuit_id in enumerate(circuit_ids):
                counts_by_circuit[circuit_id] = canonical_counts(
                    _ionq_result_counts(result, index, len(circuit_ids)),
                    config.n_qubits,
                    "qiskit",
                )
        else:
            counts_by_circuit[circuit_ids[0]] = canonical_counts(
                dict(result.measurement_counts),
                config.n_qubits,
                "q0_first",
            )
        batch["status"] = "completed"
        write_json(
            existing_counts_path,
            {
                "schema": "hamiltonian-kernel-counts-v1",
                "workload_id": workload["workload_id"],
                "provider": provider_name,
                "backend": state["backend"],
                "counts": counts_by_circuit,
            },
        )
        write_json(state_path, state)

    expected = {str(entry["circuit_id"]) for entry in _entries(workload)}
    if set(counts_by_circuit) == expected:
        state["status"] = "completed"
    elif any(batch.get("status") == "failed" for batch in state["batches"]):
        state["status"] = "failed"
    else:
        state["status"] = "pending"
    _update_state_resource_axes(state, workload)
    write_json(state_path, state)
    return state, counts_by_circuit
