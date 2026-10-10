from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import time
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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
from .learning import (
    balanced_accuracy,
    centered_kernel_alignment,
    fit_kernel_ridge,
    kernel_diagnostics,
    macro_f1,
    nearest_correlation_kernel,
    predict_kernel_ridge,
    rbf_kernel,
    sample_bloch_vectors,
    sample_fidelity_kernel,
    select_regularization,
)


ROOT = Path(__file__).resolve().parents[1]
GAMMA_GRID = (0.1, 0.3, 1.0, 3.0, 10.0)


@dataclass(frozen=True)
class Variant:
    name: str
    kernel: str
    method: str = "trotter"
    trotter_order: int = 2
    trotter_steps: int = 2
    shots: int | None = None


def smoke_variants() -> list[Variant]:
    return [
        Variant("exact_fidelity", "fidelity", method="exact"),
        Variant("t1_r1_fidelity", "fidelity", trotter_order=1, trotter_steps=1),
        Variant("t1_r4_fidelity", "fidelity", trotter_order=1, trotter_steps=4),
        Variant("t2_r1_fidelity", "fidelity", trotter_order=2, trotter_steps=1),
        Variant("t2_r4_fidelity", "fidelity", trotter_order=2, trotter_steps=4),
        Variant("t2_r2_projected", "projected", trotter_order=2, trotter_steps=2),
        Variant("t2_r2_fidelity_256shots", "fidelity", trotter_order=2, trotter_steps=2, shots=256),
        Variant("rbf", "rbf", method="classical"),
    ]


def full_variants() -> list[Variant]:
    variants = [
        Variant("exact_fidelity", "fidelity", method="exact"),
        Variant("exact_projected", "projected", method="exact"),
    ]
    for order in (1, 2):
        for steps in (1, 2, 4, 8):
            variants.append(Variant(f"t{order}_r{steps}_fidelity", "fidelity", trotter_order=order, trotter_steps=steps))
    for steps in (1, 2, 4):
        variants.append(Variant(f"t2_r{steps}_projected", "projected", trotter_order=2, trotter_steps=steps))
    variants.extend(
        [
            Variant("t2_r2_fidelity_256shots", "fidelity", trotter_order=2, trotter_steps=2, shots=256),
            Variant("t2_r2_fidelity_1024shots", "fidelity", trotter_order=2, trotter_steps=2, shots=1024),
            Variant("t2_r2_projected_256shots", "projected", trotter_order=2, trotter_steps=2, shots=256),
            Variant("t2_r2_projected_1024shots", "projected", trotter_order=2, trotter_steps=2, shots=1024),
            Variant("rbf", "rbf", method="classical"),
        ]
    )
    return variants


def evolution_config(variant: Variant, args: argparse.Namespace) -> EvolutionConfig:
    method = "exact" if variant.method == "exact" else "trotter"
    return EvolutionConfig(
        n_qubits=args.n_qubits,
        evolution_time=args.evolution_time,
        transverse_field=args.transverse_field,
        interaction_strength=args.interaction_strength,
        topology=args.topology,
        method=method,
        trotter_order=variant.trotter_order,
        trotter_steps=variant.trotter_steps,
    )


def _stable_rng(seed: int, variant_name: str) -> np.random.Generator:
    variant_code = zlib.crc32(variant_name.encode("utf-8"))
    return np.random.default_rng(np.random.SeedSequence([seed, variant_code]))


def _split_batch(values: np.ndarray, data: PreparedData) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    train_end = len(data.x_train)
    val_end = train_end + len(data.x_val)
    return values[:train_end], values[train_end:val_end], values[val_end:]


def _select_gamma(
    build_train_kernel: Any,
    y_train: np.ndarray,
) -> tuple[float, float]:
    best_gamma = GAMMA_GRID[0]
    best_alignment = -np.inf
    for gamma in GAMMA_GRID:
        alignment = centered_kernel_alignment(build_train_kernel(gamma), y_train)
        if alignment > best_alignment + 1e-12:
            best_alignment = alignment
            best_gamma = gamma
    return best_gamma, float(best_alignment)


