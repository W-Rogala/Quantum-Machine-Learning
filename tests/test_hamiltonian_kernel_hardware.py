from __future__ import annotations

import json
import unittest
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np

from hamiltonian_kernel.core import (
    EvolutionConfig,
    bloch_vectors,
    evolve_trotter,
    fidelity_kernel,
    z_eigenvalues,
)
from hamiltonian_kernel.hardware_circuits import (
    MeasurementEntry,
    allocate_exact_shots,
    analyze_hardware_counts,
    build_measurement_entries,
    build_qiskit_feature_map,
    build_qiskit_measurement_circuit,
    canonical_counts,
    config_to_dict,
)
from hamiltonian_kernel.hardware_providers import (
    _backend_snapshot,
    _ionq_result_counts,
    _pending_entries,
    _save_qiskit_reproducibility_bundle,
    _submitted_circuit_ids,
    _update_state_resource_axes,
    execute_aer,
    execute_pennylane,
    submit_braket,
    submit_ionq,
)
from hamiltonian_kernel.hardware_experiment import _validation_benchmark_source, run_workload
from hamiltonian_kernel.protocol import freeze_protocol, protocol_for_profile


class HardwareCircuitEquivalenceTests(unittest.TestCase):
    def assert_states_equal_up_to_phase(
        self,
        reference: np.ndarray,
        actual: np.ndarray,
        tolerance: float = 1e-11,
    ) -> None:
        overlap = np.vdot(reference, actual)
        aligned = actual * np.exp(-1j * np.angle(overlap))
        self.assertLess(float(np.linalg.norm(reference - aligned)), tolerance)

    def test_qiskit_feature_map_matches_matrix_simulator(self) -> None:
        from qiskit.quantum_info import Statevector

        x = np.asarray([0.2, -0.4, 0.7, -0.1])
        for order, topology in ((1, "chain"), (2, "ring"), (2, "all_to_all")):
            config = EvolutionConfig(
                n_qubits=4,
                evolution_time=1.3,
                interaction_strength=0.6,
                transverse_field=0.4,
                topology=topology,
                method="trotter",
                trotter_order=order,
                trotter_steps=3,
            )
            reference = evolve_trotter(x, config)
            actual = Statevector.from_instruction(build_qiskit_feature_map(x, config)).data
            self.assert_states_equal_up_to_phase(reference, actual)

    def test_compute_uncompute_probability_is_fidelity(self) -> None:
        from qiskit.quantum_info import Statevector

        samples = np.asarray([[0.1, -0.3], [0.6, 0.2]])
        config = EvolutionConfig(
            n_qubits=2,
            evolution_time=0.9,
            interaction_strength=0.5,
            transverse_field=0.7,
            topology="chain",
            method="trotter",
            trotter_order=2,
            trotter_steps=2,
        )
        entry = MeasurementEntry(
            circuit_id="fidelity",
            kind="fidelity",
            shots=100,
            left_index=0,
            right_index=1,
        )
        circuit = build_qiskit_measurement_circuit(entry, samples, config)
        circuit.remove_final_measurements(inplace=True)
        probability = float(Statevector.from_instruction(circuit).probabilities()[0])
        states = np.vstack([evolve_trotter(row, config) for row in samples])
        expected = float(fidelity_kernel(states, states)[0, 1])
        self.assertAlmostEqual(probability, expected, places=12)

    def test_projected_basis_rotations_match_bloch_components(self) -> None:
        from qiskit.quantum_info import Statevector

        samples = np.asarray([[0.25, -0.55]])
        config = EvolutionConfig(
            n_qubits=2,
            evolution_time=1.1,
            interaction_strength=0.4,
            transverse_field=0.8,
            topology="chain",
            method="trotter",
            trotter_order=2,
            trotter_steps=2,
        )
        state = evolve_trotter(samples[0], config)
        expected = bloch_vectors(state[None, :], 2)[0]
        for component, basis in enumerate(("x", "y", "z")):
            entry = MeasurementEntry(
                circuit_id=f"basis_{basis}",
                kind="projected",
                shots=100,
                sample_index=0,
                basis=basis,
            )
            circuit = build_qiskit_measurement_circuit(entry, samples, config)
            circuit.remove_final_measurements(inplace=True)
            probabilities = Statevector.from_instruction(circuit).probabilities()
            observed = probabilities @ z_eigenvalues(2)
            self.assertTrue(np.allclose(observed, expected[:, component], atol=1e-12))

    def test_ibm_measurement_circuit_can_explicitly_reset_each_qubit(self) -> None:
        samples = np.asarray([[0.1, -0.3]])
        config = EvolutionConfig(n_qubits=2)
        entry = MeasurementEntry(
            circuit_id="initialized",
            kind="projected",
            shots=100,
            sample_index=0,
            basis="z",
        )
        circuit = build_qiskit_measurement_circuit(
            entry,
            samples,
            config,
            initialize_qubits=True,
        )
        self.assertEqual(circuit.count_ops()["reset"], config.n_qubits)
        self.assertEqual(
            [instruction.operation.name for instruction in circuit.data[: config.n_qubits]],
            ["reset"] * config.n_qubits,
        )


