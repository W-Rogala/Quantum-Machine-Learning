"""Leakage-controlled, resource-factorial Trotter scaling experiment.

The v2 result is exploratory.  In particular, this module never calls the
exact-evolution oracle from the candidate selection path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from .core import fidelity_kernel, state_infidelity
from .estimation import kernel_stages
from .learning import balanced_accuracy, fit_kernel_ridge, predict_kernel_ridge
from .trotter_scaling import make_perfectly_annotated_dataset
from .trotter_scaling_full import (
    _best_regularization_nested,
    _condition_rng_seed,
    _outer_pair_counts,
    _sample_cross_kernel,
    _sample_symmetric_kernel,
    generate_terms,
    hamiltonian_diagnostics,
    make_cv_manifest,
    topology_edges,
)
from .universal_hamiltonian import (
    PauliTerm,
    evolve_exact_pauli_batch,
    evolve_product_formula_batch,
    product_formula_sequence,
)


SCHEMA = "trotter-scaling.protocol.v3"
RESULT_SCHEMA = "trotter-scaling.results.v3"
_CLASSICAL_CACHE: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
FROZEN_SOURCE_FILES = (
    "trotter_scaling_v3.py", "trotter_scaling_v3_summary.py",
    "trotter_scaling_full.py", "trotter_scaling.py",
    "universal_hamiltonian.py", "core.py", "learning.py", "estimation.py",
)


def _source_hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        for name in FROZEN_SOURCE_FILES
    }


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


@dataclass(frozen=True)
class V3Protocol:
    profile: str
    sample_count: int
    holdout_count: int
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
    max_terms: int
    spectral_radii: tuple[float, ...]
    dataset_seed: int
    holdout_seed: int
    split_seed: int
    minimum_label_margin: float
    outer_repeats: int
    outer_folds: int
    inner_folds: int
    shot_replicates: int
    depth_budgets: tuple[int, ...]
    shot_budgets: tuple[int, ...]
    two_qubit_gate_shot_budgets: tuple[int, ...]
    minimum_shots_per_circuit: int
    regularization_grid: tuple[float, ...]
    max_candidates: int
    transpiler_seed: int

    def validate(self) -> None:
        if self.profile not in {"smoke", "full"}:
            raise ValueError("unknown profile")
        if self.profile == "full" and len(self.hamiltonian_seeds) < 20:
            raise ValueError("full protocol requires 20 independent Hamiltonian seeds")
        if min(self.sample_count, self.holdout_count) < 12 or self.sample_count % 2 or self.holdout_count % 2:
            raise ValueError("datasets must have even counts of at least 12")
        if self.dataset_seed == self.holdout_seed or set(self.hamiltonian_seeds) & set(range(20)):
            raise ValueError("v3 must use fresh dataset and Hamiltonian seeds")
        if self.trotter_orders != (1, 2, 4) or self.delta_increment != 0.01:
            raise ValueError("orders or 0.01 grid changed")
        if not 0 < self.delta_min <= self.delta_max <= self.evolution_time:
            raise ValueError("invalid delta range")
        if min(*self.depth_budgets, *self.shot_budgets, *self.two_qubit_gate_shot_budgets) < 1:
            raise ValueError("budgets must be positive")
        if self.max_candidates < 3 or self.minimum_shots_per_circuit < 1:
            raise ValueError("invalid selection settings")

    def delta_grid(self) -> tuple[float, ...]:
        return tuple(i / 100 for i in range(round(100 * self.delta_min), round(100 * self.delta_max) + 1))

    def budget_cells(self) -> tuple[dict[str, int], ...]:
        return tuple(
            {"depth": d, "circuit_shots": s, "two_qubit_gate_shots": q}
            for d, s, q in itertools.product(
                self.depth_budgets, self.shot_budgets, self.two_qubit_gate_shot_budgets
            )
        )


def protocol_for_profile(profile: str) -> V3Protocol:
    common = dict(
        input_dim=3,
        trotter_orders=(1, 2, 4),
        delta_min=0.01,
        delta_max=1.0,
        delta_increment=0.01,
        evolution_time=1.0,
        spectral_radii=(1.0, 3.0),
        dataset_seed=20261001,
        holdout_seed=20261002,
        split_seed=20261003,
        minimum_label_margin=0.20,
        outer_repeats=2,
        outer_folds=3,
        inner_folds=2,
        shot_replicates=2,
        minimum_shots_per_circuit=16,
        regularization_grid=(1e-3, 1e-2, 1e-1),
        max_candidates=12,
        transpiler_seed=20261004,
    )
    if profile == "smoke":
        return V3Protocol(
            profile=profile, sample_count=18, holdout_count=18,
            qubit_counts=(2,), hamiltonian_profiles=("ising_zz_x_z",),
            topologies=("chain",), hamiltonian_seeds=(20,), max_terms=8,
            depth_budgets=(300, 900), shot_budgets=(50_000, 200_000),
            two_qubit_gate_shot_budgets=(2_000_000, 8_000_000), **common,
        )
    if profile == "full":
        return V3Protocol(
            profile=profile, sample_count=36, holdout_count=36,
            qubit_counts=(2, 3, 4, 5, 6),
            hamiltonian_profiles=("ising_zz_x_z", "random_k_local", "spectral_radius_1", "spectral_radius_3"),
            topologies=("chain", "ring", "grid", "all_to_all"),
            hamiltonian_seeds=tuple(range(20, 40)), max_terms=12,
            depth_budgets=(600, 2400), shot_budgets=(250_000, 1_000_000),
            two_qubit_gate_shot_budgets=(100_000_000, 1_000_000_000), **common,
        )
    raise ValueError(profile)


def _dataset(protocol: V3Protocol, holdout: bool = False):
    return make_perfectly_annotated_dataset(
        protocol.holdout_count if holdout else protocol.sample_count,
        protocol.input_dim,
        protocol.holdout_seed if holdout else protocol.dataset_seed,
        protocol.minimum_label_margin,
    )


def freeze_protocol(path: Path, protocol: V3Protocol) -> dict[str, Any]:
    protocol.validate()
    if path.exists():
        existing = load_protocol(path)[1]
        if existing["protocol"] != json.loads(json.dumps(asdict(protocol))):
            raise FileExistsError("frozen v3 protocol differs")
        return existing
    development, development_meta = _dataset(protocol)
    holdout, holdout_meta = _dataset(protocol, holdout=True)
    if development_meta["dataset_sha256"] == holdout_meta["dataset_sha256"]:
        raise ValueError("development and holdout are identical")
    manifest = make_cv_manifest(
        development.y, protocol.outer_repeats, protocol.outer_folds,
        protocol.inner_folds, protocol.split_seed,
    )
    payload = {
        "schema": SCHEMA,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_before_v3_analysis",
        "v2_p_value_status": "exploratory_not_confirmation",
        "primary_hypothesis": "Inner-CV-selected Trotter order and step depend on qubit count and independent circuit-depth, circuit-shot and 2Q-gate-shot constraints.",
        "selection_policy": "Cost-only 0.01-grid screening; full-circuit-transpiled shortlist; nested inner-CV balanced accuracy, resource tie-break. No exact evolution or outer-test labels enter selection.",
        "shortlist_policy": "For each order and depth budget, compile cost-only anchors 1.00, 0.75, 0.50, 0.25 and the smallest proxy-feasible 0.01 step plus its +0.01 neighbor. Retain up to four feasible candidates per order (12 total), ordered by step and depth. This is a screened grid, not exhaustive 300-candidate optimization.",
        "holdout_policy": "Fresh independent generated dataset, cryptographic fingerprint frozen now; its values and labels are loaded only after development selection is complete.",
        "inference_policy": "Primary 14 endpoints: seed-cluster mean OLS effects of n, independent depth/shot/2Q limits and their three n interactions, for log(delta_t) and log2(order). Restrict to blocks with all eight budget cells; adjust 14 two-sided percentile seed-bootstrap intervals by Bonferroni at familywise 0.05. Hamiltonian family/topology fixed effects. Twenty seed clusters required. Compatible sets are descriptive after empirical-best selection.",
        "ibm_gate": "Pilot conditions selected and frozen only after v3 development, diagnostics, baselines, full-circuit resource audit and holdout complete; no QPU claim without job IDs.",
        "protocol": asdict(protocol),
        "source_hashes": _source_hashes(),
        "development_sha256": development_meta["dataset_sha256"],
        "holdout_sha256": holdout_meta["dataset_sha256"],
        "cv_manifest": manifest,
    }
    payload["protocol_hash"] = _digest(payload)
    _write_json(path, payload)
    del holdout
    return payload


def load_protocol(path: Path) -> tuple[V3Protocol, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA or payload.get("protocol_hash") != _digest({k: v for k, v in payload.items() if k != "protocol_hash"}):
        raise ValueError("invalid or modified v3 protocol")
    values = dict(payload["protocol"])
    for name in (
        "qubit_counts", "trotter_orders", "hamiltonian_profiles", "topologies",
        "hamiltonian_seeds", "spectral_radii", "depth_budgets", "shot_budgets",
        "two_qubit_gate_shot_budgets", "regularization_grid",
    ):
        values[name] = tuple(values[name])
    protocol = V3Protocol(**values)
    protocol.validate()
    if payload.get("source_hashes") != _source_hashes():
        raise ValueError("v3 source changed after freezing; create a new protocol")
    return protocol, payload


def _logical_circuit(term_labels: tuple[str, ...], order: int, step: float, time: float):
    from qiskit import QuantumCircuit
    from qiskit.circuit import ParameterVector

    circuit = QuantumCircuit(len(term_labels[0]))
    coefficients = ParameterVector("c", len(term_labels))
    circuit.h(range(circuit.num_qubits))
    for index, duration in product_formula_sequence(len(term_labels), order, time, step):
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
        circuit.rz(2 * duration * coefficients[index], support[-1])
        for control, target in reversed(tuple(zip(support, support[1:]))):
            circuit.cx(control, target)
        for qubit in support:
            if label[qubit] == "X":
                circuit.h(qubit)
            elif label[qubit] == "Y":
                circuit.h(qubit)
                circuit.s(qubit)
    return circuit, coefficients


@lru_cache(maxsize=8192)
def full_circuit_resources(
    labels: tuple[str, ...], topology: str, order: int, step: float,
    time: float, seed: int,
) -> dict[str, Any]:
    from qiskit import transpile
    from qiskit.transpiler import CouplingMap

    circuit, _ = _logical_circuit(labels, order, step, time)
    edges = topology_edges(len(labels[0]), topology)
    directed = sorted({pair for a, b in edges for pair in ((a, b), (b, a))})
    compiled = transpile(
        circuit, basis_gates=["rz", "sx", "x", "cx"],
        coupling_map=CouplingMap(couplinglist=directed),
        initial_layout=list(range(circuit.num_qubits)),
        optimization_level=1, seed_transpiler=seed,
    )
    counts = {str(key): int(value) for key, value in compiled.count_ops().items()}
    return {
        "depth": int(compiled.depth()), "two_qubit_gates": sum(
            1 for instruction in compiled.data if instruction.operation.num_qubits == 2
        ),
        "total_gates": len(compiled.data), "operation_counts": counts,
        "method": "qiskit_full_parameterized_circuit_opt1",
    }


def _cost_screen(protocol: V3Protocol, terms: tuple[PauliTerm, ...], topology: str) -> list[dict[str, Any]]:
    labels = tuple(term.label for term in terms)
    compiled: dict[tuple[int, float], dict[str, Any]] = {}
    anchors = (1.0, 0.75, 0.50, 0.25)
    for order in protocol.trotter_orders:
        # This proxy proposes candidates only; every retained depth is measured
        # by transpiling the *whole* parameterized circuit.
        exponential_count = len(product_formula_sequence(len(terms), order, 1.0, 1.0))
        proxy_floor = max(0.01, min(1.0, 2 * exponential_count / max(protocol.depth_budgets)))
        probe_steps = set(anchors)
        for depth in protocol.depth_budgets:
            estimate = max(proxy_floor, min(1.0, 2 * exponential_count / depth))
            grid_step = max(1, min(100, int(np.ceil(100 * estimate))))
            probe_steps.update((grid_step / 100, min(1.0, (grid_step + 1) / 100)))
        for step in sorted(probe_steps):
            if step not in protocol.delta_grid():
                continue
            compiled[(order, step)] = full_circuit_resources(
                labels, topology, order, step, protocol.evolution_time, protocol.transpiler_seed
            )
    return [
        {"order": order, "delta_t": step, **resources}
        for (order, step), resources in sorted(compiled.items())
    ]


def _grid_resource_scan(protocol: V3Protocol, terms: tuple[PauliTerm, ...], compiled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    measured = {(row["order"], row["delta_t"]): row for row in compiled}
    rows = []
    for order in protocol.trotter_orders:
        exponentials_per_slice = len(product_formula_sequence(len(terms), order, 1.0, 1.0))
        for step in protocol.delta_grid():
            resource = measured.get((order, step))
            rows.append({
                "order": order, "delta_t": f"{step:.2f}",
                "proxy_exponentials": int(np.ceil(1 / step) * exponentials_per_slice),
                "selected_for_full_transpilation": resource is not None,
                "full_circuit_depth": "" if resource is None else resource["depth"],
                "full_circuit_two_qubit_gates": "" if resource is None else resource["two_qubit_gates"],
                "grid_interpretation": "cost_screened_not_exhaustive_inner_cv",
            })
    return rows


def _candidate_budget(candidates: list[dict[str, Any]], train_pairs: int, test_pairs: int, cell: dict[str, int]) -> tuple[int, int, int]:
    circuits = len(candidates) * train_pairs + test_pairs
    weighted_maps = 2 * (
        train_pairs * sum(int(row["two_qubit_gates"]) for row in candidates)
        + test_pairs * max(int(row["two_qubit_gates"]) for row in candidates)
    )
    shots = min(cell["circuit_shots"] // circuits, cell["two_qubit_gate_shots"] // max(weighted_maps, 1))
    return int(shots), circuits, weighted_maps


def _feasible_candidates(rows: list[dict[str, Any]], cell: dict[str, int], split: dict[str, Any], protocol: V3Protocol) -> tuple[list[dict[str, Any]], int, int, int]:
    candidates = []
    per_order = max(1, protocol.max_candidates // len(protocol.trotter_orders))
    for order in protocol.trotter_orders:
        feasible = [
            row for row in rows
            if row["order"] == order and row["depth"] <= cell["depth"]
        ]
        feasible.sort(key=lambda row: (row["delta_t"], row["depth"]))
        candidates.extend(feasible[:per_order])
    candidates.sort(key=lambda row: (row["order"], row["delta_t"]))
    train_pairs, test_pairs = _outer_pair_counts(split)
    while candidates:
        shots, circuits, maps = _candidate_budget(candidates, train_pairs, test_pairs, cell)
        if shots >= protocol.minimum_shots_per_circuit:
            return candidates, shots, circuits, maps
        counts = {order: sum(row["order"] == order for row in candidates) for order in protocol.trotter_orders}
        removable = [row for row in candidates if counts[row["order"]] > 1]
        victim = max(removable or candidates, key=lambda row: (row["two_qubit_gates"], row["depth"], -row["delta_t"]))
        candidates.remove(victim)
    return [], 0, 0, 0


def select_policy(
    protocol: V3Protocol, terms: tuple[PauliTerm, ...], values: np.ndarray,
    labels: np.ndarray, split: dict[str, Any], candidates: list[dict[str, Any]],
    shots: int, replicate: int, condition_id: str, cell_id: str,
    training_kernel_cache: dict[tuple[Any, ...], np.ndarray] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray]:
    """Select from inner CV only; oracle exact evolution is forbidden here."""
    train = np.asarray(split["train_indices"], dtype=int)
    evaluated = []
    for candidate in candidates:
        order, step = int(candidate["order"]), float(candidate["delta_t"])
        cache_key = (split["repeat"], split["fold"], order, step)
        if training_kernel_cache is not None and cache_key in training_kernel_cache:
            ideal = training_kernel_cache[cache_key]
        else:
            states = evolve_product_formula_batch(terms, values[train], protocol.evolution_time, order, step)
            ideal = fidelity_kernel(states, states)
            if training_kernel_cache is not None:
                training_kernel_cache[cache_key] = ideal
        rng = np.random.default_rng(_condition_rng_seed(condition_id, cell_id, split["repeat"], split["fold"], replicate, order, step, "inner"))
        raw = _sample_symmetric_kernel(ideal, np.arange(len(train)), shots, rng)
        local_inner = []
        positions = {int(index): local for local, index in enumerate(train)}
        for fold in split["inner_folds"]:
            local_inner.append({
                "train_indices": [positions[int(i)] for i in fold["train_indices"]],
                "validation_indices": [positions[int(i)] for i in fold["validation_indices"]],
            })
        reg, score = _best_regularization_nested(
            raw, labels[train], np.arange(len(train)), local_inner,
            protocol.regularization_grid,
        )
        evaluated.append({"candidate": candidate, "regularization": reg, "inner_ba": score, "raw": raw})
    best = min(evaluated, key=lambda item: (
        -item["inner_ba"], item["candidate"]["depth"],
        item["candidate"]["two_qubit_gates"], item["candidate"]["order"],
        -item["candidate"]["delta_t"],
    ))
    candidate_scores = [
        {"order": x["candidate"]["order"], "delta_t": x["candidate"]["delta_t"],
         "inner_ba": x["inner_ba"], "regularization": x["regularization"]}
        for x in evaluated
    ]
    return {k: v for k, v in best.items() if k != "raw"}, candidate_scores, best["raw"]


def _score_kernel(kernel_train: np.ndarray, kernel_test: np.ndarray, y_train: np.ndarray, y_test: np.ndarray, regularization: float) -> float:
    coefficients, classes = fit_kernel_ridge(kernel_train, y_train, regularization)
    prediction = predict_kernel_ridge(kernel_test, coefficients, classes)
    return balanced_accuracy(y_test, prediction, classes)


def _post_selection_diagnostics(
    protocol: V3Protocol, terms: tuple[PauliTerm, ...], values: np.ndarray,
    labels: np.ndarray, split: dict[str, Any], selected: dict[str, Any],
    raw_train: np.ndarray, shots: int, actual_total_circuit_shots: int,
    condition_id: str, cell_id: str, replicate: int,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    train = np.asarray(split["train_indices"], dtype=int)
    test = np.asarray(split["test_indices"], dtype=int)
    candidate = selected["candidate"]
    order, step = int(candidate["order"]), float(candidate["delta_t"])
    # All exact-evolution calls are strictly downstream of select_policy.
    trotter_states = evolve_product_formula_batch(terms, values, protocol.evolution_time, order, step)
    exact_states = evolve_exact_pauli_batch(terms, values, protocol.evolution_time)
    trotter_kernel = fidelity_kernel(trotter_states, trotter_states)
    exact_kernel = fidelity_kernel(exact_states, exact_states)
    rng = np.random.default_rng(_condition_rng_seed(condition_id, cell_id, split["repeat"], split["fold"], replicate, "test"))
    raw_cross = _sample_cross_kernel(trotter_kernel, test, train, shots, rng)
    trotter_finite = _score_kernel(raw_train, raw_cross, labels[train], labels[test], selected["regularization"])
    trotter_ideal_train = trotter_kernel[np.ix_(train, train)]
    trotter_ideal_cross = trotter_kernel[np.ix_(test, train)]
    trotter_ideal_selected = _score_kernel(trotter_ideal_train, trotter_ideal_cross, labels[train], labels[test], selected["regularization"])
    trotter_ideal_reg, _ = _best_regularization_nested(trotter_ideal_train, labels, train, split["inner_folds"], protocol.regularization_grid)
    trotter_ideal = _score_kernel(trotter_ideal_train, trotter_ideal_cross, labels[train], labels[test], trotter_ideal_reg)
    exact_reg, _ = _best_regularization_nested(exact_kernel[np.ix_(train, train)], labels, train, split["inner_folds"], protocol.regularization_grid)
    exact_ideal = _score_kernel(exact_kernel[np.ix_(train, train)], exact_kernel[np.ix_(test, train)], labels[train], labels[test], exact_reg)
    exact_rng = np.random.default_rng(_condition_rng_seed(condition_id, cell_id, split["repeat"], split["fold"], replicate, "exact"))
    exact_raw_train = _sample_symmetric_kernel(exact_kernel, train, shots, exact_rng)
    exact_raw_cross = _sample_cross_kernel(exact_kernel, test, train, shots, exact_rng)
    exact_finite_reg, _ = _best_regularization_nested(exact_raw_train, labels, train, split["inner_folds"], protocol.regularization_grid)
    exact_matched_circuit = _score_kernel(exact_raw_train, exact_raw_cross, labels[train], labels[test], exact_finite_reg)
    exact_circuits = len(train) * (len(train) + 1) // 2 + len(train) * len(test)
    exact_budget_shots = max(1, actual_total_circuit_shots // exact_circuits)
    exact_budget_train = _sample_symmetric_kernel(exact_kernel, train, exact_budget_shots, exact_rng)
    exact_budget_cross = _sample_cross_kernel(exact_kernel, test, train, exact_budget_shots, exact_rng)
    exact_budget_reg, _ = _best_regularization_nested(exact_budget_train, labels, train, split["inner_folds"], protocol.regularization_grid)
    exact_matched_total = _score_kernel(exact_budget_train, exact_budget_cross, labels[train], labels[test], exact_budget_reg)
    stages = kernel_stages(raw_train, relative_threshold=max(1 / np.sqrt(shots), 1e-12))
    metrics = {
        "trotter_finite_ba": trotter_finite,
        "trotter_noiseless_ba": trotter_ideal,
        "trotter_noiseless_with_finite_selected_regularization_ba": trotter_ideal_selected,
        "exact_finite_equal_per_circuit_ba": exact_matched_circuit,
        "exact_finite_equal_total_circuit_shots_ba": exact_matched_total,
        "exact_noiseless_ba": exact_ideal,
        "exact_equal_total_shots_per_circuit": exact_budget_shots,
        "exact_equal_total_circuit_shots_used": exact_budget_shots * exact_circuits,
        "trotter_actual_total_circuit_shots_used": actual_total_circuit_shots,
        "state_infidelity": float(np.mean(state_infidelity(exact_states[train], trotter_states[train]))),
        "kernel_relative_frobenius_error": float(np.linalg.norm(trotter_kernel[np.ix_(train, train)] - exact_kernel[np.ix_(train, train)]) / max(np.linalg.norm(exact_kernel[np.ix_(train, train)]), 1e-12)),
        "raw_min_eigenvalue": float(stages.raw_eigenvalues[0]),
        "psd_min_eigenvalue": float(stages.psd_eigenvalues[0]),
        "spectral_rank": int(np.count_nonzero(stages.spectral_eigenvalues)),
    }
    matrices = {"raw": stages.raw, "psd": stages.psd, "spectral": stages.spectral}
    return metrics, matrices


def _classical_models(count: int, seed: int):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.kernel_approximation import RBFSampler
    from sklearn.linear_model import RidgeClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import LinearSVC, SVC

    grids = {
        "svm_rbf": [(c, gamma) for c, gamma in itertools.product((0.03, 0.1, 0.3, 1, 3, 10), (0.03, 0.1, 0.3, 1, 3, 10))],
        "linear": [(c,) for c in np.logspace(-4, 4, 36)],
        "boosting": [(depth, rate, estimators) for depth, rate, estimators in itertools.product((1, 2, 3), (0.02, 0.05, 0.1, 0.2), (30, 60, 100))],
        "random_features": [(gamma, alpha) for gamma, alpha in itertools.product((0.03, 0.1, 0.3, 1, 3, 10), (0.003, 0.01, 0.03, 0.1, 0.3, 1))],
    }
    for name, configs in grids.items():
        for config in configs[:count]:
            if name == "svm_rbf":
                model = make_pipeline(StandardScaler(), SVC(C=config[0], gamma=config[1], kernel="rbf"))
            elif name == "linear":
                model = make_pipeline(StandardScaler(), LinearSVC(C=config[0], dual=False, max_iter=5000, random_state=seed))
            elif name == "boosting":
                model = GradientBoostingClassifier(max_depth=config[0], learning_rate=config[1], n_estimators=config[2], random_state=seed)
            else:
                model = make_pipeline(StandardScaler(), RBFSampler(gamma=config[0], n_components=256, random_state=seed), RidgeClassifier(alpha=config[1]))
            yield name, str(tuple(float(x) for x in config)), model


def _classical_baselines(values: np.ndarray, labels: np.ndarray, split: dict[str, Any], count: int, seed: int) -> list[dict[str, Any]]:
    from sklearn.base import clone

    results: list[dict[str, Any]] = []
    train = np.asarray(split["train_indices"], dtype=int)
    test = np.asarray(split["test_indices"], dtype=int)
    by_model: dict[str, list[tuple[float, str, Any]]] = {}
    for name, config, model in _classical_models(count, seed):
        scores = []
        for fold in split["inner_folds"]:
            inner_train = np.asarray(fold["train_indices"], dtype=int)
            validation = np.asarray(fold["validation_indices"], dtype=int)
            fitted = clone(model).fit(values[inner_train], labels[inner_train])
            scores.append(balanced_accuracy(labels[validation], fitted.predict(values[validation]), np.unique(labels)))
        by_model.setdefault(name, []).append((float(np.mean(scores)), config, model))
    for name, configs in by_model.items():
        inner_ba, config, model = max(configs, key=lambda row: (row[0], -configs.index(row)))
        fitted = clone(model).fit(values[train], labels[train])
        results.append({"model": name, "config": config, "inner_ba": inner_ba,
                        "outer_ba": balanced_accuracy(labels[test], fitted.predict(values[test]), np.unique(labels)),
                        "configs_evaluated": len(configs)})
    return results


def run_condition(
    protocol: V3Protocol, payload: dict[str, Any], values: np.ndarray,
    labels: np.ndarray, n: int, topology: str, profile: str, seed_index: int,
    output_dir: Path,
) -> dict[str, Any]:
    condition_id = f"n{n}_{topology}_{profile}_s{seed_index}"
    terms = generate_terms(protocol, n, topology, profile, seed_index)
    resources = _cost_screen(protocol, terms, topology)
    _write_csv(output_dir / "resources" / f"{condition_id}.csv", resources)
    _write_csv(output_dir / "grid" / f"{condition_id}.csv", _grid_resource_scan(protocol, terms, resources))
    selected_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    training_kernel_cache: dict[tuple[Any, ...], np.ndarray] = {}
    for split in payload["cv_manifest"]["splits"]:
        split_id = f"r{split['repeat']}_f{split['fold']}"
        for cell in protocol.budget_cells():
            cell_id = f"d{cell['depth']}_s{cell['circuit_shots']}_q{cell['two_qubit_gate_shots']}"
            candidates, shots, circuits, weighted_maps = _feasible_candidates(resources, cell, split, protocol)
            if not candidates:
                continue
            tuning_trials = len(candidates) * len(protocol.regularization_grid)
            baseline_key = (int(split["repeat"]), int(split["fold"]), tuning_trials)
            if baseline_key not in _CLASSICAL_CACHE:
                _CLASSICAL_CACHE[baseline_key] = _classical_baselines(
                    values, labels, split, tuning_trials, protocol.split_seed
                )
            for replicate in range(protocol.shot_replicates):
                selected, scores, raw_train = select_policy(
                    protocol, terms, values, labels, split, candidates, shots,
                    replicate, condition_id, cell_id, training_kernel_cache,
                )
                candidate_rows.extend({"condition_id": condition_id, "split_id": split_id, "cell_id": cell_id, "replicate": replicate, **score} for score in scores)
                # Persist selection before any call to the exact-evolution oracle.
                selection = {
                    "schema": RESULT_SCHEMA, "protocol_hash": payload["protocol_hash"],
                    "condition_id": condition_id, "split_id": split_id, "cell_id": cell_id,
                    "replicate": replicate, "selected_order": selected["candidate"]["order"],
                    "selected_delta_t": selected["candidate"]["delta_t"],
                    "selected_regularization": selected["regularization"],
                    "selected_inner_ba": selected["inner_ba"],
                    "selection_inputs": "inner_cv_and_known_costs_only",
                }
                selection_path = output_dir / "selection" / condition_id / f"{split_id}_{cell_id}_rep{replicate}.json"
                _write_json(selection_path, selection)
                diagnostics, matrices = _post_selection_diagnostics(
                    protocol, terms, values, labels, split, selected, raw_train,
                    shots, shots * circuits, condition_id, cell_id, replicate,
                )
                if split["repeat"] == 0 and split["fold"] == 0 and replicate == 0:
                    matrix_path = output_dir / "matrices" / condition_id / f"{cell_id}.npz"
                    matrix_path.parent.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(matrix_path, **matrices)
                selected_rows.append({
                    **selection, **cell, "candidate_count": len(candidates),
                    "quantum_tuning_configs_evaluated": tuning_trials,
                    "shots_per_circuit": shots, "circuit_executions": circuits,
                    "circuit_shots_used": shots * circuits,
                    "map_executions_used": 2 * shots * circuits,
                    "two_qubit_gate_shots_used": shots * weighted_maps,
                    "selected_full_circuit_depth": selected["candidate"]["depth"],
                    "selected_full_circuit_two_qubit_gates": selected["candidate"]["two_qubit_gates"],
                    **diagnostics,
                })
    condition_dir = output_dir / "conditions"
    _write_csv(condition_dir / f"{condition_id}_outer.csv", selected_rows)
    _write_csv(condition_dir / f"{condition_id}_candidates.csv", candidate_rows)
    return {"condition_id": condition_id, "outer_rows": len(selected_rows),
            "candidate_rows": len(candidate_rows),
            "hamiltonian_diagnostics": hamiltonian_diagnostics(terms, protocol.input_dim)}


def run_benchmark(protocol_path: Path, output_dir: Path, max_conditions: int | None = None) -> dict[str, Any]:
    protocol, payload = load_protocol(protocol_path)
    _CLASSICAL_CACHE.clear()
    classical_path = output_dir / "classical_baselines.csv"
    if classical_path.exists():
        with classical_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (int(row.pop("repeat")), int(row.pop("fold")), int(row["configs_evaluated"]))
                _CLASSICAL_CACHE.setdefault(key, []).append(row)
    development, meta = _dataset(protocol)
    if meta["dataset_sha256"] != payload["development_sha256"]:
        raise ValueError("development data changed after freezing")
    all_conditions = list(itertools.product(protocol.qubit_counts, protocol.topologies, protocol.hamiltonian_profiles, protocol.hamiltonian_seeds))
    conditions = all_conditions
    if max_conditions is not None:
        conditions = conditions[:max_conditions]
    progress_path = output_dir / "progress.json"
    if progress_path.exists():
        previous = json.loads(progress_path.read_text(encoding="utf-8"))
        if previous.get("protocol_hash") != payload["protocol_hash"]:
            raise ValueError("existing progress belongs to another protocol")
        if previous.get("conditions") and not classical_path.exists():
            raise ValueError("existing classical baseline cache is missing")
        summaries = list(previous["conditions"])
    else:
        summaries = []
    completed = {item["condition_id"] for item in summaries}
    for n, topology, profile, seed_index in conditions:
        condition_id = f"n{n}_{topology}_{profile}_s{seed_index}"
        if condition_id in completed:
            if not (output_dir / "conditions" / f"{condition_id}_outer.csv").exists():
                raise ValueError(f"completed condition file missing: {condition_id}")
            continue
        summaries.append(run_condition(protocol, payload, development.x, development.y, n, topology, profile, seed_index, output_dir))
        completed.add(condition_id)
        _write_csv(output_dir / "classical_baselines.csv", [
            {"repeat": repeat, "fold": fold, "configs_evaluated": count, **row}
            for (repeat, fold, count), rows in sorted(_CLASSICAL_CACHE.items())
            for row in rows
        ])
        _write_json(progress_path, {
            "schema": RESULT_SCHEMA, "protocol_hash": payload["protocol_hash"],
            "completed_conditions": len(summaries), "expected_conditions": len(all_conditions),
            "status": "complete" if len(summaries) == len(all_conditions) else "partial_not_confirmatory",
            "conditions": summaries,
        })
    if not progress_path.exists():
        raise RuntimeError("no benchmark conditions completed")
    return json.loads(progress_path.read_text(encoding="utf-8"))


def _final_split(protocol: V3Protocol) -> dict[str, Any]:
    from sklearn.model_selection import StratifiedKFold

    development, _ = _dataset(protocol)
    indices = np.arange(protocol.sample_count)
    folds = StratifiedKFold(
        n_splits=protocol.inner_folds, shuffle=True,
        random_state=protocol.split_seed + 500_000,
    )
    inner = [
        {"train_indices": indices[train].tolist(), "validation_indices": indices[val].tolist()}
        for train, val in folds.split(development.x, development.y)
    ]
    return {
        "repeat": "final", "fold": "holdout",
        "train_indices": indices.tolist(),
        "test_indices": np.arange(protocol.sample_count, protocol.sample_count + protocol.holdout_count).tolist(),
        "inner_folds": inner,
    }


def run_holdout(protocol_path: Path, output_dir: Path) -> dict[str, Any]:
    """Freeze every final choice before materializing any held-out test values."""
    protocol, payload = load_protocol(protocol_path)
    progress_path = output_dir / "progress.json"
    if not progress_path.exists():
        raise RuntimeError("development benchmark has not run")
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    if progress.get("status") != "complete" or progress.get("protocol_hash") != payload["protocol_hash"]:
        raise RuntimeError("holdout requires complete v3 development benchmark")
    development, meta = _dataset(protocol)
    if meta["dataset_sha256"] != payload["development_sha256"]:
        raise ValueError("development fingerprint changed")
    split = _final_split(protocol)
    frozen: list[dict[str, Any]] = []
    conditions = list(itertools.product(protocol.qubit_counts, protocol.topologies, protocol.hamiltonian_profiles, protocol.hamiltonian_seeds))
    for n, topology, profile, seed_index in conditions:
        condition_id = f"n{n}_{topology}_{profile}_s{seed_index}"
        terms = generate_terms(protocol, n, topology, profile, seed_index)
        resource_path = output_dir / "resources" / f"{condition_id}.csv"
        with resource_path.open(encoding="utf-8", newline="") as handle:
            resources = [
                {**row, "order": int(row["order"]), "delta_t": float(row["delta_t"]),
                 "depth": int(row["depth"]), "two_qubit_gates": int(row["two_qubit_gates"]),
                 "total_gates": int(row["total_gates"])}
                for row in csv.DictReader(handle)
            ]
        for cell in protocol.budget_cells():
            cell_id = f"d{cell['depth']}_s{cell['circuit_shots']}_q{cell['two_qubit_gate_shots']}"
            candidates, shots, circuits, weighted_maps = _feasible_candidates(resources, cell, split, protocol)
            if not candidates:
                continue
            for replicate in range(protocol.shot_replicates):
                selected, scores, raw_train = select_policy(
                    protocol, terms, development.x, development.y, split,
                    candidates, shots, replicate, condition_id, cell_id,
                )
                raw_path = output_dir / "final_training_matrices" / condition_id / f"{cell_id}_rep{replicate}.npz"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(raw_path, raw=raw_train)
                frozen.append({
                    "condition_id": condition_id, "n_qubits": n, "topology": topology,
                    "hamiltonian_profile": profile, "hamiltonian_seed": seed_index,
                    "cell_id": cell_id, "cell": cell, "replicate": replicate,
                    "candidate_count": len(candidates), "shots": shots,
                    "quantum_tuning_configs_evaluated": len(candidates) * len(protocol.regularization_grid),
                    "circuits": circuits, "weighted_maps": weighted_maps,
                    "selection": {
                        "order": selected["candidate"]["order"],
                        "delta_t": selected["candidate"]["delta_t"],
                        "regularization": selected["regularization"],
                        "inner_ba": selected["inner_ba"],
                    },
                    "candidate_scores": scores,
                    "raw_training_matrix_path": str(raw_path.relative_to(output_dir)),
                    "raw_training_matrix_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                })
    freeze_payload = {
        "schema": "trotter-scaling.final-selection.v3",
        "protocol_hash": payload["protocol_hash"],
        "development_sha256": payload["development_sha256"],
        "holdout_sha256": payload["holdout_sha256"],
        "holdout_not_loaded_during_selection": True,
        "selections": frozen,
    }
    freeze_payload["selection_hash"] = _digest(freeze_payload)
    freeze_path = output_dir / "final_selection_before_holdout.json"
    if freeze_path.exists():
        existing = json.loads(freeze_path.read_text(encoding="utf-8"))
        if existing.get("selection_hash") != freeze_payload["selection_hash"]:
            raise RuntimeError("a different final selection is already frozen")
    else:
        _write_json(freeze_path, freeze_payload)

    # The first access to the held-out feature values and labels is below.
    holdout, holdout_meta = _dataset(protocol, holdout=True)
    if holdout_meta["dataset_sha256"] != payload["holdout_sha256"]:
        raise ValueError("holdout fingerprint changed")
    all_values = np.vstack((development.x, holdout.x))
    all_labels = np.concatenate((development.y, holdout.y))
    holdout_baselines = [
        {"quantum_tuning_configs_evaluated": count, **row}
        for count in sorted({item["quantum_tuning_configs_evaluated"] for item in frozen})
        for row in _classical_baselines(
            all_values, all_labels, split, count, protocol.split_seed + 500_000
        )
    ]
    _write_csv(output_dir / "holdout_classical_baselines.csv", holdout_baselines)
    rows: list[dict[str, Any]] = []
    for item in frozen:
        terms = generate_terms(
            protocol, item["n_qubits"], item["topology"],
            item["hamiltonian_profile"], item["hamiltonian_seed"],
        )
        choice = item["selection"]
        selected = {
            "candidate": {"order": choice["order"], "delta_t": choice["delta_t"]},
            "regularization": choice["regularization"],
        }
        raw_path = output_dir / item["raw_training_matrix_path"]
        if hashlib.sha256(raw_path.read_bytes()).hexdigest() != item["raw_training_matrix_sha256"]:
            raise ValueError("frozen final training matrix changed")
        with np.load(raw_path) as archive:
            raw_train = archive["raw"]
        metrics, _ = _post_selection_diagnostics(
            protocol, terms, all_values, all_labels, split, selected, raw_train,
            item["shots"], item["shots"] * item["circuits"], item["condition_id"],
            item["cell_id"], item["replicate"],
        )
        rows.append({
            "schema": "trotter-scaling.holdout.v3", "protocol_hash": payload["protocol_hash"],
            "selection_hash": freeze_payload["selection_hash"],
            "condition_id": item["condition_id"], "cell_id": item["cell_id"],
            "replicate": item["replicate"], **choice, **item["cell"],
            "candidate_count": item["candidate_count"],
            "quantum_tuning_configs_evaluated": item["quantum_tuning_configs_evaluated"],
            "shots_per_circuit": item["shots"],
            "circuit_shots_used": item["shots"] * item["circuits"],
            "two_qubit_gate_shots_used": item["shots"] * item["weighted_maps"],
            **metrics,
        })
    _write_csv(output_dir / "holdout_results.csv", rows)
    result = {"schema": "trotter-scaling.holdout-summary.v3",
              "protocol_hash": payload["protocol_hash"],
              "selection_hash": freeze_payload["selection_hash"],
              "holdout_rows": len(rows), "status": "complete"}
    _write_json(output_dir / "holdout_progress.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "holdout"))
    parser.add_argument("--profile", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-conditions", type=int)
    args = parser.parse_args()
    protocol_path = args.output_dir / "protocol.json"
    if args.action == "freeze":
        result = freeze_protocol(protocol_path, protocol_for_profile(args.profile))
        print(json.dumps({"protocol_hash": result["protocol_hash"], "path": str(protocol_path)}))
    elif args.action == "run":
        result = run_benchmark(protocol_path, args.output_dir, args.max_conditions)
        print(json.dumps({"status": result["status"], "completed_conditions": result["completed_conditions"]}))
    else:
        result = run_holdout(protocol_path, args.output_dir)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
