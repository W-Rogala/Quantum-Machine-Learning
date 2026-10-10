from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .core import fidelity_kernel, state_infidelity
from .estimation import kernel_stages
from .learning import balanced_accuracy, fit_kernel_ridge, predict_kernel_ridge
from .trotter_scaling import make_perfectly_annotated_dataset
from .universal_hamiltonian import (
    PauliTerm,
    evolve_exact_pauli_batch,
    evolve_product_formula_batch,
    hamiltonian_matrix,
    product_formula_sequence,
    slice_schedule,
)


PROTOCOL_SCHEMA = "trotter-scaling-full.protocol.v2"
RESULT_SCHEMA = "trotter-scaling-full.results.v2"
GRID_SCHEMA = "trotter-scaling-full.grid.v2"
SELECTION_SCHEMA = "trotter-scaling-full.outer-results.v2"


@dataclass(frozen=True)
class BudgetTier:
    name: str
    max_transpiled_depth: int
    circuit_shots: int
    two_qubit_gate_shots: int

    def validate(self) -> None:
        if not self.name or min(
            self.max_transpiled_depth,
            self.circuit_shots,
            self.two_qubit_gate_shots,
        ) < 1:
            raise ValueError("Invalid resource budget tier")


@dataclass(frozen=True)
class FullScalingProtocol:
    profile: str
    sample_count: int
    input_dim: int
    qubit_counts: tuple[int, ...]
    trotter_orders: tuple[int, ...]
    delta_min: float
    delta_max: float
    delta_increment: float
    evolution_time: float
    hamiltonian_profiles: tuple[str, ...]
    topologies: tuple[str, ...]
    hamiltonian_seeds: tuple[int, ...]
    random_locality: int
    max_terms: int
    spectral_radii: tuple[float, ...]
    dataset_seed: int
    split_seed: int
    minimum_label_margin: float
    outer_repeats: int
    outer_folds: int
    inner_folds: int
    shot_replicates: int
    budget_tiers: tuple[BudgetTier, ...]
    minimum_shots_per_circuit: int
    regularization_grid: tuple[float, ...]
    shortlist_anchors: tuple[float, ...]
    prediction_weight: float
    state_infidelity_weight: float
    kernel_error_weight: float
    resource_weight: float
    transpiler_seed: int
    permutation_resamples: int
    bootstrap_resamples: int

    def validate(self) -> None:
        if self.profile not in {"smoke", "full"}:
            raise ValueError("profile must be smoke or full")
        if self.sample_count < 18 or self.sample_count % 2:
            raise ValueError("sample_count must be even and at least 18")
        if self.input_dim < 1:
            raise ValueError("input_dim must be positive")
        if tuple(sorted(set(self.qubit_counts))) != self.qubit_counts:
            raise ValueError("qubit_counts must be unique and increasing")
        if min(self.qubit_counts) < 2 or max(self.qubit_counts) > 6:
            raise ValueError("this preregistration supports n in [2, 6]")
        if not self.trotter_orders or set(self.trotter_orders) - {1, 2, 4}:
            raise ValueError("Trotter orders must be drawn from {1, 2, 4}")
        if Decimal(str(self.delta_increment)) != Decimal("0.01"):
            raise ValueError("delta_t increment must be exactly 0.01")
        if not 0.0 < self.delta_min <= self.delta_max <= self.evolution_time:
            raise ValueError("invalid delta_t bounds")
        for value in (self.delta_min, self.delta_max):
            scaled = Decimal(str(value)) * 100
            if scaled != scaled.to_integral_value():
                raise ValueError("delta_t bounds must lie on the 0.01 grid")
        expected_profiles = {
            "ising_zz_x_z",
            "random_k_local",
            "spectral_radius_1",
            "spectral_radius_3",
        }
        if set(self.hamiltonian_profiles) - expected_profiles:
            raise ValueError("unknown Hamiltonian profile")
        if set(self.topologies) - {"chain", "ring", "grid", "all_to_all"}:
            raise ValueError("unknown interaction topology")
        if not self.hamiltonian_seeds or len(set(self.hamiltonian_seeds)) != len(
            self.hamiltonian_seeds
        ):
            raise ValueError("Hamiltonian seeds must be unique")
        if self.profile == "full" and len(self.hamiltonian_seeds) < 20:
            raise ValueError("full profile requires at least 20 Hamiltonian seeds")
        if not 1 <= self.random_locality <= min(self.qubit_counts):
            raise ValueError("invalid random locality")
        if self.max_terms < 3:
            raise ValueError("max_terms must be at least three")
        if tuple(self.spectral_radii) != (1.0, 3.0):
            raise ValueError("spectral-radius controls are preregistered at 1 and 3")
        if min(self.outer_repeats, self.outer_folds, self.inner_folds) < 2:
            raise ValueError("nested repeated CV requires at least two folds/repeats")
        if self.shot_replicates < 1 or self.minimum_shots_per_circuit < 1:
            raise ValueError("shot settings must be positive")
        if not self.budget_tiers:
            raise ValueError("at least one budget tier is required")
        for tier in self.budget_tiers:
            tier.validate()
        if len({tier.name for tier in self.budget_tiers}) != len(self.budget_tiers):
            raise ValueError("budget names must be unique")
        if not self.regularization_grid or min(self.regularization_grid) <= 0.0:
            raise ValueError("regularization grid must be positive")
        if any(
            Decimal(str(value)) * 100
            != (Decimal(str(value)) * 100).to_integral_value()
            for value in self.shortlist_anchors
        ):
            raise ValueError("shortlist anchors must lie on the 0.01 grid")
        weights = (
            self.prediction_weight,
            self.state_infidelity_weight,
            self.kernel_error_weight,
            self.resource_weight,
        )
        if any(value < 0.0 for value in weights) or not np.isclose(sum(weights), 1.0):
            raise ValueError("objective weights must be nonnegative and sum to one")
        if min(self.permutation_resamples, self.bootstrap_resamples) < 100:
            raise ValueError("inference resampling counts must be at least 100")

    def delta_grid(self) -> tuple[float, ...]:
        self.validate()
        start = int(Decimal(str(self.delta_min)) * 100)
        stop = int(Decimal(str(self.delta_max)) * 100)
        return tuple(value / 100.0 for value in range(start, stop + 1))