class HardwareBudgetAndCountsTests(unittest.TestCase):
    def test_exact_budget_and_expected_circuit_counts(self) -> None:
        fidelity = build_measurement_entries("fidelity", 4, 6, 101, seed=5)
        projected = build_measurement_entries("projected", 4, 6, 101, seed=5)
        self.assertEqual(len(fidelity), 20)
        self.assertEqual(
            sum(entry.left_index == entry.right_index for entry in fidelity),
            6,
        )
        self.assertEqual(len(projected), 18)
        self.assertEqual(sum(entry.shots for entry in fidelity), 101)
        self.assertEqual(sum(entry.shots for entry in projected), 101)
        self.assertLessEqual(
            max(entry.shots for entry in fidelity) - min(entry.shots for entry in fidelity),
            1,
        )
        with self.assertRaises(ValueError):
            allocate_exact_shots(20, 19, seed=0)

    def test_count_key_normalization(self) -> None:
        qiskit = canonical_counts({"0001": 7, "0010": 3}, 4, "qiskit")
        braket = canonical_counts({"1000": 7, "0100": 3}, 4, "q0_first")
        self.assertEqual(qiskit, braket)
        self.assertEqual(qiskit, {"1000": 7, "0100": 3})

    def test_resource_axes_use_transpiled_two_qubit_gate_shots(self) -> None:
        state = {
            "batches": [
                {
                    "shots": 11,
                    "circuit_ids": ["a", "b"],
                    "compilation": {"two_qubit_gates_by_circuit": [3, 5]},
                    "qpu_usage": {"quantum_seconds": 0.25},
                }
            ]
        }
        _update_state_resource_axes(state, {"measurement": {"kernel": "fidelity"}})
        self.assertEqual(state["resource_axes"]["circuit_shots"], 22)
        self.assertEqual(state["resource_axes"]["map_executions"], 44)
        self.assertEqual(state["resource_axes"]["two_qubit_gate_shots"], 88)
        self.assertEqual(state["resource_axes"]["qpu_time_seconds"], 0.25)

    def test_qpy_bundle_preserves_isa_layout_and_hashes(self) -> None:
        from qiskit import qpy, transpile
        from qiskit.providers.fake_provider import GenericBackendV2

        backend = GenericBackendV2(
            num_qubits=3,
            basis_gates=["id", "rz", "sx", "x", "cx"],
            coupling_map=[[0, 1], [1, 0], [1, 2], [2, 1]],
            seed=17,
        )
        logical = [
            build_qiskit_feature_map(
                np.asarray([0.2, -0.4]),
                EvolutionConfig(n_qubits=2),
            )
        ]
        compiled = transpile(
            logical,
            backend=backend,
            optimization_level=1,
            seed_transpiler=91,
        )
        with TemporaryDirectory() as temporary:
            bundle = _save_qiskit_reproducibility_bundle(
                Path(temporary),
                batch_index=0,
                circuit_ids=["unit"],
                logical=logical,
                compiled=compiled,
                transpile_seed=91,
                optimization_level=1,
                runtime_options={"execution": {"init_qubits": True}},
                qubit_initialization={"explicit_circuit_reset": True},
                initial_layout=[2, 1],
            )
            self.assertEqual(bundle["transpile_seed"], 91)
            self.assertTrue(bundle["runtime_options"]["execution"]["init_qubits"])
            self.assertTrue(
                bundle["qubit_initialization"]["explicit_circuit_reset"]
            )
            self.assertEqual(bundle["requested_initial_layout"], [2, 1])
            self.assertTrue(bundle["isa_layouts"][0]["present"])
            self.assertEqual(len(bundle["isa_qpy_sha256"]), 64)
            with Path(bundle["isa_qpy"]).open("rb") as handle:
                restored = qpy.load(handle)
            self.assertEqual(len(restored), 1)
            self.assertIsNotNone(restored[0].layout)
            snapshot = _backend_snapshot(backend)
            self.assertEqual(snapshot["target"]["num_qubits"], 3)
            self.assertTrue(snapshot["target"]["instructions"])

    def test_ionq_prefers_exact_per_shot_memory(self) -> None:
        class ResultWithMemory:
            @staticmethod
            def get_memory(index: int) -> list[str]:
                if index != 0:
                    raise IndexError(index)
                return ["01", "10", "01", "11"]

            @staticmethod
            def get_counts(index: int) -> dict[str, int]:
                raise AssertionError("Rounded histogram must not be used when memory exists")

        counts = _ionq_result_counts(ResultWithMemory(), 0, 1)
        self.assertEqual(counts, {"01": 2, "10": 1, "11": 1})
        self.assertEqual(sum(counts.values()), 4)

    def test_resume_skips_persisted_jobs_and_blocks_unknown_submission(self) -> None:
        workload = {
            "measurement": {
                "entries": [
                    {"circuit_id": "a", "shots": 10},
                    {"circuit_id": "b", "shots": 10},
                ]
            }
        }
        state = {"batches": [{"circuit_ids": ["a"], "job_id": "job-a"}]}
        self.assertEqual(_submitted_circuit_ids(state), {"a"})
        self.assertEqual(
            [entry["circuit_id"] for entry in _pending_entries(workload, state)],
            ["b"],
        )
        unknown = {"batches": [{"circuit_ids": ["a"], "job_id": None}]}
        with self.assertRaises(RuntimeError):
            _submitted_circuit_ids(unknown)

    def test_validation_pilot_is_bound_to_completed_full_protocol(self) -> None:
        protocol = protocol_for_profile("full")
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            protocol_path = root / "protocol.json"
            frozen = freeze_protocol(protocol_path, protocol)
            split_path = root / "split.npz"
            np.savez_compressed(
                split_path,
                protocol_hash=np.asarray(frozen["protocol_hash"]),
                train_indices=np.arange(8),
                test_indices=np.arange(8, 12),
                x_train=np.zeros((8, 4)),
                y_train=np.asarray([0, 0, 0, 0, 1, 1, 1, 1]),
                x_test=np.zeros((4, 4)),
                y_test=np.asarray([0, 0, 1, 1]),
            )
            completion_path = root / "completion.json"
            completion_path.write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "protocol_hash": frozen["protocol_hash"],
                        "qpu_gate": "eligible_for_separate_reproducible_pilot_after_review",
                    }
                ),
                encoding="utf-8",
            )
            results_path = root / "outer_results.csv"
            configuration = {
                "candidate": {
                    "evolution_time": 1.0,
                    "interaction_strength": 0.4,
                    "transverse_field": 0.7,
                    "topology": "chain",
                },
                "candidate_name": "unit",
                "gamma": None,
                "regularization": 0.01,
            }
            results_path.write_text(
                "protocol_hash,dataset,outer_repeat,outer_fold,family,evaluation_regime,"
                "configuration_id,configuration_json,split_artifact\n"
                + f'{frozen["protocol_hash"]},moons,0,0,fidelity,ideal_statevector,cfg,'
                + '"'
                + json.dumps(configuration, separators=(",", ":")).replace('"', '""')
                + f'","{split_path}"\n',
                encoding="utf-8",
            )
            args = SimpleNamespace(
                protocol=protocol_path,
                benchmark_completion=completion_path,
                outer_results=results_path,
                dataset="moons",
                outer_repeat=0,
                outer_fold=0,
                budget=20_000,
                train_per_class=3,
                test_per_class=2,
                sample_seed=20260901,
                measurement_seed=20260902,
                n_qubits=4,
                trotter_order=2,
                trotter_steps=2,
                kernel="fidelity",
                evolution_time=None,
                interaction_strength=None,
                transverse_field=None,
                topology=None,
            )
            source = _validation_benchmark_source(args)
            self.assertEqual(source["study_binding"]["protocol_hash"], frozen["protocol_hash"])
            self.assertEqual(source["study_binding"]["transpile_seed"], 20260903)
            self.assertEqual(source["configuration"]["candidate_name"], "unit")


