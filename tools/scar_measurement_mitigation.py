from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def assignment_matrix(p00: float, p11: float) -> np.ndarray:
    """Return P(measured | prepared) with measured states in rows."""
    if not 0.0 <= p00 <= 1.0 or not 0.0 <= p11 <= 1.0:
        raise ValueError("Assignment fidelities must be probabilities")
    return np.asarray(
        [
            [p00, 1.0 - p11],
            [1.0 - p00, p11],
        ],
        dtype=float,
    )


def symmetric_assignment_matrix(readout_fidelity: float) -> np.ndarray:
    return assignment_matrix(readout_fidelity, readout_fidelity)


def regularized_inverse(matrix: np.ndarray, regularization: float) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)
    gram = matrix.T @ matrix
    return np.linalg.solve(
        gram + regularization * np.eye(matrix.shape[1]),
        matrix.T,
    )


class MeasurementResponse:
    """Simulate assignment error and optionally invert its calibration matrix."""

    def __init__(
        self,
        matrices: np.ndarray,
        labels: Sequence[str],
        regularization: float = 1e-6,
        calibration_note: str = "",
    ) -> None:
        matrices = np.asarray(matrices, dtype=float)
        if matrices.ndim == 2:
            matrices = matrices[None, :, :]
        if matrices.shape[1:] != (2, 2):
            raise ValueError(f"Expected (features, 2, 2), got {matrices.shape}")
        if len(labels) != len(matrices):
            raise ValueError("Each assignment matrix needs one feature label")
        if np.max(np.abs(matrices.sum(axis=1) - 1.0)) > 1e-12:
            raise ValueError("Assignment-matrix columns must sum to one")

        self.matrices = matrices
        self.labels = list(labels)
        self.regularization = float(regularization)
        self.inverses = np.asarray(
            [regularized_inverse(matrix, regularization) for matrix in matrices]
        )
        self.condition_numbers = np.asarray(
            [np.linalg.cond(matrix) for matrix in matrices],
            dtype=float,
        )
        self.calibration_note = calibration_note
        self.calls = 0
        self.total_values = 0
        self.corrected_values = 0
        self.projected_values = 0

    def apply(
        self,
        expectations: np.ndarray,
        shots: int,
        seed: int,
        *,
        mitigate: bool,
        shot_scale: float = 1.0,
    ) -> np.ndarray:
        expectations = np.asarray(expectations, dtype=float)
        if expectations.ndim != 2 or expectations.shape[1] != len(self.matrices):
            raise ValueError(
                f"Expected (samples, {len(self.matrices)}) expectations, "
                f"got {expectations.shape}"
            )
        latent = np.clip(expectations, -1.0, 1.0)
        true_probabilities = np.stack(
            [(1.0 + latent) / 2.0, (1.0 - latent) / 2.0],
            axis=-1,
        )
        measured_probabilities = np.einsum(
            "fij,sfj->sfi",
            self.matrices,
            true_probabilities,
            optimize=True,
        )

        effective_shots = max(int(round(shots * shot_scale)), 4)
        rng = np.random.default_rng(seed)
        measured_zero = rng.binomial(
            effective_shots,
            np.clip(measured_probabilities[..., 0], 0.0, 1.0),
        ) / effective_shots
        sampled = np.stack([measured_zero, 1.0 - measured_zero], axis=-1)

        self.calls += 1
        self.total_values += int(expectations.size)
        if not mitigate:
            return sampled[..., 0] - sampled[..., 1]

        corrected = np.einsum(
            "fij,sfj->sfi",
            self.inverses,
            sampled,
            optimize=True,
        )
        outside_simplex = np.any(
            (corrected < 0.0) | (corrected > 1.0),
            axis=-1,
        )
        self.corrected_values += int(expectations.size)
        self.projected_values += int(np.count_nonzero(outside_simplex))

        # The inverse can leave the probability simplex under finite-shot noise.
        corrected = np.clip(corrected, 0.0, 1.0)
        normalizer = corrected.sum(axis=-1, keepdims=True)
        corrected = np.divide(
            corrected,
            normalizer,
            out=np.full_like(corrected, 0.5),
            where=normalizer > 0.0,
        )
        return corrected[..., 0] - corrected[..., 1]

    def metadata(self) -> dict[str, Any]:
        projection_rate = (
            self.projected_values / self.corrected_values
            if self.corrected_values
            else 0.0
        )
        return {
            "orientation": "rows=measured outcomes, columns=prepared outcomes",
            "feature_labels": self.labels,
            "assignment_matrices": self.matrices.tolist(),
            "regularized_inverses": self.inverses.tolist(),
            "regularization": self.regularization,
            "condition_numbers": self.condition_numbers.tolist(),
            "max_condition_number": float(np.max(self.condition_numbers)),
            "simplex_projection": "clip negative probabilities and renormalize",
            "projection_rate": projection_rate,
            "calls": self.calls,
            "sampled_feature_values": self.total_values,
            "corrected_feature_values": self.corrected_values,
            "calibration_note": self.calibration_note,
        }
