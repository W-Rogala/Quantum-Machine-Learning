from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "pdfs" / "qml_achievements"

NAVY = "#17324D"
TEAL = "#0D7C7B"
ORANGE = "#D97706"
RED = "#B42318"
GREEN = "#3F7D57"
GRAY = "#6B7280"
LIGHT = "#E7ECEF"


def setup() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "axes.edgecolor": "#9CA3AF",
            "axes.linewidth": 0.7,
            "axes.grid": True,
            "grid.color": "#D1D5DB",
            "grid.alpha": 0.55,
            "grid.linewidth": 0.6,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight")
    plt.close(fig)


def model_accuracy_chart() -> None:
    path = (
        ROOT
        / "analysis_output"
        / "resource_aware_hamiltonian_benchmark"
        / "full_results"
        / "completion.json"
    )
    summary = json.loads(path.read_text(encoding="utf-8"))["summary"]
    wanted = [
        ("svm_rbf", "SVM-RBF", "classical", 0),
        ("random_fourier_features", "Random Fourier", "classical", 0),
        ("gradient_boosting", "Boosting", "classical", 0),
        ("linear", "Model liniowy", "classical", 0),
        ("fidelity", "Fidelity idealny", "ideal_statevector", 0),
        ("projected", "Projected idealny", "ideal_statevector", 0),
        ("fidelity", "Fidelity 1 mln", "finite_shot_simulator", 1_000_000),
        ("projected", "Projected 1 mln", "finite_shot_simulator", 1_000_000),
    ]
    labels: list[str] = []
    means: list[float] = []
    colors: list[str] = []
    for family, label, regime, budget in wanted:
        row = next(
            item
            for item in summary
            if item["family"] == family
            and item["evaluation_regime"] == regime
            and int(item["circuit_shot_budget"]) == budget
        )
        labels.append(label)
        means.append(float(row["test_balanced_accuracy_mean"]))
        colors.append(
            NAVY if regime == "classical" else (TEAL if regime == "ideal_statevector" else ORANGE)
        )
    order = np.argsort(means)
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    bars = ax.barh(
        np.asarray(labels)[order],
        np.asarray(means)[order],
        color=np.asarray(colors)[order],
        height=0.68,
    )
    ax.set_xlim(0.82, 1.0)
    ax.set_xlabel("Średnia balanced accuracy, 75 outer splitów")
    ax.set_title("Pełny benchmark: jakość modeli przy zamrożonym protokole")
    ax.grid(axis="y", visible=False)
    for bar, value in zip(bars, np.asarray(means)[order], strict=True):
        ax.text(value + 0.002, bar.get_y() + bar.get_height() / 2, f"{value:.3f}", va="center")
    save(fig, "model_accuracy.png")


def equal_budget_chart() -> None:
    path = (
        ROOT
        / "analysis_output"
        / "resource_aware_hamiltonian_benchmark"
        / "full_results"
        / "outer_results_cost_corrected.csv"
    )
    cells: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["family"] not in {"fidelity", "projected"}:
                continue
            if row["evaluation_regime"] != "finite_shot_simulator":
                continue
            key = (row["dataset"], row["family"], int(row["circuit_shot_budget"]))
            cells[key].append(float(row["test_balanced_accuracy"]))
    datasets = ["moons", "wdbc", "wine"]
    budgets = [200_000, 1_000_000]
    x = np.arange(len(datasets))
    width = 0.19
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    offsets = [-1.5, -0.5, 0.5, 1.5]
    index = 0
    for budget, hatch in zip(budgets, ["", "//"], strict=True):
        for family, color in [("fidelity", ORANGE), ("projected", TEAL)]:
            values = [np.mean(cells[(dataset, family, budget)]) for dataset in datasets]
            label = f"{family.capitalize()}, {budget // 1000} tys. shots"
            ax.bar(
                x + offsets[index] * width,
                values,
                width,
                label=label,
                color=color,
                hatch=hatch,
                edgecolor="white",
                linewidth=0.5,
            )
            index += 1
    ax.set_xticks(x, ["moons", "WDBC", "wine"])
    ax.set_ylim(0.72, 1.01)
    ax.set_ylabel("Balanced accuracy")
    ax.set_title("Fidelity i projected przy identycznym budżecie circuit-shots")
    ax.legend(
        ncols=2,
        fontsize=8,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
    )
    ax.grid(axis="x", visible=False)
    save(fig, "equal_budget.png")


