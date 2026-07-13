from __future__ import annotations

import argparse
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


def apply_h2_feature_map(values: np.ndarray, cfg: Any) -> None:
    import pennylane as qml

    angles = np.pi * cfg.angle_scale * np.asarray(values, dtype=float)
    for wire in range(cfg.qubits):
        qml.Hadamard(wires=wire)
    for wire, angle in enumerate(angles):
        qml.RZ(-2.0 * float(angle), wires=wire)
    if cfg.entanglement > 0.0:
        pair_angles = np.pi - angles
        for left in range(cfg.qubits - 1):
            for right in range(left + 1, cfg.qubits):
                theta = -2.0 * cfg.entanglement * pair_angles[left] * pair_angles[right]
                qml.IsingZZ(float(theta), wires=[left, right])


def pennylane_overlap_kernel(
    x: np.ndarray,
    cfg: Any,
    device_name: str,
    shots: int | None,
) -> np.ndarray:
    import pennylane as qml

    dev = qml.device(device_name, wires=cfg.qubits, shots=shots)

    @qml.qnode(dev)
    def overlap_probability(left, right):
        apply_h2_feature_map(left, cfg)
        qml.adjoint(apply_h2_feature_map)(right, cfg)
        return qml.probs(wires=list(range(cfg.qubits)))

    n = len(x)
    kernel = np.eye(n, dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            probs = overlap_probability(x[i], x[j])
            value = float(np.asarray(probs)[0])
            kernel[i, j] = value
            kernel[j, i] = value
    return kernel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Realizacja hipotezy H2 w PennyLane, z urzadzeniem Xanadu-kompatybilnym."
    )
    parser.add_argument("--dataset", default="wdbc", choices=["wdbc", "wine", "optdigits"])
    parser.add_argument("--seed", type=int, default=20260709)
    parser.add_argument("--samples-per-class", type=int, default=3)
    parser.add_argument("--qubits", type=int, default=None)
    parser.add_argument("--angle-scale", type=float, default=None)
    parser.add_argument("--entanglement", type=float, default=None)
    parser.add_argument(
        "--device",
        default="default.qubit",
        help="Np. default.qubit dla testu lokalnego albo nazwa urzadzenia/pluginu PennyLane.",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=None,
        help="Liczba strzalow. Brak wartosci oznacza dokladny tryb analityczny, jesli urzadzenie go wspiera.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "h2_pennylane_xanadu_realization.json",
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

    t0 = time.perf_counter()
    kernel = pennylane_overlap_kernel(
        x,
        cfg,
        device_name=args.device,
        shots=args.shots,
    )
    execution = {
        "mode": "overlap_probability",
        "device": args.device,
        "shots": args.shots,
        "runtime_s": time.perf_counter() - t0,
    }
    payload: dict[str, Any] = {
        "library": "pennylane",
        "target": "Xanadu/PennyLane device interface",
        "dataset": problem["dataset"],
        "seed": problem["seed"],
        "samples_per_class": problem["samples_per_class"],
        "config": config_to_dict(cfg),
        "pca_explained": problem["pca_explained"],
        "labels": y,
        "reference_kernel": problem["reference_kernel"],
        "reference_diagnostics": problem["reference_diagnostics"],
        "measured_kernel": kernel,
        "measured_diagnostics": kernel_diagnostics(kernel, y),
        "execution": execution,
        "xanadu_note": (
            "Ten wariant realizuje dowod H2 jako kubitowa mape ZZFeatureMap w "
            "interfejsie PennyLane. Fizyczny komputer fotoniczny Xanadu wymagalby "
            "osobnej mapy cech CV/fotonicznej i wtedy nalezaloby dowiesc nowego "
            "jadra, nie tylko uruchomic ten sam obwod."
        ),
    }
    write_json(args.output, payload)
    print(f"Zapisano {args.output}")
    print(f"Urzadzenie: {args.device}")
    print(f"Konfiguracja H2: {payload['config']}")
    print(f"Alignment: {payload['measured_diagnostics']['alignment']:.6f}")
    print(f"Min. wartosc wlasna: {payload['measured_diagnostics']['min_eigenvalue']:.6e}")


if __name__ == "__main__":
    main()
