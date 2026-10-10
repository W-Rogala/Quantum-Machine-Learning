from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


PROTOCOL_SCHEMA = "resource-aware-hamiltonian-kernel.protocol.v1"


@dataclass(frozen=True)
class ConfirmatoryProtocol:
    profile: str
    datasets: tuple[str, ...]
    n_qubits: int
    outer_repeats: int
    outer_folds: int
    inner_folds: int
    noise_replicates: int
    tuning_configurations_per_family: int
    circuit_shot_budgets: tuple[int, ...]
    bootstrap_resamples: int
    permutation_resamples: int
    base_seed: int = 20260818
    alpha: float = 0.05
    primary_metric: str = "balanced_accuracy"
    primary_contrast: str = "projected_minus_fidelity"
    primary_budget_rule: str = "largest_frozen_circuit_shot_budget"
    null_hypothesis: str = "mean paired delta balanced_accuracy <= 0"
    alternative_hypothesis: str = "mean paired delta balanced_accuracy > 0"
    primary_test: str = "one-sided sign-flip test over dataset-repeat clusters"
    confidence_interval: str = (
        "two-sided hierarchical percentile bootstrap, datasets fixed, "
        "resampling repeat/fold/noise levels"
    )
    matrix_policy: str = "publish raw, eigenvalue-clipped PSD, and truncated spectral matrices"
    qpu_policy: str = "QPU pilot is validation only and starts after protocol completion"
    qpu_pilot_dataset: str = "moons"
    qpu_pilot_outer_repeat: int = 0
    qpu_pilot_outer_fold: int = 0
    qpu_pilot_kernels: tuple[str, ...] = ("fidelity", "projected")
    qpu_pilot_circuit_shots_per_kernel: int = 20_000
    qpu_pilot_train_per_class: int = 3
    qpu_pilot_test_per_class: int = 2
    qpu_pilot_sample_seed: int = 20260901
    qpu_pilot_measurement_seed: int = 20260902
    qpu_pilot_transpile_seed: int = 20260903
    qpu_pilot_optimization_level: int = 1

    def validate(self) -> None:
        if self.profile not in {"smoke", "full"}:
            raise ValueError("profile must be 'smoke' or 'full'")
        if not self.datasets or len(set(self.datasets)) != len(self.datasets):
            raise ValueError("datasets must be non-empty and unique")
        if self.n_qubits < 1:
            raise ValueError("n_qubits must be positive")
        if self.outer_repeats < 2 or self.outer_folds < 2 or self.inner_folds < 2:
            raise ValueError("Nested repeated CV requires at least two repeats/folds")
        if self.noise_replicates < 2:
            raise ValueError("At least two shot-noise replicates are required")
        if self.tuning_configurations_per_family < 1:
            raise ValueError("The tuning budget must be positive")
        if not self.circuit_shot_budgets or any(value < 1 for value in self.circuit_shot_budgets):
            raise ValueError("Circuit-shot budgets must be positive")
        if tuple(sorted(set(self.circuit_shot_budgets))) != self.circuit_shot_budgets:
            raise ValueError("Circuit-shot budgets must be unique and increasing")
        if self.bootstrap_resamples < 100 or self.permutation_resamples < 100:
            raise ValueError("Inference requires at least 100 resamples")
        if not 0.0 < self.alpha < 0.5:
            raise ValueError("alpha must be in (0, 0.5)")
        if self.qpu_pilot_dataset not in self.datasets:
            raise ValueError("QPU pilot dataset must be one of the frozen datasets")
        if self.qpu_pilot_outer_repeat not in range(self.outer_repeats):
            raise ValueError("QPU pilot repeat is outside the frozen outer CV")
        if self.qpu_pilot_outer_fold not in range(self.outer_folds):
            raise ValueError("QPU pilot fold is outside the frozen outer CV")
        if set(self.qpu_pilot_kernels) != {"fidelity", "projected"}:
            raise ValueError("QPU pilot must contain fidelity and projected workloads")
        if self.qpu_pilot_circuit_shots_per_kernel < 1:
            raise ValueError("QPU pilot circuit-shot budget must be positive")
        if self.qpu_pilot_train_per_class < 1 or self.qpu_pilot_test_per_class < 1:
            raise ValueError("QPU pilot sample counts must be positive")
        if min(
            self.qpu_pilot_sample_seed,
            self.qpu_pilot_measurement_seed,
            self.qpu_pilot_transpile_seed,
        ) < 0:
            raise ValueError("QPU pilot seeds cannot be negative")
        if self.qpu_pilot_optimization_level not in {0, 1, 2, 3}:
            raise ValueError("Invalid QPU pilot optimization level")


