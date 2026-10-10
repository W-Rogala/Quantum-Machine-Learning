from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
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

from scar_physical_qpu_wine_benchmark import (  # noqa: E402
    classical_result,
    train_hardware_model,
)
from scar_measurement_mitigation import (  # noqa: E402
    MeasurementResponse,
    assignment_matrix,
)
from scar_wine_ibm_qpu import compile_for_backend  # noqa: E402
from scar_wine_qnn_benchmark import (  # noqa: E402
    N_QUBITS,
    SCAR_PARAMETERS,
    load_wine,
    prepare_split,
)


REAL_RESULT = ANALYSIS / "scar_wine_ibm_qpu_result.json"
REAL_HISTORY = ANALYSIS / "scar_wine_ibm_qpu_history.csv"
OUTPUT_JSON = ANALYSIS / "scar_wine_ibm_simulated_result.json"
OUTPUT_HISTORY = ANALYSIS / "scar_wine_ibm_simulated_history.csv"
OUTPUT_REPORT = ANALYSIS / "scar_wine_ibm_simulated_report.md"
OUTPUT_PNG = ANALYSIS / "scar_wine_ibm_simulated_comparison.png"
OUTPUT_SVG = ANALYSIS / "scar_wine_ibm_simulated_comparison.svg"


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    numeric = {
        "epoch",
        "train_loss",
        "train_accuracy",
        "validation_loss",
        "validation_accuracy",
        "spsa_gain",
        "spsa_perturbation",
        "job_wall_seconds",
    }
    for row in rows:
        for key in numeric & row.keys():
            row[key] = float(row[key])
        row["epoch"] = int(row["epoch"])
    return rows


