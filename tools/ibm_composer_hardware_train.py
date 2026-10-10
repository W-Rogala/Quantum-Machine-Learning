from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

import ansatz_hardware_dataset_benchmark as benchmark  # noqa: E402
import run_best_hpo_ibm_qpu as qpu_runner  # noqa: E402


DEFAULT_OUTPUT_DIR = ANALYSIS / "ibm_hardware_training"
STATE_NAME = "state.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(qpu_runner.json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_state(output_dir: Path) -> dict[str, Any]:
    path = output_dir / STATE_NAME
    if not path.exists():
        raise FileNotFoundError(f"Training state does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(output_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(output_dir / STATE_NAME, state)


def recreate_dataset(seed: int, samples_per_class: int) -> benchmark.PreparedDataset:
    raw = benchmark.load_wine()
    sampled = benchmark.balanced_subsample(raw, samples_per_class, seed)
    return benchmark.prepare_dataset(sampled, seed)


def qasm_angle(value: float) -> str:
    return format(float(value), ".17g")


def append_tree_tensor_gate(lines: list[str], theta: np.ndarray) -> None:
    for qubit, argument in enumerate("abcd"):
        lines.append(f"  ry(x{qubit}) {argument};")
    cursor = 0
    for left, right in [(0, 1), (2, 3), (1, 3)]:
        left_arg = "abcd"[left]
        right_arg = "abcd"[right]
        lines.append(f"  ry({qasm_angle(theta[cursor])}) {left_arg};")
        lines.append(f"  ry({qasm_angle(theta[cursor + 1])}) {right_arg};")
        lines.append(f"  cx {left_arg},{right_arg};")
        lines.append(f"  ry({qasm_angle(theta[cursor + 2])}) {right_arg};")
        cursor += 3


def build_qasm(
    groups: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]],
    input_scale: float,
) -> tuple[str, list[dict[str, Any]]]:
    total_samples = sum(len(values) for _, values, _, _ in groups)
    classical_bits = total_samples * benchmark.N_QUBITS
    lines = [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        f"qreg q[{benchmark.N_QUBITS}];",
        f"creg c[{classical_bits}];",
        "",
    ]
    gate_names: dict[bytes, str] = {}
    gate_parameters: list[np.ndarray] = []
    for _, _, _, theta in groups:
        key = np.asarray(theta, dtype=np.float64).tobytes()
        if key not in gate_names:
            gate_names[key] = f"tree{len(gate_names)}"
            gate_parameters.append(np.asarray(theta, dtype=float))
    for gate_index, theta in enumerate(gate_parameters):
        lines.append(f"gate tree{gate_index}(x0,x1,x2,x3) a,b,c,d {{")
        append_tree_tensor_gate(lines, theta)
        lines.append("}")
        lines.append("")

    group_metadata: list[dict[str, Any]] = []
    sample_index = 0
    for name, values, labels, theta in groups:
        start = sample_index
        gate_name = gate_names[np.asarray(theta, dtype=np.float64).tobytes()]
        for group_index, sample_values in enumerate(values):
            angles = ",".join(
                qasm_angle(input_scale * value)
                for value in sample_values[: benchmark.N_QUBITS]
            )
            lines.append(f"{gate_name}({angles}) q[0],q[1],q[2],q[3];")
            offset = sample_index * benchmark.N_QUBITS
            for qubit in range(benchmark.N_QUBITS):
                lines.append(f"measure q[{qubit}] -> c[{offset + qubit}];")
            sample_index += 1
            if sample_index < total_samples:
                lines.append("reset q;")
        group_metadata.append(
            {
                "name": name,
                "start_sample": start,
                "samples": int(len(values)),
                "labels": labels.tolist(),
                "theta_sha256": hashlib.sha256(
                    np.asarray(theta, dtype=np.float64).tobytes()
                ).hexdigest(),
            }
        )
    return "\n".join(lines), group_metadata


def adam_step(
    values: np.ndarray,
    gradient: np.ndarray,
    state: dict[str, Any],
    learning_rate: float,
    scale: float = 1.0,
) -> tuple[np.ndarray, dict[str, Any]]:
    step_number = int(state["step_number"]) + 1
    m = 0.9 * np.asarray(state["m"], dtype=float) + 0.1 * gradient
    v = 0.999 * np.asarray(state["v"], dtype=float) + 0.001 * gradient * gradient
    corrected_m = m / (1.0 - 0.9**step_number)
    corrected_v = v / (1.0 - 0.999**step_number)
    updated = values - scale * learning_rate * corrected_m / (
        np.sqrt(corrected_v) + 1e-8
    )
    return updated, {
        "m": m.tolist(),
        "v": v.tolist(),
        "step_number": step_number,
    }


