from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "datasets" / "qml_benchmarks"
OUT = ROOT / "analysis_output"
N_QUBITS = 4
DIM = 1 << N_QUBITS
EPS = 1e-12


@dataclass(frozen=True)
class Dataset:
    name: str
    x: np.ndarray
    y: np.ndarray
    class_names: tuple[str, ...]


@dataclass(frozen=True)
class PreparedDataset:
    name: str
    class_names: tuple[str, ...]
    x_train: np.ndarray
    x_val: np.ndarray
    x_test: np.ndarray
    y_train: np.ndarray
    y_val: np.ndarray
    y_test: np.ndarray
    explained_variance_4: float
    explained_variance_16: float


@dataclass(frozen=True)
class AnsatzSpec:
    key: str
    label: str
    parameters: int
    one_qubit_gates: int
    two_qubit_gates: int
    depth: int
    adaptation: str
    circuit: Callable[[np.ndarray, np.ndarray], np.ndarray]


@dataclass(frozen=True)
class ProviderProfile:
    key: str
    label: str
    simulator: str
    topology: str
    native_entangler: str
    one_qubit_fidelity: float
    two_qubit_fidelity: float
    readout_error: float
    one_qubit_multiplier: float
    two_qubit_multiplier: float


def load_wine() -> Dataset:
    rows: list[list[float]] = []
    labels: list[int] = []
    path = DATA / "wine" / "wine.data"
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.strip().split(",")
            if len(parts) != 14:
                continue
            labels.append(int(parts[0]) - 1)
            rows.append([float(value) for value in parts[1:]])
    return Dataset(
        "wine",
        np.asarray(rows, dtype=float),
        np.asarray(labels, dtype=int),
        ("class 1", "class 2", "class 3"),
    )


def load_breast_cancer() -> Dataset:
    rows: list[list[float]] = []
    labels: list[int] = []
    path = DATA / "breast_cancer_wisconsin_diagnostic" / "wdbc.data"
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.strip().split(",")
            if len(parts) < 32:
                continue
            labels.append(1 if parts[1] == "M" else 0)
            rows.append([float(value) for value in parts[2:]])
    return Dataset(
        "breast_cancer",
        np.asarray(rows, dtype=float),
        np.asarray(labels, dtype=int),
        ("benign", "malignant"),
    )


def load_optdigits() -> Dataset:
    rows: list[list[float]] = []
    labels: list[int] = []
    paths = [
        DATA / "optdigits" / "optdigits.tra",
        DATA / "optdigits" / "optdigits.tes",
    ]
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.strip().split(",")
                if len(parts) != 65:
                    continue
                labels.append(int(parts[-1]))
                rows.append([float(value) for value in parts[:-1]])
    return Dataset(
        "optdigits",
        np.asarray(rows, dtype=float),
        np.asarray(labels, dtype=int),
        tuple(f"digit {digit}" for digit in range(10)),
    )


def load_mnist(max_per_class: int, seed: int) -> Dataset:
    path = DATA / "mnist_784" / "mnist_784.arff"
    reservoirs: list[list[list[float]]] = [[] for _ in range(10)]
    counts = np.zeros(10, dtype=int)
    rng = np.random.default_rng(seed)
    in_data = False
    reservoir_size = max(max_per_class * 2, max_per_class + 8)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not in_data:
                if stripped.lower() == "@data":
                    in_data = True
                continue
            if not stripped or stripped.startswith("%"):
                continue
            values, label_text = stripped.rsplit(",", 1)
            label = int(float(label_text.strip("'\"")))
            counts[label] += 1
            bucket = reservoirs[label]
            position: int | None = None
            if len(bucket) < reservoir_size:
                position = len(bucket)
            else:
                candidate = int(rng.integers(0, counts[label]))
                if candidate < reservoir_size:
                    position = candidate
            if position is not None:
                row = [float(value) for value in values.split(",")]
                if position == len(bucket):
                    bucket.append(row)
                else:
                    bucket[position] = row
    rows: list[list[float]] = []
    labels: list[int] = []
    for label, bucket in enumerate(reservoirs):
        order = rng.permutation(len(bucket))[:max_per_class]
        rows.extend(bucket[index] for index in order)
        labels.extend([label] * len(order))
    return Dataset(
        "mnist",
        np.asarray(rows, dtype=float),
        np.asarray(labels, dtype=int),
        tuple(f"digit {digit}" for digit in range(10)),
    )


def balanced_subsample(dataset: Dataset, per_class: int, seed: int) -> Dataset:
    rng = np.random.default_rng(seed)
    indices: list[int] = []
    for label in range(len(dataset.class_names)):
        candidates = np.flatnonzero(dataset.y == label)
        selected = rng.permutation(candidates)[: min(per_class, len(candidates))]
        indices.extend(int(value) for value in selected)
    selected_indices = rng.permutation(indices)
    return Dataset(
        dataset.name,
        dataset.x[selected_indices],
        dataset.y[selected_indices],
        dataset.class_names,
    )


