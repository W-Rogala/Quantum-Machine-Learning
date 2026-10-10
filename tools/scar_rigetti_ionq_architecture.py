from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
os.environ.setdefault("MPLCONFIGDIR", str(ANALYSIS / ".matplotlib"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from qiskit import QuantumCircuit, transpile  # noqa: E402
from qiskit.quantum_info import Operator  # noqa: E402
from qiskit.transpiler import CouplingMap  # noqa: E402
from qiskit_ionq import (  # noqa: E402
    GPI2Gate,
    GPIGate,
    ZZGate,
    add_equivalences,
)
from qiskit_ionq.ionq_optimizer_plugin import CustomPassManager  # noqa: E402
from qiskit_ionq.rewrite_rules import (  # noqa: E402
    CancelGPI2Adjoint,
    CancelGPIAdjoint,
    CompactMoreThanThreeSingleQubitGates,
    CommuteGPIsThroughZZ,
    FuseConsecutiveZZ,
    GPI2TwiceIsGPI,
)


if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from scar_wine_ibm_qpu import build_parameterized_scar_qnn  # noqa: E402


OUTPUT_JSON = ANALYSIS / "scar_rigetti_ionq_architecture_result.json"
OUTPUT_PNG = ANALYSIS / "scar_rigetti_ionq_architecture.png"
OUTPUT_SVG = ANALYSIS / "scar_rigetti_ionq_architecture.svg"
IBM_RESULT = ANALYSIS / "scar_wine_ibm_qpu_result.json"


def matrix_error(reference: QuantumCircuit, candidate: QuantumCircuit) -> float:
    expected = Operator(reference).data
    actual = Operator(candidate).data
    overlap = np.vdot(expected.reshape(-1), actual.reshape(-1))
    phase = overlap / abs(overlap)
    return float(np.max(np.abs(actual - phase * expected)))


def two_qubit_depth(circuit: QuantumCircuit) -> int:
    return int(circuit.depth(filter_function=lambda item: len(item.qubits) == 2))


def bind_reference(seed: int = 42) -> QuantumCircuit:
    circuit, data, weights = build_parameterized_scar_qnn()
    rng = np.random.default_rng(seed)
    values = {
        parameter: float(rng.uniform(-1.0, 1.0))
        for parameter in [*data, *weights]
    }
    return circuit.assign_parameters(values)


def compile_rigetti(reference: QuantumCircuit) -> tuple[QuantumCircuit, dict[str, Any]]:
    # The four logical qubits are embedded in one square cell of Ankaa-3.
    square_edges = [
        (0, 1),
        (1, 0),
        (1, 2),
        (2, 1),
        (2, 3),
        (3, 2),
        (3, 0),
        (0, 3),
    ]
    compiled = transpile(
        reference,
        basis_gates=["rx", "rz", "iswap"],
        coupling_map=CouplingMap(square_edges),
        initial_layout=[0, 1, 2, 3],
        optimization_level=3,
        seed_transpiler=42,
    )
    counts = {str(name): int(value) for name, value in compiled.count_ops().items()}
    one_qubit_count = counts.get("rx", 0) + counts.get("rz", 0)
    two_qubit_count = counts.get("iswap", 0)
    return compiled, {
        "provider": "Rigetti",
        "target": "Ankaa-3",
        "technology": "superconducting tunable transmons",
        "physical_qubits": 84,
        "connectivity": "7 x 12 square lattice",
        "selected_physical_cycle": [0, 1, 8, 7],
        "native_gates": ["rx", "rz", "iswap"],
        "operation_counts": counts,
        "one_qubit_gate_count": one_qubit_count,
        "two_qubit_gate": "iswap",
        "two_qubit_gate_count": two_qubit_count,
        "depth": int(compiled.depth()),
        "two_qubit_depth": two_qubit_depth(compiled),
        "matrix_max_error": matrix_error(reference, compiled),
        "routing_swaps": counts.get("swap", 0),
        "public_median_1q_fidelity": 0.999,
        "public_median_2q_fidelity": 0.990,
        "gate_product_fidelity_estimate": (
            0.999**one_qubit_count * 0.990**two_qubit_count
        ),
    }


def append_u_native(
    circuit: QuantumCircuit,
    theta: float,
    phi: float,
    lam: float,
    qubit: int,
) -> None:
    circuit.append(GPI2Gate(0.5 - lam / (2 * np.pi)), [qubit])
    circuit.append(
        GPIGate(theta / (4 * np.pi) + phi / (4 * np.pi) - lam / (4 * np.pi)),
        [qubit],
    )
    circuit.append(GPI2Gate(0.5 + phi / (2 * np.pi)), [qubit])


def append_h_native(circuit: QuantumCircuit, qubit: int) -> None:
    append_u_native(circuit, np.pi / 2, 0.0, np.pi, qubit)


def append_rx90_native(circuit: QuantumCircuit, sign: int, qubit: int) -> None:
    circuit.append(GPI2Gate(0.0 if sign > 0 else 0.5), [qubit])


def append_zz_native(
    circuit: QuantumCircuit,
    angle_radians: float,
    left: int,
    right: int,
) -> None:
    circuit.append(ZZGate(angle_radians / (2 * np.pi)), [left, right])


def to_ionq_forte_native(reference: QuantumCircuit) -> QuantumCircuit:
    native = QuantumCircuit(reference.num_qubits)
    for instruction in reference.data:
        operation = instruction.operation
        qubits = [reference.find_bit(qubit).index for qubit in instruction.qubits]
        angle = float(operation.params[0])
        if operation.name == "ry":
            append_u_native(native, angle, 0.0, 0.0, qubits[0])
        elif operation.name == "rz":
            append_u_native(native, 0.0, 0.0, angle, qubits[0])
        elif operation.name == "rxx":
            append_h_native(native, qubits[0])
            append_h_native(native, qubits[1])
            append_zz_native(native, angle, qubits[0], qubits[1])
            append_h_native(native, qubits[0])
            append_h_native(native, qubits[1])
        elif operation.name == "ryy":
            append_rx90_native(native, -1, qubits[0])
            append_rx90_native(native, -1, qubits[1])
            append_zz_native(native, angle, qubits[0], qubits[1])
            append_rx90_native(native, 1, qubits[0])
            append_rx90_native(native, 1, qubits[1])
        elif operation.name == "rzz":
            append_zz_native(native, angle, qubits[0], qubits[1])
        else:
            raise ValueError(f"Unsupported operation: {operation.name}")
    return native


def optimize_ionq_native(circuit: QuantumCircuit) -> QuantumCircuit:
    pass_manager = CustomPassManager(
        [
            CancelGPI2Adjoint(),
            CancelGPIAdjoint(),
            GPI2TwiceIsGPI(),
            CommuteGPIsThroughZZ(),
            CompactMoreThanThreeSingleQubitGates(),
            FuseConsecutiveZZ(),
        ]
    )
    return pass_manager.run(circuit)


def compile_ionq(reference: QuantumCircuit) -> tuple[QuantumCircuit, dict[str, Any]]:
    add_equivalences()
    compiled = optimize_ionq_native(to_ionq_forte_native(reference))
    counts = {str(name): int(value) for name, value in compiled.count_ops().items()}
    one_qubit_count = counts.get("gpi", 0) + counts.get("gpi2", 0)
    two_qubit_count = counts.get("zz", 0)
    return compiled, {
        "provider": "IonQ",
        "target": "Forte-1 / Forte Enterprise-1",
        "technology": "trapped ytterbium ions",
        "physical_qubits": 36,
        "connectivity": "all-to-all",
        "selected_physical_cycle": "not required",
        "native_gates": ["gpi", "gpi2", "zz"],
        "operation_counts": counts,
        "one_qubit_gate_count": one_qubit_count,
        "two_qubit_gate": "zz",
        "two_qubit_gate_count": two_qubit_count,
        "depth": int(compiled.depth()),
        "two_qubit_depth": two_qubit_depth(compiled),
        "matrix_max_error": matrix_error(reference, compiled),
        "routing_swaps": 0,
        "public_median_1q_fidelity": 0.9998,
        "public_median_2q_fidelity": 0.996,
        "gate_product_fidelity_estimate": (
            0.9998**one_qubit_count * 0.996**two_qubit_count
        ),
    }


def workload_cost(
    configurations: int,
    shots: int,
    per_task: float,
    per_shot: float,
    programs_per_task: int,
) -> dict[str, float | int]:
    tasks = math.ceil(configurations / programs_per_task)
    total_shots = configurations * shots
    return {
        "configurations": configurations,
        "shots_per_configuration": shots,
        "total_shots": total_shots,
        "tasks": tasks,
        "estimated_usd": tasks * per_task + total_shots * per_shot,
    }


def cost_estimates(configurations: int, shots: int) -> dict[str, Any]:
    per_task = 0.30
    return {
        "pricing_basis": "Amazon Braket on-demand, verified 2026-07-21",
        "full_training": {
            "rigetti_ankaa": workload_cost(
                configurations, shots, per_task, 0.0009, 100
            ),
            "rigetti_cepheus": workload_cost(
                configurations, shots, per_task, 0.000425, 100
            ),
            "ionq_forte": workload_cost(
                configurations, shots, per_task, 0.08, 1
            ),
        },
        "test_only_35_samples_100_shots": {
            "rigetti_ankaa": workload_cost(35, 100, per_task, 0.0009, 100),
            "rigetti_cepheus": workload_cost(35, 100, per_task, 0.000425, 100),
            "ionq_forte": workload_cost(35, 100, per_task, 0.08, 1),
        },
        "notes": [
            "Rigetti program sets can package up to 100 programs or parameter sets per task.",
            "IonQ is costed as one Braket task per parameter configuration.",
            "IonQ error mitigation is excluded; it requires at least 2500 shots per task.",
            "S3 and other incidental AWS costs are excluded.",
        ],
    }


def draw_topologies(axis: plt.Axes) -> None:
    axis.set_title("Topologia czterech kubitów SCAR")
    rigetti = {0: (0, 1), 1: (1, 1), 2: (1, 0), 3: (0, 0)}
    ionq = {
        0: (3.0, 1.0),
        1: (4.0, 1.0),
        2: (4.0, 0.0),
        3: (3.0, 0.0),
    }
    for positions, complete, color in [
        (rigetti, False, "#007C83"),
        (ionq, True, "#B91C1C"),
    ]:
        nodes = list(positions)
        edges = []
        if complete:
            edges = [(left, right) for left in nodes for right in nodes if left < right]
        else:
            edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
        for left, right in edges:
            x = [positions[left][0], positions[right][0]]
            y = [positions[left][1], positions[right][1]]
            axis.plot(x, y, color=color, linewidth=2, alpha=0.72, zorder=1)
        for node, (x, y) in positions.items():
            axis.scatter(x, y, s=460, color=color, edgecolor="white", linewidth=2, zorder=2)
            axis.text(x, y, str(node), ha="center", va="center", color="white", weight="bold")
    axis.text(0.5, -0.32, "Rigetti: kwadrat", ha="center", weight="bold")
    axis.text(3.5, -0.32, "IonQ: all-to-all", ha="center", weight="bold")
    axis.set_xlim(-0.6, 4.6)
    axis.set_ylim(-0.55, 1.35)
    axis.set_aspect("equal")
    axis.axis("off")


def plot_result(payload: dict[str, Any]) -> None:
    rigetti = payload["architectures"]["rigetti_ankaa3"]
    ionq = payload["architectures"]["ionq_forte"]
    ibm = payload["ibm_reference"]
    costs = payload["costs"]["full_training"]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.8))
    fig.subplots_adjust(left=0.08, right=0.96, bottom=0.11, top=0.86, hspace=0.42, wspace=0.30)
    fig.suptitle("SCAR-QNN: Rigetti kontra IonQ", fontsize=18, weight="bold", y=0.97)
    fig.text(
        0.5,
        0.925,
        "Dokładna kompilacja natywna, 4 kubity, 2 warstwy SCAR",
        ha="center",
        color="#374151",
    )

    draw_topologies(axes[0, 0])

    metric_axis = axes[0, 1]
    labels = ["Rigetti\nAnkaa-3", "IonQ\nForte", "IBM\nHeron r2"]
    gates = [
        rigetti["two_qubit_gate_count"],
        ionq["two_qubit_gate_count"],
        ibm["two_qubit_gate_count"],
    ]
    depths = [rigetti["depth"], ionq["depth"], ibm["depth"]]
    x = np.arange(3)
    width = 0.35
    bars_gates = metric_axis.bar(x - width / 2, gates, width, color="#007C83", label="Bramki 2Q")
    bars_depth = metric_axis.bar(x + width / 2, depths, width, color="#D97706", label="Głębokość")
    for bar in [*bars_gates, *bars_depth]:
        metric_axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 5,
            f"{bar.get_height():.0f}",
            ha="center",
            weight="bold",
            fontsize=9,
        )
    metric_axis.set(title="Narzut po kompilacji", xticks=x, xticklabels=labels, ylim=(0, 290))
    metric_axis.grid(axis="y", alpha=0.25)
    metric_axis.legend(frameon=False)

    fidelity_axis = axes[1, 0]
    fidelity_values = [
        rigetti["gate_product_fidelity_estimate"],
        ionq["gate_product_fidelity_estimate"],
    ]
    fidelity_bars = fidelity_axis.bar(
        [0, 1], fidelity_values, color=["#007C83", "#B91C1C"], width=0.58
    )
    for bar in fidelity_bars:
        fidelity_axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.025,
            f"{bar.get_height():.3f}",
            ha="center",
            weight="bold",
        )
    fidelity_axis.set(
        title="Iloczyn publicznych median fidelity",
        ylabel="Przybliżona fidelity obwodu",
        xticks=[0, 1],
        xticklabels=["Rigetti Ankaa-3", "IonQ Forte"],
        ylim=(0, 1.03),
    )
    fidelity_axis.grid(axis="y", alpha=0.25)
    cost_axis = axes[1, 1]
    cost_labels = ["Rigetti\nAnkaa", "Rigetti\nCepheus", "IonQ\nForte"]
    cost_values = [
        costs["rigetti_ankaa"]["estimated_usd"],
        costs["rigetti_cepheus"]["estimated_usd"],
        costs["ionq_forte"]["estimated_usd"],
    ]
    cost_bars = cost_axis.bar(
        range(3), cost_values, color=["#007C83", "#3B82F6", "#B91C1C"], width=0.62
    )
    cost_axis.set_yscale("log")
    cost_axis.set(
        title="Szacowany koszt pełnego treningu Braket",
        ylabel="USD, skala logarytmiczna",
        xticks=range(3),
        xticklabels=cost_labels,
    )
    cost_axis.set_ylim(min(cost_values) / 1.6, max(cost_values) * 2.2)
    cost_axis.grid(axis="y", which="both", alpha=0.25)
    for bar, value in zip(cost_bars, cost_values, strict=True):
        cost_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.22,
            f"${value:,.0f}",
            ha="center",
            weight="bold",
            fontsize=9,
        )

    fig.text(
        0.08,
        0.035,
        "Bez wykonania QPU: brak poświadczeń; koszty bazują na 3178 konfiguracjach × 256 strzałów.",
        color="#4B5563",
        fontsize=9,
    )
    fig.savefig(OUTPUT_PNG, dpi=180, facecolor="white")
    fig.savefig(OUTPUT_SVG, facecolor="white")