def normalize_counts(payload: Any) -> tuple[dict[str, int], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if isinstance(payload, dict) and "counts" in payload:
        metadata = {key: value for key, value in payload.items() if key != "counts"}
        payload = payload["counts"]
    if not isinstance(payload, dict):
        raise ValueError("Counts must be a JSON object or an object with 'counts'.")
    counts: dict[str, int] = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key).replace(" ", "")
        if not key or any(bit not in "01" for bit in key):
            raise ValueError(f"Invalid count key: {raw_key!r}")
        counts[key] = counts.get(key, 0) + int(raw_value)
    if not counts or sum(counts.values()) <= 0:
        raise ValueError("Counts are empty.")
    return counts, metadata


def features_from_counts(counts: dict[str, int], samples: int) -> np.ndarray:
    required_bits = samples * benchmark.N_QUBITS
    lengths = sorted({len(key) for key in counts})
    if lengths != [required_bits]:
        raise ValueError(f"Expected {required_bits}-bit keys, received {lengths}.")
    shots = float(sum(counts.values()))
    features = np.zeros((samples, benchmark.N_QUBITS), dtype=float)
    for bitstring, count in counts.items():
        for sample in range(samples):
            for qubit in range(benchmark.N_QUBITS):
                classical_index = sample * benchmark.N_QUBITS + qubit
                bit = int(bitstring[-1 - classical_index])
                features[sample, qubit] += count * (1.0 - 2.0 * bit)
    return np.clip(features / shots, -1.0, 1.0)


def expand_counts(counts: dict[str, int]) -> list[str]:
    expanded: list[str] = []
    for bitstring, count in sorted(counts.items()):
        expanded.extend([bitstring] * int(count))
    return expanded


def combine_chunk_counts(chunk_counts: list[dict[str, int]]) -> dict[str, int]:
    expanded = [expand_counts(counts) for counts in chunk_counts]
    shot_counts = {len(items) for items in expanded}
    if len(shot_counts) != 1:
        raise ValueError(f"Chunk shot counts differ: {sorted(shot_counts)}")
    shots = shot_counts.pop()
    combined: dict[str, int] = {}
    for shot in range(shots):
        # OpenQASM count strings place the highest classical index on the left.
        bitstring = "".join(items[shot] for items in reversed(expanded))
        combined[bitstring] = combined.get(bitstring, 0) + 1
    return combined


def split_features(
    features: np.ndarray, groups: list[dict[str, Any]]
) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for group in groups:
        start = int(group["start_sample"])
        stop = start + int(group["samples"])
        result[str(group["name"])] = features[start:stop]
    return result


def write_pending_job(
    output_dir: Path,
    state: dict[str, Any],
    kind: str,
    index: int,
    shots: int,
    groups: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]],
    extra: dict[str, Any],
) -> None:
    input_scale = float(state["hyperparameters"]["input_scale"])
    qasm, group_metadata = build_qasm(groups, input_scale)
    stem = f"{kind}_{index:02d}"
    qasm_path = output_dir / f"{stem}.qasm"
    metadata_path = output_dir / f"{stem}_metadata.json"
    counts_path = output_dir / f"{stem}_counts.json"
    qasm_path.write_text(qasm, encoding="utf-8")
    metadata = {
        "kind": kind,
        "index": index,
        "shots": shots,
        "quantum_qubits": benchmark.N_QUBITS,
        "classical_bits": sum(int(item["samples"]) for item in group_metadata)
        * benchmark.N_QUBITS,
        "total_samples": sum(int(item["samples"]) for item in group_metadata),
        "groups": group_metadata,
        "measurement_mapping": "c[4*sample+qubit]",
        "qasm_sha256": hashlib.sha256(qasm.encode("utf-8")).hexdigest(),
        **extra,
    }
    write_json(metadata_path, metadata)
    state["status"] = (
        "awaiting_training_result" if kind == "training_epoch" else "awaiting_final_result"
    )
    state["pending_job"] = {
        "kind": kind,
        "index": index,
        "shots": shots,
        "qasm": str(qasm_path),
        "metadata": str(metadata_path),
        "counts": str(counts_path),
        **extra,
    }
    save_state(output_dir, state)