def write_history(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "phase",
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
            writer.writerow({key: row.get(key, "") for key in fields})


def compact_compiled_circuit(compiled: Any) -> tuple[Any, np.ndarray, dict[int, int]]:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import SparsePauliOp

    active_physical = sorted(
        {
            compiled.circuit.find_bit(qubit).index
            for instruction in compiled.circuit.data
            for qubit in instruction.qubits
        }
    )
    physical_to_compact = {
        physical: compact for compact, physical in enumerate(active_physical)
    }
    compact = QuantumCircuit(len(active_physical), name="scar_fez_compact")
    for instruction in compiled.circuit.data:
        physical = [
            compiled.circuit.find_bit(qubit).index for qubit in instruction.qubits
        ]
        compact.append(
            instruction.operation,
            [physical_to_compact[index] for index in physical],
        )

    observables = np.empty(N_QUBITS, dtype=object)
    for index, observable in enumerate(compiled.observables):
        sparse = observable.to_sparse_list()
        if len(sparse) != 1:
            raise ValueError(f"Unexpected observable: {sparse}")
        label, physical_indices, coefficient = sparse[0]
        compact_indices = [physical_to_compact[int(item)] for item in physical_indices]
        observables[index] = SparsePauliOp.from_sparse_list(
            [(label, compact_indices, coefficient)],
            num_qubits=len(active_physical),
        )
    return compact, observables[None, :], physical_to_compact


def heterogeneous_gate_error(
    backend: Any,
    physical_qubits: tuple[int, ...],
    duration: float,
    target_fidelity: float,
) -> tuple[Any, dict[str, Any]]:
    from qiskit.quantum_info import average_gate_fidelity
    from qiskit_aer.noise import depolarizing_error, thermal_relaxation_error

    thermal_parts = []
    qubit_metadata = []
    for physical in physical_qubits:
        properties = backend.qubit_properties(physical)
        t1 = float(properties.t1)
        t2 = float(min(properties.t2, 2.0 * t1))
        thermal_parts.append(thermal_relaxation_error(t1, t2, duration))
        qubit_metadata.append(
            {"physical_qubit": physical, "t1_seconds": t1, "t2_seconds": t2}
        )

    # Qiskit uses little-endian subsystem ordering for qargs.
    thermal = thermal_parts[-1]
    for part in reversed(thermal_parts[:-1]):
        thermal = thermal.tensor(part)
    thermal_fidelity = float(average_gate_fidelity(thermal.to_quantumchannel()))
    dimension = 1 << len(physical_qubits)
    if target_fidelity >= thermal_fidelity:
        depolarizing_parameter = 0.0
    else:
        depolarizing_parameter = (
            thermal_fidelity - target_fidelity
        ) / (thermal_fidelity - 1.0 / dimension)
    depolarizing_parameter = float(np.clip(depolarizing_parameter, 0.0, 1.0))
    combined = depolarizing_error(
        depolarizing_parameter,
        len(physical_qubits),
    ).compose(thermal)
    combined_fidelity = float(average_gate_fidelity(combined.to_quantumchannel()))
    return combined, {
        "physical_qubits": list(physical_qubits),
        "duration_seconds": duration,
        "target_fidelity": target_fidelity,
        "thermal_fidelity": thermal_fidelity,
        "depolarizing_parameter": depolarizing_parameter,
        "combined_fidelity": combined_fidelity,
        "qubits": qubit_metadata,
    }


def build_compact_noise_model(
    backend: Any,
    compact_circuit: Any,
    physical_to_compact: dict[int, int],
) -> tuple[Any, dict[str, Any]]:
    from qiskit_aer.noise import NoiseModel

    compact_to_physical = {
        compact: physical for physical, compact in physical_to_compact.items()
    }
    noise_model = NoiseModel()
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[int, ...]]] = set()
    for instruction in compact_circuit.data:
        name = instruction.operation.name
        compact_qubits = tuple(
            compact_circuit.find_bit(qubit).index for qubit in instruction.qubits
        )
        key = (name, compact_qubits)
        if key in seen or name == "rz":
            continue
        seen.add(key)
        physical_qubits = tuple(compact_to_physical[index] for index in compact_qubits)
        properties = backend.target[name].get(physical_qubits)
        if properties is None and len(physical_qubits) == 2:
            properties = backend.target[name].get(tuple(reversed(physical_qubits)))
        if properties is None:
            raise ValueError(f"Missing target properties for {name}{physical_qubits}")
        duration = float(properties.duration or 0.0)
        target_error = float(properties.error or 0.0)
        if duration <= 0.0 and target_error <= 0.0:
            continue
        error, metadata = heterogeneous_gate_error(
            backend,
            physical_qubits,
            duration,
            1.0 - target_error,
        )
        noise_model.add_quantum_error(error, name, compact_qubits)
        records.append(
            {
                "gate": name,
                "compact_qubits": list(compact_qubits),
                **metadata,
            }
        )

    physical_qubits = sorted(physical_to_compact)
    qubit_summary = []
    for physical in physical_qubits:
        properties = backend.qubit_properties(physical)
        measure = backend.target["measure"][(physical,)]
        qubit_summary.append(
            {
                "physical_qubit": physical,
                "compact_qubit": physical_to_compact[physical],
                "t1_seconds": float(properties.t1),
                "t2_seconds": float(properties.t2),
                "readout_error": float(measure.error),
                "readout_duration_seconds": float(measure.duration),
            }
        )
    return noise_model, {
        "gate_channels": records,
        "active_qubits": qubit_summary,
        "readout_handling": (
            "Readout errors are recorded but not applied because the real Runtime "
            "experiment enabled measurement mitigation. This is an idealized "
            "mitigation approximation."
        ),
        "dynamical_decoupling_handling": (
            "The real experiment requested XpXm dynamical decoupling. The frozen "
            "gate channels include T1/T2 and calibrated gate errors, but do not "
            "reconstruct the exact Runtime-inserted delay schedule."
        ),
    }


def validate_compaction(
    compiled: Any,
    compact_circuit: Any,
    compact_observables: np.ndarray,
    seed: int,
) -> float:
    from qiskit.quantum_info import SparsePauliOp, Statevector

    logical, data_parameters, weight_parameters = __import__(
        "scar_wine_ibm_qpu"
    ).build_parameterized_scar_qnn()
    rng = np.random.default_rng(seed)
    data = rng.uniform(-1.0, 1.0, len(data_parameters))
    weights = rng.uniform(-1.0, 1.0, len(weight_parameters))
    logical_bound = logical.assign_parameters(
        {
            **dict(zip(data_parameters, data, strict=True)),
            **dict(zip(weight_parameters, weights, strict=True)),
        }
    )
    compact_bound = compact_circuit.assign_parameters(
        {
            **dict(zip(compiled.data_parameters, data, strict=True)),
            **dict(zip(compiled.weight_parameters, weights, strict=True)),
        }
    )
    logical_state = Statevector.from_instruction(logical_bound)
    compact_state = Statevector.from_instruction(compact_bound)
    differences = []
    for qubit in range(N_QUBITS):
        logical_observable = SparsePauliOp.from_sparse_list(
            [("Z", [qubit], 1.0)],
            num_qubits=N_QUBITS,
        )
        expected = float(np.real(logical_state.expectation_value(logical_observable)))
        actual = float(
            np.real(compact_state.expectation_value(compact_observables[0, qubit]))
        )
        differences.append(abs(expected - actual))
    return max(differences)


