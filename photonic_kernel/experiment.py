from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from hamiltonian_kernel.data import PreparedData, load_dataset, prepare_dataset
from hamiltonian_kernel.learning import (
    balanced_accuracy,
    centered_kernel_alignment,
    fit_kernel_ridge,
    kernel_diagnostics,
    macro_f1,
    predict_kernel_ridge,
    rbf_kernel,
    select_regularization,
)

from .core import (
    GBSDistribution,
    X8GBSConfig,
    allocate_exact_shots,
    config_to_dict,
    event_orbit_features,
    features_from_records,
    gbs_distribution,
    hellinger_kernel,
    ideal_features,
    ideal_event_orbit_features,
    moment_kernel,
    sample_distribution,
    standardize_moments,
    x8_interferometer,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "analysis_output"
MOMENT_GAMMA_GRID = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3)
CLASSICAL_GAMMA_GRID = (0.03, 0.1, 0.3, 1.0, 3.0)
REGULARIZATION_GRID = (1e-4, 1e-3, 1e-2, 1e-1, 1.0)


@dataclass(frozen=True)
class PhotonicCandidate:
    squeezing: float
    phase_scale: float

    @property
    def name(self) -> str:
        return f"r{self.squeezing:g}_alpha{self.phase_scale:g}"

    def config(self, reservoir_seed: int, max_total_photons: int) -> X8GBSConfig:
        return X8GBSConfig(
            squeezing=(self.squeezing,) * 4,
            phase_scale=self.phase_scale,
            reservoir_seed=reservoir_seed,
            max_total_photons=max_total_photons,
        )


@dataclass(frozen=True)
class KernelSelection:
    gamma: float | None
    regularization: float
    train_alignment: float
    validation_balanced_accuracy: float


@dataclass(frozen=True)
class SelectionResult:
    candidate: PhotonicCandidate
    hellinger: KernelSelection
    moment_rbf: KernelSelection
    event_hellinger: KernelSelection
    orbit_hellinger: KernelSelection
    screening_rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Profile:
    max_total_photons: int
    train_per_class: int
    validation_per_class: int
    test_per_class: int
    budget: int


PROFILES = {
    "smoke": Profile(4, 6, 3, 3, 18_000),
    "full": Profile(6, 12, 6, 6, 180_000),
}


def candidate_grid(profile: str) -> list[PhotonicCandidate]:
    if profile == "smoke":
        squeezing_values = (0.35, 0.55)
        phase_scales = (0.6, 1.2)
    elif profile == "full":
        squeezing_values = (0.35, 0.55, 0.75)
        phase_scales = (0.5, 1.0, 1.5)
    else:
        raise ValueError(f"Unknown profile: {profile}")
    return [
        PhotonicCandidate(squeezing, phase_scale)
        for squeezing in squeezing_values
        for phase_scale in phase_scales
    ]


def balanced_subset_indices(y: np.ndarray, per_class: int, seed: int) -> np.ndarray:
    if per_class < 1:
        raise ValueError("per_class must be positive")
    rng = np.random.default_rng(seed)
    selected: list[int] = []
    for label in np.unique(y):
        indices = np.flatnonzero(y == label)
        if len(indices) < per_class:
            raise ValueError(
                f"Class {label} has {len(indices)} samples, requested {per_class}"
            )
        selected.extend(rng.permutation(indices)[:per_class].tolist())
    values = np.asarray(selected, dtype=int)
    return values[rng.permutation(len(values))]


def select_gamma(
    train_features: np.ndarray,
    y_train: np.ndarray,
    gamma_grid: Iterable[float],
    kernel_builder: Any,
) -> tuple[float, float]:
    best_gamma: float | None = None
    best_alignment = -np.inf
    for gamma in gamma_grid:
        kernel = kernel_builder(train_features, train_features, float(gamma))
        alignment = centered_kernel_alignment(kernel, y_train)
        if alignment > best_alignment + 1e-12:
            best_gamma = float(gamma)
            best_alignment = alignment
    if best_gamma is None:
        raise RuntimeError("Gamma grid is empty")
    return best_gamma, float(best_alignment)