def _measurement_cost(
    variant: Variant,
    data: PreparedData,
    n_qubits: int,
) -> tuple[int, int, int]:
    if variant.kernel == "rbf":
        return 0, 0, 0
    if variant.kernel == "fidelity":
        train_pairs = len(data.x_train) * (len(data.x_train) - 1) // 2
        cross_pairs = (len(data.x_val) + len(data.x_test)) * len(data.x_train)
        circuit_evaluations = train_pairs + cross_pairs
        observable_estimates = circuit_evaluations
    else:
        state_count = len(data.x_train) + len(data.x_val) + len(data.x_test)
        # All local Paulis in one basis are measured together: X, Y and Z.
        circuit_evaluations = state_count * 3
        observable_estimates = state_count * 3 * n_qubits
    shot_count = 0 if variant.shots is None else circuit_evaluations * variant.shots
    return circuit_evaluations, observable_estimates, shot_count


def evaluate_variant(
    variant: Variant,
    data: PreparedData,
    seed: int,
    args: argparse.Namespace,
    exact_states: np.ndarray,
    state_cache: dict[tuple[str, int, int], np.ndarray],
) -> dict[str, float | int | str | bool | None]:
    start = time.perf_counter()
    gamma: float | None = None
    selection_alignment: float | None = None
    raw_negative_eigenmass = 0.0
    psd_repaired = False
    mean_infidelity = 0.0
    maximum_infidelity = 0.0

    if variant.kernel == "rbf":
        gamma, selection_alignment = _select_gamma(
            lambda value: rbf_kernel(data.x_train, data.x_train, value),
            data.y_train,
        )
        k_train = rbf_kernel(data.x_train, data.x_train, gamma)
        k_val = rbf_kernel(data.x_val, data.x_train, gamma)
        k_test = rbf_kernel(data.x_test, data.x_train, gamma)
        resources = {
            "a_blocks": 0,
            "single_qubit_rotations": 0,
            "two_qubit_gates": 0,
            "logical_depth_proxy": 0,
        }
        resource_estimate_available = False
    else:
        key = (variant.method, variant.trotter_order, variant.trotter_steps)
        if key not in state_cache:
            config = evolution_config(variant, args)
            all_x = np.vstack((data.x_train, data.x_val, data.x_test))
            state_cache[key] = evolve_batch(all_x, config)
        states = state_cache[key]
        train_states, val_states, test_states = _split_batch(states, data)
        infidelity = state_infidelity(exact_states, states)
        mean_infidelity = float(np.mean(infidelity))
        maximum_infidelity = float(np.max(infidelity))
        resources = circuit_resources(evolution_config(variant, args))
        resource_estimate_available = variant.method != "exact"
        rng = _stable_rng(seed, variant.name)

        if variant.kernel == "fidelity":
            k_train_probabilities = fidelity_kernel(train_states, train_states)
            k_val_probabilities = fidelity_kernel(val_states, train_states)
            k_test_probabilities = fidelity_kernel(test_states, train_states)
            if variant.shots is None:
                k_train = k_train_probabilities
                k_val = k_val_probabilities
                k_test = k_test_probabilities
            else:
                k_train = sample_fidelity_kernel(k_train_probabilities, variant.shots, rng, symmetric=True)
                raw_negative_eigenmass = kernel_diagnostics(k_train, 1e-2)["kernel_negative_eigenmass"]
                k_train = nearest_correlation_kernel(k_train)
                psd_repaired = True
                k_val = sample_fidelity_kernel(k_val_probabilities, variant.shots, rng, symmetric=False)
                k_test = sample_fidelity_kernel(k_test_probabilities, variant.shots, rng, symmetric=False)
        elif variant.kernel == "projected":
            all_bloch = bloch_vectors(states, args.n_qubits)
            if variant.shots is not None:
                all_bloch = sample_bloch_vectors(all_bloch, variant.shots, rng)
            train_bloch, val_bloch, test_bloch = _split_batch(all_bloch, data)
            gamma, selection_alignment = _select_gamma(
                lambda value: projected_kernel(train_bloch, train_bloch, value),
                data.y_train,
            )
            k_train = projected_kernel(train_bloch, train_bloch, gamma)
            k_val = projected_kernel(val_bloch, train_bloch, gamma)
            k_test = projected_kernel(test_bloch, train_bloch, gamma)
        else:
            raise ValueError(f"Unknown kernel: {variant.kernel}")

    regularization, val_balanced_accuracy = select_regularization(
        k_train,
        data.y_train,
        k_val,
        data.y_val,
    )
    coefficients, classes = fit_kernel_ridge(k_train, data.y_train, regularization)
    test_prediction = predict_kernel_ridge(k_test, coefficients, classes)
    diagnostics = kernel_diagnostics(k_train, regularization)
    circuit_evaluations, observable_estimates, total_shots = _measurement_cost(variant, data, args.n_qubits)

    row: dict[str, float | int | str | bool | None] = {
        "dataset": data.name,
        "seed": seed,
        "variant": variant.name,
        "kernel": variant.kernel,
        "method": variant.method,
        "trotter_order": 0 if variant.method != "trotter" else variant.trotter_order,
        "trotter_steps": 0 if variant.method != "trotter" else variant.trotter_steps,
        "shots": variant.shots,
        "n_qubits": args.n_qubits,
        "n_train": len(data.x_train),
        "n_val": len(data.x_val),
        "n_test": len(data.x_test),
        "pca_explained_ratio": data.pca_explained_ratio,
        "gamma": gamma,
        "selection_alignment": selection_alignment,
        "regularization": regularization,
        "val_balanced_accuracy": val_balanced_accuracy,
        "test_accuracy": float(np.mean(test_prediction == data.y_test)),
        "test_balanced_accuracy": balanced_accuracy(data.y_test, test_prediction, classes),
        "test_macro_f1": macro_f1(data.y_test, test_prediction, classes),
        "train_alignment": centered_kernel_alignment(k_train, data.y_train),
        "mean_state_infidelity": mean_infidelity,
        "max_state_infidelity": maximum_infidelity,
        "raw_negative_eigenmass": raw_negative_eigenmass,
        "psd_repaired": psd_repaired,
        "resource_estimate_available": resource_estimate_available,
        "kernel_circuit_evaluations": circuit_evaluations,
        "observable_estimates": observable_estimates,
        "total_shots": total_shots,
        "kernel_seconds": time.perf_counter() - start,
        **resources,
        **diagnostics,
    }
    return row


