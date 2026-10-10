"""Sequential quantum reservoir computing with exact and Trotter evolution."""

from .benchmarks import BenchmarkSeries, benchmark_suite, mackey_glass, narma10
from .core import (
    QuantumReservoir,
    ReservoirConfig,
    circuit_resources,
    process_infidelity,
)
from .ibm_hardware import HardwareExecutionConfig

__all__ = [
    "BenchmarkSeries",
    "HardwareExecutionConfig",
    "QuantumReservoir",
    "ReservoirConfig",
    "benchmark_suite",
    "circuit_resources",
    "mackey_glass",
    "narma10",
    "process_infidelity",
]
