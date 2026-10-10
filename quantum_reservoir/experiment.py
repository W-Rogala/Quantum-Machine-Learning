from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "qml-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .benchmarks import BenchmarkSeries, benchmark_suite
from .core import (
    QuantumReservoir,
    ReservoirConfig,
    circuit_resources,
    exact_unitary,
    process_infidelity,
)


@dataclass(frozen=True)
class SplitConfig:
    washout: int = 50
    train: int = 450
    validation: int = 150
    test: int = 300

    @property
    def total(self) -> int:
        return self.washout + self.train + self.validation + self.test

    def validate(self, available: int) -> None:
        if min(self.washout, self.train, self.validation, self.test) < 1:
            raise ValueError("All split sizes must be positive")
        if self.total > available:
            raise ValueError(f"Split needs {self.total} rows but only {available} are available")


def nrmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denominator = float(np.std(y_true))
    if denominator <= 0:
        raise ValueError("NRMSE requires a target with non-zero standard deviation")
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)) / denominator)


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    residual = float(np.sum((y_true - y_pred) ** 2))
    total = float(np.sum((y_true - np.mean(y_true)) ** 2))
    return float(1.0 - residual / total)


def _fit_ridge(
    features: np.ndarray,
    target: np.ndarray,
    alpha: float,
) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    mean = np.mean(features, axis=0)
    scale = np.std(features, axis=0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    standardized = (features - mean) / scale
    target_mean = float(np.mean(target))
    centered_target = target - target_mean
    gram = standardized.T @ standardized + alpha * np.eye(standardized.shape[1])
    coefficients = np.linalg.solve(gram, standardized.T @ centered_target)
    return coefficients, target_mean, mean, scale


def _predict_ridge(
    features: np.ndarray,
    model: tuple[np.ndarray, float, np.ndarray, np.ndarray],
) -> np.ndarray:
    coefficients, target_mean, mean, scale = model
    return target_mean + ((features - mean) / scale) @ coefficients


def _split_arrays(
    features: np.ndarray,
    targets: np.ndarray,
    split: SplitConfig,
) -> tuple[np.ndarray, ...]:
    split.validate(len(features))
    train_start = split.washout
    train_end = train_start + split.train
    validation_end = train_end + split.validation
    test_end = validation_end + split.test
    return (
        features[train_start:train_end],
        targets[train_start:train_end],
        features[train_end:validation_end],
        targets[train_end:validation_end],
        features[validation_end:test_end],
        targets[validation_end:test_end],
    )


def evaluate_configuration(
    benchmark: BenchmarkSeries,
    config: ReservoirConfig,
    split: SplitConfig,
    ridge_alphas: Iterable[float],
    reference_unitary: np.ndarray,
) -> tuple[dict[str, float | int | str | None], np.ndarray, np.ndarray]:
    reservoir = QuantumReservoir(config)
    reservoir_features, transform_seconds = reservoir.transform(benchmark.inputs)
    features = np.column_stack((benchmark.inputs, reservoir_features))
    x_train, y_train, x_validation, y_validation, x_test, y_test = _split_arrays(
        features,
        benchmark.targets,
        split,
    )

    alpha_scores: list[tuple[float, float]] = []
    for alpha in ridge_alphas:
        model = _fit_ridge(x_train, y_train, float(alpha))
        validation_prediction = _predict_ridge(x_validation, model)
        alpha_scores.append((nrmse(y_validation, validation_prediction), float(alpha)))
    validation_nrmse, selected_alpha = min(alpha_scores)

    x_refit = np.vstack((x_train, x_validation))
    y_refit = np.concatenate((y_train, y_validation))
    final_model = _fit_ridge(x_refit, y_refit, selected_alpha)
    test_prediction = _predict_ridge(x_test, final_model)
    resources = circuit_resources(config)
    infidelity = (
        0.0
        if config.method == "exact"
        else process_infidelity(reference_unitary, reservoir.unitary)
    )
    record: dict[str, float | int | str | None] = {
        "benchmark": benchmark.name,
        "horizon": benchmark.horizon,
        "reservoir_seed": config.disorder_seed,
        "method": config.method,
        "trotter_order": 0 if config.method == "exact" else config.trotter_order,
        "trotter_steps": 0 if config.method == "exact" else config.trotter_steps,
        "ridge_alpha": selected_alpha,
        "validation_nrmse": validation_nrmse,
        "test_nrmse": nrmse(y_test, test_prediction),
        "test_mae": mae(y_test, test_prediction),
        "test_r2": r2_score(y_test, test_prediction),
        "process_infidelity": infidelity,
        "unitary_build_seconds": reservoir.unitary_build_seconds,
        "transform_seconds": transform_seconds,
        "trace_error": reservoir.density_trace_check(benchmark.inputs[:20]),
        "n_features": features.shape[1],
        **resources,
    }
    return record, y_test.copy(), test_prediction


def _mean_std(values: Iterable[float]) -> tuple[float, float]:
    array = np.asarray(list(values), dtype=float)
    return float(np.mean(array)), float(np.std(array, ddof=1)) if len(array) > 1 else 0.0


def _candidate_statistics(records: list[dict[str, object]]) -> list[dict[str, object]]:
    exact_lookup = {
        (record["benchmark"], record["reservoir_seed"]): float(record["validation_nrmse"])
        for record in records
        if record["method"] == "exact"
    }
    keys = sorted(
        {
            (int(record["trotter_order"]), int(record["trotter_steps"]))
            for record in records
            if record["method"] == "trotter"
        }
    )
    statistics: list[dict[str, object]] = []
    for order, steps in keys:
        subset = [
            record
            for record in records
            if record["method"] == "trotter"
            and int(record["trotter_order"]) == order
            and int(record["trotter_steps"]) == steps
        ]
        validation_ratios = [
            float(record["validation_nrmse"])
            / exact_lookup[(record["benchmark"], record["reservoir_seed"])]
            for record in subset
        ]
        ratio_mean, ratio_std = _mean_std(validation_ratios)
        infidelity_mean, infidelity_std = _mean_std(
            float(record["process_infidelity"]) for record in subset
        )
        statistics.append(
            {
                "trotter_order": order,
                "trotter_steps": steps,
                "validation_ratio_mean": ratio_mean,
                "validation_ratio_std": ratio_std,
                "process_infidelity_mean": infidelity_mean,
                "process_infidelity_std": infidelity_std,
                "two_qubit_gates": int(subset[0]["two_qubit_gates"]),
                "logical_depth_proxy": int(subset[0]["logical_depth_proxy"]),
                "evaluations": len(subset),
            }
        )
    return statistics


def select_trotter_configuration(
    candidate_statistics: list[dict[str, object]],
    performance_tolerance: float = 0.02,
    infidelity_limit: float = 0.01,
) -> tuple[dict[str, object], str]:
    acceptable = [
        candidate
        for candidate in candidate_statistics
        if float(candidate["validation_ratio_mean"]) <= 1.0 + performance_tolerance
        and float(candidate["process_infidelity_mean"]) <= infidelity_limit
    ]
    if acceptable:
        selected = min(
            acceptable,
            key=lambda candidate: (
                int(candidate["two_qubit_gates"]),
                float(candidate["validation_ratio_mean"]),
                float(candidate["process_infidelity_mean"]),
            ),
        )
        reason = (
            "Najniższy koszt dwukubitowy wśród wariantów z walidacyjnym NRMSE nie gorszym "
            f"niż dokładny model o więcej niż {100 * performance_tolerance:.1f}% i średnią "
            f"infidelity <= {infidelity_limit:g}."
        )
    else:
        selected = min(
            candidate_statistics,
            key=lambda candidate: (
                float(candidate["validation_ratio_mean"]),
                int(candidate["two_qubit_gates"]),
            ),
        )
        reason = (
            "Żaden wariant nie spełnił obu ograniczeń; wybrano najniższy średni "
            "walidacyjny NRMSE, a koszt bramek użyto do rozstrzygnięcia remisu."
        )
    return selected, reason


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    columns = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _comparison_summary(
    records: list[dict[str, object]],
    selected: dict[str, object],
) -> list[dict[str, object]]:
    order = int(selected["trotter_order"])
    steps = int(selected["trotter_steps"])
    summaries: list[dict[str, object]] = []
    for benchmark in sorted({str(record["benchmark"]) for record in records}):
        exact = [
            record for record in records if record["benchmark"] == benchmark and record["method"] == "exact"
        ]
        trotter = [
            record
            for record in records
            if record["benchmark"] == benchmark
            and record["method"] == "trotter"
            and int(record["trotter_order"]) == order
            and int(record["trotter_steps"]) == steps
        ]
        exact_mean, exact_std = _mean_std(float(row["test_nrmse"]) for row in exact)
        trotter_mean, trotter_std = _mean_std(float(row["test_nrmse"]) for row in trotter)
        exact_runtime, _ = _mean_std(
            float(row["unitary_build_seconds"]) + float(row["transform_seconds"]) for row in exact
        )
        trotter_runtime, _ = _mean_std(
            float(row["unitary_build_seconds"]) + float(row["transform_seconds"]) for row in trotter
        )
        summaries.append(
            {
                "benchmark": benchmark,
                "exact_test_nrmse_mean": exact_mean,
                "exact_test_nrmse_std": exact_std,
                "trotter_test_nrmse_mean": trotter_mean,
                "trotter_test_nrmse_std": trotter_std,
                "relative_nrmse_change_percent": 100.0 * (trotter_mean / exact_mean - 1.0),
                "exact_simulation_seconds_mean": exact_runtime,
                "trotter_simulation_seconds_mean": trotter_runtime,
                "simulation_speedup": exact_runtime / trotter_runtime,
                "trotter_order": order,
                "trotter_steps": steps,
                "trotter_two_qubit_gates_per_input": int(trotter[0]["two_qubit_gates"]),
                "trotter_logical_depth_proxy": int(trotter[0]["logical_depth_proxy"]),
            }
        )
    return summaries


def _plot_validation_tradeoff(
    candidate_statistics: list[dict[str, object]],
    selected: dict[str, object],
    output_path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(8.5, 5.2))
    palette = {1: "#C56A2D", 2: "#315C8A"}
    selected_key = (int(selected["trotter_order"]), int(selected["trotter_steps"]))
    for order in (1, 2):
        subset = [item for item in candidate_statistics if int(item["trotter_order"]) == order]
        subset.sort(key=lambda item: int(item["two_qubit_gates"]))
        x = [int(item["two_qubit_gates"]) for item in subset]
        y = [float(item["validation_ratio_mean"]) for item in subset]
        error = [float(item["validation_ratio_std"]) for item in subset]
        axis.errorbar(
            x,
            y,
            yerr=error,
            marker="o",
            linewidth=1.8,
            capsize=3,
            color=palette[order],
            label=f"Trotter rzędu {order}",
        )
        for item, x_value, y_value in zip(subset, x, y, strict=True):
            marker = (order, int(item["trotter_steps"]))
            axis.annotate(
                f"s={item['trotter_steps']}",
                (x_value, y_value),
                xytext=(5, 6 if marker != selected_key else 10),
                textcoords="offset points",
                fontsize=8,
                fontweight="bold" if marker == selected_key else "normal",
            )
    axis.axhline(1.0, color="#353A40", linestyle="--", linewidth=1.2, label="Ewolucja dokładna")
    axis.set_xlim(left=0)
    axis.set_xlabel("Logiczne bramki dwukubitowe na próbkę")
    axis.set_ylabel("Walidacyjny NRMSE / NRMSE modelu dokładnego")
    axis.set_title("Kompromis dokładność–koszt dla formuł Trottera")
    axis.grid(axis="y", color="#D9DEE5", linewidth=0.8)
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_test_comparison(summary: list[dict[str, object]], output_path: Path) -> None:
    labels = [str(row["benchmark"]) for row in summary]
    positions = np.arange(len(labels), dtype=float)
    width = 0.34
    exact = [float(row["exact_test_nrmse_mean"]) for row in summary]
    exact_error = [float(row["exact_test_nrmse_std"]) for row in summary]
    trotter = [float(row["trotter_test_nrmse_mean"]) for row in summary]
    trotter_error = [float(row["trotter_test_nrmse_std"]) for row in summary]
    fig, axis = plt.subplots(figsize=(8.5, 5.2))
    axis.bar(
        positions - width / 2,
        exact,
        width,
        yerr=exact_error,
        capsize=4,
        color="#BFC7D1",
        edgecolor="#353A40",
        label="Bez trotteryzacji (dokładna)",
    )
    axis.bar(
        positions + width / 2,
        trotter,
        width,
        yerr=trotter_error,
        capsize=4,
        color="#315C8A",
        edgecolor="#244563",
        label="Zoptymalizowana Trotteryzacja",
    )
    axis.set_xticks(positions, labels)
    axis.set_ylim(bottom=0)
    axis.set_ylabel("Testowy NRMSE (średnia ± SD po seedach)")
    axis.set_title("Jakość prognozowania: ewolucja dokładna i Trotterowska")
    axis.grid(axis="y", color="#D9DEE5", linewidth=0.8)
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_convergence(candidate_statistics: list[dict[str, object]], output_path: Path) -> None:
    fig, axis = plt.subplots(figsize=(8.5, 5.2))
    palette = {1: "#C56A2D", 2: "#315C8A"}
    for order in (1, 2):
        subset = [item for item in candidate_statistics if int(item["trotter_order"]) == order]
        subset.sort(key=lambda item: int(item["trotter_steps"]))
        axis.plot(
            [int(item["trotter_steps"]) for item in subset],
            [float(item["process_infidelity_mean"]) for item in subset],
            marker="o",
            linewidth=1.8,
            color=palette[order],
            label=f"Rząd {order}",
        )
    axis.set_xscale("log", base=2)
    axis.set_yscale("log")
    axis.set_xlabel("Liczba kroków Trottera")
    axis.set_ylabel("Średnia infidelity procesu")
    axis.set_title("Zbieżność formuł Trottera do ewolucji dokładnej")
    axis.grid(color="#D9DEE5", linewidth=0.8, which="both")
    axis.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_forecasts(
    benchmarks: tuple[BenchmarkSeries, ...],
    predictions: dict[tuple[str, int, str, int, int], tuple[np.ndarray, np.ndarray]],
    selected: dict[str, object],
    seed: int,
    output_path: Path,
) -> None:
    order = int(selected["trotter_order"])
    steps = int(selected["trotter_steps"])
    fig, axes = plt.subplots(len(benchmarks), 1, figsize=(10, 6.5), sharex=False)
    axes = np.atleast_1d(axes)
    for axis, benchmark in zip(axes, benchmarks, strict=True):
        exact_target, exact_prediction = predictions[(benchmark.name, seed, "exact", 0, 0)]
        trotter_target, trotter_prediction = predictions[
            (benchmark.name, seed, "trotter", order, steps)
        ]
        if not np.allclose(exact_target, trotter_target):
            raise AssertionError("Exact and Trotter targets differ")
        shown = min(140, len(exact_target))
        time = np.arange(shown)
        axis.plot(time, exact_target[:shown], color="#353A40", linewidth=1.5, label="Cel")
        axis.plot(time, exact_prediction[:shown], color="#AAB3BE", linewidth=1.2, label="Dokładna")
        axis.plot(
            time,
            trotter_prediction[:shown],
            color="#315C8A",
            linewidth=1.2,
            linestyle="--",
            label=f"Trotter O{order}, s={steps}",
        )
        axis.set_title(benchmark.name)
        axis.set_ylabel("Wartość")
        axis.grid(color="#E2E6EB", linewidth=0.7)
    axes[-1].set_xlabel("Indeks próbki testowej")
    axes[0].legend(frameon=False, ncol=3)
    fig.suptitle("Przykładowe prognozy testowe dla wspólnego seedu rezerwuaru", y=1.01)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def run_experiment(
    output_dir: str | Path,
    split: SplitConfig = SplitConfig(),
    n_qubits: int = 4,
    reservoir_seeds: tuple[int, ...] = (7, 11, 19),
    trotter_steps: tuple[int, ...] = (1, 2, 4, 8),
    ridge_alphas: tuple[float, ...] = (1e-8, 1e-6, 1e-4, 1e-2, 1.0, 10.0),
) -> dict[str, object]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    benchmarks = benchmark_suite(length=split.total, seed=1234)
    records: list[dict[str, object]] = []
    predictions: dict[tuple[str, int, str, int, int], tuple[np.ndarray, np.ndarray]] = {}

    for reservoir_seed in reservoir_seeds:
        base = ReservoirConfig(n_qubits=n_qubits, disorder_seed=reservoir_seed, method="exact")
        reference = exact_unitary(base)
        configurations = [base]
        configurations.extend(
            replace(
                base,
                method="trotter",
                trotter_order=order,
                trotter_steps=steps,
            )
            for order in (1, 2)
            for steps in trotter_steps
        )
        for benchmark in benchmarks:
            for config in configurations:
                record, target, prediction = evaluate_configuration(
                    benchmark=benchmark,
                    config=config,
                    split=split,
                    ridge_alphas=ridge_alphas,
                    reference_unitary=reference,
                )
                records.append(record)
                key = (
                    benchmark.name,
                    reservoir_seed,
                    config.method,
                    0 if config.method == "exact" else config.trotter_order,
                    0 if config.method == "exact" else config.trotter_steps,
                )
                predictions[key] = (target, prediction)

    candidate_statistics = _candidate_statistics(records)
    selected, selection_reason = select_trotter_configuration(candidate_statistics)
    comparison = _comparison_summary(records, selected)

    selected_order = int(selected["trotter_order"])
    selected_steps = int(selected["trotter_steps"])
    prediction_rows: list[dict[str, object]] = []
    for benchmark in benchmarks:
        for reservoir_seed in reservoir_seeds:
            target, exact_prediction = predictions[(benchmark.name, reservoir_seed, "exact", 0, 0)]
            _, trotter_prediction = predictions[
                (benchmark.name, reservoir_seed, "trotter", selected_order, selected_steps)
            ]
            for index, (actual, exact_value, trotter_value) in enumerate(
                zip(target, exact_prediction, trotter_prediction, strict=True)
            ):
                prediction_rows.append(
                    {
                        "benchmark": benchmark.name,
                        "reservoir_seed": reservoir_seed,
                        "test_index": index,
                        "actual": float(actual),
                        "exact_prediction": float(exact_value),
                        "trotter_prediction": float(trotter_value),
                    }
                )

    _write_csv(output_path / "all_results.csv", records)
    _write_csv(output_path / "candidate_statistics.csv", candidate_statistics)
    _write_csv(output_path / "comparison_summary.csv", comparison)
    _write_csv(output_path / "predictions.csv", prediction_rows)
    _plot_validation_tradeoff(candidate_statistics, selected, output_path / "validation_tradeoff.png")
    _plot_test_comparison(comparison, output_path / "test_nrmse_comparison.png")
    _plot_convergence(candidate_statistics, output_path / "trotter_convergence.png")
    _plot_forecasts(
        benchmarks,
        predictions,
        selected,
        reservoir_seeds[0],
        output_path / "forecast_examples.png",
    )

    summary: dict[str, object] = {
        "experiment": "Sequential reset-injected QRC: exact vs Suzuki-Trotter evolution",
        "reservoir": asdict(ReservoirConfig(n_qubits=n_qubits)),
        "split": asdict(split),
        "reservoir_seeds": list(reservoir_seeds),
        "trotter_steps_grid": list(trotter_steps),
        "ridge_alphas": list(ridge_alphas),
        "selection": {**selected, "reason": selection_reason},
        "comparison": comparison,
        "methodological_notes": [
            "The exact unitary is a simulator reference, not a directly compiled hardware circuit.",
            "Trotter selection uses validation data only; test data is evaluated after selection.",
            "Uncertainty is the sample standard deviation across reservoir disorder seeds.",
            "Logical gate counts are pre-transpilation estimates per input time step.",
        ],
    }
    (output_path / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="analysis_output/qrc_trotter_benchmark",
        help="Directory for CSV, JSON, and PNG outputs.",
    )
    parser.add_argument("--n-qubits", type=int, default=4)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 11, 19])
    parser.add_argument("--steps", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--quick", action="store_true", help="Use a small smoke-test configuration.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.quick:
        split = SplitConfig(washout=20, train=100, validation=50, test=80)
        seeds = (args.seeds[0],)
        steps = tuple(step for step in args.steps if step <= 2) or (1, 2)
    else:
        split = SplitConfig()
        seeds = tuple(args.seeds)
        steps = tuple(args.steps)
    summary = run_experiment(
        output_dir=args.output_dir,
        split=split,
        n_qubits=args.n_qubits,
        reservoir_seeds=seeds,
        trotter_steps=steps,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
