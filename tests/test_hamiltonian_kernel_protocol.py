from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from hamiltonian_kernel.correct_resource_costs import correct_cost_rows
from hamiltonian_kernel.protocol import (
    cluster_sign_flip_test,
    freeze_protocol,
    hierarchical_paired_interval,
    load_frozen_protocol,
    protocol_for_profile,
)
from hamiltonian_kernel.publication_benchmark import (
    _fixed_search_sample,
    classical_search_space,
    quantum_search_space,
)


class FrozenProtocolTests(unittest.TestCase):
    def test_freeze_is_idempotent_but_rejects_mutation(self) -> None:
        protocol = protocol_for_profile("smoke")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protocol.json"
            first = freeze_protocol(path, protocol)
            second = freeze_protocol(path, protocol)
            self.assertEqual(first, second)
            loaded, payload = load_frozen_protocol(path)
            self.assertEqual(loaded, protocol)
            self.assertEqual(payload["protocol_hash"], first["protocol_hash"])
            with self.assertRaises(FileExistsError):
                freeze_protocol(path, replace(protocol, alpha=0.1))

    def test_hash_detects_manual_edit(self) -> None:
        protocol = protocol_for_profile("smoke")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protocol.json"
            payload = freeze_protocol(path, protocol)
            payload["protocol"]["alpha"] = 0.1
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_frozen_protocol(path)


class EqualTuningBudgetTests(unittest.TestCase):
    def test_every_family_can_supply_same_frozen_budget(self) -> None:
        count = protocol_for_profile("full").tuning_configurations_per_family
        spaces = {
            "fidelity": quantum_search_space("fidelity", "full"),
            "projected": quantum_search_space("projected", "full"),
            "svm_rbf": classical_search_space("svm_rbf"),
            "linear": classical_search_space("linear"),
            "gradient_boosting": classical_search_space("gradient_boosting"),
            "random_fourier_features": classical_search_space("random_fourier_features"),
        }
        for index, (family, space) in enumerate(spaces.items()):
            selected = _fixed_search_sample(space, count, seed=100 + index)
            self.assertEqual(len(selected), count, family)
            self.assertEqual(len({json.dumps(row, sort_keys=True) for row in selected}), count)


class ResourceCostCorrectionTests(unittest.TestCase):
    def test_zero_interaction_correction_removes_two_qubit_cost(self) -> None:
        row = {
            "family": "fidelity",
            "configuration_json": json.dumps(
                {
                    "candidate": {
                        "evolution_time": 1.0,
                        "interaction_strength": 0.0,
                        "transverse_field": 0.7,
                        "topology": "all_to_all",
                    }
                }
            ),
            "map_executions": "2000",
            "two_qubit_gates_per_map": "36",
            "two_qubit_gate_shots": "72000",
        }
        corrected, changed = correct_cost_rows(
            [row], n_qubits=4, trotter_order=2, trotter_steps=2
        )
        self.assertEqual(changed, 1)
        self.assertEqual(corrected[0]["two_qubit_gates_per_map"], "0")
        self.assertEqual(corrected[0]["two_qubit_gate_shots"], "0")


class HierarchicalInferenceTests(unittest.TestCase):
    @staticmethod
    def rows(delta: float) -> list[dict[str, object]]:
        return [
            {
                "dataset": dataset,
                "outer_repeat": repeat,
                "outer_fold": fold,
                "noise_replicate": noise,
                "delta": delta,
            }
            for dataset in ("a", "b")
            for repeat in range(2)
            for fold in range(3)
            for noise in range(2)
        ]

    def test_hierarchical_interval_preserves_constant_delta(self) -> None:
        result = hierarchical_paired_interval(
            self.rows(0.125),
            alpha=0.05,
            resamples=200,
            seed=7,
        )
        self.assertAlmostEqual(float(result["estimate"]), 0.125)
        self.assertAlmostEqual(float(result["ci_lower"]), 0.125)
        self.assertAlmostEqual(float(result["ci_upper"]), 0.125)

    def test_sign_flip_uses_dataset_repeat_clusters(self) -> None:
        result = cluster_sign_flip_test(self.rows(0.2), resamples=1000, seed=9)
        self.assertEqual(result["cluster_count"], 4)
        self.assertLess(float(result["p_value_one_sided"]), 0.2)


if __name__ == "__main__":
    unittest.main()
