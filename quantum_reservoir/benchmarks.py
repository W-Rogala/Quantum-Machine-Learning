from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BenchmarkSeries:
    name: str
    inputs: np.ndarray
    targets: np.ndarray
    horizon: int
    description: str


def narma10(length: int, seed: int = 1234) -> BenchmarkSeries:
    """Generate the standard nonlinear NARMA10 system-identification task."""

    if length < 50:
        raise ValueError("NARMA10 length must be at least 50")
    rng = np.random.default_rng(seed)
    driving = rng.uniform(0.0, 0.5, size=length + 10)
    response = np.zeros(length + 11, dtype=float)
    for time_index in range(10, length + 10):
        response[time_index + 1] = (
            0.3 * response[time_index]
            + 0.05 * response[time_index] * np.sum(response[time_index - 9 : time_index + 1])
            + 1.5 * driving[time_index - 9] * driving[time_index]
            + 0.1
        )
    inputs = driving[10 : 10 + length] / 0.5
    targets = response[11 : 11 + length]
    return BenchmarkSeries(
        name="NARMA10",
        inputs=inputs,
        targets=targets,
        horizon=1,
        description="Nonlinear tenth-order system identification driven by uniform input.",
    )


def mackey_glass(
    length: int,
    horizon: int = 5,
    beta: float = 0.2,
    gamma: float = 0.1,
    exponent: int = 10,
    delay: int = 17,
    step: float = 1.0,
    warmup: int = 300,
) -> BenchmarkSeries:
    """Generate a delayed Mackey–Glass chaotic series with a future target."""

    if length < 50:
        raise ValueError("Mackey-Glass length must be at least 50")
    total = warmup + length + horizon + delay + 1
    values = np.full(total, 1.2, dtype=float)
    for time_index in range(delay, total - 1):
        delayed = values[time_index - delay]
        derivative = beta * delayed / (1.0 + delayed**exponent) - gamma * values[time_index]
        values[time_index + 1] = values[time_index] + step * derivative
    series = values[warmup : warmup + length + horizon]
    minimum = float(np.min(series))
    scale = float(np.max(series) - minimum)
    normalized = (series - minimum) / scale
    return BenchmarkSeries(
        name="MackeyGlass-h5",
        inputs=normalized[:length],
        targets=normalized[horizon : horizon + length],
        horizon=horizon,
        description="Five-step forecasting of the chaotic Mackey-Glass delay system.",
    )


def benchmark_suite(length: int = 950, seed: int = 1234) -> tuple[BenchmarkSeries, ...]:
    return (
        narma10(length=length, seed=seed),
        mackey_glass(length=length, horizon=5),
    )