def write_chunk_jobs(
    output_dir: Path,
    state: dict[str, Any],
    kind: str,
    index: int,
    shots: int,
    groups: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]],
) -> None:
    input_scale = float(state["hyperparameters"]["input_scale"])
    chunks: list[dict[str, Any]] = []
    for name, values, labels, theta in groups:
        qasm, group_metadata = build_qasm(
            [(name, values, labels, theta)], input_scale
        )
        stem = f"{kind}_{index:02d}_{name}"
        qasm_path = output_dir / f"{stem}.qasm"
        metadata_path = output_dir / f"{stem}_metadata.json"
        counts_path = output_dir / f"{stem}_counts.json"
        qasm_path.write_text(qasm, encoding="utf-8")
        metadata = {
            "kind": kind,
            "index": index,
            "chunk": name,
            "shots": shots,
            "quantum_qubits": benchmark.N_QUBITS,
            "classical_bits": int(len(values) * benchmark.N_QUBITS),
            "total_samples": int(len(values)),
            "groups": group_metadata,
            "measurement_mapping": "c[4*sample+qubit]",
            "qasm_sha256": hashlib.sha256(qasm.encode("utf-8")).hexdigest(),
        }
        write_json(metadata_path, metadata)
        chunks.append(
            {
                "name": name,
                "shots": shots,
                "samples": int(len(values)),
                "qasm": str(qasm_path),
                "metadata": str(metadata_path),
                "counts": str(counts_path),
            }
        )
    state["pending_job"]["chunks"] = chunks
    state["status"] = (
        "awaiting_training_chunk_results"
        if kind == "training_epoch"
        else "awaiting_final_chunk_results"
    )
    save_state(output_dir, state)


def prepare_training_job(
    output_dir: Path,
    state: dict[str, Any],
    dataset: benchmark.PreparedDataset,
) -> None:
    epoch = int(state["next_epoch"])
    rng = np.random.default_rng()
    rng.bit_generator.state = state["rng_state"]
    perturbation = rng.choice(
        [-1.0, 1.0], size=len(state["theta"])
    ).astype(float)
    state["rng_state"] = rng.bit_generator.state
    theta = np.asarray(state["theta"], dtype=float)
    c_k = float(state["hyperparameters"]["spsa_perturbation"]) / (
        epoch + 1.0
    ) ** 0.101
    groups = [
        ("current_train", dataset.x_train, dataset.y_train, theta),
        ("current_val", dataset.x_val, dataset.y_val, theta),
        (
            "plus_train",
            dataset.x_train,
            dataset.y_train,
            theta + c_k * perturbation,
        ),
        (
            "minus_train",
            dataset.x_train,
            dataset.y_train,
            theta - c_k * perturbation,
        ),
    ]
    write_pending_job(
        output_dir,
        state,
        "training_epoch",
        epoch,
        int(state["train_shots"]),
        groups,
        {"c_k": c_k, "perturbation": perturbation.tolist()},
    )
    write_chunk_jobs(
        output_dir,
        state,
        "training_epoch",
        epoch,
        int(state["train_shots"]),
        groups,
    )


def prepare_final_job(
    output_dir: Path,
    state: dict[str, Any],
    dataset: benchmark.PreparedDataset,
) -> None:
    if state.get("best_parameters") is None:
        raise RuntimeError("No hardware-observed checkpoint is available.")
    best = state["best_parameters"]
    theta = np.asarray(best["theta"], dtype=float)
    groups = [
        ("train", dataset.x_train, dataset.y_train, theta),
        ("val", dataset.x_val, dataset.y_val, theta),
        ("test", dataset.x_test, dataset.y_test, theta),
    ]
    state["evaluation_parameters"] = best
    write_pending_job(
        output_dir,
        state,
        "final_evaluation",
        int(state["epochs"]),
        int(state["evaluation_shots"]),
        groups,
        {"selected_hardware_epoch": int(state["best_epoch"])},
    )
    write_chunk_jobs(
        output_dir,
        state,
        "final_evaluation",
        int(state["epochs"]),
        int(state["evaluation_shots"]),
        groups,
    )


def append_history(output_dir: Path, history: list[dict[str, Any]]) -> None:
    if not history:
        return
    path = output_dir / "history.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)