def protocol_for_profile(profile: str) -> FullScalingProtocol:
    common: dict[str, Any] = {
        "input_dim": 3,
        "trotter_orders": (1, 2, 4),
        "delta_increment": 0.01,
        "evolution_time": 1.0,
        "random_locality": 2,
        "spectral_radii": (1.0, 3.0),
        "dataset_seed": 20260917,
        "split_seed": 20260918,
        "minimum_label_margin": 0.20,
        "minimum_shots_per_circuit": 16,
        "regularization_grid": (1e-3, 1e-2, 1e-1),
        "shortlist_anchors": (0.05, 0.10, 0.25, 0.50, 0.75, 1.00),
        "prediction_weight": 0.55,
        "state_infidelity_weight": 0.15,
        "kernel_error_weight": 0.20,
        "resource_weight": 0.10,
        "transpiler_seed": 20260919,
    }
    if profile == "smoke":
        return FullScalingProtocol(
            profile="smoke",
            sample_count=18,
            qubit_counts=(2, 3),
            hamiltonian_profiles=("ising_zz_x_z", "random_k_local"),
            topologies=("chain", "ring"),
            hamiltonian_seeds=(0, 1),
            max_terms=8,
            delta_min=0.50,
            delta_max=1.00,
            outer_repeats=2,
            outer_folds=3,
            inner_folds=2,
            shot_replicates=1,
            budget_tiers=(
                BudgetTier("low", 600, 250_000, 100_000_000),
                BudgetTier("medium", 2_000, 1_000_000, 500_000_000),
            ),
            permutation_resamples=200,
            bootstrap_resamples=200,
            **common,
        )
    if profile == "full":
        return FullScalingProtocol(
            profile="full",
            sample_count=36,
            qubit_counts=(2, 3, 4, 5, 6),
            hamiltonian_profiles=(
                "ising_zz_x_z",
                "random_k_local",
                "spectral_radius_1",
                "spectral_radius_3",
            ),
            topologies=("chain", "ring", "grid", "all_to_all"),
            hamiltonian_seeds=tuple(range(20)),
            max_terms=12,
            delta_min=0.01,
            delta_max=1.00,
            outer_repeats=2,
            outer_folds=3,
            inner_folds=2,
            shot_replicates=2,
            budget_tiers=(
                BudgetTier("low", 600, 250_000, 100_000_000),
                BudgetTier("medium", 2_000, 1_000_000, 500_000_000),
                BudgetTier("high", 6_000, 4_000_000, 2_000_000_000),
            ),
            permutation_resamples=10_000,
            bootstrap_resamples=5_000,
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


def _hash_payload(payload: dict[str, Any], field: str) -> str:
    content = {key: value for key, value in payload.items() if key != field}
    return hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()


def protocol_payload(protocol: FullScalingProtocol) -> dict[str, Any]:
    protocol.validate()
    payload = {
        "schema": PROTOCOL_SCHEMA,
        "status": "frozen",
        "frozen_at": "2026-09-17",
        "study": "preregistered resource-aware scaling of optimal Trotter policy",
        "primary_hypothesis": (
            "The nested-validation-optimal product-formula policy depends on qubit "
            "count and exogenous transpiled-depth/shot/2Q-gate-shot budgets."
        ),
        "null_hypothesis": (
            "After conditioning on Hamiltonian family, topology, seed and outer split, "
            "the selected policy is independent of qubit count and resource tier."
        ),
        "exact_role": "ideal reference only; exact evolution is never a deployable candidate",
        "search_policy": (
            "Every 0.01 grid point receives block-transpiled resource and commutator "
            "screening. Expensive statevector evaluation is restricted to a frozen "
            "union of proxy optima, their +/-0.01 neighbours and fixed anchors."
        ),
        "matrix_publication_policy": (
            "For every Hamiltonian condition and feasible budget, publish raw, "
            "eigenvalue-clipped PSD and shot-thresholded spectral training matrices "
            "for outer repeat 0, fold 0 and shot replicate 0; all repeats retain "
            "scalar spectral diagnostics in outer_results.csv."
        ),
        "transpilation_policy": (
            "Qiskit basis {rz,sx,x,cx}, deterministic layout and seed. One product-"
            "formula slice is transpiled, then composed with frozen slice barriers; "
            "reported candidate depth and gate counts are exact for that compiled policy."
        ),
        "cv_policy": (
            "Two repeated three-fold outer splits, nested two-fold inner selection, "
            "whole candidate tuning and post-selection test measurement charged to one budget."
        ),
        "inference_policy": (
            "Primary multivariate response is separately standardized log(delta_t) and "
            "selected Trotter order. The joint statistic is the squared coefficient norm "
            "for standardized qubit count, log depth budget and their interaction. Use "
            "Freedman-Lane residual permutations within Hamiltonian-profile, topology, "
            "seed and outer-split strata, plus percentile bootstrap clustered by seed."
        ),
        "test_isolation": (
            "Outer-test labels and test kernel blocks are not used until the candidate "
            "and regularization have been selected by inner CV."
        ),
        "protocol": asdict(protocol),
    }
    payload["protocol_hash"] = _hash_payload(payload, "protocol_hash")
    return payload


def freeze_protocol(path: Path, protocol: FullScalingProtocol) -> dict[str, Any]:
    payload = protocol_payload(protocol)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("protocol_hash") != _hash_payload(existing, "protocol_hash"):
            raise ValueError("existing protocol hash is invalid")
        if existing.get("protocol_hash") != payload["protocol_hash"]:
            raise FileExistsError("existing frozen protocol differs from requested protocol")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", "utf-8")
    return payload


def load_protocol(path: Path) -> tuple[FullScalingProtocol, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != PROTOCOL_SCHEMA or payload.get("status") != "frozen":
        raise ValueError("not a frozen full-scaling protocol")
    if payload.get("protocol_hash") != _hash_payload(payload, "protocol_hash"):
        raise ValueError("frozen protocol hash mismatch")
    values = dict(payload["protocol"])
    tuple_fields = (
        "qubit_counts",
        "trotter_orders",
        "hamiltonian_profiles",
        "topologies",
        "hamiltonian_seeds",
        "spectral_radii",
        "regularization_grid",
        "shortlist_anchors",
    )
    for field in tuple_fields:
        values[field] = tuple(values[field])
    values["budget_tiers"] = tuple(BudgetTier(**tier) for tier in values["budget_tiers"])
    protocol = FullScalingProtocol(**values)
    protocol.validate()
    return protocol, payload


def topology_edges(n_qubits: int, topology: str) -> tuple[tuple[int, int], ...]:
    if n_qubits < 2:
        raise ValueError("at least two qubits are required")
    if topology == "chain":
        edges = {(index, index + 1) for index in range(n_qubits - 1)}
    elif topology == "ring":
        edges = {(index, index + 1) for index in range(n_qubits - 1)}
        edges.add((0, n_qubits - 1))
    elif topology == "grid":
        rows = max(1, int(math.floor(math.sqrt(n_qubits))))
        columns = int(math.ceil(n_qubits / rows))
        edges: set[tuple[int, int]] = set()
        for node in range(n_qubits):
            row, column = divmod(node, columns)
            right = row * columns + column + 1
            down = (row + 1) * columns + column
            if column + 1 < columns and right < n_qubits:
                edges.add((node, right))
            if down < n_qubits:
                edges.add((node, down))
    elif topology == "all_to_all":
        edges = set(itertools.combinations(range(n_qubits), 2))
    else:
        raise ValueError(f"Unknown topology: {topology}")
    return tuple(sorted(tuple(sorted(edge)) for edge in edges))


def _stable_rng(seed: int, label: str) -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}:{label}".encode("ascii")).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def _make_terms(
    labels: Iterable[str],
    input_dim: int,
    seed: int,
    static_scale: float = 0.35,
    data_scale: float = 1.0,
) -> tuple[PauliTerm, ...]:
    ordered = tuple(sorted(set(labels), key=lambda value: (sum(c != "I" for c in value), value)))
    if not ordered:
        raise ValueError("Hamiltonian requires at least one Pauli term")
    static_norm = math.sqrt(len(ordered))
    data_norm = math.sqrt(len(ordered) * input_dim)
    terms: list[PauliTerm] = []
    for label in ordered:
        rng = _stable_rng(seed, label)
        terms.append(
            PauliTerm(
                label=label,
                bias=float(static_scale * rng.normal() / static_norm),
                data_weights=tuple(
                    float(value)
                    for value in data_scale * rng.normal(size=input_dim) / data_norm
                ),
            )
        )
    return tuple(terms)


def _ising_labels(n_qubits: int, edges: tuple[tuple[int, int], ...]) -> tuple[str, ...]:
    labels: list[str] = []
    for qubit in range(n_qubits):
        for axis in ("X", "Z"):
            symbols = ["I"] * n_qubits
            symbols[qubit] = axis
            labels.append("".join(symbols))
    for left, right in edges:
        symbols = ["I"] * n_qubits
        symbols[left] = symbols[right] = "Z"
        labels.append("".join(symbols))
    return tuple(labels)


def _random_local_labels(
    n_qubits: int,
    edges: tuple[tuple[int, int], ...],
    max_terms: int,
    seed: int,
) -> tuple[str, ...]:
    labels: list[str] = []
    for qubit in range(n_qubits):
        for axis in ("X", "Y", "Z"):
            symbols = ["I"] * n_qubits
            symbols[qubit] = axis
            labels.append("".join(symbols))
    for left, right in edges:
        for axes in itertools.product(("X", "Y", "Z"), repeat=2):
            symbols = ["I"] * n_qubits
            symbols[left], symbols[right] = axes
            labels.append("".join(symbols))
    labels.sort(
        key=lambda label: hashlib.sha256(f"{seed}:rank:{label}".encode("ascii")).digest()
    )
    selected = labels[: min(max_terms, len(labels))]
    return tuple(sorted(selected, key=lambda value: (sum(c != "I" for c in value), value)))


