from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .core import fidelity_kernel, z_eigenvalues


@dataclass(frozen=True)
class ResourceCost:
    """Resource axes used by simulator and QPU reports.

    The first three quantities are counts. QPU time and credits remain unknown
    until the provider returns authoritative usage metadata.
    """

    circuit_shots: int
    map_executions: int
    two_qubit_gate_shots: int
    qpu_time_seconds: float | None = None
    qpu_credits: float | None = None

    def as_dict(self) -> dict[str, int | float | str | None]:
        return {
            "circuit_shots": self.circuit_shots,
            "map_executions": self.map_executions,
            "two_qubit_gate_shots": self.two_qubit_gate_shots,
            "qpu_time_seconds": self.qpu_time_seconds,
            "qpu_credits": self.qpu_credits,
            "qpu_cost_status": (
                "provider_reported"
                if self.qpu_time_seconds is not None or self.qpu_credits is not None
                else "not_available_for_simulation"
            ),
        }


@dataclass(frozen=True)
class KernelStages:
    raw: np.ndarray
    psd: np.ndarray
    spectral: np.ndarray
    raw_eigenvalues: np.ndarray
    psd_eigenvalues: np.ndarray
    spectral_eigenvalues: np.ndarray
    spectral_threshold: float


@dataclass(frozen=True)
class FidelityEstimate:
    features: np.ndarray
    raw_landmark_kernel: np.ndarray
    raw_sample_landmark: np.ndarray
    measured_diagonal: np.ndarray
    psd_landmark_kernel: np.ndarray
    spectral_kernel: np.ndarray
    raw_eigenvalues: np.ndarray
    psd_eigenvalues: np.ndarray
    spectral_eigenvalues: np.ndarray
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class ProjectedEstimate:
    bloch: np.ndarray
    basis_probabilities: np.ndarray
    shots_by_setting: np.ndarray
    diagnostics: dict[str, Any]


def resource_cost(
    circuit_shots: int,
    feature_maps_per_shot: int,
    two_qubit_gates_per_map: int,
    *,
    qpu_time_seconds: float | None = None,
    qpu_credits: float | None = None,
) -> ResourceCost:
    if circuit_shots < 0 or feature_maps_per_shot < 0 or two_qubit_gates_per_map < 0:
        raise ValueError("Resource counts cannot be negative")
    map_executions = circuit_shots * feature_maps_per_shot
    return ResourceCost(
        circuit_shots=circuit_shots,
        map_executions=map_executions,
        two_qubit_gate_shots=map_executions * two_qubit_gates_per_map,
        qpu_time_seconds=qpu_time_seconds,
        qpu_credits=qpu_credits,
    )


def kernel_stages(raw_kernel: np.ndarray, relative_threshold: float = 1e-3) -> KernelStages:
    """Return the observed, eigenvalue-clipped, and truncated spectral matrices."""

    raw = np.asarray(raw_kernel, dtype=float)
    if raw.ndim != 2 or raw.shape[0] != raw.shape[1]:
        raise ValueError("Kernel stages require a square matrix")
    if relative_threshold <= 0.0:
        raise ValueError("relative_threshold must be positive")
    raw = 0.5 * (raw + raw.T)
    eigenvalues, eigenvectors = np.linalg.eigh(raw)
    clipped = np.maximum(eigenvalues, 0.0)
    psd = (eigenvectors * clipped) @ eigenvectors.T
    largest = float(np.max(clipped)) if len(clipped) else 0.0
    threshold = max(largest * relative_threshold, 1e-12)
    retained = np.where(clipped > threshold, clipped, 0.0)
    spectral = (eigenvectors * retained) @ eigenvectors.T
    return KernelStages(
        raw=raw,
        psd=0.5 * (psd + psd.T),
        spectral=0.5 * (spectral + spectral.T),
        raw_eigenvalues=eigenvalues,
        psd_eigenvalues=clipped,
        spectral_eigenvalues=retained,
        spectral_threshold=threshold,
    )


def fidelity_estimation_circuit_count(
    total_samples: int,
    n_train: int,
    landmark_count: int,
) -> int:
    """Count overlap settings, including a measured diagonal for every sample."""

    if not 1 <= n_train <= total_samples:
        raise ValueError("Expected 1 <= n_train <= total_samples")
    if landmark_count < 0:
        raise ValueError("landmark_count cannot be negative")
    count = n_train if landmark_count == 0 else min(n_train, landmark_count)
    landmark_upper_with_diagonal = count * (count + 1) // 2
    nonlandmark_count = total_samples - count
    cross_to_landmarks = nonlandmark_count * count
    nonlandmark_diagonal = nonlandmark_count
    return landmark_upper_with_diagonal + cross_to_landmarks + nonlandmark_diagonal