SUMMARY_METRICS = (
    "test_accuracy",
    "test_balanced_accuracy",
    "test_macro_f1",
    "val_balanced_accuracy",
    "train_alignment",
    "mean_state_infidelity",
    "max_state_infidelity",
    "kernel_effective_rank",
    "kernel_min_eigenvalue",
    "kernel_negative_eigenmass",
    "raw_negative_eigenmass",
    "kernel_condition_number",
    "kernel_offdiag_mean",
    "kernel_offdiag_std",
    "kernel_seconds",
    "two_qubit_gates",
    "logical_depth_proxy",
    "kernel_circuit_evaluations",
    "observable_estimates",
    "total_shots",
)


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((str(row["dataset"]), str(row["variant"])), []).append(row)
    summary: list[dict[str, Any]] = []
    for (dataset, variant), group in sorted(groups.items()):
        first = group[0]
        item: dict[str, Any] = {
            "dataset": dataset,
            "variant": variant,
            "runs": len(group),
            "kernel": first["kernel"],
            "method": first["method"],
            "trotter_order": first["trotter_order"],
            "trotter_steps": first["trotter_steps"],
            "shots": first["shots"],
        }
        for metric in SUMMARY_METRICS:
            values = np.asarray([float(row[metric]) for row in group], dtype=float)
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        summary.append(item)
    return summary


COMPARISON_PAIRS = (
    ("exact_fidelity", "t2_r1_fidelity"),
    ("exact_fidelity", "t2_r2_fidelity"),
    ("exact_fidelity", "t2_r4_fidelity"),
    ("exact_projected", "t2_r2_projected"),
    ("rbf", "exact_fidelity"),
    ("rbf", "exact_projected"),
    ("t2_r2_fidelity", "t2_r2_fidelity_256shots"),
    ("t2_r2_fidelity", "t2_r2_fidelity_1024shots"),
    ("t2_r2_projected", "t2_r2_projected_256shots"),
    ("t2_r2_projected", "t2_r2_projected_1024shots"),
)


