from __future__ import annotations

import inspect
import unittest

import numpy as np

from hamiltonian_kernel.core import EvolutionConfig, bloch_vectors, evolve_batch, projected_kernel
from hamiltonian_kernel.estimation import (
    estimate_fidelity_spectral,
    projected_basis_probabilities,
    resource_cost,
)
from hamiltonian_kernel.grid_experiment import (
    HamiltonianCandidate,
    allocate_exact_budget,
    budgeted_nystrom_fidelity_features,
    budgeted_projected_bloch,
    candidate_grid,
    fidelity_estimation_circuit_count,
    landmark_indices,
    screen_and_select_candidates,
)


class GridDefinitionTests(unittest.TestCase):
    def test_grid_counts_and_unique_names(self) -> None:
        smoke = candidate_grid("smoke")
        full = candidate_grid("full")
        self.assertEqual(len(smoke), 12)
        self.assertEqual(len(full), 63)
        self.assertEqual(len({candidate.name for candidate in smoke}), len(smoke))
        self.assertEqual(len({candidate.name for candidate in full}), len(full))

    def test_zero_interaction_deduplicates_topology(self) -> None:
        zero_interaction = [
            candidate for candidate in candidate_grid("full") if candidate.interaction_strength == 0.0
        ]
        self.assertEqual({candidate.topology for candidate in zero_interaction}, {"chain"})


class MeasurementBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        x = np.asarray(
            [
                [-0.8, -0.4],
                [-0.6, 0.2],
                [-0.2, 0.7],
                [0.1, -0.9],
                [0.3, 0.5],
                [0.5, -0.3],
                [0.7, 0.1],
                [0.9, 0.8],
                [-0.4, 0.9],
                [0.2, -0.1],
            ],
            dtype=float,
        )
        self.states = evolve_batch(
            x,
            EvolutionConfig(n_qubits=2, method="trotter", trotter_order=2, trotter_steps=2),
        )

    def assert_psd(self, kernel: np.ndarray, tolerance: float = 1e-10) -> None:
        self.assertTrue(np.allclose(kernel, kernel.T, atol=1e-12))
        self.assertGreaterEqual(float(np.linalg.eigvalsh(kernel)[0]), -tolerance)

    def test_allocator_spends_exact_budget(self) -> None:
        allocation = allocate_exact_budget(17, 101, np.random.default_rng(3))
        self.assertEqual(int(allocation.shots.sum()), 101)
        self.assertEqual(allocation.total_budget, 101)
        self.assertEqual(allocation.circuit_count, 17)
        self.assertLessEqual(allocation.maximum - allocation.minimum, 1)
        with self.assertRaises(ValueError):
            allocate_exact_budget(17, 16, np.random.default_rng(3))

    def test_zero_landmarks_means_full_training_spectral_map(self) -> None:
        landmarks = landmark_indices(n_train=6, landmark_count=0, seed=99)
        self.assertTrue(np.array_equal(landmarks, np.arange(6)))
        self.assertEqual(fidelity_estimation_circuit_count(10, 6, 0), 49)
        features, diagnostics = budgeted_nystrom_fidelity_features(
            self.states,
            n_train=6,
            landmarks=landmarks,
            total_budget=241,
            rng=np.random.default_rng(13),
        )
        self.assertEqual(features.shape[0], 10)
        self.assertEqual(diagnostics["circuit_count"], 49)
        self.assertEqual(
            diagnostics["estimator"],
            "measured_diagonal_full_train_spectral_fidelity",
        )
        self.assertTrue(diagnostics["diagonal_measured"])
        self.assert_psd(features @ features.T)

    def test_nystrom_features_share_one_psd_representation(self) -> None:
        features, diagnostics = budgeted_nystrom_fidelity_features(
            self.states,
            n_train=6,
            landmarks=np.asarray([0, 2, 4]),
            total_budget=241,
            rng=np.random.default_rng(7),
        )
        self.assertEqual(features.shape[0], len(self.states))
        self.assertTrue(np.all(np.isfinite(features)))
        self.assertTrue(np.allclose(np.linalg.norm(features, axis=1), 1.0, atol=1e-12))
        self.assertEqual(diagnostics["total_budget"], 241)
        self.assertEqual(diagnostics["circuit_count"], 34)
        self.assertLessEqual(
            diagnostics["shots_per_circuit_max"] - diagnostics["shots_per_circuit_min"],
            1,
        )
        self.assert_psd(features @ features.T)

    def test_projected_estimator_spends_same_budget_and_stays_psd(self) -> None:
        estimated, diagnostics = budgeted_projected_bloch(
            self.states,
            n_qubits=2,
            total_budget=241,
            rng=np.random.default_rng(11),
        )
        self.assertEqual(estimated.shape, (10, 2, 3))
        self.assertTrue(np.all((-1.0 <= estimated) & (estimated <= 1.0)))
        self.assertEqual(diagnostics["total_budget"], 241)
        self.assertEqual(diagnostics["circuit_count"], 30)
        self.assertTrue(diagnostics["joint_bitstring_sampling"])
        self.assert_psd(projected_kernel(estimated, estimated, gamma=1.0))

    def test_projected_joint_probabilities_reproduce_exact_bloch_vectors(self) -> None:
        probabilities = projected_basis_probabilities(self.states, n_qubits=2)
        z_values = np.asarray([[1.0, 1.0], [-1.0, 1.0], [1.0, -1.0], [-1.0, -1.0]])
        reconstructed = np.einsum("sbd,dq->sqb", probabilities, z_values)
        np.testing.assert_allclose(
            reconstructed,
            bloch_vectors(self.states, n_qubits=2),
            atol=1e-12,
        )

    def test_fidelity_estimate_publishes_raw_psd_spectral_and_diagonal(self) -> None:
        estimate = estimate_fidelity_spectral(
            self.states,
            n_train=6,
            landmarks=np.arange(6),
            total_budget=509,
            rng=np.random.default_rng(23),
        )
        np.testing.assert_allclose(estimate.measured_diagonal, 1.0, atol=0.0)
        self.assertEqual(estimate.raw_landmark_kernel.shape, (6, 6))
        self.assertEqual(estimate.psd_landmark_kernel.shape, (6, 6))
        self.assertEqual(estimate.spectral_kernel.shape, (10, 10))
        self.assert_psd(estimate.psd_landmark_kernel)
        self.assert_psd(estimate.spectral_kernel)

    def test_four_axis_resource_accounting(self) -> None:
        costs = resource_cost(101, feature_maps_per_shot=2, two_qubit_gates_per_map=7)
        self.assertEqual(costs.circuit_shots, 101)
        self.assertEqual(costs.map_executions, 202)
        self.assertEqual(costs.two_qubit_gate_shots, 1414)
        self.assertIsNone(costs.qpu_time_seconds)
        self.assertIsNone(costs.qpu_credits)


