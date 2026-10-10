from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis_output"


@dataclass(frozen=True)
class AnsatzSpec:
    name: str
    qubits: int
    layers: int
    samples: int
    seed: int


def ry(theta: float) -> np.ndarray:
    c = math.cos(theta / 2.0)
    s = math.sin(theta / 2.0)
    return np.array([[c, -s], [s, c]], dtype=complex)


def rz(theta: float) -> np.ndarray:
    return np.array(
        [[np.exp(-0.5j * theta), 0.0], [0.0, np.exp(0.5j * theta)]],
        dtype=complex,
    )


def crx(theta: float) -> np.ndarray:
    c = math.cos(theta / 2.0)
    s = math.sin(theta / 2.0)
    return np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, c, -1j * s],
            [0.0, 0.0, -1j * s, c],
        ],
        dtype=complex,
    )


def scar(theta: float, delta: float, phi: float) -> np.ndarray:
    """Skew-chiral amplitude router gate.

    The gate is an fSim-like exchange with a trainable chirality delta and a
    controlled phase phi:

    |00>, |11> get phase exp(-i phi/2);
    {|01>, |10>} is mixed by theta with phase direction delta and global
    phase exp(i phi/2).
    """

    p0 = np.exp(-0.5j * phi)
    p1 = np.exp(0.5j * phi)
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array(
        [
            [p0, 0.0, 0.0, 0.0],
            [0.0, p1 * c, -1j * p1 * np.exp(-1j * delta) * s, 0.0],
            [0.0, -1j * p1 * np.exp(1j * delta) * s, p1 * c, 0.0],
            [0.0, 0.0, 0.0, p0],
        ],
        dtype=complex,
    )


def apply_one_qubit(state: np.ndarray, gate: np.ndarray, qubit: int, n: int) -> np.ndarray:
    tensor = state.reshape([2] * n)
    tensor = np.moveaxis(tensor, qubit, 0)
    tensor = np.tensordot(gate, tensor, axes=([1], [0]))
    tensor = np.moveaxis(tensor, 0, qubit)
    return tensor.reshape(-1)


def apply_two_qubit(
    state: np.ndarray, gate: np.ndarray, q0: int, q1: int, n: int
) -> np.ndarray:
    tensor = state.reshape([2] * n)
    tensor = np.moveaxis(tensor, [q0, q1], [0, 1])
    original_shape = tensor.shape
    pair = tensor.reshape(4, -1)
    pair = gate @ pair
    tensor = pair.reshape(original_shape)
    tensor = np.moveaxis(tensor, [0, 1], [q0, q1])
    return tensor.reshape(-1)


def ring_edges(n: int) -> list[tuple[int, int]]:
    return [(i, (i + 1) % n) for i in range(n)]


def prepare_state(spec: AnsatzSpec, rng: np.random.Generator) -> np.ndarray:
    n = spec.qubits
    state = np.zeros(1 << n, dtype=complex)
    state[0] = 1.0

    for _ in range(spec.layers):
        for q in range(n):
            state = apply_one_qubit(state, ry(rng.uniform(0.0, 2.0 * np.pi)), q, n)
            state = apply_one_qubit(state, rz(rng.uniform(0.0, 2.0 * np.pi)), q, n)

        if spec.name == "local_ryrz":
            continue

        if spec.name == "crx_ring":
            for q0, q1 in ring_edges(n):
                state = apply_two_qubit(state, crx(rng.uniform(0.0, 2.0 * np.pi)), q0, q1, n)
            continue

        if spec.name == "scar_ring":
            delta = rng.uniform(0.0, 2.0 * np.pi)
            phi = rng.uniform(0.0, 2.0 * np.pi)
            for q0, q1 in ring_edges(n):
                theta = rng.uniform(0.0, 2.0 * np.pi)
                state = apply_two_qubit(state, scar(theta, delta, phi), q0, q1, n)
            continue

        raise ValueError(f"Unknown ansatz: {spec.name}")

    return state / np.linalg.norm(state)