def _two_sided_sign_pvalue(wins: int, losses: int) -> float:
    trials = wins + losses
    if trials == 0:
        return 1.0
    tail = sum(math.comb(trials, count) for count in range(0, min(wins, losses) + 1)) / (2**trials)
    return float(min(1.0, 2.0 * tail))


def paired_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {
        (str(row["dataset"]), int(row["seed"]), str(row["variant"])): row
        for row in rows
    }
    datasets = sorted({str(row["dataset"]) for row in rows})
    results: list[dict[str, Any]] = []
    for dataset in datasets:
        dataset_seeds = sorted({int(row["seed"]) for row in rows if row["dataset"] == dataset})
        for baseline, candidate in COMPARISON_PAIRS:
            deltas: list[float] = []
            for seed in dataset_seeds:
                baseline_row = indexed.get((dataset, seed, baseline))
                candidate_row = indexed.get((dataset, seed, candidate))
                if baseline_row is not None and candidate_row is not None:
                    deltas.append(
                        float(candidate_row["test_balanced_accuracy"])
                        - float(baseline_row["test_balanced_accuracy"])
                    )
            if not deltas:
                continue
            wins = sum(delta > 1e-12 for delta in deltas)
            losses = sum(delta < -1e-12 for delta in deltas)
            ties = len(deltas) - wins - losses
            results.append(
                {
                    "dataset": dataset,
                    "baseline": baseline,
                    "candidate": candidate,
                    "runs": len(deltas),
                    "mean_delta_balanced_accuracy": float(np.mean(deltas)),
                    "median_delta_balanced_accuracy": float(np.median(deltas)),
                    "wins": wins,
                    "losses": losses,
                    "ties": ties,
                    "two_sided_sign_pvalue": _two_sided_sign_pvalue(wins, losses),
                }
            )
    return results


