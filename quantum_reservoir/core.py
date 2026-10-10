from __future__ import annotations

from dataclasses import dataclass, replace
from functools import reduce
from time import perf_counter

import numpy as np


IDENTITY = np.eye(2, dtype=np.complex128)
PAULI_X = np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
PAULI_Z = np.asarray([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)


@dataclass(frozen=True)
class ReservoirConfig:
    """Configuration for a reset-injected transverse-field Ising reservoir."""

    n_qubits: int = 4
    evolution_time: float = 0.8
    transverse_field: float = 0.9
    interaction_strength: float = 0.7
    local_field_strength: float = 0.5
    topology: str = "ring"
    disorder_seed: int = 7
    method: str = "exact"
    trotter_order: int = 2
    trotter_steps: int = 1

    def validate(self) -> None:
        if self.n_qubits < 2:
            raise ValueError("n_qubits must be at least 2 for a memory-bearing reset reservoir")
        if self.evolution_time <= 0:
            raise ValueError("evolution_time must be positive")
        if self.topology not in {"chain", "ring", "all_to_all"}:
            raise ValueError(f"Unsupported topology: {self.topology}")
        if self.method not in {"exact", "trotter"}:
            raise ValueError(f"Unsupported method: {self.method}")
        if self.method == "trotter":
            if self.trotter_order not in {1, 2}:
                raise ValueError("trotter_order must be 1 or 2")
            if self.trotter_steps < 1:
                raise ValueError("trotter_steps must be positive")

    def exact_version(self) -> "ReservoirConfig":
        return replace(self, method="exact")


def interaction_edges(n_qubits: int, topology: str) -> tuple[tuple[int, int], ...]:
    if topology == "chain":
        return tuple((left, left + 1) for left in range(n_qubits - 1))
    if topology == "ring":
        chain = tuple((left, left + 1) for left in range(n_qubits - 1))
        return chain if n_qubits == 2 else chain + ((n_qubits - 1, 0),)
    if topology == "all_to_all":
        return tuple(
            (left, right)
            for left in range(n_qubits)
            for right in range(left + 1, n_qubits)
        )
    raise ValueError(f"Unsupported topology: {topology}")


def _kron_all(operators: list[np.ndarray]) -> np.ndarray:
    return reduce(np.kron, operators)


def operator_on_qubit(operator: np.ndarray, qubit: int, n_qubits: int) -> np.ndarray:
    factors = [IDENTITY] * n_qubits
    factors[qubit] = operator
    return _kron_all(factors)


def _local_fields(config: ReservoirConfig) -> np.ndarray:
    rng = np.random.default_rng(config.disorder_seed)
    return config.local_field_strength * rng.uniform(-1.0, 1.0, size=config.n_qubits)


def hamiltonian_parts(config: ReservoirConfig) -> tuple[np.ndarray, np.ndarray]:
    """Return non-commuting A (Z/ZZ) and B (X) Hamiltonian blocks."""

    config.validate()
    dimension = 2**config.n_qubits
    diagonal_part = np.zeros((dimension, dimension), dtype=np.complex128)
    transverse_part = np.zeros_like(diagonal_part)
    z_operators = [operator_on_qubit(PAULI_Z, q, config.n_qubits) for q in range(config.n_qubits)]

    for field, z_operator in zip(_local_fields(config), z_operators, strict=True):
        diagonal_part += field * z_operator
    for left, right in interaction_edges(config.n_qubits, config.topology):
        diagonal_part += config.interaction_strength * (z_operators[left] @ z_operators[right])
    for qubit in range(config.n_qubits):
        transverse_part += config.transverse_field * operator_on_qubit(
            PAULI_X, qubit, config.n_qubits
        )
    return diagonal_part, transverse_part


def _hermitian_exponential(hamiltonian: np.ndarray, duration: float) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    phases = np.exp(-1j * duration * eigenvalues)
    return (eigenvectors * phases) @ eigenvectors.conj().T


def exact_unitary(config: ReservoirConfig) -> np.ndarray:
    config.validate()
    diagonal_part, transverse_part = hamiltonian_parts(config)
    return _hermitian_exponential(
        diagonal_part + transverse_part,
        config.evolution_time,
    )


def trotter_unitary(config: ReservoirConfig) -> np.ndarray:
    config.validate()
    if config.method != "trotter":
        raise ValueError("trotter_unitary requires method='trotter'")
    diagonal_part, transverse_part = hamiltonian_parts(config)
    step_time = config.evolution_time / config.trotter_steps
    unitary_b = _hermitian_exponential(transverse_part, step_time)

    if config.trotter_order == 1:
        unitary_a = _hermitian_exponential(diagonal_part, step_time)
        step_unitary = unitary_b @ unitary_a
    else:
        unitary_a_half = _hermitian_exponential(diagonal_part, 0.5 * step_time)
        step_unitary = unitary_a_half @ unitary_b @ unitary_a_half
    return np.linalg.matrix_power(step_unitary, config.trotter_steps)


def process_infidelity(reference: np.ndarray, approximation: np.ndarray) -> float:
    """Global-phase-invariant process infidelity between two unitaries."""

    reference = np.asarray(reference, dtype=np.complex128)
    approximation = np.asarray(approximation, dtype=np.complex128)
    if reference.shape != approximation.shape or reference.ndim != 2:
        raise ValueError("Unitary matrices must have identical square shapes")
    dimension = reference.shape[0]
    overlap = np.trace(reference.conj().T @ approximation) / dimension
    return float(max(1.0 - np.abs(overlap) ** 2, 0.0))


def circuit_resources(config: ReservoirConfig) -> dict[str, int | None]:
    """Logical product-formula resources per reservoir time step."""

    config.validate()
    if config.method == "exact":
        return {
            "a_blocks": None,
            "b_blocks": None,
            "single_qubit_rotations": None,
            "two_qubit_gates": None,
            "logical_depth_proxy": None,
        }
    edge_count = len(interaction_edges(config.n_qubits, config.topology))
    a_blocks = config.trotter_steps if config.trotter_order == 1 else config.trotter_steps + 1
    b_blocks = config.trotter_steps
    return {
        "a_blocks": a_blocks,
        "b_blocks": b_blocks,
        "single_qubit_rotations": (a_blocks + b_blocks) * config.n_qubits,
        "two_qubit_gates": 2 * edge_count * a_blocks,
        "logical_depth_proxy": a_blocks * (2 * edge_count + 1) + b_blocks,
    }


def _input_density(value: float) -> np.ndarray:
    clipped = float(np.clip(value, 0.0, 1.0))
    state = np.asarray([np.sqrt(1.0 - clipped), np.sqrt(clipped)], dtype=np.complex128)
    return np.outer(state, state.conj())


def _trace_out_first_qubit(density: np.ndarray) -> np.ndarray:
    dimension = density.shape[0]
    if density.shape != (dimension, dimension) or dimension % 2:
        raise ValueError("Density matrix dimension must be even and square")
    environment_dimension = dimension // 2
    reshaped = density.reshape(2, environment_dimension, 2, environment_dimension)
    return np.trace(reshaped, axis1=0, axis2=2)


def inject_input(density: np.ndarray, value: float) -> np.ndarray:
    """Reset the first qubit to |psi(value)> while preserving the environment."""

    environment = _trace_out_first_qubit(np.asarray(density, dtype=np.complex128))
    return np.kron(_input_density(value), environment)


def _initial_density(n_qubits: int) -> np.ndarray:
    zero = np.zeros(2**n_qubits, dtype=np.complex128)
    zero[0] = 1.0
    return np.outer(zero, zero.conj())


def _observable_set(config: ReservoirConfig) -> tuple[tuple[str, ...], tuple[np.ndarray, ...]]:
    names: list[str] = []
    observables: list[np.ndarray] = []
    z_operators: list[np.ndarray] = []
    for qubit in range(config.n_qubits):
        x_operator = operator_on_qubit(PAULI_X, qubit, config.n_qubits)
        z_operator = operator_on_qubit(PAULI_Z, qubit, config.n_qubits)
        names.extend((f"X{qubit}", f"Z{qubit}"))
        observables.extend((x_operator, z_operator))
        z_operators.append(z_operator)
    for left, right in interaction_edges(config.n_qubits, config.topology):
        names.append(f"Z{left}Z{right}")
        observables.append(z_operators[left] @ z_operators[right])
    return tuple(names), tuple(observables)


class QuantumReservoir:
    """A sequential QRC with one-qubit input reset and fixed Ising dynamics."""

    def __init__(self, config: ReservoirConfig):
        config.validate()
        self.config = config
        started = perf_counter()
        self.unitary = exact_unitary(config) if config.method == "exact" else trotter_unitary(config)
        self.unitary_build_seconds = perf_counter() - started
        self.observable_names, self.observables = _observable_set(config)

    @property
    def n_features(self) -> int:
        return len(self.observables)

    def transform(self, inputs: np.ndarray) -> tuple[np.ndarray, float]:
        values = np.asarray(inputs, dtype=float).reshape(-1)
        density = _initial_density(self.config.n_qubits)
        features = np.empty((len(values), self.n_features), dtype=float)
        adjoint = self.unitary.conj().T
        started = perf_counter()

        for index, value in enumerate(values):
            density = inject_input(density, value)
            density = self.unitary @ density @ adjoint
            density = 0.5 * (density + density.conj().T)
            density /= np.trace(density).real
            features[index] = [np.trace(density @ observable).real for observable in self.observables]
        return features, perf_counter() - started

    def density_trace_check(self, inputs: np.ndarray) -> float:
        density = _initial_density(self.config.n_qubits)
        adjoint = self.unitary.conj().T
        maximum_error = 0.0
        for value in np.asarray(inputs, dtype=float).reshape(-1):
            density = inject_input(density, value)
            density = self.unitary @ density @ adjoint
            maximum_error = max(maximum_error, abs(float(np.trace(density).real) - 1.0))
        return maximum_error
