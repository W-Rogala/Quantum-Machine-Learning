from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import time
import zlib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .core import (
    EvolutionConfig,
    bloch_vectors,
    circuit_resources,
    evolve_batch,
    fidelity_kernel,
    projected_kernel,
    state_infidelity,
)
from .data import PreparedData, load_dataset, prepare_dataset
from .estimation import (
    estimate_fidelity_spectral,
    estimate_projected_bloch,
    fidelity_estimation_circuit_count as measured_fidelity_circuit_count,
    kernel_stages,
    resource_cost,
)
from .learning import (
    balanced_accuracy,
    centered_kernel_alignment,
    class_targets,
    fit_kernel_ridge,
    kernel_diagnostics,
    macro_f1,
    predict_kernel_ridge,
    rbf_kernel,
)


ROOT = Path(__file__).resolve().parents[1]
GAMMA_GRID = (0.1, 0.3, 1.0, 3.0, 10.0)
REGULARIZATION_GRID = (1e-4, 1e-3, 1e-2, 1e-1, 1.0)


@dataclass(frozen=True)
class HamiltonianCandidate:
    evolution_time: float
    interaction_strength: float
    transverse_field: float
    topology: str

    @property
    def name(self) -> str:
        return (
            f"t{self.evolution_time:g}_J{self.interaction_strength:g}_"
            f"g{self.transverse_field:g}_{self.topology}"
        )

    def config(self, n_qubits: int, method: str = "trotter") -> EvolutionConfig:
        return EvolutionConfig(
            n_qubits=n_qubits,
            evolution_time=self.evolution_time,
            transverse_field=self.transverse_field,
            interaction_strength=self.interaction_strength,
            topology=self.topology,
            method=method,
            trotter_order=2,
            trotter_steps=2,
        )


@dataclass(frozen=True)
class SelectedModel:
    kernel: str
    candidate: HamiltonianCandidate
    gamma: float | None
    regularization: float
    train_alignment: float
    validation_balanced_accuracy: float


@dataclass(frozen=True)
class BudgetAllocation:
    shots: np.ndarray
    total_budget: int
    circuit_count: int

    @property
    def minimum(self) -> int:
        return int(self.shots.min())

    @property
    def maximum(self) -> int:
        return int(self.shots.max())


def candidate_grid(profile: str) -> list[HamiltonianCandidate]:
    if profile == "smoke":
        times = (0.6, 1.0)
        interactions = (0.0, 0.6)
        fields = (0.4, 0.8)
        topologies = ("chain", "ring")
    else:
        times = (0.5, 1.0, 1.5)
        interactions = (0.0, 0.4, 0.8)
        fields = (0.3, 0.7, 1.1)
        topologies = ("chain", "ring", "all_to_all")

    candidates: list[HamiltonianCandidate] = []
    for evolution_time in times:
        for interaction_strength in interactions:
            active_topologies = ("chain",) if interaction_strength == 0.0 else topologies
            for transverse_field in fields:
                for topology in active_topologies:
                    candidates.append(
                        HamiltonianCandidate(
                            evolution_time=evolution_time,
                            interaction_strength=interaction_strength,
                            transverse_field=transverse_field,
                            topology=topology,
                        )
                    )
    return candidates


def stable_rng(*parts: int | str) -> np.random.Generator:
    entropy: list[int] = []
    for part in parts:
        if isinstance(part, str):
            entropy.append(zlib.crc32(part.encode("utf-8")))
        else:
            entropy.append(int(part))
    return np.random.default_rng(np.random.SeedSequence(entropy))


def allocate_exact_budget(circuit_count: int, total_budget: int, rng: np.random.Generator) -> BudgetAllocation:
    if circuit_count < 1:
        raise ValueError("circuit_count must be positive")
    if total_budget < circuit_count:
        raise ValueError(
            f"Budget {total_budget} cannot allocate at least one shot to {circuit_count} circuits"
        )
    base, remainder = divmod(total_budget, circuit_count)
    shots = np.full(circuit_count, base, dtype=np.int64)
    if remainder:
        selected = rng.choice(circuit_count, size=remainder, replace=False)
        shots[selected] += 1
    if int(shots.sum()) != total_budget:
        raise AssertionError("Budget allocation is not exact")
    return BudgetAllocation(shots=shots, total_budget=total_budget, circuit_count=circuit_count)


def select_gamma(build_kernel: Callable[[float], np.ndarray], y_train: np.ndarray) -> tuple[float, float]:
    best_gamma = GAMMA_GRID[0]
    best_alignment = -np.inf
    for gamma in GAMMA_GRID:
        alignment = centered_kernel_alignment(build_kernel(gamma), y_train)
        if alignment > best_alignment + 1e-12:
            best_gamma = gamma
            best_alignment = alignment
    return best_gamma, float(best_alignment)