def protocol_for_profile(profile: str) -> ConfirmatoryProtocol:
    if profile == "smoke":
        return ConfirmatoryProtocol(
            profile="smoke",
            datasets=("moons",),
            n_qubits=4,
            outer_repeats=2,
            outer_folds=3,
            inner_folds=2,
            noise_replicates=2,
            tuning_configurations_per_family=4,
            circuit_shot_budgets=(20_000,),
            bootstrap_resamples=500,
            permutation_resamples=1_000,
        )
    if profile == "full":
        return ConfirmatoryProtocol(
            profile="full",
            datasets=("moons", "wdbc", "wine"),
            n_qubits=4,
            outer_repeats=5,
            outer_folds=5,
            inner_folds=3,
            noise_replicates=5,
            tuning_configurations_per_family=12,
            circuit_shot_budgets=(200_000, 1_000_000),
            bootstrap_resamples=10_000,
            permutation_resamples=100_000,
        )
    raise ValueError(f"Unknown profile: {profile}")


def _canonical_protocol_payload(protocol: ConfirmatoryProtocol) -> dict[str, Any]:
    protocol.validate()
    return {
        "schema": PROTOCOL_SCHEMA,
        "status": "frozen",
        "study": "publication benchmark of resource-aware Hamiltonian kernels",
        "hypothesis_family": "confirmatory primary contrast with descriptive secondary models",
        "protocol": asdict(protocol),
        "model_families": [
            "hamiltonian_fidelity",
            "hamiltonian_projected",
            "svm_rbf",
            "linear",
            "gradient_boosting",
            "random_fourier_features",
        ],
        "cost_axes": [
            "circuit_shots",
            "map_executions",
            "two_qubit_gate_shots",
            "qpu_time_seconds_or_provider_credits",
        ],
        "tuning_budget_definition": (
            "Each model family evaluates exactly the frozen number of hyperparameter "
            "configurations on the same inner folds."
        ),
        "multiplicity_policy": (
            "Only projected-minus-fidelity at the largest frozen budget is confirmatory; "
            "all baseline contrasts and lower budgets are secondary/descriptive."
        ),
    }


