from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets" / "qml_benchmarks"
OUT = ROOT / "analysis_output"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    x: np.ndarray
    y: np.ndarray
    positive_label: str
    negative_label: str


@dataclass(frozen=True)
class KernelConfig:
    qubits: int
    angle_scale: float
    entanglement: float


def load_wdbc() -> DatasetSpec:
    path = DATA / "breast_cancer_wisconsin_diagnostic" / "wdbc.data"
    rows = []
    labels = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if not parts or len(parts) < 3:
                continue
            labels.append(1 if parts[1] == "M" else -1)
            rows.append([float(v) for v in parts[2:]])
    return DatasetSpec(
        name="WDBC breast cancer: malignant vs benign",
        x=np.asarray(rows, dtype=float),
        y=np.asarray(labels, dtype=int),
        positive_label="malignant",
        negative_label="benign",
    )


def load_wine_1_vs_2() -> DatasetSpec:
    path = DATA / "wine" / "wine.data"
    rows = []
    labels = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if not parts:
                continue
            klass = int(parts[0])
            if klass not in (1, 2):
                continue
            labels.append(1 if klass == 1 else -1)
            rows.append([float(v) for v in parts[1:]])
    return DatasetSpec(
        name="Wine: class 1 vs class 2",
        x=np.asarray(rows, dtype=float),
        y=np.asarray(labels, dtype=int),
        positive_label="class 1",
        negative_label="class 2",
    )


def load_optdigits_3_vs_8(max_per_class: int = 220, seed: int = 7) -> DatasetSpec:
    paths = [
        DATA / "optdigits" / "optdigits.tra",
        DATA / "optdigits" / "optdigits.tes",
    ]
    rows_by_label = {3: [], 8: []}
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if not parts:
                    continue
                klass = int(parts[-1])
                if klass in rows_by_label:
                    rows_by_label[klass].append([float(v) for v in parts[:-1]])

    rng = np.random.default_rng(seed)
    rows = []
    labels = []
    for klass, sign in [(3, 1), (8, -1)]:
        items = np.asarray(rows_by_label[klass], dtype=float)
        order = rng.permutation(len(items))[:max_per_class]
        rows.extend(items[order])
        labels.extend([sign] * len(order))

    return DatasetSpec(
        name=f"OptDigits: digit 3 vs digit 8, capped at {max_per_class}/class",
        x=np.asarray(rows, dtype=float),
        y=np.asarray(labels, dtype=int),
        positive_label="digit 3",
        negative_label="digit 8",
    )


def stratified_split(y: np.ndarray, train_frac: float, val_frac: float, seed: int):
    rng = np.random.default_rng(seed)
    train_idx = []
    val_idx = []
    test_idx = []
    for label in np.unique(y):
        idx = np.flatnonzero(y == label)
        idx = rng.permutation(idx)
        n_train = int(round(train_frac * len(idx)))
        n_val = int(round(val_frac * len(idx)))
        train_idx.extend(idx[:n_train])
        val_idx.extend(idx[n_train : n_train + n_val])
        test_idx.extend(idx[n_train + n_val :])
    return (
        rng.permutation(train_idx),
        rng.permutation(val_idx),
        rng.permutation(test_idx),
    )


def standardize_fit(x: np.ndarray):
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std < 1e-12] = 1.0
    return mean, std


def pca_fit(x: np.ndarray, n_components: int):
    centered = x - x.mean(axis=0, keepdims=True)
    cov = centered.T @ centered / max(1, len(x) - 1)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    comps = vecs[:, order[:n_components]]
    explained = vals[order[:n_components]].sum() / max(vals.sum(), 1e-12)
    return comps, float(explained)


def minmax_fit(x: np.ndarray):
    lo = x.min(axis=0)
    hi = x.max(axis=0)
    width = hi - lo
    width[width < 1e-12] = 1.0
    return lo, width


def preprocess_split(x_train, x_eval, qubits: int):
    mean, std = standardize_fit(x_train)
    x_train_s = (x_train - mean) / std
    x_eval_s = (x_eval - mean) / std
    comps, explained = pca_fit(x_train_s, qubits)
    z_train = x_train_s @ comps
    z_eval = x_eval_s @ comps
    lo, width = minmax_fit(z_train)
    z_train = np.clip((z_train - lo) / width, 0.0, 1.0)
    z_eval = np.clip((z_eval - lo) / width, 0.0, 1.0)
    return z_train, z_eval, explained


