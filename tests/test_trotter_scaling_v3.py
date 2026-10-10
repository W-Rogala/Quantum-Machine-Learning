import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hamiltonian_kernel.trotter_scaling import make_perfectly_annotated_dataset
from hamiltonian_kernel.trotter_scaling_full import generate_terms, make_cv_manifest
from hamiltonian_kernel.trotter_scaling_v3 import (
    _classical_models,
    _feasible_candidates,
    _logical_circuit,
    freeze_protocol,
    full_circuit_resources,
    load_protocol,
    protocol_for_profile,
    select_policy,
)


class TrotterScalingV3Tests(unittest.TestCase):
    def test_fresh_seeds_and_factorial_budgets(self):
        protocol = protocol_for_profile("full")
        protocol.validate()
        self.assertEqual(len(protocol.hamiltonian_seeds), 20)
        self.assertGreaterEqual(min(protocol.hamiltonian_seeds), 20)
        self.assertEqual(len(protocol.budget_cells()), 8)
        self.assertEqual(len(protocol.delta_grid()), 100)
        for axis in ("depth", "circuit_shots", "two_qubit_gate_shots"):
            self.assertEqual(len({cell[axis] for cell in protocol.budget_cells()}), 2)

    def test_frozen_protocol_detects_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protocol.json"
            protocol = protocol_for_profile("smoke")
            original = freeze_protocol(path, protocol)
            restored, payload = load_protocol(path)
            self.assertEqual(restored, protocol)
            self.assertEqual(payload["protocol_hash"], original["protocol_hash"])
            text = path.read_text(encoding="utf-8").replace(
                '"dataset_seed": 20261001', '"dataset_seed": 20261005'
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid or modified"):
                load_protocol(path)

    def test_exact_oracle_is_not_called_in_selection(self):
        protocol = protocol_for_profile("smoke")
        dataset, _ = make_perfectly_annotated_dataset(
            18, 3, protocol.dataset_seed, 0.2
        )
        split = make_cv_manifest(
            dataset.y, 2, 3, 2, protocol.split_seed
        )["splits"][0]
        terms = generate_terms(protocol, 2, "chain", "ising_zz_x_z", 20)
        candidates = [
            {"order": 1, "delta_t": 1.0, "depth": 30, "two_qubit_gates": 2},
            {"order": 2, "delta_t": 0.5, "depth": 80, "two_qubit_gates": 4},
        ]
        with patch(
            "hamiltonian_kernel.trotter_scaling_v3.evolve_exact_pauli_batch",
            side_effect=AssertionError("leak"),
        ):
            selected, scores, matrix = select_policy(
                protocol, terms, dataset.x, dataset.y, split,
                candidates, 32, 0, "condition", "cell",
            )
        self.assertIn(selected["candidate"], candidates)
        self.assertEqual(len(scores), 2)
        self.assertEqual(matrix.shape, (12, 12))

    def test_resource_axes_are_independent(self):
        protocol = protocol_for_profile("smoke")
        split = {
            "train_indices": list(range(12)),
            "test_indices": list(range(12, 18)),
        }
        rows = [{
            "order": 1, "delta_t": 1.0,
            "depth": 200, "two_qubit_gates": 5,
        }]
        base = {
            "depth": 300, "circuit_shots": 50_000,
            "two_qubit_gate_shots": 2_000_000,
        }
        a = _feasible_candidates(rows, base, split, protocol)
        b = _feasible_candidates(
            rows, {**base, "circuit_shots": 200_000}, split, protocol
        )
        c = _feasible_candidates(
            rows, {**base, "two_qubit_gate_shots": 8_000_000},
            split, protocol,
        )
        self.assertEqual(a[0], b[0])
        self.assertEqual(a[0], c[0])
        self.assertGreaterEqual(b[1], a[1])
        self.assertGreaterEqual(c[1], a[1])
        self.assertEqual(
            _feasible_candidates(
                rows, {**base, "depth": 100}, split, protocol
            )[0],
            [],
        )

    def test_shortlist_balances_orders_and_classical_trials(self):
        protocol = protocol_for_profile("smoke")
        split = {
            "train_indices": list(range(12)),
            "test_indices": list(range(12, 18)),
        }
        rows = [
            {"order": order, "delta_t": step, "depth": 100,
             "two_qubit_gates": 2}
            for order in (1, 2, 4)
            for step in (0.25, 0.5, 0.75, 1.0, 0.26)
        ]
        cell = {
            "depth": 300, "circuit_shots": 200_000,
            "two_qubit_gate_shots": 8_000_000,
        }
        candidates, shots, _, _ = _feasible_candidates(
            rows, cell, split, protocol
        )
        self.assertGreaterEqual(shots, protocol.minimum_shots_per_circuit)
        self.assertEqual(len(candidates), 12)
        for order in (1, 2, 4):
            self.assertEqual(sum(row["order"] == order for row in candidates), 4)
        trials = len(candidates) * len(protocol.regularization_grid)
        counts = {}
        for model_name, _, _ in _classical_models(trials, protocol.split_seed):
            counts[model_name] = counts.get(model_name, 0) + 1
        self.assertEqual(counts, {
            "svm_rbf": 36, "linear": 36,
            "boosting": 36, "random_features": 36,
        })

    def test_full_circuit_compilation_counts_entire_sequence(self):
        circuit, _ = _logical_circuit(("XI", "IZ", "ZZ"), 1, 0.5, 1.0)
        self.assertEqual(circuit.num_qubits, 2)
        resources = full_circuit_resources(
            ("XI", "IZ", "ZZ"), "chain", 1, 0.5, 1.0, 12
        )
        self.assertGreater(resources["depth"], 0)
        self.assertGreater(resources["two_qubit_gates"], 0)
        self.assertEqual(
            resources["method"], "qiskit_full_parameterized_circuit_opt1"
        )


if __name__ == "__main__":
    unittest.main()
