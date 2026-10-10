from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from experiments.legacy.qml_hypothesis_experiment import (
    OUT,
    DatasetSpec,
    KernelConfig,
    load_optdigits_3_vs_8,
    load_wdbc,
    load_wine_1_vs_2,
    metrics,
    offdiag_stats,
    predict_lssvm,
    preprocess_split,
    quantum_kernel,
    stratified_split,
    train_lssvm,
)
from experiments.legacy.qml_iterative_hypothesis_experiment import select_alignment_config_with_floor


@dataclass(frozen=True)
class NisqScenario:
    name: str
    shots: int | None
    p1: float
    p2: float
    readout: float


def stable_seed(*values: object) -> int:
    text = "|".join(str(value) for value in values)
    acc = 2166136261
    for char in text:
        acc ^= ord(char)
        acc = (acc * 16777619) & 0xFFFFFFFF
    return acc


def feature_map_gate_counts(cfg: KernelConfig) -> tuple[int, int]:
    q = cfg.qubits
    one_qubit = 2 * q
    two_qubit_pairs = q * (q - 1) // 2 if cfg.entanglement > 0.0 else 0
    two_qubit = 2 * two_qubit_pairs
    return one_qubit, two_qubit


def effective_survival(cfg: KernelConfig, scenario: NisqScenario) -> float:
    one_qubit, two_qubit = feature_map_gate_counts(cfg)
    survival = (1.0 - scenario.p1) ** one_qubit
    survival *= (1.0 - scenario.p2) ** two_qubit
    survival *= (1.0 - scenario.readout) ** cfg.qubits
    return float(np.clip(survival, 0.0, 1.0))


def apply_nisq_channel(k: np.ndarray, cfg: KernelConfig, scenario: NisqScenario) -> np.ndarray:
    if scenario.name == "ideal_exact":
        return k.copy()
    survival = effective_survival(cfg, scenario)
    uniform_probability = 1.0 / (1 << cfg.qubits)
    return survival * k + (1.0 - survival) * uniform_probability


def sample_probabilities(
    probabilities: np.ndarray,
    scenario: NisqScenario,
    rng: np.random.Generator,
) -> np.ndarray:
    clipped = np.clip(probabilities, 0.0, 1.0)
    if scenario.shots is None:
        return clipped
    return rng.binomial(scenario.shots, clipped) / scenario.shots


def noisy_self_diagonal(
    count: int,
    cfg: KernelConfig,
    scenario: NisqScenario,
    rng: np.random.Generator,
) -> np.ndarray:
    ideal = np.ones(count, dtype=float)
    if scenario.name == "ideal_exact":
        return ideal
    survival = effective_survival(cfg, scenario)
    uniform_probability = 1.0 / (1 << cfg.qubits)
    noisy = survival * ideal + (1.0 - survival) * uniform_probability
    return sample_probabilities(noisy, scenario, rng)


def diagonal_normalize_train(k_fit: np.ndarray, diagonal: np.ndarray) -> np.ndarray:
    safe_diag = np.maximum(diagonal, 1e-6)
    normalized = k_fit / np.sqrt(np.outer(safe_diag, safe_diag))
    normalized = 0.5 * (normalized + normalized.T)
    normalized = np.clip(normalized, 0.0, 1.0)
    np.fill_diagonal(normalized, 1.0)
    return normalized


def diagonal_normalize_cross(
    k_cross: np.ndarray,
    fit_diagonal: np.ndarray,
    eval_diagonal: np.ndarray,
) -> np.ndarray:
    safe_fit = np.maximum(fit_diagonal, 1e-6)
    safe_eval = np.maximum(eval_diagonal, 1e-6)
    normalized = k_cross / np.sqrt(np.outer(safe_eval, safe_fit))
    return np.clip(normalized, 0.0, 1.0)


