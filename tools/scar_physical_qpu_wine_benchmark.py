from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis_output"
os.environ.setdefault("MPLCONFIGDIR", str(ANALYSIS / ".matplotlib"))

if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from scar_wine_ibm_qpu import build_parameterized_scar_qnn  # noqa: E402
from scar_measurement_mitigation import (  # noqa: E402
    MeasurementResponse,
    assignment_matrix,
    symmetric_assignment_matrix,
)
from scar_wine_qnn_benchmark import (  # noqa: E402
    MLP_PARAMETERS,
    N_CLASSES,
    N_QUBITS,
    QNN_PARAMETERS,
    READOUT_PARAMETERS,
    SCAR_PARAMETERS,
    Adam,
    accuracy,
    cross_entropy,
    initialize_qnn,
    load_wine,
    macro_f1,
    prepare_split,
    softmax,
    train_mlp,
)


OUTPUT_JSON = ANALYSIS / "scar_physical_qpu_wine_results.json"
OUTPUT_HISTORY = ANALYSIS / "scar_physical_qpu_wine_history.csv"
OUTPUT_REPORT = ANALYSIS / "scar_physical_qpu_wine_report.md"
OUTPUT_PNG = ANALYSIS / "scar_physical_qpu_wine_comparison.png"
OUTPUT_SVG = ANALYSIS / "scar_physical_qpu_wine_comparison.svg"

LOGICAL_ONE_QUBIT_GATES = 40
LOGICAL_TWO_QUBIT_GATES = 24
X8_CIRCUIT_PARAMETERS = SCAR_PARAMETERS


@dataclass(frozen=True)
class QubitHardwareProfile:
    key: str
    provider: str
    processor: str
    technology: str
    physical_qubits: int
    topology: str
    native_gates: tuple[str, ...]
    t1_seconds: float
    t2_seconds: float
    one_qubit_gate_seconds: float
    two_qubit_gate_seconds: float
    one_qubit_fidelity: float
    two_qubit_fidelity: float
    readout_fidelity: float
    compiled_one_qubit_pulses: int
    compiled_two_qubit_pulses: int
    compiled_depth: int
    timing_notes: str
    readout_notes: str


RIGETTI = QubitHardwareProfile(
    key="rigetti_ankaa3",
    provider="Rigetti",
    processor="Ankaa-3",
    technology="superconducting tunable transmons",
    physical_qubits=84,
    topology="7 x 12 nearest-neighbour square lattice; SCAR uses one 4-qubit cell",
    native_gates=("RX", "RZ", "iSWAP"),
    t1_seconds=22e-6,
    t2_seconds=19e-6,
    one_qubit_gate_seconds=40e-9,
    two_qubit_gate_seconds=72e-9,
    one_qubit_fidelity=0.999,
    two_qubit_fidelity=0.990,
    readout_fidelity=0.950,
    compiled_one_qubit_pulses=52,
    compiled_two_qubit_pulses=24,
    compiled_depth=77,
    timing_notes=(
        "T1/T2 and gate fidelities are Ankaa-3 public medians. The 72 ns iSWAP "
        "duration is published by Rigetti. The 40 ns 1Q duration is the last "
        "directly published Rigetti 1Q median (Aspen-10), used because a live "
        "Ankaa-3 pulse calibration was not publicly accessible."
    ),
    readout_notes=(
        "0.95 is the official pyQuil generic readout-fidelity default, not a "
        "published Ankaa-3 median."
    ),
)


IONQ = QubitHardwareProfile(
    key="ionq_forte",
    provider="IonQ",
    processor="Forte-1 / Forte Enterprise-1",
    technology="trapped 171Yb+ ions",
    physical_qubits=36,
    topology="all-to-all within one ion chain; no routing SWAPs",
    native_gates=("GPI", "GPI2", "ZZ"),
    t1_seconds=10.0,
    t2_seconds=1.0,
    one_qubit_gate_seconds=10e-6,
    two_qubit_gate_seconds=600e-6,
    one_qubit_fidelity=0.9998,
    two_qubit_fidelity=0.996,
    readout_fidelity=0.995,
    compiled_one_qubit_pulses=112,
    compiled_two_qubit_pulses=24,
    compiled_depth=80,
    timing_notes=(
        "IonQ publishes T1=10-100 s and T2 about 1 s; the conservative lower "
        "T1 bound is used. Exact current Forte gate durations require an "
        "authenticated characterization API, so 10 us (1Q) and 600 us (2Q) "
        "are explicit representative timing assumptions, not IonQ claims."
    ),
    readout_notes="IonQ publishes a 0.5% aggregate SPAM error; it is mapped to symmetric readout.",
)


XANADU_X8: dict[str, Any] = {
    "key": "xanadu_x8",
    "provider": "Xanadu",
    "processor": "X8",
    "technology": "integrated continuous-variable photonics",
    "modes": 8,
    "topology": (
        "four fixed two-mode-squeezed pairs (0,4), (1,5), (2,6), (3,7), "
        "followed by one programmable SU(4) interferometer on each four-mode half"
    ),
    "native_operations": ("S2(r in {0,1})", "R", "beamsplitter", "PNR"),
    "squeezing_r": 1.0,
    "effective_input_squeezing_db": 8.0,
    "total_transmission": 0.15,
    "detector_efficiency_lower_bound": 0.95,
    "interferometer_loss_db": 3.0,
    "total_system_loss_db": 8.0,
    "beamsplitter_extinction_db": 18.0,
    "model_total_variation_error": 0.10,
    "excess_photon_mean": 0.002,
    "excess_photon_note": (
        "The paper models residual photons with a fitted Poisson term but does "
        "not publish one aggregate mean in the main article. 0.002 photons/mode "
        "is an explicit sensitivity assumption."
    ),
}