def _spectral_radius(terms: tuple[PauliTerm, ...], probes: np.ndarray) -> float:
    return max(
        float(np.max(np.abs(np.linalg.eigvalsh(hamiltonian_matrix(terms, probe)))))
        for probe in np.asarray(probes, dtype=float)
    )


def _scale_terms(terms: tuple[PauliTerm, ...], factor: float) -> tuple[PauliTerm, ...]:
    return tuple(
        PauliTerm(
            label=term.label,
            bias=float(factor * term.bias),
            data_weights=tuple(float(factor * value) for value in term.data_weights),
        )
        for term in terms
    )


def generate_terms(
    protocol: FullScalingProtocol,
    n_qubits: int,
    topology: str,
    profile: str,
    seed_index: int,
) -> tuple[PauliTerm, ...]:
    edges = topology_edges(n_qubits, topology)
    seed = 50_000 + 1_009 * seed_index + 97 * n_qubits
    if profile == "ising_zz_x_z":
        return _make_terms(_ising_labels(n_qubits, edges), protocol.input_dim, seed)
    labels = _random_local_labels(n_qubits, edges, protocol.max_terms, seed)
    base = _make_terms(labels, protocol.input_dim, seed)
    if profile == "random_k_local":
        return base
    target = {
        "spectral_radius_1": protocol.spectral_radii[0],
        "spectral_radius_3": protocol.spectral_radii[1],
    }.get(profile)
    if target is None:
        raise ValueError(f"Unknown Hamiltonian profile: {profile}")
    probes = np.vstack(
        (
            np.zeros((1, protocol.input_dim)),
            np.eye(protocol.input_dim),
            -np.eye(protocol.input_dim),
        )
    )
    radius = _spectral_radius(base, probes)
    return _scale_terms(base, target / max(radius, 1e-12))


def _anticommutes(left: str, right: str) -> bool:
    disagreements = sum(
        a != "I" and b != "I" and a != b for a, b in zip(left, right, strict=True)
    )
    return bool(disagreements % 2)


def hamiltonian_diagnostics(
    terms: tuple[PauliTerm, ...], input_dim: int
) -> dict[str, float | int]:
    bounds = np.asarray(
        [abs(term.bias) + sum(abs(value) for value in term.data_weights) for term in terms],
        dtype=float,
    )
    anticommuting = 0
    weighted = 0.0
    for left in range(len(terms)):
        for right in range(left + 1, len(terms)):
            if _anticommutes(terms[left].label, terms[right].label):
                anticommuting += 1
                weighted += 2.0 * bounds[left] * bounds[right]
    probes = np.vstack(
        (np.zeros((1, input_dim)), np.eye(input_dim), -np.eye(input_dim))
    )
    return {
        "term_count": len(terms),
        "anticommuting_pairs": anticommuting,
        "weighted_commutator_l1": float(weighted),
        "normalized_commutator": float(weighted / max(float(bounds.sum() ** 2), 1e-12)),
        "calibration_spectral_radius": _spectral_radius(terms, probes),
    }


def _hamiltonian_payload(
    protocol: FullScalingProtocol,
    n_qubits: int,
    topology: str,
    profile: str,
    seed: int,
    terms: tuple[PauliTerm, ...],
) -> dict[str, Any]:
    payload = {
        "schema": "trotter-scaling-full.hamiltonian.v2",
        "n_qubits": n_qubits,
        "topology": topology,
        "edges": topology_edges(n_qubits, topology),
        "profile": profile,
        "seed_index": seed,
        "terms": [asdict(term) for term in terms],
        "diagnostics": hamiltonian_diagnostics(terms, protocol.input_dim),
    }
    payload["hamiltonian_hash"] = _hash_payload(payload, "hamiltonian_hash")
    return payload


@lru_cache(maxsize=None)
def _transpiled_slice_resources(
    term_labels: tuple[str, ...],
    order: int,
    edges: tuple[tuple[int, int], ...],
    seed: int,
) -> dict[str, Any]:
    from qiskit import QuantumCircuit, transpile
    from qiskit.transpiler import CouplingMap

    n_qubits = len(term_labels[0])
    circuit = QuantumCircuit(n_qubits)
    sequence = product_formula_sequence(len(term_labels), order, 1.0, 1.0)
    for index, duration in sequence:
        label = term_labels[index]
        support = [qubit for qubit, symbol in enumerate(label) if symbol != "I"]
        for qubit in support:
            if label[qubit] == "X":
                circuit.h(qubit)
            elif label[qubit] == "Y":
                circuit.sdg(qubit)
                circuit.h(qubit)
        for control, target in zip(support, support[1:]):
            circuit.cx(control, target)
        circuit.rz(2.0 * float(duration), support[-1])
        for control, target in reversed(tuple(zip(support, support[1:]))):
            circuit.cx(control, target)
        for qubit in support:
            if label[qubit] == "X":
                circuit.h(qubit)
            elif label[qubit] == "Y":
                circuit.h(qubit)
                circuit.s(qubit)
    directed = [(a, b) for a, b in edges for a, b in ((a, b), (b, a))]
    compiled = transpile(
        circuit,
        basis_gates=["rz", "sx", "x", "cx"],
        coupling_map=CouplingMap(couplinglist=directed),
        initial_layout=list(range(n_qubits)),
        optimization_level=1,
        seed_transpiler=seed,
    )
    two_qubit = sum(
        1 for instruction in compiled.data if instruction.operation.num_qubits == 2
    )
    return {
        "order": order,
        "slice_depth": int(compiled.depth()),
        "slice_two_qubit_gates": int(two_qubit),
        "slice_total_gates": int(sum(compiled.count_ops().values())),
        "operation_counts": {
            str(name): int(count) for name, count in compiled.count_ops().items()
        },
        "basis_gates": ["rz", "sx", "x", "cx"],
        "optimization_level": 1,
        "transpiler_seed": seed,
        "method": "qiskit_transpiled_slice_with_frozen_inter_slice_boundaries",
    }


def _resource_row(
    protocol: FullScalingProtocol,
    diagnostics: dict[str, float | int],
    transpiled: dict[str, Any],
    delta_t: float,
) -> dict[str, Any]:
    slices = len(slice_schedule(protocol.evolution_time, delta_t))
    depth = int(transpiled["slice_depth"]) * slices + 1
    two_qubit = int(transpiled["slice_two_qubit_gates"]) * slices
    order = int(transpiled["order"])
    commutator = float(diagnostics["weighted_commutator_l1"])
    error_proxy = float(min(1.0, commutator * protocol.evolution_time * delta_t**order))
    return {
        "order": order,
        "delta_t": f"{delta_t:.2f}",
        "slice_count": slices,
        "transpiled_depth": depth,
        "transpiled_two_qubit_gates": two_qubit,
        "transpiled_total_gates": int(transpiled["slice_total_gates"]) * slices,
        "commutator_error_proxy": error_proxy,
        "transpilation_method": transpiled["method"],
        "numerically_evaluated": False,
        "mean_state_infidelity": "",
        "kernel_relative_frobenius_error": "",
    }


def _condition_key(
    n_qubits: int, topology: str, seed: int, profile: str
) -> tuple[int, str, int, str]:
    return n_qubits, topology, seed, profile


def _candidate_key(row: dict[str, Any]) -> tuple[int, float]:
    return int(row["order"]), float(row["delta_t"])


def _outer_pair_counts(split: dict[str, Any]) -> tuple[int, int]:
    train = len(split["train_indices"])
    test = len(split["test_indices"])
    return train * (train + 1) // 2, train * test


def _candidate_feasible(
    row: dict[str, Any], tier: BudgetTier
) -> bool:
    return int(row["transpiled_depth"]) <= tier.max_transpiled_depth


