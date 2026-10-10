from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from .core import fidelity_kernel, state_infidelity
from .data import Dataset, PreparedData, prepare_dataset
from .learning import (
    balanced_accuracy,
    fit_kernel_ridge,
    predict_kernel_ridge,
    select_regularization,
)
from .universal_hamiltonian import (
    PauliTerm,
    UniversalHamiltonianConfig,
    evolve_exact_pauli,
    evolve_product_formula,
    generate_universal_terms,
    product_formula_resources,
)


PROTOCOL_SCHEMA = "trotter-scaling-policy.protocol.v1"
RESULT_SCHEMA = "trotter-scaling-policy.results.v1"


@dataclass(frozen=True)
class TrotterScalingProtocol:
    profile: str
    sample_count: int
    input_dim: int
    qubit_counts: tuple[int, ...]
    depth_budgets: tuple[int, ...]
    max_locality: int | None
    max_terms: int | None
    evolution_time: float
    trotter_orders: tuple[int, ...]
    delta_min: float
    delta_max: float
    delta_increment: float
    coefficient_seed: int
    dataset_seed: int
    split_seed: int
    minimum_label_margin: float
    prediction_weight: float
    state_infidelity_weight: float
    kernel_error_weight: float
    depth_weight: float
    surrogate_pilot_points_per_order: int
    qaoa_shortlist_size: int
    qaoa_gamma_points: int
    qaoa_beta_points: int
    annealing_reads: int
    annealing_sweeps: int
    permutation_resamples: int

    def validate(self) -> None:
        if self.profile not in {"smoke", "full"}:
            raise ValueError("profile must be 'smoke' or 'full'")
        if self.sample_count < 12 or self.sample_count % 2:
            raise ValueError("sample_count must be even and at least 12")
        if self.input_dim < 1:
            raise ValueError("input_dim must be positive")
        if not self.qubit_counts or tuple(sorted(set(self.qubit_counts))) != self.qubit_counts:
            raise ValueError("qubit_counts must be unique and increasing")
        if min(self.qubit_counts) < 1:
            raise ValueError("qubit counts must be positive")
        if not self.depth_budgets or tuple(sorted(set(self.depth_budgets))) != self.depth_budgets:
            raise ValueError("depth_budgets must be unique and increasing")
        if min(self.depth_budgets) < 1:
            raise ValueError("depth budgets must be positive")
        if self.max_locality is not None and not 1 <= self.max_locality <= min(
            self.qubit_counts
        ):
            raise ValueError("max_locality must be None or valid for every qubit count")
        if self.max_terms is not None and self.max_terms < 1:
            raise ValueError("max_terms must be positive when provided")
        if self.evolution_time <= 0.0:
            raise ValueError("evolution_time must be positive")
        if not self.trotter_orders or set(self.trotter_orders) - {1, 2, 4}:
            raise ValueError("Supported Trotter orders are 1, 2, and 4")
        if Decimal(str(self.delta_increment)) != Decimal("0.01"):
            raise ValueError("The preregistered nominal Trotter-step increment must be 0.01")
        if not 0.0 < self.delta_min <= self.delta_max <= self.evolution_time:
            raise ValueError("delta bounds must satisfy 0 < min <= max <= evolution_time")
        for value in (self.delta_min, self.delta_max):
            if Decimal(str(value)) * 100 != (Decimal(str(value)) * 100).to_integral_value():
                raise ValueError("delta bounds must lie on the 0.01 grid")
        if min(self.coefficient_seed, self.dataset_seed, self.split_seed) < 0:
            raise ValueError("seeds cannot be negative")
        if self.minimum_label_margin <= 0.0:
            raise ValueError("minimum_label_margin must be positive")
        weights = (
            self.prediction_weight,
            self.state_infidelity_weight,
            self.kernel_error_weight,
            self.depth_weight,
        )
        if any(value < 0.0 for value in weights) or not np.isclose(sum(weights), 1.0):
            raise ValueError("objective weights must be non-negative and sum to one")
        if self.surrogate_pilot_points_per_order < 3:
            raise ValueError("quadratic surrogate requires at least three pilot points")
        if not 2 <= self.qaoa_shortlist_size <= 12:
            raise ValueError("qaoa_shortlist_size must be in [2, 12]")
        if min(self.qaoa_gamma_points, self.qaoa_beta_points) < 3:
            raise ValueError("QAOA angle grids require at least three points")
        if min(self.annealing_reads, self.annealing_sweeps) < 1:
            raise ValueError("annealing reads and sweeps must be positive")
        if self.permutation_resamples < 100:
            raise ValueError("permutation_resamples must be at least 100")

    def delta_grid(self) -> tuple[float, ...]:
        self.validate()
        start = int(Decimal(str(self.delta_min)) * 100)
        stop = int(Decimal(str(self.delta_max)) * 100)
        return tuple(value / 100.0 for value in range(start, stop + 1))