def _distributions(
    values: np.ndarray,
    config: X8GBSConfig,
) -> list[GBSDistribution]:
    return [gbs_distribution(row, config) for row in np.asarray(values, dtype=float)]


def _selection_for_candidate(
    candidate: PhotonicCandidate,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_validation: np.ndarray,
    y_validation: np.ndarray,
    reservoir_seed: int,
    max_total_photons: int,
) -> tuple[KernelSelection, KernelSelection, KernelSelection, KernelSelection, dict[str, Any]]:
    config = candidate.config(reservoir_seed, max_total_photons)
    train_count = len(x_train)
    distributions = _distributions(np.vstack((x_train, x_validation)), config)
    hellinger, moments, acceptance = ideal_features(distributions)
    grouped = ideal_event_orbit_features(distributions)
    h_train = hellinger[:train_count]
    h_validation = hellinger[train_count:]
    m_train, m_validation = standardize_moments(
        moments[:train_count],
        moments[train_count:],
    )

    h_train_kernel = hellinger_kernel(h_train, h_train)
    h_validation_kernel = hellinger_kernel(h_validation, h_train)
    h_alignment = centered_kernel_alignment(h_train_kernel, y_train)
    h_regularization, h_validation_score = select_regularization(
        h_train_kernel,
        y_train,
        h_validation_kernel,
        y_validation,
        REGULARIZATION_GRID,
    )
    hellinger_selection = KernelSelection(
        gamma=None,
        regularization=h_regularization,
        train_alignment=h_alignment,
        validation_balanced_accuracy=h_validation_score,
    )

    moment_gamma, moment_alignment = select_gamma(
        m_train,
        y_train,
        MOMENT_GAMMA_GRID,
        moment_kernel,
    )
    moment_train_kernel = moment_kernel(m_train, m_train, moment_gamma)
    moment_validation_kernel = moment_kernel(m_validation, m_train, moment_gamma)
    moment_regularization, moment_validation_score = select_regularization(
        moment_train_kernel,
        y_train,
        moment_validation_kernel,
        y_validation,
        REGULARIZATION_GRID,
    )
    moment_selection = KernelSelection(
        gamma=moment_gamma,
        regularization=moment_regularization,
        train_alignment=moment_alignment,
        validation_balanced_accuracy=moment_validation_score,
    )

    grouped_selections: list[KernelSelection] = []
    grouped_metrics: list[tuple[float, float, float]] = []
    for values in (np.sqrt(grouped.event), np.sqrt(grouped.orbit)):
        train_values = values[:train_count]
        validation_values = values[train_count:]
        train_kernel = hellinger_kernel(train_values, train_values)
        validation_kernel = hellinger_kernel(validation_values, train_values)
        alignment = centered_kernel_alignment(train_kernel, y_train)
        regularization, validation_score = select_regularization(
            train_kernel,
            y_train,
            validation_kernel,
            y_validation,
            REGULARIZATION_GRID,
        )
        grouped_selections.append(
            KernelSelection(None, regularization, alignment, validation_score)
        )
        grouped_metrics.append((alignment, validation_score, regularization))
    event_selection, orbit_selection = grouped_selections
    event_metrics, orbit_metrics = grouped_metrics
    validation_scores = (
        h_validation_score,
        moment_validation_score,
        event_metrics[1],
        orbit_metrics[1],
    )
    alignments = (h_alignment, moment_alignment, event_metrics[0], orbit_metrics[0])
    row = {
        "candidate": candidate.name,
        "squeezing": candidate.squeezing,
        "phase_scale": candidate.phase_scale,
        "max_total_photons": max_total_photons,
        "hellinger_train_alignment": h_alignment,
        "hellinger_validation_balanced_accuracy": h_validation_score,
        "hellinger_regularization": h_regularization,
        "moment_train_alignment": moment_alignment,
        "moment_validation_balanced_accuracy": moment_validation_score,
        "moment_gamma": moment_gamma,
        "moment_regularization": moment_regularization,
        "event_train_alignment": event_metrics[0],
        "event_validation_balanced_accuracy": event_metrics[1],
        "event_regularization": event_metrics[2],
        "orbit_train_alignment": orbit_metrics[0],
        "orbit_validation_balanced_accuracy": orbit_metrics[1],
        "orbit_regularization": orbit_metrics[2],
        "joint_validation_score": float(np.mean(validation_scores)),
        "joint_train_alignment": float(np.mean(alignments)),
        "acceptance_probability_mean": float(np.mean(acceptance)),
        "acceptance_probability_min": float(np.min(acceptance)),
    }
    return hellinger_selection, moment_selection, event_selection, orbit_selection, row


