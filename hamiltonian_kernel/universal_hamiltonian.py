from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass
from functools import lru_cache

import numpy as np


PAULI_SYMBOLS = ("X", "Y", "Z")


@dataclass(frozen=True)
class PauliTerm:
    """One real, data-dependent Pauli term in a Hermitian Hamiltonian."""

    label: str
    bias: float
    data_weights: tuple[float, ...]

    @property
    def locality(self) -> int:
        return sum(symbol != "I" for symbol in self.label)

    def validate(self, n_qubits: int, input_dim: int) -> None:
        if len(self.label) != n_qubits:
            raise ValueError("Pauli label length must equal n_qubits")
        if set(self.label) - {"I", "X", "Y", "Z"}:
            raise ValueError(f"Unsupported Pauli label: {self.label}")
        if self.locality < 1:
            raise ValueError("Identity-only terms are excluded from the feature map")
        if len(self.data_weights) != input_dim:
            raise ValueError("data_weights length must equal input_dim")
        if not np.isfinite(self.bias) or not np.all(np.isfinite(self.data_weights)):
            raise ValueError("Pauli coefficients must be finite")

    def coefficient(self, x: np.ndarray) -> float:
        values = np.asarray(x, dtype=float)
        if values.shape != (len(self.data_weights),):
            raise ValueError(
                f"Expected x with shape {(len(self.data_weights),)}, got {values.shape}"
            )
        return float(self.bias + values @ np.asarray(self.data_weights, dtype=float))


@dataclass(frozen=True)
class UniversalHamiltonianConfig:
    """Configuration of a sparse k-local universal Pauli Hamiltonian family."""

    n_qubits: int
    input_dim: int
    max_locality: int | None = None
    evolution_time: float = 1.0
    coefficient_seed: int = 20260827
    static_scale: float = 0.35
    data_scale: float = 1.0
    max_terms: int | None = None

    def validate(self) -> None:
        if self.n_qubits < 1 or self.input_dim < 1:
            raise ValueError("n_qubits and input_dim must be positive")
        if self.max_locality is not None and not 1 <= self.max_locality <= self.n_qubits:
            raise ValueError("max_locality must be None or in [1, n_qubits]")
        if self.evolution_time <= 0.0:
            raise ValueError("evolution_time must be positive")
        if self.coefficient_seed < 0:
            raise ValueError("coefficient_seed cannot be negative")
        if self.static_scale < 0.0 or self.data_scale <= 0.0:
            raise ValueError("Coefficient scales are invalid")
        if self.max_terms is not None and self.max_terms < 1:
            raise ValueError("max_terms must be positive when provided")


def _stable_rng(seed: int, label: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}:{label}".encode("ascii")).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def pauli_labels(n_qubits: int, max_locality: int) -> tuple[str, ...]:
    if n_qubits < 1 or not 1 <= max_locality <= n_qubits:
        raise ValueError("Invalid Pauli-label dimensions")
    labels: list[str] = []
    for locality in range(1, max_locality + 1):
        for support in itertools.combinations(range(n_qubits), locality):
            for axes in itertools.product(PAULI_SYMBOLS, repeat=locality):
                symbols = ["I"] * n_qubits
                for qubit, axis in zip(support, axes, strict=True):
                    symbols[qubit] = axis
                labels.append("".join(symbols))
    return tuple(labels)