def advance_training(
    output_dir: Path,
    state: dict[str, Any],
    dataset: benchmark.PreparedDataset,
    counts: dict[str, int],
    result_metadata: dict[str, Any],
    job_id: str,
    backend: str,
) -> None:
    pending = state["pending_job"]
    metadata = json.loads(Path(pending["metadata"]).read_text(encoding="utf-8"))
    features = features_from_counts(counts, int(metadata["total_samples"]))
    split = split_features(features, metadata["groups"])
    theta = np.asarray(state["theta"], dtype=float)
    weights = np.asarray(state["weights"], dtype=float)
    bias = np.asarray(state["bias"], dtype=float)
    hp = state["hyperparameters"]

    train_features = split["current_train"]
    train_probabilities = benchmark.predictions(train_features, weights, bias)
    residual = train_probabilities.copy()
    residual[np.arange(len(dataset.y_train)), dataset.y_train] -= 1.0
    residual /= len(dataset.y_train)
    weight_gradient = train_features.T @ residual + float(hp["weight_decay"]) * weights
    bias_gradient = residual.sum(axis=0)
    weights, weight_adam = adam_step(
        weights,
        weight_gradient,
        state["adam"]["weights"],
        float(hp["head_learning_rate"]),
    )
    bias, bias_adam = adam_step(
        bias,
        bias_gradient,
        state["adam"]["bias"],
        float(hp["head_learning_rate"]),
    )

    plus_loss = benchmark.cross_entropy(
        benchmark.predictions(split["plus_train"], weights, bias), dataset.y_train
    )
    minus_loss = benchmark.cross_entropy(
        benchmark.predictions(split["minus_train"], weights, bias), dataset.y_train
    )
    perturbation = np.asarray(pending["perturbation"], dtype=float)
    c_k = float(pending["c_k"])
    theta_gradient = (plus_loss - minus_loss) * perturbation / (2.0 * c_k)
    theta_gradient += float(hp["weight_decay"]) * theta
    epoch = int(pending["index"])
    schedule = 1.0 / (epoch + 1.0) ** 0.20
    updated_theta, theta_adam = adam_step(
        theta,
        theta_gradient,
        state["adam"]["theta"],
        float(hp["quantum_learning_rate"]),
        schedule,
    )

    train_metrics, _, _ = qpu_runner.evaluate(
        train_features, dataset.y_train, weights, bias
    )
    val_metrics, _, _ = qpu_runner.evaluate(
        split["current_val"], dataset.y_val, weights, bias
    )
    train_loss = benchmark.cross_entropy(
        benchmark.predictions(train_features, weights, bias), dataset.y_train
    )
    val_loss = benchmark.cross_entropy(
        benchmark.predictions(split["current_val"], weights, bias), dataset.y_val
    )
    entry = {
        "epoch": epoch,
        "backend": backend,
        "job_id": job_id,
        "shots": int(sum(counts.values())),
        "train_loss": train_loss,
        "val_loss": val_loss,
        "train_accuracy": train_metrics["accuracy"],
        "train_balanced_accuracy": train_metrics["balanced_accuracy"],
        "val_accuracy": val_metrics["accuracy"],
        "val_balanced_accuracy": val_metrics["balanced_accuracy"],
        "plus_loss": plus_loss,
        "minus_loss": minus_loss,
        "theta_gradient_norm": float(np.linalg.norm(theta_gradient)),
        "completed_at": now_iso(),
    }
    state["history"].append(entry)
    append_history(output_dir, state["history"])

    if state["best_val_loss"] is None or val_loss < float(state["best_val_loss"]):
        state["best_val_loss"] = val_loss
        state["best_epoch"] = epoch
        state["best_parameters"] = {
            "theta": theta.tolist(),
            "weights": weights.tolist(),
            "bias": bias.tolist(),
        }

    state["theta"] = updated_theta.tolist()
    state["weights"] = weights.tolist()
    state["bias"] = bias.tolist()
    state["adam"] = {
        "theta": theta_adam,
        "weights": weight_adam,
        "bias": bias_adam,
    }
    state["completed_jobs"].append(
        {
            "kind": "training_epoch",
            "index": epoch,
            "backend": backend,
            "job_id": job_id,
            "shots": int(sum(counts.values())),
            "counts": [chunk["counts"] for chunk in pending.get("chunks", [])]
            or pending["counts"],
            "result_metadata": result_metadata,
            "completed_at": now_iso(),
        }
    )
    state["next_epoch"] = epoch + 1
    state["pending_job"] = None
    if int(state["next_epoch"]) < int(state["epochs"]):
        prepare_training_job(output_dir, state, dataset)
    else:
        prepare_final_job(output_dir, state, dataset)