def select_photonic_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_validation: np.ndarray,
    y_validation: np.ndarray,
    candidates: list[PhotonicCandidate],
    reservoir_seed: int,
    max_total_photons: int,
) -> SelectionResult:
    """Select a shared optical map without accepting any test data."""

    if not candidates:
        raise ValueError("At least one photonic candidate is required")
    results: list[
        tuple[
            PhotonicCandidate,
            KernelSelection,
            KernelSelection,
            KernelSelection,
            KernelSelection,
            dict[str, Any],
        ]
    ] = []
    for candidate in candidates:
        hellinger, moment_rbf, event_hellinger, orbit_hellinger, row = _selection_for_candidate(
            candidate,
            x_train,
            y_train,
            x_validation,
            y_validation,
            reservoir_seed,
            max_total_photons,
        )
        results.append(
            (candidate, hellinger, moment_rbf, event_hellinger, orbit_hellinger, row)
        )

    selected = max(
        results,
        key=lambda item: (
            float(item[5]["joint_validation_score"]),
            float(item[5]["joint_train_alignment"]),
            -item[0].squeezing,
            -item[0].phase_scale,
        ),
    )
    return SelectionResult(
        candidate=selected[0],
        hellinger=selected[1],
        moment_rbf=selected[2],
        event_hellinger=selected[3],
        orbit_hellinger=selected[4],
        screening_rows=tuple(item[5] for item in results),
    )


def _prediction_metrics(
    train_kernel: np.ndarray,
    y_train: np.ndarray,
    cross_kernel: np.ndarray,
    y_evaluation: np.ndarray,
    regularization: float,
) -> dict[str, float]:
    coefficients, classes = fit_kernel_ridge(
        train_kernel,
        y_train,
        regularization,
    )
    prediction = predict_kernel_ridge(cross_kernel, coefficients, classes)
    return {
        "balanced_accuracy": balanced_accuracy(y_evaluation, prediction, classes),
        "macro_f1": macro_f1(y_evaluation, prediction, classes),
    }


def _relative_frobenius(observed: np.ndarray, reference: np.ndarray) -> float:
    return float(
        np.linalg.norm(observed - reference, "fro")
        / max(float(np.linalg.norm(reference, "fro")), 1e-12)
    )


def _select_classical_baseline(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_validation: np.ndarray,
    y_validation: np.ndarray,
) -> KernelSelection:
    gamma, alignment = select_gamma(
        x_train,
        y_train,
        CLASSICAL_GAMMA_GRID,
        rbf_kernel,
    )
    train_kernel = rbf_kernel(x_train, x_train, gamma)
    validation_kernel = rbf_kernel(x_validation, x_train, gamma)
    regularization, score = select_regularization(
        train_kernel,
        y_train,
        validation_kernel,
        y_validation,
        REGULARIZATION_GRID,
    )
    return KernelSelection(gamma, regularization, alignment, score)


def _complex_matrix_payload(matrix: np.ndarray) -> dict[str, list[list[float]]]:
    return {
        "real": np.asarray(matrix.real, dtype=float).tolist(),
        "imag": np.asarray(matrix.imag, dtype=float).tolist(),
    }