def _shortlist_rows(
    rows: list[dict[str, Any]],
    protocol: FullScalingProtocol,
) -> list[dict[str, Any]]:
    selected: dict[tuple[int, float], dict[str, Any]] = {}
    by_key = {_candidate_key(row): row for row in rows}
    delta_values = protocol.delta_grid()
    for tier in protocol.budget_tiers:
        for order in protocol.trotter_orders:
            feasible = [
                row
                for row in rows
                if int(row["order"]) == order and _candidate_feasible(row, tier)
            ]
            if not feasible:
                continue
            best = min(
                feasible,
                key=lambda row: (
                    float(row["commutator_error_proxy"])
                    + protocol.resource_weight
                    * int(row["transpiled_depth"])
                    / tier.max_transpiled_depth,
                    int(row["transpiled_depth"]),
                    -float(row["delta_t"]),
                ),
            )
            best_index = delta_values.index(float(best["delta_t"]))
            for index in (best_index - 1, best_index, best_index + 1):
                if 0 <= index < len(delta_values):
                    candidate = by_key[(order, delta_values[index])]
                    if _candidate_feasible(candidate, tier):
                        selected[_candidate_key(candidate)] = candidate
            for anchor in protocol.shortlist_anchors:
                key = (order, float(anchor))
                candidate = by_key.get(key)
                if candidate is not None and _candidate_feasible(candidate, tier):
                    selected[key] = candidate
    # Fixed anchors are numerical references even when no deployment tier can
    # accommodate them. Feasibility is applied later when building candidates.
    for order in protocol.trotter_orders:
        for anchor in protocol.shortlist_anchors:
            candidate = by_key.get((order, float(anchor)))
            if candidate is not None:
                selected[_candidate_key(candidate)] = candidate
    return sorted(
        selected.values(),
        key=lambda row: (int(row["order"]), float(row["delta_t"])),
    )


def _stratified_folds(
    indices: np.ndarray,
    labels: np.ndarray,
    folds: int,
    seed: int,
) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    buckets: list[list[int]] = [[] for _ in range(folds)]
    for label in np.unique(labels[indices]):
        members = indices[labels[indices] == label].copy()
        rng.shuffle(members)
        for position, member in enumerate(members):
            buckets[position % folds].append(int(member))
    for bucket in buckets:
        rng.shuffle(bucket)
    return [np.asarray(bucket, dtype=int) for bucket in buckets]


def make_cv_manifest(
    labels: np.ndarray,
    repeats: int,
    outer_folds: int,
    inner_folds: int,
    seed: int,
) -> dict[str, Any]:
    all_indices = np.arange(len(labels), dtype=int)
    splits: list[dict[str, Any]] = []
    for repeat_index in range(repeats):
        outer = _stratified_folds(
            all_indices, labels, outer_folds, seed + 10_000 * repeat_index
        )
        for fold_index, test_indices in enumerate(outer):
            train_indices = np.setdiff1d(all_indices, test_indices, assume_unique=False)
            inner_validation = _stratified_folds(
                train_indices,
                labels,
                inner_folds,
                seed + 10_000 * repeat_index + 100 * fold_index + 1,
            )
            inner: list[dict[str, list[int]]] = []
            for inner_val in inner_validation:
                inner_train = np.setdiff1d(
                    train_indices, inner_val, assume_unique=False
                )
                inner.append(
                    {
                        "train_indices": inner_train.tolist(),
                        "validation_indices": inner_val.tolist(),
                    }
                )
            splits.append(
                {
                    "repeat": repeat_index,
                    "fold": fold_index,
                    "train_indices": train_indices.tolist(),
                    "test_indices": test_indices.tolist(),
                    "inner_folds": inner,
                }
            )
    payload: dict[str, Any] = {
        "schema": "trotter-scaling-full.cv-splits.v2",
        "split_seed": seed,
        "outer_repeats": repeats,
        "outer_folds": outer_folds,
        "inner_folds": inner_folds,
        "splits": splits,
    }
    payload["split_hash"] = _hash_payload(payload, "split_hash")
    return payload


def _sample_symmetric_kernel(
    ideal: np.ndarray, indices: np.ndarray, shots: int, rng: np.random.Generator
) -> np.ndarray:
    probabilities = np.clip(ideal[np.ix_(indices, indices)], 0.0, 1.0)
    result = np.empty_like(probabilities, dtype=float)
    upper = np.triu_indices(len(indices), k=0)
    sampled = rng.binomial(shots, probabilities[upper]) / shots
    result[upper] = sampled
    result[(upper[1], upper[0])] = sampled
    return result


def _sample_cross_kernel(
    ideal: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    shots: int,
    rng: np.random.Generator,
) -> np.ndarray:
    probabilities = np.clip(ideal[np.ix_(left, right)], 0.0, 1.0)
    return rng.binomial(shots, probabilities) / shots


def _best_regularization_nested(
    kernel: np.ndarray,
    labels: np.ndarray,
    outer_train_indices: np.ndarray,
    inner_folds: list[dict[str, list[int]]],
    grid: tuple[float, ...],
) -> tuple[float, float]:
    position = {int(value): index for index, value in enumerate(outer_train_indices)}
    best_regularization = grid[0]
    best_score = -np.inf
    for regularization in grid:
        scores: list[float] = []
        for split in inner_folds:
            train = np.asarray([position[int(i)] for i in split["train_indices"]])
            validation = np.asarray(
                [position[int(i)] for i in split["validation_indices"]]
            )
            coefficients, classes = fit_kernel_ridge(
                kernel[np.ix_(train, train)], labels[outer_train_indices[train]], regularization
            )
            prediction = predict_kernel_ridge(
                kernel[np.ix_(validation, train)], coefficients, classes
            )
            scores.append(
                balanced_accuracy(
                    labels[outer_train_indices[validation]], prediction, classes
                )
            )
        score = float(np.mean(scores))
        if score > best_score + 1e-12:
            best_regularization = regularization
            best_score = score
    return float(best_regularization), float(best_score)


def _shot_allocation(
    candidates: list[dict[str, Any]],
    train_pairs: int,
    test_pairs: int,
    tier: BudgetTier,
) -> tuple[int, int, int]:
    circuit_count = len(candidates) * train_pairs + test_pairs
    weighted_maps = 2 * (
        train_pairs
        * sum(int(row["transpiled_two_qubit_gates"]) for row in candidates)
        + test_pairs
        * max(int(row["transpiled_two_qubit_gates"]) for row in candidates)
    )
    by_circuits = tier.circuit_shots // max(circuit_count, 1)
    by_two_qubit = (
        tier.two_qubit_gate_shots // weighted_maps if weighted_maps else by_circuits
    )
    shots = int(min(by_circuits, by_two_qubit))
    return shots, circuit_count, weighted_maps


