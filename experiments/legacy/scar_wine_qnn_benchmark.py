from __future__ import annotations

import argparse
import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from experiments.legacy.vqe_scar_ansatz_experiment import scar


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis_output"
WINE_DATA = ROOT / "datasets" / "qml_benchmarks" / "wine" / "wine.data"

N_QUBITS = 4
N_CLASSES = 3
SCAR_LAYERS = 2
SCAR_PARAMETERS = SCAR_LAYERS * (3 * N_QUBITS + 2)
READOUT_PARAMETERS = N_QUBITS * N_CLASSES + N_CLASSES
QNN_PARAMETERS = SCAR_PARAMETERS + READOUT_PARAMETERS
MLP_HIDDEN = 5
MLP_PARAMETERS = (
    N_QUBITS * MLP_HIDDEN
    + MLP_HIDDEN
    + MLP_HIDDEN * N_CLASSES
    + N_CLASSES
)


@dataclass(frozen=True)
class Split:
    x_train: np.ndarray
    y_train: np.ndarray
    x_val: np.ndarray
    y_val: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray
    pca_explained: float


@dataclass
class Adam:
    m: np.ndarray
    v: np.ndarray
    step: int = 0

    @classmethod
    def for_parameters(cls, parameters: np.ndarray) -> "Adam":
        return cls(np.zeros_like(parameters), np.zeros_like(parameters))

    def update(
        self,
        parameters: np.ndarray,
        gradient: np.ndarray,
        learning_rate: float,
        beta1: float = 0.9,
        beta2: float = 0.999,
        epsilon: float = 1e-8,
    ) -> np.ndarray:
        self.step += 1
        self.m = beta1 * self.m + (1.0 - beta1) * gradient
        self.v = beta2 * self.v + (1.0 - beta2) * (gradient * gradient)
        m_hat = self.m / (1.0 - beta1**self.step)
        v_hat = self.v / (1.0 - beta2**self.step)
        return parameters - learning_rate * m_hat / (np.sqrt(v_hat) + epsilon)


def load_wine() -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(WINE_DATA, delimiter=",", dtype=float)
    y = data[:, 0].astype(int) - 1
    x = data[:, 1:]
    if x.shape != (178, 13) or set(np.unique(y)) != {0, 1, 2}:
        raise ValueError(f"Unexpected Wine data shape or labels: x={x.shape}, y={np.unique(y)}")
    return x, y