def workload_identifier(payload: dict[str, Any]) -> str:
    excluded = {"workload_id", "created_utc", "environment"}
    canonical_payload = {
        key: value for key, value in payload.items() if key not in excluded
    }
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def build_workload(
    data: PreparedData,
    train_indices: np.ndarray,
    test_indices: np.ndarray,
    selection: SelectionResult,
    config: X8GBSConfig,
    budget: int,
    dataset_seed: int,
    sample_seed: int,
    measurement_seed: int,
    profile: str,
) -> dict[str, Any]:
    train_x = data.x_train[train_indices]
    train_y = data.y_train[train_indices]
    test_x = data.x_test[test_indices]
    test_y = data.y_test[test_indices]
    all_x = np.vstack((train_x, test_x))
    allocation = allocate_exact_shots(budget, len(all_x), measurement_seed)
    entries: list[dict[str, Any]] = []
    for index, (x, shots) in enumerate(zip(all_x, allocation)):
        split = "train" if index < len(train_x) else "test"
        split_index = index if split == "train" else index - len(train_x)
        entries.append(
            {
                "circuit_id": f"x8_{split}_{split_index:04d}",
                "split": split,
                "sample_index": split_index,
                "shots": int(shots),
                "x": np.asarray(x, dtype=float).tolist(),
                "interferometer": _complex_matrix_payload(
                    x8_interferometer(x, config)
                ),
            }
        )

    workload: dict[str, Any] = {
        "schema": "photonic_kernel.x8_gbs.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "dataset": {
            "name": data.name,
            "seed": int(dataset_seed),
            "profile": profile,
            "preprocessing": (
                "standardization, PCA(4), and min-max scaling fitted on the outer train split"
            ),
            "pca_explained_ratio": data.pca_explained_ratio,
        },
        "model": {
            "family": "continuous-variable Gaussian boson sampling kernel",
            "not_a_qubit_backend_port": True,
            "target_topology": "X8/Xunitary",
            "feature_map": (
                "four TMSV pairs (i,i+4), followed by the same data-dependent "
                "four-mode interferometer on modes 0:4 and 4:8"
            ),
            "config": config_to_dict(config),
            "selected_candidate": selection.candidate.name,
            "selection_rule": (
                "maximize mean validation balanced accuracy across pattern, moment, "
                "event and orbit kernels; break ties with mean train alignment"
            ),
            "kernels": {
                "hellinger": {
                    **asdict(selection.hellinger),
                    "definition": "inner product of square-root raw PNR probabilities with overflow bin",
                },
                "moment_rbf": {
                    **asdict(selection.moment_rbf),
                    "definition": "RBF over standardized truncated moments and overflow rate",
                },
                "event_hellinger": {
                    **asdict(selection.event_hellinger),
                    "definition": "Hellinger kernel over total-photon/click-count events plus overflow",
                },
                "orbit_hellinger": {
                    **asdict(selection.orbit_hellinger),
                    "definition": "Hellinger kernel over permutation orbits plus overflow",
                },
            },
        },
        "samples": {
            "sample_seed": int(sample_seed),
            "selection_boundary": (
                "hyperparameters use train and validation only; test is evaluated after freezing"
            ),
            "train": {
                "split_indices": train_indices.tolist(),
                "x": train_x.tolist(),
                "y": train_y.tolist(),
            },
            "test": {
                "split_indices": test_indices.tolist(),
                "x": test_x.tolist(),
                "y": test_y.tolist(),
            },
        },
        "measurement": {
            "protocol": "photon-number-resolving samples in all eight modes",
            "comparison": (
                "all four kernels are computed from every shared raw sample record; overflow "
                "is an explicit feature and events are not replenished"
            ),
            "total_budget": int(budget),
            "budget_unit": "raw PNR shots",
            "circuit_count": len(entries),
            "shots_per_circuit_min": int(allocation.min()),
            "shots_per_circuit_max": int(allocation.max()),
            "max_total_photons": config.max_total_photons,
            "entries": entries,
        },
        "execution_policy": {
            "remote_submission_requires_explicit_confirmation": True,
            "expected_target": "X8",
            "public_xanadu_quantum_cloud_available": False,
            "cloud_status_checked_utc": "2026-08-17",
            "cloud_status": (
                "Official Strawberry Fields documentation states that Xanadu Quantum "
                "Cloud is no longer available; remote code is retained only for a "
                "separately confirmed private or legacy endpoint."
            ),
            "credentials_persisted_in_workload": False,
        },
    }
    workload["workload_id"] = workload_identifier(workload)
    return workload


