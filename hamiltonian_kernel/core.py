from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EvolutionConfig:
    """Configuration of the data-dependent transverse-field Ising map."""

    n_qubits: int
    evolution_time: float = 1.0
    transverse_field: float = 0.7
    interaction_strength: float = 0.6
    topology: str = "chain"
    method: str = "trotter"
    trotter_order: int = 2
    trotter_steps: int = 2

    def validate(self) -> None:
        if self.n_qubits < 1:
            raise ValueError("n_qubits must be positive")
        if self.evolution_time <= 0:
            raise ValueError("evolution_time must be positive")
        if self.topology not in {"chain", "ring", "all_to_all"}:
            raise ValueError(f"Unsupported topology: {self.topology}")
        if self.method not in {"exact", "trotter"}:
            raise ValueError(f"Unsupported evolution method: {self.method}")
        if self.method == "trotter":
            if self.trotter_order not in {1, 2}:
                raise ValueError("trotter_order must be 1 or 2")
            if self.trotter_steps < 1:
                raise ValueError("trotter_steps must be positive")


def interaction_edges(n_qubits: int, topology: str) -> tuple[tuple[int, int], ...]:
    if topology == "chain":
        return tuple((left, left + 1) for left in range(n_qubits - 1))
    if topology == "ring":
        if n_qubits < 3:
            return tuple((left, left + 1) for left in range(n_qubits - 1))
        return tuple((left, left + 1) for left in range(n_qubits - 1)) + ((n_qubits - 1, 0),)
    if topology == "all_to_all":
        return tuple((left, right) for left in range(n_qubits) for right in range(left + 1, n_qubits))
    raise ValueError(f"Unsupported topology: {topology}")


def z_eigenvalues(n_qubits: int) -> np.ndarray:
    """Return computational-basis eigenvalues of each local Pauli Z."""

    basis = np.arange(2**n_qubits, dtype=np.uint64)[:, None]
    positions = np.arange(n_qubits, dtype=np.uint64)[None, :]
    bits = (basis >> positions) & 1
    return 1.0 - 2.0 * bits.astype(float)


def plus_state(n_qubits: int) -> np.ndarray:
    return np.ones(2**n_qubits, dtype=np.complex128) / np.sqrt(2**n_qubits)


def diagonal_hamiltonian(x: np.ndarray, config: EvolutionConfig) -> np.ndarray:
    """Diagonal A(x) = sum_i x_i Z_i + J sum_(i,j) Z_i Z_j."""

    config.validate()
    x = np.asarray(x, dtype=float)
    if x.shape != (config.n_qubits,):
        raise ValueError(f"Expected x with shape {(config.n_qubits,)}, got {x.shape}")

    z_values = z_eigenvalues(config.n_qubits)
    diagonal = z_values @ x
    for left, right in interaction_edges(config.n_qubits, config.topology):
        diagonal += config.interaction_strength * z_values[:, left] * z_values[:, right]
    return diagonal


def _apply_diagonal(state: np.ndarray, diagonal: np.ndarray, duration: float) -> np.ndarray:
    return state * np.exp(-1j * duration * diagonal)


def _apply_x_layer(state: np.ndarray, angle: float, n_qubits: int) -> np.ndarray:
    """Apply exp(-i angle sum_i X_i), exploiting commuting local rotations."""

    result = np.asarray(state, dtype=np.complex128).copy()
    cosine = np.cos(angle)
    sine = np.sin(angle)
    for qubit in range(n_qubits):
        stride = 1 << qubit
        block = stride << 1
        for start in range(0, len(result), block):
            zero = result[start : start + stride].copy()
            one = result[start + stride : start + block].copy()
            result[start : start + stride] = cosine * zero - 1j * sine * one
            result[start + stride : start + block] = cosine * one - 1j * sine * zero
    return result


def evolve_trotter(x: np.ndarray, config: EvolutionConfig) -> np.ndarray:
    """Prepare a feature state with first- or second-order product formulas."""

    config.validate()
    if config.method != "trotter":
        raise ValueError("evolve_trotter requires method='trotter'")

    diagonal = diagonal_hamiltonian(x, config)
    state = plus_state(config.n_qubits)
    step_time = config.evolution_time / config.trotter_steps
    x_angle = config.transverse_field * step_time

    if config.trotter_order == 1:
        # Each step realizes exp(-i B dt) exp(-i A dt).
        for _ in range(config.trotter_steps):
            state = _apply_diagonal(state, diagonal, step_time)
            state = _apply_x_layer(state, x_angle, config.n_qubits)
    else:
        for _ in range(config.trotter_steps):
            state = _apply_diagonal(state, diagonal, 0.5 * step_time)
            state = _apply_x_layer(state, x_angle, config.n_qubits)
            state = _apply_diagonal(state, diagonal, 0.5 * step_time)

    return state


def _dense_transverse_hamiltonian(config: EvolutionConfig) -> np.ndarray:
    dimension = 2**config.n_qubits
    transverse = np.zeros((dimension, dimension), dtype=np.complex128)
    basis = np.arange(dimension)
    for qubit in range(config.n_qubits):
        flipped = basis ^ (1 << qubit)
        transverse[basis, flipped] += config.transverse_field
    return transverse