def stratified_split(
    y: np.ndarray,
    seed: int,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train: list[int] = []
    validation: list[int] = []
    test: list[int] = []
    for label in sorted(np.unique(y)):
        indices = rng.permutation(np.flatnonzero(y == label))
        n_train = int(round(train_fraction * len(indices)))
        n_validation = int(round(validation_fraction * len(indices)))
        train.extend(indices[:n_train].tolist())
        validation.extend(indices[n_train : n_train + n_validation].tolist())
        test.extend(indices[n_train + n_validation :].tolist())
    return (
        rng.permutation(np.asarray(train, dtype=int)),
        rng.permutation(np.asarray(validation, dtype=int)),
        rng.permutation(np.asarray(test, dtype=int)),
    )


def pca_preprocess(
    x_train: np.ndarray,
    x_val: np.ndarray,
    x_test: np.ndarray,
    components: int = N_QUBITS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std = np.where(std < 1e-12, 1.0, std)
    train_standard = (x_train - mean) / std
    val_standard = (x_val - mean) / std
    test_standard = (x_test - mean) / std

    covariance = train_standard.T @ train_standard / (len(train_standard) - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    basis = eigenvectors[:, order[:components]].copy()

    # Stabilize the arbitrary PCA sign so repeated runs are easy to compare.
    for column in range(basis.shape[1]):
        pivot = int(np.argmax(np.abs(basis[:, column])))
        if basis[pivot, column] < 0.0:
            basis[:, column] *= -1.0

    scale = np.sqrt(np.maximum(eigenvalues[:components], 1e-12))

    def transform(values: np.ndarray) -> np.ndarray:
        whitened = (values @ basis) / scale
        # The clipping is learned from no test information and maps robustly to angles.
        return np.pi * np.clip(whitened, -3.0, 3.0) / 3.0

    explained = float(eigenvalues[:components].sum() / eigenvalues.sum())
    return (
        transform(train_standard),
        transform(val_standard),
        transform(test_standard),
        explained,
    )


def prepare_split(x: np.ndarray, y: np.ndarray, seed: int) -> Split:
    train_idx, validation_idx, test_idx = stratified_split(y, seed)
    x_train, x_val, x_test, explained = pca_preprocess(
        x[train_idx], x[validation_idx], x[test_idx]
    )
    return Split(
        x_train=x_train,
        y_train=y[train_idx],
        x_val=x_val,
        y_val=y[validation_idx],
        x_test=x_test,
        y_test=y[test_idx],
        pca_explained=explained,
    )


def ry_batch(theta: np.ndarray) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    cosine = np.cos(theta / 2.0)
    sine = np.sin(theta / 2.0)
    gates = np.empty((len(theta), 2, 2), dtype=complex)
    gates[:, 0, 0] = cosine
    gates[:, 0, 1] = -sine
    gates[:, 1, 0] = sine
    gates[:, 1, 1] = cosine
    return gates


def rz_batch(theta: np.ndarray) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    gates = np.zeros((len(theta), 2, 2), dtype=complex)
    gates[:, 0, 0] = np.exp(-0.5j * theta)
    gates[:, 1, 1] = np.exp(0.5j * theta)
    return gates


def ry(theta: float) -> np.ndarray:
    cosine = math.cos(theta / 2.0)
    sine = math.sin(theta / 2.0)
    return np.array([[cosine, -sine], [sine, cosine]], dtype=complex)


def rz(theta: float) -> np.ndarray:
    return np.array(
        [
            [np.exp(-0.5j * theta), 0.0],
            [0.0, np.exp(0.5j * theta)],
        ],
        dtype=complex,
    )


def apply_one_shared(
    state: np.ndarray, gate: np.ndarray, qubit: int, qubits: int = N_QUBITS
) -> np.ndarray:
    batch = len(state)
    tensor = state.reshape((batch,) + (2,) * qubits)
    tensor = np.moveaxis(tensor, 1 + qubit, 1)
    shape = tensor.shape
    pair = tensor.reshape(batch, 2, -1)
    pair = np.einsum("ij,bjk->bik", gate, pair, optimize=True)
    tensor = pair.reshape(shape)
    tensor = np.moveaxis(tensor, 1, 1 + qubit)
    return tensor.reshape(batch, -1)


def apply_one_batched(
    state: np.ndarray, gates: np.ndarray, qubit: int, qubits: int = N_QUBITS
) -> np.ndarray:
    batch = len(state)
    tensor = state.reshape((batch,) + (2,) * qubits)
    tensor = np.moveaxis(tensor, 1 + qubit, 1)
    shape = tensor.shape
    pair = tensor.reshape(batch, 2, -1)
    pair = np.einsum("bij,bjk->bik", gates, pair, optimize=True)
    tensor = pair.reshape(shape)
    tensor = np.moveaxis(tensor, 1, 1 + qubit)
    return tensor.reshape(batch, -1)


def apply_two_shared(
    state: np.ndarray,
    gate: np.ndarray,
    q0: int,
    q1: int,
    qubits: int = N_QUBITS,
) -> np.ndarray:
    batch = len(state)
    tensor = state.reshape((batch,) + (2,) * qubits)
    tensor = np.moveaxis(tensor, [1 + q0, 1 + q1], [1, 2])
    shape = tensor.shape
    pair = tensor.reshape(batch, 4, -1)
    pair = np.einsum("ij,bjk->bik", gate, pair, optimize=True)
    tensor = pair.reshape(shape)
    tensor = np.moveaxis(tensor, [1, 2], [1 + q0, 1 + q1])
    return tensor.reshape(batch, -1)


def scar_ring_features(x: np.ndarray, parameters: np.ndarray) -> np.ndarray:
    if len(parameters) != SCAR_PARAMETERS:
        raise ValueError(f"Expected {SCAR_PARAMETERS} SCAR parameters, got {len(parameters)}")
    batch = len(x)
    state = np.zeros((batch, 1 << N_QUBITS), dtype=complex)
    state[:, 0] = 1.0

    for qubit in range(N_QUBITS):
        state = apply_one_batched(state, ry_batch(x[:, qubit]), qubit)
        state = apply_one_batched(state, rz_batch(x[:, qubit]), qubit)

    edges = [(q, (q + 1) % N_QUBITS) for q in range(N_QUBITS)]
    offset = 0
    for _ in range(SCAR_LAYERS):
        local_ry = parameters[offset : offset + N_QUBITS]
        offset += N_QUBITS
        local_rz = parameters[offset : offset + N_QUBITS]
        offset += N_QUBITS
        exchange = parameters[offset : offset + N_QUBITS]
        offset += N_QUBITS
        delta = float(parameters[offset])
        phi = float(parameters[offset + 1])
        offset += 2

        for qubit in range(N_QUBITS):
            state = apply_one_shared(state, ry(float(local_ry[qubit])), qubit)
            state = apply_one_shared(state, rz(float(local_rz[qubit])), qubit)
        for edge_index, (q0, q1) in enumerate(edges):
            gate = scar(float(exchange[edge_index]), delta, phi)
            state = apply_two_shared(state, gate, q0, q1)

    probabilities = np.abs(state) ** 2
    basis = np.arange(1 << N_QUBITS)
    signs = np.empty((N_QUBITS, 1 << N_QUBITS), dtype=float)
    for qubit in range(N_QUBITS):
        bit = (basis >> (N_QUBITS - 1 - qubit)) & 1
        signs[qubit] = 1.0 - 2.0 * bit
    return probabilities @ signs.T


def initialize_qnn(rng: np.random.Generator) -> np.ndarray:
    circuit: list[float] = []
    for _ in range(SCAR_LAYERS):
        circuit.extend(rng.normal(0.0, 0.20, size=N_QUBITS))
        circuit.extend(rng.normal(0.0, 0.20, size=N_QUBITS))
        circuit.extend(rng.normal(0.25, 0.08, size=N_QUBITS))
        circuit.append(float(rng.uniform(-np.pi, np.pi)))
        circuit.append(float(rng.normal(0.0, 0.20)))
    circuit_array = np.asarray(circuit, dtype=float)
    readout = rng.normal(
        0.0, math.sqrt(2.0 / (N_QUBITS + N_CLASSES)), size=(N_QUBITS, N_CLASSES)
    )
    bias = np.zeros(N_CLASSES, dtype=float)
    return np.concatenate([circuit_array, readout.reshape(-1), bias])


def unpack_qnn(parameters: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    circuit = parameters[:SCAR_PARAMETERS]
    readout_start = SCAR_PARAMETERS
    readout_end = readout_start + N_QUBITS * N_CLASSES
    readout = parameters[readout_start:readout_end].reshape(N_QUBITS, N_CLASSES)
    bias = parameters[readout_end:]
    return circuit, readout, bias


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponential = np.exp(shifted)
    return exponential / exponential.sum(axis=1, keepdims=True)


def cross_entropy(probabilities: np.ndarray, y: np.ndarray) -> float:
    selected = np.maximum(probabilities[np.arange(len(y)), y], 1e-12)
    return float(-np.mean(np.log(selected)))


def accuracy(probabilities: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(np.argmax(probabilities, axis=1) == y))


def qnn_probabilities(x: np.ndarray, parameters: np.ndarray) -> np.ndarray:
    circuit, readout, bias = unpack_qnn(parameters)
    features = scar_ring_features(x, circuit)
    return softmax(features @ readout + bias)


def qnn_loss_and_gradient(
    x: np.ndarray,
    y: np.ndarray,
    parameters: np.ndarray,
    finite_difference: float,
    weight_decay: float,
) -> tuple[float, np.ndarray, np.ndarray, int]:
    circuit, readout, bias = unpack_qnn(parameters)
    features = scar_ring_features(x, circuit)
    logits = features @ readout + bias
    probabilities = softmax(logits)
    loss = cross_entropy(probabilities, y)

    targets = np.zeros_like(probabilities)
    targets[np.arange(len(y)), y] = 1.0
    d_logits = (probabilities - targets) / len(y)
    readout_gradient = features.T @ d_logits + weight_decay * readout
    bias_gradient = d_logits.sum(axis=0)
    d_features = d_logits @ readout.T

    circuit_gradient = np.empty_like(circuit)
    for index in range(len(circuit)):
        plus = circuit.copy()
        minus = circuit.copy()
        plus[index] += finite_difference
        minus[index] -= finite_difference
        plus_features = scar_ring_features(x, plus)
        minus_features = scar_ring_features(x, minus)
        derivative = (plus_features - minus_features) / (2.0 * finite_difference)
        circuit_gradient[index] = np.sum(d_features * derivative)
    circuit_gradient += weight_decay * circuit

    gradient = np.concatenate(
        [circuit_gradient, readout_gradient.reshape(-1), bias_gradient]
    )
    sample_circuit_evaluations = len(x) * (1 + 2 * len(circuit))
    return loss, gradient, probabilities, sample_circuit_evaluations


def initialize_mlp(rng: np.random.Generator) -> np.ndarray:
    w1 = rng.normal(
        0.0, math.sqrt(2.0 / (N_QUBITS + MLP_HIDDEN)), size=(N_QUBITS, MLP_HIDDEN)
    )
    b1 = np.zeros(MLP_HIDDEN, dtype=float)
    w2 = rng.normal(
        0.0, math.sqrt(2.0 / (MLP_HIDDEN + N_CLASSES)), size=(MLP_HIDDEN, N_CLASSES)
    )
    b2 = np.zeros(N_CLASSES, dtype=float)
    return np.concatenate([w1.reshape(-1), b1, w2.reshape(-1), b2])


def unpack_mlp(
    parameters: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    offset = 0
    w1 = parameters[offset : offset + N_QUBITS * MLP_HIDDEN].reshape(
        N_QUBITS, MLP_HIDDEN
    )
    offset += N_QUBITS * MLP_HIDDEN
    b1 = parameters[offset : offset + MLP_HIDDEN]
    offset += MLP_HIDDEN
    w2 = parameters[offset : offset + MLP_HIDDEN * N_CLASSES].reshape(
        MLP_HIDDEN, N_CLASSES
    )
    offset += MLP_HIDDEN * N_CLASSES
    b2 = parameters[offset:]
    return w1, b1, w2, b2


def mlp_probabilities(x: np.ndarray, parameters: np.ndarray) -> np.ndarray:
    w1, b1, w2, b2 = unpack_mlp(parameters)
    hidden = np.tanh(x @ w1 + b1)
    return softmax(hidden @ w2 + b2)


def mlp_loss_and_gradient(
    x: np.ndarray,
    y: np.ndarray,
    parameters: np.ndarray,
    weight_decay: float,
) -> tuple[float, np.ndarray, np.ndarray]:
    w1, b1, w2, b2 = unpack_mlp(parameters)
    hidden = np.tanh(x @ w1 + b1)
    probabilities = softmax(hidden @ w2 + b2)
    loss = cross_entropy(probabilities, y)

    targets = np.zeros_like(probabilities)
    targets[np.arange(len(y)), y] = 1.0
    d_logits = (probabilities - targets) / len(y)
    dw2 = hidden.T @ d_logits + weight_decay * w2
    db2 = d_logits.sum(axis=0)
    d_hidden = d_logits @ w2.T
    d_pre_activation = d_hidden * (1.0 - hidden * hidden)
    dw1 = x.T @ d_pre_activation + weight_decay * w1
    db1 = d_pre_activation.sum(axis=0)
    gradient = np.concatenate([dw1.reshape(-1), db1, dw2.reshape(-1), db2])
    return loss, gradient, probabilities


def confusion_matrix(y: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    matrix = np.zeros((N_CLASSES, N_CLASSES), dtype=int)
    for actual, predicted in zip(y, prediction, strict=True):
        matrix[int(actual), int(predicted)] += 1
    return matrix


def macro_f1(y: np.ndarray, prediction: np.ndarray) -> float:
    scores = []
    for label in range(N_CLASSES):
        true_positive = np.sum((y == label) & (prediction == label))
        false_positive = np.sum((y != label) & (prediction == label))
        false_negative = np.sum((y == label) & (prediction != label))
        precision = true_positive / max(true_positive + false_positive, 1)
        recall = true_positive / max(true_positive + false_negative, 1)
        scores.append(2.0 * precision * recall / max(precision + recall, 1e-12))
    return float(np.mean(scores))


def evaluate(
    model: str,
    split_name: str,
    x: np.ndarray,
    y: np.ndarray,
    parameters: np.ndarray,
) -> dict[str, Any]:
    if model == "scar_qnn":
        probabilities = qnn_probabilities(x, parameters)
    elif model == "classical_mlp":
        probabilities = mlp_probabilities(x, parameters)
    else:
        raise ValueError(model)
    prediction = np.argmax(probabilities, axis=1)
    return {
        f"{split_name}_loss": cross_entropy(probabilities, y),
        f"{split_name}_accuracy": accuracy(probabilities, y),
        f"{split_name}_macro_f1": macro_f1(y, prediction),
        f"{split_name}_confusion": confusion_matrix(y, prediction).tolist(),
    }


def train_qnn(
    split: Split,
    seed: int,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    finite_difference: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rng = np.random.default_rng(seed + 10_000)
    parameters = initialize_qnn(rng)
    optimizer = Adam.for_parameters(parameters)
    history: list[dict[str, Any]] = []
    best_parameters = parameters.copy()
    best_validation_loss = float("inf")
    best_epoch = 0
    circuit_evaluations = 0

    start = time.perf_counter()
    for epoch in range(epochs + 1):
        train_probabilities = qnn_probabilities(split.x_train, parameters)
        validation_probabilities = qnn_probabilities(split.x_val, parameters)
        circuit_evaluations += len(split.x_train) + len(split.x_val)
        train_loss = cross_entropy(train_probabilities, split.y_train)
        validation_loss = cross_entropy(validation_probabilities, split.y_val)
        history.append(
            {
                "model": "scar_qnn",
                "seed": seed,
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
                "train_accuracy": accuracy(train_probabilities, split.y_train),
                "validation_accuracy": accuracy(
                    validation_probabilities, split.y_val
                ),
            }
        )
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_parameters = parameters.copy()
            best_epoch = epoch
        if epoch == epochs:
            break
        _, gradient, _, evaluations = qnn_loss_and_gradient(
            split.x_train,
            split.y_train,
            parameters,
            finite_difference,
            weight_decay,
        )
        circuit_evaluations += evaluations
        parameters = optimizer.update(parameters, gradient, learning_rate)
    training_seconds = time.perf_counter() - start

    result: dict[str, Any] = {
        "model": "scar_qnn",
        "seed": seed,
        "parameters": QNN_PARAMETERS,
        "best_epoch": best_epoch,
        "training_seconds": training_seconds,
        "sample_circuit_evaluations": circuit_evaluations,
        "pca_explained": split.pca_explained,
    }
    result.update(
        evaluate(
            "scar_qnn",
            "train",
            split.x_train,
            split.y_train,
            best_parameters,
        )
    )
    result.update(
        evaluate(
            "scar_qnn", "validation", split.x_val, split.y_val, best_parameters
        )
    )
    result.update(
        evaluate("scar_qnn", "test", split.x_test, split.y_test, best_parameters)
    )
    return result, history


def train_mlp(
    split: Split,
    seed: int,
    epochs: int,
    learning_rate: float,
    weight_decay: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rng = np.random.default_rng(seed + 20_000)
    parameters = initialize_mlp(rng)
    optimizer = Adam.for_parameters(parameters)
    history: list[dict[str, Any]] = []
    best_parameters = parameters.copy()
    best_validation_loss = float("inf")
    best_epoch = 0

    start = time.perf_counter()
    for epoch in range(epochs + 1):
        train_probabilities = mlp_probabilities(split.x_train, parameters)
        validation_probabilities = mlp_probabilities(split.x_val, parameters)
        train_loss = cross_entropy(train_probabilities, split.y_train)
        validation_loss = cross_entropy(validation_probabilities, split.y_val)
        history.append(
            {
                "model": "classical_mlp",
                "seed": seed,
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": validation_loss,
                "train_accuracy": accuracy(train_probabilities, split.y_train),
                "validation_accuracy": accuracy(
                    validation_probabilities, split.y_val
                ),
            }
        )
        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_parameters = parameters.copy()
            best_epoch = epoch
        if epoch == epochs:
            break
        _, gradient, _ = mlp_loss_and_gradient(
            split.x_train, split.y_train, parameters, weight_decay
        )
        parameters = optimizer.update(parameters, gradient, learning_rate)
    training_seconds = time.perf_counter() - start

    result: dict[str, Any] = {
        "model": "classical_mlp",
        "seed": seed,
        "parameters": MLP_PARAMETERS,
        "best_epoch": best_epoch,
        "training_seconds": training_seconds,
        "sample_circuit_evaluations": 0,
        "pca_explained": split.pca_explained,
    }
    result.update(
        evaluate(
            "classical_mlp",
            "train",
            split.x_train,
            split.y_train,
            best_parameters,
        )
    )
    result.update(
        evaluate(
            "classical_mlp",
            "validation",
            split.x_val,
            split.y_val,
            best_parameters,
        )
    )
    result.update(
        evaluate(
            "classical_mlp",
            "test",
            split.x_test,
            split.y_test,
            best_parameters,
        )
    )
    return result, history


def numeric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [
        "test_accuracy",
        "test_macro_f1",
        "test_loss",
        "training_seconds",
        "best_epoch",
        "pca_explained",
    ]
    summary: dict[str, Any] = {}
    for model in ["scar_qnn", "classical_mlp"]:
        model_rows = [row for row in rows if row["model"] == model]
        model_summary: dict[str, Any] = {
            "runs": len(model_rows),
            "parameters": int(model_rows[0]["parameters"]),
        }
        for metric in metrics:
            values = np.asarray([row[metric] for row in model_rows], dtype=float)
            model_summary[metric] = {
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                "min": float(values.min()),
                "max": float(values.max()),
            }
        summary[model] = model_summary

    qnn_by_seed = {
        int(row["seed"]): row for row in rows if row["model"] == "scar_qnn"
    }
    mlp_by_seed = {
        int(row["seed"]): row for row in rows if row["model"] == "classical_mlp"
    }
    common_seeds = sorted(set(qnn_by_seed) & set(mlp_by_seed))
    differences = np.asarray(
        [
            qnn_by_seed[seed]["test_accuracy"]
            - mlp_by_seed[seed]["test_accuracy"]
            for seed in common_seeds
        ],
        dtype=float,
    )
    if len(differences) > 1:
        # Student t critical value for n=5; normal approximation otherwise.
        critical = 2.776 if len(differences) == 5 else 1.96
        half_width = critical * differences.std(ddof=1) / math.sqrt(len(differences))
    else:
        half_width = 0.0
    summary["paired_test_accuracy_difference_qnn_minus_mlp"] = {
        "mean": float(differences.mean()),
        "ci95_low": float(differences.mean() - half_width),
        "ci95_high": float(differences.mean() + half_width),
        "qnn_wins": int(np.sum(differences > 0.0)),
        "ties": int(np.sum(np.isclose(differences, 0.0))),
        "mlp_wins": int(np.sum(differences < 0.0)),
        "seeds": common_seeds,
    }
    return summary


def csv_ready(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: json.dumps(value) if isinstance(value, (list, dict)) else value
        for key, value in row.items()
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_ready(row) for row in rows)


def write_report(
    path: Path,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    epochs: int,
    learning_rate_qnn: float,
    learning_rate_mlp: float,
    weight_decay: float,
) -> None:
    qnn = summary["scar_qnn"]
    mlp = summary["classical_mlp"]
    difference = summary["paired_test_accuracy_difference_qnn_minus_mlp"]
    qnn_accuracy = qnn["test_accuracy"]
    mlp_accuracy = mlp["test_accuracy"]
    qnn_f1 = qnn["test_macro_f1"]
    mlp_f1 = mlp["test_macro_f1"]
    qnn_time = qnn["training_seconds"]
    mlp_time = mlp["training_seconds"]

    winner = (
        "SCAR-QNN"
        if qnn_accuracy["mean"] > mlp_accuracy["mean"]
        else "klasyczne MLP"
    )
    lines = [
        "# SCAR-QNN kontra klasyczna sieć neuronowa na zbiorze Wine",
        "",
        "## Wynik",
        "",
        f"Średnio lepszą trafność testową uzyskało **{winner}**. "
        f"SCAR-QNN: `{qnn_accuracy['mean']:.3f} ± {qnn_accuracy['std']:.3f}`, "
        f"MLP: `{mlp_accuracy['mean']:.3f} ± {mlp_accuracy['std']:.3f}`.",
        "",
        f"Parowana różnica trafności `QNN - MLP` wyniosła "
        f"`{difference['mean']:+.3f}` z orientacyjnym 95% CI "
        f"`[{difference['ci95_low']:+.3f}, {difference['ci95_high']:+.3f}]`. "
        f"Bilans seedów: QNN {difference['qnn_wins']} wygranych, "
        f"{difference['ties']} remisów, MLP {difference['mlp_wins']} wygranych.",
        "",
        "## Porównanie",
        "",
        "| Model | Parametry | Test accuracy | Test macro-F1 | Czas treningu [s] |",
        "|---|---:|---:|---:|---:|",
        f"| SCAR-QNN | {qnn['parameters']} | "
        f"{qnn_accuracy['mean']:.3f} ± {qnn_accuracy['std']:.3f} | "
        f"{qnn_f1['mean']:.3f} ± {qnn_f1['std']:.3f} | "
        f"{qnn_time['mean']:.2f} ± {qnn_time['std']:.2f} |",
        f"| MLP 4→5→3 | {mlp['parameters']} | "
        f"{mlp_accuracy['mean']:.3f} ± {mlp_accuracy['std']:.3f} | "
        f"{mlp_f1['mean']:.3f} ± {mlp_f1['std']:.3f} | "
        f"{mlp_time['mean']:.4f} ± {mlp_time['std']:.4f} |",
        "",
        "## Protokół",
        "",
        f"- Dane: pełny UCI Wine, 178 próbek, 13 cech, 3 klasy.",
        f"- Splity: stratyfikowane 60/20/20, osobny split dla każdego z "
        f"{len(difference['seeds'])} sparowanych seedów.",
        f"- Preprocessing: standaryzacja uczona tylko na treningu, PCA 13→4; "
        f"średnio zachowane `{qnn['pca_explained']['mean']:.3f}` wariancji.",
        f"- SCAR-QNN: 4 kubity, 2 warstwy SCAR-ring, 28 parametrów obwodu, "
        f"4 pomiary Z i klasyczna głowica 4→3 (15 parametrów).",
        f"- MLP: warstwy 4→5→3 z aktywacją tanh; dokładnie ten sam budżet "
        f"{MLP_PARAMETERS} parametrów.",
        f"- Optymalizacja: Adam, {epochs} epok, pełny batch, weight decay "
        f"{weight_decay:g}; lr QNN={learning_rate_qnn:g}, lr MLP={learning_rate_mlp:g}.",
        "- W obu modelach raportowany jest checkpoint o najniższej stracie walidacyjnej.",
        "",
        "## Ważne ograniczenia",
        "",
        "- QNN był trenowany na bezszumowym symulatorze statevector. Czas CPU nie "
        "jest estymacją czasu na sprzęcie kwantowym.",
        "- Gradient 28 parametrów obwodu liczono centralną różnicą skończoną. "
        "Na sprzęcie wymagałoby to wielu wykonań obwodu i pomiarów.",
        "- Równa liczba parametrów nie oznacza równego kosztu obliczeniowego ani "
        "identycznej klasy funkcji.",
        "- Wine jest małym i dość łatwym zbiorem. Ten benchmark ocenia użyteczność "
        "ansatzu, ale sam nie może dowieść przewagi kwantowej.",
        "",
        "## Wyniki per seed",
        "",
        "| Seed | Model | Test accuracy | Macro-F1 | Najlepsza epoka | Czas [s] |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in sorted(rows, key=lambda item: (int(item["seed"]), item["model"])):
        lines.append(
            f"| {row['seed']} | {row['model']} | {row['test_accuracy']:.3f} | "
            f"{row['test_macro_f1']:.3f} | {row['best_epoch']} | "
            f"{row['training_seconds']:.4f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_seeds(value: str) -> list[int]:
    seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not seeds:
        raise argparse.ArgumentTypeError("Provide at least one seed")
    return seeds


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark a SCAR-ring QNN against a parameter-matched MLP on Wine."
    )
    parser.add_argument("--seeds", type=parse_seeds, default=parse_seeds("7,21,42,84,168"))
    parser.add_argument("--epochs", type=int, default=160)
    parser.add_argument("--qnn-learning-rate", type=float, default=0.035)
    parser.add_argument("--mlp-learning-rate", type=float, default=0.035)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--finite-difference", type=float, default=1e-4)
    parser.add_argument("--output-stem", default="scar_wine_benchmark")
    args = parser.parse_args()

    if QNN_PARAMETERS != MLP_PARAMETERS:
        raise AssertionError(
            f"Parameter budgets differ: QNN={QNN_PARAMETERS}, MLP={MLP_PARAMETERS}"
        )

    x, y = load_wine()
    rows: list[dict[str, Any]] = []
    histories: list[dict[str, Any]] = []
    for seed in args.seeds:
        split = prepare_split(x, y, seed)
        qnn_result, qnn_history = train_qnn(
            split,
            seed,
            args.epochs,
            args.qnn_learning_rate,
            args.weight_decay,
            args.finite_difference,
        )
        mlp_result, mlp_history = train_mlp(
            split,
            seed,
            args.epochs,
            args.mlp_learning_rate,
            args.weight_decay,
        )
        rows.extend([qnn_result, mlp_result])
        histories.extend(qnn_history)
        histories.extend(mlp_history)
        print(
            f"seed={seed:3d} "
            f"QNN acc={qnn_result['test_accuracy']:.3f} "
            f"MLP acc={mlp_result['test_accuracy']:.3f} "
            f"QNN time={qnn_result['training_seconds']:.2f}s"
        )

    summary = numeric_summary(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    results_path = OUT / f"{args.output_stem}_results.csv"
    history_path = OUT / f"{args.output_stem}_history.csv"
    summary_path = OUT / f"{args.output_stem}_summary.json"
    report_path = OUT / f"{args.output_stem}_report.md"
    write_csv(results_path, rows)
    write_csv(history_path, histories)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_report(
        report_path,
        rows,
        summary,
        args.epochs,
        args.qnn_learning_rate,
        args.mlp_learning_rate,
        args.weight_decay,
    )

    difference = summary["paired_test_accuracy_difference_qnn_minus_mlp"]
    print(
        "QNN - MLP test accuracy: "
        f"{difference['mean']:+.3f} "
        f"[{difference['ci95_low']:+.3f}, {difference['ci95_high']:+.3f}]"
    )
    print(f"Wrote {results_path}")
    print(f"Wrote {history_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
