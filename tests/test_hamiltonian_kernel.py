from __future__ import annotations

import unittest

import numpy as np

from hamiltonian_kernel.core import (
    EvolutionConfig,
    bloch_vectors,
    circuit_resources,
    evolve_batch,
    evolve_exact,
    evolve_trotter,
    fidelity_kernel,
    projected_kernel,
    state_infidelity,
)
from hamiltonian_kernel.learning import nearest_correlation_kernel, sample_fidelity_kernel


class HamiltonianEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.x = np.asarray([0.3, -0.8, 0.5], dtype=float)

    def test_exact_and_trotter_states_remain_normalized(self) -> None:
        exact = evolve_exact(self.x, EvolutionConfig(n_qubits=3, method="exact"))
        trotter = evolve_trotter(
            self.x,
            EvolutionConfig(n_qubits=3, method="trotter", trotter_order=2, trotter_steps=4),
        )
        self.assertAlmostEqual(float(np.linalg.norm(exact)), 1.0, places=12)
        self.assertAlmostEqual(float(np.linalg.norm(trotter)), 1.0, places=12)

    def test_more_second_order_steps_reduce_reference_error(self) -> None:
        exact = evolve_exact(self.x, EvolutionConfig(n_qubits=3, method="exact"))[None, :]
        coarse = evolve_trotter(
            self.x,
            EvolutionConfig(n_qubits=3, method="trotter", trotter_order=2, trotter_steps=1),
        )[None, :]
        fine = evolve_trotter(
            self.x,
            EvolutionConfig(n_qubits=3, method="trotter", trotter_order=2, trotter_steps=8),
        )[None, :]
        self.assertLess(float(state_infidelity(exact, fine)[0]), float(state_infidelity(exact, coarse)[0]))

    def test_batch_shape(self) -> None:
        x = np.vstack((self.x, -self.x))
        states = evolve_batch(x, EvolutionConfig(n_qubits=3, method="trotter"))
        self.assertEqual(states.shape, (2, 8))


class KernelTests(unittest.TestCase):
    def setUp(self) -> None:
        x = np.asarray(
            [
                [0.1, -0.2, 0.3],
                [0.4, 0.0, -0.7],
                [-0.8, 0.2, 0.6],
                [0.5, 0.9, -0.1],
            ],
            dtype=float,
        )
        self.states = evolve_batch(x, EvolutionConfig(n_qubits=3, method="trotter", trotter_steps=3))

    def assert_psd(self, kernel: np.ndarray, tolerance: float = 1e-10) -> None:
        self.assertTrue(np.allclose(kernel, kernel.T, atol=1e-12))
        self.assertGreaterEqual(float(np.linalg.eigvalsh(kernel)[0]), -tolerance)

    def test_fidelity_kernel_is_normalized_and_psd(self) -> None:
        kernel = fidelity_kernel(self.states, self.states)
        self.assertTrue(np.allclose(np.diag(kernel), 1.0, atol=1e-12))
        self.assert_psd(kernel)

    def test_projected_kernel_is_normalized_and_psd(self) -> None:
        bloch = bloch_vectors(self.states, n_qubits=3)
        kernel = projected_kernel(bloch, bloch, gamma=1.0)
        self.assertTrue(np.allclose(np.diag(kernel), 1.0, atol=1e-12))
        self.assert_psd(kernel)

    def test_sampled_fidelity_kernel_can_be_repaired(self) -> None:
        exact = fidelity_kernel(self.states, self.states)
        sampled = sample_fidelity_kernel(exact, shots=32, rng=np.random.default_rng(7), symmetric=True)
        repaired = nearest_correlation_kernel(sampled)
        self.assertTrue(np.allclose(np.diag(repaired), 1.0, atol=1e-12))
        self.assert_psd(repaired, tolerance=1e-9)

    def test_second_order_resource_count_merges_adjacent_half_steps(self) -> None:
        resources = circuit_resources(
            EvolutionConfig(n_qubits=4, topology="chain", trotter_order=2, trotter_steps=3),
        )
        self.assertEqual(resources["a_blocks"], 4)
        self.assertEqual(resources["two_qubit_gates"], 24)

    def test_zero_interaction_has_no_logical_two_qubit_gates(self) -> None:
        resources = circuit_resources(
            EvolutionConfig(
                n_qubits=4,
                topology="all_to_all",
                interaction_strength=0.0,
                trotter_order=2,
                trotter_steps=2,
            ),
        )
        self.assertEqual(resources["two_qubit_gates"], 0)


if __name__ == "__main__":
    unittest.main()