def evolve_exact(x: np.ndarray, config: EvolutionConfig) -> np.ndarray:
    """Prepare exp(-i H(x)t)|+> using exact Hermitian diagonalization."""

    config.validate()
    diagonal = diagonal_hamiltonian(x, config)
    hamiltonian = np.diag(diagonal.astype(np.complex128)) + _dense_transverse_hamiltonian(config)
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    initial = plus_state(config.n_qubits)
    coefficients = eigenvectors.conj().T @ initial
    phases = np.exp(-1j * config.evolution_time * eigenvalues)
    return eigenvectors @ (phases * coefficients)


def evolve_batch(x: np.ndarray, config: EvolutionConfig) -> np.ndarray:
    config.validate()
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or x.shape[1] != config.n_qubits:
        raise ValueError(f"Expected x with shape (samples, {config.n_qubits}), got {x.shape}")
    evolve = evolve_exact if config.method == "exact" else evolve_trotter
    return np.vstack([evolve(row, config) for row in x])


def fidelity_kernel(left_states: np.ndarray, right_states: np.ndarray) -> np.ndarray:
    left_states = np.asarray(left_states, dtype=np.complex128)
    right_states = np.asarray(right_states, dtype=np.complex128)
    return np.abs(left_states.conj() @ right_states.T) ** 2


def bloch_vectors(states: np.ndarray, n_qubits: int) -> np.ndarray:
    """Compute local (X, Y, Z) expectation values for every state and qubit."""

    states = np.atleast_2d(np.asarray(states, dtype=np.complex128))
    expected_dimension = 2**n_qubits
    if states.shape[1] != expected_dimension:
        raise ValueError(f"Expected state dimension {expected_dimension}, got {states.shape[1]}")

    vectors = np.empty((states.shape[0], n_qubits, 3), dtype=float)
    probabilities = np.abs(states) ** 2
    z_values = z_eigenvalues(n_qubits)
    vectors[:, :, 2] = probabilities @ z_values

    dimension = states.shape[1]
    for qubit in range(n_qubits):
        stride = 1 << qubit
        block = stride << 1
        coherence = np.zeros(states.shape[0], dtype=np.complex128)
        for start in range(0, dimension, block):
            zero = states[:, start : start + stride]
            one = states[:, start + stride : start + block]
            coherence += np.sum(zero.conj() * one, axis=1)
        vectors[:, qubit, 0] = 2.0 * coherence.real
        vectors[:, qubit, 1] = 2.0 * coherence.imag
    return vectors


def projected_kernel(left_bloch: np.ndarray, right_bloch: np.ndarray, gamma: float) -> np.ndarray:
    """RBF kernel on one-qubit reduced states using Hilbert-Schmidt distance."""

    if gamma <= 0:
        raise ValueError("gamma must be positive")
    left = np.asarray(left_bloch, dtype=float).reshape(len(left_bloch), -1)
    right = np.asarray(right_bloch, dtype=float).reshape(len(right_bloch), -1)
    left_norm = np.sum(left * left, axis=1)[:, None]
    right_norm = np.sum(right * right, axis=1)[None, :]
    squared_bloch_distance = np.maximum(left_norm + right_norm - 2.0 * (left @ right.T), 0.0)
    hilbert_schmidt_distance = 0.5 * squared_bloch_distance
    return np.exp(-gamma * hilbert_schmidt_distance)


def state_infidelity(reference: np.ndarray, approximation: np.ndarray) -> np.ndarray:
    reference = np.asarray(reference, dtype=np.complex128)
    approximation = np.asarray(approximation, dtype=np.complex128)
    if reference.shape != approximation.shape:
        raise ValueError("State batches must have identical shapes")
    overlaps = np.sum(reference.conj() * approximation, axis=1)
    return np.maximum(1.0 - np.abs(overlaps) ** 2, 0.0)


def circuit_resources(config: EvolutionConfig) -> dict[str, int | float]:
    """Estimate logical rotations and CX count before hardware transpilation."""

    config.validate()
    if config.method == "exact":
        return {
            "a_blocks": 0,
            "single_qubit_rotations": 0,
            "two_qubit_gates": 0,
            "logical_depth_proxy": 0,
        }

    edge_count = (
        len(interaction_edges(config.n_qubits, config.topology))
        if config.interaction_strength != 0.0
        else 0
    )
    if config.trotter_order == 1:
        a_blocks = config.trotter_steps
    else:
        # Adjacent half A blocks merge between symmetric Trotter steps.
        a_blocks = config.trotter_steps + 1
    x_blocks = config.trotter_steps
    return {
        "a_blocks": a_blocks,
        "single_qubit_rotations": a_blocks * config.n_qubits + x_blocks * config.n_qubits,
        "two_qubit_gates": 2 * edge_count * a_blocks,
        "logical_depth_proxy": a_blocks * (2 * edge_count + 1) + x_blocks,
    }