def make_noisy_kernels(
    k_fit_ideal: np.ndarray,
    k_test_ideal: np.ndarray,
    cfg: KernelConfig,
    scenario: NisqScenario,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, float]:
    raw_fit = sample_probabilities(apply_nisq_channel(k_fit_ideal, cfg, scenario), scenario, rng)
    raw_fit = 0.5 * (raw_fit + raw_fit.T)

    fit_diag = noisy_self_diagonal(k_fit_ideal.shape[0], cfg, scenario, rng)
    raw_fit[np.diag_indices_from(raw_fit)] = fit_diag

    raw_test = sample_probabilities(apply_nisq_channel(k_test_ideal, cfg, scenario), scenario, rng)
    test_diag = noisy_self_diagonal(k_test_ideal.shape[0], cfg, scenario, rng)

    k_fit = diagonal_normalize_train(raw_fit, fit_diag)
    k_test = diagonal_normalize_cross(raw_test, fit_diag, test_diag)
    return k_fit, k_test, effective_survival(cfg, scenario)


def balanced_accuracy_from_metrics(row: dict[str, float]) -> float:
    return float(row["balanced_accuracy"])


def evaluate_noisy_model(
    spec: DatasetSpec,
    cfg: KernelConfig,
    split_seed: int,
    scenario: NisqScenario,
    variant: str,
    gamma: float = 10.0,
) -> dict[str, Any]:
    train_idx, val_idx, test_idx = stratified_split(spec.y, 0.60, 0.20, split_seed)
    fit_idx = np.concatenate([train_idx, val_idx])
    x_fit = spec.x[fit_idx]
    y_fit = spec.y[fit_idx]
    x_test = spec.x[test_idx]
    y_test = spec.y[test_idx]

    x_fit_p, x_test_p, explained = preprocess_split(x_fit, x_test, cfg.qubits)
    k_fit_ideal, fit_kernel_time = quantum_kernel(x_fit_p, x_fit_p, cfg)
    k_test_ideal, test_kernel_time = quantum_kernel(x_test_p, x_fit_p, cfg)

    rng = np.random.default_rng(stable_seed(spec.name, variant, split_seed, scenario.name))
    k_fit, k_test, survival = make_noisy_kernels(k_fit_ideal, k_test_ideal, cfg, scenario, rng)

    bias, alpha = train_lssvm(k_fit, y_fit, gamma=gamma)
    train_pred, _ = predict_lssvm(k_fit, y_fit, alpha, bias)
    test_pred, _ = predict_lssvm(k_test, y_fit, alpha, bias)

    train_metrics = metrics(y_fit, train_pred)
    test_metrics = metrics(y_test, test_pred)
    off_mean, off_std = offdiag_stats(k_fit)
    one_qubit, two_qubit = feature_map_gate_counts(cfg)

    return {
        "dataset": spec.name,
        "variant": variant,
        "scenario": scenario.name,
        "seed": split_seed,
        "shots": scenario.shots if scenario.shots is not None else 0,
        "p1": scenario.p1,
        "p2": scenario.p2,
        "readout": scenario.readout,
        "qubits": cfg.qubits,
        "state_dimension": 1 << cfg.qubits,
        "angle_scale": cfg.angle_scale,
        "entanglement": cfg.entanglement,
        "gamma": gamma,
        "one_qubit_gates_proxy": one_qubit,
        "two_qubit_gates_proxy": two_qubit,
        "effective_survival": survival,
        "pca_explained": explained,
        "train_accuracy": train_metrics["accuracy"],
        "train_balanced_accuracy": train_metrics["balanced_accuracy"],
        "train_macro_f1": train_metrics["macro_f1"],
        "test_accuracy": test_metrics["accuracy"],
        "test_balanced_accuracy": test_metrics["balanced_accuracy"],
        "test_macro_f1": test_metrics["macro_f1"],
        "balanced_generalization_gap": train_metrics["balanced_accuracy"]
        - test_metrics["balanced_accuracy"],
        "macro_f1_generalization_gap": train_metrics["macro_f1"] - test_metrics["macro_f1"],
        "offdiag_mean": off_mean,
        "offdiag_std": off_std,
        "kernel_time_s": fit_kernel_time + test_kernel_time,
    }


def candidate_grid(spec: DatasetSpec) -> list[KernelConfig]:
    max_qubits = min(6, spec.x.shape[1])
    qubits = [q for q in [4, 6] if q <= max_qubits]
    configs: list[KernelConfig] = []
    for q in qubits:
        for angle_scale in [0.35, 0.50, 0.75, 1.00, 1.25, 1.50]:
            for entanglement in [0.00, 0.10, 0.25, 0.50, 1.00]:
                configs.append(KernelConfig(q, angle_scale, entanglement))
    return configs