def write_final_report(output_dir: Path, result: dict[str, Any]) -> None:
    test = result["metrics"]["test"]
    lines = [
        "# Sprzetowe uczenie Wine + Tree tensor na IBM Quantum",
        "",
        "Status: `completed_hardware_training`.",
        "",
        "## Protokol",
        "",
        f"- Epoki SPSA na QPU: {result['epochs']}.",
        f"- Strzaly na epoke: {result['train_shots']}.",
        f"- Strzaly oceny koncowej: {result['evaluation_shots']}.",
        f"- Wybrana epoka sprzetowa: {result['selected_hardware_epoch']}.",
        "- Kazda aktualizacja theta wykorzystala pomiary QPU dla theta+c*delta i theta-c*delta.",
        "- Glowa klasyfikacyjna Adam byla aktualizowana z cech zmierzonych na QPU.",
        "",
        "## Wynik testowy",
        "",
        f"- Backend: `{result['backend']}`.",
        f"- Job ID: `{result['job_id']}`.",
        f"- Accuracy: {float(test['accuracy']):.3f}.",
        f"- Balanced accuracy: {float(test['balanced_accuracy']):.3f}.",
        f"- Macro F1: {float(test['macro_f1']):.3f}.",
        f"- Loss: {float(test['loss']):.3f}.",
        f"- Confusion matrix: `{test['confusion']}`.",
        "",
        "## Uwaga",
        "",
        "To jest adaptacyjne uczenie sprzetowe, a nie tylko inferencja parametrow wytrenowanych lokalnie.",
    ]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def advance_final(
    output_dir: Path,
    state: dict[str, Any],
    dataset: benchmark.PreparedDataset,
    counts: dict[str, int],
    result_metadata: dict[str, Any],
    job_id: str,
    backend: str,
) -> None:
    pending = state["pending_job"]
    metadata = json.loads(Path(pending["metadata"]).read_text(encoding="utf-8"))
    features = features_from_counts(counts, int(metadata["total_samples"]))
    split = split_features(features, metadata["groups"])
    selected = state["evaluation_parameters"]
    weights = np.asarray(selected["weights"], dtype=float)
    bias = np.asarray(selected["bias"], dtype=float)
    metrics: dict[str, Any] = {}
    probabilities: dict[str, np.ndarray] = {}
    predictions: dict[str, np.ndarray] = {}
    for name, labels in [
        ("train", dataset.y_train),
        ("val", dataset.y_val),
        ("test", dataset.y_test),
    ]:
        metric, probability, predicted = qpu_runner.evaluate(
            split[name], labels, weights, bias
        )
        metrics[name] = metric
        probabilities[name] = probability
        predictions[name] = predicted

    model_path = output_dir / "hardware_trained_model.npz"
    np.savez(
        model_path,
        theta=np.asarray(selected["theta"], dtype=float),
        weights=weights,
        bias=bias,
        input_scale=np.asarray(float(state["hyperparameters"]["input_scale"])),
        best_epoch=np.asarray(int(state["best_epoch"])),
        best_val_loss=np.asarray(float(state["best_val_loss"])),
    )
    qpu_runner.write_samples(
        output_dir / "test_samples.csv",
        dataset,
        split["test"],
        probabilities["test"],
        predictions["test"],
    )
    state["completed_jobs"].append(
        {
            "kind": "final_evaluation",
            "backend": backend,
            "job_id": job_id,
            "shots": int(sum(counts.values())),
            "counts": [chunk["counts"] for chunk in pending.get("chunks", [])]
            or pending["counts"],
            "completed_at": now_iso(),
        }
    )
    result = {
        "execution_status": "completed_hardware_training",
        "dataset": "wine",
        "ansatz": "tree_tensor",
        "backend": backend,
        "job_id": job_id,
        "epochs": int(state["epochs"]),
        "train_shots": int(state["train_shots"]),
        "evaluation_shots": int(sum(counts.values())),
        "selected_hardware_epoch": int(state["best_epoch"]),
        "selected_hyperparameters": state["hyperparameters"],
        "metrics": metrics,
        "features": {name: value.tolist() for name, value in split.items()},
        "history": state["history"],
        "jobs": state["completed_jobs"],
        "final_result_metadata": result_metadata,
        "model": str(model_path),
    }
    write_json(output_dir / "result.json", result)
    write_final_report(output_dir, result)
    state["status"] = "completed_hardware_training"
    state["pending_job"] = None
    state["final_result"] = str(output_dir / "result.json")
    save_state(output_dir, state)


