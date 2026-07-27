from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

import ansatz_hardware_dataset_benchmark as benchmark  # noqa: E402
import run_best_hpo_ibm_qpu as qpu_runner  # noqa: E402


DEFAULT_QASM = ANALYSIS / "best_hpo_tree_tensor_ibm_composer.qasm"
DEFAULT_METADATA = ANALYSIS / "best_hpo_tree_tensor_ibm_composer_metadata.json"
DEFAULT_MODEL = ANALYSIS / "best_hpo_tree_tensor_ibm_local_model.npz"


def qasm_angle(value: float) -> str:
    return format(float(value), ".17g")


def build_qasm(
    x_test: np.ndarray,
    theta: np.ndarray,
    input_scale: float,
) -> str:
    samples = int(len(x_test))
    classical_bits = samples * benchmark.N_QUBITS
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{benchmark.N_QUBITS}];",
        f"creg c[{classical_bits}];",
        "",
    ]
    interactions = [(0, 1), (2, 3), (1, 3)]
    for sample_index, values in enumerate(x_test[:, : benchmark.N_QUBITS]):
        lines.append(f"// Test sample {sample_index}")
        for qubit, value in enumerate(values):
            lines.append(f"ry({qasm_angle(input_scale * value)}) q[{qubit}];")
        cursor = 0
        for left, right in interactions:
            lines.append(f"ry({qasm_angle(theta[cursor])}) q[{left}];")
            lines.append(f"ry({qasm_angle(theta[cursor + 1])}) q[{right}];")
            lines.append(f"cx q[{left}],q[{right}];")
            lines.append(f"ry({qasm_angle(theta[cursor + 2])}) q[{right}];")
            cursor += 3
        lines.append("barrier q;")
        offset = sample_index * benchmark.N_QUBITS
        for qubit in range(benchmark.N_QUBITS):
            lines.append(f"measure q[{qubit}] -> c[{offset + qubit}];")
        if sample_index + 1 < samples:
            for qubit in range(benchmark.N_QUBITS):
                lines.append(f"reset q[{qubit}];")
            lines.append("barrier q;")
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the best Wine tree-tensor trial for IBM Composer."
    )
    parser.add_argument("--shots", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--samples-per-class", type=int, default=24)
    parser.add_argument("--qasm-output", type=Path, default=DEFAULT_QASM)
    parser.add_argument("--metadata-output", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected, hyperparameters = qpu_runner.select_best_ibm_case(
        qpu_runner.DEFAULT_RESULTS,
        qpu_runner.DEFAULT_BEST,
    )
    dataset, local_result, theta, weights, bias = qpu_runner.recreate_model(
        selected,
        hyperparameters,
        args.seed,
        args.samples_per_class,
        args.shots,
        args.model_output,
    )
    qasm = build_qasm(
        dataset.x_test,
        theta,
        float(hyperparameters["input_scale"]),
    )
    args.qasm_output.parent.mkdir(parents=True, exist_ok=True)
    args.qasm_output.write_text(qasm, encoding="utf-8")

    ideal_features = benchmark.quantum_features(
        benchmark.ANSATZE["tree_tensor"],
        dataset.x_test,
        theta,
        float(hyperparameters["input_scale"]),
    )
    ideal_metrics, _, _ = qpu_runner.evaluate(
        ideal_features,
        dataset.y_test,
        weights,
        bias,
    )
    metadata = {
        "execution_status": "prepared_for_ibm_composer",
        "selected_case": selected,
        "selected_hyperparameters": hyperparameters,
        "dataset": {
            "name": "Wine",
            "class_names": list(dataset.class_names),
            "test_samples": int(len(dataset.y_test)),
            "test_labels": dataset.y_test.tolist(),
            "split_seed": args.seed,
        },
        "local_reproduction": local_result,
        "local_ideal_metrics": ideal_metrics,
        "composer_protocol": {
            "format": "OpenQASM 2.0",
            "quantum_qubits": benchmark.N_QUBITS,
            "classical_bits": int(len(dataset.y_test) * benchmark.N_QUBITS),
            "shots": args.shots,
            "samples_sequenced_in_one_circuit": int(len(dataset.y_test)),
            "reset_between_samples": True,
            "measurement_mapping": "c[4*sample+qubit]",
        },
        "qasm_file": str(args.qasm_output),
        "qasm_sha256": hashlib.sha256(qasm.encode("utf-8")).hexdigest(),
        "model_file": str(args.model_output),
    }
    args.metadata_output.write_text(
        json.dumps(qpu_runner.json_ready(metadata), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Prepared {args.qasm_output}")
    print(f"Test samples: {len(dataset.y_test)}")
    print(f"Classical bits: {len(dataset.y_test) * benchmark.N_QUBITS}")
    print(f"Local balanced accuracy: {local_result['test_balanced_accuracy_profile_shots']:.3f}")


if __name__ == "__main__":
    main()