def _condition_rng_seed(*parts: Any) -> int:
    digest = hashlib.sha256(":".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little")


def _evaluate_condition(
    protocol: FullScalingProtocol,
    values: np.ndarray,
    labels: np.ndarray,
    cv_manifest: dict[str, Any],
    n_qubits: int,
    topology: str,
    seed_index: int,
    profile: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, np.ndarray],
]:
    terms = generate_terms(protocol, n_qubits, topology, profile, seed_index)
    hamiltonian = _hamiltonian_payload(
        protocol, n_qubits, topology, profile, seed_index, terms
    )
    diagnostics = hamiltonian["diagnostics"]
    edges = topology_edges(n_qubits, topology)
    transpiled_by_order = {
        order: _transpiled_slice_resources(
            tuple(term.label for term in terms),
            order,
            edges,
            protocol.transpiler_seed,
        )
        for order in protocol.trotter_orders
    }
    grid_rows: list[dict[str, Any]] = []
    for order in protocol.trotter_orders:
        for delta_t in protocol.delta_grid():
            row = {
                "schema": GRID_SCHEMA,
                "n_qubits": n_qubits,
                "topology": topology,
                "hamiltonian_seed": seed_index,
                "hamiltonian_profile": profile,
                "hamiltonian_hash": hamiltonian["hamiltonian_hash"],
                "term_count": diagnostics["term_count"],
                "anticommuting_pairs": diagnostics["anticommuting_pairs"],
                "weighted_commutator_l1": diagnostics["weighted_commutator_l1"],
                "normalized_commutator": diagnostics["normalized_commutator"],
                "calibration_spectral_radius": diagnostics[
                    "calibration_spectral_radius"
                ],
                **_resource_row(
                    protocol, diagnostics, transpiled_by_order[order], delta_t
                ),
            }
            for tier in protocol.budget_tiers:
                row[f"depth_feasible_{tier.name}"] = _candidate_feasible(row, tier)
            grid_rows.append(row)

    shortlist = _shortlist_rows(grid_rows, protocol)
    shortlist_keys = {_candidate_key(row) for row in shortlist}
    exact_states = evolve_exact_pauli_batch(terms, values, protocol.evolution_time)
    exact_kernel = fidelity_kernel(exact_states, exact_states)
    numerical: dict[tuple[int, float], dict[str, Any]] = {}
    for row in shortlist:
        key = _candidate_key(row)
        states = evolve_product_formula_batch(
            terms,
            values,
            protocol.evolution_time,
            key[0],
            key[1],
        )
        kernel = fidelity_kernel(states, states)
        metrics = {
            "states": states,
            "kernel": kernel,
            "mean_state_infidelity": float(
                np.mean(state_infidelity(exact_states, states))
            ),
            "kernel_relative_frobenius_error": float(
                np.linalg.norm(kernel - exact_kernel, "fro")
                / max(float(np.linalg.norm(exact_kernel, "fro")), 1e-12)
            ),
        }
        numerical[key] = metrics
    for row in grid_rows:
        key = _candidate_key(row)
        if key in numerical:
            row["numerically_evaluated"] = True
            row["mean_state_infidelity"] = numerical[key]["mean_state_infidelity"]
            row["kernel_relative_frobenius_error"] = numerical[key][
                "kernel_relative_frobenius_error"
            ]

    selection_rows: list[dict[str, Any]] = []
    matrix_records: dict[str, np.ndarray] = {}
    for split in cv_manifest["splits"]:
        outer_train = np.asarray(split["train_indices"], dtype=int)
        outer_test = np.asarray(split["test_indices"], dtype=int)
        train_pairs, test_pairs = _outer_pair_counts(split)
        exact_regularization, exact_inner_score = _best_regularization_nested(
            exact_kernel[np.ix_(outer_train, outer_train)],
            labels,
            outer_train,
            split["inner_folds"],
            protocol.regularization_grid,
        )
        exact_coefficients, exact_classes = fit_kernel_ridge(
            exact_kernel[np.ix_(outer_train, outer_train)],
            labels[outer_train],
            exact_regularization,
        )
        exact_prediction = predict_kernel_ridge(
            exact_kernel[np.ix_(outer_test, outer_train)],
            exact_coefficients,
            exact_classes,
        )
        exact_test_score = balanced_accuracy(
            labels[outer_test], exact_prediction, exact_classes
        )
        for tier in protocol.budget_tiers:
            candidates = [row for row in shortlist if _candidate_feasible(row, tier)]
            if not candidates:
                continue
            shots, circuit_count, weighted_maps = _shot_allocation(
                candidates, train_pairs, test_pairs, tier
            )
            if shots < protocol.minimum_shots_per_circuit:
                candidates = sorted(
                    candidates,
                    key=lambda row: (
                        float(row["commutator_error_proxy"]),
                        int(row["transpiled_two_qubit_gates"]),
                    ),
                )
                while len(candidates) > 1:
                    shots, circuit_count, weighted_maps = _shot_allocation(
                        candidates, train_pairs, test_pairs, tier
                    )
                    if shots >= protocol.minimum_shots_per_circuit:
                        break
                    candidates.pop()
            if shots < protocol.minimum_shots_per_circuit:
                continue
            for shot_replicate in range(protocol.shot_replicates):
                evaluated: list[dict[str, Any]] = []
                for candidate in candidates:
                    key = _candidate_key(candidate)
                    rng = np.random.default_rng(
                        _condition_rng_seed(
                            n_qubits,
                            topology,
                            seed_index,
                            profile,
                            split["repeat"],
                            split["fold"],
                            tier.name,
                            shot_replicate,
                            key,
                            "train",
                        )
                    )
                    raw_train = _sample_symmetric_kernel(
                        numerical[key]["kernel"], outer_train, shots, rng
                    )
                    regularization, inner_score = _best_regularization_nested(
                        raw_train,
                        labels,
                        outer_train,
                        split["inner_folds"],
                        protocol.regularization_grid,
                    )
                    eigenvalues = np.linalg.eigvalsh(
                        0.5 * (raw_train + raw_train.T)
                    )
                    resource_ratio = max(
                        int(candidate["transpiled_depth"])
                        / tier.max_transpiled_depth,
                        shots * circuit_count / tier.circuit_shots,
                        shots * weighted_maps / tier.two_qubit_gate_shots,
                    )
                    objective = (
                        protocol.prediction_weight * (1.0 - inner_score)
                        + protocol.state_infidelity_weight
                        * min(numerical[key]["mean_state_infidelity"], 1.0)
                        + protocol.kernel_error_weight
                        * min(
                            numerical[key]["kernel_relative_frobenius_error"], 1.0
                        )
                        + protocol.resource_weight * min(resource_ratio, 1.0)
                    )
                    evaluated.append(
                        {
                            "candidate": candidate,
                            "key": key,
                            "raw_train": raw_train,
                            "regularization": regularization,
                            "inner_score": inner_score,
                            "raw_min_eigenvalue": float(eigenvalues[0]),
                            "raw_negative_eigenmass": float(
                                np.abs(eigenvalues[eigenvalues < 0.0]).sum()
                            ),
                            "spectral_threshold": float(
                                max(eigenvalues[-1], 0.0) / math.sqrt(max(shots, 1))
                            ),
                            "resource_ratio": float(resource_ratio),
                            "objective": float(objective),
                        }
                    )
                selected = min(
                    evaluated,
                    key=lambda item: (
                        item["objective"],
                        int(item["candidate"]["transpiled_depth"]),
                        int(item["candidate"]["order"]),
                        -float(item["candidate"]["delta_t"]),
                    ),
                )
                selected_candidate = selected["candidate"]
                selected_key = selected["key"]
                selected_stages = kernel_stages(
                    selected["raw_train"],
                    relative_threshold=max(1.0 / math.sqrt(shots), 1e-12),
                )
                test_rng = np.random.default_rng(
                    _condition_rng_seed(
                        n_qubits,
                        topology,
                        seed_index,
                        profile,
                        split["repeat"],
                        split["fold"],
                        tier.name,
                        shot_replicate,
                        selected_key,
                        "test_after_selection",
                    )
                )
                raw_cross = _sample_cross_kernel(
                    numerical[selected_key]["kernel"],
                    outer_test,
                    outer_train,
                    shots,
                    test_rng,
                )
                coefficients, classes = fit_kernel_ridge(
                    selected["raw_train"],
                    labels[outer_train],
                    selected["regularization"],
                )
                prediction = predict_kernel_ridge(raw_cross, coefficients, classes)
                test_score = balanced_accuracy(labels[outer_test], prediction, classes)
                used_circuit_shots = shots * circuit_count
                selected_gates = int(
                    selected_candidate["transpiled_two_qubit_gates"]
                )
                used_two_qubit_gate_shots = 2 * shots * (
                    train_pairs
                    * sum(
                        int(row["transpiled_two_qubit_gates"])
                        for row in candidates
                    )
                    + test_pairs * selected_gates
                )
                selection_rows.append(
                    {
                        "schema": SELECTION_SCHEMA,
                        "n_qubits": n_qubits,
                        "topology": topology,
                        "hamiltonian_seed": seed_index,
                        "hamiltonian_profile": profile,
                        "hamiltonian_hash": hamiltonian["hamiltonian_hash"],
                        "weighted_commutator_l1": diagnostics[
                            "weighted_commutator_l1"
                        ],
                        "calibration_spectral_radius": diagnostics[
                            "calibration_spectral_radius"
                        ],
                        "outer_repeat": split["repeat"],
                        "outer_fold": split["fold"],
                        "shot_replicate": shot_replicate,
                        "budget_tier": tier.name,
                        "depth_budget": tier.max_transpiled_depth,
                        "circuit_shot_budget": tier.circuit_shots,
                        "two_qubit_gate_shot_budget": tier.two_qubit_gate_shots,
                        "candidate_count": len(candidates),
                        "shots_per_circuit": shots,
                        "circuit_shots_used": used_circuit_shots,
                        "map_executions_used": 2 * used_circuit_shots,
                        "two_qubit_gate_shots_used": used_two_qubit_gate_shots,
                        "order": selected_key[0],
                        "delta_t": f"{selected_key[1]:.2f}",
                        "slice_count": selected_candidate["slice_count"],
                        "transpiled_depth": selected_candidate[
                            "transpiled_depth"
                        ],
                        "transpiled_two_qubit_gates": selected_gates,
                        "mean_state_infidelity": numerical[selected_key][
                            "mean_state_infidelity"
                        ],
                        "kernel_relative_frobenius_error": numerical[selected_key][
                            "kernel_relative_frobenius_error"
                        ],
                        "selected_regularization": selected["regularization"],
                        "inner_balanced_accuracy": selected["inner_score"],
                        "outer_test_balanced_accuracy": test_score,
                        "exact_inner_balanced_accuracy": exact_inner_score,
                        "exact_outer_test_balanced_accuracy": exact_test_score,
                        "objective": selected["objective"],
                        "resource_ratio": selected["resource_ratio"],
                        "raw_train_min_eigenvalue": selected[
                            "raw_min_eigenvalue"
                        ],
                        "raw_train_negative_eigenmass": selected[
                            "raw_negative_eigenmass"
                        ],
                        "spectral_threshold": selected["spectral_threshold"],
                        "selection_used_outer_test": False,
                        "test_kernel_measured_after_selection": True,
                    }
                )
                if (
                    int(split["repeat"]) == 0
                    and int(split["fold"]) == 0
                    and shot_replicate == 0
                ):
                    prefix = tier.name
                    metadata = {
                        "budget_tier": tier.name,
                        "outer_repeat": 0,
                        "outer_fold": 0,
                        "shot_replicate": 0,
                        "order": selected_key[0],
                        "delta_t": selected_key[1],
                        "shots_per_circuit": shots,
                        "outer_train_indices": outer_train.tolist(),
                        "spectral_relative_threshold": 1.0 / math.sqrt(shots),
                        "spectral_absolute_threshold": selected_stages.spectral_threshold,
                    }
                    matrix_records[f"{prefix}__raw_train"] = selected_stages.raw
                    matrix_records[f"{prefix}__psd_train"] = selected_stages.psd
                    matrix_records[f"{prefix}__spectral_train"] = selected_stages.spectral
                    matrix_records[f"{prefix}__measured_diagonal"] = np.diag(
                        selected_stages.raw
                    )
                    matrix_records[f"{prefix}__raw_eigenvalues"] = (
                        selected_stages.raw_eigenvalues
                    )
                    matrix_records[f"{prefix}__psd_eigenvalues"] = (
                        selected_stages.psd_eigenvalues
                    )
                    matrix_records[f"{prefix}__spectral_eigenvalues"] = (
                        selected_stages.spectral_eigenvalues
                    )
                    matrix_records[f"{prefix}__metadata_json"] = np.asarray(
                        _canonical_json(metadata)
                    )
    return grid_rows, selection_rows, hamiltonian, matrix_records


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_task(
    protocol_payload_value: dict[str, Any],
    values: np.ndarray,
    labels: np.ndarray,
    cv_manifest: dict[str, Any],
    output_dir: str,
    task: tuple[int, str, int],
) -> str:
    values_dict = dict(protocol_payload_value["protocol"])
    for field in (
        "qubit_counts",
        "trotter_orders",
        "hamiltonian_profiles",
        "topologies",
        "hamiltonian_seeds",
        "spectral_radii",
        "regularization_grid",
        "shortlist_anchors",
    ):
        values_dict[field] = tuple(values_dict[field])
    values_dict["budget_tiers"] = tuple(
        BudgetTier(**tier) for tier in values_dict["budget_tiers"]
    )
    protocol = FullScalingProtocol(**values_dict)
    n_qubits, topology, seed_index = task
    shard_dir = Path(output_dir) / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    stem = f"n{n_qubits}_{topology}_seed{seed_index:02d}"
    completion_path = shard_dir / f"{stem}.json"
    grid_path = shard_dir / f"{stem}.grid.csv"
    outer_path = shard_dir / f"{stem}.outer.csv"
    hamiltonian_dir = Path(output_dir) / "hamiltonians" / stem
    if completion_path.exists() and grid_path.exists() and outer_path.exists():
        completion = json.loads(completion_path.read_text("utf-8"))
        matrix_hashes = completion.get("matrix_artifact_hashes", {})
        matrices_valid = len(matrix_hashes) == len(protocol.hamiltonian_profiles) and all(
            (Path(output_dir) / relative_path).exists()
            and digest == _file_sha256(Path(output_dir) / relative_path)
            for relative_path, digest in matrix_hashes.items()
        )
        if (
            completion.get("protocol_hash")
            == protocol_payload_value["protocol_hash"]
            and completion.get("grid_sha256") == _file_sha256(grid_path)
            and completion.get("outer_sha256") == _file_sha256(outer_path)
            and matrices_valid
        ):
            return stem
    all_grid: list[dict[str, Any]] = []
    all_outer: list[dict[str, Any]] = []
    matrix_artifact_hashes: dict[str, str] = {}
    hamiltonian_dir.mkdir(parents=True, exist_ok=True)
    for profile in protocol.hamiltonian_profiles:
        grid_rows, outer_rows, hamiltonian, matrix_records = _evaluate_condition(
            protocol,
            values,
            labels,
            cv_manifest,
            n_qubits,
            topology,
            seed_index,
            profile,
        )
        all_grid.extend(grid_rows)
        all_outer.extend(outer_rows)
        (hamiltonian_dir / f"{profile}.json").write_text(
            json.dumps(hamiltonian, indent=2, ensure_ascii=True) + "\n", "utf-8"
        )
        matrix_path = hamiltonian_dir / f"{profile}.kernel_stages.npz"
        np.savez_compressed(matrix_path, **matrix_records)
        relative_matrix_path = matrix_path.relative_to(Path(output_dir)).as_posix()
        matrix_artifact_hashes[relative_matrix_path] = _file_sha256(matrix_path)
    _write_csv(grid_path, all_grid)
    _write_csv(outer_path, all_outer)
    completion = {
        "schema": "trotter-scaling-full.shard.v2",
        "status": "complete",
        "protocol_hash": protocol_payload_value["protocol_hash"],
        "n_qubits": n_qubits,
        "topology": topology,
        "hamiltonian_seed": seed_index,
        "grid_rows": len(all_grid),
        "outer_rows": len(all_outer),
        "grid_sha256": _file_sha256(grid_path),
        "outer_sha256": _file_sha256(outer_path),
        "matrix_artifact_hashes": matrix_artifact_hashes,
    }
    completion["shard_hash"] = _hash_payload(completion, "shard_hash")
    completion_path.write_text(
        json.dumps(completion, indent=2, ensure_ascii=True) + "\n", "utf-8"
    )
    return stem