class ExactFakeFezEvaluator:
    def __init__(
        self,
        seed: int = 42,
        measurement_mode: str = "legacy",
        mitigation_regularization: float = 1e-6,
    ) -> None:
        from qiskit_ibm_runtime.fake_provider import FakeFez

        if measurement_mode not in {"legacy", "raw", "mitigated"}:
            raise ValueError(f"Unsupported measurement mode: {measurement_mode}")
        self.measurement_mode = measurement_mode
        self.backend = FakeFez()
        self.compiled = compile_for_backend(self.backend, optimization_level=3, seed=seed)
        (
            self.circuit,
            self.observables,
            self.physical_to_compact,
        ) = compact_compiled_circuit(self.compiled)
        self.noise_model, self.noise_metadata = build_compact_noise_model(
            self.backend,
            self.circuit,
            self.physical_to_compact,
        )
        compact_to_physical = {
            compact: physical
            for physical, compact in self.physical_to_compact.items()
        }
        backend_properties = self.backend.properties()
        matrices = []
        self.feature_physical_qubits = []
        for observable in self.observables[0]:
            sparse = observable.to_sparse_list()
            compact_qubit = int(sparse[0][1][0])
            physical_qubit = compact_to_physical[compact_qubit]
            self.feature_physical_qubits.append(physical_qubit)
            values = {
                item.name: float(item.value)
                for item in backend_properties.qubits[physical_qubit]
            }
            matrices.append(
                assignment_matrix(
                    1.0 - values["prob_meas1_prep0"],
                    1.0 - values["prob_meas0_prep1"],
                )
            )
        self.measurement_response = MeasurementResponse(
            np.asarray(matrices),
            [
                f"logical_feature_{index}_physical_qubit_{physical}"
                for index, physical in enumerate(self.feature_physical_qubits)
            ],
            regularization=mitigation_regularization,
            calibration_note=(
                "Per-qubit asymmetric FakeFez assignment matrices from "
                "prob_meas1_prep0 and prob_meas0_prep1. Calibration-shot "
                "uncertainty and calibration drift are not included."
            ),
        )
        if measurement_mode != "legacy":
            self.noise_metadata["readout_handling"] = (
                "Readout is explicitly sampled from per-qubit asymmetric "
                "assignment matrices; the mitigated mode applies their "
                "regularized inverse and projects onto the probability simplex."
            )
        self.compaction_max_expectation_error = validate_compaction(
            self.compiled,
            self.circuit,
            self.observables,
            seed,
        )

    def __call__(
        self,
        x: np.ndarray,
        circuit_parameters: np.ndarray,
        shots: int,
        seed: int,
    ) -> np.ndarray:
        from qiskit_aer.primitives import EstimatorV2

        parameters = np.asarray(circuit_parameters, dtype=float)
        if parameters.ndim == 1:
            parameters = np.repeat(parameters[None, :], len(x), axis=0)
        if parameters.shape != (len(x), SCAR_PARAMETERS):
            raise ValueError(
                f"Expected {(len(x), SCAR_PARAMETERS)} parameters, got {parameters.shape}"
            )
        bindings = {
            self.compiled.data_parameters: np.asarray(x, dtype=float)[:, None, :],
            self.compiled.weight_parameters: parameters[:, None, :],
        }
        estimator = EstimatorV2(
            options={
                "backend_options": {
                    "method": "density_matrix",
                    "noise_model": self.noise_model,
                },
                "run_options": {"seed_simulator": int(seed)},
            }
        )
        precision = (
            1.0 / math.sqrt(shots)
            if self.measurement_mode == "legacy"
            else 0.0
        )
        result = estimator.run(
            [(self.circuit, self.observables, bindings)],
            precision=precision,
        ).result()
        features = np.asarray(result[0].data.evs, dtype=float)
        if self.measurement_mode != "legacy":
            return self.measurement_response.apply(
                features,
                shots,
                seed,
                mitigate=self.measurement_mode == "mitigated",
            )
        return np.clip(features, -1.0, 1.0)

    def measurement_metadata(self) -> dict[str, Any]:
        return {
            "mode": self.measurement_mode,
            "logical_feature_physical_qubits": self.feature_physical_qubits,
            **self.measurement_response.metadata(),
        }

    def metadata(self) -> dict[str, Any]:
        properties = self.backend.properties()
        active = sorted(self.physical_to_compact)
        counts = {
            str(name): int(count) for name, count in self.circuit.count_ops().items()
        }
        return {
            "backend": "FakeFez",
            "represents": "ibm_fez, Heron r2, 156 qubits, heavy-hex",
            "snapshot_last_update": str(properties.last_update_date),
            "snapshot_not_experiment_date": True,
            "active_physical_qubits": active,
            "compact_mapping": self.physical_to_compact,
            "compiled_depth": int(self.circuit.depth()),
            "compiled_operation_counts": counts,
            "compiled_two_qubit_gate_count": counts.get("cz", 0),
            "actual_qpu_compiled_depth": 260,
            "actual_qpu_operation_counts": {"rz": 175, "sx": 169, "cz": 66, "x": 1},
            "compaction_max_expectation_error": self.compaction_max_expectation_error,
            "noise": self.noise_metadata,
            "measurement_error_mitigation": self.measurement_metadata(),
        }


