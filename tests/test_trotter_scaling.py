from __future__ import annotations

import csv
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from hamiltonian_kernel.core import state_infidelity
from hamiltonian_kernel.trotter_scaling import (
    freeze_protocol,
    make_perfectly_annotated_dataset,
    one_hot_qubo_energies,
    one_hot_qubo_payload,
    protocol_for_profile,
    protocol_payload,
    qaoa_one_hot_select,
    run_benchmark,
    simulated_annealing_one_hot_select,
)
from hamiltonian_kernel.universal_hamiltonian import (
    UniversalHamiltonianConfig,
    evolve_exact_pauli,
    evolve_exact_pauli_batch,
    evolve_product_formula,
    evolve_product_formula_batch,
    generate_universal_terms,
    pauli_labels,
    product_formula_resources,
    slice_schedule,
)
import hamiltonian_kernel.trotter_scaling_full as full_scaling


class UniversalHamiltonianTests(unittest.TestCase):
    def test_two_qubit_family_spans_all_nonidentity_paulis(self) -> None:
        labels = pauli_labels(2, 2)
        self.assertEqual(len(labels), 15)
        self.assertEqual(len(set(labels)), 15)
        self.assertIn("XI", labels)
        self.assertIn("IY", labels)
        self.assertIn("ZZ", labels)
        self.assertIn("XY", labels)

    def test_product_formula_is_normalized_and_refines_toward_exact(self) -> None:
        config = UniversalHamiltonianConfig(
            n_qubits=2,
            input_dim=2,
            max_locality=2,
            coefficient_seed=17,
        )
        terms = generate_universal_terms(config)
        x = np.asarray([0.4, -0.7], dtype=float)
        exact = evolve_exact_pauli(terms, x, 1.0)[None, :]
        coarse = evolve_product_formula(terms, x, 1.0, 2, 0.5)[None, :]
        fine = evolve_product_formula(terms, x, 1.0, 2, 0.1)[None, :]
        self.assertAlmostEqual(float(np.linalg.norm(fine)), 1.0, places=11)
        self.assertLess(
            float(state_infidelity(exact, fine)[0]),
            float(state_infidelity(exact, coarse)[0]),
        )

    def test_nominal_step_uses_positive_remainder_and_exact_total_time(self) -> None:
        schedule = slice_schedule(1.0, 0.27)
        self.assertEqual(schedule[:3], (0.27, 0.27, 0.27))
        self.assertAlmostEqual(schedule[-1], 0.19, places=12)
        self.assertAlmostEqual(sum(schedule), 1.0, places=12)
        self.assertTrue(all(value > 0.0 for value in schedule))

    def test_batch_evolution_matches_scalar_reference(self) -> None:
        terms = generate_universal_terms(
            UniversalHamiltonianConfig(
                n_qubits=2,
                input_dim=3,
                max_locality=2,
                coefficient_seed=31,
                max_terms=7,
            )
        )
        values = np.asarray([[0.2, -0.3, 0.7], [-0.5, 0.1, 0.4]])
        exact_reference = np.asarray(
            [evolve_exact_pauli(terms, row, 1.0) for row in values]
        )
        trotter_reference = np.asarray(
            [evolve_product_formula(terms, row, 1.0, 4, 0.25) for row in values]
        )
        self.assertTrue(
            np.allclose(evolve_exact_pauli_batch(terms, values, 1.0), exact_reference)
        )
        self.assertTrue(
            np.allclose(
                evolve_product_formula_batch(terms, values, 1.0, 4, 0.25),
                trotter_reference,
            )
        )

    def test_resource_depth_increases_with_finer_steps_and_more_terms(self) -> None:
        terms_two = generate_universal_terms(
            UniversalHamiltonianConfig(n_qubits=2, input_dim=2, max_locality=2)
        )
        terms_three = generate_universal_terms(
            UniversalHamiltonianConfig(n_qubits=3, input_dim=2, max_locality=2)
        )
        coarse = product_formula_resources(terms_two, 1.0, 1, 1.0)
        fine = product_formula_resources(terms_two, 1.0, 1, 0.25)
        larger = product_formula_resources(terms_three, 1.0, 1, 1.0)
        self.assertGreater(fine.serial_depth_proxy, coarse.serial_depth_proxy)
        self.assertGreater(larger.serial_depth_proxy, coarse.serial_depth_proxy)