def protocol_hash(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "protocol_hash"}
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def freeze_protocol(path: Path, protocol: ConfirmatoryProtocol) -> dict[str, Any]:
    """Create an immutable manifest or verify an identical existing one."""

    payload = json.loads(
        json.dumps(_canonical_protocol_payload(protocol), ensure_ascii=True, allow_nan=False)
    )
    payload["protocol_hash"] = protocol_hash(payload)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if (
            protocol_hash(existing) != existing.get("protocol_hash")
            or existing.get("protocol_hash") != payload["protocol_hash"]
        ):
            raise FileExistsError(
                f"Frozen protocol differs from the requested protocol: {path}"
            )
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def load_frozen_protocol(path: Path) -> tuple[ConfirmatoryProtocol, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != PROTOCOL_SCHEMA or payload.get("status") != "frozen":
        raise ValueError("Not a frozen confirmatory protocol")
    if protocol_hash(payload) != payload.get("protocol_hash"):
        raise ValueError("Frozen protocol hash mismatch")
    values = dict(payload["protocol"])
    values["datasets"] = tuple(values["datasets"])
    values["circuit_shot_budgets"] = tuple(values["circuit_shot_budgets"])
    if "qpu_pilot_kernels" in values:
        values["qpu_pilot_kernels"] = tuple(values["qpu_pilot_kernels"])
    protocol = ConfirmatoryProtocol(**values)
    protocol.validate()
    return protocol, payload


def _nested_cluster_mean(
    rows: list[dict[str, Any]],
    rng: np.random.Generator,
) -> float:
    """Bootstrap repeats, folds and noise while retaining datasets as fixed strata."""

    dataset_means: list[float] = []
    for dataset in sorted({str(row["dataset"]) for row in rows}):
        dataset_rows = [row for row in rows if str(row["dataset"]) == dataset]
        repeats = sorted({int(row["outer_repeat"]) for row in dataset_rows})
        selected_repeats = rng.choice(repeats, size=len(repeats), replace=True)
        repeat_means: list[float] = []
        for repeat in selected_repeats:
            repeat_rows = [
                row for row in dataset_rows if int(row["outer_repeat"]) == int(repeat)
            ]
            folds = sorted({int(row["outer_fold"]) for row in repeat_rows})
            selected_folds = rng.choice(folds, size=len(folds), replace=True)
            fold_means: list[float] = []
            for fold in selected_folds:
                fold_values = np.asarray(
                    [
                        float(row["delta"])
                        for row in repeat_rows
                        if int(row["outer_fold"]) == int(fold)
                    ],
                    dtype=float,
                )
                selected = rng.choice(fold_values, size=len(fold_values), replace=True)
                fold_means.append(float(np.mean(selected)))
            repeat_means.append(float(np.mean(fold_means)))
        dataset_means.append(float(np.mean(repeat_means)))
    return float(np.mean(dataset_means))


def hierarchical_paired_interval(
    delta_rows: Iterable[dict[str, Any]],
    *,
    alpha: float,
    resamples: int,
    seed: int,
) -> dict[str, float | int | str]:
    rows = list(delta_rows)
    if not rows:
        raise ValueError("At least one paired delta is required")
    required = {"dataset", "outer_repeat", "outer_fold", "noise_replicate", "delta"}
    if any(not required.issubset(row) for row in rows):
        raise ValueError(f"Delta rows require fields: {sorted(required)}")
    dataset_point_estimates = []
    for dataset in sorted({str(row["dataset"]) for row in rows}):
        dataset_point_estimates.append(
            float(np.mean([float(row["delta"]) for row in rows if row["dataset"] == dataset]))
        )
    point = float(np.mean(dataset_point_estimates))
    rng = np.random.default_rng(seed)
    draws = np.asarray([_nested_cluster_mean(rows, rng) for _ in range(resamples)])
    lower, upper = np.quantile(draws, [alpha / 2.0, 1.0 - alpha / 2.0])
    return {
        "estimate": point,
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "confidence_level": 1.0 - alpha,
        "bootstrap_resamples": resamples,
        "hierarchy": "datasets fixed; repeat > fold > shot-noise replicate resampled",
    }


def cluster_sign_flip_test(
    delta_rows: Iterable[dict[str, Any]],
    *,
    resamples: int,
    seed: int,
) -> dict[str, float | int | str]:
    """One-sided randomization test using dataset-repeat clusters as exchangeable units."""

    rows = list(delta_rows)
    grouped: dict[tuple[str, int], list[float]] = {}
    for row in rows:
        key = (str(row["dataset"]), int(row["outer_repeat"]))
        grouped.setdefault(key, []).append(float(row["delta"]))
    cluster_means = np.asarray([np.mean(grouped[key]) for key in sorted(grouped)], dtype=float)
    if len(cluster_means) < 2:
        raise ValueError("At least two dataset-repeat clusters are required")
    observed = float(np.mean(cluster_means))
    rng = np.random.default_rng(seed)
    exceedances = 0
    for _ in range(resamples):
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=len(cluster_means))
        exceedances += float(np.mean(signs * cluster_means)) >= observed - 1e-15
    return {
        "estimate": observed,
        "p_value_one_sided": (exceedances + 1) / (resamples + 1),
        "permutation_resamples": resamples,
        "cluster_count": len(cluster_means),
        "exchangeability_unit": "dataset-repeat",
    }