def stratified_split(y: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train: list[int] = []
    val: list[int] = []
    test: list[int] = []
    for label in np.unique(y):
        indices = rng.permutation(np.flatnonzero(y == label))
        n_train = max(1, int(round(0.60 * len(indices))))
        n_val = max(1, int(round(0.20 * len(indices))))
        if n_train + n_val >= len(indices):
            n_train = max(1, len(indices) - 2)
            n_val = 1
        train.extend(int(value) for value in indices[:n_train])
        val.extend(int(value) for value in indices[n_train : n_train + n_val])
        test.extend(int(value) for value in indices[n_train + n_val :])
    return rng.permutation(train), rng.permutation(val), rng.permutation(test)


def fit_pca(x_train: np.ndarray, components: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale[scale < EPS] = 1.0
    standardized = (x_train - mean) / scale
    _, singular_values, vectors = np.linalg.svd(standardized, full_matrices=False)
    available = min(components, vectors.shape[0])
    projection = vectors[:available].T
    if available < components:
        projection = np.pad(projection, ((0, 0), (0, components - available)))
    total = float(np.sum(singular_values**2))
    explained = float(np.sum(singular_values[:available] ** 2) / max(total, EPS))
    return mean, scale, projection, explained


def project_and_scale(
    x_train: np.ndarray,
    x_val: np.ndarray,
    x_test: np.ndarray,
    components: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    mean, scale, projection, explained = fit_pca(x_train, components)

    def project(values: np.ndarray) -> np.ndarray:
        return ((values - mean) / scale) @ projection

    z_train = project(x_train)
    z_val = project(x_val)
    z_test = project(x_test)
    low = z_train.min(axis=0)
    width = z_train.max(axis=0) - low
    width[width < EPS] = 1.0

    def angle_scale(values: np.ndarray) -> np.ndarray:
        unit = np.clip((values - low) / width, 0.0, 1.0)
        return np.pi * (2.0 * unit - 1.0)

    return angle_scale(z_train), angle_scale(z_val), angle_scale(z_test), explained


def prepare_dataset(dataset: Dataset, seed: int) -> PreparedDataset:
    train_idx, val_idx, test_idx = stratified_split(dataset.y, seed)
    x_train_raw = dataset.x[train_idx]
    x_val_raw = dataset.x[val_idx]
    x_test_raw = dataset.x[test_idx]
    train4, val4, test4, explained4 = project_and_scale(
        x_train_raw, x_val_raw, x_test_raw, 4
    )
    train16, val16, test16, explained16 = project_and_scale(
        x_train_raw, x_val_raw, x_test_raw, 16
    )
    return PreparedDataset(
        dataset.name,
        dataset.class_names,
        np.concatenate([train4, train16], axis=1),
        np.concatenate([val4, val16], axis=1),
        np.concatenate([test4, test16], axis=1),
        dataset.y[train_idx],
        dataset.y[val_idx],
        dataset.y[test_idx],
        explained4,
        explained16,
    )


PAIR_INDICES: dict[int, tuple[np.ndarray, np.ndarray]] = {}
for qubit in range(N_QUBITS):
    zero = np.array([index for index in range(DIM) if not (index >> qubit) & 1])
    PAIR_INDICES[qubit] = zero, zero | (1 << qubit)

Z_BASIS = np.empty((DIM, N_QUBITS), dtype=float)
for basis in range(DIM):
    for qubit in range(N_QUBITS):
        Z_BASIS[basis, qubit] = 1.0 - 2.0 * ((basis >> qubit) & 1)


def zero_state(batch: int) -> np.ndarray:
    state = np.zeros((batch, DIM), dtype=complex)
    state[:, 0] = 1.0
    return state


def basis_state(batch: int, basis: int) -> np.ndarray:
    state = np.zeros((batch, DIM), dtype=complex)
    state[:, basis] = 1.0
    return state


def as_batch_angle(theta: float | np.ndarray, batch: int) -> np.ndarray:
    values = np.asarray(theta, dtype=float)
    if values.ndim == 0:
        return np.full(batch, float(values))
    return values


def apply_ry(state: np.ndarray, theta: float | np.ndarray, qubit: int) -> None:
    zero, one = PAIR_INDICES[qubit]
    angles = as_batch_angle(theta, len(state))
    cosine = np.cos(angles / 2.0)[:, None]
    sine = np.sin(angles / 2.0)[:, None]
    left = state[:, zero].copy()
    right = state[:, one].copy()
    state[:, zero] = cosine * left - sine * right
    state[:, one] = sine * left + cosine * right


def apply_rx(state: np.ndarray, theta: float | np.ndarray, qubit: int) -> None:
    zero, one = PAIR_INDICES[qubit]
    angles = as_batch_angle(theta, len(state))
    cosine = np.cos(angles / 2.0)[:, None]
    sine = (-1j * np.sin(angles / 2.0))[:, None]
    left = state[:, zero].copy()
    right = state[:, one].copy()
    state[:, zero] = cosine * left + sine * right
    state[:, one] = sine * left + cosine * right


def apply_rz(state: np.ndarray, theta: float | np.ndarray, qubit: int) -> None:
    zero, one = PAIR_INDICES[qubit]
    angles = as_batch_angle(theta, len(state))
    state[:, zero] *= np.exp(-0.5j * angles)[:, None]
    state[:, one] *= np.exp(0.5j * angles)[:, None]


def apply_h(state: np.ndarray, qubit: int) -> None:
    zero, one = PAIR_INDICES[qubit]
    left = state[:, zero].copy()
    right = state[:, one].copy()
    factor = 1.0 / math.sqrt(2.0)
    state[:, zero] = factor * (left + right)
    state[:, one] = factor * (left - right)


def apply_rot(
    state: np.ndarray,
    phi: float | np.ndarray,
    theta: float | np.ndarray,
    omega: float | np.ndarray,
    qubit: int,
) -> None:
    apply_rz(state, phi, qubit)
    apply_ry(state, theta, qubit)
    apply_rz(state, omega, qubit)


def apply_cnot(state: np.ndarray, control: int, target: int) -> None:
    source = np.array(
        [
            index
            for index in range(DIM)
            if ((index >> control) & 1) and not ((index >> target) & 1)
        ]
    )
    destination = source | (1 << target)
    saved = state[:, source].copy()
    state[:, source] = state[:, destination]
    state[:, destination] = saved


def apply_cz(state: np.ndarray, left: int, right: int) -> None:
    selected = np.array(
        [
            index
            for index in range(DIM)
            if ((index >> left) & 1) and ((index >> right) & 1)
        ]
    )
    state[:, selected] *= -1.0


def apply_rzz(
    state: np.ndarray, theta: float | np.ndarray, left: int, right: int
) -> None:
    angles = as_batch_angle(theta, len(state))
    parity = Z_BASIS[:, left] * Z_BASIS[:, right]
    state *= np.exp(-0.5j * angles[:, None] * parity[None, :])


def apply_single_excitation(
    state: np.ndarray, theta: float | np.ndarray, occupied: int, virtual: int
) -> None:
    source = np.array(
        [
            index
            for index in range(DIM)
            if ((index >> occupied) & 1) and not ((index >> virtual) & 1)
        ]
    )
    destination = source ^ (1 << occupied) ^ (1 << virtual)
    angles = as_batch_angle(theta, len(state))
    cosine = np.cos(angles / 2.0)[:, None]
    sine = np.sin(angles / 2.0)[:, None]
    left = state[:, source].copy()
    right = state[:, destination].copy()
    state[:, source] = cosine * left - sine * right
    state[:, destination] = sine * left + cosine * right


def apply_double_excitation(state: np.ndarray, theta: float | np.ndarray) -> None:
    angles = as_batch_angle(theta, len(state))
    cosine = np.cos(angles / 2.0)
    sine = np.sin(angles / 2.0)
    occupied = state[:, 3].copy()
    virtual = state[:, 12].copy()
    state[:, 3] = cosine * occupied - sine * virtual
    state[:, 12] = sine * occupied + cosine * virtual


def angle_embedding(x: np.ndarray) -> np.ndarray:
    state = zero_state(len(x))
    for qubit in range(N_QUBITS):
        apply_ry(state, x[:, qubit], qubit)
    return state


def ring_edges() -> list[tuple[int, int]]:
    return [(0, 1), (1, 2), (2, 3), (3, 0)]


def circuit_general_vqa(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for _ in range(2):
        for qubit in range(N_QUBITS):
            apply_ry(state, theta[cursor], qubit)
            apply_rz(state, theta[cursor + 1], qubit)
            cursor += 2
        for left, right in ring_edges():
            apply_cz(state, left, right)
    return state


def circuit_hardware_efficient(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for _ in range(2):
        for qubit in range(N_QUBITS):
            apply_ry(state, theta[cursor], qubit)
            cursor += 1
        for control, target in ring_edges():
            apply_cnot(state, control, target)
    return state


def circuit_efficient_su2(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for block in range(2):
        for qubit in range(N_QUBITS):
            apply_ry(state, theta[cursor], qubit)
            apply_rz(state, theta[cursor + 1], qubit)
            cursor += 2
        if block == 0:
            for control, target in [(0, 1), (1, 2), (2, 3)]:
                apply_cnot(state, control, target)
    return state


def circuit_uccsd_hf(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = basis_state(len(x), 3)
    singles = [(0, 2), (0, 3), (1, 2), (1, 3)]
    for index, (occupied, virtual) in enumerate(singles):
        data_angle = theta[index] + 0.35 * x[:, index]
        apply_single_excitation(state, data_angle, occupied, virtual)
    apply_double_excitation(state, theta[4] + 0.10 * np.sum(x[:, :4], axis=1))
    return state


def circuit_qaoa(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = zero_state(len(x))
    for qubit in range(N_QUBITS):
        apply_h(state, qubit)
    for layer in range(2):
        gamma = theta[2 * layer]
        beta = theta[2 * layer + 1]
        for qubit in range(N_QUBITS):
            apply_rz(state, gamma * x[:, qubit], qubit)
        for left, right in ring_edges():
            coupling = 0.25 * gamma * x[:, left] * x[:, right]
            apply_rzz(state, coupling, left, right)
        for qubit in range(N_QUBITS):
            apply_rx(state, 2.0 * beta, qubit)
    return state


def zz_feature_map(x: np.ndarray) -> np.ndarray:
    state = zero_state(len(x))
    for qubit in range(N_QUBITS):
        apply_h(state, qubit)
        apply_rz(state, x[:, qubit], qubit)
    for left, right in ring_edges():
        apply_rzz(state, 0.25 * x[:, left] * x[:, right], left, right)
    return state


def circuit_qnn_vqc(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = zz_feature_map(x)
    cursor = 0
    for block in range(2):
        for qubit in range(N_QUBITS):
            apply_ry(state, theta[cursor], qubit)
            cursor += 1
        if block == 0:
            for control, target in ring_edges():
                apply_cnot(state, control, target)
    return state


def circuit_two_local(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for repetition in range(3):
        for qubit in range(N_QUBITS):
            apply_ry(state, theta[cursor], qubit)
            cursor += 1
        if repetition < 2:
            for control, target in [(0, 1), (1, 2), (2, 3)]:
                apply_cnot(state, control, target)
    return state


def circuit_tree_tensor(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for left, right in [(0, 1), (2, 3), (1, 3)]:
        apply_ry(state, theta[cursor], left)
        apply_ry(state, theta[cursor + 1], right)
        apply_cnot(state, left, right)
        apply_ry(state, theta[cursor + 2], right)
        cursor += 3
    return state


def circuit_strongly_entangling(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for layer in range(2):
        for qubit in range(N_QUBITS):
            apply_rot(
                state,
                theta[cursor],
                theta[cursor + 1],
                theta[cursor + 2],
                qubit,
            )
            cursor += 3
        distance = layer + 1
        for control in range(N_QUBITS):
            apply_cnot(state, control, (control + distance) % N_QUBITS)
    return state


def circuit_qgan_u3(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for qubit in range(N_QUBITS):
        apply_rot(
            state,
            theta[cursor],
            theta[cursor + 1],
            theta[cursor + 2],
            qubit,
        )
        cursor += 3
    return state


def circuit_qgan_two_local(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for _ in range(2):
        for qubit in range(N_QUBITS):
            apply_ry(state, theta[cursor], qubit)
            apply_rz(state, theta[cursor + 1], qubit)
            cursor += 2
        for left, right in ring_edges():
            apply_cz(state, left, right)
    return state


def circuit_qgan_rot_cz(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = angle_embedding(x)
    cursor = 0
    for _ in range(2):
        for qubit in range(N_QUBITS):
            apply_rot(
                state,
                theta[cursor],
                theta[cursor + 1],
                theta[cursor + 2],
                qubit,
            )
            cursor += 3
        for left, right in ring_edges():
            apply_cz(state, left, right)
    return state


APPROX_PROJECTION = np.asarray(
    [
        [1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1, 0],
        [0, 1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1, 0, 1, 0, -1],
        [1, 1, 0, 0, -1, -1, 0, 0, 1, 1, 0, 0, -1, -1, 0, 0],
        [0, 0, 1, 1, 0, 0, -1, -1, 0, 0, 1, 1, 0, 0, -1, -1],
    ],
    dtype=float,
) / 4.0


def circuit_approx_amplitude(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    compressed = np.tanh(x[:, 4:20] @ APPROX_PROJECTION.T)
    state = zero_state(len(x))
    for qubit in range(N_QUBITS):
        apply_ry(state, np.pi * compressed[:, qubit], qubit)
    cursor = 0
    for _ in range(2):
        for qubit in range(N_QUBITS):
            apply_ry(state, theta[cursor], qubit)
            apply_rz(state, theta[cursor + 1], qubit)
            cursor += 2
        for control, target in ring_edges():
            apply_cnot(state, control, target)
    return state


def circuit_data_reuploading(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    state = zero_state(len(x))
    cursor = 0
    for layer in range(2):
        for qubit in range(N_QUBITS):
            apply_ry(state, x[:, qubit], qubit)
            apply_rz(state, x[:, (qubit + layer + 1) % N_QUBITS], qubit)
            apply_ry(state, theta[cursor], qubit)
            apply_rz(state, theta[cursor + 1], qubit)
            cursor += 2
        for control, target in ring_edges():
            apply_cnot(state, control, target)
    return state


ANSATZE = {
    spec.key: spec
    for spec in [
        AnsatzSpec(
            "general_vqa_pqc",
            "General VQA/PQC W(theta)",
            16,
            20,
            8,
            8,
            "Angle embedding followed by a generic trainable W(theta).",
            circuit_general_vqa,
        ),
        AnsatzSpec(
            "hardware_ry_cnot_ring",
            "Hardware-efficient RY + CNOT ring",
            8,
            12,
            8,
            7,
            "Angle embedding added before the requested hardware-efficient ansatz.",
            circuit_hardware_efficient,
        ),
        AnsatzSpec(
            "efficient_su2",
            "EfficientSU2",
            16,
            20,
            3,
            5,
            "RY/RZ blocks and linear CNOT entanglement after angle embedding.",
            circuit_efficient_su2,
        ),
        AnsatzSpec(
            "uccsd_hf",
            "UCCSD + Hartree-Fock",
            5,
            16,
            20,
            18,
            "Classifier proxy: HF |1100>, data-modulated singles and one double excitation; no molecular Hamiltonian.",
            circuit_uccsd_hf,
        ),
        AnsatzSpec(
            "qaoa",
            "QAOA ansatz",
            4,
            20,
            8,
            10,
            "Classifier proxy: PCA features define the Ising cost phases; p=2 gamma/beta layers.",
            circuit_qaoa,
        ),
        AnsatzSpec(
            "qnn_vqc_feature_map",
            "QNN/VQC feature map + variational form",
            8,
            16,
            8,
            8,
            "ZZ feature map followed by a trainable RY/CNOT variational form.",
            circuit_qnn_vqc,
        ),
        AnsatzSpec(
            "two_local",
            "TwoLocal",
            12,
            16,
            6,
            7,
            "Angle embedding and two linear-entanglement repetitions plus final RY block.",
            circuit_two_local,
        ),
        AnsatzSpec(
            "tree_tensor",
            "Tree tensor",
            9,
            13,
            3,
            7,
            "Binary tree of trainable two-qubit blocks, reused unchanged for multiclass readout.",
            circuit_tree_tensor,
        ),
        AnsatzSpec(
            "strongly_entangling",
            "Strongly entangling layers",
            24,
            28,
            8,
            10,
            "Two Rot layers with CNOT ranges 1 and 2.",
            circuit_strongly_entangling,
        ),
        AnsatzSpec(
            "qgan_u3",
            "QGAN U3",
            12,
            16,
            0,
            2,
            "Generator block adapted as a discriminative feature circuit; no adversarial loss.",
            circuit_qgan_u3,
        ),
        AnsatzSpec(
            "qgan_two_local",
            "QGAN two-local variant",
            16,
            20,
            8,
            8,
            "Two-local generator/discriminator block used with classification cross-entropy.",
            circuit_qgan_two_local,
        ),
        AnsatzSpec(
            "qgan_rot_cz",
            "QGAN Rot + CZ",
            24,
            28,
            8,
            8,
            "Patch-generator Rot/CZ block adapted to classification; no adversarial loss.",
            circuit_qgan_rot_cz,
        ),
        AnsatzSpec(
            "approx_amplitude_encoding",
            "Approximate amplitude encoding",
            16,
            20,
            8,
            9,
            "Sixteen PCA components compressed into a shallow four-qubit preparation circuit.",
            circuit_approx_amplitude,
        ),
        AnsatzSpec(
            "data_reuploading",
            "Data re-uploading",
            16,
            32,
            8,
            10,
            "PCA angles are uploaded again in each of two variational layers.",
            circuit_data_reuploading,
        ),
    ]
}


PROVIDERS = {
    profile.key: profile
    for profile in [
        ProviderProfile(
            "ibm",
            "IBM superconducting profile",
            "local statevector + analytic noise + finite shots",
            "sparse heavy-hex proxy",
            "ECR/CX",
            0.9995,
            0.9940,
            0.015,
            1.10,
            1.25,
        ),
        ProviderProfile(
            "rigetti",
            "Rigetti superconducting profile",
            "local statevector + analytic noise + finite shots",
            "square-lattice proxy",
            "iSWAP",
            0.9990,
            0.9900,
            0.025,
            1.15,
            1.60,
        ),
        ProviderProfile(
            "ionq",
            "IonQ trapped-ion profile",
            "local statevector + analytic noise + finite shots",
            "all-to-all",
            "ZZ/MS",
            0.9998,
            0.9960,
            0.005,
            1.25,
            1.00,
        ),
        ProviderProfile(
            "xanadu",
            "Xanadu/PennyLane ideal profile",
            "local ideal statevector (default.qubit semantics)",
            "software all-to-all",
            "abstract qubit gates",
            1.0000,
            1.0000,
            0.000,
            1.00,
            1.00,
        ),
    ]
}


DEFAULT_HYPERPARAMETERS: dict[str, float | str] = {
    "candidate_id": "baseline",
    "quantum_learning_rate": 0.055,
    "head_learning_rate": 0.090,
    "spsa_perturbation": 0.120,
    "weight_decay": 1e-4,
    "initialization_scale": 0.200,
    "input_scale": 1.000,
}

HPO_CANDIDATES: list[dict[str, float | str]] = [
    dict(DEFAULT_HYPERPARAMETERS),
    {
        "candidate_id": "cautious",
        "quantum_learning_rate": 0.030,
        "head_learning_rate": 0.060,
        "spsa_perturbation": 0.080,
        "weight_decay": 5e-4,
        "initialization_scale": 0.100,
        "input_scale": 0.750,
    },
    {
        "candidate_id": "low_perturbation",
        "quantum_learning_rate": 0.045,
        "head_learning_rate": 0.100,
        "spsa_perturbation": 0.050,
        "weight_decay": 1e-4,
        "initialization_scale": 0.150,
        "input_scale": 1.000,
    },
    {
        "candidate_id": "aggressive",
        "quantum_learning_rate": 0.090,
        "head_learning_rate": 0.140,
        "spsa_perturbation": 0.100,
        "weight_decay": 1e-5,
        "initialization_scale": 0.200,
        "input_scale": 1.250,
    },
    {
        "candidate_id": "broad_perturbation",
        "quantum_learning_rate": 0.040,
        "head_learning_rate": 0.080,
        "spsa_perturbation": 0.200,
        "weight_decay": 1e-4,
        "initialization_scale": 0.250,
        "input_scale": 1.250,
    },
    {
        "candidate_id": "regularized",
        "quantum_learning_rate": 0.060,
        "head_learning_rate": 0.080,
        "spsa_perturbation": 0.100,
        "weight_decay": 3e-3,
        "initialization_scale": 0.120,
        "input_scale": 0.750,
    },
    {
        "candidate_id": "small_initialization",
        "quantum_learning_rate": 0.035,
        "head_learning_rate": 0.120,
        "spsa_perturbation": 0.060,
        "weight_decay": 1e-5,
        "initialization_scale": 0.050,
        "input_scale": 1.500,
    },
    {
        "candidate_id": "high_scale",
        "quantum_learning_rate": 0.075,
        "head_learning_rate": 0.060,
        "spsa_perturbation": 0.160,
        "weight_decay": 5e-4,
        "initialization_scale": 0.300,
        "input_scale": 1.500,
    },
]


def quantum_features(
    spec: AnsatzSpec,
    x: np.ndarray,
    theta: np.ndarray,
    input_scale: float = 1.0,
) -> np.ndarray:
    state = spec.circuit(input_scale * x, theta)
    norm_error = float(np.max(np.abs(np.sum(np.abs(state) ** 2, axis=1) - 1.0)))
    if norm_error > 1e-8:
        raise RuntimeError(f"State norm error for {spec.key}: {norm_error}")
    probabilities = np.abs(state) ** 2
    return probabilities @ Z_BASIS


def profile_attenuation(spec: AnsatzSpec, profile: ProviderProfile) -> float:
    one_count = spec.one_qubit_gates * profile.one_qubit_multiplier
    two_count = spec.two_qubit_gates * profile.two_qubit_multiplier
    gate_survival = (
        profile.one_qubit_fidelity**one_count
        * profile.two_qubit_fidelity**two_count
    )
    return float(gate_survival * (1.0 - 2.0 * profile.readout_error))


def apply_profile(
    features: np.ndarray,
    spec: AnsatzSpec,
    profile: ProviderProfile,
    shots: int,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    noisy = np.clip(profile_attenuation(spec, profile) * features, -1.0, 1.0)
    if shots <= 0 or profile.key == "xanadu":
        return noisy
    if rng is None:
        raise ValueError("A random generator is required for finite-shot simulation.")
    plus_probability = np.clip((noisy + 1.0) / 2.0, 0.0, 1.0)
    plus_counts = rng.binomial(shots, plus_probability)
    return 2.0 * plus_counts / shots - 1.0


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponential = np.exp(shifted)
    return exponential / exponential.sum(axis=1, keepdims=True)


def cross_entropy(probabilities: np.ndarray, y: np.ndarray) -> float:
    return float(-np.mean(np.log(probabilities[np.arange(len(y)), y] + EPS)))


def predictions(features: np.ndarray, weights: np.ndarray, bias: np.ndarray) -> np.ndarray:
    return softmax(features @ weights + bias)


def classification_metrics(y: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    labels = np.unique(y)
    accuracy = float(np.mean(predicted == y))
    recalls: list[float] = []
    f1_scores: list[float] = []
    for label in labels:
        true_positive = int(np.sum((predicted == label) & (y == label)))
        false_positive = int(np.sum((predicted == label) & (y != label)))
        false_negative = int(np.sum((predicted != label) & (y == label)))
        recall = true_positive / max(1, true_positive + false_negative)
        precision = true_positive / max(1, true_positive + false_positive)
        f1 = 2.0 * precision * recall / max(EPS, precision + recall)
        recalls.append(recall)
        f1_scores.append(f1)
    return {
        "accuracy": accuracy,
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_f1": float(np.mean(f1_scores)),
    }


class Adam:
    def __init__(self, shape: tuple[int, ...], learning_rate: float) -> None:
        self.learning_rate = learning_rate
        self.m = np.zeros(shape, dtype=float)
        self.v = np.zeros(shape, dtype=float)
        self.step_number = 0

    def step(self, values: np.ndarray, gradient: np.ndarray, scale: float = 1.0) -> np.ndarray:
        self.step_number += 1
        self.m = 0.9 * self.m + 0.1 * gradient
        self.v = 0.999 * self.v + 0.001 * gradient * gradient
        corrected_m = self.m / (1.0 - 0.9**self.step_number)
        corrected_v = self.v / (1.0 - 0.999**self.step_number)
        return values - scale * self.learning_rate * corrected_m / (
            np.sqrt(corrected_v) + 1e-8
        )


def stable_seed(*parts: str | int) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")


def train_configuration(
    dataset: PreparedDataset,
    spec: AnsatzSpec,
    profile: ProviderProfile,
    epochs: int,
    shots: int,
    seed: int,
    hyperparameters: dict[str, float | str] | None = None,
    evaluate_test: bool = True,
    model_output_path: Path | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    started = time.perf_counter()
    hp = dict(DEFAULT_HYPERPARAMETERS)
    if hyperparameters is not None:
        hp.update(hyperparameters)
    quantum_learning_rate = float(hp["quantum_learning_rate"])
    head_learning_rate = float(hp["head_learning_rate"])
    spsa_perturbation = float(hp["spsa_perturbation"])
    weight_decay = float(hp["weight_decay"])
    initialization_scale = float(hp["initialization_scale"])
    input_scale = float(hp["input_scale"])

    def run_features(values: np.ndarray, parameters: np.ndarray) -> np.ndarray:
        return quantum_features(spec, values, parameters, input_scale)

    # Common initialization and SPSA perturbations isolate the provider profile effect.
    run_seed = stable_seed(seed, dataset.name, spec.key)
    rng = np.random.default_rng(run_seed)
    n_classes = len(dataset.class_names)
    theta = rng.normal(0.0, initialization_scale, size=spec.parameters)
    weights = rng.normal(0.0, 0.12, size=(N_QUBITS, n_classes))
    bias = np.zeros(n_classes, dtype=float)
    theta_adam = Adam(theta.shape, quantum_learning_rate)
    weight_adam = Adam(weights.shape, head_learning_rate)
    bias_adam = Adam(bias.shape, head_learning_rate)
    best_loss = float("inf")
    best_epoch = 0
    best = (theta.copy(), weights.copy(), bias.copy())
    history: list[dict[str, object]] = []

    for epoch in range(epochs + 1):
        train_ideal = run_features(dataset.x_train, theta)
        train_features = apply_profile(train_ideal, spec, profile, 0)
        train_probabilities = predictions(train_features, weights, bias)

        if epoch < epochs:
            residual = train_probabilities.copy()
            residual[np.arange(len(dataset.y_train)), dataset.y_train] -= 1.0
            residual /= len(dataset.y_train)
            weight_gradient = train_features.T @ residual + weight_decay * weights
            bias_gradient = residual.sum(axis=0)
            weights = weight_adam.step(weights, weight_gradient)
            bias = bias_adam.step(bias, bias_gradient)

            perturbation = rng.choice([-1.0, 1.0], size=spec.parameters)
            c_k = spsa_perturbation / (epoch + 1.0) ** 0.101
            plus_features = apply_profile(
                run_features(dataset.x_train, theta + c_k * perturbation),
                spec,
                profile,
                0,
            )
            minus_features = apply_profile(
                run_features(dataset.x_train, theta - c_k * perturbation),
                spec,
                profile,
                0,
            )
            plus_loss = cross_entropy(
                predictions(plus_features, weights, bias), dataset.y_train
            )
            minus_loss = cross_entropy(
                predictions(minus_features, weights, bias), dataset.y_train
            )
            gradient = (plus_loss - minus_loss) * perturbation / (2.0 * c_k)
            gradient += weight_decay * theta
            schedule = 1.0 / (epoch + 1.0) ** 0.20
            theta = theta_adam.step(theta, gradient, schedule)

        train_features = apply_profile(
            run_features(dataset.x_train, theta), spec, profile, 0
        )
        val_features = apply_profile(
            run_features(dataset.x_val, theta), spec, profile, 0
        )
        train_probabilities = predictions(train_features, weights, bias)
        val_probabilities = predictions(val_features, weights, bias)
        train_loss = cross_entropy(train_probabilities, dataset.y_train)
        val_loss = cross_entropy(val_probabilities, dataset.y_val)
        train_accuracy = float(
            np.mean(np.argmax(train_probabilities, axis=1) == dataset.y_train)
        )
        val_accuracy = float(
            np.mean(np.argmax(val_probabilities, axis=1) == dataset.y_val)
        )
        history.append(
            {
                "dataset": dataset.name,
                "ansatz": spec.key,
                "provider": profile.key,
                "candidate_id": str(hp["candidate_id"]),
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "train_accuracy": train_accuracy,
                "val_accuracy": val_accuracy,
            }
        )
        if val_loss < best_loss:
            best_loss = val_loss
            best_epoch = epoch
            best = (theta.copy(), weights.copy(), bias.copy())

    theta, weights, bias = best
    if model_output_path is not None:
        model_output_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            model_output_path,
            theta=theta,
            weights=weights,
            bias=bias,
            input_scale=np.asarray(input_scale),
            candidate_id=np.asarray(str(hp["candidate_id"])),
            best_epoch=np.asarray(best_epoch),
            best_val_loss=np.asarray(best_loss),
            run_seed=np.asarray(run_seed),
        )
    common_result: dict[str, object] = {
        "dataset": dataset.name,
        "ansatz": spec.key,
        "ansatz_label": spec.label,
        "provider": profile.key,
        "provider_label": profile.label,
        "candidate_id": str(hp["candidate_id"]),
        "quantum_learning_rate": quantum_learning_rate,
        "head_learning_rate": head_learning_rate,
        "spsa_perturbation": spsa_perturbation,
        "weight_decay": weight_decay,
        "initialization_scale": initialization_scale,
        "input_scale": input_scale,
        "classes": len(dataset.class_names),
        "train_samples": len(dataset.y_train),
        "val_samples": len(dataset.y_val),
        "test_samples": len(dataset.y_test),
        "qubits": N_QUBITS,
        "quantum_parameters": spec.parameters,
        "classical_parameters": N_QUBITS * len(dataset.class_names)
        + len(dataset.class_names),
        "one_qubit_gates": spec.one_qubit_gates,
        "two_qubit_gates": spec.two_qubit_gates,
        "estimated_depth": spec.depth,
        "profile_attenuation": profile_attenuation(spec, profile),
        "shots": 0 if profile.key == "xanadu" else shots,
        "epochs": epochs,
        "best_epoch": best_epoch,
        "best_val_loss": best_loss,
        "explained_variance_4": dataset.explained_variance_4,
        "explained_variance_16": dataset.explained_variance_16,
        "runtime_seconds": time.perf_counter() - started,
        "run_seed": run_seed,
    }
    if not evaluate_test:
        return common_result, history

    ideal_test_features = run_features(dataset.x_test, theta)
    analytic_test_features = apply_profile(ideal_test_features, spec, profile, 0)
    shot_rng = np.random.default_rng(stable_seed(run_seed, profile.key, "shots"))
    shot_test_features = apply_profile(
        ideal_test_features, spec, profile, shots, shot_rng
    )
    ideal_probabilities = predictions(ideal_test_features, weights, bias)
    analytic_probabilities = predictions(analytic_test_features, weights, bias)
    shot_probabilities = predictions(shot_test_features, weights, bias)
    ideal_metrics = classification_metrics(
        dataset.y_test, np.argmax(ideal_probabilities, axis=1)
    )
    analytic_metrics = classification_metrics(
        dataset.y_test, np.argmax(analytic_probabilities, axis=1)
    )
    shot_metrics = classification_metrics(
        dataset.y_test, np.argmax(shot_probabilities, axis=1)
    )
    result = dict(common_result)
    result.update({
        "test_loss_ideal": cross_entropy(ideal_probabilities, dataset.y_test),
        "test_loss_profile_analytic": cross_entropy(
            analytic_probabilities, dataset.y_test
        ),
        "test_loss_profile_shots": cross_entropy(shot_probabilities, dataset.y_test),
        "test_accuracy_ideal": ideal_metrics["accuracy"],
        "test_accuracy_profile_analytic": analytic_metrics["accuracy"],
        "test_accuracy_profile_shots": shot_metrics["accuracy"],
        "test_balanced_accuracy_profile_shots": shot_metrics["balanced_accuracy"],
        "test_macro_f1_profile_shots": shot_metrics["macro_f1"],
    })
    result["runtime_seconds"] = time.perf_counter() - started
    return result, history


def hpo_trial_row(result: dict[str, object], stage: str) -> dict[str, object]:
    return {
        "dataset": result["dataset"],
        "ansatz": result["ansatz"],
        "provider": result["provider"],
        "stage": stage,
        "candidate_id": result["candidate_id"],
        "epochs": result["epochs"],
        "best_epoch": result["best_epoch"],
        "best_val_loss": result["best_val_loss"],
        "quantum_learning_rate": result["quantum_learning_rate"],
        "head_learning_rate": result["head_learning_rate"],
        "spsa_perturbation": result["spsa_perturbation"],
        "weight_decay": result["weight_decay"],
        "initialization_scale": result["initialization_scale"],
        "input_scale": result["input_scale"],
        "runtime_seconds": result["runtime_seconds"],
    }


def tune_configuration(
    dataset: PreparedDataset,
    spec: AnsatzSpec,
    profile: ProviderProfile,
    final_epochs: int,
    stage1_epochs: int,
    stage2_epochs: int,
    top_k: int,
    shots: int,
    seed: int,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    if top_k < 1 or top_k > len(HPO_CANDIDATES):
        raise ValueError("hpo_top_k must be between 1 and the candidate count.")
    trial_rows: list[dict[str, object]] = []
    stage1_results: list[tuple[dict[str, float | str], dict[str, object]]] = []
    for candidate in HPO_CANDIDATES:
        candidate_result, _ = train_configuration(
            dataset,
            spec,
            profile,
            stage1_epochs,
            shots,
            seed,
            candidate,
            evaluate_test=False,
        )
        stage1_results.append((candidate, candidate_result))
        trial_rows.append(hpo_trial_row(candidate_result, "stage1"))

    promoted = sorted(
        stage1_results,
        key=lambda item: (
            float(item[1]["best_val_loss"]),
            str(item[1]["candidate_id"]),
        ),
    )[:top_k]
    stage2_results: list[tuple[dict[str, float | str], dict[str, object]]] = []
    for candidate, _ in promoted:
        candidate_result, _ = train_configuration(
            dataset,
            spec,
            profile,
            stage2_epochs,
            shots,
            seed,
            candidate,
            evaluate_test=False,
        )
        stage2_results.append((candidate, candidate_result))
        trial_rows.append(hpo_trial_row(candidate_result, "stage2"))

    selected, selected_result = min(
        stage2_results,
        key=lambda item: (
            float(item[1]["best_val_loss"]),
            str(item[1]["candidate_id"]),
        ),
    )
    final_result, final_history = train_configuration(
        dataset,
        spec,
        profile,
        final_epochs,
        shots,
        seed,
        selected,
        evaluate_test=True,
    )
    hpo_runtime = sum(float(row["runtime_seconds"]) for row in trial_rows)
    final_result["hpo_trials"] = len(trial_rows)
    final_result["hpo_runtime_seconds"] = hpo_runtime
    final_result["total_runtime_seconds"] = hpo_runtime + float(
        final_result["runtime_seconds"]
    )
    best_row = {
        "dataset": dataset.name,
        "ansatz": spec.key,
        "provider": profile.key,
        "candidate_id": selected_result["candidate_id"],
        "stage2_best_epoch": selected_result["best_epoch"],
        "stage2_best_val_loss": selected_result["best_val_loss"],
        "quantum_learning_rate": selected_result["quantum_learning_rate"],
        "head_learning_rate": selected_result["head_learning_rate"],
        "spsa_perturbation": selected_result["spsa_perturbation"],
        "weight_decay": selected_result["weight_decay"],
        "initialization_scale": selected_result["initialization_scale"],
        "input_scale": selected_result["input_scale"],
    }
    return final_result, final_history, trial_rows, best_row


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(results: list[dict[str, object]]) -> dict[str, object]:
    def grouped(keys: tuple[str, ...]) -> list[dict[str, object]]:
        buckets: dict[tuple[str, ...], list[dict[str, object]]] = {}
        for row in results:
            group = tuple(str(row[key]) for key in keys)
            buckets.setdefault(group, []).append(row)
        output: list[dict[str, object]] = []
        for group, rows in sorted(buckets.items()):
            values = np.asarray(
                [float(row["test_balanced_accuracy_profile_shots"]) for row in rows]
            )
            record: dict[str, object] = {
                key: value for key, value in zip(keys, group)
            }
            record.update(
                {
                    "runs": len(rows),
                    "mean_balanced_accuracy": float(np.mean(values)),
                    "std_balanced_accuracy": float(np.std(values)),
                    "min_balanced_accuracy": float(np.min(values)),
                    "max_balanced_accuracy": float(np.max(values)),
                }
            )
            output.append(record)
        return output

    return {
        "result_count": len(results),
        "by_ansatz": grouped(("ansatz",)),
        "by_provider": grouped(("provider",)),
        "by_dataset": grouped(("dataset",)),
        "by_ansatz_provider": grouped(("ansatz", "provider")),
        "by_dataset_ansatz": grouped(("dataset", "ansatz")),
    }


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def write_report(
    path: Path,
    results: list[dict[str, object]],
    summary: dict[str, object],
    epochs: int,
    samples_per_class: int,
    shots: int,
    wall_elapsed: float,
    model_runtime: float,
    output_stem: str,
) -> None:
    by_ansatz = sorted(
        summary["by_ansatz"],
        key=lambda row: float(row["mean_balanced_accuracy"]),
        reverse=True,
    )
    by_provider = sorted(
        summary["by_provider"],
        key=lambda row: float(row["mean_balanced_accuracy"]),
        reverse=True,
    )
    lines = [
        "# Symulowane uczenie ansatzow na profilach Rigetti, IBM, IonQ i Xanadu",
        "",
        "## Status eksperymentu",
        "",
        f"- Ukonczone konfiguracje: {len(results)}.",
        f"- Budzet: {epochs} epok SPSA, do {samples_per_class} probek na klase.",
        f"- Odczyt: {shots} strzalow dla IBM/Rigetti/IonQ; Xanadu/PennyLane jest idealnym statevectorem.",
        f"- Czas calego procesu: {wall_elapsed:.1f} s.",
        f"- Suma czasu obliczen modeli: {model_runtime:.1f} s.",
        "- Metryka glowna: balanced accuracy na zbiorze testowym po symulacji profilu i strzalow.",
        "",
        "## Najwazniejsze wyniki",
        "",
    ]
    lines.extend(
        markdown_table(
            ["Ansatz", "Srednia BA", "Std", "Min", "Max", "Uruchomienia"],
            [
                [
                    ANSATZE[str(row["ansatz"])].label,
                    f"{float(row['mean_balanced_accuracy']):.3f}",
                    f"{float(row['std_balanced_accuracy']):.3f}",
                    f"{float(row['min_balanced_accuracy']):.3f}",
                    f"{float(row['max_balanced_accuracy']):.3f}",
                    str(row["runs"]),
                ]
                for row in by_ansatz
            ],
        )
    )
    lines.extend(["", "## Zalozenia profili", "", "Parametry szumu sa zalozeniami scenariusza, nie biezacymi kalibracjami konkretnego QPU.", ""])
    lines.extend(
        markdown_table(
            ["Profil", "Topologia", "Entangler", "F1", "F2", "Readout error"],
            [
                [
                    PROVIDERS[str(row["provider"])].label,
                    PROVIDERS[str(row["provider"])].topology,
                    PROVIDERS[str(row["provider"])].native_entangler,
                    f"{PROVIDERS[str(row['provider'])].one_qubit_fidelity:.4f}",
                    f"{PROVIDERS[str(row['provider'])].two_qubit_fidelity:.4f}",
                    f"{PROVIDERS[str(row['provider'])].readout_error:.3f}",
                ]
                for row in by_provider
            ],
        )
    )
    lines.extend(["", "## Profile sprzetowe", ""])
    lines.extend(
        markdown_table(
            ["Profil", "Srednia BA", "Std", "Min", "Max"],
            [
                [
                    PROVIDERS[str(row["provider"])].label,
                    f"{float(row['mean_balanced_accuracy']):.3f}",
                    f"{float(row['std_balanced_accuracy']):.3f}",
                    f"{float(row['min_balanced_accuracy']):.3f}",
                    f"{float(row['max_balanced_accuracy']):.3f}",
                ]
                for row in by_provider
            ],
        )
    )
    lines.extend(["", "## Najlepszy wariant dla kazdego zbioru i profilu", ""])
    best_rows: list[list[str]] = []
    datasets = sorted({str(row["dataset"]) for row in results})
    providers = sorted({str(row["provider"]) for row in results})
    for dataset in datasets:
        for provider in providers:
            candidates = [
                row
                for row in results
                if row["dataset"] == dataset and row["provider"] == provider
            ]
            if not candidates:
                continue
            best = max(
                candidates,
                key=lambda row: float(row["test_balanced_accuracy_profile_shots"]),
            )
            best_rows.append(
                [
                    dataset,
                    provider,
                    str(best["ansatz_label"]),
                    f"{float(best['test_balanced_accuracy_profile_shots']):.3f}",
                    f"{float(best['test_macro_f1_profile_shots']):.3f}",
                ]
            )
    lines.extend(
        markdown_table(
            ["Dataset", "Profil", "Najlepszy ansatz", "BA", "Macro F1"],
            best_rows,
        )
    )
    lines.extend(
        [
            "",
            "## Protokol",
            "",
            "1. Stratyfikowane 60/20/20 train/validation/test i PCA dopasowane wylacznie na train.",
            "2. Cztery skladowe PCA koduja standardowe obwody; approximate amplitude encoding korzysta z 16 skladowych.",
            "3. Kazdy obwod zwraca cztery wartosci oczekiwane Z. Liniowa glowica klasyczna mapuje je na 2, 3 lub 10 klas.",
            "4. Parametry kwantowe sa uczone przez SPSA, a glowica przez Adam. Najlepsza epoka jest wybierana po validation loss.",
            "5. Profil sprzetowy tlumi wartosci oczekiwane na podstawie liczby bramek, wskazanych fidelities, kosztu kompilacji i bledu odczytu; test IBM/Rigetti/IonQ uzywa skonczonej liczby strzalow.",
            "",
            "## Interpretacja ansatzow domenowych",
            "",
            "- UCCSD + Hartree-Fock jest tu klasyfikatorem zachowujacym liczbe wzbudzen, a nie obliczeniem energii molekuly.",
            "- QAOA uzywa cech jako wspolczynnikow faz kosztu, a nie rozwiazuje osobnego problemu kombinatorycznego.",
            "- Bloki QGAN sa oceniane jako obwody cech z cross-entropy; nie jest to pelne uczenie adversarialne generatora i dyskryminatora.",
            "- Xanadu oznacza idealna semantyke qubitowego symulatora PennyLane. Nie jest to emulacja fotonicznego QPU ani Gaussian boson sampling.",
            "- QAOA zajmuje pierwsze miejsce dla tej konkretnej adaptacji danych do faz kosztu; nie dowodzi to ogolnej przewagi QAOA w klasyfikacji.",
            "",
            "## Weryfikacja profili",
            "",
            "- [IBM](https://quantum.cloud.ibm.com/docs/en/guides/calibration-jobs) opisuje heavy-hex oraz zalezne od generacji bramki ECR, CZ i RZZ.",
            "- [Rigetti](https://docs.rigetti.com/qcs/faq) wskazuje program kalibracyjny QPU jako autorytatywne i zmienne w czasie zrodlo bramek natywnych.",
            "- [IonQ](https://www.ionq.com/resources/best-practices-for-using-ionq-hardware) potwierdza trapped ions i lacznosc all-to-all.",
            "- [PennyLane](https://docs.pennylane.ai/en/stable/introduction/circuits.html) opisuje default.qubit jako lokalny symulator.",
            "",
            "## Ograniczenia",
            "",
            "- To kontrolowany benchmark lokalny, nie wykonanie na fizycznych QPU i nie kalibrowany digital twin konkretnego urzadzenia.",
            "- Jedno ziarno losowe i maly budzet danych/epok sluza do przesiewu architektur, nie do publikacyjnego rankingu.",
            "- Analityczny model szumu nie odtwarza crosstalku, dryfu kalibracji, leakage ani pelnej kompilacji natywnych bramek; fidelities w tabeli sa zalozeniami, nie pomiarami z 23 lipca 2026.",
            "- Wieloklasowe MNIST i OptDigits sa celowo trudne dla czterech wartosci oczekiwanych; wynik nalezy porownywac z poziomem losowym 0.1.",
            "",
            "## Pliki",
            "",
            f"- `{output_stem}_results.csv` - jedna linia na konfiguracje.",
            f"- `{output_stem}_history.csv` - przebieg kazdej epoki.",
            f"- `{output_stem}_summary.json` - agregaty i parametry profili.",
            f"- `{output_stem}.png` - srednia balanced accuracy ansatz x profil.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_baseline_comparison(
    results: list[dict[str, object]], baseline_rows: list[dict[str, object]]
) -> None:
    lookup = {
        (str(row["dataset"]), str(row["ansatz"]), str(row["provider"])): (
            float(row["test_balanced_accuracy_profile_shots"]),
            int(float(row["epochs"])),
        )
        for row in baseline_rows
    }
    for row in results:
        key = (str(row["dataset"]), str(row["ansatz"]), str(row["provider"]))
        baseline, baseline_epochs = lookup.get(key, (float("nan"), 0))
        tuned = float(row["test_balanced_accuracy_profile_shots"])
        row["baseline_balanced_accuracy"] = baseline
        row["baseline_epochs"] = baseline_epochs
        row["delta_balanced_accuracy_vs_baseline"] = tuned - baseline


def append_hpo_report(
    path: Path,
    results: list[dict[str, object]],
    trials: list[dict[str, object]],
    best_rows: list[dict[str, object]],
    stage1_epochs: int,
    stage2_epochs: int,
    top_k: int,
    output_stem: str,
) -> None:
    selection_counts: dict[str, int] = {}
    for row in best_rows:
        candidate = str(row["candidate_id"])
        selection_counts[candidate] = selection_counts.get(candidate, 0) + 1

    comparable = [
        row
        for row in results
        if math.isfinite(float(row.get("baseline_balanced_accuracy", float("nan"))))
    ]

    def comparison(label: str, rows: list[dict[str, object]]) -> list[str]:
        baseline = np.asarray(
            [float(row["baseline_balanced_accuracy"]) for row in rows], dtype=float
        )
        tuned = np.asarray(
            [float(row["test_balanced_accuracy_profile_shots"]) for row in rows],
            dtype=float,
        )
        delta = tuned - baseline
        return [
            label,
            f"{float(np.mean(baseline)):.3f}",
            f"{float(np.mean(tuned)):.3f}",
            f"{float(np.mean(delta)):+.3f}",
            str(int(np.sum(delta > 1e-12))),
            str(int(np.sum(np.abs(delta) <= 1e-12))),
            str(int(np.sum(delta < -1e-12))),
        ]

    comparison_rows: list[list[str]] = []
    if comparable:
        comparison_rows.append(comparison("Wszystkie", comparable))
        for dataset in sorted({str(row["dataset"]) for row in comparable}):
            comparison_rows.append(
                comparison(
                    dataset,
                    [row for row in comparable if str(row["dataset"]) == dataset],
                )
            )

    lines = [
        "",
        "## Optymalizacja hiperparametrow",
        "",
        f"Dla kazdej konfiguracji oceniono {len(HPO_CANDIDATES)} kandydatow przez {stage1_epochs} epok. Do drugiego etapu przechodzilo {top_k} kandydatow, uczonych od nowa przez {stage2_epochs} epok. Zwyciezca byl wybierany tylko wedlug validation loss, a test zostal obliczony dopiero po wyborze i koncowym treningu.",
        "",
        f"Liczba zapisanych prob HPO: {len(trials)}. Liczba wybranych zestawow: {len(best_rows)}.",
        "",
    ]
    lines.extend(
        markdown_table(
            ["Kandydat", "LR quantum", "LR head", "SPSA c", "L2", "Init", "Input scale"],
            [
                [
                    str(candidate["candidate_id"]),
                    f"{float(candidate['quantum_learning_rate']):.3f}",
                    f"{float(candidate['head_learning_rate']):.3f}",
                    f"{float(candidate['spsa_perturbation']):.3f}",
                    f"{float(candidate['weight_decay']):.5f}",
                    f"{float(candidate['initialization_scale']):.3f}",
                    f"{float(candidate['input_scale']):.2f}",
                ]
                for candidate in HPO_CANDIDATES
            ],
        )
    )
    lines.extend(["", "### Wybrane zestawy", ""])
    lines.extend(
        markdown_table(
            ["Kandydat", "Wybrany dla konfiguracji"],
            [
                [candidate, str(count)]
                for candidate, count in sorted(
                    selection_counts.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        )
    )
    if comparison_rows:
        lines.extend(["", "### Porownanie z procesem bazowym", ""])
        lines.extend(
            markdown_table(
                ["Zakres", "Bazowa BA", "BA po HPO", "Delta", "Lepsze", "Remis", "Gorsze"],
                comparison_rows,
            )
        )
        baseline_budgets = sorted(
            {int(float(row["baseline_epochs"])) for row in comparable}
        )
        tuned_budgets = sorted({int(float(row["epochs"])) for row in comparable})
        baseline_budget_text = ", ".join(str(value) for value in baseline_budgets)
        tuned_budget_text = ", ".join(str(value) for value in tuned_budgets)
        lines.extend(
            [
                "",
                f"Uwaga: proces bazowy uzywal budzetu {baseline_budget_text} epok, a trening koncowy po HPO {tuned_budget_text} epok. Delta laczy efekt strojenia i wiekszego budzetu; nie izoluje wylacznie wplywu hiperparametrow.",
            ]
        )
    lines.extend(
        [
            "",
            "### Pliki HPO",
            "",
            f"- `{output_stem}_hpo_trials.csv` - wyniki obu etapow strojenia bez metryk testowych.",
            f"- `{output_stem}_best_hyperparameters.csv` - zestaw wybrany dla kazdej konfiguracji.",
            "",
            "Wielokrotne porownania na malym zbiorze validation moga powodowac optymizm selekcyjny. Do wnioskowania publikacyjnego potrzebne sa powtorzenia na wielu ziarnach albo nested cross-validation.",
        ]
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def plot_summary(path: Path, summary: dict[str, object]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ansatz_keys = list(ANSATZE)
    provider_keys = list(PROVIDERS)
    lookup = {
        (str(row["ansatz"]), str(row["provider"])): float(
            row["mean_balanced_accuracy"]
        )
        for row in summary["by_ansatz_provider"]
    }
    matrix = np.full((len(ansatz_keys), len(provider_keys)), np.nan)
    for row_index, ansatz in enumerate(ansatz_keys):
        for column_index, provider in enumerate(provider_keys):
            matrix[row_index, column_index] = lookup.get((ansatz, provider), np.nan)
    figure, axis = plt.subplots(figsize=(10, 9))
    image = axis.imshow(matrix, vmin=0.0, vmax=1.0, cmap="viridis", aspect="auto")
    axis.set_xticks(range(len(provider_keys)), [key.upper() for key in provider_keys])
    axis.set_yticks(
        range(len(ansatz_keys)), [ANSATZE[key].label for key in ansatz_keys], fontsize=8
    )
    axis.set_title("Srednia balanced accuracy po profilach sprzetowych")
    axis.set_xlabel("Profil symulowanego wykonania")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            if np.isfinite(value):
                color = "white" if value < 0.45 else "black"
                axis.text(
                    column,
                    row,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=8,
                )
    figure.colorbar(image, ax=axis, label="Balanced accuracy")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def parse_selection(value: str, options: dict[str, object], name: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(options)
    selected = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(selected) - set(options))
    if unknown:
        raise ValueError(f"Unknown {name}: {', '.join(unknown)}")
    return selected


def load_existing(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train 14 ansatz families on four datasets and four hardware profiles."
    )
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--samples-per-class", type=int, default=24)
    parser.add_argument("--shots", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--datasets", default="all")
    parser.add_argument("--ansatze", default="all")
    parser.add_argument("--providers", default="all")
    parser.add_argument("--output-stem", default="ansatz_hardware_dataset_benchmark")
    parser.add_argument("--hpo", action="store_true")
    parser.add_argument("--hpo-stage1-epochs", type=int, default=8)
    parser.add_argument("--hpo-stage2-epochs", type=int, default=18)
    parser.add_argument("--hpo-top-k", type=int, default=3)
    parser.add_argument(
        "--baseline-results",
        default=str(OUT / "ansatz_hardware_dataset_benchmark_results.csv"),
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    dataset_options = {
        "wine": lambda: load_wine(),
        "mnist": lambda: load_mnist(args.samples_per_class, args.seed),
        "optdigits": lambda: load_optdigits(),
        "breast_cancer": lambda: load_breast_cancer(),
    }
    dataset_keys = parse_selection(args.datasets, dataset_options, "dataset")
    ansatz_keys = parse_selection(args.ansatze, ANSATZE, "ansatz")
    provider_keys = parse_selection(args.providers, PROVIDERS, "provider")
    results_path = OUT / f"{args.output_stem}_results.csv"
    history_path = OUT / f"{args.output_stem}_history.csv"
    summary_path = OUT / f"{args.output_stem}_summary.json"
    report_path = OUT / f"{args.output_stem}_report.md"
    plot_path = OUT / f"{args.output_stem}.png"
    hpo_trials_path = OUT / f"{args.output_stem}_hpo_trials.csv"
    best_hyperparameters_path = OUT / f"{args.output_stem}_best_hyperparameters.csv"
    previous_wall_elapsed = 0.0
    if args.resume and summary_path.exists():
        try:
            previous_payload = json.loads(summary_path.read_text(encoding="utf-8"))
            previous_metadata = previous_payload.get("metadata", {})
            previous_wall_elapsed = float(
                previous_metadata.get(
                    "wall_clock_seconds_full_run",
                    previous_metadata.get("elapsed_seconds_current_process", 0.0),
                )
            )
        except (ValueError, TypeError, json.JSONDecodeError):
            previous_wall_elapsed = 0.0
    results = load_existing(results_path) if args.resume else []
    results = list(
        {
            (
                str(row["dataset"]),
                str(row["ansatz"]),
                str(row["provider"]),
            ): row
            for row in results
        }.values()
    )
    history = load_existing(history_path) if args.resume else []
    history = list(
        {
            (
                str(row["dataset"]),
                str(row["ansatz"]),
                str(row["provider"]),
                str(row["epoch"]),
            ): row
            for row in history
        }.values()
    )
    hpo_trials = (
        load_existing(hpo_trials_path) if args.resume and args.hpo else []
    )
    hpo_trials = list(
        {
            (
                str(row["dataset"]),
                str(row["ansatz"]),
                str(row["provider"]),
                str(row["stage"]),
                str(row["candidate_id"]),
            ): row
            for row in hpo_trials
        }.values()
    )
    best_hyperparameters = (
        load_existing(best_hyperparameters_path) if args.resume and args.hpo else []
    )
    best_hyperparameters = list(
        {
            (
                str(row["dataset"]),
                str(row["ansatz"]),
                str(row["provider"]),
            ): row
            for row in best_hyperparameters
        }.values()
    )
    completed = {
        (str(row["dataset"]), str(row["ansatz"]), str(row["provider"]))
        for row in results
    }
    total = len(dataset_keys) * len(ansatz_keys) * len(provider_keys)
    finished = sum(
        (dataset, ansatz, provider) in completed
        for dataset in dataset_keys
        for ansatz in ansatz_keys
        for provider in provider_keys
    )
    started = time.perf_counter()

    for dataset_key in dataset_keys:
        print(f"Loading and preparing {dataset_key}...", flush=True)
        raw = dataset_options[dataset_key]()
        sampled = balanced_subsample(raw, args.samples_per_class, args.seed)
        dataset = prepare_dataset(sampled, args.seed)
        for ansatz_key in ansatz_keys:
            spec = ANSATZE[ansatz_key]
            for provider_key in provider_keys:
                profile = PROVIDERS[provider_key]
                key = (dataset_key, ansatz_key, provider_key)
                if key in completed:
                    continue
                finished += 1
                print(
                    f"[{finished}/{total}] {dataset_key} | {ansatz_key} | {provider_key}",
                    flush=True,
                )
                if args.hpo:
                    result, run_history, run_trials, best_row = tune_configuration(
                        dataset,
                        spec,
                        profile,
                        args.epochs,
                        args.hpo_stage1_epochs,
                        args.hpo_stage2_epochs,
                        args.hpo_top_k,
                        args.shots,
                        args.seed,
                    )
                    hpo_trials = [
                        row
                        for row in hpo_trials
                        if (
                            str(row["dataset"]),
                            str(row["ansatz"]),
                            str(row["provider"]),
                        )
                        != key
                    ]
                    hpo_trials.extend(run_trials)
                    best_hyperparameters = [
                        row
                        for row in best_hyperparameters
                        if (
                            str(row["dataset"]),
                            str(row["ansatz"]),
                            str(row["provider"]),
                        )
                        != key
                    ]
                    best_hyperparameters.append(best_row)
                else:
                    result, run_history = train_configuration(
                        dataset,
                        spec,
                        profile,
                        args.epochs,
                        args.shots,
                        args.seed,
                    )
                results.append(result)
                history = [
                    row
                    for row in history
                    if (
                        str(row["dataset"]),
                        str(row["ansatz"]),
                        str(row["provider"]),
                    )
                    != key
                ]
                history.extend(run_history)
                completed.add(key)
                write_csv(results_path, results)
                write_csv(history_path, history)
                if args.hpo:
                    write_csv(hpo_trials_path, hpo_trials)
                    write_csv(best_hyperparameters_path, best_hyperparameters)

    experiment_results = [
        row
        for row in results
        if str(row["dataset"]) in dataset_keys
        and str(row["ansatz"]) in ansatz_keys
        and str(row["provider"]) in provider_keys
    ]
    experiment_trials = [
        row
        for row in hpo_trials
        if str(row["dataset"]) in dataset_keys
        and str(row["ansatz"]) in ansatz_keys
        and str(row["provider"]) in provider_keys
    ]
    experiment_best_hyperparameters = [
        row
        for row in best_hyperparameters
        if str(row["dataset"]) in dataset_keys
        and str(row["ansatz"]) in ansatz_keys
        and str(row["provider"]) in provider_keys
    ]
    baseline_rows: list[dict[str, object]] = []
    if args.hpo:
        baseline_path = Path(args.baseline_results)
        baseline_rows = load_existing(baseline_path)
        add_baseline_comparison(experiment_results, baseline_rows)
    write_csv(results_path, results)
    write_csv(history_path, history)
    if args.hpo:
        write_csv(hpo_trials_path, hpo_trials)
        write_csv(best_hyperparameters_path, best_hyperparameters)
    summary = summarize(experiment_results)
    elapsed = time.perf_counter() - started
    wall_elapsed = max(elapsed, previous_wall_elapsed)
    total_model_runtime = sum(
        float(row["runtime_seconds"]) for row in experiment_results
    )
    total_hpo_runtime = sum(
        float(row["runtime_seconds"]) for row in experiment_trials
    )
    total_compute_runtime = total_model_runtime + total_hpo_runtime
    payload = {
        "metadata": {
            "epochs": args.epochs,
            "samples_per_class": args.samples_per_class,
            "shots": args.shots,
            "seed": args.seed,
            "qubits": N_QUBITS,
            "datasets": dataset_keys,
            "ansatze": ansatz_keys,
            "providers": provider_keys,
            "wall_clock_seconds_full_run": wall_elapsed,
            "elapsed_seconds_current_process": elapsed,
            "summed_configuration_runtime_seconds": total_model_runtime,
            "summed_hpo_runtime_seconds": total_hpo_runtime,
            "summed_total_compute_runtime_seconds": total_compute_runtime,
            "hpo_enabled": args.hpo,
            "hpo_stage1_epochs": args.hpo_stage1_epochs if args.hpo else None,
            "hpo_stage2_epochs": args.hpo_stage2_epochs if args.hpo else None,
            "hpo_top_k": args.hpo_top_k if args.hpo else None,
        },
        "provider_profiles": {
            key: asdict(PROVIDERS[key]) for key in provider_keys
        },
        "ansatz_specs": {
            key: {
                field: value
                for field, value in asdict(ANSATZE[key]).items()
                if field != "circuit"
            }
            for key in ansatz_keys
        },
        "summary": summary,
        "hpo_candidates": HPO_CANDIDATES if args.hpo else [],
        "best_hyperparameters": experiment_best_hyperparameters if args.hpo else [],
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(
        report_path,
        experiment_results,
        summary,
        args.epochs,
        args.samples_per_class,
        args.shots,
        wall_elapsed,
        total_compute_runtime,
        args.output_stem,
    )
    if args.hpo:
        append_hpo_report(
            report_path,
            experiment_results,
            experiment_trials,
            experiment_best_hyperparameters,
            args.hpo_stage1_epochs,
            args.hpo_stage2_epochs,
            args.hpo_top_k,
            args.output_stem,
        )
    if not args.no_plots:
        plot_summary(plot_path, summary)
    print(f"Completed {len(experiment_results)} configurations in {elapsed:.1f} s.")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