def _merge_csv(paths: list[Path], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] | None = None
    count = 0
    with output.open("w", encoding="utf-8", newline="") as target:
        writer: csv.DictWriter[str] | None = None
        for path in paths:
            with path.open("r", encoding="utf-8", newline="") as source:
                reader = csv.DictReader(source)
                if fieldnames is None:
                    fieldnames = list(reader.fieldnames or [])
                    writer = csv.DictWriter(target, fieldnames=fieldnames)
                    writer.writeheader()
                elif list(reader.fieldnames or []) != fieldnames:
                    raise ValueError(f"CSV schema mismatch in {path}")
                assert writer is not None
                for row in reader:
                    writer.writerow(row)
                    count += 1
    return count


def _policy_response(rows: list[dict[str, str]]) -> np.ndarray:
    raw = np.column_stack(
        (
            [math.log(float(row["delta_t"])) for row in rows],
            [float(row["order"]) for row in rows],
        )
    )
    return (raw - raw.mean(axis=0)) / np.maximum(raw.std(axis=0), 1e-12)


def _policy_design(
    rows: list[dict[str, str]], *, include_primary: bool
) -> tuple[np.ndarray, list[str]]:
    n_values = np.asarray([float(row["n_qubits"]) for row in rows])
    depth_values = np.log(np.asarray([float(row["depth_budget"]) for row in rows]))
    commutators = np.log1p(
        np.asarray([float(row["weighted_commutator_l1"]) for row in rows])
    )
    radius = np.asarray([float(row["calibration_spectral_radius"]) for row in rows])
    columns = [np.ones(len(rows))]
    names = ["intercept"]
    standardized_values: dict[str, np.ndarray] = {}
    for name, values in (
        ("n_qubits", n_values),
        ("log_depth_budget", depth_values),
        ("log1p_commutator", commutators),
        ("spectral_radius", radius),
    ):
        standardized_values[name] = (values - values.mean()) / max(
            float(values.std()), 1e-12
        )
    if include_primary:
        for name in ("n_qubits", "log_depth_budget"):
            columns.append(standardized_values[name])
            names.append(name)
        columns.append(
            standardized_values["n_qubits"]
            * standardized_values["log_depth_budget"]
        )
        names.append("n_qubits_x_log_depth_budget")
    for name in ("log1p_commutator", "spectral_radius"):
        standardized = standardized_values[name]
        columns.append(standardized)
        names.append(name)
    for field, prefix in (
        ("hamiltonian_profile", "profile"),
        ("topology", "topology"),
    ):
        levels = sorted({row[field] for row in rows})
        for level in levels[1:]:
            columns.append(
                np.asarray([float(row[field] == level) for row in rows], dtype=float)
            )
            names.append(f"{prefix}[{level}]")
    split_levels = sorted(
        {(row["outer_repeat"], row["outer_fold"]) for row in rows}
    )
    for repeat, fold in split_levels[1:]:
        columns.append(
            np.asarray(
                [
                    float(
                        row["outer_repeat"] == repeat
                        and row["outer_fold"] == fold
                    )
                    for row in rows
                ],
                dtype=float,
            )
        )
        names.append(f"outer_split[{repeat},{fold}]")
    return np.column_stack(columns), names


