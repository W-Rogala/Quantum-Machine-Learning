from __future__ import annotations

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
os.environ.setdefault("MPLCONFIGDIR", str(ANALYSIS / ".matplotlib"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


RESULT_PATH = ANALYSIS / "scar_wine_ibm_qpu_result.json"
HISTORY_PATH = ANALYSIS / "scar_wine_ibm_qpu_history.csv"
SIMULATOR_PATH = ANALYSIS / "scar_wine_benchmark_results.csv"
OUTPUT_PNG = ANALYSIS / "scar_wine_ibm_qpu_comparison.png"
OUTPUT_SVG = ANALYSIS / "scar_wine_ibm_qpu_comparison.svg"


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def annotate_bars(axis: plt.Axes, bars: list) -> None:
    for bar in bars:
        value = float(bar.get_height())
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.025,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    history = load_csv(HISTORY_PATH)
    simulator_runs = load_csv(SIMULATOR_PATH)

    qpu = result["qpu_result"]
    classical = result["classical_reference"]
    seed = int(qpu["seed"])
    simulator = next(
        row
        for row in simulator_runs
        if row["model"] == "scar_qnn" and int(row["seed"]) == seed
    )

    epochs = np.asarray([int(row["epoch"]) for row in history])
    train_loss = np.asarray([float(row["train_loss"]) for row in history])
    validation_loss = np.asarray(
        [float(row["validation_loss"]) for row in history]
    )
    train_accuracy = np.asarray(
        [float(row["train_accuracy"]) for row in history]
    )
    validation_accuracy = np.asarray(
        [float(row["validation_accuracy"]) for row in history]
    )

    charge_seconds = sum(
        float(job["job_metrics"]["usage"]["qpu_charge_time_seconds"])
        for job in qpu["jobs"]
    )
    architecture = result["architecture"]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.2))
    fig.subplots_adjust(
        left=0.07,
        right=0.96,
        bottom=0.11,
        top=0.86,
        hspace=0.40,
        wspace=0.24,
    )
    fig.suptitle(
        "SCAR-QNN na IBM Quantum: klasyfikacja win",
        fontsize=17,
        fontweight="bold",
        y=0.98,
    )
    fig.text(
        0.5,
        0.94,
        (
            f"{architecture['backend']} | Heron r2 | "
            f"depth {architecture['transpiled_depth']} | "
            f"{architecture['transpiled_two_qubit_gate_count']} CZ | "
            f"QPU charge {charge_seconds / 60:.1f} min"
        ),
        ha="center",
        va="top",
        color="#374151",
        fontsize=10.5,
    )

    loss_axis = axes[0, 0]
    loss_axis.plot(
        epochs,
        train_loss,
        marker="o",
        color="#007C83",
        linewidth=2,
        label="Trening",
    )
    loss_axis.plot(
        epochs,
        validation_loss,
        marker="s",
        color="#D97706",
        linewidth=2,
        label="Walidacja",
    )
    loss_axis.axhline(
        np.log(3),
        color="#6B7280",
        linestyle="--",
        linewidth=1.4,
        label="Losowy klasyfikator: ln(3)",
    )
    loss_axis.axvline(
        qpu["best_epoch"],
        color="#B91C1C",
        linestyle=":",
        linewidth=1.4,
        label=f"Checkpoint: epoka {qpu['best_epoch']}",
    )
    loss_axis.set(
        title="Strata podczas uczenia na QPU",
        xlabel="Epoka SPSA",
        ylabel="Cross-entropy",
        xticks=epochs,
    )
    loss_axis.grid(axis="y", alpha=0.25)
    loss_axis.legend(frameon=False, fontsize=8.5)

    accuracy_axis = axes[0, 1]
    accuracy_axis.plot(
        epochs,
        train_accuracy,
        marker="o",
        color="#007C83",
        linewidth=2,
        label="Trening",
    )
    accuracy_axis.plot(
        epochs,
        validation_accuracy,
        marker="s",
        color="#D97706",
        linewidth=2,
        label="Walidacja",
    )
    accuracy_axis.axhline(
        1 / 3,
        color="#6B7280",
        linestyle="--",
        linewidth=1.4,
        label="Poziom losowy",
    )
    accuracy_axis.set(
        title="Accuracy podczas uczenia na QPU",
        xlabel="Epoka SPSA",
        ylabel="Accuracy",
        xticks=epochs,
        ylim=(0.2, 0.65),
    )
    accuracy_axis.grid(axis="y", alpha=0.25)
    accuracy_axis.legend(frameon=False, fontsize=8.5)

    comparison_axis = axes[1, 0]
    labels = ["IBM QPU\n12 epok", "Idealny QNN\n160 epok", "MLP\n160 epok"]
    accuracy_values = [
        float(qpu["test"]["accuracy"]),
        float(simulator["test_accuracy"]),
        float(classical["test_accuracy"]),
    ]
    f1_values = [
        float(qpu["test"]["macro_f1"]),
        float(simulator["test_macro_f1"]),
        float(classical["test_macro_f1"]),
    ]
    positions = np.arange(len(labels))
    width = 0.34
    accuracy_bars = comparison_axis.bar(
        positions - width / 2,
        accuracy_values,
        width,
        color="#007C83",
        label="Accuracy",
    )
    f1_bars = comparison_axis.bar(
        positions + width / 2,
        f1_values,
        width,
        color="#D97706",
        label="Macro F1",
    )
    annotate_bars(comparison_axis, list(accuracy_bars) + list(f1_bars))
    comparison_axis.set(
        title=f"Wynik testowy, seed {seed}",
        ylabel="Wartość metryki",
        xticks=positions,
        xticklabels=labels,
        ylim=(0, 1.12),
    )
    comparison_axis.grid(axis="y", alpha=0.25)
    comparison_axis.legend(frameon=False, loc="upper left")
    confusion_axis = axes[1, 1]
    confusion = np.asarray(qpu["test"]["confusion"], dtype=int)
    image = confusion_axis.imshow(confusion, cmap="YlOrRd", vmin=0)
    for row in range(confusion.shape[0]):
        for column in range(confusion.shape[1]):
            value = int(confusion[row, column])
            confusion_axis.text(
                column,
                row,
                str(value),
                ha="center",
                va="center",
                color="white" if value >= 7 else "#111827",
                fontsize=13,
                fontweight="bold",
            )
    confusion_axis.set(
        title="Macierz pomyłek SCAR-QNN na QPU",
        xlabel="Klasa przewidziana",
        ylabel="Klasa rzeczywista",
        xticks=range(3),
        yticks=range(3),
    )
    fig.colorbar(image, ax=confusion_axis, shrink=0.82, label="Liczba próbek")
    fig.text(
        0.07,
        0.025,
        "Uwaga: idealny QNN ma inny budżet optymalizacji; "
        "jest kontekstem, a nie czystym oszacowaniem szumu QPU.",
        fontsize=8.5,
        color="#4B5563",
    )

    fig.savefig(OUTPUT_PNG, dpi=180, facecolor="white")
    fig.savefig(OUTPUT_SVG, facecolor="white")
    print(f"Wrote {OUTPUT_PNG}")
    print(f"Wrote {OUTPUT_SVG}")


if __name__ == "__main__":
    main()
