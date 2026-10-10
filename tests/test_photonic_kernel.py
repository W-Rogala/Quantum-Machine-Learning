from __future__ import annotations

import math
import unittest

import numpy as np

from photonic_kernel.core import (
    DetectorConfig,
    X8GBSConfig,
    allocate_exact_shots,
    apply_detector_model,
    apply_uniform_loss,
    event_orbit_features,
    features_from_records,
    gbs_distribution,
    gbs_pattern_probability,
    hafnian,
    hellinger_kernel,
    ideal_features,
    moment_kernel,
    sample_distribution,
    sample_record_from_array,
    standardize_moments,
    x8_adjacency,
    x8_interferometer,
)
from photonic_kernel.robustness import cutoff_loss_detector_sweep


class PhotonicKernelCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = X8GBSConfig(
            squeezing=(0.35, 0.4, 0.45, 0.5),
            phase_scale=0.8,
            reservoir_seed=17,
            max_total_photons=4,
        )
        self.x = np.asarray([-0.8, -0.2, 0.3, 0.9])

    def test_hafnian_known_cases(self) -> None:
        self.assertEqual(hafnian(np.empty((0, 0))), 1.0 + 0.0j)
        self.assertEqual(hafnian(np.asarray([[0.0, 2.5], [2.5, 0.0]])), 2.5)
        matrix = np.asarray(
            [
                [0.0, 1.0, 2.0, 3.0],
                [1.0, 0.0, 4.0, 5.0],
                [2.0, 4.0, 0.0, 6.0],
                [3.0, 5.0, 6.0, 0.0],
            ]
        )
        self.assertAlmostEqual(hafnian(matrix).real, 1.0 * 6.0 + 2.0 * 5.0 + 3.0 * 4.0)

    def test_two_mode_squeezed_vacuum_probability(self) -> None:
        squeezing = 0.43
        amplitude = math.tanh(squeezing)
        adjacency = np.asarray([[0.0, amplitude], [amplitude, 0.0]])
        for photons in range(4):
            expected = (1.0 - amplitude**2) * amplitude ** (2 * photons)
            observed = gbs_pattern_probability(
                adjacency,
                np.asarray([photons, photons]),
            )
            self.assertAlmostEqual(observed, expected, places=13)
        self.assertEqual(gbs_pattern_probability(adjacency, np.asarray([1, 0])), 0.0)

    def test_x8_feature_map_respects_physical_constraints(self) -> None:
        unitary = x8_interferometer(self.x, self.config)
        np.testing.assert_allclose(unitary.conj().T @ unitary, np.eye(4), atol=1e-12)
        adjacency = x8_adjacency(self.x, self.config)
        np.testing.assert_allclose(adjacency, adjacency.T, atol=1e-12)
        self.assertLess(float(np.linalg.svd(adjacency, compute_uv=False)[0]), 1.0)
        changed = x8_adjacency(self.x + np.asarray([0.1, 0.0, 0.0, 0.0]), self.config)
        self.assertFalse(np.allclose(adjacency, changed))

    def test_distribution_is_normalized_inside_and_outside_window(self) -> None:
        first = gbs_distribution(self.x, self.config)
        second = gbs_distribution(-self.x, self.config)
        self.assertAlmostEqual(
            first.acceptance_probability + first.rejected_probability,
            1.0,
            places=12,
        )
        self.assertGreater(first.acceptance_probability, 0.0)
        self.assertLess(first.acceptance_probability, 1.0)
        # A passive interferometer preserves the total photon-number distribution.
        self.assertAlmostEqual(
            first.acceptance_probability,
            second.acceptance_probability,
            places=11,
        )
        odd = first.patterns.sum(axis=1) % 2 == 1
        np.testing.assert_allclose(first.probabilities[odd], 0.0, atol=1e-15)

    def test_one_sample_stream_builds_two_psd_kernels(self) -> None:
        distributions = [
            gbs_distribution(self.x, self.config),
            gbs_distribution(-self.x, self.config),
            gbs_distribution(np.roll(self.x, 1), self.config),
        ]
        rng = np.random.default_rng(9)
        records = [sample_distribution(row, 4000, rng) for row in distributions]
        hellinger, moments, acceptance = features_from_records(
            records,
            self.config.max_total_photons,
        )
        standardized, = standardize_moments(moments)
        kernels = (
            hellinger_kernel(hellinger, hellinger),
            moment_kernel(standardized, standardized, gamma=0.1),
        )
        for kernel in kernels:
            np.testing.assert_allclose(kernel, kernel.T, atol=1e-12)
            self.assertGreaterEqual(float(np.linalg.eigvalsh(kernel).min()), -1e-10)
            np.testing.assert_allclose(np.diag(kernel), 1.0, atol=1e-12)
        self.assertTrue(np.all((acceptance > 0.0) & (acceptance <= 1.0)))

    def test_finite_shot_features_converge_to_ideal_features(self) -> None:
        distributions = [
            gbs_distribution(self.x, self.config),
            gbs_distribution(-self.x, self.config),
        ]
        ideal_hellinger, ideal_moments, _ = ideal_features(distributions)
        records = [
            sample_distribution(row, 200_000, np.random.default_rng(index))
            for index, row in enumerate(distributions)
        ]
        sampled_hellinger, sampled_moments, _ = features_from_records(
            records,
            self.config.max_total_photons,
        )
        sampled_probabilities = sampled_hellinger**2
        ideal_probabilities = ideal_hellinger**2
        self.assertLess(float(np.max(np.abs(sampled_probabilities - ideal_probabilities))), 0.01)
        self.assertLess(float(np.max(np.abs(sampled_moments - ideal_moments))), 0.03)

    def test_budget_and_hardware_sample_accounting(self) -> None:
        allocation = allocate_exact_shots(10_003, 7, seed=4)
        self.assertEqual(int(allocation.sum()), 10_003)
        self.assertLessEqual(int(allocation.max() - allocation.min()), 1)
        samples = np.asarray(
            [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [1, 0, 0, 0, 0, 0, 0, 0],
                [1, 1, 1, 1, 1, 0, 0, 0],
            ]
        )
        record = sample_record_from_array(samples, max_total_photons=4)
        self.assertEqual(record["shots"], 3)
        self.assertEqual(record["accepted_shots"], 2)
        self.assertEqual(record["rejected_shots"], 1)
        self.assertEqual(record["overflow_shots"], 1)
        self.assertIn("1,0,0,0,0,0,0,0", record["histogram"])
        self.assertIn("1,1,1,1,1,0,0,0", record["overflow_histogram"])

    def test_overflow_is_an_explicit_normalized_feature(self) -> None:
        samples = np.asarray(
            [
                [0, 0, 0, 0, 0, 0, 0, 0],
                [1, 0, 0, 0, 0, 0, 0, 0],
                [2, 2, 2, 0, 0, 0, 0, 0],
            ]
        )
        record = sample_record_from_array(samples, max_total_photons=4)
        hellinger, moments, acceptance = features_from_records([record], 4)
        self.assertAlmostEqual(float(np.sum(hellinger[0] ** 2)), 1.0)
        self.assertAlmostEqual(float(hellinger[0, -1] ** 2), 1.0 / 3.0)
        self.assertAlmostEqual(float(moments[0, -1]), 1.0 / 3.0)
        self.assertAlmostEqual(float(acceptance[0]), 2.0 / 3.0)

    def test_loss_and_detector_models(self) -> None:
        samples = np.asarray([[3, 2, 1, 0, 0, 0, 0, 0]] * 20)
        lost = apply_uniform_loss(samples, 0.0, np.random.default_rng(3))
        np.testing.assert_array_equal(lost, np.zeros_like(samples))
        threshold = apply_detector_model(
            samples,
            DetectorConfig("threshold"),
            np.random.default_rng(4),
        )
        self.assertTrue(np.all((threshold == 0) | (threshold == 1)))
        saturated = apply_detector_model(
            samples,
            DetectorConfig("pnr_saturation", saturation_count=2),
            np.random.default_rng(5),
        )
        self.assertEqual(int(saturated.max()), 2)

    def test_event_orbit_features_and_cutoff_sweep_share_raw_events(self) -> None:
        batches = [
            np.asarray(
                [
                    [0, 0, 0, 0, 0, 0, 0, 0],
                    [1, 1, 0, 0, 0, 0, 0, 0],
                    [2, 2, 1, 0, 0, 0, 0, 0],
                    [3, 2, 2, 0, 0, 0, 0, 0],
                ]
            ),
            np.asarray(
                [
                    [0, 0, 0, 0, 0, 0, 0, 0],
                    [2, 0, 0, 0, 0, 0, 0, 0],
                    [1, 1, 1, 1, 0, 0, 0, 0],
                    [2, 2, 2, 2, 0, 0, 0, 0],
                ]
            ),
        ]
        records = [sample_record_from_array(batch, 4) for batch in batches]
        grouped = event_orbit_features(records, 4)
        np.testing.assert_allclose(grouped.event.sum(axis=1), 1.0)
        np.testing.assert_allclose(grouped.orbit.sum(axis=1), 1.0)
        rows, matrices = cutoff_loss_detector_sweep(
            batches,
            cutoffs=(2, 4, 6),
            transmissivities=(1.0,),
            detectors=(DetectorConfig("pnr"),),
            seed=10,
        )
        overflow = [float(row["overflow_rate_mean"]) for row in rows]
        self.assertEqual(overflow, sorted(overflow, reverse=True))
        self.assertEqual(len(matrices), 3)
        self.assertTrue(all(bool(row["kernels_psd"]) for row in rows))


if __name__ == "__main__":
    unittest.main()