def protocol_for_profile(profile: str) -> TrotterScalingProtocol:
    common = {
        "input_dim": 3,
        "max_locality": None,
        "evolution_time": 1.0,
        "trotter_orders": (1, 2),
        "delta_increment": 0.01,
        "coefficient_seed": 20260827,
        "dataset_seed": 20260828,
        "split_seed": 20260829,
        "minimum_label_margin": 0.20,
        "prediction_weight": 0.55,
        "state_infidelity_weight": 0.15,
        "kernel_error_weight": 0.20,
        "depth_weight": 0.10,
        "surrogate_pilot_points_per_order": 7,
        "qaoa_shortlist_size": 6,
        "qaoa_gamma_points": 17,
        "qaoa_beta_points": 17,
        "annealing_reads": 64,
        "annealing_sweeps": 200,
    }
    if profile == "smoke":
        return TrotterScalingProtocol(
            profile="smoke",
            sample_count=30,
            qubit_counts=(2, 3),
            depth_budgets=(900, 1_800),
            max_terms=None,
            delta_min=0.10,
            delta_max=1.00,
            permutation_resamples=500,
            **common,
        )
    if profile == "full":
        return TrotterScalingProtocol(
            profile="full",
            sample_count=120,
            qubit_counts=(2, 3, 4, 5, 6),
            depth_budgets=(250, 500, 1_000, 2_000),
            max_terms=64,
            delta_min=0.01,
            delta_max=1.00,
            permutation_resamples=10_000,
            **common,
        )
    raise ValueError(f"Unknown profile: {profile}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "protocol_hash"}
    return hashlib.sha256(_canonical_json(canonical).encode("utf-8")).hexdigest()


def protocol_payload(protocol: TrotterScalingProtocol) -> dict[str, Any]:
    protocol.validate()
    payload: dict[str, Any] = {
        "schema": PROTOCOL_SCHEMA,
        "status": "frozen",
        "study": "resource-conditioned scaling of optimal product-formula policy",
        "hypothesis": (
            "The validation-optimal Trotter policy (order, nominal delta_t) depends "
            "on qubit count and an exogenous serial-depth budget."
        ),
        "null_hypothesis": (
            "After using the same perfectly annotated benchmark and fixed objective, "
            "the selected policy is independent of qubit count and depth budget."
        ),
        "parameter_definition": {
            "order": "discrete product-formula order in {1,2,4}",
            "nominal_delta_t": (
                "continuous grid coordinate with increment 0.01; the final positive "
                "slice is shortened so durations sum exactly to evolution_time"
            ),
        },
        "hamiltonian_family": (
            "real data-dependent k-local Pauli expansion; universal when k=n and "
            "all non-identity Pauli strings are retained"
        ),
        "annotation_policy": {
            "assumption": "labels are deterministic and error-free",
            "implementation": "planted noiseless teacher with a frozen minimum margin",
            "label_noise": 0.0,
        },
        "test_isolation": (
            "candidate metrics and all optimizers use train/validation only; test "
            "kernels are evaluated only after each optimizer has selected a candidate"
        ),
        "optimizers": [
            "exhaustive_grid_reference",
            "quadratic_response_surface",
            "exact_one_hot_qubo_on_surrogate_shortlist",
            "simulated_annealing_on_the_same_qubo",
            "p1_qaoa_statevector_on_the_same_qubo",
        ],
        "protocol": asdict(protocol),
    }
    payload["protocol_hash"] = _payload_hash(payload)
    return payload


def freeze_protocol(path: Path, protocol: TrotterScalingProtocol) -> dict[str, Any]:
    payload = protocol_payload(protocol)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("protocol_hash") != _payload_hash(existing):
            raise ValueError("Existing protocol has an invalid hash")
        if existing.get("protocol_hash") != payload["protocol_hash"]:
            raise FileExistsError("Existing frozen protocol differs from the request")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return payload


def load_protocol(path: Path) -> tuple[TrotterScalingProtocol, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != PROTOCOL_SCHEMA or payload.get("status") != "frozen":
        raise ValueError("Not a frozen Trotter-scaling protocol")
    if payload.get("protocol_hash") != _payload_hash(payload):
        raise ValueError("Frozen protocol hash mismatch")
    values = dict(payload["protocol"])
    values["qubit_counts"] = tuple(values["qubit_counts"])
    values["depth_budgets"] = tuple(values["depth_budgets"])
    values["trotter_orders"] = tuple(values["trotter_orders"])
    protocol = TrotterScalingProtocol(**values)
    protocol.validate()
    return protocol, payload


def _teacher_score(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    score = 1.15 * np.sin(np.pi * x[:, 0])
    for feature in range(1, x.shape[1]):
        sign = -1.0 if feature % 2 else 1.0
        score += sign * (0.55 / feature) * x[:, feature]
        score += (0.30 / feature) * x[:, 0] * x[:, feature]
        score += (0.15 / feature) * np.cos((feature + 1) * np.pi * x[:, feature])
    return score


def make_perfectly_annotated_dataset(
    sample_count: int,
    input_dim: int,
    seed: int,
    minimum_margin: float,
) -> tuple[Dataset, dict[str, Any]]:
    if sample_count < 12 or sample_count % 2:
        raise ValueError("sample_count must be even and at least 12")
    if input_dim < 1 or minimum_margin <= 0.0:
        raise ValueError("Invalid perfect-dataset configuration")
    rng = np.random.default_rng(seed)
    target_per_class = sample_count // 2
    selected: dict[int, list[np.ndarray]] = {0: [], 1: []}
    selected_scores: dict[int, list[float]] = {0: [], 1: []}
    attempts = 0
    while min(len(selected[0]), len(selected[1])) < target_per_class:
        attempts += 1
        if attempts > 10_000:
            raise RuntimeError("Could not generate enough margin-separated samples")
        batch = rng.uniform(-1.0, 1.0, size=(max(64, sample_count * 2), input_dim))
        scores = _teacher_score(batch)
        for row, score in zip(batch, scores, strict=True):
            if abs(float(score)) < minimum_margin:
                continue
            label = int(score > 0.0)
            if len(selected[label]) < target_per_class:
                selected[label].append(row.copy())
                selected_scores[label].append(float(score))

    x = np.vstack((selected[0], selected[1]))
    y = np.concatenate(
        (np.zeros(target_per_class, dtype=int), np.ones(target_per_class, dtype=int))
    )
    scores = np.asarray(selected_scores[0] + selected_scores[1], dtype=float)
    order = rng.permutation(sample_count)
    x = x[order]
    y = y[order]
    scores = scores[order]
    digest = hashlib.sha256(x.tobytes() + y.tobytes()).hexdigest()
    metadata = {
        "schema": "perfectly-annotated-benchmark.v1",
        "teacher": "frozen nonlinear trigonometric-polynomial teacher",
        "label_noise": 0.0,
        "minimum_requested_margin": minimum_margin,
        "minimum_observed_margin": float(np.min(np.abs(scores))),
        "balanced_classes": True,
        "sample_count": sample_count,
        "input_dim": input_dim,
        "seed": seed,
        "dataset_sha256": digest,
    }
    return Dataset("perfect_teacher", x, y), metadata


def _terms_payload(
    config: UniversalHamiltonianConfig,
    terms: tuple[PauliTerm, ...],
) -> dict[str, Any]:
    term_values = [asdict(term) for term in terms]
    payload = {
        "schema": "universal-pauli-hamiltonian.v1",
        "config": asdict(config),
        "term_count": len(terms),
        "terms": term_values,
    }
    payload["hamiltonian_hash"] = hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


def _relative_frobenius(reference: np.ndarray, approximation: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(reference, "fro")), 1e-12)
    return float(np.linalg.norm(reference - approximation, "fro") / denominator)


def _candidate_key(row: dict[str, Any]) -> tuple[int, float]:
    return int(row["order"]), float(row["delta_t"])


def _surrogate_pilot_rows(
    rows: list[dict[str, Any]],
    points_per_order: int,
) -> list[dict[str, Any]]:
    pilots: list[dict[str, Any]] = []
    for order in sorted({int(row["order"]) for row in rows}):
        subset = sorted(
            (row for row in rows if int(row["order"]) == order),
            key=lambda row: float(row["delta_t"]),
        )
        point_count = min(points_per_order, len(subset))
        indices = np.unique(
            np.rint(np.linspace(0, len(subset) - 1, point_count)).astype(int)
        )
        pilots.extend(subset[int(index)] for index in indices)
    return pilots


def _quadratic_predictions(
    rows: list[dict[str, Any]],
    pilot_rows: list[dict[str, Any]],
) -> dict[tuple[int, float], float]:
    predictions: dict[tuple[int, float], float] = {}
    for order in sorted({int(row["order"]) for row in rows}):
        subset = [row for row in rows if int(row["order"]) == order]
        training = [row for row in pilot_rows if int(row["order"]) == order]
        x = np.asarray([float(row["delta_t"]) for row in training], dtype=float)
        y = np.asarray([float(row["objective"]) for row in training], dtype=float)
        target = np.asarray([float(row["delta_t"]) for row in subset], dtype=float)
        if len(training) >= 3 and np.ptp(x) > 1e-12:
            design = np.column_stack((np.ones(len(x)), x, x * x))
            coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
            target_design = np.column_stack(
                (np.ones(len(target)), target, target * target)
            )
            fitted = target_design @ coefficients
        else:
            fitted = np.full(len(subset), float(np.mean(y)))
        for row, value in zip(subset, fitted, strict=True):
            predictions[_candidate_key(row)] = float(value)
    return predictions


def _surrogate_shortlist(
    rows: list[dict[str, Any]],
    predictions: dict[tuple[int, float], float],
    count: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: (
            predictions[_candidate_key(row)],
            int(row["serial_depth_proxy"]),
            int(row["order"]),
            -float(row["delta_t"]),
        ),
    )
    selected: list[dict[str, Any]] = []
    for order in sorted({int(row["order"]) for row in rows}):
        selected.extend([row for row in ranked if int(row["order"]) == order][:2])
    for row in ranked:
        if row not in selected:
            selected.append(row)
        if len(selected) >= count:
            break
    return selected[:count]


def one_hot_qubo_energies(scores: np.ndarray, penalty: float) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or len(values) < 2 or penalty <= 0.0:
        raise ValueError("Invalid one-hot QUBO")
    basis = np.arange(2 ** len(values), dtype=np.uint64)[:, None]
    positions = np.arange(len(values), dtype=np.uint64)[None, :]
    bits = ((basis >> positions) & np.uint64(1)).astype(float)
    energies = bits @ values + penalty * (bits.sum(axis=1) - 1.0) ** 2
    return bits, energies


def one_hot_qubo_payload(scores: np.ndarray, penalty: float) -> dict[str, Any]:
    """Return an upper-triangular QUBO representation without its constant."""

    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or len(values) < 2 or penalty <= 0.0:
        raise ValueError("Invalid one-hot QUBO")
    linear = values - penalty
    quadratic = [
        {"i": i, "j": j, "coefficient": 2.0 * penalty}
        for i in range(len(values))
        for j in range(i + 1, len(values))
    ]
    return {
        "form": "sum_i score_i z_i + penalty * (sum_i z_i - 1)^2",
        "constant": float(penalty),
        "linear": [float(value) for value in linear],
        "quadratic": quadratic,
        "penalty": float(penalty),
    }


def _normalized_scores(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    shifted = values - float(np.min(values))
    span = float(np.ptp(shifted))
    return shifted / span if span > 1e-12 else np.zeros_like(shifted)


def simulated_annealing_one_hot_select(
    scores: np.ndarray,
    reads: int,
    sweeps: int,
    seed: int,
) -> dict[str, Any]:
    """Classical Metropolis baseline for the QUBO exported to annealers."""

    values = _normalized_scores(scores)
    if values.ndim != 1 or len(values) < 2 or min(reads, sweeps) < 1:
        raise ValueError("Invalid simulated-annealing configuration")
    penalty = 2.0
    rng = np.random.default_rng(seed)
    temperatures = np.geomspace(2.0, 0.01, sweeps)
    best_bits: np.ndarray | None = None
    best_energy = np.inf
    feasible_visits = 0

    def energy(bits: np.ndarray) -> float:
        return float(bits @ values + penalty * (float(np.sum(bits)) - 1.0) ** 2)

    for _ in range(reads):
        bits = np.zeros(len(values), dtype=float)
        bits[int(rng.integers(0, len(values)))] = 1.0
        current = energy(bits)
        for temperature in temperatures:
            qubit = int(rng.integers(0, len(values)))
            proposal = bits.copy()
            proposal[qubit] = 1.0 - proposal[qubit]
            candidate = energy(proposal)
            if candidate <= current or rng.random() < np.exp(
                -(candidate - current) / temperature
            ):
                bits = proposal
                current = candidate
            if int(np.sum(bits)) == 1:
                feasible_visits += 1
                if current < best_energy:
                    best_bits = bits.copy()
                    best_energy = current
    if best_bits is None:
        best_bits = np.zeros(len(values), dtype=float)
        best_bits[int(np.argmin(values))] = 1.0
        best_energy = energy(best_bits)
    return {
        "selected_index": int(np.argmax(best_bits)),
        "best_normalized_qubo_energy": float(best_energy),
        "feasible_visits": feasible_visits,
        "reads": reads,
        "sweeps": sweeps,
        "seed": seed,
        "penalty": penalty,
        "execution": "classical_simulated_annealing_not_quantum_annealing",
    }


def _apply_x_mixer(state: np.ndarray, beta: float, n_qubits: int) -> np.ndarray:
    result = np.asarray(state, dtype=np.complex128).copy()
    cosine = np.cos(beta)
    sine = np.sin(beta)
    for qubit in range(n_qubits):
        stride = 1 << qubit
        block = stride << 1
        for start in range(0, len(result), block):
            zero = result[start : start + stride].copy()
            one = result[start + stride : start + block].copy()
            result[start : start + stride] = cosine * zero - 1.0j * sine * one
            result[start + stride : start + block] = cosine * one - 1.0j * sine * zero
    return result


def qaoa_one_hot_select(
    scores: np.ndarray,
    gamma_points: int,
    beta_points: int,
) -> dict[str, Any]:
    """Use a p=1 statevector QAOA arm to select one shortlisted candidate."""

    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("QAOA requires at least two candidate scores")
    normalized = _normalized_scores(values)
    penalty = 2.0
    bits, energies = one_hot_qubo_energies(normalized, penalty)
    scaled_energies = energies / max(float(np.max(np.abs(energies))), 1.0)
    dimension = len(energies)
    initial = np.ones(dimension, dtype=np.complex128) / np.sqrt(dimension)
    best_expected = np.inf
    best_state = initial
    best_gamma = 0.0
    best_beta = 0.0
    for gamma in np.linspace(0.0, 2.0 * np.pi, gamma_points, endpoint=False):
        phased = initial * np.exp(-1.0j * gamma * scaled_energies)
        for beta in np.linspace(0.0, np.pi, beta_points, endpoint=False):
            state = _apply_x_mixer(phased, float(beta), len(values))
            probabilities = np.abs(state) ** 2
            expected = float(probabilities @ scaled_energies)
            if expected < best_expected:
                best_expected = expected
                best_state = state
                best_gamma = float(gamma)
                best_beta = float(beta)
    probabilities = np.abs(best_state) ** 2
    feasible_states = np.flatnonzero(bits.sum(axis=1) == 1.0)
    chosen_state = int(feasible_states[np.argmax(probabilities[feasible_states])])
    chosen_candidate = int(np.argmax(bits[chosen_state]))
    return {
        "selected_index": chosen_candidate,
        "selected_probability": float(probabilities[chosen_state]),
        "feasible_probability": float(probabilities[feasible_states].sum()),
        "expected_scaled_qubo_energy": best_expected,
        "gamma": best_gamma,
        "beta": best_beta,
        "penalty": penalty,
        "qaoa_depth_p": 1,
        "execution": "exact_statevector_simulation_not_qpu",
    }


def _objective(
    protocol: TrotterScalingProtocol,
    validation_accuracy: float,
    mean_infidelity: float,
    kernel_error: float,
    depth_ratio: float,
) -> float:
    return float(
        protocol.prediction_weight * (1.0 - validation_accuracy)
        + protocol.state_infidelity_weight * min(max(mean_infidelity, 0.0), 1.0)
        + protocol.kernel_error_weight * min(max(kernel_error, 0.0), 1.0)
        + protocol.depth_weight * min(max(depth_ratio, 0.0), 1.0)
    )


def _test_accuracy(
    prepared: PreparedData,
    states: np.ndarray,
    regularization: float,
) -> float:
    n_train = len(prepared.x_train)
    n_val = len(prepared.x_val)
    kernel = fidelity_kernel(states, states)
    train_kernel = kernel[:n_train, :n_train]
    test_kernel = kernel[n_train + n_val :, :n_train]
    coefficients, classes = fit_kernel_ridge(
        train_kernel, prepared.y_train, regularization
    )
    prediction = predict_kernel_ridge(test_kernel, coefficients, classes)
    return balanced_accuracy(prepared.y_test, prediction, classes)


def _dependence_analysis(
    selection_rows: list[dict[str, Any]],
    protocol: TrotterScalingProtocol,
) -> dict[str, Any]:
    primary = [row for row in selection_rows if row["optimizer"] == "grid_reference"]
    n_values = np.log2(np.asarray([float(row["n_qubits"]) for row in primary]))
    d_values = np.log2(np.asarray([float(row["depth_budget"]) for row in primary]))
    n_centered = n_values - np.mean(n_values)
    d_centered = d_values - np.mean(d_values)
    design = np.column_stack(
        (np.ones(len(primary)), n_centered, d_centered, n_centered * d_centered)
    )
    fineness = -np.log10(np.asarray([float(row["delta_t"]) for row in primary]))
    order_response = np.log2(np.asarray([float(row["order"]) for row in primary]))
    fineness_coef = np.linalg.lstsq(design, fineness, rcond=None)[0]
    order_coef = np.linalg.lstsq(design, order_response, rcond=None)[0]
    observed = float(np.sum(fineness_coef[1:] ** 2) + np.sum(order_coef[1:] ** 2))
    rng = np.random.default_rng(protocol.split_seed + 99)
    exceed = 0
    for _ in range(protocol.permutation_resamples):
        permuted_fineness = rng.permutation(fineness)
        permuted_order = rng.permutation(order_response)
        f_coef = np.linalg.lstsq(design, permuted_fineness, rcond=None)[0]
        o_coef = np.linalg.lstsq(design, permuted_order, rcond=None)[0]
        statistic = float(np.sum(f_coef[1:] ** 2) + np.sum(o_coef[1:] ** 2))
        exceed += int(statistic >= observed - 1e-15)
    p_value = (exceed + 1) / (protocol.permutation_resamples + 1)
    inferential = len(primary) >= 8 and protocol.profile == "full"
    return {
        "status": "tested" if inferential else "descriptive_only",
        "condition_count": len(primary),
        "fineness_coefficients": {
            "intercept": float(fineness_coef[0]),
            "log2_n_qubits": float(fineness_coef[1]),
            "log2_depth_budget": float(fineness_coef[2]),
            "interaction": float(fineness_coef[3]),
        },
        "order_coefficients": {
            "intercept": float(order_coef[0]),
            "log2_n_qubits": float(order_coef[1]),
            "log2_depth_budget": float(order_coef[2]),
            "interaction": float(order_coef[3]),
        },
        "permutation_statistic": observed,
        "permutation_p_value": p_value,
        "hypothesis_supported": bool(inferential and p_value < 0.05),
        "causal_claim_allowed": False,
        "caveat": (
            "Trotterization itself changes circuit depth. This tests a resource-conditioned "
            "selection policy, not a causal effect of depth independent of the formula."
        ),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty result table")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_benchmark(
    protocol: TrotterScalingProtocol,
    protocol_manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    protocol.validate()
    if protocol_manifest.get("protocol_hash") != _payload_hash(protocol_manifest):
        raise ValueError("Protocol manifest is not authentic")
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset, annotation = make_perfectly_annotated_dataset(
        protocol.sample_count,
        protocol.input_dim,
        protocol.dataset_seed,
        protocol.minimum_label_margin,
    )
    prepared = prepare_dataset(dataset, protocol.input_dim, protocol.split_seed)
    all_x = np.vstack((prepared.x_train, prepared.x_val, prepared.x_test))
    n_train = len(prepared.x_train)
    n_val = len(prepared.x_val)
    maximum_depth = max(protocol.depth_budgets)

    candidate_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    state_cache: dict[tuple[int, int, float], np.ndarray] = {}
    base_rows_by_n: dict[int, list[dict[str, Any]]] = {}

    hamiltonian_dir = output_dir / "hamiltonians"
    hamiltonian_dir.mkdir(parents=True, exist_ok=True)
    optimizer_dir = output_dir / "optimizer_instances"
    optimizer_dir.mkdir(parents=True, exist_ok=True)
    for n_qubits in protocol.qubit_counts:
        config = UniversalHamiltonianConfig(
            n_qubits=n_qubits,
            input_dim=protocol.input_dim,
            max_locality=protocol.max_locality,
            evolution_time=protocol.evolution_time,
            coefficient_seed=protocol.coefficient_seed,
            max_terms=protocol.max_terms,
        )
        terms = generate_universal_terms(config)
        terms_payload = _terms_payload(config, terms)
        (hamiltonian_dir / f"n{n_qubits}.json").write_text(
            json.dumps(terms_payload, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        exact_states = np.vstack(
            [evolve_exact_pauli(terms, row, protocol.evolution_time) for row in all_x]
        )
        exact_kernel = fidelity_kernel(exact_states, exact_states)
        rows_for_n: list[dict[str, Any]] = []
        for order in protocol.trotter_orders:
            for delta_t in protocol.delta_grid():
                resources = product_formula_resources(
                    terms,
                    protocol.evolution_time,
                    order,
                    delta_t,
                )
                base: dict[str, Any] = {
                    "n_qubits": n_qubits,
                    "term_count": len(terms),
                    "order": order,
                    "delta_t": f"{delta_t:.2f}",
                    "slice_count": resources.slice_count,
                    "pauli_exponentials": resources.pauli_exponentials,
                    "single_qubit_rotations": resources.single_qubit_rotations,
                    "two_qubit_gates": resources.two_qubit_gates,
                    "serial_depth_proxy": resources.serial_depth_proxy,
                }
                if resources.serial_depth_proxy <= maximum_depth:
                    states = np.vstack(
                        [
                            evolve_product_formula(
                                terms,
                                row,
                                protocol.evolution_time,
                                order,
                                delta_t,
                            )
                            for row in all_x
                        ]
                    )
                    state_cache[(n_qubits, order, delta_t)] = states
                    kernel = fidelity_kernel(states, states)
                    train_kernel = kernel[:n_train, :n_train]
                    val_kernel = kernel[n_train : n_train + n_val, :n_train]
                    regularization, validation_accuracy = select_regularization(
                        train_kernel,
                        prepared.y_train,
                        val_kernel,
                        prepared.y_val,
                    )
                    infidelity = state_infidelity(exact_states, states)
                    base.update(
                        {
                            "validation_balanced_accuracy": validation_accuracy,
                            "selected_regularization": regularization,
                            "mean_state_infidelity": float(np.mean(infidelity)),
                            "max_state_infidelity": float(np.max(infidelity)),
                            "kernel_relative_frobenius_error": _relative_frobenius(
                                exact_kernel, kernel
                            ),
                        }
                    )
                else:
                    base.update(
                        {
                            "validation_balanced_accuracy": "",
                            "selected_regularization": "",
                            "mean_state_infidelity": "",
                            "max_state_infidelity": "",
                            "kernel_relative_frobenius_error": "",
                        }
                    )
                rows_for_n.append(base)
        base_rows_by_n[n_qubits] = rows_for_n

        for depth_budget in protocol.depth_budgets:
            for base in rows_for_n:
                feasible = int(base["serial_depth_proxy"]) <= depth_budget
                row = {
                    **base,
                    "depth_budget": depth_budget,
                    "feasible": feasible,
                    "depth_ratio": (
                        float(base["serial_depth_proxy"]) / depth_budget if feasible else ""
                    ),
                    "objective": "",
                    "test_metric_exposed": False,
                }
                if feasible:
                    row["objective"] = _objective(
                        protocol,
                        float(base["validation_balanced_accuracy"]),
                        float(base["mean_state_infidelity"]),
                        float(base["kernel_relative_frobenius_error"]),
                        float(row["depth_ratio"]),
                    )
                candidate_rows.append(row)

    test_cache: dict[tuple[int, int, float, float], float] = {}
    for n_qubits in protocol.qubit_counts:
        for depth_budget in protocol.depth_budgets:
            condition = [
                row
                for row in candidate_rows
                if int(row["n_qubits"]) == n_qubits
                and int(row["depth_budget"]) == depth_budget
                and bool(row["feasible"])
            ]
            if len(condition) < 2:
                raise RuntimeError(
                    f"Depth budget {depth_budget} leaves fewer than two candidates for n={n_qubits}"
                )
            grid_best = min(
                condition,
                key=lambda row: (
                    float(row["objective"]),
                    int(row["serial_depth_proxy"]),
                    int(row["order"]),
                    -float(row["delta_t"]),
                ),
            )
            pilot_rows = _surrogate_pilot_rows(
                condition, protocol.surrogate_pilot_points_per_order
            )
            predictions = _quadratic_predictions(condition, pilot_rows)
            quadratic_best = min(
                condition,
                key=lambda row: (
                    predictions[_candidate_key(row)],
                    int(row["serial_depth_proxy"]),
                ),
            )
            shortlist = _surrogate_shortlist(
                condition, predictions, protocol.qaoa_shortlist_size
            )
            exact_qubo_best = min(shortlist, key=lambda row: float(row["objective"]))
            shortlist_scores = np.asarray(
                [float(row["objective"]) for row in shortlist], dtype=float
            )
            annealing = simulated_annealing_one_hot_select(
                shortlist_scores,
                protocol.annealing_reads,
                protocol.annealing_sweeps,
                protocol.split_seed + 1_000 * n_qubits + depth_budget,
            )
            annealing_best = shortlist[int(annealing["selected_index"])]
            qaoa = qaoa_one_hot_select(
                shortlist_scores,
                protocol.qaoa_gamma_points,
                protocol.qaoa_beta_points,
            )
            qaoa_best = shortlist[int(qaoa["selected_index"])]
            optimizer_instance = {
                "schema": "trotter-policy-one-hot-qubo.v1",
                "n_qubits": n_qubits,
                "depth_budget": depth_budget,
                "objective_source": "train_validation_only",
                "surrogate_pilots": [
                    {
                        "order": int(row["order"]),
                        "delta_t": str(row["delta_t"]),
                        "objective": float(row["objective"]),
                    }
                    for row in pilot_rows
                ],
                "variables": [
                    {
                        "index": index,
                        "order": int(row["order"]),
                        "delta_t": str(row["delta_t"]),
                        "objective": float(row["objective"]),
                    }
                    for index, row in enumerate(shortlist)
                ],
                "normalized_scores": [
                    float(value) for value in _normalized_scores(shortlist_scores)
                ],
                "qubo": one_hot_qubo_payload(
                    _normalized_scores(shortlist_scores), penalty=2.0
                ),
                "solver_results": {
                    "simulated_annealing": annealing,
                    "qaoa_p1": qaoa,
                },
                "hardware_status": (
                    "portable QUBO instance only; neither a quantum annealer nor a "
                    "gate-model QPU was executed"
                ),
            }
            optimizer_instance["instance_hash"] = hashlib.sha256(
                _canonical_json(optimizer_instance).encode("utf-8")
            ).hexdigest()
            optimizer_path = optimizer_dir / f"n{n_qubits}_depth{depth_budget}.json"
            optimizer_path.write_text(
                json.dumps(optimizer_instance, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            common_metadata = {
                "optimizer_instance": str(optimizer_path.relative_to(output_dir)),
                "surrogate_pilot_count": len(pilot_rows),
                "surrogate_shortlist_count": len(shortlist),
            }
            arms = (
                ("grid_reference", grid_best, common_metadata),
                (
                    "quadratic_surrogate",
                    quadratic_best,
                    {
                        **common_metadata,
                        "surrogate_predicted_objective": predictions[
                            _candidate_key(quadratic_best)
                        ]
                    },
                ),
                ("exact_shortlist_qubo", exact_qubo_best, common_metadata),
                (
                    "simulated_annealing_shortlist_qubo",
                    annealing_best,
                    {**common_metadata, **annealing},
                ),
                (
                    "qaoa_p1_shortlist_qubo",
                    qaoa_best,
                    {**common_metadata, **qaoa},
                ),
            )
            for optimizer, selected, optimizer_metadata in arms:
                key = (
                    n_qubits,
                    int(selected["order"]),
                    float(selected["delta_t"]),
                    float(selected["selected_regularization"]),
                )
                if key not in test_cache:
                    states = state_cache[(n_qubits, key[1], key[2])]
                    test_cache[key] = _test_accuracy(prepared, states, key[3])
                selection_rows.append(
                    {
                        "n_qubits": n_qubits,
                        "depth_budget": depth_budget,
                        "optimizer": optimizer,
                        "order": int(selected["order"]),
                        "delta_t": selected["delta_t"],
                        "slice_count": int(selected["slice_count"]),
                        "serial_depth_proxy": int(selected["serial_depth_proxy"]),
                        "two_qubit_gates": int(selected["two_qubit_gates"]),
                        "objective": float(selected["objective"]),
                        "objective_regret_vs_grid": float(selected["objective"])
                        - float(grid_best["objective"]),
                        "validation_balanced_accuracy": float(
                            selected["validation_balanced_accuracy"]
                        ),
                        "test_balanced_accuracy": test_cache[key],
                        "selection_used_test": False,
                        "optimizer_metadata": json.dumps(
                            optimizer_metadata, sort_keys=True, ensure_ascii=True
                        ),
                    }
                )

    analysis = _dependence_analysis(selection_rows, protocol)
    _write_csv(output_dir / "candidates.csv", candidate_rows)
    _write_csv(output_dir / "selections.csv", selection_rows)
    (output_dir / "annotation_manifest.json").write_text(
        json.dumps(annotation, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (output_dir / "hypothesis_analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    result = {
        "schema": RESULT_SCHEMA,
        "status": "complete",
        "protocol_hash": protocol_manifest["protocol_hash"],
        "candidate_rows": len(candidate_rows),
        "selection_rows": len(selection_rows),
        "annotation_manifest": "annotation_manifest.json",
        "candidate_table": "candidates.csv",
        "selection_table": "selections.csv",
        "hypothesis_analysis": "hypothesis_analysis.json",
        "qaoa_status": "statevector methodological arm; no QPU execution",
        "annealing_status": (
            "portable QUBO plus classical simulated annealing; no quantum annealer execution"
        ),
        "test_isolation_verified": all(
            not bool(row["selection_used_test"]) for row in selection_rows
        ),
    }
    result["result_hash"] = hashlib.sha256(
        _canonical_json(result).encode("utf-8")
    ).hexdigest()
    (output_dir / "completion.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    report_lines = [
        "# Trotter-scaling framework",
        "",
        f"- Status: `{result['status']}`.",
        f"- Protocol hash: `{result['protocol_hash']}`.",
        f"- Delta grid: `{protocol.delta_min:.2f}` to `{protocol.delta_max:.2f}` with increment `0.01`.",
        "- Labels: deterministic, balanced, zero injected label noise, frozen margin.",
        "- Hamiltonian: real data-dependent k-local Pauli expansion.",
        "- Quadratic surrogate: fitted only to frozen pilot points per Trotter order.",
        "- Annealing: portable one-hot QUBO plus a classical simulated-annealing baseline; no quantum annealer result.",
        "- QAOA: p=1 exact statevector arm on a one-hot QUBO shortlist; not a QPU result.",
        "",
        "## Grid-reference selections",
        "",
        "| n | depth budget | order | delta_t | slices | depth | val BA | test BA |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in selection_rows:
        if row["optimizer"] == "grid_reference":
            report_lines.append(
                f"| {row['n_qubits']} | {row['depth_budget']} | {row['order']} | "
                f"{row['delta_t']} | {row['slice_count']} | {row['serial_depth_proxy']} | "
                f"{row['validation_balanced_accuracy']:.3f} | {row['test_balanced_accuracy']:.3f} |"
            )
    report_lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            f"- Hypothesis status: `{analysis['status']}`; supported: `{analysis['hypothesis_supported']}`.",
            "- The smoke profile is pipeline validation and cannot confirm the hypothesis.",
            "- Circuit depth is partly generated by the Trotter policy itself. Results describe a resource-conditioned policy, not an independent causal depth effect.",
            "- A k=n Hamiltonian is universal but has exponentially many Pauli terms. Any max_terms cap is a declared sparse approximation.",
            "- QAOA selection must be judged by regret against the exhaustive grid reference; it is not evidence of quantum advantage.",
        ]
    )
    (output_dir / "report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimize Trotter policy versus qubit count and depth budget"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze", help="Freeze an immutable protocol")
    freeze.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    freeze.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("run", help="Run a frozen protocol")
    run.add_argument("--protocol", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "freeze":
        payload = freeze_protocol(args.output, protocol_for_profile(args.profile))
        print(json.dumps({"status": "frozen", "protocol_hash": payload["protocol_hash"]}, indent=2))
        return
    protocol, manifest = load_protocol(args.protocol)
    result = run_benchmark(protocol, manifest, args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