SOURCES = [
    {
        "title": "Rigetti: Building scalable, innovative quantum systems",
        "url": "https://www.rigetti.com/what-we-build",
        "used_for": (
            "Ankaa-3 qubit count, T1, T2, 1Q and iSWAP fidelities, crosstalk "
            "context, and the last directly published 40 ns Rigetti 1Q median"
        ),
    },
    {
        "title": "Rigetti QCS FAQ",
        "url": "https://docs.rigetti.com/qcs/faq",
        "used_for": "native calibrations and limitations of public live calibration data",
    },
    {
        "title": "Rigetti 2025 Form 10-K",
        "url": "https://investors.rigetti.com/static-files/7d2eb912-600b-48fc-8845-87de6bff68d4",
        "used_for": "Ankaa-3 72 ns median iSWAP duration",
    },
    {
        "title": "Rigetti pyQuil noise documentation",
        "url": "https://pyquil-docs.rigetti.com/en/latest/apidocs/pyquil.noise.html",
        "used_for": "generic 0.95 readout assumption and channel-model semantics",
    },
    {
        "title": "IonQ Forte specifications",
        "url": "https://www.ionq.com/quantum-systems/forte",
        "used_for": "36 qubits, T1/T2, 1Q/2Q/SPAM errors",
    },
    {
        "title": "IonQ hardware best practices",
        "url": "https://www.ionq.com/resources/best-practices-for-using-ionq-hardware",
        "used_for": "all-to-all connectivity and native-control context",
    },
    {
        "title": "IonQ characterization API",
        "url": (
            "https://docs.ionq.com/api-reference/v0.3/characterizations/"
            "get-the-most-recent-backend-characterization"
        ),
        "used_for": "fields available only through authenticated current characterization",
    },
    {
        "title": "Xanadu X-Series",
        "url": "https://xanadu.ai/products/x-series/",
        "used_for": "X8 availability, squeezed-state and PNR architecture",
    },
    {
        "title": "Quantum circuits with many photons on a programmable nanophotonic chip",
        "url": "https://doi.org/10.1038/s41586-021-03202-1",
        "used_for": "X8 topology, squeezing, loss, detector efficiency and optical noise model",
    },
]


def _json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_history(path: Path, history: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0]))
        writer.writeheader()
        writer.writerows(history)


def _target_matched_error(
    qubits: int,
    t1_seconds: float,
    t2_seconds: float,
    duration_seconds: float,
    target_fidelity: float,
) -> tuple[Any, dict[str, float]]:
    from qiskit.quantum_info import average_gate_fidelity
    from qiskit_aer.noise import depolarizing_error, thermal_relaxation_error

    thermal_one = thermal_relaxation_error(
        t1_seconds,
        t2_seconds,
        duration_seconds,
    )
    thermal = thermal_one
    for _ in range(qubits - 1):
        thermal = thermal.tensor(thermal_one)

    thermal_fidelity = float(average_gate_fidelity(thermal.to_quantumchannel()))
    dimension = 1 << qubits
    if target_fidelity >= thermal_fidelity:
        depolarizing_parameter = 0.0
    else:
        depolarizing_parameter = (
            thermal_fidelity - target_fidelity
        ) / (thermal_fidelity - 1.0 / dimension)
    depolarizing_parameter = float(np.clip(depolarizing_parameter, 0.0, 1.0))
    depolarizing = depolarizing_error(depolarizing_parameter, qubits)
    combined = depolarizing.compose(thermal)
    combined_fidelity = float(average_gate_fidelity(combined.to_quantumchannel()))
    return combined, {
        "target_fidelity": target_fidelity,
        "thermal_only_fidelity": thermal_fidelity,
        "residual_depolarizing_parameter": depolarizing_parameter,
        "combined_fidelity": combined_fidelity,
        "effective_duration_seconds": duration_seconds,
    }


def build_qubit_noise_model(profile: QubitHardwareProfile) -> tuple[Any, dict[str, Any]]:
    from qiskit_aer.noise import NoiseModel

    one_ratio = profile.compiled_one_qubit_pulses / LOGICAL_ONE_QUBIT_GATES
    two_ratio = profile.compiled_two_qubit_pulses / LOGICAL_TWO_QUBIT_GATES
    one_target = profile.one_qubit_fidelity**one_ratio
    two_target = profile.two_qubit_fidelity**two_ratio
    one_duration = profile.one_qubit_gate_seconds * one_ratio
    two_duration = profile.two_qubit_gate_seconds * two_ratio

    one_error, one_metadata = _target_matched_error(
        1,
        profile.t1_seconds,
        profile.t2_seconds,
        one_duration,
        one_target,
    )
    two_error, two_metadata = _target_matched_error(
        2,
        profile.t1_seconds,
        profile.t2_seconds,
        two_duration,
        two_target,
    )

    noise_model = NoiseModel()
    noise_model.add_all_qubit_quantum_error(one_error, ["ry", "rz"])
    noise_model.add_all_qubit_quantum_error(two_error, ["rxx", "ryy", "rzz"])
    metadata = {
        "logical_gate_mapping": {
            "logical_1q_gate_count": LOGICAL_ONE_QUBIT_GATES,
            "compiled_physical_1q_pulse_count": profile.compiled_one_qubit_pulses,
            "logical_2q_gate_count": LOGICAL_TWO_QUBIT_GATES,
            "compiled_physical_2q_pulse_count": profile.compiled_two_qubit_pulses,
            "one_qubit_pulses_per_logical_gate": one_ratio,
            "two_qubit_pulses_per_logical_gate": two_ratio,
        },
        "one_qubit_channel": one_metadata,
        "two_qubit_channel": two_metadata,
        "readout_contrast": 2.0 * profile.readout_fidelity - 1.0,
        "channel_components": [
            "amplitude damping from T1",
            "phase damping from T2",
            "residual depolarizing noise matched to published aggregate fidelity",
            "symmetric readout/SPAM attenuation",
            "finite-shot estimator noise",
        ],
    }
    return noise_model, metadata