def select_regularization_eigendecomposition(
    k_train: np.ndarray,
    y_train: np.ndarray,
    k_val: np.ndarray,
    y_val: np.ndarray,
) -> tuple[float, float]:
    classes = np.unique(y_train)
    targets = class_targets(y_train, classes)
    symmetric = 0.5 * (np.asarray(k_train, dtype=float) + np.asarray(k_train, dtype=float).T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    eigenvalues = np.maximum(eigenvalues, 0.0)
    projected_targets = eigenvectors.T @ targets

    best_regularization = REGULARIZATION_GRID[0]
    best_score = -np.inf
    for regularization in REGULARIZATION_GRID:
        coefficients = eigenvectors @ (projected_targets / (eigenvalues[:, None] + regularization))
        prediction = classes[np.argmax(k_val @ coefficients, axis=1)]
        score = balanced_accuracy(y_val, prediction, classes)
        if score > best_score + 1e-12:
            best_regularization = regularization
            best_score = score
    return best_regularization, float(best_score)


def _candidate_row(
    dataset: str,
    seed: int,
    kernel: str,
    candidate: HamiltonianCandidate,
    alignment: float,
    gamma: float | None,
    n_qubits: int,
) -> dict[str, Any]:
    resources = circuit_resources(candidate.config(n_qubits))
    return {
        "dataset": dataset,
        "seed": seed,
        "kernel": kernel,
        "candidate": candidate.name,
        "evolution_time": candidate.evolution_time,
        "interaction_strength": candidate.interaction_strength,
        "transverse_field": candidate.transverse_field,
        "topology": candidate.topology,
        "train_alignment": alignment,
        "gamma": gamma,
        **resources,
    }


def screen_and_select_candidates(
    dataset_name: str,
    seed: int,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    candidates: list[HamiltonianCandidate],
    n_qubits: int,
    top_k: int,
) -> tuple[
    dict[str, SelectedModel],
    dict[str, np.ndarray],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Select models without accepting test features or labels."""

    train_count = len(x_train)
    selection_x = np.vstack((x_train, x_val))
    states_by_candidate: dict[str, np.ndarray] = {}
    bloch_by_candidate: dict[str, np.ndarray] = {}
    screening_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        states = evolve_batch(selection_x, candidate.config(n_qubits))
        states_by_candidate[candidate.name] = states
        train_states = states[:train_count]

        fidelity_train = fidelity_kernel(train_states, train_states)
        screening_rows.append(
            _candidate_row(
                dataset_name,
                seed,
                "fidelity",
                candidate,
                centered_kernel_alignment(fidelity_train, y_train),
                None,
                n_qubits,
            )
        )

        all_bloch = bloch_vectors(states, n_qubits)
        bloch_by_candidate[candidate.name] = all_bloch
        train_bloch = all_bloch[:train_count]
        gamma, alignment = select_gamma(
            lambda value: projected_kernel(train_bloch, train_bloch, value),
            y_train,
        )
        screening_rows.append(
            _candidate_row(
                dataset_name,
                seed,
                "projected",
                candidate,
                alignment,
                gamma,
                n_qubits,
            )
        )

    validation_rows: list[dict[str, Any]] = []
    selected: dict[str, SelectedModel] = {}
    candidate_lookup = {candidate.name: candidate for candidate in candidates}
    for kernel in ("fidelity", "projected"):
        kernel_rows = [row for row in screening_rows if row["kernel"] == kernel]
        finalists = sorted(
            kernel_rows,
            key=lambda row: (
                -float(row["train_alignment"]),
                int(row["two_qubit_gates"]),
                str(row["candidate"]),
            ),
        )[: min(top_k, len(kernel_rows))]

        for screening in finalists:
            candidate_name = str(screening["candidate"])
            if kernel == "fidelity":
                states = states_by_candidate[candidate_name]
                k_train = fidelity_kernel(states[:train_count], states[:train_count])
                k_val = fidelity_kernel(states[train_count:], states[:train_count])
            else:
                all_bloch = bloch_by_candidate[candidate_name]
                gamma = float(screening["gamma"])
                k_train = projected_kernel(all_bloch[:train_count], all_bloch[:train_count], gamma)
                k_val = projected_kernel(all_bloch[train_count:], all_bloch[:train_count], gamma)

            regularization, validation_score = select_regularization_eigendecomposition(
                k_train,
                y_train,
                k_val,
                y_val,
            )
            validation_rows.append(
                {
                    **screening,
                    "regularization": regularization,
                    "validation_balanced_accuracy": validation_score,
                }
            )

        kernel_validation = [row for row in validation_rows if row["kernel"] == kernel]
        winner = sorted(
            kernel_validation,
            key=lambda row: (
                -float(row["validation_balanced_accuracy"]),
                -float(row["train_alignment"]),
                int(row["two_qubit_gates"]),
                str(row["candidate"]),
            ),
        )[0]
        selected[kernel] = SelectedModel(
            kernel=kernel,
            candidate=candidate_lookup[str(winner["candidate"])],
            gamma=None if winner["gamma"] in (None, "") else float(winner["gamma"]),
            regularization=float(winner["regularization"]),
            train_alignment=float(winner["train_alignment"]),
            validation_balanced_accuracy=float(winner["validation_balanced_accuracy"]),
        )

    return selected, states_by_candidate, screening_rows, validation_rows


def split_states(states: np.ndarray, data: PreparedData) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    train_end = len(data.x_train)
    val_end = train_end + len(data.x_val)
    return states[:train_end], states[train_end:val_end], states[val_end:]


def evaluate_ideal_selected(
    model: SelectedModel,
    data: PreparedData,
    selection_states: np.ndarray,
    n_qubits: int,
    seed: int,
) -> tuple[dict[str, Any], np.ndarray]:
    test_states = evolve_batch(data.x_test, model.candidate.config(n_qubits))
    all_states = np.vstack((selection_states, test_states))
    train_states, val_states, test_states = split_states(all_states, data)

    if model.kernel == "fidelity":
        k_train = fidelity_kernel(train_states, train_states)
        k_val = fidelity_kernel(val_states, train_states)
        k_test = fidelity_kernel(test_states, train_states)
    else:
        all_bloch = bloch_vectors(all_states, n_qubits)
        train_bloch, val_bloch, test_bloch = split_states(all_bloch, data)
        gamma = float(model.gamma)
        k_train = projected_kernel(train_bloch, train_bloch, gamma)
        k_val = projected_kernel(val_bloch, train_bloch, gamma)
        k_test = projected_kernel(test_bloch, train_bloch, gamma)

    coefficients, classes = fit_kernel_ridge(k_train, data.y_train, model.regularization)
    prediction = predict_kernel_ridge(k_test, coefficients, classes)
    validation_prediction = predict_kernel_ridge(k_val, coefficients, classes)

    exact_states = evolve_batch(
        np.vstack((data.x_train, data.x_val, data.x_test)),
        model.candidate.config(n_qubits, method="exact"),
    )
    infidelity = state_infidelity(exact_states, all_states)
    resources = circuit_resources(model.candidate.config(n_qubits))
    row = {
        "dataset": data.name,
        "seed": seed,
        "kernel": model.kernel,
        "candidate": model.candidate.name,
        "evolution_time": model.candidate.evolution_time,
        "interaction_strength": model.candidate.interaction_strength,
        "transverse_field": model.candidate.transverse_field,
        "topology": model.candidate.topology,
        "gamma": model.gamma,
        "regularization": model.regularization,
        "train_alignment": model.train_alignment,
        "selected_validation_balanced_accuracy": model.validation_balanced_accuracy,
        "recomputed_validation_balanced_accuracy": balanced_accuracy(data.y_val, validation_prediction, classes),
        "test_accuracy": float(np.mean(prediction == data.y_test)),
        "test_balanced_accuracy": balanced_accuracy(data.y_test, prediction, classes),
        "test_macro_f1": macro_f1(data.y_test, prediction, classes),
        "mean_state_infidelity": float(np.mean(infidelity)),
        "max_state_infidelity": float(np.max(infidelity)),
        **resources,
        **kernel_diagnostics(k_train, model.regularization),
    }
    return row, all_states


def evaluate_rbf(data: PreparedData, seed: int) -> dict[str, Any]:
    gamma, alignment = select_gamma(
        lambda value: rbf_kernel(data.x_train, data.x_train, value),
        data.y_train,
    )
    k_train = rbf_kernel(data.x_train, data.x_train, gamma)
    k_val = rbf_kernel(data.x_val, data.x_train, gamma)
    k_test = rbf_kernel(data.x_test, data.x_train, gamma)
    regularization, validation_score = select_regularization_eigendecomposition(
        k_train,
        data.y_train,
        k_val,
        data.y_val,
    )
    coefficients, classes = fit_kernel_ridge(k_train, data.y_train, regularization)
    prediction = predict_kernel_ridge(k_test, coefficients, classes)
    return {
        "dataset": data.name,
        "seed": seed,
        "kernel": "rbf",
        "candidate": "classical_rbf",
        "evolution_time": None,
        "interaction_strength": None,
        "transverse_field": None,
        "topology": None,
        "gamma": gamma,
        "regularization": regularization,
        "train_alignment": alignment,
        "selected_validation_balanced_accuracy": validation_score,
        "recomputed_validation_balanced_accuracy": validation_score,
        "test_accuracy": float(np.mean(prediction == data.y_test)),
        "test_balanced_accuracy": balanced_accuracy(data.y_test, prediction, classes),
        "test_macro_f1": macro_f1(data.y_test, prediction, classes),
        "mean_state_infidelity": 0.0,
        "max_state_infidelity": 0.0,
        "a_blocks": 0,
        "single_qubit_rotations": 0,
        "two_qubit_gates": 0,
        "logical_depth_proxy": 0,
        **kernel_diagnostics(k_train, regularization),
    }


def landmark_indices(n_train: int, landmark_count: int, seed: int) -> np.ndarray:
    if n_train < 1:
        raise ValueError("n_train must be positive")
    if landmark_count < 0:
        raise ValueError("landmark_count cannot be negative")
    if landmark_count == 0 or landmark_count >= n_train:
        return np.arange(n_train, dtype=int)
    count = landmark_count
    return np.sort(stable_rng(seed, "nystrom_landmarks").choice(n_train, size=count, replace=False))


def fidelity_estimation_circuit_count(
    total_samples: int,
    n_train: int,
    landmark_count: int,
) -> int:
    return measured_fidelity_circuit_count(total_samples, n_train, landmark_count)


def budgeted_nystrom_fidelity_features(
    states: np.ndarray,
    n_train: int,
    landmarks: np.ndarray,
    total_budget: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, Any]]:
    estimate = estimate_fidelity_spectral(
        states,
        n_train,
        landmarks,
        total_budget,
        rng,
    )
    return estimate.features, estimate.diagnostics


def budgeted_projected_bloch(
    states: np.ndarray,
    n_qubits: int,
    total_budget: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, Any]]:
    estimate = estimate_projected_bloch(states, n_qubits, total_budget, rng)
    return estimate.bloch, estimate.diagnostics


def evaluate_budgeted_model(
    model: SelectedModel,
    data: PreparedData,
    all_states: np.ndarray,
    n_qubits: int,
    seed: int,
    noise_replicate: int,
    total_budget: int,
    landmark_count: int,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    rng = stable_rng(seed, noise_replicate, total_budget, model.kernel, model.candidate.name)
    artifact_payload: dict[str, np.ndarray]
    if model.kernel == "fidelity":
        landmarks = landmark_indices(len(data.x_train), landmark_count, seed)
        estimate = estimate_fidelity_spectral(
            all_states,
            len(data.x_train),
            landmarks,
            total_budget,
            rng,
        )
        features = estimate.features
        diagnostics = estimate.diagnostics
        train_features, val_features, test_features = split_states(features, data)
        k_train = train_features @ train_features.T
        k_val = val_features @ train_features.T
        k_test = test_features @ train_features.T
        artifact_payload = {
            "raw_landmark_kernel": estimate.raw_landmark_kernel,
            "raw_sample_landmark": estimate.raw_sample_landmark,
            "raw_measured_diagonal": estimate.measured_diagonal,
            "psd_landmark_kernel": estimate.psd_landmark_kernel,
            "spectral_kernel_all": estimate.spectral_kernel,
            "raw_eigenvalues": estimate.raw_eigenvalues,
            "psd_eigenvalues": estimate.psd_eigenvalues,
            "spectral_eigenvalues": estimate.spectral_eigenvalues,
        }
    else:
        estimate = estimate_projected_bloch(all_states, n_qubits, total_budget, rng)
        estimated_bloch = estimate.bloch
        diagnostics = estimate.diagnostics
        train_bloch, val_bloch, test_bloch = split_states(estimated_bloch, data)
        gamma = float(model.gamma)
        k_train = projected_kernel(train_bloch, train_bloch, gamma)
        k_val = projected_kernel(val_bloch, train_bloch, gamma)
        k_test = projected_kernel(test_bloch, train_bloch, gamma)
        raw_all = projected_kernel(estimated_bloch, estimated_bloch, gamma)
        stages = kernel_stages(raw_all)
        diagnostics = {
            **diagnostics,
            "raw_min_eigenvalue": float(stages.raw_eigenvalues[0]),
            "psd_min_eigenvalue": float(stages.psd_eigenvalues[0]),
            "spectral_threshold": stages.spectral_threshold,
            "spectral_rank": int(np.count_nonzero(stages.spectral_eigenvalues)),
        }
        artifact_payload = {
            "raw_kernel_all": stages.raw,
            "psd_kernel_all": stages.psd,
            "spectral_kernel_all": stages.spectral,
            "raw_eigenvalues": stages.raw_eigenvalues,
            "psd_eigenvalues": stages.psd_eigenvalues,
            "spectral_eigenvalues": stages.spectral_eigenvalues,
            "sampled_bloch": estimated_bloch,
            "shots_by_setting": estimate.shots_by_setting,
        }

    regularization, validation_score = select_regularization_eigendecomposition(
        k_train,
        data.y_train,
        k_val,
        data.y_val,
    )
    coefficients, classes = fit_kernel_ridge(k_train, data.y_train, regularization)
    prediction = predict_kernel_ridge(k_test, coefficients, classes)
    resources = circuit_resources(model.candidate.config(n_qubits))
    costs = resource_cost(
        total_budget,
        2 if model.kernel == "fidelity" else 1,
        int(resources["two_qubit_gates"]),
    )
    artifact_path: str | None = None
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / (
            f"{data.name}_seed{seed}_{model.kernel}_budget{total_budget}_"
            f"noise{noise_replicate}.npz"
        )
        np.savez_compressed(path, **artifact_payload)
        artifact_path = str(path)
    return {
        "dataset": data.name,
        "seed": seed,
        "noise_replicate": noise_replicate,
        "kernel": model.kernel,
        "candidate": model.candidate.name,
        "evolution_time": model.candidate.evolution_time,
        "interaction_strength": model.candidate.interaction_strength,
        "transverse_field": model.candidate.transverse_field,
        "topology": model.candidate.topology,
        "gamma": model.gamma,
        "total_measurement_budget": total_budget,
        "regularization": regularization,
        "validation_balanced_accuracy": validation_score,
        "test_accuracy": float(np.mean(prediction == data.y_test)),
        "test_balanced_accuracy": balanced_accuracy(data.y_test, prediction, classes),
        "test_macro_f1": macro_f1(data.y_test, prediction, classes),
        "train_alignment": centered_kernel_alignment(k_train, data.y_train),
        "two_qubit_gates_per_map": int(resources["two_qubit_gates"]),
        "matrix_artifact": artifact_path,
        **costs.as_dict(),
        # Backwards-compatible alias used by the previous audit tables.
        "two_qubit_gate_executions": costs.two_qubit_gate_shots,
        **diagnostics,
        **kernel_diagnostics(k_train, regularization),
    }


def summarize_ideal(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["dataset"]), str(row["kernel"]))].append(row)
    summary: list[dict[str, Any]] = []
    for (dataset, kernel), group in sorted(grouped.items()):
        item: dict[str, Any] = {"dataset": dataset, "kernel": kernel, "outer_splits": len(group)}
        for metric in (
            "test_accuracy",
            "test_balanced_accuracy",
            "test_macro_f1",
            "selected_validation_balanced_accuracy",
            "mean_state_infidelity",
            "two_qubit_gates",
        ):
            values = np.asarray([float(row[metric]) for row in group])
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        summary.append(item)
    return summary


def summarize_budget(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["dataset"]), str(row["kernel"]), int(row["total_measurement_budget"]))].append(row)

    summary: list[dict[str, Any]] = []
    for (dataset, kernel, budget), group in sorted(grouped.items()):
        by_seed: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in group:
            by_seed[int(row["seed"])].append(row)
        item: dict[str, Any] = {
            "dataset": dataset,
            "kernel": kernel,
            "total_measurement_budget": budget,
            "outer_splits": len(by_seed),
            "noise_replicates": min(len(values) for values in by_seed.values()),
        }
        for metric in ("test_accuracy", "test_balanced_accuracy", "test_macro_f1"):
            outer_means = np.asarray(
                [np.mean([float(row[metric]) for row in seed_rows]) for seed_rows in by_seed.values()]
            )
            within_std = np.asarray(
                [
                    np.std([float(row[metric]) for row in seed_rows], ddof=1)
                    if len(seed_rows) > 1
                    else 0.0
                    for seed_rows in by_seed.values()
                ]
            )
            item[f"{metric}_mean"] = float(np.mean(outer_means))
            item[f"{metric}_between_split_std"] = (
                float(np.std(outer_means, ddof=1)) if len(outer_means) > 1 else 0.0
            )
            item[f"{metric}_mean_within_noise_std"] = float(np.mean(within_std))
        for metric in (
            "circuit_count",
            "shots_per_circuit_min",
            "shots_per_circuit_max",
            "circuit_shots",
            "map_executions",
            "two_qubit_gate_shots",
            "two_qubit_gate_executions",
            "landmark_negative_eigenmass",
            "nystrom_rank",
        ):
            item[f"{metric}_mean"] = float(np.mean([float(row[metric]) for row in group]))
        summary.append(item)
    return summary


def budget_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {
        (
            str(row["dataset"]),
            int(row["seed"]),
            int(row["noise_replicate"]),
            int(row["total_measurement_budget"]),
            str(row["kernel"]),
        ): row
        for row in rows
    }
    combinations = sorted(
        {
            (str(row["dataset"]), int(row["total_measurement_budget"]))
            for row in rows
        }
    )
    results: list[dict[str, Any]] = []
    for dataset, budget in combinations:
        seeds = sorted({int(row["seed"]) for row in rows if row["dataset"] == dataset})
        seed_deltas: list[float] = []
        for seed in seeds:
            replicate_deltas: list[float] = []
            replicates = sorted(
                {
                    int(row["noise_replicate"])
                    for row in rows
                    if row["dataset"] == dataset and int(row["seed"]) == seed
                }
            )
            for replicate in replicates:
                fidelity_row = indexed[(dataset, seed, replicate, budget, "fidelity")]
                projected_row = indexed[(dataset, seed, replicate, budget, "projected")]
                replicate_deltas.append(
                    float(projected_row["test_balanced_accuracy"])
                    - float(fidelity_row["test_balanced_accuracy"])
                )
            seed_deltas.append(float(np.mean(replicate_deltas)))
        wins = sum(delta > 1e-12 for delta in seed_deltas)
        losses = sum(delta < -1e-12 for delta in seed_deltas)
        ties = len(seed_deltas) - wins - losses
        results.append(
            {
                "dataset": dataset,
                "total_measurement_budget": budget,
                "delta_definition": "projected_minus_fidelity",
                "mean_delta_balanced_accuracy": float(np.mean(seed_deltas)),
                "median_delta_balanced_accuracy": float(np.median(seed_deltas)),
                "between_split_std": float(np.std(seed_deltas, ddof=1)) if len(seed_deltas) > 1 else 0.0,
                "wins": wins,
                "losses": losses,
                "ties": ties,
            }
        )
    return results


def selection_frequencies(ideal_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in ideal_rows:
        if row["kernel"] != "rbf":
            grouped[(str(row["dataset"]), str(row["kernel"]))][str(row["candidate"])] += 1
    rows: list[dict[str, Any]] = []
    for (dataset, kernel), counts in sorted(grouped.items()):
        for candidate, count in counts.most_common():
            rows.append(
                {
                    "dataset": dataset,
                    "kernel": kernel,
                    "candidate": candidate,
                    "selected_count": count,
                    "selection_fraction": count / sum(counts.values()),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_plots(
    output_dir: Path,
    budget_summary: list[dict[str, Any]],
    frequencies: list[dict[str, Any]],
) -> None:
    datasets = sorted({str(row["dataset"]) for row in budget_summary})
    figure, axes = plt.subplots(1, len(datasets), figsize=(5.2 * len(datasets), 4.2), squeeze=False)
    colors = {"fidelity": "#245c8a", "projected": "#c45d36"}
    for index, dataset in enumerate(datasets):
        axis = axes[0, index]
        for kernel in ("fidelity", "projected"):
            rows = sorted(
                [row for row in budget_summary if row["dataset"] == dataset and row["kernel"] == kernel],
                key=lambda row: int(row["total_measurement_budget"]),
            )
            axis.errorbar(
                [row["total_measurement_budget"] for row in rows],
                [row["test_balanced_accuracy_mean"] for row in rows],
                yerr=[row["test_balanced_accuracy_between_split_std"] for row in rows],
                marker="o",
                capsize=3,
                color=colors[kernel],
                label=kernel,
            )
        axis.set_xscale("log")
        axis.set_ylim(0.0, 1.05)
        axis.set_title(dataset)
        axis.set_xlabel("total measurement budget")
        axis.set_ylabel("balanced accuracy")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.tight_layout()
    figure.savefig(output_dir / "equal_budget_performance.png", dpi=180)
    plt.close(figure)

    top = []
    for dataset in sorted({str(row["dataset"]) for row in frequencies}):
        for kernel in ("fidelity", "projected"):
            rows = [row for row in frequencies if row["dataset"] == dataset and row["kernel"] == kernel]
            top.extend(sorted(rows, key=lambda row: -int(row["selected_count"]))[:4])
    labels = [f"{row['dataset']} {row['kernel'][0].upper()}\n{row['candidate']}" for row in top]
    values = [int(row["selected_count"]) for row in top]
    figure, axis = plt.subplots(figsize=(11, max(4, 0.42 * len(top))))
    positions = np.arange(len(top))
    axis.barh(positions, values, color="#477a6b")
    axis.set_yticks(positions, labels, fontsize=8)
    axis.invert_yaxis()
    axis.set_xlabel("selection count across outer splits")
    axis.grid(axis="x", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "selection_frequency.png", dpi=180)
    plt.close(figure)


def write_report(
    path: Path,
    args: argparse.Namespace,
    candidates: list[HamiltonianCandidate],
    ideal_summary: list[dict[str, Any]],
    budget_summary: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    frequencies: list[dict[str, Any]],
) -> None:
    fidelity_description = (
        "Fidelity finite-shot wykorzystuje wszystkie stany treningowe i jedną znormalizowaną "
        "spektralną mapę cech wspólną dla train, validation i test."
        if args.landmarks == 0
        else "Fidelity finite-shot wykorzystuje jedną znormalizowaną mapę cech Nyströma wspólną dla train, validation i test."
    )
    fidelity_limitation = (
        "- Spektralne obcięcie zaszumionej treningowej macierzy Grama zapewnia jedną spójną mapę "
        "cech PSD, ale wprowadza bias estymatora przy małej liczbie strzałów na obwód."
        if args.landmarks == 0
        else "- Nyström jest spójnym, lecz przybliżonym estymatorem fidelity kernel; wynik zależy od liczby i wyboru landmarków."
    )
    lines = [
        "# Siatka Hamiltonian quantum kernel i równy budżet pomiarowy",
        "",
        "## Bramka audytowa",
        "",
        "Eksperyment uruchomiono po niezależnym audycie `PASS_WITH_REQUIRED_REMEDIATIONS` i po wdrożeniu działań A1-A3 oraz A5.",
        "",
        "## Protokół",
        "",
        f"- Siatka zawiera `{len(candidates)}` unikalnych konfiguracji `(t, J, g, topology)`.",
        "- Wszystkie konfiguracje są oceniane przez alignment na train; tylko najlepsze przechodzą ocenę validation.",
        "- Test jest obliczany jeden raz dla konfiguracji wybranej niezależnie dla każdej rodziny kernela.",
        f"- {fidelity_description}",
        "- Projected finite-shot estymuje lokalne wektory Blocha w trzech bazach pomiarowych na stan.",
        "- Obie rodziny otrzymują dokładnie ten sam całkowity budżet circuit-shots.",
        f"- Każdy punkt budżetowy ma `{args.noise_replicates}` niezależne realizacje szumu na outer split.",
        "- Koszt przeszukiwania siatki jest symulacyjny i nie wchodzi do budżetu finalnej estymacji kernela.",
        "",
        "## Wyniki idealne po zagnieżdżonej selekcji",
        "",
        "| zbiór | kernel | balanced acc. | macro-F1 | validation | infidelity | CX/map |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in ideal_summary:
        lines.append(
            f"| {row['dataset']} | {row['kernel']} | "
            + f"{row['test_balanced_accuracy_mean']:.3f} +/- {row['test_balanced_accuracy_std']:.3f} | "
            + f"{row['test_macro_f1_mean']:.3f} +/- {row['test_macro_f1_std']:.3f} | "
            + f"{row['selected_validation_balanced_accuracy_mean']:.3f} | "
            + f"{row['mean_state_infidelity_mean']:.3e} | {row['two_qubit_gates_mean']:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Wyniki przy równym budżecie",
            "",
            "Odchylenie `split` jest liczone po średniej z realizacji szumu w każdym outer split; `noise SD` opisuje średnią zmienność wewnątrz splitu.",
            "",
            "| zbiór | kernel | budżet | balanced acc. | split SD | noise SD | circuits | shots/circuit |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in budget_summary:
        shot_range = f"{row['shots_per_circuit_min_mean']:.0f}-{row['shots_per_circuit_max_mean']:.0f}"
        lines.append(
            f"| {row['dataset']} | {row['kernel']} | {int(row['total_measurement_budget'])} | "
            + f"{row['test_balanced_accuracy_mean']:.3f} | "
            + f"{row['test_balanced_accuracy_between_split_std']:.3f} | "
            + f"{row['test_balanced_accuracy_mean_within_noise_std']:.3f} | "
            + f"{row['circuit_count_mean']:.0f} | {shot_range} |"
        )

    lines.extend(
        [
            "",
            "## Porównanie sparowane przy tym samym budżecie",
            "",
            "Delta jest zdefiniowana jako `projected - fidelity` i najpierw uśredniona po realizacjach szumu w outer split.",
            "",
            "| zbiór | budżet | mean delta | split SD | W/L/T |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in comparisons:
        lines.append(
            f"| {row['dataset']} | {row['total_measurement_budget']} | "
            + f"{row['mean_delta_balanced_accuracy']:+.3f} | {row['between_split_std']:.3f} | "
            + f"{row['wins']}/{row['losses']}/{row['ties']} |"
        )

    lines.extend(["", "## Najczęściej wybierane konfiguracje", ""])
    for dataset in sorted({str(row["dataset"]) for row in frequencies}):
        for kernel in ("fidelity", "projected"):
            rows = [row for row in frequencies if row["dataset"] == dataset and row["kernel"] == kernel]
            top = sorted(rows, key=lambda row: -int(row["selected_count"]))[:3]
            description = ", ".join(f"`{row['candidate']}` ({row['selected_count']})" for row in top)
            lines.append(f"- {dataset}/{kernel}: {description}")

    lines.extend(
        [
            "",
            "## Ograniczenia",
            "",
            fidelity_limitation,
            "- Równy budżet pomiarowy nie oznacza równego kosztu bramek: overlap fidelity wykonuje dwie mapy cech na circuit-shot.",
            "- Projected noise używa poprawnych marginalnych rozkładów dwumianowych, ale pomija kowariancje wspólnych strzałów między kubitami.",
            "- Outer splity są powtarzanymi holdoutami i nakładają się; wyniki mają charakter eksploracyjny, nie potwierdzający.",
            "- Screening top-k może pominąć konfigurację o słabszym alignment, ale lepszym wyniku validation.",
            "- Wyniki nie dowodzą przewagi kwantowej.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nested Hamiltonian grid and equal-budget kernel experiment")
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--datasets", help="Comma-separated override")
    parser.add_argument("--seeds", help="Comma-separated outer split seeds")
    parser.add_argument("--budgets", help="Comma-separated total measurement budgets")
    parser.add_argument("--noise-replicates", type=int)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--landmarks", type=int)
    parser.add_argument("--n-qubits", type=int, default=4)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def configure_args(args: argparse.Namespace) -> argparse.Namespace:
    smoke = args.profile == "smoke"
    args.dataset_names = args.datasets.split(",") if args.datasets else (["moons"] if smoke else ["moons", "wdbc", "wine"])
    args.seed_values = [int(value) for value in args.seeds.split(",")] if args.seeds else ([0] if smoke else list(range(10)))
    args.budget_values = [int(value) for value in args.budgets.split(",")] if args.budgets else ([20_000] if smoke else [200_000, 1_000_000])
    args.noise_replicates = args.noise_replicates if args.noise_replicates is not None else (2 if smoke else 3)
    args.top_k = args.top_k if args.top_k is not None else (4 if smoke else 8)
    # Zero means all training samples. Positive values enable a Nystrom sensitivity analysis.
    args.landmarks = args.landmarks if args.landmarks is not None else 0
    estimator_suffix = "spectral" if args.landmarks == 0 else f"nystrom{args.landmarks}"
    args.output_dir = (
        args.output_dir
        or ROOT / "analysis_output" / f"hamiltonian_kernel_grid_{args.profile}_{estimator_suffix}"
    )
    if args.noise_replicates < 2:
        raise ValueError("At least two noise replicates are required by audit remediation A3")
    if args.n_qubits < 1:
        raise ValueError("n_qubits must be positive")
    if args.top_k < 1:
        raise ValueError("top_k must be positive")
    if args.landmarks < 0:
        raise ValueError("landmarks cannot be negative")
    if not args.dataset_names or any(not name for name in args.dataset_names):
        raise ValueError("At least one non-empty dataset name is required")
    if not args.seed_values:
        raise ValueError("At least one seed is required")
    if not args.budget_values or any(budget < 1 for budget in args.budget_values):
        raise ValueError("Measurement budgets must be positive")
    return args


def main() -> None:
    args = configure_args(parse_args())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates = candidate_grid(args.profile)
    screening_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    ideal_rows: list[dict[str, Any]] = []
    budget_rows: list[dict[str, Any]] = []
    started = time.perf_counter()

    for dataset_name in args.dataset_names:
        for seed in args.seed_values:
            dataset = load_dataset(dataset_name, seed=seed, smoke=args.profile == "smoke")
            data = prepare_dataset(dataset, n_components=args.n_qubits, seed=seed)
            required_circuits = fidelity_estimation_circuit_count(
                len(data.x_train) + len(data.x_val) + len(data.x_test),
                len(data.x_train),
                args.landmarks,
            )
            if min(args.budget_values) < required_circuits:
                raise ValueError(
                    f"Smallest budget {min(args.budget_values)} cannot cover the "
                    f"{required_circuits} fidelity circuits required for {data.name}"
                )
            selected, state_cache, split_screening, split_validation = screen_and_select_candidates(
                dataset_name=data.name,
                seed=seed,
                x_train=data.x_train,
                y_train=data.y_train,
                x_val=data.x_val,
                y_val=data.y_val,
                candidates=candidates,
                n_qubits=args.n_qubits,
                top_k=args.top_k,
            )
            screening_rows.extend(split_screening)
            validation_rows.extend(split_validation)

            for kernel in ("fidelity", "projected"):
                model = selected[kernel]
                ideal_row, all_states = evaluate_ideal_selected(
                    model,
                    data,
                    state_cache[model.candidate.name],
                    args.n_qubits,
                    seed,
                )
                ideal_rows.append(ideal_row)

                for budget in args.budget_values:
                    for replicate in range(args.noise_replicates):
                        budget_rows.append(
                            evaluate_budgeted_model(
                                model=model,
                                data=data,
                                all_states=all_states,
                                n_qubits=args.n_qubits,
                                seed=seed,
                                noise_replicate=replicate,
                                total_budget=budget,
                                landmark_count=args.landmarks,
                                artifact_dir=args.output_dir / "kernel_matrices",
                            )
                        )
            ideal_rows.append(evaluate_rbf(data, seed))

    ideal_summary = summarize_ideal(ideal_rows)
    budget_summary = summarize_budget(budget_rows)
    comparisons = budget_comparisons(budget_rows)
    frequencies = selection_frequencies(ideal_rows)

    write_csv(args.output_dir / "grid_screening.csv", screening_rows)
    write_csv(args.output_dir / "validation_finalists.csv", validation_rows)
    write_csv(args.output_dir / "selected_ideal_runs.csv", ideal_rows)
    write_csv(args.output_dir / "equal_budget_runs.csv", budget_rows)
    write_csv(args.output_dir / "ideal_summary.csv", ideal_summary)
    write_csv(args.output_dir / "equal_budget_summary.csv", budget_summary)
    write_csv(args.output_dir / "budget_comparisons.csv", comparisons)
    write_csv(args.output_dir / "selection_frequencies.csv", frequencies)

    serializable_arguments = {
        "profile": args.profile,
        "datasets": args.dataset_names,
        "seeds": args.seed_values,
        "budgets": args.budget_values,
        "noise_replicates": args.noise_replicates,
        "top_k": args.top_k,
        "landmarks": args.landmarks,
        "n_qubits": args.n_qubits,
        "output_dir": str(args.output_dir),
    }
    payload = {
        "audit_gate": "PASS_WITH_REQUIRED_REMEDIATIONS",
        "audit_remediations": {
            "A1": "Shared normalized spectral feature map for all fidelity splits",
            "A2": "Exact common total circuit-shot budget",
            "A3": f"{args.noise_replicates} noise replicates per outer split",
            "A4": "Repeated-holdout inference explicitly descriptive",
            "A5": "Train screening, validation selection, single final test evaluation",
        },
        "arguments": serializable_arguments,
        "candidate_count": len(candidates),
        "candidates": [asdict(candidate) | {"name": candidate.name} for candidate in candidates],
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "runtime_seconds": time.perf_counter() - started,
        "ideal_summary": ideal_summary,
        "equal_budget_summary": budget_summary,
        "budget_comparisons": comparisons,
        "selection_frequencies": frequencies,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_report(
        args.output_dir / "report.md",
        args,
        candidates,
        ideal_summary,
        budget_summary,
        comparisons,
        frequencies,
    )
    make_plots(args.output_dir, budget_summary, frequencies)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "candidate_count": len(candidates),
                "screening_rows": len(screening_rows),
                "ideal_runs": len(ideal_rows),
                "budget_runs": len(budget_rows),
                "runtime_seconds": payload["runtime_seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