def command_init(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.resolve()
    state_path = output_dir / STATE_NAME
    if state_path.exists() and not args.force:
        raise FileExistsError(
            f"Training state already exists: {state_path}. Use --force to replace it."
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    selected, hyperparameters = qpu_runner.select_best_ibm_case(
        qpu_runner.DEFAULT_RESULTS, qpu_runner.DEFAULT_BEST
    )
    dataset = recreate_dataset(args.seed, args.samples_per_class)
    spec = benchmark.ANSATZE["tree_tensor"]
    run_seed = benchmark.stable_seed(args.seed, dataset.name, spec.key)
    rng = np.random.default_rng(run_seed)
    theta = rng.normal(
        0.0, float(hyperparameters["initialization_scale"]), size=spec.parameters
    )
    weights = rng.normal(
        0.0, 0.12, size=(benchmark.N_QUBITS, len(dataset.class_names))
    )
    bias = np.zeros(len(dataset.class_names), dtype=float)
    state: dict[str, Any] = {
        "version": 1,
        "created_at": now_iso(),
        "status": "initializing",
        "dataset": "wine",
        "ansatz": "tree_tensor",
        "selected_case": selected,
        "hyperparameters": hyperparameters,
        "seed": args.seed,
        "samples_per_class": args.samples_per_class,
        "run_seed": run_seed,
        "epochs": args.epochs,
        "train_shots": args.train_shots,
        "evaluation_shots": args.evaluation_shots,
        "next_epoch": 0,
        "theta": theta.tolist(),
        "weights": weights.tolist(),
        "bias": bias.tolist(),
        "rng_state": rng.bit_generator.state,
        "adam": {
            "theta": {
                "m": np.zeros_like(theta).tolist(),
                "v": np.zeros_like(theta).tolist(),
                "step_number": 0,
            },
            "weights": {
                "m": np.zeros_like(weights).tolist(),
                "v": np.zeros_like(weights).tolist(),
                "step_number": 0,
            },
            "bias": {
                "m": np.zeros_like(bias).tolist(),
                "v": np.zeros_like(bias).tolist(),
                "step_number": 0,
            },
        },
        "best_val_loss": None,
        "best_epoch": None,
        "best_parameters": None,
        "history": [],
        "completed_jobs": [],
        "pending_job": None,
    }
    prepare_training_job(output_dir, state, dataset)
    pending = state["pending_job"]
    print(f"Initialized {args.epochs}-epoch hardware training")
    print(f"Pending QASM: {pending['qasm']}")
    print(f"Shots: {pending['shots']}")


def command_advance(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.resolve()
    state = load_state(output_dir)
    pending = state.get("pending_job")
    if pending is None:
        raise RuntimeError(f"State has no pending job (status={state['status']}).")
    if pending.get("chunks"):
        if args.counts:
            raise ValueError("--counts cannot be used for a chunked pending job.")
        chunk_counts: list[dict[str, int]] = []
        chunk_results: list[dict[str, Any]] = []
        backends: list[str] = []
        job_ids: list[str] = []
        for chunk in pending["chunks"]:
            counts_path = Path(chunk["counts"])
            if not counts_path.exists():
                raise FileNotFoundError(
                    f"Missing result for chunk {chunk['name']}: {counts_path}"
                )
            raw_counts = json.loads(counts_path.read_text(encoding="utf-8"))
            normalized, metadata = normalize_counts(raw_counts)
            expected_bits = int(chunk["samples"]) * benchmark.N_QUBITS
            lengths = sorted({len(key) for key in normalized})
            if lengths != [expected_bits]:
                raise ValueError(
                    f"Chunk {chunk['name']} expected {expected_bits}-bit keys, got {lengths}."
                )
            chunk_counts.append(normalized)
            chunk_backend = str(metadata.get("backend") or args.backend or "")
            chunk_job_id = str(metadata.get("job_id") or "")
            if chunk_backend:
                backends.append(chunk_backend)
            if chunk_job_id:
                job_ids.append(chunk_job_id)
            chunk_results.append(
                {
                    "name": chunk["name"],
                    "counts": str(counts_path),
                    "shots": int(sum(normalized.values())),
                    "metadata": metadata,
                }
            )
        counts = combine_chunk_counts(chunk_counts)
        result_metadata = {"chunks": chunk_results}
        backend = args.backend or ",".join(sorted(set(backends)))
        job_id = args.job_id or ",".join(job_ids)
    else:
        counts_path = args.counts.resolve() if args.counts else Path(pending["counts"])
        raw_counts = json.loads(counts_path.read_text(encoding="utf-8"))
        counts, result_metadata = normalize_counts(raw_counts)
        backend = args.backend or str(result_metadata.get("backend") or "")
        job_id = args.job_id or str(result_metadata.get("job_id") or "")
    if not backend or not job_id:
        raise ValueError("Backend and job ID must be provided in counts metadata or CLI.")
    dataset = recreate_dataset(int(state["seed"]), int(state["samples_per_class"]))
    if pending["kind"] == "training_epoch":
        advance_training(
            output_dir,
            state,
            dataset,
            counts,
            result_metadata,
            job_id,
            backend,
        )
    elif pending["kind"] == "final_evaluation":
        advance_final(
            output_dir,
            state,
            dataset,
            counts,
            result_metadata,
            job_id,
            backend,
        )
    else:
        raise RuntimeError(f"Unknown pending job kind: {pending['kind']}")
    updated = load_state(output_dir)
    print(f"Status: {updated['status']}")
    if updated.get("pending_job"):
        print(f"Next QASM: {updated['pending_job']['qasm']}")
        print(f"Shots: {updated['pending_job']['shots']}")
    else:
        print(f"Result: {updated.get('final_result')}")


def command_simulate(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.resolve()
    state = load_state(output_dir)
    pending = state.get("pending_job")
    if pending is None:
        raise RuntimeError("There is no pending QASM to simulate.")
    from qiskit import QuantumCircuit
    from qiskit.providers.basic_provider import BasicSimulator

    backend = BasicSimulator()
    targets = pending.get("chunks") or [pending]
    if args.counts_output and len(targets) != 1:
        raise ValueError("--counts-output is only valid for an unchunked job.")
    for target_index, target in enumerate(targets):
        circuit = QuantumCircuit.from_qasm_file(target["qasm"]).decompose(reps=10)
        job = backend.run(
            circuit,
            shots=int(target["shots"]),
            seed_simulator=args.seed + target_index,
        )
        counts = job.result().get_counts(circuit)
        output = args.counts_output or Path(target["counts"])
        write_json(
            output,
            {
                "backend": "BasicSimulator",
                "job_id": (
                    f"local-simulator-{pending['kind']}-{pending['index']}-"
                    f"{target.get('name', 'all')}"
                ),
                "shots": int(sum(counts.values())),
                "counts": counts,
            },
        )
        print(f"Simulated {target['qasm']}")
        print(f"Counts: {output}")


def command_inspect(args: argparse.Namespace) -> None:
    state = load_state(args.output_dir.resolve())
    summary = {
        "status": state["status"],
        "next_epoch": state["next_epoch"],
        "epochs": state["epochs"],
        "completed_jobs": len(state["completed_jobs"]),
        "best_epoch": state["best_epoch"],
        "best_val_loss": state["best_val_loss"],
        "pending_job": state.get("pending_job"),
        "final_result": state.get("final_result"),
    }
    print(json.dumps(qpu_runner.json_ready(summary), indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resumable SPSA/Adam training driven by IBM Composer QPU counts."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--epochs", type=int, default=30)
    init.add_argument("--train-shots", type=int, default=64)
    init.add_argument("--evaluation-shots", type=int, default=512)
    init.add_argument("--seed", type=int, default=42)
    init.add_argument("--samples-per-class", type=int, default=24)
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=command_init)

    advance = subparsers.add_parser("advance")
    advance.add_argument("--counts", type=Path)
    advance.add_argument("--job-id")
    advance.add_argument("--backend")
    advance.set_defaults(handler=command_advance)

    simulate = subparsers.add_parser("simulate")
    simulate.add_argument("--seed", type=int, default=12345)
    simulate.add_argument("--counts-output", type=Path)
    simulate.set_defaults(handler=command_simulate)

    inspect = subparsers.add_parser("inspect")
    inspect.set_defaults(handler=command_inspect)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
