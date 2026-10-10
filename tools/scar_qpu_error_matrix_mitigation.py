from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
os.environ.setdefault("MPLCONFIGDIR", str(ANALYSIS / ".matplotlib"))

if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from scar_ibm_fez_simulated_reproduction import ExactFakeFezEvaluator  # noqa: E402
from scar_physical_qpu_wine_benchmark import (  # noqa: E402
    IONQ,
    RIGETTI,
    QubitFeatureEvaluator,
    X8FeatureEvaluator,
    classical_result,
    train_hardware_model,
)
from scar_wine_qnn_benchmark import load_wine, prepare_split  # noqa: E402


OUTPUT_JSON = ANALYSIS / "scar_qpu_error_matrix_mitigation_results.json"
OUTPUT_HISTORY = ANALYSIS / "scar_qpu_error_matrix_mitigation_history.csv"
OUTPUT_REPORT = ANALYSIS / "scar_qpu_error_matrix_mitigation_report.md"
OUTPUT_PNG = ANALYSIS / "scar_qpu_error_matrix_mitigation_comparison.png"
OUTPUT_SVG = ANALYSIS / "scar_qpu_error_matrix_mitigation_comparison.svg"

CASE_ORDER = [
    "rigetti_ankaa3",
    "ionq_forte",
    "xanadu_x8",
    "ibm_reproduction",
    "ibm_tuned",
]
CASE_LABELS = {
    "rigetti_ankaa3": "Rigetti\nAnkaa-3",
    "ionq_forte": "IonQ\nForte",
    "xanadu_x8": "Xanadu\nX8",
    "ibm_reproduction": "IBM Fez\n12 epochs",
    "ibm_tuned": "IBM Fez\n64 epochs",
}
PROTOCOLS = {
    "rigetti_ankaa3": {
        "epochs": 64,
        "shots": 1024,
        "final_shots": 4096,
        "spsa_a": 0.10,
        "spsa_c": 0.08,
        "head_learning_rate": 0.08,
    },
    "ionq_forte": {
        "epochs": 64,
        "shots": 1024,
        "final_shots": 4096,
        "spsa_a": 0.10,
        "spsa_c": 0.08,
        "head_learning_rate": 0.08,
    },
    "xanadu_x8": {
        "epochs": 64,
        "shots": 1024,
        "final_shots": 4096,
        "spsa_a": 0.10,
        "spsa_c": 0.08,
        "head_learning_rate": 0.08,
    },
    "ibm_reproduction": {
        "epochs": 12,
        "shots": 256,
        "final_shots": 256,
        "spsa_a": 0.12,
        "spsa_c": 0.15,
        "head_learning_rate": 0.04,
    },
    "ibm_tuned": {
        "epochs": 64,
        "shots": 1024,
        "final_shots": 4096,
        "spsa_a": 0.10,
        "spsa_c": 0.08,
        "head_learning_rate": 0.08,
    },
}


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_history(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "case",
        "measurement_mode",
        "model",
        "epoch",
        "train_loss",
        "train_accuracy",
        "validation_loss",
        "validation_accuracy",
        "spsa_gain",
        "spsa_perturbation",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def make_evaluators(seed: int) -> dict[str, dict[str, Any]]:
    evaluators: dict[str, dict[str, Any]] = {}
    for mode in ("raw", "mitigated"):
        ibm = ExactFakeFezEvaluator(seed=seed, measurement_mode=mode)
        evaluators[mode] = {
            "rigetti_ankaa3": QubitFeatureEvaluator(
                RIGETTI,
                measurement_mode=mode,
            ),
            "ionq_forte": QubitFeatureEvaluator(
                IONQ,
                measurement_mode=mode,
            ),
            "xanadu_x8": X8FeatureEvaluator(measurement_mode=mode),
            "ibm_reproduction": ibm,
            "ibm_tuned": ibm,
        }
    return evaluators


def hardware_metadata(evaluators: dict[str, dict[str, Any]]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for mode in ("raw", "mitigated"):
        rigetti = evaluators[mode]["rigetti_ankaa3"]
        ionq = evaluators[mode]["ionq_forte"]
        xanadu = evaluators[mode]["xanadu_x8"]
        ibm = evaluators[mode]["ibm_tuned"]
        metadata[mode] = {
            "rigetti_ankaa3": {
                "profile": asdict(RIGETTI),
                "gate_noise": rigetti.noise_metadata,
                "measurement_response": rigetti.measurement_metadata(),
            },
            "ionq_forte": {
                "profile": asdict(IONQ),
                "gate_noise": ionq.noise_metadata,
                "measurement_response": ionq.measurement_metadata(),
            },
            "xanadu_x8": {
                "profile": xanadu.metadata,
                "visibility": xanadu.visibility,
                "measurement_response": xanadu.measurement_metadata(),
            },
            "ibm_fez": ibm.metadata(),
        }
    return metadata


def train_all(
    split: Any,
    evaluators: dict[str, dict[str, Any]],
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results: dict[str, Any] = {case: {} for case in CASE_ORDER}
    history: list[dict[str, Any]] = []
    for mode in ("raw", "mitigated"):
        for case in CASE_ORDER:
            protocol = PROTOCOLS[case]
            model_key = f"{case}_{mode}"
            print(f"\nTraining {model_key}...", flush=True)
            result, rows = train_hardware_model(
                model_key,
                split,
                evaluators[mode][case],
                epochs=protocol["epochs"],
                shots=protocol["shots"],
                final_shots=protocol["final_shots"],
                seed=seed,
                spsa_a=protocol["spsa_a"],
                spsa_c=protocol["spsa_c"],
                head_learning_rate=protocol["head_learning_rate"],
                weight_decay=1e-4,
                verbose=False,
            )
            results[case][mode] = result
            print(
                f"Finished {model_key}: test_acc={result['test']['accuracy']:.3f}, "
                f"macro_f1={result['test']['macro_f1']:.3f}",
                flush=True,
            )
            for row in rows:
                history.append(
                    {
                        "case": case,
                        "measurement_mode": mode,
                        **row,
                    }
                )
    return results, history


def build_comparison(results: dict[str, Any]) -> dict[str, Any]:
    comparison = {}
    for case in CASE_ORDER:
        raw = results[case]["raw"]["test"]
        mitigated = results[case]["mitigated"]["test"]
        comparison[case] = {
            "raw_accuracy": raw["accuracy"],
            "mitigated_accuracy": mitigated["accuracy"],
            "accuracy_delta": mitigated["accuracy"] - raw["accuracy"],
            "raw_macro_f1": raw["macro_f1"],
            "mitigated_macro_f1": mitigated["macro_f1"],
            "macro_f1_delta": mitigated["macro_f1"] - raw["macro_f1"],
        }
    return comparison


def plot_results(payload: dict[str, Any], history: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    comparison = payload["comparison"]
    x = np.arange(len(CASE_ORDER))
    labels = [CASE_LABELS[case] for case in CASE_ORDER]
    raw_color = "#64748B"
    fixed_color = "#2563EB"

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(14.2, 9.4))
    fig.subplots_adjust(
        left=0.07,
        right=0.92,
        bottom=0.10,
        top=0.88,
        hspace=0.42,
        wspace=0.27,
    )
    fig.suptitle(
        "SCAR-QNN: assignment-matrix error mitigation",
        fontsize=19,
        weight="bold",
        y=0.965,
    )
    fig.text(
        0.5,
        0.925,
        "Paired raw and corrected training | same hardware noise, shots, seed and hyperparameters",
        ha="center",
        color="#475569",
    )

    width = 0.36
    raw_accuracy = [comparison[case]["raw_accuracy"] for case in CASE_ORDER]
    fixed_accuracy = [comparison[case]["mitigated_accuracy"] for case in CASE_ORDER]
    bars_raw = axes[0, 0].bar(
        x - width / 2,
        raw_accuracy,
        width,
        color=raw_color,
        label="Raw readout",
    )
    bars_fixed = axes[0, 0].bar(
        x + width / 2,
        fixed_accuracy,
        width,
        color=fixed_color,
        label="Matrix corrected",
    )
    axes[0, 0].bar_label(bars_raw, fmt="%.2f", padding=2, fontsize=9)
    axes[0, 0].bar_label(bars_fixed, fmt="%.2f", padding=2, fontsize=9)
    axes[0, 0].set_title("Test accuracy")
    axes[0, 0].set_ylabel("Accuracy")
    axes[0, 0].set_xticks(x, labels)
    axes[0, 0].set_ylim(0.0, 1.05)
    axes[0, 0].grid(axis="y", alpha=0.25)
    axes[0, 0].legend(frameon=False, loc="lower right")

    colors = ["#C2410C", "#7C3AED", "#059669", "#111827", "#2563EB"]
    for case, color in zip(CASE_ORDER, colors, strict=True):
        for mode, style, alpha in (
            ("raw", "--", 0.55),
            ("mitigated", "-", 1.0),
        ):
            rows = [
                row
                for row in history
                if row["case"] == case and row["measurement_mode"] == mode
            ]
            axes[0, 1].plot(
                [int(row["epoch"]) + 1 for row in rows],
                [float(row["validation_loss"]) for row in rows],
                linestyle=style,
                color=color,
                alpha=alpha,
                linewidth=2 if mode == "mitigated" else 1.4,
                label=(CASE_LABELS[case].replace("\n", " ") if mode == "mitigated" else None),
            )
    axes[0, 1].set_title("Validation loss")
    axes[0, 1].set_xlabel("Epoch")
    axes[0, 1].set_ylabel("Cross entropy")
    axes[0, 1].grid(alpha=0.25)
    axes[0, 1].legend(frameon=False, fontsize=8, ncol=2)
    axes[0, 1].text(
        0.98,
        0.04,
        "solid: corrected\ndashed: raw",
        transform=axes[0, 1].transAxes,
        ha="right",
        va="bottom",
        color="#475569",
        fontsize=9,
    )

    accuracy_delta = [comparison[case]["accuracy_delta"] for case in CASE_ORDER]
    f1_delta = [comparison[case]["macro_f1_delta"] for case in CASE_ORDER]
    delta_colors = ["#16A34A" if value >= 0 else "#DC2626" for value in accuracy_delta]
    axes[1, 0].bar(
        x - width / 2,
        accuracy_delta,
        width,
        color=delta_colors,
        label="Accuracy delta",
    )
    axes[1, 0].bar(
        x + width / 2,
        f1_delta,
        width,
        color="#0F766E",
        alpha=0.75,
        label="Macro-F1 delta",
    )
    axes[1, 0].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1, 0].set_title("Correction impact on the test set")
    axes[1, 0].set_ylabel("Corrected minus raw")
    axes[1, 0].set_xticks(x, labels)
    axes[1, 0].grid(axis="y", alpha=0.25)
    axes[1, 0].legend(frameon=False)

    metadata = payload["hardware_models"]["mitigated"]
    matrix_keys = ["rigetti_ankaa3", "ionq_forte", "xanadu_x8", "ibm_fez", "ibm_fez"]
    condition_numbers = []
    projection_rates = []
    for key in matrix_keys:
        if key == "ibm_fez":
            response = metadata[key]["measurement_error_mitigation"]
        else:
            response = metadata[key]["measurement_response"]
        condition_numbers.append(response["max_condition_number"])
        projection_rates.append(100.0 * response["projection_rate"])
    condition_bars = axes[1, 1].bar(
        x - width / 2,
        condition_numbers,
        width,
        color="#7C3AED",
        label="Condition number",
    )
    axes[1, 1].bar_label(condition_bars, fmt="%.2f", padding=2, fontsize=9)
    axes[1, 1].set_title("Matrix stability and physical projection")
    axes[1, 1].set_ylabel("Condition number")
    axes[1, 1].set_xticks(x, labels)
    axes[1, 1].set_ylim(0.0, max(condition_numbers) * 1.35)
    axes[1, 1].grid(axis="y", alpha=0.25)
    projection_axis = axes[1, 1].twinx()
    projection_axis.plot(
        x + width / 2,
        projection_rates,
        color="#D97706",
        marker="o",
        linewidth=2,
        label="Projection rate",
    )
    projection_axis.set_ylabel("Projected corrected values (%)")
    projection_axis.spines["top"].set_visible(False)
    handles_left, labels_left = axes[1, 1].get_legend_handles_labels()
    handles_right, labels_right = projection_axis.get_legend_handles_labels()
    axes[1, 1].legend(
        handles_left + handles_right,
        labels_left + labels_right,
        frameon=False,
        loc="upper right",
    )

    fig.savefig(OUTPUT_PNG, dpi=180, facecolor="white")
    fig.savefig(OUTPUT_SVG, facecolor="white")
    plt.close(fig)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    rows = []
    for case in CASE_ORDER:
        result = payload["comparison"][case]
        rows.append(
            "| {label} | {raw_acc:.3f} | {fixed_acc:.3f} | {acc_delta:+.3f} | "
            "{raw_f1:.3f} | {fixed_f1:.3f} | {f1_delta:+.3f} |".format(
                label=CASE_LABELS[case].replace("\n", " "),
                raw_acc=result["raw_accuracy"],
                fixed_acc=result["mitigated_accuracy"],
                acc_delta=result["accuracy_delta"],
                raw_f1=result["raw_macro_f1"],
                fixed_f1=result["mitigated_macro_f1"],
                f1_delta=result["macro_f1_delta"],
            )
        )

    metadata = payload["hardware_models"]["mitigated"]
    matrix_lines = []
    for key, label in (
        ("rigetti_ankaa3", "Rigetti Ankaa-3"),
        ("ionq_forte", "IonQ Forte"),
        ("xanadu_x8", "Xanadu X8"),
        ("ibm_fez", "IBM Fez"),
    ):
        if key == "ibm_fez":
            response = metadata[key]["measurement_error_mitigation"]
        else:
            response = metadata[key]["measurement_response"]
        matrix_lines.append(
            f"- {label}: max condition number `{response['max_condition_number']:.3f}`, "
            f"simplex projection `{100.0 * response['projection_rate']:.2f}%`."
        )

    report = "\n".join(
        [
            "# Korekcja macierzy bledow odczytu: SCAR-QNN na symulowanych QPU",
            "",
            "## Wyniki sparowane",
            "",
            "Kazdy wariant surowy i skorygowany ma ten sam seed, szum bramek, "
            "liczbe strzalow i hiperparametry. Roznica dotyczy regularizowanej "
            "inwersji macierzy przypisania oraz projekcji na simpleks.",
            "",
            "| Przypadek | Raw acc. | Corrected acc. | Delta | Raw F1 | Corrected F1 | Delta F1 |",
            "|---|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Zastosowane macierze",
            "",
            *matrix_lines,
            "",
            "- Rigetti i IonQ: symetryczna macierz 2x2 z agregatowej fidelity odczytu.",
            "- IBM: osobna asymetryczna macierz 2x2 dla kazdego aktywnego kubitu FakeFez.",
            "- Xanadu: macierz coincidence/no-coincidence wyprowadzona z dolnej granicy "
            "sprawnosci PNR i modelu nadmiarowych fotonow; nie jest to pelna macierz Focka.",
            "- Inwersja: Tikhonov lambda=1e-6; wartosci spoza simpleksu sa obcinane i normalizowane.",
            "",
            "## Protokoly",
            "",
            "- Rigetti, IonQ, Xanadu i IBM tuned: 64 epoki, 1024 strzaly treningowe, "
            "4096 strzalow koncowych, SPSA a=0.10, c=0.08, head lr=0.08.",
            "- IBM reproduction: 12 epok, 256 strzalow, SPSA a=0.12, c=0.15, head lr=0.04.",
            "- Wine split i PCA: seed 42, 13->4 cechy, 43 parametry modelu.",
            "",
            "## Ograniczenia",
            "",
            "Macierze uzyte do symulacji odczytu sa rownoczesnie macierzami kalibracyjnymi, "
            "wiec nie modelujemy niepewnosci estymacji macierzy ani dryfu pomiedzy kalibracja "
            "a uczeniem. Wyniki sa pojedynczym przebiegiem i nie stanowia dowodu przewagi kwantowej.",
            "",
            "## Pliki",
            "",
            "- Wyniki: `scar_qpu_error_matrix_mitigation_results.json`",
            "- Historia: `scar_qpu_error_matrix_mitigation_history.csv`",
            "- Wykres: `scar_qpu_error_matrix_mitigation_comparison.png`",
        ]
    )
    path.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    seed = 42
    x, y = load_wine()
    split = prepare_split(x, y, seed)
    evaluators = make_evaluators(seed)
    results, history = train_all(split, evaluators, seed)
    mlp, _ = classical_result(split, seed)
    comparison = build_comparison(results)
    hardware = hardware_metadata(evaluators)

    payload = {
        "execution_status": "completed_paired_assignment_matrix_mitigation",
        "not_physical_qpu_execution": True,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dataset": {
            "name": "UCI Wine",
            "samples": int(len(x)),
            "features": int(x.shape[1]),
            "classes": int(len(np.unique(y))),
            "split_seed": seed,
            "train_samples": int(len(split.x_train)),
            "validation_samples": int(len(split.x_val)),
            "test_samples": int(len(split.x_test)),
            "pca_explained": split.pca_explained,
        },
        "method": {
            "name": "assignment-matrix measurement-error mitigation",
            "paired_design": True,
            "measurement_sampling": "binomial samples after the assignment channel",
            "inverse": "Tikhonov-regularized inverse",
            "regularization": 1e-6,
            "physicality": "clip and renormalize corrected probabilities",
            "calibration_shot_uncertainty": "not modeled",
        },
        "protocols": PROTOCOLS,
        "results": results,
        "comparison": comparison,
        "classical_reference": mlp,
        "hardware_models": hardware,
        "limitations": [
            "The assignment matrices are exact within each simulator and have no calibration-shot uncertainty.",
            "Public aggregate readout data replace live per-qubit matrices for Rigetti and IonQ.",
            "The Xanadu 2x2 coincidence response is not a full PNR Fock-space response matrix.",
            "FakeFez is a frozen calibration snapshot, not the calibration from the real 2026-07-20 jobs.",
            "One seed and one data split are reported.",
        ],
    }
    write_json(OUTPUT_JSON, payload)
    write_history(OUTPUT_HISTORY, history)
    plot_results(payload, history)
    write_report(OUTPUT_REPORT, payload)

    print(f"\nWrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_HISTORY}")
    for case in CASE_ORDER:
        row = comparison[case]
        print(
            f"{case}: raw={row['raw_accuracy']:.3f}, "
            f"corrected={row['mitigated_accuracy']:.3f}, "
            f"delta={row['accuracy_delta']:+.3f}"
        )


if __name__ == "__main__":
    main()