def estimate_fidelity_spectral(
    states: np.ndarray,
    n_train: int,
    landmarks: np.ndarray,
    total_budget: int,
    rng: np.random.Generator,
    relative_threshold: float = 1e-3,
) -> FidelityEstimate:
    """Estimate a shared spectral fidelity map with an explicitly sampled diagonal."""

    states = np.asarray(states, dtype=np.complex128)
    landmarks = np.asarray(landmarks, dtype=int)
    if states.ndim != 2 or not 1 <= n_train <= len(states):
        raise ValueError("Expected a state matrix and 1 <= n_train <= len(states)")
    if landmarks.ndim != 1 or len(landmarks) < 1:
        raise ValueError("At least one one-dimensional landmark index is required")
    if np.any(landmarks < 0) or np.any(landmarks >= n_train):
        raise ValueError("Landmarks must index training states only")
    if len(np.unique(landmarks)) != len(landmarks):
        raise ValueError("Landmark indices must be unique")

    landmark_count = len(landmarks)
    landmark_set = set(int(index) for index in landmarks)
    nonlandmarks = np.asarray(
        [index for index in range(len(states)) if index not in landmark_set],
        dtype=int,
    )
    upper = np.triu_indices(landmark_count, k=0)
    landmark_probabilities = fidelity_kernel(states[landmarks], states[landmarks])[upper]
    cross_probabilities = fidelity_kernel(states[nonlandmarks], states[landmarks]).reshape(-1)
    diagonal_probabilities = np.real(
        np.sum(states[nonlandmarks].conj() * states[nonlandmarks], axis=1)
    ) ** 2
    probabilities = np.concatenate(
        (landmark_probabilities, cross_probabilities, diagonal_probabilities)
    )
    circuit_count = len(probabilities)
    if total_budget < circuit_count:
        raise ValueError(
            f"Budget {total_budget} cannot allocate at least one shot to {circuit_count} circuits"
        )
    base, remainder = divmod(total_budget, circuit_count)
    shots = np.full(circuit_count, base, dtype=np.int64)
    if remainder:
        shots[rng.choice(circuit_count, size=remainder, replace=False)] += 1
    sampled = rng.binomial(shots, np.clip(probabilities, 0.0, 1.0)) / shots

    landmark_end = len(landmark_probabilities)
    cross_end = landmark_end + len(cross_probabilities)
    sampled_landmarks = sampled[:landmark_end]
    sampled_cross = sampled[landmark_end:cross_end]
    sampled_nonlandmark_diagonal = sampled[cross_end:]

    w_matrix = np.zeros((landmark_count, landmark_count), dtype=float)
    w_matrix[upper] = sampled_landmarks
    w_matrix[(upper[1], upper[0])] = sampled_landmarks
    c_matrix = np.empty((len(states), landmark_count), dtype=float)
    c_matrix[landmarks] = w_matrix
    c_matrix[nonlandmarks] = sampled_cross.reshape(len(nonlandmarks), landmark_count)
    measured_diagonal = np.empty(len(states), dtype=float)
    measured_diagonal[landmarks] = np.diag(w_matrix)
    measured_diagonal[nonlandmarks] = sampled_nonlandmark_diagonal

    stages = kernel_stages(w_matrix, relative_threshold=relative_threshold)
    keep = stages.spectral_eigenvalues > 0.0
    if not np.any(keep):
        raise RuntimeError("No positive fidelity directions survived spectral truncation")
    eigenvalues, eigenvectors = np.linalg.eigh(stages.raw)
    transform = eigenvectors[:, keep] / np.sqrt(eigenvalues[keep])[None, :]
    features = c_matrix @ transform
    feature_norms = np.linalg.norm(features, axis=1)
    valid = feature_norms > 1e-12
    features[valid] *= (
        np.sqrt(np.maximum(measured_diagonal[valid], 0.0)) / feature_norms[valid]
    )[:, None]
    features[~valid] = 0.0
    spectral_kernel = features @ features.T
    diagnostics = {
        "estimator": (
            "measured_diagonal_full_train_spectral_fidelity"
            if landmark_count == n_train
            else "measured_diagonal_nystrom_fidelity"
        ),
        "circuit_count": circuit_count,
        "diagonal_circuit_count": len(states),
        "diagonal_measured": True,
        "total_budget": total_budget,
        "shots_per_circuit_min": int(shots.min()),
        "shots_per_circuit_max": int(shots.max()),
        "landmark_count": landmark_count,
        "nystrom_rank": int(np.sum(keep)),
        "landmark_negative_eigenmass": float(
            np.abs(stages.raw_eigenvalues[stages.raw_eigenvalues < 0.0]).sum()
        ),
        "spectral_threshold": stages.spectral_threshold,
        "raw_min_eigenvalue": float(stages.raw_eigenvalues[0]),
        "psd_min_eigenvalue": float(stages.psd_eigenvalues[0]),
        "spectral_rank": int(np.count_nonzero(stages.spectral_eigenvalues)),
    }
    return FidelityEstimate(
        features=features,
        raw_landmark_kernel=w_matrix,
        raw_sample_landmark=c_matrix,
        measured_diagonal=measured_diagonal,
        psd_landmark_kernel=stages.psd,
        spectral_kernel=spectral_kernel,
        raw_eigenvalues=stages.raw_eigenvalues,
        psd_eigenvalues=stages.psd_eigenvalues,
        spectral_eigenvalues=stages.spectral_eigenvalues,
        diagnostics=diagnostics,
    )


