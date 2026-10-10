"""Small IBM validation pilot, gated on completed frozen v3 results."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .hardware_providers import (
    IBM_SAMPLER_RUNTIME_OPTIONS,
    _backend_snapshot,
    _save_qiskit_reproducibility_bundle,
)
from .trotter_scaling_v3 import (
    _dataset,
    _digest,
    _logical_circuit,
    _write_json,
    load_protocol,
)
from .trotter_scaling_full import generate_terms


PILOT_SHOTS = 128
PILOT_TRANSPILE_SEED = 20261009


def _pilot_gate(output_dir: Path) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    protocol, payload = load_protocol(output_dir / "protocol.json")
    if protocol.profile != "full":
        raise RuntimeError("IBM pilot requires the full v3 profile")
    required_inputs = (
        "progress.json", "holdout_progress.json",
        "final_selection_before_holdout.json", "v3_summary.json",
    )
    if any(not (output_dir / name).exists() for name in required_inputs):
        raise RuntimeError("IBM pilot requires complete development, holdout and v3 summary artifacts")
    progress = json.loads((output_dir / "progress.json").read_text(encoding="utf-8"))
    holdout = json.loads((output_dir / "holdout_progress.json").read_text(encoding="utf-8"))
    selection = json.loads((output_dir / "final_selection_before_holdout.json").read_text(encoding="utf-8"))
    if progress.get("status") != "complete" or holdout.get("status") != "complete":
        raise RuntimeError("complete v3 development and holdout are required")
    if any(item.get("protocol_hash") != payload["protocol_hash"] for item in (progress, holdout, selection)):
        raise ValueError("pilot inputs do not match frozen protocol")
    if holdout.get("selection_hash") != selection.get("selection_hash"):
        raise ValueError("holdout/selection hash mismatch")
    if selection["selection_hash"] != _digest({k: v for k, v in selection.items() if k != "selection_hash"}):
        raise ValueError("final selection was modified")
    summary = json.loads((output_dir / "v3_summary.json").read_text(encoding="utf-8"))
    if summary.get("protocol_hash") != payload["protocol_hash"] or summary.get("confirmatory_status") != "inference_computed":
        raise RuntimeError("IBM pilot requires completed v3 inference and resource/classical audit")
    for required in ("classical_baselines.csv", "resource_factorial_summary.csv", "compatible_policies.csv", "preregistered_inference.csv"):
        if not (output_dir / required).exists():
            raise RuntimeError(f"IBM pilot prerequisite missing: {required}")
    return protocol, payload, selection


def freeze_pilot(output_dir: Path) -> dict[str, Any]:
    protocol, payload, selection = _pilot_gate(output_dir)
    # Physical feasibility is prioritized, not held-out model performance.
    target_conditions = [
        (2, "chain", "ising_zz_x_z", 20),
        (3, "chain", "random_k_local", 20),
    ]
    highest_shots = max(protocol.shot_budgets)
    highest_two_qubit = max(protocol.two_qubit_gate_shot_budgets)
    lowest_depth = min(protocol.depth_budgets)
    choices = []
    for n, topology, profile, seed in target_conditions:
        condition_id = f"n{n}_{topology}_{profile}_s{seed}"
        selected = [
            item for item in selection["selections"]
            if item["condition_id"] == condition_id
            and item["replicate"] == 0
            and item["cell"] == {
                "depth": lowest_depth,
                "circuit_shots": highest_shots,
                "two_qubit_gate_shots": highest_two_qubit,
            }
        ]
        if len(selected) != 1:
            raise RuntimeError(f"pilot condition unavailable: {condition_id}")
        choices.append({
            "condition_id": condition_id,
            "n_qubits": n,
            "topology": topology,
            "hamiltonian_profile": profile,
            "hamiltonian_seed": seed,
            "order": selected[0]["selection"]["order"],
            "delta_t": selected[0]["selection"]["delta_t"],
            "cell_id": selected[0]["cell_id"],
        })
    pilot = {
        "schema": "trotter-scaling.ibm-pilot.v3",
        "status": "frozen_before_qpu",
        "protocol_hash": payload["protocol_hash"],
        "selection_hash": selection["selection_hash"],
        "holdout_sha256": payload["holdout_sha256"],
        "condition_policy": "fixed n=2 and n=3 conditions, seed=20, shallowest depth cell, largest shot and 2Q budgets; no holdout performance ranking",
        "pairs_per_condition": [["dev", 0, "dev", 0], ["holdout", 0, "holdout", 0], ["holdout", 0, "dev", 0], ["holdout", 0, "dev", 1], ["holdout", 1, "dev", 0], ["holdout", 1, "dev", 1]],
        "shots_per_circuit": PILOT_SHOTS,
        "transpile_seed": PILOT_TRANSPILE_SEED,
        "choices": choices,
    }
    pilot["pilot_hash"] = _digest(pilot)
    path = output_dir / "ibm_pilot" / "pilot_plan.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old != pilot:
            raise FileExistsError("a different IBM pilot is already frozen")
    else:
        _write_json(path, pilot)
    return pilot


def _pilot_circuits(protocol: Any, plan: dict[str, Any]):
    development, _ = _dataset(protocol)
    holdout, metadata = _dataset(protocol, holdout=True)
    if metadata["dataset_sha256"] != plan["holdout_sha256"]:
        raise ValueError("held-out data do not match pilot plan")
    circuits = []
    circuit_ids = []
    for choice in plan["choices"]:
        terms = generate_terms(
            protocol, choice["n_qubits"], choice["topology"],
            choice["hamiltonian_profile"], choice["hamiltonian_seed"],
        )
        template, parameters = _logical_circuit(
            tuple(term.label for term in terms), choice["order"],
            choice["delta_t"], protocol.evolution_time,
        )
        def assigned(source: str, index: int):
            x = development.x[index] if source == "dev" else holdout.x[index]
            return template.assign_parameters({parameter: term.coefficient(x) for parameter, term in zip(parameters, terms)})
        for index, (left_source, left_index, right_source, right_index) in enumerate(plan["pairs_per_condition"]):
            from qiskit import QuantumCircuit

            logical = QuantumCircuit(choice["n_qubits"])
            logical.reset(range(choice["n_qubits"]))
            logical.compose(assigned(left_source, left_index), inplace=True)
            logical.compose(assigned(right_source, right_index).inverse(), inplace=True)
            logical.measure_all()
            circuits.append(logical)
            circuit_ids.append(f"{choice['condition_id']}_pair{index}")
    return circuit_ids, circuits


def compile_or_submit(output_dir: Path, backend_name: str, submit: bool = False) -> dict[str, Any]:
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    protocol, payload, _ = _pilot_gate(output_dir)
    plan = freeze_pilot(output_dir)
    pilot_dir = output_dir / "ibm_pilot"
    state_path = pilot_dir / "run_state.json"
    if state_path.exists():
        raise FileExistsError("IBM pilot already compiled or submitted; do not duplicate it")
    service = QiskitRuntimeService(channel="ibm_quantum_platform")
    backend = service.least_busy(operational=True, simulator=False, min_num_qubits=3) if backend_name == "least_busy" else service.backend(backend_name)
    if getattr(backend.configuration(), "simulator", False):
        raise ValueError("the pilot requires a physical QPU backend")
    circuit_ids, logical = _pilot_circuits(protocol, plan)
    pass_manager = generate_preset_pass_manager(
        backend=backend, optimization_level=1,
        seed_transpiler=PILOT_TRANSPILE_SEED,
    )
    compiled = pass_manager.run(logical)
    if not isinstance(compiled, list):
        compiled = [compiled]
    snapshot_path = pilot_dir / "backend_target_calibration.json"
    _write_json(snapshot_path, _backend_snapshot(backend))
    reproducibility = _save_qiskit_reproducibility_bundle(
        pilot_dir / "qpy", 0, circuit_ids, logical, compiled,
        PILOT_TRANSPILE_SEED, 1, IBM_SAMPLER_RUNTIME_OPTIONS,
        {"explicit_reset_each_circuit": True}, None,
    )
    manifest = {
        "schema": "trotter-scaling.ibm-pilot-run.v3",
        "pilot_hash": plan["pilot_hash"],
        "protocol_hash": payload["protocol_hash"],
        "backend": backend.name,
        "backend_snapshot": str(snapshot_path),
        "backend_snapshot_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        "reproducibility": reproducibility,
        "circuit_ids": circuit_ids,
        "shots_per_circuit": PILOT_SHOTS,
        "circuit_shots": PILOT_SHOTS * len(circuit_ids),
        "map_executions": 2 * PILOT_SHOTS * len(circuit_ids),
        "two_qubit_gate_shots": PILOT_SHOTS * sum(sum(instruction.operation.num_qubits == 2 for instruction in circuit.data) for circuit in compiled),
        "qpu_time_seconds": None,
        "qpu_credits": None,
        "job_id": None,
        "status": "compiled_only",
    }
    _write_json(state_path, manifest)
    if submit:
        sampler = SamplerV2(mode=backend, options=IBM_SAMPLER_RUNTIME_OPTIONS)
        manifest["status"] = "submission_started"
        _write_json(state_path, manifest)
        try:
            job = sampler.run(compiled, shots=PILOT_SHOTS)
        except Exception:
            manifest["status"] = "submission_unknown"
            _write_json(state_path, manifest)
            raise
        manifest["job_id"] = job.job_id()
        manifest["status"] = "submitted"
        _write_json(state_path, manifest)
    return manifest


def retrieve(output_dir: Path) -> dict[str, Any]:
    from qiskit_ibm_runtime import QiskitRuntimeService

    _pilot_gate(output_dir)
    state_path = output_dir / "ibm_pilot" / "run_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not state.get("job_id"):
        raise RuntimeError("IBM pilot has no submitted job ID")
    service = QiskitRuntimeService(channel="ibm_quantum_platform")
    job = service.job(state["job_id"])
    status = str(job.status())
    state["remote_status"] = status
    if status.split(".")[-1].upper() not in {"DONE", "COMPLETED"}:
        _write_json(state_path, state)
        return state
    result = job.result()
    counts = {}
    for index, circuit_id in enumerate(state["circuit_ids"]):
        counts[circuit_id] = {
            str(bitstring): int(count)
            for bitstring, count in result[index].data.meas.get_counts().items()
        }
    usage = job.usage() if hasattr(job, "usage") else None
    state["counts"] = counts
    state["zero_probabilities"] = {
        circuit_id: values.get("0" * int(circuit_id.split("_", 1)[0][1:]), 0)
        / max(sum(values.values()), 1)
        for circuit_id, values in counts.items()
    }
    state["usage"] = usage
    if isinstance(usage, (int, float)):
        state["qpu_time_seconds"] = float(usage)
    elif isinstance(usage, dict):
        state["qpu_time_seconds"] = usage.get("quantum_seconds")
        state["qpu_credits"] = usage.get("credits")
    state["status"] = "retrieved"
    _write_json(state_path, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "compile", "submit", "retrieve"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend", default="least_busy")
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze_pilot(args.output_dir)
    elif args.action == "retrieve":
        result = retrieve(args.output_dir)
    else:
        result = compile_or_submit(args.output_dir, args.backend, args.action == "submit")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
