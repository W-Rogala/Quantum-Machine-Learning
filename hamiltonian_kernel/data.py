from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "datasets" / "qml_benchmarks"


@dataclass(frozen=True)
class Dataset:
    name: str
    x: np.ndarray
    y: np.ndarray


@dataclass(frozen=True)
class PreparedData:
    name: str
    x_train: np.ndarray
    x_val: np.ndarray
    x_test: np.ndarray
    y_train: np.ndarray
    y_val: np.ndarray
    y_test: np.ndarray
    pca_explained_ratio: float


def load_wdbc() -> Dataset:
    path = DATA_ROOT / "breast_cancer_wisconsin_diagnostic" / "wdbc.data"
    x_rows: list[list[float]] = []
    y_rows: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if row:
                y_rows.append(1 if row[1] == "M" else 0)
                x_rows.append([float(value) for value in row[2:]])
    return Dataset("wdbc", np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int))


def load_wine() -> Dataset:
    path = DATA_ROOT / "wine" / "wine.data"
    x_rows: list[list[float]] = []
    y_rows: list[int] = []
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if row:
                y_rows.append(int(row[0]) - 1)
                x_rows.append([float(value) for value in row[1:]])
    return Dataset("wine", np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=int))


def make_moons(n_samples: int = 240, noise: float = 0.12, seed: int = 0) -> Dataset:
    if n_samples < 4:
        raise ValueError("n_samples must be at least 4")
    rng = np.random.default_rng(seed)
    first_count = n_samples // 2
    second_count = n_samples - first_count
    first_angle = rng.uniform(0.0, np.pi, first_count)
    second_angle = rng.uniform(0.0, np.pi, second_count)
    first = np.column_stack((np.cos(first_angle), np.sin(first_angle)))
    second = np.column_stack((1.0 - np.cos(second_angle), 0.5 - np.sin(second_angle)))
    x = np.vstack((first, second)) + rng.normal(0.0, noise, size=(n_samples, 2))
    y = np.concatenate((np.zeros(first_count, dtype=int), np.ones(second_count, dtype=int)))
    order = rng.permutation(n_samples)
    return Dataset("moons", x[order], y[order])


def load_dataset(name: str, seed: int = 0, smoke: bool = False) -> Dataset:
    if name == "moons":
        # Keep the generated dataset fixed; repeated seeds vary only the split.
        return make_moons(n_samples=120 if smoke else 240, seed=20_260)
    if name == "wdbc":
        dataset = load_wdbc()
    elif name == "wine":
        dataset = load_wine()
    else:
        raise ValueError(f"Unknown dataset: {name}")

    if smoke:
        per_class = 30
        rng = np.random.default_rng(20_000 + seed)
        selected: list[int] = []
        for label in np.unique(dataset.y):
            indices = np.flatnonzero(dataset.y == label)
            rng.shuffle(indices)
            selected.extend(indices[:per_class])
        selected_array = np.asarray(selected, dtype=int)
        rng.shuffle(selected_array)
        return Dataset(dataset.name, dataset.x[selected_array], dataset.y[selected_array])
    return dataset


def stratified_split(
    y: np.ndarray,
    seed: int,
    train_fraction: float = 0.6,
    val_fraction: float = 0.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train: list[int] = []
    validation: list[int] = []
    test: list[int] = []
    for label in np.unique(y):
        indices = np.flatnonzero(y == label)
        rng.shuffle(indices)
        n_train = max(1, int(round(train_fraction * len(indices))))
        n_val = max(1, int(round(val_fraction * len(indices))))
        if n_train + n_val >= len(indices):
            n_val = max(1, len(indices) - n_train - 1)
        train.extend(indices[:n_train])
        validation.extend(indices[n_train : n_train + n_val])
        test.extend(indices[n_train + n_val :])
    rng.shuffle(train)
    rng.shuffle(validation)
    rng.shuffle(test)
    return np.asarray(train), np.asarray(validation), np.asarray(test)


def prepare_dataset(dataset: Dataset, n_components: int, seed: int) -> PreparedData:
    train_idx, val_idx, test_idx = stratified_split(dataset.y, seed)
    x_train = np.asarray(dataset.x[train_idx], dtype=float)
    x_val = np.asarray(dataset.x[val_idx], dtype=float)
    x_test = np.asarray(dataset.x[test_idx], dtype=float)

    mean = x_train.mean(axis=0)
    standard_deviation = x_train.std(axis=0)
    standard_deviation[standard_deviation < 1e-12] = 1.0
    x_train = (x_train - mean) / standard_deviation
    x_val = (x_val - mean) / standard_deviation
    x_test = (x_test - mean) / standard_deviation

    component_count = min(n_components, x_train.shape[0], x_train.shape[1])
    _, singular_values, right_vectors = np.linalg.svd(x_train, full_matrices=False)
    components = right_vectors[:component_count]
    x_train = x_train @ components.T
    x_val = x_val @ components.T
    x_test = x_test @ components.T
    explained_variance = singular_values**2
    explained_ratio = float(explained_variance[:component_count].sum() / explained_variance.sum())

    minimum = x_train.min(axis=0)
    width = x_train.max(axis=0) - minimum
    width[width < 1e-12] = 1.0

    def scale(values: np.ndarray) -> np.ndarray:
        return np.clip(2.0 * (values - minimum) / width - 1.0, -1.0, 1.0)

    x_train = scale(x_train)
    x_val = scale(x_val)
    x_test = scale(x_test)

    if component_count < n_components:
        padding = n_components - component_count
        x_train = np.pad(x_train, ((0, 0), (0, padding)))
        x_val = np.pad(x_val, ((0, 0), (0, padding)))
        x_test = np.pad(x_test, ((0, 0), (0, padding)))

    return PreparedData(
        name=dataset.name,
        x_train=x_train,
        x_val=x_val,
        x_test=x_test,
        y_train=dataset.y[train_idx],
        y_val=dataset.y[val_idx],
        y_test=dataset.y[test_idx],
        pca_explained_ratio=explained_ratio,
    )
