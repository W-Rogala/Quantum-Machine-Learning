from __future__ import annotations

import argparse
import inspect
import unittest

import numpy as np

from hamiltonian_kernel.data import PreparedData
from photonic_kernel.core import X8GBSConfig, gbs_distribution, sample_distribution
from photonic_kernel.experiment import (
    KernelSelection,
    PhotonicCandidate,
    SelectionResult,
    analyze_records,
    build_workload,
    select_photonic_model,
    workload_identifier,
)
from photonic_kernel.xanadu_x8 import (
    _result_samples,
    program_specification,
    submit_command,
    validate_workload,
)


class _FakeResultJob:
    result = {"output": [np.zeros((3, 8), dtype=int)]}


class PhotonicKernelExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = PreparedData(
            name="synthetic",
            x_train=np.asarray(
                [
                    [-0.8, -0.2, 0.1, 0.4],
                    [-0.6, 0.1, -0.2, 0.2],
                    [0.6, -0.1, 0.2, -0.3],
                    [0.9, 0.3, -0.1, -0.5],
                ]
            ),
            x_val=np.asarray([[-0.7, 0.0, 0.0, 0.3], [0.7, 0.0, 0.0, -0.3]]),
            x_test=np.asarray([[-0.65, -0.1, 0.1, 0.2], [0.75, 0.2, -0.2, -0.4]]),
            y_train=np.asarray([0, 0, 1, 1]),
            y_val=np.asarray([0, 1]),
            y_test=np.asarray([0, 1]),
            pca_explained_ratio=1.0,
        )
        candidate = PhotonicCandidate(0.35, 0.6)
        self.selection = SelectionResult(
            candidate=candidate,
            hellinger=KernelSelection(None, 1e-3, 0.4, 0.75),
            moment_rbf=KernelSelection(0.03, 1e-2, 0.5, 0.75),
            event_hellinger=KernelSelection(None, 1e-3, 0.35, 0.75),
            orbit_hellinger=KernelSelection(None, 1e-2, 0.45, 0.75),
            screening_rows=(),
        )
        self.config = candidate.config(reservoir_seed=5, max_total_photons=2)
        self.workload = build_workload(
            self.data,
            np.arange(4),
            np.arange(2),
            self.selection,
            self.config,
            budget=601,
            dataset_seed=11,
            sample_seed=12,
            measurement_seed=13,
            profile="test",
        )

    def test_selection_api_cannot_receive_test_data(self) -> None:
        parameters = set(inspect.signature(select_photonic_model).parameters)
        self.assertFalse(any("test" in name for name in parameters))
        result = select_photonic_model(
            self.data.x_train,
            self.data.y_train,
            self.data.x_val,
            self.data.y_val,
            [PhotonicCandidate(0.35, 0.6)],
            reservoir_seed=5,
            max_total_photons=2,
        )
        self.assertEqual(result.candidate, PhotonicCandidate(0.35, 0.6))

    def test_workload_has_exact_budget_and_stable_identifier(self) -> None:
        entries = self.workload["measurement"]["entries"]
        self.assertEqual(sum(int(row["shots"]) for row in entries), 601)
        self.assertLessEqual(
            max(int(row["shots"]) for row in entries)
            - min(int(row["shots"]) for row in entries),
            1,
        )
        self.assertEqual(self.workload["dataset"]["seed"], 11)
        self.assertEqual(self.workload["samples"]["sample_seed"], 12)
        self.assertEqual(self.workload["workload_id"], workload_identifier(self.workload))
        changed = dict(self.workload)
        changed["created_utc"] = "different"
        changed["environment"] = {"different": True}
        self.assertEqual(workload_identifier(changed), self.workload["workload_id"])

    def test_x8_program_specification_repeats_the_same_unitary(self) -> None:
        validation = validate_workload(self.workload)
        self.assertTrue(validation["passed"], validation["problems"])
        specification = program_specification(
            self.workload["measurement"]["entries"][0],
            self.workload,
        )
        operations = specification["operations"]
        self.assertEqual([row["modes"] for row in operations[:4]], [[0, 4], [1, 5], [2, 6], [3, 7]])
        self.assertEqual(operations[4]["matrix"], operations[5]["matrix"])
        self.assertEqual(operations[-1]["modes"], list(range(8)))

    def test_one_record_set_is_analyzed_as_both_kernels(self) -> None:
        rng = np.random.default_rng(19)
        distributions = [
            gbs_distribution(np.asarray(entry["x"]), self.config)
            for entry in self.workload["measurement"]["entries"]
        ]
        records = {
            entry["circuit_id"]: sample_distribution(distribution, int(entry["shots"]), rng)
            for entry, distribution in zip(
                self.workload["measurement"]["entries"],
                distributions,
            )
        }
        analysis = analyze_records(self.workload, records, distributions)
        self.assertTrue(analysis["same_raw_records_for_all_kernels"])
        self.assertTrue(analysis["overflow_is_explicit_feature"])
        self.assertEqual(analysis["shot_accounting"]["observed_total"], 601)
        self.assertEqual(
            set(analysis["finite_shot"]),
            {"hellinger", "moment_rbf", "event_hellinger", "orbit_hellinger"},
        )
        for name in ("hellinger", "moment_rbf", "event_hellinger", "orbit_hellinger"):
            kernel = np.asarray(analysis["kernels"][name]["train"])
            self.assertGreaterEqual(float(np.linalg.eigvalsh(kernel).min()), -1e-10)

    def test_remote_submission_requires_explicit_confirmation(self) -> None:
        arguments = argparse.Namespace(confirm_submit=False)
        with self.assertRaisesRegex(RuntimeError, "confirm-submit"):
            submit_command(arguments)

    def test_retired_public_cloud_is_blocked_after_confirmation(self) -> None:
        arguments = argparse.Namespace(
            confirm_submit=True,
            target="X8",
            allow_retired_cloud_endpoint=False,
        )
        with self.assertRaisesRegex(RuntimeError, "no longer available"):
            submit_command(arguments)

    def test_xcc_result_shape_extraction(self) -> None:
        samples = _result_samples(_FakeResultJob())
        self.assertEqual(samples.shape, (3, 8))


if __name__ == "__main__":
    unittest.main()
