from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

import numpy as np

from .core import (
    DetectorConfig,
    apply_detector_model,
    apply_uniform_loss,
    event_orbit_features,
    features_from_records,
    hellinger_kernel,
    moment_kernel,
    sample_record_from_array,
)


@dataclass(frozen=True)
class RobustnessScenario:
    max_total_photons: int
    transmissivity: float
    detector: DetectorConfig

    def validate(self) -> None:
        if self.max_total_photons < 0:
            raise ValueError("max_total_photons cannot be negative")
        if not 0.0 <= self.transmissivity <= 1.0:
            raise ValueError("transmissivity must be in [0, 1]")
        self.detector.validate()


@dataclass(frozen=True)
class RobustnessFeatures:
    hellinger: np.ndarray
    moments: np.ndarray
    event: np.ndarray
    orbit: np.ndarray
    acceptance: np.ndarray
    records: tuple[dict[str, Any], ...]
    scenario: RobustnessScenario


def process_sample_batches(
    raw_sample_batches: Iterable[np.ndarray],
    scenario: RobustnessScenario,
    seed: int,
) -> RobustnessFeatures:
    """Apply loss/detection once, then derive all feature families from shared events."""

    scenario.validate()
    rng = np.random.default_rng(seed)
    records: list[dict[str, Any]] = []
    for samples in raw_sample_batches:
        after_channel = apply_uniform_loss(samples, scenario.transmissivity, rng)
        detected = apply_detector_model(after_channel, scenario.detector, rng)
        records.append(
            sample_record_from_array(detected, scenario.max_total_photons)
        )
    if not records:
        raise ValueError("At least one raw sample batch is required")
    hellinger, moments, acceptance = features_from_records(
        records,
        scenario.max_total_photons,
        include_overflow=True,
    )
    grouped = event_orbit_features(records, scenario.max_total_photons)
    return RobustnessFeatures(
        hellinger=hellinger,
        moments=moments,
        event=np.sqrt(grouped.event),
        orbit=np.sqrt(grouped.orbit),
        acceptance=acceptance,
        records=tuple(records),
        scenario=scenario,
    )


def robustness_kernel_matrices(
    features: RobustnessFeatures,
    moment_gamma: float = 0.1,
) -> dict[str, np.ndarray]:
    return {
        "pattern_hellinger": hellinger_kernel(features.hellinger, features.hellinger),
        "moment_rbf": moment_kernel(features.moments, features.moments, moment_gamma),
        "event_hellinger": hellinger_kernel(features.event, features.event),
        "orbit_hellinger": hellinger_kernel(features.orbit, features.orbit),
    }


def cutoff_loss_detector_sweep(
    raw_sample_batches: Iterable[np.ndarray],
    cutoffs: Iterable[int],
    transmissivities: Iterable[float],
    detectors: Iterable[DetectorConfig],
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]]]:
    """Run a factorial robustness sweep without resampling the underlying GBS events."""

    batches = tuple(np.asarray(batch) for batch in raw_sample_batches)
    rows: list[dict[str, Any]] = []
    matrices: dict[str, dict[str, np.ndarray]] = {}
    cutoff_values = tuple(int(value) for value in cutoffs)
    transmissivity_values = tuple(float(value) for value in transmissivities)
    detector_values = tuple(detectors)
    for transmissivity_index, transmissivity in enumerate(transmissivity_values):
        for detector_index, detector in enumerate(detector_values):
            paired_seed = seed + transmissivity_index * 10_007 + detector_index * 1_009
            for cutoff in cutoff_values:
                scenario = RobustnessScenario(int(cutoff), float(transmissivity), detector)
                features = process_sample_batches(
                    batches,
                    scenario,
                    paired_seed,
                )
                scenario_id = (
                    f"cutoff{cutoff}_eta{float(transmissivity):g}_"
                    f"{detector.model}_qe{detector.quantum_efficiency:g}_"
                    f"dark{detector.dark_count_mean:g}_sat{detector.saturation_count}"
                )
                scenario_matrices = robustness_kernel_matrices(features)
                matrices[scenario_id] = scenario_matrices
                rows.append(
                    {
                        "scenario_id": scenario_id,
                        "max_total_photons": int(cutoff),
                        "transmissivity": float(transmissivity),
                        "detector": asdict(detector),
                        "sample_batches": len(batches),
                        "raw_shots": int(sum(int(record["shots"]) for record in features.records)),
                        "acceptance_rate_mean": float(np.mean(features.acceptance)),
                        "acceptance_rate_min": float(np.min(features.acceptance)),
                        "overflow_rate_mean": float(np.mean(1.0 - features.acceptance)),
                        "pattern_feature_dimension": int(features.hellinger.shape[1]),
                        "event_feature_dimension": int(features.event.shape[1]),
                        "orbit_feature_dimension": int(features.orbit.shape[1]),
                        "kernels_psd": all(
                            float(np.linalg.eigvalsh(0.5 * (matrix + matrix.T))[0]) >= -1e-10
                            for matrix in scenario_matrices.values()
                        ),
                    }
                )
    if not rows:
        raise ValueError("The robustness sweep is empty")
    return rows, matrices