class ScalingProtocolTests(unittest.TestCase):
    def test_grid_increment_is_exactly_one_hundredth(self) -> None:
        protocol = protocol_for_profile("smoke")
        grid = protocol.delta_grid()
        differences = np.diff(np.asarray(grid))
        self.assertTrue(np.allclose(differences, 0.01, atol=1e-14))
        self.assertEqual(grid[0], 0.10)
        self.assertEqual(grid[-1], 1.00)

    def test_perfect_annotations_are_balanced_deterministic_and_margin_separated(self) -> None:
        first, first_metadata = make_perfectly_annotated_dataset(20, 3, 7, 0.2)
        second, second_metadata = make_perfectly_annotated_dataset(20, 3, 7, 0.2)
        self.assertTrue(np.array_equal(first.x, second.x))
        self.assertTrue(np.array_equal(first.y, second.y))
        self.assertEqual(np.bincount(first.y).tolist(), [10, 10])
        self.assertEqual(first_metadata["label_noise"], 0.0)
        self.assertGreaterEqual(first_metadata["minimum_observed_margin"], 0.2)
        self.assertEqual(
            first_metadata["dataset_sha256"], second_metadata["dataset_sha256"]
        )

    def test_frozen_protocol_rejects_mutation(self) -> None:
        protocol = protocol_for_profile("smoke")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protocol.json"
            freeze_protocol(path, protocol)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["protocol"]["delta_increment"] = 0.02
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                freeze_protocol(path, protocol)


class FullScalingProtocolV2Tests(unittest.TestCase):
    def test_full_profile_freezes_all_requested_axes(self) -> None:
        protocol = full_scaling.protocol_for_profile("full")
        protocol.validate()
        self.assertEqual(protocol.qubit_counts, (2, 3, 4, 5, 6))
        self.assertEqual(protocol.trotter_orders, (1, 2, 4))
        self.assertEqual(protocol.delta_grid(), tuple(value / 100 for value in range(1, 101)))
        self.assertEqual(len(protocol.hamiltonian_seeds), 20)
        self.assertEqual(
            protocol.topologies, ("chain", "ring", "grid", "all_to_all")
        )
        self.assertEqual(
            protocol.hamiltonian_profiles,
            (
                "ising_zz_x_z",
                "random_k_local",
                "spectral_radius_1",
                "spectral_radius_3",
            ),
        )
        expected_rows = 5 * 4 * 20 * 4 * 3 * 100
        self.assertEqual(expected_rows, 480_000)

    def test_every_topology_is_connected_and_uses_valid_edges(self) -> None:
        for n_qubits in range(2, 7):
            for topology in ("chain", "ring", "grid", "all_to_all"):
                edges = full_scaling.topology_edges(n_qubits, topology)
                self.assertTrue(edges)
                self.assertTrue(
                    all(0 <= left < right < n_qubits for left, right in edges)
                )
                reached = {0}
                while True:
                    expanded = reached | {
                        right
                        for left, right in edges
                        if left in reached
                    } | {
                        left
                        for left, right in edges
                        if right in reached
                    }
                    if expanded == reached:
                        break
                    reached = expanded
                self.assertEqual(reached, set(range(n_qubits)))

    def test_controlled_spectral_radius_profiles_hit_their_targets(self) -> None:
        protocol = full_scaling.protocol_for_profile("full")
        for profile, target in (("spectral_radius_1", 1.0), ("spectral_radius_3", 3.0)):
            terms = full_scaling.generate_terms(
                protocol, 3, "ring", profile, seed_index=4
            )
            diagnostics = full_scaling.hamiltonian_diagnostics(
                terms, protocol.input_dim
            )
            self.assertAlmostEqual(
                float(diagnostics["calibration_spectral_radius"]), target, places=10
            )

    def test_resource_measurement_is_qiskit_transpiled(self) -> None:
        protocol = full_scaling.protocol_for_profile("smoke")
        terms = full_scaling.generate_terms(
            protocol, 2, "chain", "ising_zz_x_z", seed_index=0
        )
        resources = full_scaling._transpiled_slice_resources(
            tuple(term.label for term in terms),
            2,
            full_scaling.topology_edges(2, "chain"),
            protocol.transpiler_seed,
        )
        self.assertGreater(resources["slice_depth"], 0)
        self.assertGreaterEqual(resources["slice_two_qubit_gates"], 0)
        self.assertEqual(
            resources["method"],
            "qiskit_transpiled_slice_with_frozen_inter_slice_boundaries",
        )

    def test_fixed_anchors_are_evaluated_even_when_depth_infeasible(self) -> None:
        protocol = full_scaling.protocol_for_profile("full")
        rows = [
            {
                "order": order,
                "delta_t": delta_t,
                "transpiled_depth": 10_000,
                "commutator_error_proxy": 0.5,
            }
            for order in protocol.trotter_orders
            for delta_t in protocol.delta_grid()
        ]
        selected = full_scaling._shortlist_rows(rows, protocol)
        selected_keys = {
            (int(row["order"]), float(row["delta_t"])) for row in selected
        }
        expected = {
            (order, anchor)
            for order in protocol.trotter_orders
            for anchor in protocol.shortlist_anchors
        }
        self.assertEqual(selected_keys, expected)