def _records_for_workload(
    workload: dict[str, Any],
    config: X8GBSConfig,
    measurement_seed: int,
) -> tuple[dict[str, dict[str, Any]], list[GBSDistribution]]:
    records: dict[str, dict[str, Any]] = {}
    distributions: list[GBSDistribution] = []
    rng = np.random.default_rng(measurement_seed)
    for entry in workload["measurement"]["entries"]:
        distribution = gbs_distribution(np.asarray(entry["x"], dtype=float), config)
        distributions.append(distribution)
        records[entry["circuit_id"]] = sample_distribution(
            distribution,
            int(entry["shots"]),
            rng,
        )
    return records, distributions


def analyze_records(
    workload: dict[str, Any],
    records_by_id: dict[str, dict[str, Any]],
    ideal_distributions: list[GBSDistribution] | None = None,
) -> dict[str, Any]:
    entries = workload["measurement"]["entries"]
    entry_ids = [str(entry["circuit_id"]) for entry in entries]
    if set(records_by_id) != set(entry_ids):
        missing = sorted(set(entry_ids) - set(records_by_id))
        extra = sorted(set(records_by_id) - set(entry_ids))
        raise ValueError(f"Sample-record IDs differ from workload; missing={missing}, extra={extra}")
    records = [records_by_id[circuit_id] for circuit_id in entry_ids]
    expected_shots = [int(entry["shots"]) for entry in entries]
    observed_shots = [int(record["shots"]) for record in records]
    if observed_shots != expected_shots:
        raise ValueError("Per-circuit shot counts differ from the frozen workload")
    if sum(observed_shots) != int(workload["measurement"]["total_budget"]):
        raise ValueError("Observed sample records do not use the exact total budget")

    train_count = len(workload["samples"]["train"]["y"])
    y_train = np.asarray(workload["samples"]["train"]["y"], dtype=int)
    y_test = np.asarray(workload["samples"]["test"]["y"], dtype=int)
    max_total = int(workload["measurement"]["max_total_photons"])
    hellinger, moments, acceptance = features_from_records(records, max_total)
    grouped = event_orbit_features(records, max_total)
    h_train = hellinger[:train_count]
    h_test = hellinger[train_count:]
    m_train, m_test = standardize_moments(
        moments[:train_count],
        moments[train_count:],
    )
    event = np.sqrt(grouped.event)
    orbit = np.sqrt(grouped.orbit)

    selections = workload["model"]["kernels"]
    moment_gamma = float(selections["moment_rbf"]["gamma"])
    sampled_kernels = {
        "hellinger": {
            "train": hellinger_kernel(h_train, h_train),
            "test": hellinger_kernel(h_test, h_train),
        },
        "moment_rbf": {
            "train": moment_kernel(m_train, m_train, moment_gamma),
            "test": moment_kernel(m_test, m_train, moment_gamma),
        },
        "event_hellinger": {
            "train": hellinger_kernel(event[:train_count], event[:train_count]),
            "test": hellinger_kernel(event[train_count:], event[:train_count]),
        },
        "orbit_hellinger": {
            "train": hellinger_kernel(orbit[:train_count], orbit[:train_count]),
            "test": hellinger_kernel(orbit[train_count:], orbit[:train_count]),
        },
    }

    analysis: dict[str, Any] = {
        "schema": "photonic_kernel.analysis.v1",
        "workload_id": workload["workload_id"],
        "same_raw_records_for_all_kernels": True,
        "overflow_is_explicit_feature": True,
        "shot_accounting": {
            "expected_total": int(workload["measurement"]["total_budget"]),
            "observed_total": int(sum(observed_shots)),
            "accepted_total": int(sum(int(record["accepted_shots"]) for record in records)),
            "rejected_total": int(sum(int(record["rejected_shots"]) for record in records)),
            "acceptance_rate_mean": float(np.mean(acceptance)),
            "acceptance_rate_min": float(np.min(acceptance)),
        },
        "finite_shot": {},
        "kernels": {},
    }
    for name, matrices in sampled_kernels.items():
        regularization = float(selections[name]["regularization"])
        metrics = _prediction_metrics(
            matrices["train"],
            y_train,
            matrices["test"],
            y_test,
            regularization,
        )
        analysis["finite_shot"][name] = {
            **metrics,
            **kernel_diagnostics(matrices["train"], regularization),
        }
        analysis["kernels"][name] = {
            "train": matrices["train"].tolist(),
            "test": matrices["test"].tolist(),
        }

    if ideal_distributions is not None:
        ideal_hellinger, ideal_moments, ideal_acceptance = ideal_features(
            ideal_distributions
        )
        ideal_grouped = ideal_event_orbit_features(ideal_distributions)
        ih_train = ideal_hellinger[:train_count]
        ih_test = ideal_hellinger[train_count:]
        im_train, im_test = standardize_moments(
            ideal_moments[:train_count],
            ideal_moments[train_count:],
        )
        ideal_event = np.sqrt(ideal_grouped.event)
        ideal_orbit = np.sqrt(ideal_grouped.orbit)
        ideal_kernels = {
            "hellinger": {
                "train": hellinger_kernel(ih_train, ih_train),
                "test": hellinger_kernel(ih_test, ih_train),
            },
            "moment_rbf": {
                "train": moment_kernel(im_train, im_train, moment_gamma),
                "test": moment_kernel(im_test, im_train, moment_gamma),
            },
            "event_hellinger": {
                "train": hellinger_kernel(
                    ideal_event[:train_count], ideal_event[:train_count]
                ),
                "test": hellinger_kernel(
                    ideal_event[train_count:], ideal_event[:train_count]
                ),
            },
            "orbit_hellinger": {
                "train": hellinger_kernel(
                    ideal_orbit[:train_count], ideal_orbit[:train_count]
                ),
                "test": hellinger_kernel(
                    ideal_orbit[train_count:], ideal_orbit[:train_count]
                ),
            },
        }
        analysis["ideal"] = {}
        for name, matrices in ideal_kernels.items():
            regularization = float(selections[name]["regularization"])
            analysis["ideal"][name] = {
                **_prediction_metrics(
                    matrices["train"],
                    y_train,
                    matrices["test"],
                    y_test,
                    regularization,
                ),
                **kernel_diagnostics(matrices["train"], regularization),
                "sampled_train_relative_frobenius": _relative_frobenius(
                    sampled_kernels[name]["train"], matrices["train"]
                ),
                "sampled_test_relative_frobenius": _relative_frobenius(
                    sampled_kernels[name]["test"], matrices["test"]
                ),
            }
            analysis["kernels"][name]["ideal_train"] = matrices["train"].tolist()
            analysis["kernels"][name]["ideal_test"] = matrices["test"].tolist()
        analysis["ideal"]["acceptance_probability_mean"] = float(
            np.mean(ideal_acceptance)
        )
    return analysis


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_screening(path: Path, rows: tuple[dict[str, Any], ...]) -> None:
    if not rows:
        raise ValueError("No screening rows")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_kernel_csv(path: Path, values: list[list[float]]) -> None:
    np.savetxt(path, np.asarray(values, dtype=float), delimiter=",", fmt="%.12g")