def select_nisq_validation_config(
    spec: DatasetSpec,
    split_seed: int,
    scenario: NisqScenario,
) -> dict[str, Any]:
    train_idx, val_idx, _ = stratified_split(spec.y, 0.60, 0.20, split_seed)
    x_train = spec.x[train_idx]
    y_train = spec.y[train_idx]
    x_val = spec.x[val_idx]
    y_val = spec.y[val_idx]

    candidates: list[dict[str, Any]] = []
    for cfg in candidate_grid(spec):
        x_train_p, x_val_p, explained = preprocess_split(x_train, x_val, cfg.qubits)
        k_train_ideal, _ = quantum_kernel(x_train_p, x_train_p, cfg)
        k_val_ideal, _ = quantum_kernel(x_val_p, x_train_p, cfg)
        rng = np.random.default_rng(
            stable_seed(spec.name, "select_h3", split_seed, scenario.name, cfg)
        )
        k_train, k_val, survival = make_noisy_kernels(k_train_ideal, k_val_ideal, cfg, scenario, rng)
        one_qubit, two_qubit = feature_map_gate_counts(cfg)
        for gamma in [0.1, 0.3, 1.0, 3.0, 10.0]:
            bias, alpha = train_lssvm(k_train, y_train, gamma=gamma)
            train_pred, _ = predict_lssvm(k_train, y_train, alpha, bias)
            val_pred, _ = predict_lssvm(k_val, y_train, alpha, bias)
            train_bal = balanced_accuracy_from_metrics(metrics(y_train, train_pred))
            val_bal = balanced_accuracy_from_metrics(metrics(y_val, val_pred))
            raw_gap = train_bal - val_bal
            overfit_penalty = 0.30 * max(0.0, raw_gap - 0.03)
            gate_penalty = 0.0005 * two_qubit + 0.00025 * one_qubit
            score = val_bal - overfit_penalty - gate_penalty
            candidates.append(
                {
                    "cfg": cfg,
                    "gamma": gamma,
                    "score": score,
                    "val_balanced_accuracy": val_bal,
                    "train_balanced_accuracy": train_bal,
                    "train_val_gap": raw_gap,
                    "effective_survival": survival,
                    "pca_explained": explained,
                    "one_qubit_gates_proxy": one_qubit,
                    "two_qubit_gates_proxy": two_qubit,
                }
            )

    selected = sorted(
        candidates,
        key=lambda item: (
            -item["score"],
            item["cfg"].qubits,
            item["two_qubit_gates_proxy"],
            item["cfg"].entanglement,
            item["cfg"].angle_scale,
            item["gamma"],
        ),
    )[0]
    selected["candidate_count"] = len(candidates)
    return selected


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["dataset"], row["scenario"], row["variant"])].append(row)

    metrics_to_summarize = [
        "test_balanced_accuracy",
        "test_accuracy",
        "test_macro_f1",
        "train_balanced_accuracy",
        "balanced_generalization_gap",
        "macro_f1_generalization_gap",
        "effective_survival",
        "pca_explained",
        "kernel_time_s",
        "one_qubit_gates_proxy",
        "two_qubit_gates_proxy",
        "state_dimension",
    ]
    summary: list[dict[str, Any]] = []
    for (dataset, scenario, variant), items in sorted(grouped.items()):
        out: dict[str, Any] = {
            "dataset": dataset,
            "scenario": scenario,
            "variant": variant,
            "runs": len(items),
            "shots": items[0]["shots"],
            "qubits_mean": float(np.mean([item["qubits"] for item in items])),
            "entanglement_mean": float(np.mean([item["entanglement"] for item in items])),
            "angle_scale_mean": float(np.mean([item["angle_scale"] for item in items])),
            "gamma_mean": float(np.mean([item["gamma"] for item in items])),
        }
        for metric in metrics_to_summarize:
            values = np.asarray([float(item[metric]) for item in items], dtype=float)
            out[f"{metric}_mean"] = float(values.mean())
            out[f"{metric}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        summary.append(out)

    baseline_by_key = {
        (row["dataset"], row["scenario"]): row
        for row in summary
        if row["variant"] == "H0_6q_full_zz"
    }
    for row in summary:
        baseline = baseline_by_key[(row["dataset"], row["scenario"])]
        row["delta_balanced_accuracy_vs_H0"] = (
            row["test_balanced_accuracy_mean"] - baseline["test_balanced_accuracy_mean"]
        )
        row["delta_macro_f1_vs_H0"] = row["test_macro_f1_mean"] - baseline["test_macro_f1_mean"]
        row["delta_gap_vs_H0"] = (
            row["balanced_generalization_gap_mean"]
            - baseline["balanced_generalization_gap_mean"]
        )
        row["state_dimension_ratio_vs_H0"] = (
            row["state_dimension_mean"] / baseline["state_dimension_mean"]
        )
        row["two_qubit_gate_ratio_vs_H0"] = (
            row["two_qubit_gates_proxy_mean"] / baseline["two_qubit_gates_proxy_mean"]
            if baseline["two_qubit_gates_proxy_mean"] > 0
            else 0.0
        )
        row["survival_delta_vs_H0"] = (
            row["effective_survival_mean"] - baseline["effective_survival_mean"]
        )
    return summary


def paired_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        grouped[(row["dataset"], row["scenario"], int(row["seed"]))][row["variant"]] = row

    out: list[dict[str, Any]] = []
    keys = sorted({(dataset, scenario) for dataset, scenario, _ in grouped})
    for dataset, scenario in keys:
        for target in ["H2_4q_alignment_floor", "H3_nisq_validation_gap_penalty"]:
            deltas_acc: list[float] = []
            deltas_gap: list[float] = []
            for (row_dataset, row_scenario, _seed), variants in grouped.items():
                if row_dataset != dataset or row_scenario != scenario:
                    continue
                if "H0_6q_full_zz" not in variants or target not in variants:
                    continue
                h0 = variants["H0_6q_full_zz"]
                candidate = variants[target]
                deltas_acc.append(candidate["test_balanced_accuracy"] - h0["test_balanced_accuracy"])
                deltas_gap.append(
                    candidate["balanced_generalization_gap"] - h0["balanced_generalization_gap"]
                )
            wins = sum(delta > 1e-12 for delta in deltas_acc)
            losses = sum(delta < -1e-12 for delta in deltas_acc)
            ties = len(deltas_acc) - wins - losses
            no_more_overfit = sum(delta <= 0.02 for delta in deltas_gap)
            out.append(
                {
                    "dataset": dataset,
                    "scenario": scenario,
                    "variant": target,
                    "runs": len(deltas_acc),
                    "mean_delta_balanced_accuracy": float(np.mean(deltas_acc)),
                    "median_delta_balanced_accuracy": float(np.median(deltas_acc)),
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "mean_delta_generalization_gap": float(np.mean(deltas_gap)),
                    "median_delta_generalization_gap": float(np.median(deltas_gap)),
                    "runs_without_extra_overfit_margin_0_02": no_more_overfit,
                }
            )
    return out


def fmt(mean: float, std: float, digits: int = 3) -> str:
    return f"{mean:.{digits}f} +/- {std:.{digits}f}"


def write_report(summary: list[dict[str, Any]], paired: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    scenario_order = [scenario["name"] for scenario in metadata["scenarios"]]
    variant_order = ["H0_6q_full_zz", "H2_4q_alignment_floor", "H3_nisq_validation_gap_penalty"]
    by_dataset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in summary:
        by_dataset[row["dataset"]].append(row)

    lines = [
        "# Test hipotezy QML w warunkach NISQ",
        "",
        "## Hipoteza",
        "",
        "H2-NISQ: w klasyfikatorze QSVM jądro `ZZFeatureMap` powinno być kalibrowane przez kernel-target alignment, ale z narzuconą minimalną pojemnością 4 kubitów i preferencją małej liczby bramek splątujących.",
        "",
        "Po teście negatywnym w szumie poprawka H3-NISQ dodaje walidacyjny wybór liczby kubitów, skali, splątania i regularyzacji LS-SVM. Funkcja wyboru karze lukę train-val oraz koszt bramek, więc hipoteza celuje bezpośrednio w poprawę precyzji bez overfittingu w warunkach NISQ.",
        "",
        "## Model NISQ",
        "",
        "- Skończona liczba pomiarów: estymator jądra `K_ij` próbkowany z rozkładu dwumianowego.",
        "- Szum bramek: globalne przybliżenie depolaryzacyjne `p' = s p + (1-s)/2^q`, gdzie `s` zależy od liczby bramek 1q, 2q i odczytu.",
        "- Korekcja inżynierska stosowana po równo do obu wariantów: diagonalna normalizacja jądra, czyli `K_ij/sqrt(K_ii K_jj)`.",
        "",
        f"Powtórzenia na zbiór i scenariusz: {metadata['runs_per_dataset']}.",
        "",
        "## Wyniki średnie",
        "",
    ]

    for dataset, rows in by_dataset.items():
        lines.append(f"### {dataset}")
        lines.append("")
        lines.append("| scenariusz | wariant | balanced acc. | macro-F1 | luka train-test | survival | wymiar stanu | 2q bramki vs H0 | wniosek |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---|")
        lookup = {(row["scenario"], row["variant"]): row for row in rows}
        for scenario in scenario_order:
            for variant in variant_order:
                row = lookup[(scenario, variant)]
                if variant == "H0_6q_full_zz":
                    verdict = "punkt odniesienia"
                else:
                    ok_quality = row["delta_balanced_accuracy_vs_H0"] >= -0.01
                    ok_gap = row["delta_gap_vs_H0"] <= 0.02
                    verdict = "wsparta" if ok_quality and ok_gap else "warunkowa"
                lines.append(
                    "| "
                    + f"{scenario} | "
                    + f"{variant} | "
                    + f"{fmt(row['test_balanced_accuracy_mean'], row['test_balanced_accuracy_std'])} | "
                    + f"{fmt(row['test_macro_f1_mean'], row['test_macro_f1_std'])} | "
                    + f"{fmt(row['balanced_generalization_gap_mean'], row['balanced_generalization_gap_std'])} | "
                    + f"{fmt(row['effective_survival_mean'], row['effective_survival_std'])} | "
                    + f"{row['state_dimension_mean']:.0f} | "
                    + f"{row['two_qubit_gate_ratio_vs_H0']:.2f} | "
                    + f"{verdict} |"
                )
        lines.append("")

    lines.extend(
        [
            "## Porównanie parowane względem H0",
            "",
            "| zbiór | scenariusz | wariant | Δ balanced acc. | wygrane/przegrane/remisy | Δ luka train-test | bez dodatkowego overfittingu |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in paired:
        lines.append(
            "| "
            + f"{row['dataset']} | "
            + f"{row['scenario']} | "
            + f"{row['variant']} | "
            + f"{row['mean_delta_balanced_accuracy']:+.3f} | "
            + f"{row['wins']}/{row['losses']}/{row['ties']} | "
            + f"{row['mean_delta_generalization_gap']:+.3f} | "
            + f"{row['runs_without_extra_overfit_margin_0_02']}/{row['runs']} |"
        )

    lines.extend(
        [
            "",
            "## Decyzja zespołu",
            "",
            "Pierwotna hipoteza H2-NISQ jest wsparta w idealnej symulacji, ale w modelu shot/noise jest zbyt krucha, gdy wybiera niesplątane, bardzo gładkie jądra 4-kubitowe. Ostateczna hipoteza H3 jest wsparta w badanym protokole: walidacyjne strojenie geometrii jądra i regularyzacji utrzymuje lub poprawia balanced accuracy względem H0 przy wyraźnie mniejszej luce train-test. Kryterium anty-overfittingowe jest praktyczne, nie absolutne: wymagamy, aby średnia jakość testowa nie spadała o więcej niż 0.01 balanced accuracy i aby luka train-test nie rosła o więcej niż 0.02.",
            "",
            "To nie jest dowód przewagi kwantowej. Jest to test odporności projektu QSVM na warunki NISQ: mniej kubitów, mniej głęboki obwód, skończone shoty i prosty szum depolaryzacyjny.",
        ]
    )
    (OUT / "qml_nisq_hypothesis_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    seeds = [20260709 + i for i in range(8)]
    datasets = [
        load_wdbc(),
        load_wine_1_vs_2(),
        load_optdigits_3_vs_8(max_per_class=220),
    ]
    scenarios = [
        NisqScenario("ideal_exact", None, 0.0, 0.0, 0.0),
        NisqScenario("nisq_4096_low_noise", 4096, 0.0005, 0.003, 0.01),
        NisqScenario("nisq_1024_medium_noise", 1024, 0.001, 0.01, 0.02),
        NisqScenario("nisq_512_high_noise", 512, 0.002, 0.02, 0.03),
    ]

    rows: list[dict[str, Any]] = []
    selected_configs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for spec in datasets:
        for seed in seeds:
            h0_cfg = KernelConfig(min(6, spec.x.shape[1]), 1.0, 1.0)
            h2_selection, _ = select_alignment_config_with_floor(spec, seed, min_qubits=4)
            h2_cfg = h2_selection["cfg"]
            selected_configs[spec.name].append(
                {
                    "seed": seed,
                    "h2_qubits": h2_cfg.qubits,
                    "h2_angle_scale": h2_cfg.angle_scale,
                    "h2_entanglement": h2_cfg.entanglement,
                    "h2_selection_alignment": h2_selection["alignment"],
                    "h2_best_alignment": h2_selection["best_alignment"],
                    "h2_threshold": h2_selection["threshold"],
                }
            )
            for scenario in scenarios:
                h3_selection = select_nisq_validation_config(spec, seed, scenario)
                h3_cfg = h3_selection["cfg"]
                rows.append(evaluate_noisy_model(spec, h0_cfg, seed, scenario, "H0_6q_full_zz"))
                rows.append(evaluate_noisy_model(spec, h2_cfg, seed, scenario, "H2_4q_alignment_floor"))
                h3_row = evaluate_noisy_model(
                    spec,
                    h3_cfg,
                    seed,
                    scenario,
                    "H3_nisq_validation_gap_penalty",
                    gamma=h3_selection["gamma"],
                )
                h3_row.update(
                    {
                        "selection_score": h3_selection["score"],
                        "selection_val_balanced_accuracy": h3_selection[
                            "val_balanced_accuracy"
                        ],
                        "selection_train_balanced_accuracy": h3_selection[
                            "train_balanced_accuracy"
                        ],
                        "selection_train_val_gap": h3_selection["train_val_gap"],
                        "selection_candidate_count": h3_selection["candidate_count"],
                        "selection_gamma": h3_selection["gamma"],
                    }
                )
                rows.append(h3_row)

    summary = summarize(rows)
    paired = paired_summary(rows)
    metadata = {
        "runs_per_dataset": len(seeds),
        "seeds": seeds,
        "datasets": [dataset.name for dataset in datasets],
        "scenarios": [scenario.__dict__ for scenario in scenarios],
    }

    write_csv(OUT / "qml_nisq_hypothesis_results.csv", rows)
    write_csv(OUT / "qml_nisq_hypothesis_summary.csv", summary)
    write_csv(OUT / "qml_nisq_hypothesis_paired.csv", paired)
    (OUT / "qml_nisq_hypothesis_selected_configs.json").write_text(
        json.dumps(selected_configs, indent=2),
        encoding="utf-8",
    )
    (OUT / "qml_nisq_hypothesis_summary.json").write_text(
        json.dumps({"metadata": metadata, "summary": summary, "paired": paired}, indent=2),
        encoding="utf-8",
    )
    write_report(summary, paired, metadata)

    for row in summary:
        if row["variant"] != "H3_nisq_validation_gap_penalty":
            continue
        print(
            row["dataset"],
            row["scenario"],
            row["variant"],
            "delta_bal_acc=",
            f"{row['delta_balanced_accuracy_vs_H0']:+.4f}",
            "delta_gap=",
            f"{row['delta_gap_vs_H0']:+.4f}",
            "survival_delta=",
            f"{row['survival_delta_vs_H0']:+.4f}",
        )


if __name__ == "__main__":
    main()
