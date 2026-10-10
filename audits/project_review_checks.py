"""Small, offline reproductions of findings from the 2026-09-22 project review.

These are evidence probes, not passing regression tests for the known defects.
No historical experimental output is modified.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from hamiltonian_kernel.estimation import estimate_fidelity_spectral
from hamiltonian_kernel.trotter_scaling_v3 import _candidate_budget
from quantum_reservoir.core import inject_input
from experiments.legacy.vqe_scar_ansatz_experiment import scar

ROOT = Path(__file__).resolve().parents[1]


def main():
    rng = np.random.default_rng(220926)
    states = rng.normal(size=(12, 4)) + 1j * rng.normal(size=(12, 4))
    states /= np.linalg.norm(states, axis=1, keepdims=True)
    estimate = estimate_fidelity_spectral(states, 12, np.arange(12), 156, rng)
    spectral_gap = float(np.max(np.abs(np.linalg.eigvalsh(estimate.spectral_kernel) - estimate.spectral_eigenvalues)))
    shots, circuits, reserved = _candidate_budget(
        [{"two_qubit_gates": 1}, {"two_qubit_gates": 10}], 3, 4,
        {"circuit_shots": 1000, "two_qubit_gate_shots": 10000})
    actual_if_cheap_selected = 2 * (3 * (1 + 10) + 4 * 1)
    a = np.zeros((4, 4), complex); a[0, 0] = 1
    b = np.zeros((4, 4), complex); b[1, 1] = 1
    reset_ratio = float(np.linalg.norm(inject_input(a, .37) - inject_input(b, .37), ord="nuc") / np.linalg.norm(a-b, ord="nuc"))
    matrix = scar(.4, .6, .8)
    qsvt_counterexample = np.diag([1, -1])  # P=1: even SV transformation is identity, not polar(A).
    result = {
        "spectral_eigenvalue_label_gap": spectral_gap,
        "resource_reservation_example": {"shots": shots, "circuits": circuits,
            "reported_gate_shots": shots * reserved,
            "actual_gate_shots_if_cheaper_candidate_selected": shots * actual_if_cheap_selected},
        "threshold_detector_two_photons_eta_half": {"current_post_threshold_thinning": .5,
            "physical_loss_before_threshold": 1-(1-.5)**2},
        "reset_one_qubit_trace_distance_ratio": reset_ratio,
        "scar_unitarity_max_error": float(np.max(abs(matrix.conj().T @ matrix-np.eye(4)))),
        "even_qsvt_constant_polynomial_counterexample_error": float(np.linalg.norm(qsvt_counterexample-np.eye(2))),
        "h2_dimension_ratio_by_allowed_qubits": {str(q): 2**q / 2**6 for q in (4, 6, 8)},
        "note": "Diagnostic values reproduce findings; no experiments were retrained or QPU jobs submitted."
    }
    assert spectral_gap > 1e-4
    assert reset_ratio > .999999
    assert result["scar_unitarity_max_error"] < 1e-12
    output = ROOT / "docs/audit/review_checks.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