def zz_feature_states(x: np.ndarray, cfg: KernelConfig) -> np.ndarray:
    n_samples, n_qubits = x.shape
    dim = 1 << n_qubits
    angles = np.pi * cfg.angle_scale * x

    basis = np.arange(dim, dtype=np.uint32)
    z = np.empty((dim, n_qubits), dtype=float)
    for q in range(n_qubits):
        z[:, q] = 1.0 - 2.0 * ((basis >> q) & 1)

    linear_phase = angles @ z.T
    phase = linear_phase

    if cfg.entanglement > 0.0 and n_qubits > 1:
        pair_phase = np.zeros((n_samples, dim), dtype=float)
        pair_angles = np.pi - angles
        for a in range(n_qubits - 1):
            for b in range(a + 1, n_qubits):
                pair_phase += (
                    pair_angles[:, [a]]
                    * pair_angles[:, [b]]
                    * (z[:, a] * z[:, b])[None, :]
                )
        phase = phase + cfg.entanglement * pair_phase

    return np.exp(1j * phase) / math.sqrt(dim)


def quantum_kernel(x_a: np.ndarray, x_b: np.ndarray, cfg: KernelConfig):
    t0 = time.perf_counter()
    states_a = zz_feature_states(x_a, cfg)
    states_b = zz_feature_states(x_b, cfg)
    overlaps = states_a @ states_b.conj().T
    kernel = np.abs(overlaps) ** 2
    return kernel.real, time.perf_counter() - t0


def rbf_kernel(x_a: np.ndarray, x_b: np.ndarray, gamma: float):
    aa = np.sum(x_a * x_a, axis=1)[:, None]
    bb = np.sum(x_b * x_b, axis=1)[None, :]
    dist2 = np.maximum(aa + bb - 2.0 * (x_a @ x_b.T), 0.0)
    return np.exp(-gamma * dist2)


def median_gamma(x: np.ndarray):
    aa = np.sum(x * x, axis=1)[:, None]
    dist2 = np.maximum(aa + aa.T - 2.0 * (x @ x.T), 0.0)
    tri = dist2[np.triu_indices_from(dist2, k=1)]
    med = np.median(tri[tri > 1e-12]) if np.any(tri > 1e-12) else 1.0
    return 1.0 / max(med, 1e-12)


def centered_alignment(k: np.ndarray, y: np.ndarray) -> float:
    labels = np.outer(y, y).astype(float)
    h = np.eye(len(y)) - np.ones_like(k) / len(y)
    kc = h @ k @ h
    yc = h @ labels @ h
    denom = np.linalg.norm(kc, "fro") * np.linalg.norm(yc, "fro")
    if denom < 1e-12:
        return 0.0
    return float(np.sum(kc * yc) / denom)


def offdiag_stats(k: np.ndarray):
    vals = k[np.triu_indices_from(k, k=1)]
    return float(vals.mean()), float(vals.std())


def train_lssvm(k: np.ndarray, y: np.ndarray, gamma: float = 10.0):
    n = len(y)
    yy = y[:, None] * y[None, :]
    a = np.empty((n + 1, n + 1), dtype=float)
    a[0, 0] = 0.0
    a[0, 1:] = y
    a[1:, 0] = y
    a[1:, 1:] = yy * k + np.eye(n) / gamma
    rhs = np.concatenate([[0.0], np.ones(n)])
    try:
        sol = np.linalg.solve(a, rhs)
    except np.linalg.LinAlgError:
        sol = np.linalg.lstsq(a, rhs, rcond=None)[0]
    return sol[0], sol[1:]


def predict_lssvm(k_eval_train: np.ndarray, y_train: np.ndarray, alpha: np.ndarray, bias: float):
    scores = (k_eval_train * y_train[None, :]) @ alpha + bias
    pred = np.where(scores >= 0.0, 1, -1)
    return pred, scores


def metrics(y_true: np.ndarray, y_pred: np.ndarray):
    acc = float(np.mean(y_true == y_pred))
    recalls = []
    precisions = []
    f1s = []
    for label in [-1, 1]:
        tp = np.sum((y_true == label) & (y_pred == label))
        fp = np.sum((y_true != label) & (y_pred == label))
        fn = np.sum((y_true == label) & (y_pred != label))
        recall = tp / max(tp + fn, 1)
        precision = tp / max(tp + fp, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-12)
        recalls.append(recall)
        precisions.append(precision)
        f1s.append(f1)
    return {
        "accuracy": acc,
        "balanced_accuracy": float(np.mean(recalls)),
        "macro_precision": float(np.mean(precisions)),
        "macro_f1": float(np.mean(f1s)),
    }