def _report(
    workload: dict[str, Any],
    analysis: dict[str, Any],
    classical: dict[str, Any],
) -> str:
    model = workload["model"]
    measurement = workload["measurement"]
    finite = analysis["finite_shot"]
    ideal = analysis.get("ideal", {})
    lines = [
        "# Fotoniczny kernel CV/GBS dla Xanadu X8",
        "",
        f"Workload ID: `{workload['workload_id']}`.",
        "",
        "## Model",
        "",
        "To jest osobna hipoteza fotoniczna, a nie translacja kubitowej ewolucji Isinga.",
        f"Wybrana konfiguracja: `{model['selected_candidate']}`; topologia `Xunitary`.",
        "Cztery pary TMSV sa laczone tym samym interferometrem 4-modowym w obu polowach X8.",
        "",
        "## Protokol",
        "",
        f"- Liczba obwodow: `{measurement['circuit_count']}`.",
        f"- Wspolny budzet: `{measurement['total_budget']}` surowych pomiarow PNR.",
        f"- Zakres strzalow na obwod: `{measurement['shots_per_circuit_min']}-{measurement['shots_per_circuit_max']}`.",
        f"- Okno cech: laczna liczba fotonow <= `{measurement['max_total_photons']}`.",
        f"- Zaakceptowano `{analysis['shot_accounting']['accepted_total']}` zdarzen; odrzucono `{analysis['shot_accounting']['rejected_total']}` bez uzupelniania.",
        "- Cztery rodziny cech powstaly z tych samych rekordow PNR; overflow jest jawnym binem.",
        "",
        "## Wyniki testowe",
        "",
        "| model | ideal BA | finite-shot BA | finite-shot macro-F1 |",
        "|---|---:|---:|---:|",
    ]
    for name in ("hellinger", "moment_rbf", "event_hellinger", "orbit_hellinger"):
        lines.append(
            f"| {name} | {ideal[name]['balanced_accuracy']:.3f} | "
            f"{finite[name]['balanced_accuracy']:.3f} | {finite[name]['macro_f1']:.3f} |"
        )
    lines.append(
        f"| classical_rbf | {classical['balanced_accuracy']:.3f} | n/a | "
        f"{classical['macro_f1']:.3f} |"
    )
    lines.extend(
        [
            "",
            "## Ograniczenia",
            "",
            "Selekcja siatki jest symulacyjna i pozostaje poza budzetem sprzetowym.",
            "Rozklad idealny jest liczony dokladnie z hafnianow tylko w zadanym oknie fotonowym.",
            "Wynik lokalny jest symulacja finite-shot, nie wykonaniem na QPU Xanadu.",
            "Publiczna chmura Xanadu jest wycofana; zdalny adapter wymaga osobno potwierdzonego endpointu prywatnego/historycznego.",
            "",
        ]
    )
    return "\n".join(lines)