class QuadraticAndQAOATests(unittest.TestCase):
    def test_one_hot_qubo_has_the_expected_exact_minimum(self) -> None:
        scores = np.asarray([0.1, 0.7, 0.9], dtype=float)
        bits, energies = one_hot_qubo_energies(scores, penalty=2.0)
        minimum = int(np.argmin(energies))
        self.assertEqual(bits[minimum].tolist(), [1.0, 0.0, 0.0])

        payload = one_hot_qubo_payload(scores, penalty=2.0)
        reconstructed = []
        for state in bits:
            value = payload["constant"] + np.asarray(payload["linear"]) @ state
            value += sum(
                term["coefficient"] * state[term["i"]] * state[term["j"]]
                for term in payload["quadratic"]
            )
            reconstructed.append(value)
        self.assertTrue(np.allclose(reconstructed, energies))

    def test_simulated_annealing_uses_the_portable_qubo(self) -> None:
        result = simulated_annealing_one_hot_select(
            np.asarray([0.4, 0.1, 0.8], dtype=float),
            reads=16,
            sweeps=40,
            seed=9,
        )
        self.assertIn(result["selected_index"], range(3))
        self.assertGreater(result["feasible_visits"], 0)
        self.assertEqual(
            result["execution"],
            "classical_simulated_annealing_not_quantum_annealing",
        )

    def test_qaoa_arm_always_returns_a_feasible_candidate(self) -> None:
        result = qaoa_one_hot_select(
            np.asarray([0.1, 0.35, 0.8], dtype=float),
            gamma_points=13,
            beta_points=13,
        )
        self.assertIn(result["selected_index"], range(3))
        self.assertGreater(result["selected_probability"], 0.0)
        self.assertGreater(result["feasible_probability"], 0.0)
        self.assertEqual(result["execution"], "exact_statevector_simulation_not_qpu")


class EndToEndScalingFrameworkTests(unittest.TestCase):
    def test_mini_run_keeps_test_metric_out_of_candidate_selection(self) -> None:
        protocol = replace(
            protocol_for_profile("smoke"),
            sample_count=12,
            qubit_counts=(2,),
            depth_budgets=(100,),
            max_locality=1,
            delta_min=0.80,
            delta_max=1.00,
            qaoa_shortlist_size=4,
            qaoa_gamma_points=5,
            qaoa_beta_points=5,
            permutation_resamples=100,
        )
        manifest = protocol_payload(protocol)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_benchmark(protocol, manifest, output)
            self.assertEqual(result["status"], "complete")
            self.assertTrue(result["test_isolation_verified"])
            self.assertEqual(result["candidate_rows"], 42)
            self.assertEqual(result["selection_rows"], 5)
            with (output / "candidates.csv").open("r", encoding="utf-8") as handle:
                candidates = list(csv.DictReader(handle))
            self.assertNotIn("test_balanced_accuracy", candidates[0])
            self.assertTrue(all(row["test_metric_exposed"] == "False" for row in candidates))
            with (output / "selections.csv").open("r", encoding="utf-8") as handle:
                selections = list(csv.DictReader(handle))
            self.assertTrue(all(row["selection_used_test"] == "False" for row in selections))
            self.assertTrue(all(row["test_balanced_accuracy"] for row in selections))
            instance = json.loads(
                next((output / "optimizer_instances").glob("*.json")).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(instance["objective_source"], "train_validation_only")
            self.assertLess(len(instance["surrogate_pilots"]), len(candidates))
            self.assertIn("qubo", instance)


if __name__ == "__main__":
    unittest.main()