def convergence_analysis(summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    datasets = sorted({str(row["dataset"]) for row in summary})
    for dataset in datasets:
        for order in (1, 2):
            candidates = sorted(
                (
                    row
                    for row in summary
                    if row["dataset"] == dataset
                    and row["method"] == "trotter"
                    and row["kernel"] == "fidelity"
                    and row["shots"] is None
                    and int(row["trotter_order"]) == order
                ),
                key=lambda row: int(row["trotter_steps"]),
            )
            if len(candidates) < 2:
                continue
            steps = np.asarray([float(row["trotter_steps"]) for row in candidates])
            errors = np.asarray([max(float(row["mean_state_infidelity_mean"]), 1e-16) for row in candidates])
            slope, intercept = np.polyfit(np.log(steps), np.log(errors), deg=1)
            fitted = slope * np.log(steps) + intercept
            residual = np.sum((np.log(errors) - fitted) ** 2)
            total = np.sum((np.log(errors) - np.mean(np.log(errors))) ** 2)
            r_squared = 1.0 if total < 1e-15 else 1.0 - residual / total
            results.append(
                {
                    "dataset": dataset,
                    "trotter_order": order,
                    "points": len(candidates),
                    "log_log_slope": float(slope),
                    "r_squared": float(r_squared),
                    "steps": steps.astype(int).tolist(),
                    "mean_infidelities": errors.tolist(),
                }
            )
    return results


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _metric(mean: float, std: float) -> str:
    return f"{mean:.3f} +/- {std:.3f}"


def write_report(
    path: Path,
    summary: list[dict[str, Any]],
    args: argparse.Namespace,
    comparisons: list[dict[str, Any]],
    convergence: list[dict[str, Any]],
) -> None:
    by_dataset: dict[str, list[dict[str, Any]]] = {}
    for row in summary:
        by_dataset.setdefault(str(row["dataset"]), []).append(row)

    lines = [
        "# Hamiltonian quantum kernel: raport eksperymentalny",
        "",
        "## Cel",
        "",
        "Badanie kompromisu między błędem trotterowania, jakością klasyfikacji, widmem macierzy kernela i logicznym kosztem obwodu.",
        "",
        "## Model",
        "",
        f"- Hamiltonian: `H(x) = sum_i x_i Z_i + {args.interaction_strength:g} sum_(i,j) Z_i Z_j + {args.transverse_field:g} sum_i X_i`.",
        f"- Liczba kubitów: `{args.n_qubits}`; topologia: `{args.topology}`; czas ewolucji: `{args.evolution_time:g}`.",
        "- Preprocessing: standaryzacja, PCA i skalowanie do `[-1, 1]`, dopasowane tylko na zbiorze treningowym.",
        "- Hiperparametry: gamma wybierana przez centered kernel-target alignment na train; regularyzacja KRR wybierana na validation.",
        "- Wyniki testowe nie uczestniczą w wyborze hiperparametrów.",
        "",
        "## Wyniki",
        "",
    ]
    for dataset, dataset_rows in sorted(by_dataset.items()):
        lines.extend(
            [
                f"### {dataset}",
                "",
                "| wariant | kernel | order/r | shots | balanced acc. | macro-F1 | alignment | infidelity | eff. rank | CX/map | circuits |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in sorted(dataset_rows, key=lambda value: str(value["variant"])):
            order_steps = "-" if int(row["trotter_order"]) == 0 else f"{int(row['trotter_order'])}/{int(row['trotter_steps'])}"
            shots = "-" if row["shots"] is None else str(int(row["shots"]))
            cx_text = "-" if row["method"] != "trotter" else f"{row['two_qubit_gates_mean']:.0f}"
            lines.append(
                "| "
                + f"{row['variant']} | {row['kernel']} | {order_steps} | {shots} | "
                + f"{_metric(row['test_balanced_accuracy_mean'], row['test_balanced_accuracy_std'])} | "
                + f"{_metric(row['test_macro_f1_mean'], row['test_macro_f1_std'])} | "
                + f"{row['train_alignment_mean']:.3f} | {row['mean_state_infidelity_mean']:.3e} | "
                + f"{row['kernel_effective_rank_mean']:.2f} | {cx_text} | {row['kernel_circuit_evaluations_mean']:.0f} |"
            )
        lines.append("")

        finite_shot_rows = [row for row in dataset_rows if row["shots"] is not None]
        if finite_shot_rows:
            lines.extend(
                [
                    "Finite shots:",
                    "",
                    "| wariant | shots/circuit | total shots | raw negative eigenmass | PSD repair |",
                    "|---|---:|---:|---:|---|",
                ]
            )
            for row in sorted(finite_shot_rows, key=lambda value: str(value["variant"])):
                repair = "yes" if row["kernel"] == "fidelity" else "no"
                lines.append(
                    f"| {row['variant']} | {int(row['shots'])} | {row['total_shots_mean']:.0f} | "
                    + f"{row['raw_negative_eigenmass_mean']:.3f} | {repair} |"
                )
            lines.append("")

    if convergence:
        lines.extend(
            [
                "## Zbieżność wzorów Trottera",
                "",
                "Nachylenie jest estymowane z regresji `log(mean infidelity)` względem `log(r)`.",
                "Dla dostatecznie małego kroku oczekujemy w przybliżeniu `-2` dla rzędu 1 i `-4` dla rzędu 2.",
                "",
                "| zbiór | rząd | nachylenie | R^2 |",
                "|---|---:|---:|---:|",
            ]
        )
        for item in convergence:
            lines.append(
                f"| {item['dataset']} | {item['trotter_order']} | {item['log_log_slope']:.3f} | {item['r_squared']:.4f} |"
            )
        lines.append("")

    if comparisons:
        lines.extend(
            [
                "## Porównania sparowane",
                "",
                "Delta oznacza `candidate - baseline` dla balanced accuracy. Test znaku pomija remisy.",
                "",
                "| zbiór | baseline | candidate | mean delta | W/L/T | sign p |",
                "|---|---|---|---:|---:|---:|",
            ]
        )
        for item in comparisons:
            lines.append(
                "| "
                + f"{item['dataset']} | {item['baseline']} | {item['candidate']} | "
                + f"{item['mean_delta_balanced_accuracy']:+.3f} | "
                + f"{item['wins']}/{item['losses']}/{item['ties']} | {item['two_sided_sign_pvalue']:.4f} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Zasady interpretacji",
            "",
            "- Mniejsza infidelity oznacza wierniejsze przybliżenie ewolucji, ale nie musi oznaczać lepszej generalizacji.",
            "- Fidelity kernel wymaga obwodu dla par próbek, natomiast projected kernel estymuje lokalne obserwable dla każdego stanu.",
            "- Kolumna `CX/map` opisuje pojedynczą mapę cech; obwód overlapowy fidelity zawiera mapę dla obu porównywanych próbek.",
            "- Warianty finite-shot używają tej samej liczby strzałów na obwód, nie tego samego całkowitego budżetu pomiarowego.",
            "- Dla wariantów fidelity z finite shots macierz treningowa jest naprawiana projekcją PSD; raport zachowuje surową ujemną masę widmową jako diagnostykę.",
            "- Wyniki symulacyjne nie stanowią dowodu przewagi kwantowej.",
            "",
            "## Artefakty",
            "",
            "- `runs.csv`: wyniki wszystkich podziałów.",
            "- `summary.csv` i `summary.json`: agregaty oraz konfiguracja.",
            "- `performance.png`: jakość klasyfikacji i błąd Trottera.",
            "- `kernel_diagnostics.png`: alignment i efektywny rząd kernela.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_plots(output_dir: Path, summary: list[dict[str, Any]]) -> None:
    def short_label(row: dict[str, Any]) -> str:
        if row["method"] == "exact":
            return "exact F" if row["kernel"] == "fidelity" else "exact P"
        if row["kernel"] == "rbf":
            return "RBF"
        kernel_code = "F" if row["kernel"] == "fidelity" else "P"
        label = f"T{int(row['trotter_order'])} r{int(row['trotter_steps'])} {kernel_code}"
        if row["shots"] is not None:
            label += f" {int(row['shots'])}s"
        return label

    datasets = sorted({str(row["dataset"]) for row in summary})
    figure, axes = plt.subplots(len(datasets), 2, figsize=(13, max(4, 3.8 * len(datasets))), squeeze=False)
    for row_index, dataset in enumerate(datasets):
        rows = [row for row in summary if row["dataset"] == dataset]
        labels = [short_label(row) for row in rows]
        positions = np.arange(len(rows))
        axes[row_index, 0].bar(
            positions,
            [row["test_balanced_accuracy_mean"] for row in rows],
            yerr=[row["test_balanced_accuracy_std"] for row in rows],
            color="#287271",
            capsize=2,
        )
        axes[row_index, 0].set_ylim(0.0, 1.05)
        axes[row_index, 0].set_ylabel("balanced accuracy")
        axes[row_index, 0].set_title(dataset)
        axes[row_index, 0].set_xticks(positions, labels, rotation=55, ha="right", fontsize=8)

        quantum_rows = [row for row in rows if row["method"] == "trotter" and row["kernel"] == "fidelity" and row["shots"] is None]
        axes[row_index, 1].scatter(
            [row["mean_state_infidelity_mean"] for row in quantum_rows],
            [row["test_balanced_accuracy_mean"] for row in quantum_rows],
            color="#d26444",
            s=45,
        )
        quantum_rows.sort(key=lambda row: float(row["mean_state_infidelity_mean"]))
        for point_index, row in enumerate(quantum_rows):
            annotation_label = f"T{int(row['trotter_order'])}, r={int(row['trotter_steps'])}"
            axes[row_index, 1].annotate(
                annotation_label,
                (row["mean_state_infidelity_mean"], row["test_balanced_accuracy_mean"]),
                xytext=(4, 5 + 10 * (point_index % 3)),
                textcoords="offset points",
                fontsize=7,
            )
        axes[row_index, 1].set_xlabel("mean state infidelity")
        axes[row_index, 1].set_ylabel("balanced accuracy")
        axes[row_index, 1].set_xscale("log")
        if quantum_rows:
            y_values = np.asarray([float(row["test_balanced_accuracy_mean"]) for row in quantum_rows])
            y_padding = max(float(np.ptp(y_values)) * 0.2, 0.004)
            axes[row_index, 1].set_ylim(max(0.0, float(y_values.min()) - y_padding), min(1.02, float(y_values.max()) + 3 * y_padding))
        axes[row_index, 1].grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_dir / "performance.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(len(datasets), 1, figsize=(12, max(4, 3.6 * len(datasets))), squeeze=False)
    for row_index, dataset in enumerate(datasets):
        rows = [row for row in summary if row["dataset"] == dataset]
        positions = np.arange(len(rows))
        axis = axes[row_index, 0]
        axis.bar(positions - 0.2, [row["train_alignment_mean"] for row in rows], width=0.4, label="alignment", color="#2a6fbb")
        rank_axis = axis.twinx()
        rank_axis.bar(
            positions + 0.2,
            [row["kernel_effective_rank_mean"] for row in rows],
            width=0.4,
            label="effective rank",
            color="#e9c46a",
        )
        axis.set_ylim(0.0, 1.05)
        axis.set_ylabel("alignment")
        rank_axis.set_ylabel("effective rank")
        axis.set_title(dataset)
        axis.set_xticks(positions, [short_label(row) for row in rows], rotation=55, ha="right", fontsize=8)
        handles_left, labels_left = axis.get_legend_handles_labels()
        handles_right, labels_right = rank_axis.get_legend_handles_labels()
        axis.legend(handles_left + handles_right, labels_left + labels_right, loc="upper right")
    figure.tight_layout()
    figure.savefig(output_dir / "kernel_diagnostics.png", dpi=180)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hamiltonian quantum-kernel experiment")
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--datasets", help="Comma-separated override, e.g. moons,wdbc")
    parser.add_argument("--seeds", help="Comma-separated override, e.g. 0,1,2")
    parser.add_argument("--n-qubits", type=int, default=4)
    parser.add_argument("--evolution-time", type=float, default=1.0)
    parser.add_argument("--transverse-field", type=float, default=0.7)
    parser.add_argument("--interaction-strength", type=float, default=0.6)
    parser.add_argument("--topology", choices=("chain", "ring", "all_to_all"), default="chain")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    smoke = args.profile == "smoke"
    dataset_names = args.datasets.split(",") if args.datasets else (["moons"] if smoke else ["moons", "wdbc", "wine"])
    seeds = [int(value) for value in args.seeds.split(",")] if args.seeds else ([0] if smoke else list(range(10)))
    variants = smoke_variants() if smoke else full_variants()
    output_dir = args.output_dir or ROOT / "analysis_output" / f"hamiltonian_kernel_{args.profile}"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for dataset_name in dataset_names:
        for seed in seeds:
            dataset = load_dataset(dataset_name, seed=seed, smoke=smoke)
            prepared = prepare_dataset(dataset, n_components=args.n_qubits, seed=seed)
            all_x = np.vstack((prepared.x_train, prepared.x_val, prepared.x_test))
            exact_config = EvolutionConfig(
                n_qubits=args.n_qubits,
                evolution_time=args.evolution_time,
                transverse_field=args.transverse_field,
                interaction_strength=args.interaction_strength,
                topology=args.topology,
                method="exact",
            )
            exact_states = evolve_batch(all_x, exact_config)
            state_cache: dict[tuple[str, int, int], np.ndarray] = {("exact", 2, 2): exact_states}
            for variant in variants:
                rows.append(evaluate_variant(variant, prepared, seed, args, exact_states, state_cache))

    summary = summarize(rows)
    comparisons = paired_comparisons(rows)
    convergence = convergence_analysis(summary)
    write_csv(output_dir / "runs.csv", rows)
    write_csv(output_dir / "summary.csv", summary)
    metadata = {
        "profile": args.profile,
        "datasets": dataset_names,
        "seeds": seeds,
        "arguments": vars(args) | {"output_dir": str(output_dir)},
        "variants": [asdict(variant) for variant in variants],
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "paired_comparisons": comparisons,
        "convergence": convergence,
        "summary": summary,
    }
    (output_dir / "summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_report(output_dir / "report.md", summary, args, comparisons, convergence)
    make_plots(output_dir, summary)
    print(json.dumps({"output_dir": str(output_dir), "runs": len(rows), "summary_rows": len(summary)}, indent=2))


if __name__ == "__main__":
    main()
