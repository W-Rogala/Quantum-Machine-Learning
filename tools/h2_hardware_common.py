from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis_output"
OUT_DIR = ROOT / "analysis_output"

if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from qml_hypothesis_experiment import (  # noqa: E402
    DatasetSpec,
    KernelConfig,
    centered_alignment,
    load_optdigits_3_vs_8,
    load_wdbc,
    load_wine_1_vs_2,
    offdiag_stats,
    preprocess_split,
    quantum_kernel,
    stratified_split,
)


DATASET_ALIASES = {
    "wdbc": load_wdbc,
    "breast_cancer": load_wdbc,
    "wine": load_wine_1_vs_2,
    "optdigits": load_optdigits_3_vs_8,
    "digits": load_optdigits_3_vs_8,
}


def load_dataset(alias: str) -> DatasetSpec:
    key = alias.strip().lower()
    if key not in DATASET_ALIASES:
        allowed = ", ".join(sorted(DATASET_ALIASES))
        raise ValueError(f"Nieznany zbior danych '{alias}'. Dostepne: {allowed}.")
    return DATASET_ALIASES[key]()


def _selected_h2_config(spec_name: str, seed: int) -> KernelConfig | None:
    path = OUT_DIR / "qml_iterative_hypothesis_selected_configs.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data.get(spec_name, []):
        if int(row.get("seed", -1)) == int(seed) and "H2" in row:
            cfg = row["H2"]
            return KernelConfig(
                qubits=int(cfg["qubits"]),
                angle_scale=float(cfg["angle_scale"]),
                entanglement=float(cfg["entanglement"]),
            )
    return None


def resolve_h2_config(
    spec: DatasetSpec,
    seed: int,
    qubits: int | None = None,
    angle_scale: float | None = None,
    entanglement: float | None = None,
) -> KernelConfig:
    selected = _selected_h2_config(spec.name, seed)
    if selected is None:
        selected = KernelConfig(qubits=4, angle_scale=0.5, entanglement=0.25)
    return KernelConfig(
        qubits=int(qubits if qubits is not None else selected.qubits),
        angle_scale=float(
            angle_scale if angle_scale is not None else selected.angle_scale
        ),
        entanglement=float(
            entanglement if entanglement is not None else selected.entanglement
        ),
    )


def balanced_subset_indices(
    y: np.ndarray,
    samples_per_class: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    chosen: list[int] = []
    for label in sorted(np.unique(y)):
        idx = np.flatnonzero(y == label)
        if len(idx) < samples_per_class:
            raise ValueError(
                f"Za malo probek klasy {label}: {len(idx)} < {samples_per_class}."
            )
        chosen.extend(rng.permutation(idx)[:samples_per_class].tolist())
    return rng.permutation(np.asarray(chosen, dtype=int))


def prepare_h2_problem(
    dataset_alias: str,
    seed: int = 20260709,
    samples_per_class: int = 3,
    qubits: int | None = None,
    angle_scale: float | None = None,
    entanglement: float | None = None,
) -> dict[str, Any]:
    spec = load_dataset(dataset_alias)
    cfg = resolve_h2_config(
        spec,
        seed,
        qubits=qubits,
        angle_scale=angle_scale,
        entanglement=entanglement,
    )
    if cfg.qubits < 4:
        raise ValueError("Hipoteza H2 wymaga co najmniej 4 kubitow.")

    train_idx, _, _ = stratified_split(spec.y, 0.60, 0.20, seed)
    x_train = spec.x[train_idx]
    y_train = spec.y[train_idx]
    subset_rel = balanced_subset_indices(y_train, samples_per_class, seed)
    x_subset_raw = x_train[subset_rel]
    y_subset = y_train[subset_rel]

    _, x_subset, pca_explained = preprocess_split(
        x_train,
        x_subset_raw,
        cfg.qubits,
    )
    reference_kernel, _ = quantum_kernel(x_subset, x_subset, cfg)
    diagnostics = kernel_diagnostics(reference_kernel, y_subset)

    return {
        "dataset": {
            "alias": dataset_alias,
            "name": spec.name,
            "positive_label": spec.positive_label,
            "negative_label": spec.negative_label,
        },
        "seed": seed,
        "samples_per_class": samples_per_class,
        "config": cfg,
        "x": x_subset,
        "y": y_subset,
        "pca_explained": pca_explained,
        "reference_kernel": reference_kernel,
        "reference_diagnostics": diagnostics,
    }


def kernel_diagnostics(kernel: np.ndarray, y: np.ndarray) -> dict[str, float]:
    symmetric = 0.5 * (kernel + kernel.T)
    eigvals = np.linalg.eigvalsh(symmetric)
    off_mean, off_std = offdiag_stats(symmetric)
    return {
        "alignment": centered_alignment(symmetric, y),
        "min_eigenvalue": float(np.min(eigvals)),
        "max_eigenvalue": float(np.max(eigvals)),
        "offdiag_mean": off_mean,
        "offdiag_std": off_std,
        "trace": float(np.trace(symmetric)),
    }


def config_to_dict(cfg: KernelConfig) -> dict[str, float | int]:
    return {
        "qubits": cfg.qubits,
        "state_dimension": 1 << cfg.qubits,
        "angle_scale": cfg.angle_scale,
        "entanglement": cfg.entanglement,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, KernelConfig):
        return config_to_dict(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
