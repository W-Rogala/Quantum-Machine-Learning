from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

import numpy as np


X8_MODES = 8
X8_HALF_MODES = 4


@dataclass(frozen=True)
class X8GBSConfig:
    squeezing: tuple[float, float, float, float] = (0.55, 0.55, 0.55, 0.55)
    phase_scale: float = 1.0
    reservoir_seed: int = 20260817
    max_total_photons: int = 6

    def validate(self) -> None:
        if len(self.squeezing) != X8_HALF_MODES:
            raise ValueError("X8 requires four two-mode squeezing parameters")
        if any(not 0.0 < float(value) < 1.5 for value in self.squeezing):
            raise ValueError("Each squeezing parameter must be in (0, 1.5)")
        if not 0.0 < self.phase_scale <= 4.0:
            raise ValueError("phase_scale must be in (0, 4]")
        if self.max_total_photons < 2:
            raise ValueError("max_total_photons must be at least 2")


@dataclass(frozen=True)
class GBSDistribution:
    patterns: np.ndarray
    probabilities: np.ndarray
    rejected_probability: float

    @property
    def acceptance_probability(self) -> float:
        return float(self.probabilities.sum())

    @property
    def conditional_probabilities(self) -> np.ndarray:
        acceptance = self.acceptance_probability
        if acceptance <= 0.0:
            raise RuntimeError("The selected photon window has zero probability")
        return self.probabilities / acceptance


@dataclass(frozen=True)
class DetectorConfig:
    model: str = "pnr"
    quantum_efficiency: float = 1.0
    dark_count_mean: float = 0.0
    saturation_count: int | None = None

    def validate(self) -> None:
        if self.model not in {"pnr", "threshold", "pnr_saturation"}:
            raise ValueError(f"Unsupported detector model: {self.model}")
        if not 0.0 <= self.quantum_efficiency <= 1.0:
            raise ValueError("quantum_efficiency must be in [0, 1]")
        if self.dark_count_mean < 0.0:
            raise ValueError("dark_count_mean cannot be negative")
        if self.model == "pnr_saturation":
            if self.saturation_count is None or self.saturation_count < 1:
                raise ValueError("pnr_saturation requires a positive saturation_count")
        elif self.saturation_count is not None:
            raise ValueError("saturation_count is only valid for pnr_saturation")


@dataclass(frozen=True)
class EventOrbitFeatures:
    event: np.ndarray
    orbit: np.ndarray
    event_labels: tuple[str, ...]
    orbit_labels: tuple[str, ...]


def config_to_dict(config: X8GBSConfig) -> dict[str, Any]:
    config.validate()
    return {
        "modes": X8_MODES,
        "squeezing": list(config.squeezing),
        "phase_scale": config.phase_scale,
        "reservoir_seed": config.reservoir_seed,
        "max_total_photons": config.max_total_photons,
    }


def config_from_dict(values: dict[str, Any]) -> X8GBSConfig:
    if int(values.get("modes", X8_MODES)) != X8_MODES:
        raise ValueError("This model targets the eight-mode X8 topology")
    squeezing = tuple(float(value) for value in values["squeezing"])
    if len(squeezing) != X8_HALF_MODES:
        raise ValueError("Expected four squeezing parameters")
    config = X8GBSConfig(
        squeezing=squeezing,  # type: ignore[arg-type]
        phase_scale=float(values["phase_scale"]),
        reservoir_seed=int(values["reservoir_seed"]),
        max_total_photons=int(values["max_total_photons"]),
    )
    config.validate()
    return config


def _haar_unitary(size: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(size, size)) + 1j * rng.normal(size=(size, size))
    unitary, triangular = np.linalg.qr(matrix)
    diagonal = np.diag(triangular)
    phases = np.ones(size, dtype=np.complex128)
    nonzero = np.abs(diagonal) > 1e-15
    phases[nonzero] = diagonal[nonzero] / np.abs(diagonal[nonzero])
    return unitary * phases.conj()[None, :]


@lru_cache(maxsize=32)
def _reservoir_unitaries(seed: int) -> tuple[np.ndarray, np.ndarray]:
    return (
        _haar_unitary(X8_HALF_MODES, seed),
        _haar_unitary(X8_HALF_MODES, seed + 1_000_003),
    )