def one_qubit_purity(state: np.ndarray, qubit: int, n: int) -> float:
    tensor = state.reshape([2] * n)
    tensor = np.moveaxis(tensor, qubit, 0).reshape(2, -1)
    rho = tensor @ tensor.conj().T
    return float(np.real(np.trace(rho @ rho)))


def meyer_wallach_q(state: np.ndarray, n: int) -> float:
    purities = [one_qubit_purity(state, q, n) for q in range(n)]
    return float(2.0 * (1.0 - np.mean(purities)))


def sample_states(spec: AnsatzSpec) -> np.ndarray:
    rng = np.random.default_rng(spec.seed)
    states = np.empty((spec.samples, 1 << spec.qubits), dtype=complex)
    for i in range(spec.samples):
        states[i] = prepare_state(spec, rng)
    return states


def haar_bin_probabilities(dim: int, bins: np.ndarray) -> np.ndarray:
    # For two Haar-random pure states in complex dimension d, the fidelity has
    # density (d - 1) * (1 - f) ** (d - 2). The CDF is 1 - (1 - f) ** (d - 1).
    cdf = 1.0 - (1.0 - bins) ** (dim - 1)
    probs = np.diff(cdf)
    return probs / np.sum(probs)


def expressibility_kl(states: np.ndarray, bins_count: int = 75) -> float:
    dim = states.shape[1]
    rng = np.random.default_rng(12345)
    pairs = rng.integers(0, len(states), size=(min(20000, len(states) * 20), 2))
    mask = pairs[:, 0] != pairs[:, 1]
    pairs = pairs[mask]
    fidelities = np.abs(np.sum(states[pairs[:, 0]].conj() * states[pairs[:, 1]], axis=1)) ** 2
    bins = np.linspace(0.0, 1.0, bins_count + 1)
    observed, _ = np.histogram(fidelities, bins=bins)
    observed = observed.astype(float) + 1e-12
    observed /= observed.sum()
    expected = haar_bin_probabilities(dim, bins) + 1e-12
    expected /= expected.sum()
    return float(np.sum(observed * np.log(observed / expected)))


def summarize(spec: AnsatzSpec) -> dict[str, float | int | str]:
    states = sample_states(spec)
    ent = np.array([meyer_wallach_q(s, spec.qubits) for s in states])
    params_per_layer = {
        "local_ryrz": 2 * spec.qubits,
        "crx_ring": 3 * spec.qubits,
        "scar_ring": 3 * spec.qubits + 2,
    }[spec.name]
    twoq_per_layer = {
        "local_ryrz": 0,
        "crx_ring": spec.qubits,
        "scar_ring": spec.qubits,
    }[spec.name]
    return {
        "ansatz": spec.name,
        "qubits": spec.qubits,
        "layers": spec.layers,
        "samples": spec.samples,
        "parameters": params_per_layer * spec.layers,
        "two_qubit_gates": twoq_per_layer * spec.layers,
        "expressibility_kl": expressibility_kl(states),
        "mean_meyer_wallach_q": float(ent.mean()),
        "std_meyer_wallach_q": float(ent.std()),
    }


def main() -> None:
    rows = []
    for layers in [1, 2]:
        for name in ["local_ryrz", "crx_ring", "scar_ring"]:
            spec = AnsatzSpec(name=name, qubits=4, layers=layers, samples=1000, seed=20260712 + layers)
            rows.append(summarize(spec))

    out_csv = OUT / "vqe_scar_ansatz_results.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            row["ansatz"],
            "L=",
            row["layers"],
            "params=",
            row["parameters"],
            "2q=",
            row["two_qubit_gates"],
            "KL=",
            f"{row['expressibility_kl']:.6f}",
            "Q=",
            f"{row['mean_meyer_wallach_q']:.4f}",
        )
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
