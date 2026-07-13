from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

import numpy as np

from h2_hardware_common import (
    OUT_DIR,
    config_to_dict,
    kernel_diagnostics,
    prepare_h2_problem,
    write_json,
)


def build_h2_feature_map(x: np.ndarray, cfg: Any):
    from qiskit import QuantumCircuit

    values = np.asarray(x, dtype=float)
    if len(values) != cfg.qubits:
        raise ValueError(f"Oczekiwano {cfg.qubits} cech, otrzymano {len(values)}.")

    angles = np.pi * cfg.angle_scale * values
    qc = QuantumCircuit(cfg.qubits, name="H2_ZZFeatureMap")
    qc.h(range(cfg.qubits))
    for wire, angle in enumerate(angles):
        qc.rz(-2.0 * float(angle), wire)
    if cfg.entanglement > 0.0:
        pair_angles = np.pi - angles
        for left in range(cfg.qubits - 1):
            for right in range(left + 1, cfg.qubits):
                theta = -2.0 * cfg.entanglement * pair_angles[left] * pair_angles[right]
                qc.rzz(float(theta), left, right)
    return qc


def exact_statevector_kernel(x: np.ndarray, cfg: Any) -> np.ndarray:
    from qiskit.quantum_info import Statevector

    states = [
        Statevector.from_instruction(build_h2_feature_map(row, cfg)).data
        for row in x
    ]
    n = len(states)
    kernel = np.eye(n, dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            overlap = np.vdot(states[i], states[j])
            value = float(np.abs(overlap) ** 2)
            kernel[i, j] = value
            kernel[j, i] = value
    return kernel


def build_overlap_circuit(x_left: np.ndarray, x_right: np.ndarray, cfg: Any):
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(cfg.qubits, cfg.qubits)
    qc.compose(build_h2_feature_map(x_left, cfg), inplace=True)
    qc.compose(build_h2_feature_map(x_right, cfg).inverse(), inplace=True)
    qc.measure(range(cfg.qubits), range(cfg.qubits))
    return qc


def upper_triangle_overlap_circuits(x: np.ndarray, cfg: Any):
    circuits = []
    pairs = []
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            circuit = build_overlap_circuit(x[i], x[j], cfg)
            circuit.name = f"h2_overlap_{i}_{j}"
            circuits.append(circuit)
            pairs.append((i, j))
    return circuits, pairs


def _is_zero_key(key: Any) -> bool:
    text = str(key).replace(" ", "")
    if text.startswith("0x"):
        return int(text, 16) == 0
    return text.strip("0") == ""


def zero_probability_from_counts(counts: dict[Any, int]) -> float:
    shots = sum(int(v) for v in counts.values())
    if shots <= 0:
        raise ValueError("Brak zliczen w wyniku Samplera.")
    zero_shots = sum(int(v) for k, v in counts.items() if _is_zero_key(k))
    return zero_shots / shots


def counts_from_pub_result(pub_result: Any) -> dict[Any, int]:
    data = getattr(pub_result, "data", None)
    if data is None:
        raise RuntimeError("Wynik Samplera nie zawiera pola data.")

    for attr in ("meas", "c", "cr", "classical"):
        register = getattr(data, attr, None)
        if register is not None and hasattr(register, "get_counts"):
            return register.get_counts()

    for attr in dir(data):
        if attr.startswith("_"):
            continue
        register = getattr(data, attr)
        if hasattr(register, "get_counts"):
            return register.get_counts()

    raise RuntimeError(
        "Nie umiem odczytac zliczen z wyniku SamplerV2. "
        "Sprawdz nazwe rejestru klasycznego w obiekcie result.data."
    )


def ibm_runtime_kernel(
    x: np.ndarray,
    cfg: Any,
    backend_name: str,
    channel: str,
    shots: int,
    optimization_level: int,
    dry_run: bool,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler

    token = os.getenv("IBM_QUANTUM_TOKEN")
    if token:
        service = QiskitRuntimeService(channel=channel, token=token)
    else:
        service = QiskitRuntimeService(channel=channel)

    if backend_name == "least_busy":
        backend = service.least_busy(
            operational=True,
            simulator=False,
            min_num_qubits=cfg.qubits,
        )
    else:
        backend = service.backend(backend_name)

    circuits, pairs = upper_triangle_overlap_circuits(x, cfg)
    pass_manager = generate_preset_pass_manager(
        backend=backend,
        optimization_level=optimization_level,
    )
    isa_circuits = pass_manager.run(circuits)
    backend_label = getattr(backend, "name", str(backend))
    if callable(backend_label):
        backend_label = backend_label()
    metadata = {
        "backend": backend_label,
        "backend_mode": backend_name,
        "shots": shots,
        "circuit_count": len(isa_circuits),
        "pair_count": len(pairs),
        "optimization_level": optimization_level,
        "dry_run": dry_run,
    }
    if dry_run:
        return None, metadata

    sampler = Sampler(mode=backend)
    t0 = time.perf_counter()
    job = sampler.run(isa_circuits, shots=shots)
    result = job.result()
    metadata["runtime_s"] = time.perf_counter() - t0
    metadata["job_id"] = job.job_id() if callable(getattr(job, "job_id", None)) else None

    kernel = np.eye(len(x), dtype=float)
    for pub_result, (i, j) in zip(result, pairs):
        value = zero_probability_from_counts(counts_from_pub_result(pub_result))
        kernel[i, j] = value
        kernel[j, i] = value
    return kernel, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Realizacja hipotezy H2 w Qiskit/IBM Quantum."
    )
    parser.add_argument("--dataset", default="wdbc", choices=["wdbc", "wine", "optdigits"])
    parser.add_argument("--seed", type=int, default=20260709)
    parser.add_argument("--samples-per-class", type=int, default=3)
    parser.add_argument("--qubits", type=int, default=None)
    parser.add_argument("--angle-scale", type=float, default=None)
    parser.add_argument("--entanglement", type=float, default=None)
    parser.add_argument(
        "--mode",
        choices=["statevector", "ibm"],
        default="statevector",
        help="statevector liczy dokladnie lokalnie; ibm wysyla obwody overlap do IBM Runtime.",
    )
    parser.add_argument("--backend", default="least_busy")
    parser.add_argument("--channel", default="ibm_quantum_platform")
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument("--optimization-level", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "h2_qiskit_ibm_realization.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    problem = prepare_h2_problem(
        args.dataset,
        seed=args.seed,
        samples_per_class=args.samples_per_class,
        qubits=args.qubits,
        angle_scale=args.angle_scale,
        entanglement=args.entanglement,
    )
    cfg = problem["config"]
    x = problem["x"]
    y = problem["y"]

    if args.mode == "statevector":
        t0 = time.perf_counter()
        kernel = exact_statevector_kernel(x, cfg)
        execution = {"mode": "statevector", "runtime_s": time.perf_counter() - t0}
    else:
        kernel, execution = ibm_runtime_kernel(
            x,
            cfg,
            backend_name=args.backend,
            channel=args.channel,
            shots=args.shots,
            optimization_level=args.optimization_level,
            dry_run=args.dry_run,
        )

    payload: dict[str, Any] = {
        "library": "qiskit",
        "target": "IBM Quantum" if args.mode == "ibm" else "local Statevector",
        "dataset": problem["dataset"],
        "seed": problem["seed"],
        "samples_per_class": problem["samples_per_class"],
        "config": config_to_dict(cfg),
        "pca_explained": problem["pca_explained"],
        "labels": y,
        "reference_kernel": problem["reference_kernel"],
        "reference_diagnostics": problem["reference_diagnostics"],
        "execution": execution,
    }
    if kernel is not None:
        payload["measured_kernel"] = kernel
        payload["measured_diagnostics"] = kernel_diagnostics(kernel, y)

    write_json(args.output, payload)
    print(f"Zapisano {args.output}")
    print(f"Tryb: {payload['target']}")
    print(f"Konfiguracja H2: {payload['config']}")
    if kernel is not None:
        print(f"Alignment: {payload['measured_diagnostics']['alignment']:.6f}")
        print(f"Min. wartosc wlasna: {payload['measured_diagnostics']['min_eigenvalue']:.6e}")


if __name__ == "__main__":
    main()