def x8_interferometer(x: np.ndarray, config: X8GBSConfig) -> np.ndarray:
    """Return the four-mode unitary repeated on both halves of X8."""

    config.validate()
    values = np.asarray(x, dtype=float)
    if values.shape != (X8_HALF_MODES,):
        raise ValueError(f"Expected four encoded features, got {values.shape}")
    if not np.all(np.isfinite(values)):
        raise ValueError("Encoded features must be finite")
    left, right = _reservoir_unitaries(config.reservoir_seed)
    phases = np.exp(1j * np.pi * config.phase_scale * values)
    unitary = right @ np.diag(phases) @ left
    if not np.allclose(unitary.conj().T @ unitary, np.eye(X8_HALF_MODES), atol=1e-12):
        raise AssertionError("Feature interferometer is not unitary")
    return unitary


def x8_adjacency(x: np.ndarray, config: X8GBSConfig) -> np.ndarray:
    """Return the pure-state GBS adjacency matrix after the X8 interferometers."""

    unitary = x8_interferometer(x, config)
    source = np.zeros((X8_MODES, X8_MODES), dtype=np.complex128)
    for mode, squeezing in enumerate(config.squeezing):
        amplitude = math.tanh(float(squeezing))
        source[mode, mode + X8_HALF_MODES] = amplitude
        source[mode + X8_HALF_MODES, mode] = amplitude
    passive = np.zeros_like(source)
    passive[:X8_HALF_MODES, :X8_HALF_MODES] = unitary
    passive[X8_HALF_MODES:, X8_HALF_MODES:] = unitary
    adjacency = passive @ source @ passive.T
    if not np.allclose(adjacency, adjacency.T, atol=1e-12):
        raise AssertionError("GBS adjacency matrix must be complex symmetric")
    if float(np.linalg.svd(adjacency, compute_uv=False)[0]) >= 1.0:
        raise ValueError("Unphysical GBS adjacency: singular value is not below one")
    return adjacency


def hafnian(matrix: np.ndarray) -> complex:
    """Compute a loop-free hafnian with a bit-mask dynamic program."""

    values = np.asarray(matrix, dtype=np.complex128)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError("hafnian expects a square matrix")
    size = len(values)
    if size % 2:
        return 0.0j
    if size == 0:
        return 1.0 + 0.0j

    @lru_cache(maxsize=None)
    def recurse(mask: int) -> complex:
        if mask == 0:
            return 1.0 + 0.0j
        first_bit = mask & -mask
        first = first_bit.bit_length() - 1
        remaining = mask ^ first_bit
        total = 0.0 + 0.0j
        candidates = remaining
        while candidates:
            second_bit = candidates & -candidates
            second = second_bit.bit_length() - 1
            total += values[first, second] * recurse(remaining ^ second_bit)
            candidates ^= second_bit
        return total

    return recurse((1 << size) - 1)


def _compositions(total: int, modes: int) -> Iterable[tuple[int, ...]]:
    if modes == 1:
        yield (total,)
        return
    for value in range(total + 1):
        for suffix in _compositions(total - value, modes - 1):
            yield (value, *suffix)


@lru_cache(maxsize=16)
def _pattern_tuples(modes: int, max_total_photons: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        pattern
        for total in range(max_total_photons + 1)
        for pattern in _compositions(total, modes)
    )


def photon_patterns(
    max_total_photons: int,
    modes: int = X8_MODES,
) -> np.ndarray:
    if modes < 1 or max_total_photons < 0:
        raise ValueError("Invalid photon-pattern dimensions")
    return np.asarray(_pattern_tuples(modes, max_total_photons), dtype=np.int16)


def _gbs_pattern_probability(
    adjacency: np.ndarray,
    pattern: np.ndarray,
    normalization: float,
) -> float:
    counts = np.asarray(pattern, dtype=int)
    total = int(counts.sum())
    if total % 2:
        return 0.0
    if total == 0:
        return normalization
    repeated_indices = np.repeat(np.arange(len(counts)), counts)
    repeated = adjacency[np.ix_(repeated_indices, repeated_indices)]
    denominator = math.prod(math.factorial(int(value)) for value in counts)
    return float(normalization * abs(hafnian(repeated)) ** 2 / denominator)


def _gbs_normalization(adjacency: np.ndarray) -> float:
    covariance_factor = np.eye(len(adjacency)) - adjacency @ adjacency.conj().T
    determinant = float(np.linalg.det(covariance_factor).real)
    if determinant <= 0.0:
        raise ValueError("Invalid GBS normalization determinant")
    return math.sqrt(determinant)


def gbs_pattern_probability(adjacency: np.ndarray, pattern: np.ndarray) -> float:
    matrix = np.asarray(adjacency, dtype=np.complex128)
    counts = np.asarray(pattern, dtype=int)
    if matrix.shape != (len(counts), len(counts)) or np.any(counts < 0):
        raise ValueError("Pattern and adjacency dimensions do not match")
    return _gbs_pattern_probability(matrix, counts, _gbs_normalization(matrix))