def actual_qpu_result(real_payload: dict[str, Any]) -> dict[str, Any]:
    result = real_payload["qpu_result"]
    return {
        "model": "actual_ibm_fez_qpu",
        "seed": result["seed"],
        "parameters": result["parameters"],
        "epochs": result["epochs"],
        "shots": result["shots"],
        "best_epoch": result["best_epoch"],
        "wall_seconds": result["wall_seconds"],
        "train": result["train"],
        "validation": result["validation"],
        "test": result["test"],
        "job_count": result["job_count"],
        "job_ids": [job["job_id"] for job in result["jobs"]],
    }


def mlp_from_real(real_payload: dict[str, Any]) -> dict[str, Any]:
    source = real_payload["classical_reference"]
    return {
        "model": "classical_mlp",
        "seed": source["seed"],
        "parameters": source["parameters"],
        "best_epoch": source["best_epoch"],
        "training_seconds": source["training_seconds"],
        "train": {
            "loss": source["train_loss"],
            "accuracy": source["train_accuracy"],
            "macro_f1": source["train_macro_f1"],
            "confusion": source["train_confusion"],
        },
        "validation": {
            "loss": source["validation_loss"],
            "accuracy": source["validation_accuracy"],
            "macro_f1": source["validation_macro_f1"],
            "confusion": source["validation_confusion"],
        },
        "test": {
            "loss": source["test_loss"],
            "accuracy": source["test_accuracy"],
            "macro_f1": source["test_macro_f1"],
            "confusion": source["test_confusion"],
        },
    }