class QubitFeatureEvaluator:
    def __init__(
        self,
        profile: QubitHardwareProfile,
        measurement_mode: str = "legacy",
        mitigation_regularization: float = 1e-6,
    ) -> None:
        from qiskit.quantum_info import SparsePauliOp

        if measurement_mode not in {"legacy", "raw", "mitigated"}:
            raise ValueError(f"Unsupported measurement mode: {measurement_mode}")
        self.profile = profile
        self.measurement_mode = measurement_mode
        self.circuit, self.data_parameters, self.weight_parameters = (
            build_parameterized_scar_qnn()
        )
        observables = np.empty(N_QUBITS, dtype=object)
        for qubit in range(N_QUBITS):
            observables[qubit] = SparsePauliOp.from_sparse_list(
                [("Z", [qubit], 1.0)],
                num_qubits=N_QUBITS,
            )
        self.observables = observables[None, :]
        self.noise_model, self.noise_metadata = build_qubit_noise_model(profile)
        matrix = symmetric_assignment_matrix(profile.readout_fidelity)
        self.measurement_response = MeasurementResponse(
            np.repeat(matrix[None, :, :], N_QUBITS, axis=0),
            [f"logical_qubit_{qubit}" for qubit in range(N_QUBITS)],
            regularization=mitigation_regularization,
            calibration_note=(
                f"Symmetric assignment matrix from aggregate readout fidelity "
                f"{profile.readout_fidelity:.6f}. Calibration-shot uncertainty "
                "is not included."
            ),
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
                f"Expected {(len(x), SCAR_PARAMETERS)} circuit parameters, got {parameters.shape}"
            )

        bindings = {
            self.data_parameters: np.asarray(x, dtype=float)[:, None, :],
            self.weight_parameters: parameters[:, None, :],
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
        features *= 2.0 * self.profile.readout_fidelity - 1.0
        return np.clip(features, -1.0, 1.0)

    def measurement_metadata(self) -> dict[str, Any]:
        return {
            "mode": self.measurement_mode,
            **self.measurement_response.metadata(),
        }


X8_MESH_EDGES = ((0, 1), (2, 3), (1, 2), (0, 1), (2, 3), (1, 2))


def _mesh_unitary(
    x: np.ndarray,
    parameters: np.ndarray,
    side: int,
) -> np.ndarray:
    batch = len(x)
    if parameters.shape != (batch, 14):
        raise ValueError(f"Expected mesh parameters {(batch, 14)}, got {parameters.shape}")
    unitary = np.repeat(np.eye(4, dtype=complex)[None, :, :], batch, axis=0)

    for index, (left, right) in enumerate(X8_MESH_EDGES):
        data_theta = x[:, (index + (0 if side > 0 else 2)) % N_QUBITS]
        data_phase = x[:, (index + (1 if side > 0 else 3)) % N_QUBITS]
        theta = 0.25 * np.pi + 0.30 * np.tanh(
            parameters[:, index] + 0.55 * side * data_theta
        )
        phase = parameters[:, 6 + index] + 0.45 * data_phase
        cosine = np.cos(theta)
        sine = np.sin(theta)
        phase_positive = np.exp(1j * phase)
        phase_negative = np.conj(phase_positive)

        rows = unitary[:, [left, right], :].copy()
        unitary[:, left, :] = (
            cosine[:, None] * rows[:, 0, :]
            - phase_positive[:, None] * sine[:, None] * rows[:, 1, :]
        )
        unitary[:, right, :] = (
            phase_negative[:, None] * sine[:, None] * rows[:, 0, :]
            + cosine[:, None] * rows[:, 1, :]
        )

    output_phases = np.zeros((batch, 4), dtype=float)
    output_phases[:, 0] = parameters[:, 12] + 0.25 * x[:, 0]
    output_phases[:, 1] = parameters[:, 13] + 0.25 * x[:, 1]
    output_phases[:, 2] = -parameters[:, 12] + 0.25 * x[:, 2]
    output_phases[:, 3] = -parameters[:, 13] + 0.25 * x[:, 3]
    unitary *= np.exp(1j * output_phases)[:, :, None]
    return unitary


class X8FeatureEvaluator:
    def __init__(
        self,
        measurement_mode: str = "legacy",
        mitigation_regularization: float = 1e-6,
    ) -> None:
        if measurement_mode not in {"legacy", "raw", "mitigated"}:
            raise ValueError(f"Unsupported measurement mode: {measurement_mode}")
        self.measurement_mode = measurement_mode
        self.metadata = dict(XANADU_X8)
        self.visibility = 1.0 - 10.0 ** (
            -float(XANADU_X8["beamsplitter_extinction_db"]) / 10.0
        )
        detector_efficiency = float(XANADU_X8["detector_efficiency_lower_bound"])
        pair_detection_fidelity = detector_efficiency**2
        false_positive = 1.0 - math.exp(-float(XANADU_X8["excess_photon_mean"]))
        matrix = assignment_matrix(
            pair_detection_fidelity,
            1.0 - false_positive,
        )
        self.measurement_response = MeasurementResponse(
            np.repeat(matrix[None, :, :], N_QUBITS, axis=0),
            [f"normalized_pair_correlation_{index}" for index in range(N_QUBITS)],
            regularization=mitigation_regularization,
            calibration_note=(
                "Binary coincidence/no-coincidence response induced from the "
                "X8 PNR detector-efficiency lower bound and excess-photon model. "
                "This is not a full photon-number transition matrix."
            ),
        )

    def __call__(
        self,
        x: np.ndarray,
        circuit_parameters: np.ndarray,
        shots: int,
        seed: int,
    ) -> np.ndarray:
        parameters = np.asarray(circuit_parameters, dtype=float)
        if parameters.ndim == 1:
            parameters = np.repeat(parameters[None, :], len(x), axis=0)
        if parameters.shape != (len(x), X8_CIRCUIT_PARAMETERS):
            raise ValueError(
                f"Expected {(len(x), X8_CIRCUIT_PARAMETERS)} parameters, got {parameters.shape}"
            )

        signal = _mesh_unitary(x, parameters[:, :14], side=1)
        idler = _mesh_unitary(x, parameters[:, 14:], side=-1)
        pair_amplitudes = np.einsum("bij,bkj->bik", signal, idler, optimize=True)
        diagonal_pair_probability = np.abs(
            np.diagonal(pair_amplitudes, axis1=1, axis2=2)
        ) ** 2

        r = float(XANADU_X8["squeezing_r"])
        transmission = float(XANADU_X8["total_transmission"])
        excess = float(XANADU_X8["excess_photon_mean"])
        mean_photons = math.sinh(r) ** 2
        pair_covariance_scale = (
            transmission**2
            * mean_photons
            * (mean_photons + 1.0)
            * self.visibility
        )
        marginal_variance = (
            transmission * mean_photons * (transmission * mean_photons + 1.0)
            + excess
        )
        correlation = (
            pair_covariance_scale * diagonal_pair_probability / marginal_variance
        )
        maximum_correlation = pair_covariance_scale / marginal_variance
        calibrated_features = 2.0 * correlation / maximum_correlation - 1.0

        # Loss-corrected correlation estimates have fewer effective samples.
        if self.measurement_mode != "legacy":
            return self.measurement_response.apply(
                calibrated_features,
                shots,
                seed,
                mitigate=self.measurement_mode == "mitigated",
                shot_scale=transmission,
            )
        effective_shots = max(shots * transmission, 4.0)
        standard_error = np.sqrt(
            np.maximum(1.0 - calibrated_features**2, 0.08) / effective_shots
        )
        standard_error *= 1.0 + 5.0 * excess
        rng = np.random.default_rng(seed)
        sampled = calibrated_features + rng.normal(
            0.0,
            standard_error,
            size=calibrated_features.shape,
        )
        return np.clip(sampled, -1.0, 1.0)

    def measurement_metadata(self) -> dict[str, Any]:
        return {
            "mode": self.measurement_mode,
            **self.measurement_response.metadata(),
        }


def classifier_loss(
    features: np.ndarray,
    labels: np.ndarray,
    readout: np.ndarray,
    bias: np.ndarray,
) -> tuple[float, np.ndarray]:
    probabilities = softmax(features @ readout + bias)
    return cross_entropy(probabilities, labels), probabilities


def head_gradient(
    features: np.ndarray,
    labels: np.ndarray,
    readout: np.ndarray,
    bias: np.ndarray,
    weight_decay: float,
) -> np.ndarray:
    probabilities = softmax(features @ readout + bias)
    targets = np.zeros_like(probabilities)
    targets[np.arange(len(labels)), labels] = 1.0
    d_logits = (probabilities - targets) / len(labels)
    readout_gradient = features.T @ d_logits + weight_decay * readout
    bias_gradient = d_logits.sum(axis=0)
    return np.concatenate([readout_gradient.reshape(-1), bias_gradient])


def unpack_head(head: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    readout_count = N_QUBITS * N_CLASSES
    return (
        head[:readout_count].reshape(N_QUBITS, N_CLASSES),
        head[readout_count:],
    )


def model_metrics(
    features: np.ndarray,
    labels: np.ndarray,
    readout: np.ndarray,
    bias: np.ndarray,
) -> dict[str, Any]:
    loss, probabilities = classifier_loss(features, labels, readout, bias)
    prediction = np.argmax(probabilities, axis=1)
    confusion = np.zeros((N_CLASSES, N_CLASSES), dtype=int)
    for actual, predicted in zip(labels, prediction, strict=True):
        confusion[int(actual), int(predicted)] += 1
    return {
        "loss": loss,
        "accuracy": accuracy(probabilities, labels),
        "macro_f1": macro_f1(labels, prediction),
        "confusion": confusion.tolist(),
        "predictions": prediction.tolist(),
    }


FeatureEvaluator = Callable[[np.ndarray, np.ndarray, int, int], np.ndarray]


def train_hardware_model(
    model_key: str,
    split: Any,
    evaluator: FeatureEvaluator,
    epochs: int,
    shots: int,
    final_shots: int,
    seed: int,
    spsa_a: float,
    spsa_c: float,
    head_learning_rate: float,
    weight_decay: float,
    verbose: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rng = np.random.default_rng(seed + 30_000)
    initialized = initialize_qnn(rng)
    circuit = initialized[:SCAR_PARAMETERS].copy()
    readout_end = SCAR_PARAMETERS + N_QUBITS * N_CLASSES
    head = np.concatenate(
        [initialized[SCAR_PARAMETERS:readout_end], initialized[-N_CLASSES:]]
    )
    head_optimizer = Adam.for_parameters(head)

    best_validation_loss = float("inf")
    best_epoch = 0
    best_circuit = circuit.copy()
    best_head = head.copy()
    history: list[dict[str, Any]] = []
    circuit_evaluations = 0
    started = time.perf_counter()

    for epoch in range(epochs):
        gain = spsa_a / (epoch + 1 + 0.1 * epochs) ** 0.602
        perturbation_size = spsa_c / (epoch + 1) ** 0.101
        direction = rng.choice(np.asarray([-1.0, 1.0]), size=SCAR_PARAMETERS)
        plus = circuit + perturbation_size * direction
        minus = circuit - perturbation_size * direction

        train_count = len(split.x_train)
        validation_count = len(split.x_val)
        all_x = np.concatenate([split.x_train, split.x_train, split.x_val], axis=0)
        all_parameters = np.concatenate(
            [
                np.repeat(plus[None, :], train_count, axis=0),
                np.repeat(minus[None, :], train_count, axis=0),
                np.repeat(circuit[None, :], validation_count, axis=0),
            ],
            axis=0,
        )
        features = evaluator(
            all_x,
            all_parameters,
            shots,
            seed + 1000 * (epoch + 1),
        )
        circuit_evaluations += len(all_x)
        plus_features = features[:train_count]
        minus_features = features[train_count : 2 * train_count]
        validation_features = features[2 * train_count :]
        readout, bias = unpack_head(head)
        plus_loss, _ = classifier_loss(plus_features, split.y_train, readout, bias)
        minus_loss, _ = classifier_loss(minus_features, split.y_train, readout, bias)
        validation_loss, validation_probabilities = classifier_loss(
            validation_features,
            split.y_val,
            readout,
            bias,
        )
        midpoint_features = 0.5 * (plus_features + minus_features)
        midpoint_loss, midpoint_probabilities = classifier_loss(
            midpoint_features,
            split.y_train,
            readout,
            bias,
        )

        if validation_loss < best_validation_loss:
            best_validation_loss = validation_loss
            best_epoch = epoch
            best_circuit = circuit.copy()
            best_head = head.copy()

        scalar_gradient = (plus_loss - minus_loss) / (2.0 * perturbation_size)
        circuit_gradient = scalar_gradient * direction + weight_decay * circuit
        circuit -= gain * circuit_gradient
        head_grad = head_gradient(
            midpoint_features,
            split.y_train,
            readout,
            bias,
            weight_decay,
        )
        head = head_optimizer.update(head, head_grad, head_learning_rate)

        row = {
            "model": model_key,
            "epoch": epoch,
            "train_loss": midpoint_loss,
            "train_accuracy": accuracy(midpoint_probabilities, split.y_train),
            "validation_loss": validation_loss,
            "validation_accuracy": accuracy(validation_probabilities, split.y_val),
            "spsa_gain": gain,
            "spsa_perturbation": perturbation_size,
        }
        history.append(row)
        if verbose:
            print(
                f"{model_key}: epoch {epoch + 1:02d}/{epochs}, "
                f"loss={midpoint_loss:.3f}, val_acc={row['validation_accuracy']:.3f}",
                flush=True,
            )

    combined_x = np.concatenate(
        [split.x_train, split.x_val, split.x_test],
        axis=0,
    )
    final_features = evaluator(
        combined_x,
        best_circuit,
        final_shots,
        seed + 900_000,
    )
    circuit_evaluations += len(combined_x)
    training_seconds = time.perf_counter() - started

    train_end = len(split.x_train)
    validation_end = train_end + len(split.x_val)
    best_readout, best_bias = unpack_head(best_head)
    result = {
        "model": model_key,
        "seed": seed,
        "parameters": QNN_PARAMETERS,
        "quantum_parameters": SCAR_PARAMETERS,
        "readout_parameters": READOUT_PARAMETERS,
        "epochs": epochs,
        "shots": shots,
        "final_evaluation_shots": final_shots,
        "best_epoch": best_epoch,
        "training_seconds": training_seconds,
        "sample_circuit_evaluations": circuit_evaluations,
        "pca_explained": split.pca_explained,
        "train": model_metrics(
            final_features[:train_end],
            split.y_train,
            best_readout,
            best_bias,
        ),
        "validation": model_metrics(
            final_features[train_end:validation_end],
            split.y_val,
            best_readout,
            best_bias,
        ),
        "test": model_metrics(
            final_features[validation_end:],
            split.y_test,
            best_readout,
            best_bias,
        ),
    }
    return result, history


def classical_result(split: Any, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result, history = train_mlp(
        split,
        seed=seed,
        epochs=160,
        learning_rate=0.035,
        weight_decay=1e-4,
    )
    compact = {
        "model": "classical_mlp",
        "seed": seed,
        "parameters": MLP_PARAMETERS,
        "best_epoch": result["best_epoch"],
        "training_seconds": result["training_seconds"],
        "train": {
            "loss": result["train_loss"],
            "accuracy": result["train_accuracy"],
            "macro_f1": result["train_macro_f1"],
            "confusion": result["train_confusion"],
        },
        "validation": {
            "loss": result["validation_loss"],
            "accuracy": result["validation_accuracy"],
            "macro_f1": result["validation_macro_f1"],
            "confusion": result["validation_confusion"],
        },
        "test": {
            "loss": result["test_loss"],
            "accuracy": result["test_accuracy"],
            "macro_f1": result["test_macro_f1"],
            "confusion": result["test_confusion"],
        },
    }
    normalized_history = [
        {
            "model": "classical_mlp",
            "epoch": row["epoch"],
            "train_loss": row["train_loss"],
            "train_accuracy": row["train_accuracy"],
            "validation_loss": row["validation_loss"],
            "validation_accuracy": row["validation_accuracy"],
            "spsa_gain": "",
            "spsa_perturbation": "",
        }
        for row in history
    ]
    return compact, normalized_history


def plot_results(payload: dict[str, Any], history: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = ["rigetti_ankaa3", "ionq_forte", "xanadu_x8", "classical_mlp"]
    labels = ["Rigetti\nAnkaa-3", "IonQ\nForte", "Xanadu\nX8", "MLP\n4-5-3"]
    colors = ["#007C83", "#B91C1C", "#2563EB", "#D97706"]
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
    fig.subplots_adjust(
        left=0.08,
        right=0.97,
        bottom=0.09,
        top=0.88,
        hspace=0.38,
        wspace=0.28,
    )
    fig.suptitle("Wine: QPU-informed noisy training", fontsize=19, weight="bold", y=0.965)
    fig.text(
        0.5,
        0.925,
        "Same split, PCA 13 to 4 and 43 trainable parameters per model",
        ha="center",
        color="#374151",
    )

    accuracy_axis = axes[0, 0]
    x_positions = np.arange(len(order))
    accuracies = [results[key]["test"]["accuracy"] for key in order]
    f1_values = [results[key]["test"]["macro_f1"] for key in order]
    width = 0.34
    accuracy_bars = accuracy_axis.bar(
        x_positions - width / 2,
        accuracies,
        width,
        color=colors,
        label="Accuracy",
    )
    f1_bars = accuracy_axis.bar(
        x_positions + width / 2,
        f1_values,
        width,
        color=colors,
        alpha=0.48,
        label="Macro-F1",
    )
    for bar in [*accuracy_bars, *f1_bars]:
        accuracy_axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.018,
            f"{bar.get_height():.2f}",
            ha="center",
            fontsize=9,
            weight="bold",
        )
    accuracy_axis.set(
        title="Test performance",
        xticks=x_positions,
        xticklabels=labels,
        ylim=(0.0, 1.08),
        ylabel="Score",
    )
    accuracy_axis.grid(axis="y", alpha=0.24)
    accuracy_axis.legend(frameon=False, loc="lower right")

    loss_axis = axes[0, 1]
    for key, color, label in zip(order[:3], colors[:3], labels[:3], strict=True):
        rows = [row for row in history if row["model"] == key]
        loss_axis.plot(
            [row["epoch"] + 1 for row in rows],
            [row["validation_loss"] for row in rows],
            color=color,
            marker="o",
            markersize=3.5,
            linewidth=2,
            label=label.replace("\n", " "),
        )
    loss_axis.set(
        title="Noisy validation loss",
        xlabel="Epoch",
        ylabel="Cross entropy",
    )
    loss_axis.grid(alpha=0.24)
    loss_axis.legend(frameon=False)

    coherence_axis = axes[1, 0]
    coherence_labels = ["Rigetti T1", "Rigetti T2", "IonQ T1", "IonQ T2"]
    coherence_values = [
        RIGETTI.t1_seconds,
        RIGETTI.t2_seconds,
        IONQ.t1_seconds,
        IONQ.t2_seconds,
    ]
    coherence_colors = [colors[0], colors[0], colors[1], colors[1]]
    bars = coherence_axis.bar(coherence_labels, coherence_values, color=coherence_colors)
    coherence_axis.set_yscale("log")
    coherence_axis.set(title="Published coherence scale", ylabel="Seconds (log scale)")
    coherence_axis.grid(axis="y", alpha=0.24, which="both")
    coherence_axis.tick_params(axis="x", rotation=18)
    for bar, value in zip(bars, coherence_values, strict=True):
        coherence_axis.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.45,
            f"{value:.2g} s",
            ha="center",
            fontsize=9,
            weight="bold",
        )

    noise_axis = axes[1, 1]
    categories = ["1Q error", "2Q error", "Readout/SPAM", "Optical loss"]
    rigetti_values = [
        1.0 - RIGETTI.one_qubit_fidelity,
        1.0 - RIGETTI.two_qubit_fidelity,
        1.0 - RIGETTI.readout_fidelity,
        np.nan,
    ]
    ionq_values = [
        1.0 - IONQ.one_qubit_fidelity,
        1.0 - IONQ.two_qubit_fidelity,
        1.0 - IONQ.readout_fidelity,
        np.nan,
    ]
    xanadu_values = [np.nan, np.nan, np.nan, 1.0 - XANADU_X8["total_transmission"]]
    y_positions = np.arange(len(categories))
    noise_axis.scatter(rigetti_values, y_positions, s=90, color=colors[0], label="Rigetti")
    noise_axis.scatter(ionq_values, y_positions, s=90, color=colors[1], label="IonQ")
    noise_axis.scatter(xanadu_values, y_positions, s=90, color=colors[2], label="Xanadu")
    noise_axis.set_xscale("log")
    noise_axis.set(
        title="Dominant published error scales",
        yticks=y_positions,
        yticklabels=categories,
        xlabel="Error / loss probability (log scale)",
        xlim=(1e-4, 1.2),
    )
    noise_axis.grid(axis="x", alpha=0.24, which="both")
    noise_axis.legend(frameon=False, loc="lower right")

    fig.savefig(OUTPUT_PNG, dpi=180)
    fig.savefig(OUTPUT_SVG)
    plt.close(fig)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    results = payload["results"]
    rigetti = results["rigetti_ankaa3"]
    ionq = results["ionq_forte"]
    xanadu = results["xanadu_x8"]
    mlp = results["classical_mlp"]
    winner_key = max(results, key=lambda key: results[key]["test"]["accuracy"])
    winner_names = {
        "rigetti_ankaa3": "Rigetti Ankaa-3",
        "ionq_forte": "IonQ Forte",
        "xanadu_x8": "Xanadu X8",
        "classical_mlp": "klasyczne MLP",
    }

    lines = [
        "# Wine na symulowanych QPU: Rigetti, IonQ i Xanadu",
        "",
        "## Najwazniejszy wynik",
        "",
        f"Najwyzsza trafnosc testowa w tym pojedynczym, kontrolowanym przebiegu: "
        f"**{winner_names[winner_key]}** (`{results[winner_key]['test']['accuracy']:.3f}`).",
        "",
        "| Model | Parametry | Accuracy | Macro-F1 | Najlepsza epoka |",
        "|---|---:|---:|---:|---:|",
        f"| Rigetti Ankaa-3, noisy SCAR-QNN | {rigetti['parameters']} | "
        f"{rigetti['test']['accuracy']:.3f} | {rigetti['test']['macro_f1']:.3f} | "
        f"{rigetti['best_epoch'] + 1} |",
        f"| IonQ Forte, noisy SCAR-QNN | {ionq['parameters']} | "
        f"{ionq['test']['accuracy']:.3f} | {ionq['test']['macro_f1']:.3f} | "
        f"{ionq['best_epoch'] + 1} |",
        f"| Xanadu X8, photonic QNN | {xanadu['parameters']} | "
        f"{xanadu['test']['accuracy']:.3f} | {xanadu['test']['macro_f1']:.3f} | "
        f"{xanadu['best_epoch'] + 1} |",
        f"| MLP 4-5-3 | {mlp['parameters']} | {mlp['test']['accuracy']:.3f} | "
        f"{mlp['test']['macro_f1']:.3f} | {mlp['best_epoch'] + 1} |",
        "",
        "## Co zostalo zasymulowane",
        "",
        "- Rigetti: kwadratowa topologia Ankaa-3, brak SWAP dla 4-kubitowego pierscienia, "
        "natywne koszty RX/RZ/iSWAP, T1/T2, czas bramek, relaksacja, dephasing, "
        "szum dopasowany do fidelity, odczyt i skonczona liczba strzalow.",
        "- IonQ: pelne polaczenia Forte, GPI/GPI2/ZZ bez SWAP, T1/T2, relaksacja, "
        "dephasing, szum dopasowany do 1Q/2Q fidelity, SPAM i strzaly.",
        "- Xanadu: osiem modow X8, cztery pary two-mode squeezed z r=1, dwa "
        "interferometry SU(4), 15% transmisji, 8 dB efektywnego sciskania, "
        "niedoskonala widzialnosc, PNR, Poisson excess photons i strzaly.",
        "",
        "## Uczciwe ograniczenie",
        "",
        "To jest **lokalny symulator hardware-informed**, a nie cyfrowy blizniak ani "
        "wykonanie na fizycznym QPU. Producenci nie publikuja pelnych, aktualnych "
        "macierzy kalibracji, dryfu, crosstalku dla kazdej pary i rozkladow bledow. "
        "Model wykorzystuje wszystkie znalezione parametry publiczne istotne dla "
        "tego obwodu, a wartosci zastepcze sa oznaczone w JSON-ie jako zalozenia.",
        "",
        "Dla IonQ dokladne biezace czasy bramek sa dostepne w uwierzytelnionym "
        "Characterization API. Dla Ankaa-3 publiczna mediana readoutu nie zostala "
        "znaleziona. Dla X8 jedna zbiorcza wartosc szumu resztkowych fotonow nie "
        "jest podana w glownym artykule. Te trzy pola maja jawne zalozenia wraz z "
        "analiza ich pochodzenia.",
        "",
        "## Protokol",
        "",
        f"- Wine: 178 probek, 13 cech, 3 klasy; split 60/20/20, seed "
        f"`{payload['dataset']['split_seed']}`.",
        f"- Standaryzacja i PCA 13->4 uczone tylko na treningu; zachowana wariancja "
        f"`{payload['dataset']['pca_explained']:.3f}`.",
        f"- Kazdy model ma `{QNN_PARAMETERS}` parametry: 28 kwantowych/fotonicznych "
        "i 15 w klasycznej glowicy 4->3. MLP ma ten sam budzet.",
        "- Profil `validation_tuned_v2` wybrano po sredniej cross-entropy na "
        "walidacji w porownaniu dwoch konfiguracji; metryki testowe nie braly "
        "udzialu w wyborze.",
        f"- Trening QNN: SPSA + Adam, `{payload['training']['epochs']}` epok, "
        f"`{payload['training']['shots']}` strzalow; test: "
        f"`{payload['training']['final_shots']}` strzalow.",
        "- Wynik jest pojedynczym przebiegiem. Nie jest podstawa do twierdzenia o "
        "przewadze kwantowej.",
        "",
        "## Zrodla pierwotne",
        "",
    ]
    for source in payload["sources"]:
        lines.append(
            f"- [{source['title']}]({source['url']}) - {source['used_for']}."
        )
    lines.extend(
        [
            "",
            "## Pliki",
            "",
            f"- Wyniki: `{OUTPUT_JSON.name}`",
            f"- Historia: `{OUTPUT_HISTORY.name}`",
            f"- Wykres: `{OUTPUT_PNG.name}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hardware-informed Wine training for Rigetti, IonQ and Xanadu."
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=64)
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--final-shots", type=int, default=4096)
    parser.add_argument("--spsa-a", type=float, default=0.10)
    parser.add_argument("--spsa-c", type=float, default=0.08)
    parser.add_argument("--head-learning-rate", type=float, default=0.08)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument(
        "--models",
        nargs="+",
        choices=["rigetti_ankaa3", "ionq_forte", "xanadu_x8"],
        default=["rigetti_ankaa3", "ionq_forte", "xanadu_x8"],
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--history", type=Path, default=OUTPUT_HISTORY)
    parser.add_argument("--report", type=Path, default=OUTPUT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    x, y = load_wine()
    split = prepare_split(x, y, args.seed)

    profile_evaluators: dict[str, tuple[FeatureEvaluator, dict[str, Any]]] = {}
    if "rigetti_ankaa3" in args.models:
        rigetti_evaluator = QubitFeatureEvaluator(RIGETTI)
        profile_evaluators["rigetti_ankaa3"] = (
            rigetti_evaluator,
            {
                "profile": asdict(RIGETTI),
                "noise_model": rigetti_evaluator.noise_metadata,
            },
        )
    if "ionq_forte" in args.models:
        ionq_evaluator = QubitFeatureEvaluator(IONQ)
        profile_evaluators["ionq_forte"] = (
            ionq_evaluator,
            {
                "profile": asdict(IONQ),
                "noise_model": ionq_evaluator.noise_metadata,
            },
        )
    if "xanadu_x8" in args.models:
        x8_evaluator = X8FeatureEvaluator()
        profile_evaluators["xanadu_x8"] = (
            x8_evaluator,
            {
                "profile": x8_evaluator.metadata,
                "noise_model": {
                    "components": [
                        "uniform optical transmission loss",
                        "finite squeezing",
                        "beamsplitter visibility from extinction ratio",
                        "Poisson excess photons",
                        "PNR finite-shot correlation-estimation noise",
                    ],
                    "visibility": x8_evaluator.visibility,
                    "t1_t2_applicability": (
                        "T1/T2 are not the physical noise coordinates for flying "
                        "photonic modes; optical loss and mode mismatch are used instead."
                    ),
                },
            },
        )

    results: dict[str, Any] = {}
    all_history: list[dict[str, Any]] = []
    hardware: dict[str, Any] = {}
    for model_key in args.models:
        evaluator, hardware_metadata = profile_evaluators[model_key]
        result, history = train_hardware_model(
            model_key,
            split,
            evaluator,
            epochs=args.epochs,
            shots=args.shots,
            final_shots=args.final_shots,
            seed=args.seed,
            spsa_a=args.spsa_a,
            spsa_c=args.spsa_c,
            head_learning_rate=args.head_learning_rate,
            weight_decay=args.weight_decay,
        )
        results[model_key] = result
        all_history.extend(history)
        hardware[model_key] = hardware_metadata

    mlp_result, mlp_history = classical_result(split, args.seed)
    results["classical_mlp"] = mlp_result
    all_history.extend(mlp_history)

    payload = {
        "execution_status": "completed_local_hardware_informed_simulation",
        "not_physical_qpu_execution": True,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dataset": {
            "name": "UCI Wine",
            "samples": int(len(x)),
            "features": int(x.shape[1]),
            "classes": int(len(np.unique(y))),
            "split_seed": args.seed,
            "train_samples": int(len(split.x_train)),
            "validation_samples": int(len(split.x_val)),
            "test_samples": int(len(split.x_test)),
            "pca_explained": split.pca_explained,
        },
        "training": {
            "hyperparameter_profile": "validation_tuned_v2",
            "selection_basis": (
                "lowest mean validation cross-entropy across Rigetti, IonQ and "
                "Xanadu in a 32-epoch two-profile screening; test metrics were "
                "not used for selection"
            ),
            "previous_profile": {
                "epochs": 12,
                "shots": 256,
                "final_shots": 1024,
                "spsa_a": 0.12,
                "spsa_c": 0.15,
                "head_learning_rate": 0.04,
            },
            "optimizer": "SPSA quantum/photonic circuit + Adam classical head",
            "epochs": args.epochs,
            "shots": args.shots,
            "final_shots": args.final_shots,
            "spsa_a": args.spsa_a,
            "spsa_c": args.spsa_c,
            "head_learning_rate": args.head_learning_rate,
            "weight_decay": args.weight_decay,
            "parameter_budget": QNN_PARAMETERS,
            "quantum_or_photonic_parameters": SCAR_PARAMETERS,
            "classical_head_parameters": READOUT_PARAMETERS,
        },
        "hardware_models": hardware,
        "results": results,
        "sources": SOURCES,
        "limitations": [
            "No model is a calibration-identical digital twin.",
            "Public aggregate medians replace per-qubit and per-edge live calibrations.",
            "Unpublished drift and detailed crosstalk matrices are not reconstructed.",
            "Aer finite-shot behavior uses a Gaussian expectation estimator surrogate.",
            "The X8 model propagates Gaussian second moments and noisy PNR correlations, not full Fock samples.",
            "One seed and one data split are reported.",
        ],
    }
    write_json(args.output, payload)
    write_history(args.history, all_history)
    if set(args.models) == {"rigetti_ankaa3", "ionq_forte", "xanadu_x8"}:
        plot_results(payload, all_history)
        write_report(args.report, payload)

    print(f"Wrote {args.output}")
    print(f"Wrote {args.history}")
    for key, result in results.items():
        print(
            f"{key}: test_acc={result['test']['accuracy']:.3f}, "
            f"macro_f1={result['test']['macro_f1']:.3f}"
        )


if __name__ == "__main__":
    main()
