from __future__ import annotations

import unittest

import numpy as np

from quantum_reservoir.core import QuantumReservoir, ReservoirConfig, trotter_unitary
from quantum_reservoir.ibm_hardware import (
    append_trotter_evolution,
    build_feature_circuits,
    build_replay_circuit,
    compile_for_backend,
    decode_feature_counts,
    observable_names,
    ridge_readout,
    run_local_sampler,
)


class IBMHardwareCircuitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ReservoirConfig(
            n_qubits=3,
            disorder_seed=5,
            method="trotter",
            trotter_order=2,
            trotter_steps=2,
        )

    def test_trotter_circuit_matches_dense_unitary(self) -> None:
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Operator

        circuit = QuantumCircuit(self.config.n_qubits)
        append_trotter_evolution(circuit, self.config)
        hardware_unitary = np.asarray(Operator(circuit).data)
        dense_unitary = trotter_unitary(self.config)
        overlap = np.trace(dense_unitary.conj().T @ hardware_unitary) / len(dense_unitary)
        self.assertGreater(abs(overlap), 1.0 - 1e-11)

    def test_replay_window_caps_number_of_resets(self) -> None:
        circuit = build_replay_circuit(
            np.linspace(0.0, 1.0, 10),
            time_index=9,
            config=self.config,
            history_window=4,
        )
        self.assertEqual(int(circuit.count_ops().get("reset", 0)), 4)
        self.assertEqual(circuit.metadata["history_start"], 6)
        self.assertEqual(circuit.metadata["history_length"], 4)

    def test_two_measurement_groups_per_time_point(self) -> None:
        circuits, records = build_feature_circuits([0.2, 0.4, 0.8], self.config, None)
        self.assertEqual(len(circuits), 6)
        self.assertEqual([row["basis"] for row in records], ["Z", "X"] * 3)
        self.assertTrue(all(circuit.num_clbits == self.config.n_qubits for circuit in circuits))

    def test_decode_counts_uses_dense_feature_order(self) -> None:
        config = ReservoirConfig(n_qubits=2, method="trotter", trotter_order=2, trotter_steps=1)
        records = [{"time_index": 0, "basis": "Z"}, {"time_index": 0, "basis": "X"}]
        features, errors = decode_feature_counts(
            [{"00": 100}, {"11": 100}],
            records,
            config,
        )
        self.assertEqual(observable_names(config), ("X0", "Z0", "X1", "Z1", "Z0Z1"))
        self.assertTrue(np.allclose(features[0], [-1.0, 1.0, -1.0, 1.0, 1.0]))
        self.assertTrue(np.allclose(errors, 0.0))

    def test_aer_sampler_agrees_with_dense_reset_channel(self) -> None:
        config = ReservoirConfig(
            n_qubits=2,
            disorder_seed=3,
            method="trotter",
            trotter_order=2,
            trotter_steps=2,
        )
        inputs = np.asarray([0.15, 0.72, 0.31])
        circuits, records = build_feature_circuits(inputs, config, None)
        counts = run_local_sampler(circuits, shots=100_000, seed=91)
        sampled, _ = decode_feature_counts(counts, records, config)
        dense, _ = QuantumReservoir(config).transform(inputs)
        self.assertTrue(np.allclose(sampled, dense, atol=0.018), (sampled, dense))

    def test_compiles_reset_circuit_to_fake_ibm_isa(self) -> None:
        from qiskit_ibm_runtime.fake_provider import FakeFez

        circuits, _ = build_feature_circuits([0.2, 0.7], self.config, history_window=2)
        backend = FakeFez()
        compiled = compile_for_backend(circuits, backend, optimization_level=1, seed_transpiler=4)
        allowed = set(backend.operation_names)
        self.assertEqual(len(compiled), len(circuits))
        for circuit in compiled:
            self.assertLessEqual(set(circuit.count_ops()), allowed)


class HardwareReadoutTests(unittest.TestCase):
    def test_temporal_ridge_readout_returns_finite_metrics(self) -> None:
        rng = np.random.default_rng(8)
        inputs = rng.uniform(size=60)
        features = np.column_stack((inputs**2, np.sin(inputs), rng.normal(size=60)))
        targets = 0.3 + 0.5 * inputs + 0.2 * features[:, 0]
        metrics, prediction = ridge_readout(inputs, features, targets, (5, 30, 10, 15))
        self.assertEqual(prediction.shape, (15,))
        self.assertTrue(all(np.isfinite(value) for value in metrics.values()))
        self.assertLess(metrics["test_nrmse"], 0.05)


if __name__ == "__main__":
    unittest.main()