def plot_results(payload: dict[str, Any], history: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = ["actual_qpu", "simulated_reproduction", "simulated_tuned", "classical_mlp"]
    labels = ["Real IBM\nFez", "FakeFez\nreproduction", "FakeFez\ntuned", "MLP\n4-5-3"]
    colors = ["#111827", "#64748B", "#2563EB", "#D97706"]
    results = payload["results"]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.2))
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.09, top=0.88, hspace=0.40, wspace=0.30)
    fig.suptitle("IBM Fez: real QPU and hardware simulation", fontsize=19, weight="bold", y=0.965)
    fig.text(
        0.5,
        0.925,
        "SCAR-QNN on Wine | exact native circuit: 66 CZ | frozen FakeFez calibration",
        ha="center",
        color="#374151",
    )

    metric_axis = axes[0, 0]
    positions = np.arange(len(keys))
    width = 0.34
    accuracies = [results[key]["test"]["accuracy"] for key in keys]
    f1_values = [results[key]["test"]["macro_f1"] for key in keys]
    bars_accuracy = metric_axis.bar(
        positions - width / 2,
        accuracies,
        width,
        color=colors,
        label="Accuracy",
    )
    bars_f1 = metric_axis.bar(
        positions + width / 2,
        f1_values,
        width,
        color=colors,
        alpha=0.50,
        label="Macro-F1",
    )
    for bar in [*bars_accuracy, *bars_f1]:
        metric_axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.018,
            f"{bar.get_height():.2f}",
            ha="center",
            fontsize=9,
            weight="bold",
        )
    metric_axis.set(
        title="Test performance",
        xticks=positions,
        xticklabels=labels,
        ylabel="Score",
        ylim=(0.0, 1.08),
    )
    metric_axis.grid(axis="y", alpha=0.24)
    metric_axis.legend(frameon=False, loc="lower right")

    loss_axis = axes[0, 1]
    curves = [
        ("actual_qpu", "Real IBM Fez", colors[0]),
        ("reproduction", "FakeFez reproduction", colors[1]),
        ("tuned", "FakeFez tuned", colors[2]),
    ]
    for phase, label, color in curves:
        rows = [row for row in history if row["phase"] == phase]
        loss_axis.plot(
            [row["epoch"] + 1 for row in rows],
            [row["validation_loss"] for row in rows],
            color=color,
            linewidth=2,
            marker="o" if phase != "tuned" else None,
            markersize=3.5,
            label=label,
        )
    loss_axis.set(
        title="Validation loss",
        xlabel="Epoch",
        ylabel="Cross entropy",
    )
    loss_axis.grid(alpha=0.24)
    loss_axis.legend(frameon=False)

    topology_axis = axes[1, 0]
    path = [25, 37, 45, 44]
    x_positions = np.arange(4)
    topology_axis.plot(x_positions, np.zeros(4), color="#2563EB", linewidth=4, zorder=1)
    topology_axis.plot(
        [x_positions[0], x_positions[-1]],
        [0.0, 0.0],
        color="#DC2626",
        linewidth=2,
        linestyle="--",
        alpha=0.85,
        zorder=0,
    )
    for x_value, physical in zip(x_positions, path, strict=True):
        topology_axis.scatter(
            x_value,
            0.0,
            s=650,
            color="#2563EB",
            edgecolor="white",
            linewidth=2,
            zorder=2,
        )
        topology_axis.text(
            x_value,
            0.0,
            str(physical),
            color="white",
            ha="center",
            va="center",
            weight="bold",
        )
    topology_axis.text(1.5, 0.25, "native heavy-hex path", ha="center", color="#2563EB")
    topology_axis.text(1.5, -0.26, "missing ring edge -> routed CZ overhead", ha="center", color="#B91C1C")
    topology_axis.set(title="Active physical qubits in frozen FakeFez snapshot", xlim=(-0.5, 3.5), ylim=(-0.55, 0.55))
    topology_axis.axis("off")

    calibration_axis = axes[1, 1]
    active = payload["hardware_model"]["noise"]["active_qubits"]
    qubit_labels = [str(row["physical_qubit"]) for row in active]
    t1 = [1e6 * row["t1_seconds"] for row in active]
    t2 = [1e6 * row["t2_seconds"] for row in active]
    x_values = np.arange(len(active))
    bars_t1 = calibration_axis.bar(x_values - width / 2, t1, width, color="#007C83", label="T1")
    bars_t2 = calibration_axis.bar(x_values + width / 2, t2, width, color="#7C3AED", label="T2")
    for bar in [*bars_t1, *bars_t2]:
        calibration_axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 4,
            f"{bar.get_height():.0f}",
            ha="center",
            fontsize=8,
        )
    calibration_axis.set(
        title="Frozen active-qubit coherence",
        xlabel="Physical qubit",
        ylabel="Microseconds",
        xticks=x_values,
        xticklabels=qubit_labels,
        ylim=(0, max(max(t1), max(t2)) * 1.22),
    )
    calibration_axis.grid(axis="y", alpha=0.24)
    calibration_axis.legend(frameon=False)

    fig.savefig(OUTPUT_PNG, dpi=180)
    fig.savefig(OUTPUT_SVG)
    plt.close(fig)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    results = payload["results"]
    actual = results["actual_qpu"]
    reproduction = results["simulated_reproduction"]
    tuned = results["simulated_tuned"]
    mlp = results["classical_mlp"]
    comparison = payload["comparison"]
    hardware = payload["hardware_model"]
    lines = [
        "# IBM Fez: odtworzenie QPU i strojony trening na symulatorze",
        "",
        "## Wynik",
        "",
        "| Wariant | Epoki | Strzaly | Accuracy | Macro-F1 |",
        "|---|---:|---:|---:|---:|",
        f"| Prawdziwy ibm_fez | {actual['epochs']} | {actual['shots']} | "
        f"{actual['test']['accuracy']:.3f} | {actual['test']['macro_f1']:.3f} |",
        f"| FakeFez, odtworzenie | {reproduction['epochs']} | {reproduction['shots']} | "
        f"{reproduction['test']['accuracy']:.3f} | {reproduction['test']['macro_f1']:.3f} |",
        f"| FakeFez, profil v2 | {tuned['epochs']} | {tuned['shots']} | "
        f"{tuned['test']['accuracy']:.3f} | {tuned['test']['macro_f1']:.3f} |",
        f"| Klasyczne MLP | 160 | - | {mlp['test']['accuracy']:.3f} | "
        f"{mlp['test']['macro_f1']:.3f} |",
        "",
        f"Odtworzenie rozni sie od wyniku prawdziwego QPU o "
        f"`{comparison['reproduction_accuracy_minus_qpu']:+.3f}` accuracy. "
        f"Strojenie zmienilo wynik symulatora o "
        f"`{comparison['tuned_accuracy_minus_reproduction']:+.3f}`.",
        "",
        "## Co zostalo odtworzone",
        "",
        "- Ten sam Wine split (seed 42), PCA 13->4, ansatz 4 kubity / 2 warstwy "
        "SCAR i 43 parametry.",
        "- Protokol QPU: 12 epok, SPSA a=0.12, c=0.15, Adam lr=0.04 i 256 strzalow.",
        f"- Dokladny natywny obwod FakeFez: glebokosc `{hardware['compiled_depth']}`, "
        f"`{hardware['compiled_two_qubit_gate_count']}` bramek CZ i aktywne kubity "
        f"`{hardware['active_physical_qubits']}`.",
        "- Osobne kanaly T1/T2 + residual depolarizing dla kazdej bramki SX/X/CZ, "
        "dopasowane do zamrozonej kalibracji IBM.",
        "- Measurement mitigation odwzorowano jako idealna korekcje readoutu. "
        "Dokladny harmonogram XpXm dynamical decoupling nie jest rekonstruowany.",
        "",
        "## Zmienione hiperparametry",
        "",
        "- Epoki: 12 -> 64.",
        "- Strzaly treningowe: 256 -> 1024; ewaluacja: 256 -> 4096.",
        "- SPSA a: 0.12 -> 0.10; SPSA c: 0.15 -> 0.08.",
        "- Learning rate glowicy: 0.04 -> 0.08.",
        "- Checkpoint nadal wybiera najnizsza strate walidacyjna.",
        "",
        "## Ograniczenie odtworzenia",
        "",
        f"FakeFez jest snapshotem z `{hardware['snapshot_last_update']}`, a prawdziwy "
        "eksperyment wykonano 2026-07-20. Tymczasowy klucz z eksperymentu nie byl "
        "zapisany, dlatego kalibracja z chwili jobow nie jest dostepna. Zgodnosc "
        "66 CZ i bardzo podobnej glebokosci potwierdza architekture, ale rozne "
        "kalibracje, losowanie strzalow, mitigation i Runtime DD uniemozliwiaja "
        "bitowe odtworzenie wyniku.",
        "",
        f"Blad kompakcji obwodu wyniosl `{hardware['compaction_max_expectation_error']:.2e}`.",
        "Wyniki pochodza z jednego seedu i nie dowodza przewagi kwantowej.",
        "",
        "## Pliki",
        "",
        f"- Wyniki: `{OUTPUT_JSON.name}`",
        f"- Historia: `{OUTPUT_HISTORY.name}`",
        f"- Wykres: `{OUTPUT_PNG.name}`",
        f"- Zrodlo prawdziwego QPU: `{REAL_RESULT.name}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    seed = 42
    real_payload = load_json(REAL_RESULT)
    real_history = read_csv(REAL_HISTORY)
    x, y = load_wine()
    split = prepare_split(x, y, seed)
    evaluator = ExactFakeFezEvaluator(seed)
    hardware_metadata = evaluator.metadata()
    if evaluator.compaction_max_expectation_error > 1e-10:
        raise AssertionError(
            f"Circuit compaction error: {evaluator.compaction_max_expectation_error}"
        )

    print("Reproducing the real IBM QPU protocol on frozen FakeFez...", flush=True)
    reproduction, reproduction_history = train_hardware_model(
        "simulated_ibm_reproduction",
        split,
        evaluator,
        epochs=12,
        shots=256,
        final_shots=256,
        seed=seed,
        spsa_a=0.12,
        spsa_c=0.15,
        head_learning_rate=0.04,
        weight_decay=1e-4,
    )
    print("Training the tuned IBM simulation profile...", flush=True)
    tuned, tuned_history = train_hardware_model(
        "simulated_ibm_tuned",
        split,
        evaluator,
        epochs=64,
        shots=1024,
        final_shots=4096,
        seed=seed,
        spsa_a=0.10,
        spsa_c=0.08,
        head_learning_rate=0.08,
        weight_decay=1e-4,
    )

    actual = actual_qpu_result(real_payload)
    mlp = mlp_from_real(real_payload)
    all_history = []
    for row in real_history:
        all_history.append({"phase": "actual_qpu", "model": "actual_ibm_fez_qpu", **row})
    for row in reproduction_history:
        all_history.append({"phase": "reproduction", **row})
    for row in tuned_history:
        all_history.append({"phase": "tuned", **row})

    payload = {
        "execution_status": "completed_local_ibm_reproduction_and_tuned_simulation",
        "not_a_new_physical_qpu_execution": True,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dataset": real_payload["dataset"],
        "real_qpu_source": {
            "path": str(REAL_RESULT),
            "execution_status": real_payload["execution_status"],
            "backend": real_payload["architecture"]["backend"],
            "processor_type": real_payload["architecture"]["processor_type"],
            "batch_id": "e6ef9c37-9d0a-4168-995d-698a0c83fca6",
        },
        "hardware_model": hardware_metadata,
        "protocols": {
            "reproduction": {
                "epochs": 12,
                "shots": 256,
                "final_shots": 256,
                "spsa_a": 0.12,
                "spsa_c": 0.15,
                "head_learning_rate": 0.04,
            },
            "tuned_v2": {
                "epochs": 64,
                "shots": 1024,
                "final_shots": 4096,
                "spsa_a": 0.10,
                "spsa_c": 0.08,
                "head_learning_rate": 0.08,
                "selection": "same validation-tuned profile used for the other simulated QPUs",
            },
        },
        "results": {
            "actual_qpu": actual,
            "simulated_reproduction": reproduction,
            "simulated_tuned": tuned,
            "classical_mlp": mlp,
        },
        "comparison": {
            "reproduction_accuracy_minus_qpu": (
                reproduction["test"]["accuracy"] - actual["test"]["accuracy"]
            ),
            "reproduction_macro_f1_minus_qpu": (
                reproduction["test"]["macro_f1"] - actual["test"]["macro_f1"]
            ),
            "tuned_accuracy_minus_reproduction": (
                tuned["test"]["accuracy"] - reproduction["test"]["accuracy"]
            ),
            "tuned_macro_f1_minus_reproduction": (
                tuned["test"]["macro_f1"] - reproduction["test"]["macro_f1"]
            ),
        },
        "limitations": [
            "FakeFez calibration snapshot predates the real 2026-07-20 experiment.",
            "Measurement mitigation is approximated as ideal readout correction.",
            "The exact Runtime XpXm dynamical-decoupling schedule is unavailable.",
            "Aer finite-shot expectation noise is a Gaussian surrogate.",
            "One split and one seed are reported.",
        ],
    }
    write_json(OUTPUT_JSON, payload)
    write_history(OUTPUT_HISTORY, all_history)
    plot_results(payload, all_history)
    write_report(OUTPUT_REPORT, payload)

    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_HISTORY}")
    print(f"Real QPU accuracy: {actual['test']['accuracy']:.3f}")
    print(f"Reproduced simulator accuracy: {reproduction['test']['accuracy']:.3f}")
    print(f"Tuned simulator accuracy: {tuned['test']['accuracy']:.3f}")


if __name__ == "__main__":
    main()