class SelectionProtocolTests(unittest.TestCase):
    def test_selection_api_cannot_receive_test_data(self) -> None:
        parameters = set(inspect.signature(screen_and_select_candidates).parameters)
        self.assertTrue({"x_test", "y_test", "test"}.isdisjoint(parameters))

    def test_small_selection_run_returns_both_kernel_families(self) -> None:
        x_train = np.asarray(
            [
                [-0.9, -0.7],
                [-0.7, -0.2],
                [-0.4, -0.8],
                [-0.2, -0.3],
                [0.2, 0.4],
                [0.4, 0.9],
                [0.7, 0.3],
                [0.9, 0.8],
            ]
        )
        y_train = np.asarray([0, 0, 0, 0, 1, 1, 1, 1])
        x_val = np.asarray([[-0.8, -0.5], [-0.3, -0.6], [0.3, 0.7], [0.8, 0.5]])
        y_val = np.asarray([0, 0, 1, 1])
        candidates = [
            HamiltonianCandidate(0.6, 0.0, 0.4, "chain"),
            HamiltonianCandidate(1.0, 0.6, 0.8, "chain"),
        ]
        selected, state_cache, screening, finalists = screen_and_select_candidates(
            dataset_name="unit",
            seed=0,
            x_train=x_train,
            y_train=y_train,
            x_val=x_val,
            y_val=y_val,
            candidates=candidates,
            n_qubits=2,
            top_k=2,
        )
        self.assertEqual(set(selected), {"fidelity", "projected"})
        self.assertEqual(len(screening), 4)
        self.assertEqual(len(finalists), 4)
        self.assertEqual(set(state_cache), {candidate.name for candidate in candidates})
        self.assertTrue(all(states.shape == (12, 4) for states in state_cache.values()))


if __name__ == "__main__":
    unittest.main()