def generate_universal_terms(config: UniversalHamiltonianConfig) -> tuple[PauliTerm, ...]:
    """Generate a reproducible real Pauli expansion.

    With max_locality=n_qubits and no term cap this spans every non-identity
    Hermitian Pauli direction. Fixed locality or max_terms gives a controlled,
    explicitly reported sparse approximation of that universal family.
    """

    config.validate()
    locality = config.n_qubits if config.max_locality is None else config.max_locality
    labels = list(pauli_labels(config.n_qubits, locality))
    if config.max_terms is not None and len(labels) > config.max_terms:
        labels.sort(
            key=lambda label: hashlib.sha256(
                f"{config.coefficient_seed}:rank:{label}".encode("ascii")
            ).digest()
        )
        labels = labels[: config.max_terms]
        labels.sort(key=lambda value: (sum(c != "I" for c in value), value))

    term_normalization = np.sqrt(len(labels))
    data_normalization = np.sqrt(len(labels) * config.input_dim)
    terms: list[PauliTerm] = []
    for label in labels:
        rng = _stable_rng(config.coefficient_seed, label)
        term = PauliTerm(
            label=label,
            bias=float(config.static_scale * rng.normal() / term_normalization),
            data_weights=tuple(
                float(value)
                for value in (
                    config.data_scale
                    * rng.normal(size=config.input_dim)
                    / data_normalization
                )
            ),
        )
        term.validate(config.n_qubits, config.input_dim)
        terms.append(term)
    return tuple(terms)


@lru_cache(maxsize=None)
def pauli_matrix(label: str) -> np.ndarray:
    matrices = {
        "I": np.eye(2, dtype=np.complex128),
        "X": np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128),
        "Y": np.asarray([[0.0, -1.0j], [1.0j, 0.0]], dtype=np.complex128),
        "Z": np.asarray([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128),
    }
    if not label or set(label) - set(matrices):
        raise ValueError(f"Unsupported Pauli label: {label}")
    result = np.asarray([[1.0]], dtype=np.complex128)
    # Qubit zero is the least-significant bit in state-vector indexing.
    for symbol in reversed(label):
        result = np.kron(result, matrices[symbol])
    return result


def hamiltonian_matrix(terms: tuple[PauliTerm, ...], x: np.ndarray) -> np.ndarray:
    if not terms:
        raise ValueError("At least one Pauli term is required")
    dimension = 2 ** len(terms[0].label)
    result = np.zeros((dimension, dimension), dtype=np.complex128)
    for term in terms:
        result += term.coefficient(x) * pauli_matrix(term.label)
    return result


def plus_state(n_qubits: int) -> np.ndarray:
    if n_qubits < 1:
        raise ValueError("n_qubits must be positive")
    return np.ones(2**n_qubits, dtype=np.complex128) / np.sqrt(2**n_qubits)


def evolve_exact_pauli(
    terms: tuple[PauliTerm, ...],
    x: np.ndarray,
    evolution_time: float,
) -> np.ndarray:
    if evolution_time <= 0.0:
        raise ValueError("evolution_time must be positive")
    hamiltonian = hamiltonian_matrix(terms, x)
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    initial = plus_state(len(terms[0].label))
    coefficients = eigenvectors.conj().T @ initial
    return eigenvectors @ (np.exp(-1.0j * evolution_time * eigenvalues) * coefficients)


def evolve_exact_pauli_batch(
    terms: tuple[PauliTerm, ...],
    values: np.ndarray,
    evolution_time: float,
) -> np.ndarray:
    """Evaluate exact Hamiltonian evolution for a batch of classical inputs."""

    inputs = np.asarray(values, dtype=float)
    if inputs.ndim != 2:
        raise ValueError("values must have shape (samples, input_dim)")
    return np.asarray(
        [evolve_exact_pauli(terms, row, evolution_time) for row in inputs],
        dtype=np.complex128,
    )


def _apply_pauli(state: np.ndarray, label: str) -> np.ndarray:
    values = np.asarray(state, dtype=np.complex128)
    dimension = 2 ** len(label)
    if values.shape != (dimension,):
        raise ValueError(f"Expected state with shape {(dimension,)}, got {values.shape}")
    basis = np.arange(dimension, dtype=np.uint64)
    target = basis.copy()
    phase = np.ones(dimension, dtype=np.complex128)
    for qubit, symbol in enumerate(label):
        bits = (basis >> np.uint64(qubit)) & np.uint64(1)
        if symbol == "X":
            target ^= np.uint64(1 << qubit)
        elif symbol == "Y":
            target ^= np.uint64(1 << qubit)
            phase *= np.where(bits == 0, 1.0j, -1.0j)
        elif symbol == "Z":
            phase *= np.where(bits == 0, 1.0, -1.0)
        elif symbol != "I":
            raise ValueError(f"Unsupported Pauli symbol: {symbol}")
    result = np.empty_like(values)
    result[target.astype(int)] = phase * values
    return result