def _fit_policy_model(
    rows: list[dict[str, str]],
    *,
    response: np.ndarray | None = None,
    include_primary: bool = True,
) -> tuple[np.ndarray, np.ndarray, list[str], np.ndarray]:
    observed_response = _policy_response(rows) if response is None else response
    design, names = _policy_design(rows, include_primary=include_primary)
    coefficients = np.linalg.lstsq(design, observed_response, rcond=None)[0]
    fitted = design @ coefficients
    residual = observed_response - fitted
    return coefficients, residual, names, fitted


def analyze_hypothesis(
    rows: list[dict[str, str]],
    protocol: FullScalingProtocol,
    *,
    shot_replicate: int = 0,
) -> dict[str, Any]:
    primary = [
        row for row in rows if int(row["shot_replicate"]) == shot_replicate
    ]
    if not primary:
        raise ValueError(f"No rows for shot replicate {shot_replicate}")
    response = _policy_response(primary)
    design, names = _policy_design(primary, include_primary=True)
    coefficients = np.linalg.lstsq(design, response, rcond=None)[0]
    residual = response - design @ coefficients
    primary_names = (
        "n_qubits",
        "log_depth_budget",
        "n_qubits_x_log_depth_budget",
    )
    primary_indices = [names.index(name) for name in primary_names]
    observed = float(np.sum(coefficients[primary_indices, :] ** 2))
    reduced_design, _ = _policy_design(primary, include_primary=False)
    reduced_coefficients = np.linalg.lstsq(
        reduced_design, response, rcond=None
    )[0]
    reduced_fitted = reduced_design @ reduced_coefficients
    reduced_residual = response - reduced_fitted
    full_pseudoinverse = np.linalg.pinv(design)
    rng = np.random.default_rng(protocol.split_seed + 90_000)
    permuted_statistics: list[float] = []
    strata: dict[tuple[str, ...], list[int]] = {}
    for index, row in enumerate(primary):
        key = (
            row["hamiltonian_profile"],
            row["topology"],
            row["hamiltonian_seed"],
            row["outer_repeat"],
            row["outer_fold"],
        )
        strata.setdefault(key, []).append(index)
    strata_by_size: dict[int, list[list[int]]] = {}
    for indices in strata.values():
        strata_by_size.setdefault(len(indices), []).append(indices)
    strata_arrays = {
        size: np.asarray(groups, dtype=int)
        for size, groups in strata_by_size.items()
    }
    for _ in range(protocol.permutation_resamples):
        permuted_residual = reduced_residual.copy()
        for block in strata_arrays.values():
            order = np.argsort(rng.random(block.shape), axis=1)
            sources = np.take_along_axis(block, order, axis=1)
            permuted_residual[block.ravel()] = reduced_residual[sources.ravel()]
        permuted_response = reduced_fitted + permuted_residual
        permuted_coefficients = full_pseudoinverse @ permuted_response
        permuted_statistics.append(
            float(np.sum(permuted_coefficients[primary_indices, :] ** 2))
        )
    p_value = (1.0 + sum(value >= observed for value in permuted_statistics)) / (
        protocol.permutation_resamples + 1.0
    )
    seed_values = sorted({int(row["hamiltonian_seed"]) for row in primary})
    cluster_crossproducts: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    for seed in seed_values:
        indices = np.asarray(
            [
                index
                for index, row in enumerate(primary)
                if int(row["hamiltonian_seed"]) == seed
            ],
            dtype=int,
        )
        cluster_design = design[indices]
        cluster_response = response[indices]
        cluster_crossproducts[seed] = (
            cluster_design.T @ cluster_design,
            cluster_design.T @ cluster_response,
        )
    bootstrap_coefficients: list[np.ndarray] = []
    for _ in range(protocol.bootstrap_resamples):
        sampled_seeds = rng.choice(seed_values, size=len(seed_values), replace=True)
        counts = {
            seed: int(np.count_nonzero(sampled_seeds == seed)) for seed in seed_values
        }
        xtx = sum(
            count * cluster_crossproducts[seed][0]
            for seed, count in counts.items()
        )
        xty = sum(
            count * cluster_crossproducts[seed][1]
            for seed, count in counts.items()
        )
        estimate = np.linalg.pinv(xtx) @ xty
        bootstrap_coefficients.append(estimate)
    bootstrap = np.asarray(bootstrap_coefficients)
    response_names = ("log_delta_t", "trotter_order")
    intervals = {
        response_name: {
            name: {
                "estimate": float(coefficients[index, response_index]),
                "ci95": [
                    float(np.quantile(bootstrap[:, index, response_index], 0.025)),
                    float(np.quantile(bootstrap[:, index, response_index], 0.975)),
                ],
            }
            for index, name in enumerate(names)
        }
        for response_index, response_name in enumerate(response_names)
    }
    return {
        "schema": "trotter-scaling-full.hypothesis.v2",
        "status": "tested" if protocol.profile == "full" else "descriptive_only",
        "shot_replicate": shot_replicate,
        "primary_statistic": observed,
        "permutation_p_value": float(p_value),
        "permutation_method": "Freedman-Lane residual permutation within preregistered strata",
        "permutation_strata": (
            "hamiltonian_profile, topology, hamiltonian_seed, outer_repeat, outer_fold"
        ),
        "primary_terms": list(primary_names),
        "multivariate_response": list(response_names),
        "response_standardization": "each response centered and scaled over primary rows",
        "permutation_resamples": protocol.permutation_resamples,
        "bootstrap_resamples": protocol.bootstrap_resamples,
        "cluster_level": "hamiltonian_seed",
        "coefficient_intervals": intervals,
        "residual_standard_deviation": {
            name: float(np.std(residual[:, index]))
            for index, name in enumerate(response_names)
        },
        "hypothesis_supported": bool(
            protocol.profile == "full" and p_value < 0.05
        ),
        "causal_claim_allowed": False,
    }