def evaluate_quantum_model(spec: DatasetSpec, cfg: KernelConfig, split_seed: int):
    train_idx, val_idx, test_idx = stratified_split(spec.y, 0.60, 0.20, split_seed)
    fit_idx = np.concatenate([train_idx, val_idx])
    x_fit = spec.x[fit_idx]
    y_fit = spec.y[fit_idx]
    x_test = spec.x[test_idx]
    y_test = spec.y[test_idx]

    x_fit_p, x_test_p, explained = preprocess_split(x_fit, x_test, cfg.qubits)
    k_fit, kernel_time = quantum_kernel(x_fit_p, x_fit_p, cfg)
    k_test, test_kernel_time = quantum_kernel(x_test_p, x_fit_p, cfg)
    t0 = time.perf_counter()
    bias, alpha = train_lssvm(k_fit, y_fit)
    train_time = time.perf_counter() - t0
    pred, _ = predict_lssvm(k_test, y_fit, alpha, bias)
    out = metrics(y_test, pred)
    off_mean, off_std = offdiag_stats(k_fit)
    out.update(
        {
            "qubits": cfg.qubits,
            "state_dimension": 1 << cfg.qubits,
            "angle_scale": cfg.angle_scale,
            "entanglement": cfg.entanglement,
            "pca_explained": explained,
            "alignment_fit": centered_alignment(k_fit, y_fit),
            "offdiag_mean": off_mean,
            "offdiag_std": off_std,
            "kernel_time_s": kernel_time + test_kernel_time,
            "train_time_s": train_time,
            "fit_samples": len(fit_idx),
            "test_samples": len(test_idx),
        }
    )
    return out


def select_alignment_config(spec: DatasetSpec, split_seed: int):
    train_idx, val_idx, _ = stratified_split(spec.y, 0.60, 0.20, split_seed)
    x_select = spec.x[train_idx]
    y_select = spec.y[train_idx]

    max_qubits = min(8, spec.x.shape[1], max(2, len(train_idx) - 1))
    qubit_grid = [q for q in [2, 4, 6, 8] if q <= max_qubits]
    if not qubit_grid:
        qubit_grid = [min(max_qubits, 2)]

    candidates = []
    for qubits in qubit_grid:
        x_train_p, x_val_p, explained = preprocess_split(x_select, spec.x[val_idx], qubits)
        del x_val_p
        for angle_scale in [0.35, 0.50, 0.75, 1.00, 1.25, 1.50]:
            for entanglement in [0.00, 0.10, 0.25, 0.50, 1.00]:
                cfg = KernelConfig(qubits, angle_scale, entanglement)
                k_train, kernel_time = quantum_kernel(x_train_p, x_train_p, cfg)
                alignment = centered_alignment(k_train, y_select)
                off_mean, off_std = offdiag_stats(k_train)
                candidates.append(
                    {
                        "cfg": cfg,
                        "alignment": alignment,
                        "pca_explained": explained,
                        "offdiag_mean": off_mean,
                        "offdiag_std": off_std,
                        "kernel_time_s": kernel_time,
                    }
                )

    best_alignment = max(c["alignment"] for c in candidates)
    threshold = 0.95 * best_alignment
    near_best = [c for c in candidates if c["alignment"] >= threshold]
    selected = sorted(
        near_best,
        key=lambda c: (
            c["cfg"].qubits,
            c["cfg"].entanglement,
            -c["alignment"],
            c["cfg"].angle_scale,
        ),
    )[0]
    selected["best_alignment"] = best_alignment
    selected["threshold"] = threshold
    selected["candidate_count"] = len(candidates)
    return selected, candidates