def run_experiment(args: argparse.Namespace) -> Path:
    profile = PROFILES[args.profile]
    train_per_class = (
        profile.train_per_class if args.train_per_class is None else args.train_per_class
    )
    validation_per_class = (
        profile.validation_per_class
        if args.validation_per_class is None
        else args.validation_per_class
    )
    test_per_class = (
        profile.test_per_class if args.test_per_class is None else args.test_per_class
    )
    budget = profile.budget if args.budget is None else args.budget
    max_total = (
        profile.max_total_photons
        if args.max_total_photons is None
        else args.max_total_photons
    )

    raw = load_dataset(args.dataset, seed=args.seed, smoke=args.profile == "smoke")
    data = prepare_dataset(raw, n_components=4, seed=args.seed)
    train_indices = balanced_subset_indices(data.y_train, train_per_class, args.sample_seed)
    validation_indices = balanced_subset_indices(
        data.y_val,
        validation_per_class,
        args.sample_seed + 1,
    )
    test_indices = balanced_subset_indices(
        data.y_test,
        test_per_class,
        args.sample_seed + 2,
    )
    x_train = data.x_train[train_indices]
    y_train = data.y_train[train_indices]
    x_validation = data.x_val[validation_indices]
    y_validation = data.y_val[validation_indices]

    selection = select_photonic_model(
        x_train,
        y_train,
        x_validation,
        y_validation,
        candidate_grid(args.profile),
        args.reservoir_seed,
        max_total,
    )
    classical_selection = _select_classical_baseline(
        x_train,
        y_train,
        x_validation,
        y_validation,
    )
    classical_train = rbf_kernel(
        x_train,
        x_train,
        float(classical_selection.gamma),
    )
    classical_test = rbf_kernel(
        data.x_test[test_indices],
        x_train,
        float(classical_selection.gamma),
    )
    classical_metrics = {
        **asdict(classical_selection),
        **_prediction_metrics(
            classical_train,
            y_train,
            classical_test,
            data.y_test[test_indices],
            classical_selection.regularization,
        ),
        **kernel_diagnostics(classical_train, classical_selection.regularization),
    }

    config = selection.candidate.config(args.reservoir_seed, max_total)
    workload = build_workload(
        data,
        train_indices,
        test_indices,
        selection,
        config,
        budget,
        args.seed,
        args.sample_seed,
        args.measurement_seed,
        args.profile,
    )
    records, ideal_distributions = _records_for_workload(
        workload,
        config,
        args.measurement_seed,
    )
    analysis = analyze_records(workload, records, ideal_distributions)
    analysis["classical_rbf"] = classical_metrics
    analysis["selection"] = {
        "candidate": selection.candidate.name,
        "hellinger": asdict(selection.hellinger),
        "moment_rbf": asdict(selection.moment_rbf),
        "event_hellinger": asdict(selection.event_hellinger),
        "orbit_hellinger": asdict(selection.orbit_hellinger),
        "classical_rbf": asdict(classical_selection),
        "train_split_indices": train_indices.tolist(),
        "validation_split_indices": validation_indices.tolist(),
        "sample_seed": args.sample_seed,
        "test_used_during_selection": False,
    }

    output_dir = (
        args.output_dir
        or DEFAULT_OUTPUT_ROOT
        / f"photonic_kernel_x8_{args.profile}_{args.dataset}_seed{args.seed}"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_screening(output_dir / "screening.csv", selection.screening_rows)
    _write_json(output_dir / "selected_model.json", analysis["selection"])
    _write_json(output_dir / "workload.json", workload)
    _write_json(
        output_dir / "local_counts.json",
        {
            "schema": "photonic_kernel.sample_records.v1",
            "workload_id": workload["workload_id"],
            "source": "local exact-GBS multinomial simulation",
            "not_a_qpu_execution": True,
            "records": records,
        },
    )
    _write_json(output_dir / "analysis.json", analysis)
    for name in ("hellinger", "moment_rbf", "event_hellinger", "orbit_hellinger"):
        for matrix_name, values in analysis["kernels"][name].items():
            _write_kernel_csv(output_dir / f"{name}_{matrix_name}.csv", values)
    (output_dir / "report.md").write_text(
        _report(workload, analysis, classical_metrics),
        encoding="utf-8",
    )
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="X8-compatible CV/GBS kernel experiment"
    )
    parser.add_argument("--profile", choices=tuple(PROFILES), default="smoke")
    parser.add_argument("--dataset", choices=("moons", "wdbc", "wine"), default="moons")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample-seed", type=int, default=20260817)
    parser.add_argument("--measurement-seed", type=int, default=20260818)
    parser.add_argument("--reservoir-seed", type=int, default=20260819)
    parser.add_argument("--train-per-class", type=int)
    parser.add_argument("--validation-per-class", type=int)
    parser.add_argument("--test-per-class", type=int)
    parser.add_argument("--budget", type=int)
    parser.add_argument("--max-total-photons", type=int)
    parser.add_argument("--output-dir", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = run_experiment(args)
    print(output_dir)


if __name__ == "__main__":
    main()