def run_benchmark(
    protocol: FullScalingProtocol,
    manifest: dict[str, Any],
    output_dir: Path,
    max_workers: int,
) -> dict[str, Any]:
    protocol.validate()
    output_dir.mkdir(parents=True, exist_ok=True)
    protocol_path = output_dir / "protocol.json"
    if protocol_path.exists():
        existing = json.loads(protocol_path.read_text("utf-8"))
        if existing.get("protocol_hash") != manifest["protocol_hash"]:
            raise FileExistsError("output directory contains another frozen protocol")
    else:
        protocol_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", "utf-8"
        )
    dataset, dataset_metadata = make_perfectly_annotated_dataset(
        protocol.sample_count,
        protocol.input_dim,
        protocol.dataset_seed,
        protocol.minimum_label_margin,
    )
    dataset_manifest = {
        **dataset_metadata,
        "features": dataset.x.tolist(),
        "labels": dataset.y.tolist(),
    }
    dataset_manifest["manifest_hash"] = _hash_payload(
        dataset_manifest, "manifest_hash"
    )
    (output_dir / "dataset_manifest.json").write_text(
        json.dumps(dataset_manifest, indent=2, ensure_ascii=True) + "\n", "utf-8"
    )
    cv_manifest = make_cv_manifest(
        dataset.y,
        protocol.outer_repeats,
        protocol.outer_folds,
        protocol.inner_folds,
        protocol.split_seed,
    )
    (output_dir / "cv_splits.json").write_text(
        json.dumps(cv_manifest, indent=2, ensure_ascii=True) + "\n", "utf-8"
    )
    tasks = list(
        itertools.product(
            protocol.qubit_counts, protocol.topologies, protocol.hamiltonian_seeds
        )
    )
    if max_workers <= 1:
        for task in tasks:
            _run_task(
                manifest,
                dataset.x,
                dataset.y,
                cv_manifest,
                str(output_dir),
                task,
            )
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _run_task,
                    manifest,
                    dataset.x,
                    dataset.y,
                    cv_manifest,
                    str(output_dir),
                    task,
                ): task
                for task in tasks
            }
            for future in as_completed(futures):
                future.result()
    shard_dir = output_dir / "shards"
    stems = [f"n{n}_{topology}_seed{seed:02d}" for n, topology, seed in tasks]
    grid_paths = [shard_dir / f"{stem}.grid.csv" for stem in stems]
    outer_paths = [shard_dir / f"{stem}.outer.csv" for stem in stems]
    matrix_artifacts: dict[str, str] = {}
    for stem in stems:
        shard_completion = json.loads(
            (shard_dir / f"{stem}.json").read_text(encoding="utf-8")
        )
        matrix_artifacts.update(shard_completion["matrix_artifact_hashes"])
    matrix_manifest = {
        "schema": "trotter-scaling-full.kernel-stage-manifest.v2",
        "selection": "outer_repeat=0, outer_fold=0, shot_replicate=0",
        "artifacts": matrix_artifacts,
    }
    matrix_manifest["manifest_hash"] = _hash_payload(
        matrix_manifest, "manifest_hash"
    )
    matrix_manifest_path = output_dir / "kernel_stage_manifest.json"
    matrix_manifest_path.write_text(
        json.dumps(matrix_manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    grid_output = output_dir / "grid_candidates.csv"
    outer_output = output_dir / "outer_results.csv"
    grid_count = _merge_csv(grid_paths, grid_output)
    outer_count = _merge_csv(outer_paths, outer_output)
    outer_rows = _read_csv(outer_output)
    analysis = analyze_hypothesis(outer_rows, protocol)
    (output_dir / "hypothesis_analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=True) + "\n", "utf-8"
    )
    completion = {
        "schema": RESULT_SCHEMA,
        "status": "complete",
        "protocol_hash": manifest["protocol_hash"],
        "condition_count": len(tasks) * len(protocol.hamiltonian_profiles),
        "task_count": len(tasks),
        "grid_rows": grid_count,
        "outer_rows": outer_count,
        "hamiltonian_seed_count": len(protocol.hamiltonian_seeds),
        "dataset_manifest": "dataset_manifest.json",
        "cv_manifest": "cv_splits.json",
        "grid_table": "grid_candidates.csv",
        "outer_table": "outer_results.csv",
        "hypothesis_analysis": "hypothesis_analysis.json",
        "kernel_stage_manifest": "kernel_stage_manifest.json",
        "kernel_stage_artifact_count": len(matrix_artifacts),
        "test_isolation_verified": all(
            row["selection_used_outer_test"] == "False"
            and row["test_kernel_measured_after_selection"] == "True"
            for row in outer_rows
        ),
        "transpilation_status": (
            "Qiskit-transpiled slice blocks composed under frozen inter-slice boundaries"
        ),
        "artifact_hashes": {
            "grid_candidates.csv": _file_sha256(grid_output),
            "outer_results.csv": _file_sha256(outer_output),
            "dataset_manifest.json": _file_sha256(
                output_dir / "dataset_manifest.json"
            ),
            "cv_splits.json": _file_sha256(output_dir / "cv_splits.json"),
            "hypothesis_analysis.json": _file_sha256(
                output_dir / "hypothesis_analysis.json"
            ),
            "kernel_stage_manifest.json": _file_sha256(matrix_manifest_path),
        },
    }
    completion["result_hash"] = _hash_payload(completion, "result_hash")
    (output_dir / "completion.json").write_text(
        json.dumps(completion, indent=2, ensure_ascii=True) + "\n", "utf-8"
    )
    report = [
        "# Preregistered full Trotter-scaling experiment",
        "",
        f"- Status: `{completion['status']}`.",
        f"- Protocol hash: `{manifest['protocol_hash']}`.",
        f"- Conditions: `{completion['condition_count']}`.",
        f"- Full-grid rows: `{grid_count}`.",
        f"- Nested outer-test rows: `{outer_count}`.",
        f"- Hamiltonian seeds per condition: `{len(protocol.hamiltonian_seeds)}`.",
        "- Search grid: exact 0.01 delta_t increment; orders 1, 2 and 4.",
        "- Exact evolution: ideal reference, never a deployable candidate.",
        "- Costs: transpiled depth, circuit-shots, map executions and 2Q-gate-shots.",
        "- Inference: Hamiltonian-seed cluster bootstrap and frozen permutation test.",
        "",
        "## Primary result",
        "",
        f"- Status: `{analysis['status']}`.",
        f"- Permutation p-value: `{analysis['permutation_p_value']:.6g}`.",
        f"- Hypothesis supported at alpha=0.05: `{analysis['hypothesis_supported']}`.",
        "- The result is resource-conditioned and does not identify an independent causal depth effect.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", "utf-8")
    return completion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preregister and execute the full resource-aware Trotter scaling study"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    freeze.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--protocol", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--max-workers", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "freeze":
        payload = freeze_protocol(args.output, protocol_for_profile(args.profile))
        print(
            json.dumps(
                {"status": "frozen", "protocol_hash": payload["protocol_hash"]},
                indent=2,
            )
        )
        return
    protocol, manifest = load_protocol(args.protocol)
    result = run_benchmark(
        protocol,
        manifest,
        args.output_dir,
        max_workers=max(1, int(args.max_workers)),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