def evaluate_rbf_baseline(spec: DatasetSpec, split_seed: int, qubits: int):
    train_idx, val_idx, test_idx = stratified_split(spec.y, 0.60, 0.20, split_seed)
    fit_idx = np.concatenate([train_idx, val_idx])
    x_fit = spec.x[fit_idx]
    y_fit = spec.y[fit_idx]
    x_test = spec.x[test_idx]
    y_test = spec.y[test_idx]
    x_fit_p, x_test_p, explained = preprocess_split(x_fit, x_test, qubits)
    gamma = median_gamma(x_fit_p)
    t0 = time.perf_counter()
    k_fit = rbf_kernel(x_fit_p, x_fit_p, gamma)
    k_test = rbf_kernel(x_test_p, x_fit_p, gamma)
    kernel_time = time.perf_counter() - t0
    t1 = time.perf_counter()
    bias, alpha = train_lssvm(k_fit, y_fit)
    train_time = time.perf_counter() - t1
    pred, _ = predict_lssvm(k_test, y_fit, alpha, bias)
    out = metrics(y_test, pred)
    off_mean, off_std = offdiag_stats(k_fit)
    out.update(
        {
            "qubits": qubits,
            "state_dimension": None,
            "angle_scale": None,
            "entanglement": None,
            "pca_explained": explained,
            "alignment_fit": centered_alignment(k_fit, y_fit),
            "offdiag_mean": off_mean,
            "offdiag_std": off_std,
            "kernel_time_s": kernel_time,
            "train_time_s": train_time,
            "fit_samples": len(fit_idx),
            "test_samples": len(test_idx),
            "rbf_gamma": gamma,
        }
    )
    return out


def main():
    split_seed = 20260709
    datasets = [load_wdbc(), load_wine_1_vs_2(), load_optdigits_3_vs_8()]
    rows = []
    candidate_dump = {}

    for spec in datasets:
        selected, candidates = select_alignment_config(spec, split_seed)
        candidate_dump[spec.name] = [
            {
                "qubits": c["cfg"].qubits,
                "state_dimension": 1 << c["cfg"].qubits,
                "angle_scale": c["cfg"].angle_scale,
                "entanglement": c["cfg"].entanglement,
                "alignment": c["alignment"],
                "pca_explained": c["pca_explained"],
                "offdiag_mean": c["offdiag_mean"],
                "offdiag_std": c["offdiag_std"],
                "kernel_time_s": c["kernel_time_s"],
            }
            for c in sorted(candidates, key=lambda c: c["alignment"], reverse=True)[:15]
        ]

        max_default_qubits = min(6, spec.x.shape[1])
        default_cfg = KernelConfig(max_default_qubits, 1.0, 1.0)
        selected_cfg = selected["cfg"]

        for method, cfg in [
            ("default_quantum_kernel", default_cfg),
            ("alignment_selected_quantum_kernel", selected_cfg),
        ]:
            result = evaluate_quantum_model(spec, cfg, split_seed)
            result.update(
                {
                    "dataset": spec.name,
                    "method": method,
                    "selected_by_alignment": method.startswith("alignment"),
                    "selection_train_alignment": selected["alignment"]
                    if method.startswith("alignment")
                    else None,
                    "selection_best_alignment": selected["best_alignment"]
                    if method.startswith("alignment")
                    else None,
                    "selection_threshold": selected["threshold"]
                    if method.startswith("alignment")
                    else None,
                    "candidate_count": selected["candidate_count"]
                    if method.startswith("alignment")
                    else None,
                }
            )
            rows.append(result)

        rbf_result = evaluate_rbf_baseline(spec, split_seed, selected_cfg.qubits)
        rbf_result.update(
            {
                "dataset": spec.name,
                "method": "classical_rbf_kernel_same_pca_dim",
                "selected_by_alignment": False,
                "selection_train_alignment": None,
                "selection_best_alignment": None,
                "selection_threshold": None,
                "candidate_count": None,
            }
        )
        rows.append(rbf_result)

    fieldnames = [
        "dataset",
        "method",
        "accuracy",
        "balanced_accuracy",
        "macro_precision",
        "macro_f1",
        "qubits",
        "state_dimension",
        "angle_scale",
        "entanglement",
        "pca_explained",
        "alignment_fit",
        "offdiag_mean",
        "offdiag_std",
        "kernel_time_s",
        "train_time_s",
        "fit_samples",
        "test_samples",
        "selected_by_alignment",
        "selection_train_alignment",
        "selection_best_alignment",
        "selection_threshold",
        "candidate_count",
        "rbf_gamma",
    ]

    out_csv = OUT / "qml_hypothesis_results.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})

    out_json = OUT / "qml_hypothesis_candidates.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(candidate_dump, f, indent=2)

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_json}")
    for row in rows:
        print(
            row["dataset"],
            row["method"],
            "bal_acc=",
            f"{row['balanced_accuracy']:.4f}",
            "qubits=",
            row["qubits"],
            "scale=",
            row["angle_scale"],
            "ent=",
            row["entanglement"],
        )


if __name__ == "__main__":
    main()