def trotter_scaling_chart() -> None:
    path = ROOT / "analysis_output" / "trotter_scaling_smoke" / "candidates.csv"
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    fig, axes = plt.subplots(2, 2, figsize=(7.3, 5.4), sharex="col")
    for column, n_qubits in enumerate([2, 3]):
        subset = [
            row
            for row in rows
            if int(row["n_qubits"]) == n_qubits
            and int(row["depth_budget"]) == 1800
            and row["feasible"] == "True"
        ]
        for order, color in [(1, ORANGE), (2, TEAL)]:
            ordered = sorted(
                (row for row in subset if int(row["order"]) == order),
                key=lambda row: float(row["delta_t"]),
            )
            x = [float(row["delta_t"]) for row in ordered]
            y = [float(row["objective"]) for row in ordered]
            depth = [int(row["serial_depth_proxy"]) for row in ordered]
            axes[0, column].plot(x, y, color=color, lw=1.6, label=f"rząd {order}")
            axes[1, column].step(x, depth, where="mid", color=color, lw=1.6)
        axes[0, column].set_title(f"n = {n_qubits}, pełna baza Pauliego")
        axes[0, column].set_ylabel("Funkcja celu" if column == 0 else "")
        axes[1, column].set_ylabel("Proxy-depth" if column == 0 else "")
        axes[1, column].set_xlabel("Nominalny krok Δt")
        axes[0, column].legend(frameon=False, fontsize=8)
        axes[0, column].grid(axis="x", visible=False)
        axes[1, column].grid(axis="x", visible=False)
    fig.suptitle("Siatka Trottera co 0,01: koszt jest funkcją schodkową", y=1.01, fontweight="bold")
    save(fig, "trotter_scaling.png")


def ibm_pilot_chart() -> None:
    base = ROOT / "analysis_output"
    dirs = {
        "Fidelity": base
        / "ibm_validation_fidelity_v2"
        / "ibm_kingston_qpu_layout_89_90_91_98_20260825",
        "Projected": base
        / "ibm_validation_projected_v2"
        / "ibm_kingston_qpu_layout_89_90_91_98_20260825",
    }
    qpu_ba = []
    ideal_ba = []
    train_error = []
    test_error = []
    for directory in dirs.values():
        data = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
        qpu_ba.append(float(data["classification"]["test_balanced_accuracy"]))
        ideal_ba.append(float(data["classification"]["ideal_test_balanced_accuracy"]))
        train_error.append(float(data["kernel_error"]["train_relative_frobenius"]))
        test_error.append(float(data["kernel_error"]["test_relative_frobenius"]))
    labels = list(dirs)
    x = np.arange(2)
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25))
    axes[0].bar(x - width / 2, ideal_ba, width, label="Idealny", color=LIGHT, edgecolor=NAVY)
    axes[0].bar(x + width / 2, qpu_ba, width, label="IBM QPU", color=[ORANGE, TEAL])
    axes[0].set_xticks(x, labels)
    axes[0].set_ylim(0, 1.08)
    axes[0].set_ylabel("Balanced accuracy")
    axes[0].set_title("Klasyfikacja, 4 próbki testowe")
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].grid(axis="x", visible=False)
    axes[1].bar(x - width / 2, train_error, width, label="Train", color=NAVY)
    axes[1].bar(x + width / 2, test_error, width, label="Test", color=RED)
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("Względny błąd Frobeniusa")
    axes[1].set_title("Odchylenie kernela QPU od ideału")
    axes[1].legend(frameon=False, fontsize=8)
    axes[1].grid(axis="x", visible=False)
    save(fig, "ibm_pilot.png")


def photonic_chart() -> None:
    path = ROOT / "analysis_output" / "photonic_kernel_x8_smoke" / "analysis.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    labels = ["Hellinger", "Moment-RBF", "Klasyczny RBF"]
    ideal = [
        data["ideal"]["hellinger"]["balanced_accuracy"],
        data["ideal"]["moment_rbf"]["balanced_accuracy"],
        data["classical_rbf"]["balanced_accuracy"],
    ]
    finite = [
        data["finite_shot"]["hellinger"]["balanced_accuracy"],
        data["finite_shot"]["moment_rbf"]["balanced_accuracy"],
        np.nan,
    ]
    x = np.arange(3)
    width = 0.34
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    ax.bar(x - width / 2, ideal, width, color=NAVY, label="Idealny")
    ax.bar(x + width / 2, finite, width, color=TEAL, label="Finite-shot")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Balanced accuracy")
    ax.set_title("Fotoniczny CV/GBS: wspólne rekordy PNR, 12 000 shots")
    ax.legend(
        frameon=False,
        ncols=2,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
    )
    ax.grid(axis="x", visible=False)
    save(fig, "photonic.png")


def main() -> None:
    setup()
    model_accuracy_chart()
    equal_budget_chart()
    trotter_scaling_chart()
    ibm_pilot_chart()
    photonic_chart()
    print(json.dumps({"output_dir": str(OUT), "charts": sorted(path.name for path in OUT.glob("*.png"))}))


if __name__ == "__main__":
    main()