@lru_cache(maxsize=None)
def _pauli_action(label: str) -> tuple[np.ndarray, np.ndarray]:
    """Return the permutation and phase implementing one Pauli string."""

    dimension = 2 ** len(label)
    basis = np.arange(dimension, dtype=np.uint64)
    target = basis.copy()
    phase = np.ones(dimension, dtype=np.complex128)
    for qubit, symbol in enumerate(label):
        bits = (basis >> np.uint64(qubit)) & np.uint64(1)
        if symbol == "X":
            target ^= np.uint64(1 << qubit)
        elif symbol == "Y":
            target ^= np.uint64(1 << qubit)
            phase *= np.where(bits == 0, 1.0j, -1.0j)
        elif symbol == "Z":
            phase *= np.where(bits == 0, 1.0, -1.0)
        elif symbol != "I":
            raise ValueError(f"Unsupported Pauli symbol: {symbol}")
    return target.astype(int), phase


def _apply_pauli_batch(states: np.ndarray, label: str) -> np.ndarray:
    values = np.asarray(states, dtype=np.complex128)
    dimension = 2 ** len(label)
    if values.ndim != 2 or values.shape[1] != dimension:
        raise ValueError(
            f"Expected states with shape (samples, {dimension}), got {values.shape}"
        )
    target, phase = _pauli_action(label)
    result = np.empty_like(values)
    result[:, target] = values * phase[None, :]
    return result


def apply_pauli_exponential(
    state: np.ndarray,
    label: str,
    angle: float,
) -> np.ndarray:
    return np.cos(angle) * state - 1.0j * np.sin(angle) * _apply_pauli(state, label)


def slice_schedule(evolution_time: float, nominal_step: float) -> tuple[float, ...]:
    """Return positive slice durations that sum exactly to evolution_time."""

    if evolution_time <= 0.0 or nominal_step <= 0.0:
        raise ValueError("Evolution time and nominal step must be positive")
    if nominal_step >= evolution_time:
        return (float(evolution_time),)
    full_steps = int(np.floor(evolution_time / nominal_step + 1e-12))
    durations = [float(nominal_step)] * full_steps
    remainder = float(evolution_time - full_steps * nominal_step)
    if remainder > 1e-12:
        durations.append(remainder)
    difference = float(evolution_time - sum(durations))
    durations[-1] += difference
    if any(value <= 0.0 for value in durations):
        raise RuntimeError("Slice construction produced a non-positive duration")
    return tuple(durations)


def _second_order_sequence(term_count: int, duration: float) -> list[tuple[int, float]]:
    half = 0.5 * duration
    return (
        [(index, half) for index in range(term_count)]
        + [(index, half) for index in reversed(range(term_count))]
    )


def _slice_sequence(
    order: int,
    term_count: int,
    duration: float,
) -> list[tuple[int, float]]:
    if order == 1:
        return [(index, duration) for index in range(term_count)]
    if order == 2:
        return _second_order_sequence(term_count, duration)
    if order == 4:
        coefficient = 1.0 / (4.0 - 4.0 ** (1.0 / 3.0))
        sequence: list[tuple[int, float]] = []
        for scale in (
            coefficient,
            coefficient,
            1.0 - 4.0 * coefficient,
            coefficient,
            coefficient,
        ):
            sequence.extend(_second_order_sequence(term_count, scale * duration))
        return sequence
    raise ValueError("Supported product-formula orders are 1, 2, and 4")