class HardwareLocalIntegrationTests(unittest.TestCase):
    def test_remote_submission_requires_explicit_confirmation(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workload_path = root / "workload.json"
            workload_path.write_text(
                json.dumps({"workload_id": "confirmation-test"}),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                workload=workload_path,
                output_dir=root / "ibm",
                provider="ibm",
                allow_existing=False,
                dry_run=False,
                confirm_submit=False,
            )
            with self.assertRaisesRegex(ValueError, "confirm-submit"):
                run_workload(args)

    def test_aer_execution_is_complete_and_analyzable(self) -> None:
        config = EvolutionConfig(
            n_qubits=2,
            evolution_time=0.8,
            interaction_strength=0.5,
            transverse_field=0.6,
            topology="chain",
            method="trotter",
            trotter_order=2,
            trotter_steps=2,
        )
        train_x = np.asarray(
            [[-0.8, -0.5], [-0.6, 0.1], [0.5, -0.2], [0.8, 0.6]],
            dtype=float,
        )
        test_x = np.asarray([[-0.7, -0.2], [0.7, 0.3]], dtype=float)
        entries = build_measurement_entries("projected", 4, 6, 900, seed=9)
        workload = {
            "workload_id": "unit-hardware",
            "model": {
                "evolution_config": config_to_dict(config),
                "gamma": 1.0,
                "regularization": 0.01,
            },
            "samples": {
                "train": {"x": train_x.tolist(), "y": [0, 0, 1, 1]},
                "test": {"x": test_x.tolist(), "y": [0, 1]},
            },
            "measurement": {
                "kernel": "projected",
                "total_budget": 900,
                "entries": [asdict(entry) for entry in entries],
            },
        }
        state, counts = execute_aer(workload, seed=12, optimization_level=0)
        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["not_a_qpu_execution"])
        self.assertEqual(state["resource_axes"]["circuit_shots"], 900)
        self.assertEqual(state["resource_axes"]["map_executions"], 900)
        self.assertGreaterEqual(state["resource_axes"]["two_qubit_gate_shots"], 0)
        self.assertIsNone(state["resource_axes"]["qpu_time_seconds"])
        self.assertIsNone(state["resource_axes"]["qpu_credits"])
        self.assertEqual(len(counts), len(entries))
        for entry in entries:
            self.assertEqual(sum(counts[entry.circuit_id].values()), entry.shots)

        analysis = analyze_hardware_counts(workload, counts)
        self.assertEqual(np.asarray(analysis["train_kernel"]).shape, (4, 4))
        self.assertEqual(np.asarray(analysis["test_kernel"]).shape, (2, 4))
        self.assertGreaterEqual(
            float(analysis["train_kernel_diagnostics"]["kernel_min_eigenvalue"]),
            -1e-10,
        )

    def test_fidelity_analysis_uses_measured_diagonal_and_publishes_stages(self) -> None:
        config = EvolutionConfig(n_qubits=2, trotter_steps=1)
        entries = build_measurement_entries("fidelity", 2, 4, 900, seed=2)
        workload = {
            "workload_id": "unit-fidelity-diagonal",
            "model": {
                "evolution_config": config_to_dict(config),
                "regularization": 0.01,
            },
            "samples": {
                "train": {"x": [[-0.3, 0.1], [0.4, -0.2]], "y": [0, 1]},
                "test": {"x": [[0.2, 0.5], [-0.1, -0.4]], "y": [0, 1]},
            },
            "measurement": {
                "kernel": "fidelity",
                "total_budget": 900,
                "entries": [asdict(entry) for entry in entries],
            },
        }
        diagonal_probabilities = {0: 0.8, 1: 0.9, 2: 0.7, 3: 0.75}
        counts: dict[str, dict[str, int]] = {}
        for entry in entries:
            if entry.left_index == entry.right_index:
                probability = diagonal_probabilities[int(entry.left_index)]
            else:
                probability = 0.25 + 0.05 * int(entry.left_index)
            zero = int(round(entry.shots * probability))
            counts[entry.circuit_id] = {"00": zero, "10": entry.shots - zero}
        analysis = analyze_hardware_counts(workload, counts)
        raw_diagonal = np.asarray(analysis["kernel_matrices"]["raw_diagonal"])
        np.testing.assert_allclose(raw_diagonal, [0.8, 0.9, 0.7, 0.75])
        self.assertEqual(
            set(analysis["kernel_matrices"]),
            {
                "raw_train",
                "raw_test",
                "raw_diagonal",
                "psd_train",
                "spectral_train",
                "spectral_test",
                "raw_eigenvalues",
                "psd_eigenvalues",
                "spectral_eigenvalues",
            },
        )
        self.assertGreaterEqual(
            float(np.linalg.eigvalsh(analysis["kernel_matrices"]["psd_train"])[0]),
            -1e-10,
        )

    def test_pennylane_is_explicitly_software_validation(self) -> None:
        config = EvolutionConfig(
            n_qubits=1,
            evolution_time=0.5,
            interaction_strength=0.0,
            transverse_field=0.4,
            topology="chain",
            method="trotter",
            trotter_order=1,
            trotter_steps=1,
        )
        entries = build_measurement_entries("projected", 1, 2, 60, seed=3)
        workload = {
            "workload_id": "unit-pennylane",
            "model": {"evolution_config": config_to_dict(config)},
            "samples": {
                "train": {"x": [[-0.2]], "y": [0]},
                "test": {"x": [[0.3]], "y": [1]},
            },
            "measurement": {"entries": [asdict(entry) for entry in entries]},
        }
        state, counts = execute_pennylane(workload, "default.qubit", seed=17)
        self.assertTrue(state["not_a_qpu_execution"])
        self.assertIn("not Xanadu", state["warning"])
        self.assertEqual(state["seed"], 17)
        self.assertEqual(sum(sum(row.values()) for row in counts.values()), 60)

    def test_braket_dry_run_is_prepared_not_compiled(self) -> None:
        config = EvolutionConfig(
            n_qubits=2,
            evolution_time=0.7,
            interaction_strength=0.5,
            transverse_field=0.4,
            topology="chain",
            method="trotter",
            trotter_order=2,
            trotter_steps=1,
        )
        entries = [
            MeasurementEntry(
                circuit_id="braket_prepare",
                kind="projected",
                shots=20,
                sample_index=0,
                basis="z",
            )
        ]
        workload = {
            "workload_id": "unit-braket-dry-run",
            "model": {"evolution_config": config_to_dict(config)},
            "samples": {
                "train": {"x": [[-0.2, 0.1], [0.4, -0.5]], "y": [0, 1]},
                "test": {"x": [[0.3, 0.2]], "y": [1]},
            },
            "measurement": {"entries": [asdict(entry) for entry in entries]},
        }
        with TemporaryDirectory() as temporary:
            state = submit_braket(
                workload,
                device_arn="arn:aws:braket:us-west-1::device/qpu/rigetti/Ankaa-3",
                s3_bucket=None,
                s3_prefix="unit",
                dry_run=True,
                state_path=Path(temporary) / "execution.json",
            )
        self.assertEqual(state["status"], "prepared_only")
        self.assertTrue(state["not_a_qpu_execution"])
        self.assertTrue(all(batch["status"] == "prepared_only" for batch in state["batches"]))
        self.assertTrue(all(batch["job_id"] is None for batch in state["batches"]))

    def test_offline_ionq_forte_compiles_entanglement_to_native_zz(self) -> None:
        config = EvolutionConfig(
            n_qubits=2,
            evolution_time=0.7,
            interaction_strength=0.5,
            transverse_field=0.4,
            topology="chain",
            method="trotter",
            trotter_order=2,
            trotter_steps=1,
        )
        entries = [
            MeasurementEntry(
                circuit_id="ionq_native_zz",
                kind="projected",
                shots=20,
                sample_index=0,
                basis="z",
            )
        ]
        workload = {
            "workload_id": "unit-ionq-native-dry-run",
            "model": {"evolution_config": config_to_dict(config)},
            "samples": {
                "train": {"x": [[-0.2, 0.1], [0.4, -0.5]], "y": [0, 1]},
                "test": {"x": [[0.3, 0.2]], "y": [1]},
            },
            "measurement": {"entries": [asdict(entry) for entry in entries]},
        }
        with TemporaryDirectory() as temporary:
            state = submit_ionq(
                workload,
                backend_name="offline.forte",
                gateset="native",
                optimization_level=0,
                max_circuits_per_job=100,
                dry_run=True,
                state_path=Path(temporary) / "execution.json",
            )
        operation_totals: dict[str, int] = {}
        for batch in state["batches"]:
            for name, count in batch["compilation"]["operation_totals"].items():
                operation_totals[name] = operation_totals.get(name, 0) + int(count)
        self.assertEqual(state["status"], "compiled_only")
        self.assertTrue(state["offline_target"])
        self.assertTrue(state["not_a_qpu_execution"])
        self.assertGreater(operation_totals.get("zz", 0), 0)


if __name__ == "__main__":
    unittest.main()
