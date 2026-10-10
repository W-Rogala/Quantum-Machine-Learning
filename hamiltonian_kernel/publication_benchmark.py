from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.decomposition import PCA
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.kernel_approximation import RBFSampler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.svm import LinearSVC, SVC

from .core import bloch_vectors, circuit_resources, evolve_batch, fidelity_kernel, projected_kernel
from .data import Dataset, load_dataset
from .estimation import (
    estimate_fidelity_spectral,
    estimate_projected_bloch,
    fidelity_estimation_circuit_count,
    kernel_stages,
    resource_cost,
)
from .grid_experiment import (
    GAMMA_GRID,
    REGULARIZATION_GRID,
    HamiltonianCandidate,
    candidate_grid,
    stable_rng,
)
from .learning import fit_kernel_ridge, kernel_diagnostics, predict_kernel_ridge
from .protocol import (
    ConfirmatoryProtocol,
    cluster_sign_flip_test,
    freeze_protocol,
    hierarchical_paired_interval,
    load_frozen_protocol,
    protocol_for_profile,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "analysis_output" / "resource_aware_hamiltonian_benchmark"


class FoldPreprocessor:
    """Fold-local standardization, PCA and bounded angle scaling."""

    def __init__(self, n_components: int, seed: int) -> None:
        self.n_components = n_components
        self.seed = seed
        self.standardizer = StandardScaler()
        self.pca: PCA | None = None
        self.scaler = MinMaxScaler(feature_range=(-1.0, 1.0), clip=True)
        self.fitted_components = 0

    def fit(self, values: np.ndarray) -> FoldPreprocessor:
        standardized = self.standardizer.fit_transform(np.asarray(values, dtype=float))
        self.fitted_components = min(
            self.n_components,
            standardized.shape[0],
            standardized.shape[1],
        )
        self.pca = PCA(
            n_components=self.fitted_components,
            svd_solver="full",
            random_state=self.seed,
        )
        reduced = self.pca.fit_transform(standardized)
        self.scaler.fit(reduced)
        return self

    def transform(self, values: np.ndarray) -> np.ndarray:
        if self.pca is None:
            raise RuntimeError("Preprocessor has not been fitted")
        standardized = self.standardizer.transform(np.asarray(values, dtype=float))
        reduced = self.scaler.transform(self.pca.transform(standardized))
        if self.fitted_components < self.n_components:
            reduced = np.pad(
                reduced,
                ((0, 0), (0, self.n_components - self.fitted_components)),
            )
        return reduced


def _configuration_id(configuration: dict[str, Any]) -> str:
    canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _fixed_search_sample(
    space: list[dict[str, Any]],
    count: int,
    seed: int,
) -> list[dict[str, Any]]:
    if len(space) < count:
        raise ValueError(f"Search space has {len(space)} configurations, requires {count}")
    order = np.random.default_rng(seed).permutation(len(space))[:count]
    return [space[int(index)] for index in order]


def quantum_search_space(kernel: str, profile: str) -> list[dict[str, Any]]:
    configurations: list[dict[str, Any]] = []
    for candidate in candidate_grid(profile):
        gammas: tuple[float | None, ...] = (None,) if kernel == "fidelity" else GAMMA_GRID
        for gamma in gammas:
            for regularization in REGULARIZATION_GRID:
                configurations.append(
                    {
                        "candidate": asdict(candidate),
                        "candidate_name": candidate.name,
                        "gamma": gamma,
                        "regularization": regularization,
                    }
                )
    if kernel not in {"fidelity", "projected"}:
        raise ValueError("Unknown quantum kernel family")
    return configurations


def classical_search_space(family: str) -> list[dict[str, Any]]:
    c_values = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
    gamma_values = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
    if family == "svm_rbf":
        return [{"C": c, "gamma": gamma} for c in c_values for gamma in gamma_values]
    if family == "linear":
        return [
            {"estimator": estimator, "C": c}
            for estimator in ("logistic", "linear_svc")
            for c in c_values
        ]
    if family == "gradient_boosting":
        return [
            {"n_estimators": estimators, "learning_rate": rate, "max_depth": depth}
            for estimators in (50, 100, 200)
            for rate in (0.03, 0.1, 0.3)
            for depth in (1, 2, 3)
        ]
    if family == "random_fourier_features":
        return [
            {"gamma": gamma, "n_components": components, "C": c}
            for gamma in (0.03, 0.1, 0.3, 1.0, 3.0)
            for components in (64, 128, 256)
            for c in (0.1, 1.0, 10.0)
        ]
    raise ValueError(f"Unknown classical family: {family}")


def _candidate_from_configuration(configuration: dict[str, Any]) -> HamiltonianCandidate:
    return HamiltonianCandidate(**configuration["candidate"])


def _kernel_prediction(
    train_kernel: np.ndarray,
    y_train: np.ndarray,
    cross_kernel: np.ndarray,
    regularization: float,
) -> np.ndarray:
    coefficients, classes = fit_kernel_ridge(train_kernel, y_train, regularization)
    return predict_kernel_ridge(cross_kernel, coefficients, classes)


def _quantum_predict(
    kernel: str,
    configuration: dict[str, Any],
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_evaluation: np.ndarray,
    n_qubits: int,
) -> np.ndarray:
    candidate = _candidate_from_configuration(configuration)
    states = evolve_batch(np.vstack((x_train, x_evaluation)), candidate.config(n_qubits))
    train_count = len(x_train)
    if kernel == "fidelity":
        train_kernel = fidelity_kernel(states[:train_count], states[:train_count])
        cross_kernel = fidelity_kernel(states[train_count:], states[:train_count])
    else:
        vectors = bloch_vectors(states, n_qubits)
        gamma = float(configuration["gamma"])
        train_kernel = projected_kernel(vectors[:train_count], vectors[:train_count], gamma)
        cross_kernel = projected_kernel(vectors[train_count:], vectors[:train_count], gamma)
    return _kernel_prediction(
        train_kernel,
        y_train,
        cross_kernel,
        float(configuration["regularization"]),
    )


def _classical_estimator(
    family: str,
    configuration: dict[str, Any],
    seed: int,
) -> Any:
    if family == "svm_rbf":
        return SVC(
            C=float(configuration["C"]),
            gamma=float(configuration["gamma"]),
            kernel="rbf",
            class_weight="balanced",
        )
    if family == "linear" and configuration["estimator"] == "logistic":
        return LogisticRegression(
            C=float(configuration["C"]),
            class_weight="balanced",
            max_iter=5_000,
            random_state=seed,
        )
    if family == "linear":
        return LinearSVC(
            C=float(configuration["C"]),
            class_weight="balanced",
            dual="auto",
            max_iter=10_000,
            random_state=seed,
        )
    if family == "gradient_boosting":
        return GradientBoostingClassifier(
            n_estimators=int(configuration["n_estimators"]),
            learning_rate=float(configuration["learning_rate"]),
            max_depth=int(configuration["max_depth"]),
            random_state=seed,
        )
    if family == "random_fourier_features":
        return (
            RBFSampler(
                gamma=float(configuration["gamma"]),
                n_components=int(configuration["n_components"]),
                random_state=seed,
            ),
            LogisticRegression(
                C=float(configuration["C"]),
                class_weight="balanced",
                max_iter=5_000,
                random_state=seed,
            ),
        )
    raise ValueError(f"Unknown classical family: {family}")


def _classical_predict(
    family: str,
    configuration: dict[str, Any],
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_evaluation: np.ndarray,
    seed: int,
) -> np.ndarray:
    estimator = _classical_estimator(family, configuration, seed)
    if family == "random_fourier_features":
        feature_map, classifier = estimator
        train_features = feature_map.fit_transform(x_train)
        evaluation_features = feature_map.transform(x_evaluation)
        classifier.fit(train_features, y_train)
        return classifier.predict(evaluation_features)
    estimator.fit(x_train, y_train)
    return estimator.predict(x_evaluation)


def _nested_select(
    family: str,
    configurations: list[dict[str, Any]],
    x_outer_train: np.ndarray,
    y_outer_train: np.ndarray,
    inner_splits: list[tuple[np.ndarray, np.ndarray]],
    n_qubits: int,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    is_quantum = family in {"fidelity", "projected"}
    for configuration_index, configuration in enumerate(configurations):
        fold_scores: list[float] = []
        for inner_fold, (train_indices, validation_indices) in enumerate(inner_splits):
            preprocessing = FoldPreprocessor(n_qubits, seed + inner_fold).fit(
                x_outer_train[train_indices]
            )
            x_train = preprocessing.transform(x_outer_train[train_indices])
            x_validation = preprocessing.transform(x_outer_train[validation_indices])
            if is_quantum:
                prediction = _quantum_predict(
                    family,
                    configuration,
                    x_train,
                    y_outer_train[train_indices],
                    x_validation,
                    n_qubits,
                )
            else:
                prediction = _classical_predict(
                    family,
                    configuration,
                    x_train,
                    y_outer_train[train_indices],
                    x_validation,
                    seed + inner_fold + configuration_index * 101,
                )
            fold_scores.append(
                float(
                    balanced_accuracy_score(
                        y_outer_train[validation_indices],
                        prediction,
                    )
                )
            )
        rows.append(
            {
                "family": family,
                "configuration_id": _configuration_id(configuration),
                "configuration": configuration,
                "mean_inner_balanced_accuracy": float(np.mean(fold_scores)),
                "inner_fold_scores": fold_scores,
            }
        )
    selected = sorted(
        rows,
        key=lambda row: (-float(row["mean_inner_balanced_accuracy"]), str(row["configuration_id"])),
    )[0]
    return dict(selected["configuration"]), rows


def _metrics(y_true: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return {
        "test_accuracy": float(np.mean(prediction == y_true)),
        "test_balanced_accuracy": float(balanced_accuracy_score(y_true, prediction)),
        "test_macro_f1": float(f1_score(y_true, prediction, average="macro")),
    }


def _base_row(
    protocol_hash: str,
    dataset: str,
    repeat: int,
    fold: int,
    family: str,
    configuration: dict[str, Any],
    tuning_budget: int,
    inner_folds: int,
) -> dict[str, Any]:
    return {
        "protocol_hash": protocol_hash,
        "dataset": dataset,
        "outer_repeat": repeat,
        "outer_fold": fold,
        "family": family,
        "configuration_id": _configuration_id(configuration),
        "configuration_json": json.dumps(configuration, sort_keys=True, separators=(",", ":")),
        "tuning_configurations_evaluated": tuning_budget,
        "inner_fit_count": tuning_budget * inner_folds,
    }


def _save_quantum_artifact(
    path: Path,
    protocol_hash_value: str,
    payload: dict[str, np.ndarray],
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        protocol_hash=np.asarray(protocol_hash_value),
        **payload,
    )
    return str(path)


def _evaluate_quantum_outer(
    family: str,
    configuration: dict[str, Any],
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    protocol: ConfirmatoryProtocol,
    protocol_hash_value: str,
    dataset_name: str,
    repeat: int,
    fold: int,
    artifact_root: Path,
) -> list[dict[str, Any]]:
    candidate = _candidate_from_configuration(configuration)
    states = evolve_batch(np.vstack((x_train, x_test)), candidate.config(protocol.n_qubits))
    train_count = len(x_train)
    if family == "fidelity":
        ideal_train = fidelity_kernel(states[:train_count], states[:train_count])
        ideal_test = fidelity_kernel(states[train_count:], states[:train_count])
    else:
        vectors = bloch_vectors(states, protocol.n_qubits)
        gamma = float(configuration["gamma"])
        ideal_train = projected_kernel(vectors[:train_count], vectors[:train_count], gamma)
        ideal_test = projected_kernel(vectors[train_count:], vectors[:train_count], gamma)
    prediction = _kernel_prediction(
        ideal_train,
        y_train,
        ideal_test,
        float(configuration["regularization"]),
    )
    common = _base_row(
        protocol_hash_value,
        dataset_name,
        repeat,
        fold,
        family,
        configuration,
        protocol.tuning_configurations_per_family,
        protocol.inner_folds,
    )
    logical_resources = circuit_resources(candidate.config(protocol.n_qubits))
    rows = [
        {
            **common,
            "evaluation_regime": "ideal_statevector",
            "circuit_shot_budget": 0,
            "noise_replicate": -1,
            **_metrics(y_test, prediction),
            **resource_cost(0, 0, int(logical_resources["two_qubit_gates"])).as_dict(),
            "two_qubit_gates_per_map": int(logical_resources["two_qubit_gates"]),
            **kernel_diagnostics(ideal_train, float(configuration["regularization"])),
            "matrix_artifact": None,
        }
    ]

    for budget in protocol.circuit_shot_budgets:
        required = (
            fidelity_estimation_circuit_count(len(states), train_count, 0)
            if family == "fidelity"
            else len(states) * 3
        )
        if budget < required:
            raise ValueError(
                f"Frozen budget {budget} cannot cover {required} {family} circuits "
                f"for {dataset_name} repeat={repeat} fold={fold}"
            )
        for noise_replicate in range(protocol.noise_replicates):
            rng = stable_rng(
                protocol.base_seed,
                dataset_name,
                repeat,
                fold,
                family,
                budget,
                noise_replicate,
            )
            if family == "fidelity":
                estimate = estimate_fidelity_spectral(
                    states,
                    train_count,
                    np.arange(train_count),
                    budget,
                    rng,
                )
                train_features = estimate.features[:train_count]
                test_features = estimate.features[train_count:]
                train_kernel = train_features @ train_features.T
                test_kernel = test_features @ train_features.T
                diagnostics = estimate.diagnostics
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
                estimate = estimate_projected_bloch(
                    states,
                    protocol.n_qubits,
                    budget,
                    rng,
                )
                gamma = float(configuration["gamma"])
                raw_all = projected_kernel(estimate.bloch, estimate.bloch, gamma)
                stages = kernel_stages(raw_all)
                train_kernel = stages.raw[:train_count, :train_count]
                test_kernel = stages.raw[train_count:, :train_count]
                diagnostics = {
                    **estimate.diagnostics,
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
                    "sampled_bloch": estimate.bloch,
                    "shots_by_setting": estimate.shots_by_setting,
                }
            prediction = _kernel_prediction(
                train_kernel,
                y_train,
                test_kernel,
                float(configuration["regularization"]),
            )
            artifact = _save_quantum_artifact(
                artifact_root
                / dataset_name
                / f"repeat{repeat}_fold{fold}_{family}_budget{budget}_noise{noise_replicate}.npz",
                protocol_hash_value,
                artifact_payload,
            )
            costs = resource_cost(
                budget,
                2 if family == "fidelity" else 1,
                int(logical_resources["two_qubit_gates"]),
            )
            rows.append(
                {
                    **common,
                    "evaluation_regime": "finite_shot_simulator",
                    "circuit_shot_budget": budget,
                    "noise_replicate": noise_replicate,
                    **_metrics(y_test, prediction),
                    **costs.as_dict(),
                    "two_qubit_gates_per_map": int(logical_resources["two_qubit_gates"]),
                    **diagnostics,
                    **kernel_diagnostics(train_kernel, float(configuration["regularization"])),
                    "matrix_artifact": artifact,
                }
            )
    return rows


def _evaluate_classical_outer(
    family: str,
    configuration: dict[str, Any],
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    protocol: ConfirmatoryProtocol,
    protocol_hash_value: str,
    dataset_name: str,
    repeat: int,
    fold: int,
    seed: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    prediction = _classical_predict(
        family,
        configuration,
        x_train,
        y_train,
        x_test,
        seed,
    )
    return {
        **_base_row(
            protocol_hash_value,
            dataset_name,
            repeat,
            fold,
            family,
            configuration,
            protocol.tuning_configurations_per_family,
            protocol.inner_folds,
        ),
        "evaluation_regime": "classical",
        "circuit_shot_budget": 0,
        "noise_replicate": -1,
        **_metrics(y_test, prediction),
        **resource_cost(0, 0, 0).as_dict(),
        "classical_fit_predict_seconds": time.perf_counter() - started,
        "matrix_artifact": None,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _paired_deltas(rows: list[dict[str, Any]], budget: int) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row["evaluation_regime"] == "finite_shot_simulator"
        and int(row["circuit_shot_budget"]) == budget
    ]
    index = {
        (
            str(row["dataset"]),
            int(row["outer_repeat"]),
            int(row["outer_fold"]),
            int(row["noise_replicate"]),
            str(row["family"]),
        ): row
        for row in selected
    }
    pairs = sorted(
        {
            (key[0], key[1], key[2], key[3])
            for key in index
            if key[4] in {"fidelity", "projected"}
        }
    )
    deltas: list[dict[str, Any]] = []
    for dataset, repeat, fold, noise in pairs:
        fidelity = index[(dataset, repeat, fold, noise, "fidelity")]
        projected = index[(dataset, repeat, fold, noise, "projected")]
        deltas.append(
            {
                "dataset": dataset,
                "outer_repeat": repeat,
                "outer_fold": fold,
                "noise_replicate": noise,
                "circuit_shot_budget": budget,
                "fidelity_balanced_accuracy": float(fidelity["test_balanced_accuracy"]),
                "projected_balanced_accuracy": float(projected["test_balanced_accuracy"]),
                "delta": float(projected["test_balanced_accuracy"])
                - float(fidelity["test_balanced_accuracy"]),
            }
        )
    return deltas


def _summaries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row["family"]),
            str(row["evaluation_regime"]),
            int(row["circuit_shot_budget"]),
        )
        groups.setdefault(key, []).append(row)
    summary: list[dict[str, Any]] = []
    for (family, regime, budget), group in sorted(groups.items()):
        values = np.asarray([float(row["test_balanced_accuracy"]) for row in group])
        summary.append(
            {
                "family": family,
                "evaluation_regime": regime,
                "circuit_shot_budget": budget,
                "observations": len(group),
                "test_balanced_accuracy_mean": float(np.mean(values)),
                "test_balanced_accuracy_std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "tuning_configurations_per_family": int(
                    group[0]["tuning_configurations_evaluated"]
                ),
            }
        )
    return summary


def run_benchmark(protocol_path: Path, output_dir: Path) -> Path:
    protocol, frozen_payload = load_frozen_protocol(protocol_path)
    protocol_hash_value = str(frozen_payload["protocol_hash"])
    completion_path = output_dir / "completion.json"
    if completion_path.exists():
        raise FileExistsError(f"Confirmatory output already exists: {completion_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    tuning_rows: list[dict[str, Any]] = []
    classical_families = (
        "svm_rbf",
        "linear",
        "gradient_boosting",
        "random_fourier_features",
    )

    for dataset_name in protocol.datasets:
        dataset: Dataset = load_dataset(
            dataset_name,
            seed=protocol.base_seed,
            smoke=protocol.profile == "smoke",
        )
        outer = RepeatedStratifiedKFold(
            n_splits=protocol.outer_folds,
            n_repeats=protocol.outer_repeats,
            random_state=protocol.base_seed,
        )
        for split_index, (outer_train, outer_test) in enumerate(outer.split(dataset.x, dataset.y)):
            repeat, fold = divmod(split_index, protocol.outer_folds)
            split_seed = protocol.base_seed + split_index + 10_000 * repeat
            inner = StratifiedKFold(
                n_splits=protocol.inner_folds,
                shuffle=True,
                random_state=split_seed,
            )
            inner_splits = list(inner.split(dataset.x[outer_train], dataset.y[outer_train]))
            selected: dict[str, dict[str, Any]] = {}
            for family in ("fidelity", "projected", *classical_families):
                space = (
                    quantum_search_space(family, protocol.profile)
                    if family in {"fidelity", "projected"}
                    else classical_search_space(family)
                )
                configurations = _fixed_search_sample(
                    space,
                    protocol.tuning_configurations_per_family,
                    int(stable_rng(protocol.base_seed, dataset_name, repeat, fold, family).integers(2**31)),
                )
                selected[family], family_tuning = _nested_select(
                    family,
                    configurations,
                    dataset.x[outer_train],
                    dataset.y[outer_train],
                    inner_splits,
                    protocol.n_qubits,
                    split_seed,
                )
                for item in family_tuning:
                    tuning_rows.append(
                        {
                            "protocol_hash": protocol_hash_value,
                            "dataset": dataset_name,
                            "outer_repeat": repeat,
                            "outer_fold": fold,
                            "family": family,
                            "selected": item["configuration_id"]
                            == _configuration_id(selected[family]),
                            "configuration_id": item["configuration_id"],
                            "configuration_json": json.dumps(
                                item["configuration"], sort_keys=True, separators=(",", ":")
                            ),
                            "mean_inner_balanced_accuracy": item[
                                "mean_inner_balanced_accuracy"
                            ],
                            "inner_fold_scores_json": json.dumps(item["inner_fold_scores"]),
                        }
                    )

            preprocessing = FoldPreprocessor(protocol.n_qubits, split_seed).fit(
                dataset.x[outer_train]
            )
            x_train = preprocessing.transform(dataset.x[outer_train])
            x_test = preprocessing.transform(dataset.x[outer_test])
            split_path = (
                output_dir
                / "outer_splits"
                / f"{dataset_name}_repeat{repeat}_fold{fold}.npz"
            )
            split_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                split_path,
                protocol_hash=np.asarray(protocol_hash_value),
                train_indices=outer_train,
                test_indices=outer_test,
                x_train=x_train,
                y_train=dataset.y[outer_train],
                x_test=x_test,
                y_test=dataset.y[outer_test],
                standardizer_mean=preprocessing.standardizer.mean_,
                standardizer_scale=preprocessing.standardizer.scale_,
                pca_components=preprocessing.pca.components_,
                pca_mean=preprocessing.pca.mean_,
                angle_scale_min=preprocessing.scaler.data_min_,
                angle_scale_max=preprocessing.scaler.data_max_,
            )
            for family in ("fidelity", "projected"):
                family_rows = _evaluate_quantum_outer(
                        family,
                        selected[family],
                        x_train,
                        dataset.y[outer_train],
                        x_test,
                        dataset.y[outer_test],
                        protocol,
                        protocol_hash_value,
                        dataset_name,
                        repeat,
                        fold,
                        output_dir / "kernel_matrices",
                    )
                for row in family_rows:
                    row["split_artifact"] = str(split_path.resolve())
                rows.extend(family_rows)
            for family in classical_families:
                classical_row = _evaluate_classical_outer(
                        family,
                        selected[family],
                        x_train,
                        dataset.y[outer_train],
                        x_test,
                        dataset.y[outer_test],
                        protocol,
                        protocol_hash_value,
                        dataset_name,
                        repeat,
                        fold,
                        split_seed,
                    )
                classical_row["split_artifact"] = str(split_path.resolve())
                rows.append(classical_row)

    primary_budget = max(protocol.circuit_shot_budgets)
    deltas = _paired_deltas(rows, primary_budget)
    interval = hierarchical_paired_interval(
        deltas,
        alpha=protocol.alpha,
        resamples=protocol.bootstrap_resamples,
        seed=protocol.base_seed + 901,
    )
    test = cluster_sign_flip_test(
        deltas,
        resamples=protocol.permutation_resamples,
        seed=protocol.base_seed + 902,
    )
    primary_inference = {
        "contrast": protocol.primary_contrast,
        "metric": protocol.primary_metric,
        "circuit_shot_budget": primary_budget,
        "null_hypothesis": protocol.null_hypothesis,
        "alternative_hypothesis": protocol.alternative_hypothesis,
        "interval": interval,
        "test": test,
        "reject_null_at_alpha": float(test["p_value_one_sided"]) < protocol.alpha,
    }
    summaries = _summaries(rows)
    _write_csv(output_dir / "outer_results.csv", rows)
    _write_csv(output_dir / "inner_tuning.csv", tuning_rows)
    _write_csv(output_dir / "primary_paired_deltas.csv", deltas)
    _write_csv(output_dir / "summary.csv", summaries)
    completion = {
        "schema": "resource-aware-hamiltonian-kernel.results.v1",
        "status": "completed",
        "protocol_path": str(protocol_path.resolve()),
        "protocol_hash": protocol_hash_value,
        "confirmatory_scope": (
            "projected versus fidelity at the largest frozen budget only"
            if protocol.profile == "full"
            else "pipeline smoke test only; no confirmatory claim"
        ),
        "qpu_executed": False,
        "qpu_gate": (
            "eligible_for_separate_reproducible_pilot_after_review"
            if protocol.profile == "full"
            else "blocked_smoke_profile_is_not_confirmatory"
        ),
        "primary_inference": primary_inference,
        "summary": summaries,
        "row_count": len(rows),
        "tuning_row_count": len(tuning_rows),
        "outer_split_artifact_count": len(protocol.datasets)
        * protocol.outer_repeats
        * protocol.outer_folds,
        "runtime_seconds": time.perf_counter() - started,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": __import__("sklearn").__version__,
            "platform": platform.platform(),
        },
    }
    completion_path.write_text(
        json.dumps(completion, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return completion_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frozen resource-aware Hamiltonian-kernel benchmark")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Freeze hypothesis, budgets and statistical test")
    freeze.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    freeze.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run", help="Run a previously frozen protocol")
    run.add_argument("--protocol", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "freeze":
        payload = freeze_protocol(args.output, protocol_for_profile(args.profile))
        print(json.dumps({"status": "frozen", "path": str(args.output), "hash": payload["protocol_hash"]}, indent=2))
    elif args.command == "run":
        path = run_benchmark(args.protocol, args.output_dir)
        print(json.dumps({"status": "completed", "completion": str(path)}, indent=2))
    else:
        raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
