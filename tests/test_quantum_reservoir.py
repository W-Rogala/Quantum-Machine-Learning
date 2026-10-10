from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np

from quantum_reservoir.benchmarks import benchmark_suite, mackey_glass, narma10
from quantum_reservoir.core import (
    QuantumReservoir,
    ReservoirConfig,
    circuit_resources,
    exact_unitary,
    inject_input,
    process_infidelity,
    trotter_unitary,
)
from quantum_reservoir.experiment import SplitConfig, evaluate_configuration


class BenchmarkTests(unittest.TestCase):
    def test_benchmarks_have_aligned_finite_arrays(self) -> None:
        for benchmark in (narma10(250, seed=3), mackey_glass(250, horizon=5)):
            self.assertEqual(benchmark.inputs.shape, (250,))
            self.assertEqual(benchmark.targets.shape, (250,))
            self.assertTrue(np.all(np.isfinite(benchmark.inputs)))
            self.assertTrue(np.all(np.isfinite(benchmark.targets)))
            self.assertGreater(float(np.std(benchmark.targets)), 0.0)
            self.assertGreaterEqual(float(np.min(benchmark.inputs)), 0.0)
            self.assertLessEqual(float(np.max(benchmark.inputs)), 1.0)

    def test_suite_uses_requested_length(self) -> None:
        suite = benchmark_suite(length=275, seed=9)
        self.assertEqual({len(item.inputs) for item in suite}, {275})


class ReservoirEvolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.exact_config = ReservoirConfig(n_qubits=3, disorder_seed=5, method="exact")

    def test_input_injection_preserves_density_trace(self) -> None:
        density = np.eye(8, dtype=np.complex128) / 8.0
        injected = inject_input(density, 0.37)
        self.assertAlmostEqual(float(np.trace(injected).real), 1.0, places=12)
        self.assertTrue(np.allclose(injected, injected.conj().T, atol=1e-12))
        self.assertGreaterEqual(float(np.linalg.eigvalsh(injected)[0]), -1e-12)

    def test_second_order_trotter_converges_to_exact(self) -> None:
        reference = exact_unitary(self.exact_config)
        coarse = trotter_unitary(
            replace(self.exact_config, method="trotter", trotter_order=2, trotter_steps=1)
        )
        fine = trotter_unitary(
            replace(self.exact_config, method="trotter", trotter_order=2, trotter_steps=8)
        )
        self.assertLess(process_infidelity(reference, fine), process_infidelity(reference, coarse))

    def test_transform_is_deterministic_and_finite(self) -> None:
        inputs = np.linspace(0.0, 1.0, 30)
        first, _ = QuantumReservoir(self.exact_config).transform(inputs)
        second, _ = QuantumReservoir(self.exact_config).transform(inputs)
        self.assertEqual(first.shape, (30, 9))
        self.assertTrue(np.all(np.isfinite(first)))
        self.assertTrue(np.allclose(first, second, atol=1e-12))

    def test_resource_count_increases_with_trotter_steps(self) -> None:
        coarse = circuit_resources(
            replace(self.exact_config, method="trotter", trotter_order=2, trotter_steps=1)
        )
        fine = circuit_resources(
            replace(self.exact_config, method="trotter", trotter_order=2, trotter_steps=4)
        )
        self.assertLess(int(coarse["two_qubit_gates"]), int(fine["two_qubit_gates"]))


class ExperimentTests(unittest.TestCase):
    def test_small_exact_and_trotter_evaluations_share_target(self) -> None:
        split = SplitConfig(washout=20, train=100, validation=50, test=80)
        benchmark = narma10(split.total, seed=4)
        exact_config = ReservoirConfig(n_qubits=3, disorder_seed=7, method="exact")
        reference = exact_unitary(exact_config)
        exact_record, exact_target, _ = evaluate_configuration(
            benchmark,
            exact_config,
            split,
            (1e-6, 1e-3, 1.0),
            reference,
        )
        trotter_record, trotter_target, _ = evaluate_configuration(
            benchmark,
            replace(exact_config, method="trotter", trotter_order=2, trotter_steps=2),
            split,
            (1e-6, 1e-3, 1.0),
            reference,
        )
        self.assertTrue(np.allclose(exact_target, trotter_target))
        self.assertTrue(np.isfinite(float(exact_record["test_nrmse"])))
        self.assertTrue(np.isfinite(float(trotter_record["test_nrmse"])))
        self.assertGreater(float(trotter_record["process_infidelity"]), 0.0)


if __name__ == "__main__":
    unittest.main()