def gbs_distribution(x: np.ndarray, config: X8GBSConfig) -> GBSDistribution:
    adjacency = x8_adjacency(x, config)
    normalization = _gbs_normalization(adjacency)
    patterns = photon_patterns(config.max_total_photons)
    probabilities = np.zeros(len(patterns), dtype=float)
    even = np.flatnonzero(patterns.sum(axis=1) % 2 == 0)
    for index in even:
        probabilities[index] = _gbs_pattern_probability(
            adjacency,
            patterns[index],
            normalization,
        )
    accepted = float(probabilities.sum())
    if accepted > 1.0 + 1e-9:
        raise RuntimeError(f"Truncated GBS probability exceeds one: {accepted}")
    rejected = max(0.0, 1.0 - accepted)
    return GBSDistribution(patterns, probabilities, rejected)


def allocate_exact_shots(total_budget: int, circuit_count: int, seed: int) -> np.ndarray:
    if circuit_count < 1:
        raise ValueError("circuit_count must be positive")
    if total_budget < circuit_count:
        raise ValueError("Budget must provide at least one shot per circuit")
    base, remainder = divmod(total_budget, circuit_count)
    shots = np.full(circuit_count, base, dtype=np.int64)
    if remainder:
        rng = np.random.default_rng(seed)
        shots[rng.choice(circuit_count, size=remainder, replace=False)] += 1
    if int(shots.sum()) != total_budget:
        raise AssertionError("Shot allocation is not exact")
    return shots


def pattern_key(pattern: np.ndarray | tuple[int, ...]) -> str:
    return ",".join(str(int(value)) for value in pattern)


def parse_pattern_key(key: str, modes: int = X8_MODES) -> tuple[int, ...]:
    values = tuple(int(value) for value in key.split(","))
    if len(values) != modes or any(value < 0 for value in values):
        raise ValueError(f"Invalid {modes}-mode photon pattern: {key!r}")
    return values


