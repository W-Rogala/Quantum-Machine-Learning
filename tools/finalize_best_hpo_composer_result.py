from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

import ansatz_hardware_dataset_benchmark as benchmark  # noqa: E402
import run_best_hpo_ibm_qpu as qpu_runner  # noqa: E402


DEFAULT_COUNTS = ANALYSIS / "best_hpo_tree_tensor_ibm_composer_counts.json"
DEFAULT_METADATA = ANALYSIS / "best_hpo_tree_tensor_ibm_composer_metadata.json"
DEFAULT_MODEL = ANALYSIS / "best_hpo_tree_tensor_ibm_local_model.npz"
DEFAULT_OUTPUT = ANALYSIS / "best_hpo_tree_tensor_ibm_qpu_result.json"
DEFAULT_SAMPLES = ANALYSIS / "best_hpo_tree_tensor_ibm_qpu_samples.csv"
DEFAULT_REPORT = ANALYSIS / "best_hpo_tree_tensor_ibm_qpu_report.md"


def normalize_counts(payload: Any) -> tuple[dict[str, int], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if isinstance(payload, dict) and "counts" in payload:
        metadata = {key: value for key, value in payload.items() if key != "counts"}
        payload = payload["counts"]
    if not isinstance(payload, dict):
        raise ValueError("Counts file must contain a JSON object or an object with 'counts'.")
    counts: dict[str, int] = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key).replace(" ", "")
        if not key or any(bit not in "01" for bit in key):
            raise ValueError(f"Invalid count key: {raw_key!r}")
        counts[key] = counts.get(key, 0) + int(raw_value)
    if not counts or sum(counts.values()) <= 0:
        raise ValueError("Counts are empty.")
    return counts, metadata


def features_from_counts(
    counts: dict[str, int],
    samples: int,
    qubits: int,
) -> np.ndarray:
    required_bits = samples * qubits
    if any(len(key) != required_bits for key in counts):
        lengths = sorted({len(key) for key in counts})
        raise ValueError(f"Expected {required_bits}-bit keys, received lengths {lengths}.")
    shots = float(sum(counts.values()))
    features = np.zeros((samples, qubits), dtype=float)
    for bitstring, count in counts.items():
        for sample in range(samples):
            for qubit in range(qubits):
                classical_index = sample * qubits + qubit
                bit = int(bitstring[-1 - classical_index])
                features[sample, qubit] += count * (1.0 - 2.0 * bit)
    return np.clip(features / shots, -1.0, 1.0)


def write_samples(
    path: Path,
    y: np.ndarray,
    features: np.ndarray,
    probabilities: np.ndarray,
    predicted: np.ndarray,
) -> None:
    rows: list[dict[str, Any]] = []
    for index in range(len(y)):
        row: dict[str, Any] = {
            "sample": index,
            "true_label": int(y[index]),
            "predicted_label": int(predicted[index]),
            "correct": int(predicted[index] == y[index]),
        }
        for qubit in range(features.shape[1]):
            row[f"z_q{qubit}"] = float(features[index, qubit])
        for klass in range(probabilities.shape[1]):
            row[f"probability_class_{klass}"] = float(probabilities[index, klass])
        rows.append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize an IBM Composer QPU result.")
    parser.add_argument("--counts", type=Path, default=DEFAULT_COUNTS)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--samples-output", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--backend", default=None)
    parser.add_argument("--job-id", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prepared = json.loads(args.metadata.read_text(encoding="utf-8"))
    raw_counts = json.loads(args.counts.read_text(encoding="utf-8"))
    counts, result_metadata = normalize_counts(raw_counts)
    y = np.asarray(prepared["dataset"]["test_labels"], dtype=int)
    features = features_from_counts(counts, len(y), benchmark.N_QUBITS)
    model = np.load(args.model)
    weights = np.asarray(model["weights"], dtype=float)
    bias = np.asarray(model["bias"], dtype=float)
    metrics, probabilities, predicted = qpu_runner.evaluate(features, y, weights, bias)
    backend = args.backend or result_metadata.get("backend") or "unknown_ibm_qpu"
    job_id = args.job_id or result_metadata.get("job_id") or "unknown"
    shots = int(sum(counts.values()))
    payload = {
        "execution_status": "completed_on_ibm_qpu_via_composer",
        "selected_case": prepared["selected_case"],
        "selected_hyperparameters": prepared["selected_hyperparameters"],
        "dataset": prepared["dataset"],
        "local_reproduction": prepared["local_reproduction"],
        "execution_protocol": prepared["composer_protocol"],
        "qpu_result": {
            "job_id": job_id,
            "backend": backend,
            "shots": shots,
            "features": features,
            "metrics": metrics,
            "composer_metadata": result_metadata,
        },
        "comparison": {
            "qpu_minus_local_balanced_accuracy": float(metrics["balanced_accuracy"])
            - float(prepared["local_reproduction"]["test_balanced_accuracy_profile_shots"]),
            "qpu_minus_local_accuracy": float(metrics["accuracy"])
            - float(prepared["local_reproduction"]["test_accuracy_profile_shots"]),
        },
        "artifacts": {
            "counts": str(args.counts),
            "qasm": prepared["qasm_file"],
            "qasm_sha256": prepared["qasm_sha256"],
            "model": str(args.model),
        },
    }
    args.output.write_text(
        json.dumps(qpu_runner.json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_samples(args.samples_output, y, features, probabilities, predicted)
    lines = [
        "# Najlepszy model HPO na IBM Quantum",
        "",
        "Status: `completed_on_ibm_qpu_via_composer`.",
        "",
        "## Wykonanie",
        "",
        f"- Backend: `{backend}`.",
        f"- Job ID: `{job_id}`.",
        f"- Shots: {shots}.",
        "- Model: Wine + Tree tensor, 4 kubity, hiperparametry HPO `regularized`.",
        "- 15 probek wykonano sekwencyjnie w jednym obwodzie z resetem miedzy probkami.",
        "",
        "## Wynik",
        "",
        f"- Accuracy: {float(metrics['accuracy']):.3f}.",
        f"- Balanced accuracy: {float(metrics['balanced_accuracy']):.3f}.",
        f"- Macro F1: {float(metrics['macro_f1']):.3f}.",
        f"- Loss: {float(metrics['loss']):.3f}.",
        f"- Confusion matrix: `{metrics['confusion']}`.",
        f"- Delta QPU - lokalna BA: {float(payload['comparison']['qpu_minus_local_balanced_accuracy']):+.3f}.",
        "",
        "## Ograniczenia",
        "",
        "- Parametry wytrenowano lokalnie; QPU wykonalo koncowa inferencje.",
        "- Reset w srodku obwodu pozwala wykonac wszystkie probki w jednym zadaniu, ale wnosi dodatkowy blad.",
        "- Zbior testowy ma 15 probek; pojedynczy blad zmienia accuracy o 0.067.",
    ]
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Completed Composer result from {shots} shots on {backend}")
    print(f"Balanced accuracy: {metrics['balanced_accuracy']:.3f}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