def product_formula_sequence(
    term_count: int,
    order: int,
    evolution_time: float,
    nominal_step: float,
) -> tuple[tuple[int, float], ...]:
    if term_count < 1:
        raise ValueError("term_count must be positive")
    raw: list[tuple[int, float]] = []
    for duration in slice_schedule(evolution_time, nominal_step):
        raw.extend(_slice_sequence(order, term_count, duration))

    compressed: list[tuple[int, float]] = []
    for index, duration in raw:
        if compressed and compressed[-1][0] == index:
            previous_index, previous_duration = compressed[-1]
            combined = previous_duration + duration
            if abs(combined) < 1e-14:
                compressed.pop()
            else:
                compressed[-1] = (previous_index, combined)
        elif abs(duration) >= 1e-14:
            compressed.append((index, duration))
    return tuple(compressed)


def evolve_product_formula(
    terms: tuple[PauliTerm, ...],
    x: np.ndarray,
    evolution_time: float,
    order: int,
    nominal_step: float,
) -> np.ndarray:
    if not terms:
        raise ValueError("At least one Pauli term is required")
    coefficients = np.asarray([term.coefficient(x) for term in terms], dtype=float)
    state = plus_state(len(terms[0].label))
    for index, duration in product_formula_sequence(
        len(terms), order, evolution_time, nominal_step
    ):
        state = apply_pauli_exponential(
            state,
            terms[index].label,
            coefficients[index] * duration,
        )
    return state


def evolve_product_formula_batch(
    terms: tuple[PauliTerm, ...],
    values: np.ndarray,
    evolution_time: float,
    order: int,
    nominal_step: float,
) -> np.ndarray:
    """Vectorized product-formula evolution for many inputs.

    The product-formula sequence is shared by all samples. Only its rotation
    angles differ, so applying each Pauli permutation to the complete state
    batch removes the per-sample Python loop used by the scalar implementation.
    """

    if not terms:
        raise ValueError("At least one Pauli term is required")
    inputs = np.asarray(values, dtype=float)
    if inputs.ndim != 2 or inputs.shape[1] != len(terms[0].data_weights):
        raise ValueError("values must have shape (samples, input_dim)")
    biases = np.asarray([term.bias for term in terms], dtype=float)
    weights = np.asarray([term.data_weights for term in terms], dtype=float)
    coefficients = biases[None, :] + inputs @ weights.T
    initial = plus_state(len(terms[0].label))
    states = np.repeat(initial[None, :], len(inputs), axis=0)
    for index, duration in product_formula_sequence(
        len(terms), order, evolution_time, nominal_step
    ):
        angles = coefficients[:, index] * duration
        transformed = _apply_pauli_batch(states, terms[index].label)
        states = np.cos(angles)[:, None] * states - 1.0j * np.sin(angles)[:, None] * transformed
    return states


@dataclass(frozen=True)
class ProductFormulaResources:
    order: int
    nominal_step: float
    slice_count: int
    pauli_exponentials: int
    single_qubit_rotations: int
    two_qubit_gates: int
    serial_depth_proxy: int


def product_formula_resources(
    terms: tuple[PauliTerm, ...],
    evolution_time: float,
    order: int,
    nominal_step: float,
) -> ProductFormulaResources:
    sequence = product_formula_sequence(
        len(terms), order, evolution_time, nominal_step
    )
    single_qubit = 0
    two_qubit = 0
    depth = 0
    for index, _ in sequence:
        label = terms[index].label
        support = sum(symbol != "I" for symbol in label)
        non_z = sum(symbol in {"X", "Y"} for symbol in label)
        entanglers = 2 * max(support - 1, 0)
        basis_changes = 2 * non_z
        single_qubit += basis_changes + 1
        two_qubit += entanglers
        depth += basis_changes + entanglers + 1
    return ProductFormulaResources(
        order=order,
        nominal_step=float(nominal_step),
        slice_count=len(slice_schedule(evolution_time, nominal_step)),
        pauli_exponentials=len(sequence),
        single_qubit_rotations=single_qubit,
        two_qubit_gates=two_qubit,
        serial_depth_proxy=depth,
    )