def sample_distribution(
    distribution: GBSDistribution,
    shots: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    if shots < 1:
        raise ValueError("shots must be positive")
    probabilities = np.append(distribution.probabilities, distribution.rejected_probability)
    probabilities /= probabilities.sum()
    sampled = rng.multinomial(shots, probabilities)
    histogram = {
        pattern_key(pattern): int(count)
        for pattern, count in zip(distribution.patterns, sampled[:-1])
        if count
    }
    accepted = int(sampled[:-1].sum())
    return {
        "shots": shots,
        "accepted_shots": accepted,
        "rejected_shots": int(sampled[-1]),
        "overflow_shots": int(sampled[-1]),
        "histogram": histogram,
        "overflow_histogram": {},
    }


def sample_record_from_array(
    samples: np.ndarray,
    max_total_photons: int,
) -> dict[str, Any]:
    values = np.asarray(samples)
    if values.ndim != 2 or values.shape[1] != X8_MODES:
        raise ValueError(f"Expected samples with shape (shots, {X8_MODES})")
    if np.any(values < 0) or not np.allclose(values, np.rint(values)):
        raise ValueError("Photon-number samples must be non-negative integers")
    integer = np.asarray(np.rint(values), dtype=np.int64)
    accepted_mask = integer.sum(axis=1) <= max_total_photons
    histogram: dict[str, int] = {}
    for row in integer[accepted_mask]:
        key = pattern_key(row)
        histogram[key] = histogram.get(key, 0) + 1
    overflow_histogram: dict[str, int] = {}
    for row in integer[~accepted_mask]:
        key = pattern_key(row)
        overflow_histogram[key] = overflow_histogram.get(key, 0) + 1
    return {
        "shots": len(integer),
        "accepted_shots": int(np.sum(accepted_mask)),
        "rejected_shots": int(np.sum(~accepted_mask)),
        "overflow_shots": int(np.sum(~accepted_mask)),
        "histogram": histogram,
        "overflow_histogram": overflow_histogram,
    }


def apply_uniform_loss(
    samples: np.ndarray,
    transmissivity: float | np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply independent photon thinning to each mode of raw PNR samples."""

    values = np.asarray(samples)
    if values.ndim != 2 or values.shape[1] != X8_MODES:
        raise ValueError(f"Expected samples with shape (shots, {X8_MODES})")
    if np.any(values < 0) or not np.allclose(values, np.rint(values)):
        raise ValueError("Photon-number samples must be non-negative integers")
    transmission = np.asarray(transmissivity, dtype=float)
    if transmission.ndim == 0:
        transmission = np.full(X8_MODES, float(transmission))
    if transmission.shape != (X8_MODES,) or np.any((transmission < 0.0) | (transmission > 1.0)):
        raise ValueError("transmissivity must be a scalar or eight values in [0, 1]")
    return rng.binomial(np.asarray(np.rint(values), dtype=np.int64), transmission[None, :])


def apply_detector_model(
    samples: np.ndarray,
    config: DetectorConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply quantum efficiency, dark counts and detector readout semantics."""

    config.validate()
    detected = apply_uniform_loss(samples, config.quantum_efficiency, rng)
    if config.dark_count_mean > 0.0:
        detected = detected + rng.poisson(config.dark_count_mean, size=detected.shape)
    if config.model == "threshold":
        detected = (detected > 0).astype(np.int64)
    elif config.model == "pnr_saturation":
        detected = np.minimum(detected, int(config.saturation_count))
    return np.asarray(detected, dtype=np.int64)


def _probability_features_from_records(
    records: list[dict[str, Any]],
    patterns: np.ndarray,
    include_overflow: bool,
) -> tuple[np.ndarray, np.ndarray]:
    index = {tuple(int(value) for value in row): position for position, row in enumerate(patterns)}
    feature_count = len(patterns) + int(include_overflow)
    probabilities = np.zeros((len(records), feature_count), dtype=float)
    acceptance = np.empty(len(records), dtype=float)
    for row_index, record in enumerate(records):
        shots = int(record["shots"])
        accepted = int(record["accepted_shots"])
        rejected = int(record["rejected_shots"])
        if shots < 1 or accepted + rejected != shots:
            raise ValueError("Inconsistent shot accounting in sample record")
        if accepted < 1 and not include_overflow:
            raise ValueError("No accepted PNR samples in the photon window")
        observed = 0
        for key, count in record["histogram"].items():
            pattern = parse_pattern_key(str(key))
            if pattern not in index:
                raise ValueError(f"Accepted histogram contains an unknown pattern: {key}")
            probabilities[row_index, index[pattern]] += int(count)
            observed += int(count)
        if observed != accepted:
            raise ValueError("Histogram counts do not equal accepted_shots")
        denominator = shots if include_overflow else accepted
        probabilities[row_index, : len(patterns)] /= denominator
        if include_overflow:
            probabilities[row_index, -1] = rejected / shots
        acceptance[row_index] = accepted / shots
    return probabilities, acceptance


def photon_moment_basis(patterns: np.ndarray) -> np.ndarray:
    values = np.asarray(patterns, dtype=float)
    columns = [values[:, mode] for mode in range(X8_MODES)]
    columns.extend(
        values[:, left] * values[:, right]
        for left in range(X8_MODES)
        for right in range(left, X8_MODES)
    )
    return np.column_stack(columns)


def features_from_records(
    records: list[dict[str, Any]],
    max_total_photons: int,
    include_overflow: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    patterns = photon_patterns(max_total_photons)
    probabilities, acceptance = _probability_features_from_records(
        records,
        patterns,
        include_overflow,
    )
    hellinger = np.sqrt(probabilities)
    accepted_probabilities = probabilities[:, : len(patterns)]
    moments = accepted_probabilities @ photon_moment_basis(patterns)
    if include_overflow:
        moments = np.column_stack((moments, acceptance, 1.0 - acceptance))
    return hellinger, moments, acceptance


def ideal_features(
    distributions: list[GBSDistribution],
    include_overflow: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not distributions:
        raise ValueError("At least one distribution is required")
    reference_patterns = distributions[0].patterns
    if any(not np.array_equal(row.patterns, reference_patterns) for row in distributions[1:]):
        raise ValueError("All distributions must use the same photon window")
    if include_overflow:
        probabilities = np.vstack(
            [np.append(row.probabilities, row.rejected_probability) for row in distributions]
        )
    else:
        probabilities = np.vstack([row.conditional_probabilities for row in distributions])
    hellinger = np.sqrt(probabilities)
    acceptance = np.asarray([row.acceptance_probability for row in distributions])
    moments = probabilities[:, : len(reference_patterns)] @ photon_moment_basis(reference_patterns)
    if include_overflow:
        moments = np.column_stack((moments, acceptance, 1.0 - acceptance))
    return hellinger, moments, acceptance


def _event_key(pattern: tuple[int, ...]) -> tuple[int, int]:
    return sum(pattern), sum(value > 0 for value in pattern)


def _orbit_key(pattern: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted(pattern, reverse=True))


def event_orbit_features(
    records: list[dict[str, Any]],
    max_total_photons: int,
) -> EventOrbitFeatures:
    """Aggregate raw events by total/click event and permutation orbit."""

    patterns = [tuple(int(value) for value in row) for row in photon_patterns(max_total_photons)]
    event_keys = sorted({_event_key(pattern) for pattern in patterns})
    orbit_keys = sorted({_orbit_key(pattern) for pattern in patterns})
    event_index = {key: index for index, key in enumerate(event_keys)}
    orbit_index = {key: index for index, key in enumerate(orbit_keys)}
    event = np.zeros((len(records), len(event_keys) + 1), dtype=float)
    orbit = np.zeros((len(records), len(orbit_keys) + 1), dtype=float)
    for row_index, record in enumerate(records):
        shots = int(record["shots"])
        accepted = int(record["accepted_shots"])
        rejected = int(record["rejected_shots"])
        if shots < 1 or accepted + rejected != shots:
            raise ValueError("Inconsistent shot accounting in sample record")
        observed = 0
        for key, count_value in record["histogram"].items():
            pattern = parse_pattern_key(str(key))
            if sum(pattern) > max_total_photons:
                raise ValueError("Accepted histogram contains an overflow event")
            count = int(count_value)
            event[row_index, event_index[_event_key(pattern)]] += count
            orbit[row_index, orbit_index[_orbit_key(pattern)]] += count
            observed += count
        if observed != accepted:
            raise ValueError("Histogram counts do not equal accepted_shots")
        event[row_index, -1] = rejected
        orbit[row_index, -1] = rejected
        event[row_index] /= shots
        orbit[row_index] /= shots
    return EventOrbitFeatures(
        event=event,
        orbit=orbit,
        event_labels=tuple(
            [f"total={total};clicks={clicks}" for total, clicks in event_keys] + ["overflow"]
        ),
        orbit_labels=tuple(
            ["orbit=" + ",".join(str(value) for value in key) for key in orbit_keys]
            + ["overflow"]
        ),
    )


def ideal_event_orbit_features(
    distributions: list[GBSDistribution],
) -> EventOrbitFeatures:
    if not distributions:
        raise ValueError("At least one distribution is required")
    reference = distributions[0].patterns
    if any(not np.array_equal(row.patterns, reference) for row in distributions[1:]):
        raise ValueError("All distributions must use the same photon window")
    patterns = [tuple(int(value) for value in row) for row in reference]
    event_keys = sorted({_event_key(pattern) for pattern in patterns})
    orbit_keys = sorted({_orbit_key(pattern) for pattern in patterns})
    event_index = {key: index for index, key in enumerate(event_keys)}
    orbit_index = {key: index for index, key in enumerate(orbit_keys)}
    event = np.zeros((len(distributions), len(event_keys) + 1), dtype=float)
    orbit = np.zeros((len(distributions), len(orbit_keys) + 1), dtype=float)
    for row_index, distribution in enumerate(distributions):
        for pattern, probability in zip(patterns, distribution.probabilities):
            event[row_index, event_index[_event_key(pattern)]] += float(probability)
            orbit[row_index, orbit_index[_orbit_key(pattern)]] += float(probability)
        event[row_index, -1] = distribution.rejected_probability
        orbit[row_index, -1] = distribution.rejected_probability
    return EventOrbitFeatures(
        event=event,
        orbit=orbit,
        event_labels=tuple(
            [f"total={total};clicks={clicks}" for total, clicks in event_keys] + ["overflow"]
        ),
        orbit_labels=tuple(
            ["orbit=" + ",".join(str(value) for value in key) for key in orbit_keys]
            + ["overflow"]
        ),
    )


def standardize_moments(
    train: np.ndarray,
    *others: np.ndarray,
) -> tuple[np.ndarray, ...]:
    train_values = np.asarray(train, dtype=float)
    mean = train_values.mean(axis=0)
    scale = train_values.std(axis=0)
    scale[scale < 1e-10] = 1.0
    return tuple((np.asarray(values, dtype=float) - mean) / scale for values in (train, *others))


def hellinger_kernel(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return np.asarray(left, dtype=float) @ np.asarray(right, dtype=float).T


def moment_kernel(left: np.ndarray, right: np.ndarray, gamma: float) -> np.ndarray:
    if gamma <= 0.0:
        raise ValueError("gamma must be positive")
    differences = np.asarray(left)[:, None, :] - np.asarray(right)[None, :, :]
    return np.exp(-gamma * np.sum(differences * differences, axis=2))