def _apply_local_matrix(
    states: np.ndarray,
    matrix: np.ndarray,
    qubit: int,
) -> np.ndarray:
    result = np.asarray(states, dtype=np.complex128).copy()
    stride = 1 << qubit
    block = stride << 1
    for start in range(0, result.shape[1], block):
        zero = result[:, start : start + stride].copy()
        one = result[:, start + stride : start + block].copy()
        result[:, start : start + stride] = matrix[0, 0] * zero + matrix[0, 1] * one
        result[:, start + stride : start + block] = matrix[1, 0] * zero + matrix[1, 1] * one
    return result


def projected_basis_probabilities(states: np.ndarray, n_qubits: int) -> np.ndarray:
    """Joint bitstring probabilities for all-qubit X, Y, and Z settings."""

    values = np.atleast_2d(np.asarray(states, dtype=np.complex128))
    if values.shape[1] != 2**n_qubits:
        raise ValueError(f"Expected state dimension {2**n_qubits}, got {values.shape[1]}")
    hadamard = np.asarray([[1.0, 1.0], [1.0, -1.0]], dtype=np.complex128) / np.sqrt(2.0)
    y_to_z = hadamard @ np.diag(np.asarray([1.0, -1.0j]))
    rotations = (hadamard, y_to_z, np.eye(2, dtype=np.complex128))
    probabilities = np.empty((len(values), 3, values.shape[1]), dtype=float)
    for basis, rotation in enumerate(rotations):
        rotated = values
        for qubit in range(n_qubits):
            rotated = _apply_local_matrix(rotated, rotation, qubit)
        basis_probabilities = np.abs(rotated) ** 2
        probabilities[:, basis, :] = basis_probabilities / basis_probabilities.sum(
            axis=1, keepdims=True
        )
    return probabilities


def estimate_projected_bloch(
    states: np.ndarray,
    n_qubits: int,
    total_budget: int,
    rng: np.random.Generator,
) -> ProjectedEstimate:
    """Sample joint bitstrings and derive all local Bloch components per shot."""

    probabilities = projected_basis_probabilities(states, n_qubits)
    sample_count = len(probabilities)
    circuit_count = sample_count * 3
    if total_budget < circuit_count:
        raise ValueError(
            f"Budget {total_budget} cannot allocate at least one shot to {circuit_count} circuits"
        )
    base, remainder = divmod(total_budget, circuit_count)
    shots = np.full(circuit_count, base, dtype=np.int64)
    if remainder:
        shots[rng.choice(circuit_count, size=remainder, replace=False)] += 1
    shots_by_setting = shots.reshape(sample_count, 3)
    z_values = z_eigenvalues(n_qubits)
    estimated = np.empty((sample_count, n_qubits, 3), dtype=float)
    for sample in range(sample_count):
        for basis in range(3):
            counts = rng.multinomial(
                int(shots_by_setting[sample, basis]), probabilities[sample, basis]
            )
            estimated[sample, :, basis] = (
                counts @ z_values / shots_by_setting[sample, basis]
            )
    diagnostics = {
        "estimator": "joint_bitstring_local_bloch_projected",
        "joint_bitstring_sampling": True,
        "circuit_count": circuit_count,
        "total_budget": total_budget,
        "shots_per_circuit_min": int(shots.min()),
        "shots_per_circuit_max": int(shots.max()),
        "landmark_count": 0,
        "nystrom_rank": 0,
        "landmark_negative_eigenmass": 0.0,
    }
    return ProjectedEstimate(
        bloch=estimated,
        basis_probabilities=probabilities,
        shots_by_setting=shots_by_setting,
        diagnostics=diagnostics,
    )
