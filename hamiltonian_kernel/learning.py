from __future__ import annotations

import numpy as np


def class_targets(y: np.ndarray, classes: np.ndarray) -> np.ndarray:
    targets = -np.ones((len(y), len(classes)), dtype=float)
    positions = {int(label): position for position, label in enumerate(classes)}
    for row, label in enumerate(y):
        targets[row, positions[int(label)]] = 1.0
    return targets


def fit_kernel_ridge(k_train: np.ndarray, y_train: np.ndarray, regularization: float) -> tuple[np.ndarray, np.ndarray]:
    classes = np.unique(y_train)
    targets = class_targets(y_train, classes)
    system = np.asarray(k_train, dtype=float) + regularization * np.eye(len(k_train))
    try:
        coefficients = np.linalg.solve(system, targets)
    except np.linalg.LinAlgError:
        coefficients = np.linalg.pinv(system, rcond=1e-10) @ targets
    return coefficients, classes


def predict_kernel_ridge(k_cross: np.ndarray, coefficients: np.ndarray, classes: np.ndarray) -> np.ndarray:
    return classes[np.argmax(np.asarray(k_cross) @ coefficients, axis=1)]


def balanced_accuracy(y_true: np.ndarray, y_pred: np.ndarray, classes: np.ndarray) -> float:
    recalls = [float(np.mean(y_pred[y_true == label] == label)) for label in classes]
    return float(np.mean(recalls))


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, classes: np.ndarray) -> float:
    scores: list[float] = []
    for label in classes:
        true_positive = int(np.sum((y_true == label) & (y_pred == label)))
        false_positive = int(np.sum((y_true != label) & (y_pred == label)))
        false_negative = int(np.sum((y_true == label) & (y_pred != label)))
        precision = true_positive / max(true_positive + false_positive, 1)
        recall = true_positive / max(true_positive + false_negative, 1)
        scores.append(0.0 if precision + recall == 0 else 2.0 * precision * recall / (precision + recall))
    return float(np.mean(scores))


def select_regularization(
    k_train: np.ndarray,
    y_train: np.ndarray,
    k_val: np.ndarray,
    y_val: np.ndarray,
    grid: tuple[float, ...] = (1e-4, 1e-3, 1e-2, 1e-1, 1.0),
) -> tuple[float, float]:
    best_regularization = grid[0]
    best_score = -np.inf
    for regularization in grid:
        coefficients, classes = fit_kernel_ridge(k_train, y_train, regularization)
        prediction = predict_kernel_ridge(k_val, coefficients, classes)
        score = balanced_accuracy(y_val, prediction, classes)
        if score > best_score + 1e-12:
            best_score = score
            best_regularization = regularization
    return best_regularization, float(best_score)


def centered_kernel_alignment(k_train: np.ndarray, y_train: np.ndarray) -> float:
    classes = np.unique(y_train)
    targets = class_targets(y_train, classes)
    target_kernel = targets @ targets.T
    sample_count = len(k_train)
    centering = np.eye(sample_count) - np.ones((sample_count, sample_count)) / sample_count
    kernel_centered = centering @ k_train @ centering
    target_centered = centering @ target_kernel @ centering
    denominator = np.linalg.norm(kernel_centered, "fro") * np.linalg.norm(target_centered, "fro")
    return 0.0 if denominator < 1e-12 else float(np.sum(kernel_centered * target_centered) / denominator)


def kernel_diagnostics(k_train: np.ndarray, regularization: float) -> dict[str, float]:
    symmetric = 0.5 * (np.asarray(k_train, dtype=float) + np.asarray(k_train, dtype=float).T)
    eigenvalues = np.linalg.eigvalsh(symmetric)
    positive = np.clip(eigenvalues, 0.0, None)
    positive_sum = float(positive.sum())
    effective_rank = 0.0
    if positive_sum > 1e-12:
        effective_rank = positive_sum**2 / max(float(np.sum(positive**2)), 1e-12)
    off_diagonal = symmetric[~np.eye(len(symmetric), dtype=bool)]
    regularized = symmetric + regularization * np.eye(len(symmetric))
    return {
        "kernel_effective_rank": float(effective_rank),
        "kernel_min_eigenvalue": float(eigenvalues[0]),
        "kernel_negative_eigenmass": float(np.abs(eigenvalues[eigenvalues < 0]).sum()),
        "kernel_condition_number": float(np.linalg.cond(regularized)),
        "kernel_offdiag_mean": float(np.mean(off_diagonal)),
        "kernel_offdiag_std": float(np.std(off_diagonal)),
    }


def rbf_kernel(left: np.ndarray, right: np.ndarray, gamma: float) -> np.ndarray:
    differences = left[:, None, :] - right[None, :, :]
    squared_distances = np.sum(differences * differences, axis=2)
    return np.exp(-gamma * squared_distances)


def sample_fidelity_kernel(
    probabilities: np.ndarray,
    shots: int,
    rng: np.random.Generator,
    symmetric: bool,
) -> np.ndarray:
    if shots < 1:
        raise ValueError("shots must be positive")
    probabilities = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    if not symmetric:
        return rng.binomial(shots, probabilities) / shots

    if probabilities.shape[0] != probabilities.shape[1]:
        raise ValueError("A symmetric sampled kernel must be square")
    result = np.eye(len(probabilities), dtype=float)
    upper = np.triu_indices(len(probabilities), k=1)
    samples = rng.binomial(shots, probabilities[upper]) / shots
    result[upper] = samples
    result[(upper[1], upper[0])] = samples
    return result


def sample_bloch_vectors(bloch: np.ndarray, shots: int, rng: np.random.Generator) -> np.ndarray:
    if shots < 1:
        raise ValueError("shots must be positive")
    probabilities = np.clip((np.asarray(bloch, dtype=float) + 1.0) / 2.0, 0.0, 1.0)
    plus_counts = rng.binomial(shots, probabilities)
    return 2.0 * plus_counts / shots - 1.0


def nearest_correlation_kernel(kernel: np.ndarray, floor: float = 1e-10) -> np.ndarray:
    """PSD repair used only for independently sampled fidelity Gram matrices."""

    symmetric = 0.5 * (kernel + kernel.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    repaired = (eigenvectors * np.maximum(eigenvalues, floor)) @ eigenvectors.T
    scale = np.sqrt(np.maximum(np.diag(repaired), floor))
    repaired = repaired / scale[:, None] / scale[None, :]
    np.fill_diagonal(repaired, 1.0)
    # Diagonal congruence preserves PSD. Entrywise clipping would not.
    return repaired