def main() -> None:
    reference = bind_reference()
    _, rigetti = compile_rigetti(reference)
    _, ionq = compile_ionq(reference)

    ibm_payload = json.loads(IBM_RESULT.read_text(encoding="utf-8"))
    configurations = int(
        ibm_payload["training_protocol"][
            "estimated_parameterized_circuit_configurations"
        ]
    )
    shots = int(ibm_payload["training_protocol"]["shots"])
    payload = {
        "execution_status": "architecture_compile_and_local_exact_validation",
        "not_a_qpu_execution": True,
        "reference": {
            "model": "SCAR-QNN Wine",
            "qubits": reference.num_qubits,
            "scar_layers": 2,
            "seed_for_numeric_compilation": 42,
        },
        "architectures": {
            "rigetti_ankaa3": rigetti,
            "ionq_forte": ionq,
        },
        "ibm_reference": {
            "target": "ibm_fez Heron r2",
            "depth": int(ibm_payload["architecture"]["transpiled_depth"]),
            "two_qubit_gate": "cz",
            "two_qubit_gate_count": int(
                ibm_payload["architecture"]["transpiled_two_qubit_gate_count"]
            ),
            "qpu_test_accuracy": float(
                ibm_payload["qpu_result"]["test"]["accuracy"]
            ),
        },
        "costs": cost_estimates(configurations, shots),
        "interpretation": {
            "best_hardware_fit": "IonQ Forte",
            "best_cost_to_fit_tradeoff": "Rigetti Ankaa-3",
            "reason": (
                "IonQ provides all-to-all connectivity and a native ZZ gate; "
                "Rigetti provides a physical square and native iSWAP. Both avoid "
                "the routing overhead observed on IBM Heron heavy-hex."
            ),
            "accuracy_warning": (
                "Gate fidelity products cannot be converted into a reliable "
                "classification accuracy without a calibrated noise model or QPU run."
            ),
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    plot_result(payload)
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_PNG}")
    print(f"Wrote {OUTPUT_SVG}")


if __name__ == "__main__":
    main()
