from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .core import DetectorConfig, X8GBSConfig, apply_detector_model, x8_interferometer
from .robustness import cutoff_loss_detector_sweep


def _load_strawberry_fields() -> tuple[Any, Any]:
    try:
        import strawberryfields as sf
        from strawberryfields import ops
    except ImportError as error:
        raise RuntimeError(
            "Strawberry Fields is not installed in this interpreter. Use the isolated "
            "CPython 3.10 environment pinned in requirements-xanadu-x8.txt."
        ) from error
    return sf, ops


def build_lossy_gbs_program(
    x: np.ndarray,
    config: X8GBSConfig,
    transmissivity: float,
    detector_model: str = "pnr",
) -> Any:
    """Build an eight-mode SF program with physical loss before detection."""

    if not 0.0 <= transmissivity <= 1.0:
        raise ValueError("transmissivity must be in [0, 1]")
    if detector_model not in {"pnr", "threshold"}:
        raise ValueError("SF program supports native 'pnr' or 'threshold' measurement")
    sf, ops = _load_strawberry_fields()
    program = sf.Program(8)
    unitary = x8_interferometer(np.asarray(x, dtype=float), config)
    with program.context as modes:
        for mode, squeezing in enumerate(config.squeezing):
            ops.S2gate(float(squeezing), 0.0) | (modes[mode], modes[mode + 4])
        ops.Interferometer(unitary) | tuple(modes[:4])
        ops.Interferometer(unitary) | tuple(modes[4:])
        for mode in modes:
            ops.LossChannel(float(transmissivity)) | mode
        measurement = ops.MeasureFock() if detector_model == "pnr" else ops.MeasureThreshold()
        measurement | tuple(modes)
    return program


def run_strawberry_fields_samples(
    x: np.ndarray,
    config: X8GBSConfig,
    shots: int,
    transmissivity: float,
    detector: DetectorConfig,
    seed: int,
    backend: str = "gaussian",
    cutoff_dim: int | None = None,
) -> np.ndarray:
    """Execute a local SF program and return detector-level samples."""

    if shots < 1:
        raise ValueError("shots must be positive")
    detector.validate()
    native_model = "threshold" if detector.model == "threshold" else "pnr"
    program = build_lossy_gbs_program(x, config, transmissivity, native_model)
    sf, _ = _load_strawberry_fields()
    backend_options: dict[str, Any] = {}
    if cutoff_dim is not None:
        if cutoff_dim < 2:
            raise ValueError("cutoff_dim must be at least 2")
        backend_options["cutoff_dim"] = cutoff_dim
    np.random.seed(seed)
    engine = sf.Engine(backend, backend_options=backend_options)
    result = engine.run(program, shots=shots)
    samples = np.asarray(result.samples, dtype=np.int64)
    if samples.shape != (shots, 8):
        raise RuntimeError(f"Unexpected Strawberry Fields sample shape: {samples.shape}")
    postprocess = DetectorConfig(
        model=detector.model,
        quantum_efficiency=detector.quantum_efficiency,
        dark_count_mean=detector.dark_count_mean,
        saturation_count=detector.saturation_count,
    )
    # Native threshold measurement has already thresholded the samples.
    if native_model == "threshold":
        postprocess = DetectorConfig(
            model="pnr",
            quantum_efficiency=detector.quantum_efficiency,
            dark_count_mean=detector.dark_count_mean,
        )
    detected = apply_detector_model(samples, postprocess, np.random.default_rng(seed + 1))
    return (detected > 0).astype(np.int64) if detector.model == "threshold" else detected


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def analyze_saved_samples(args: argparse.Namespace) -> Path:
    arrays = np.load(args.samples, allow_pickle=False)
    batch_names = sorted(arrays.files)
    batches = [np.asarray(arrays[name], dtype=np.int64) for name in batch_names]
    detectors = (
        DetectorConfig("pnr"),
        DetectorConfig("threshold"),
        DetectorConfig("pnr_saturation", saturation_count=2),
        DetectorConfig("pnr", quantum_efficiency=0.85, dark_count_mean=0.01),
    )
    rows, matrices = cutoff_loss_detector_sweep(
        batches,
        args.cutoffs,
        args.transmissivities,
        detectors,
        args.seed,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_dir / "robustness_sweep.csv", rows)
    manifest = {
        "schema": "photonic-kernel.robustness.v1",
        "source_samples": str(args.samples.resolve()),
        "batch_names": batch_names,
        "cutoffs": args.cutoffs,
        "transmissivities": args.transmissivities,
        "detectors": [asdict(detector) for detector in detectors],
        "same_raw_samples_across_scenarios": True,
        "overflow_is_explicit_feature": True,
        "feature_families": [
            "pattern_hellinger",
            "moment_rbf",
            "event_hellinger",
            "orbit_hellinger",
        ],
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    for scenario_id, kernel_family in matrices.items():
        np.savez_compressed(
            args.output_dir / f"kernels_{scenario_id}.npz",
            **kernel_family,
        )
    return args.output_dir / "manifest.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strawberry Fields CV/GBS loss robustness")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze-samples")
    analyze.add_argument("--samples", type=Path, required=True, help="NPZ with one (shots, 8) array per sample")
    analyze.add_argument("--cutoffs", type=lambda value: [int(item) for item in value.split(",")], default=[2, 4, 6, 8])
    analyze.add_argument(
        "--transmissivities",
        type=lambda value: [float(item) for item in value.split(",")],
        default=[1.0, 0.9, 0.75, 0.5],
    )
    analyze.add_argument("--seed", type=int, default=20260818)
    analyze.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "analyze-samples":
        path = analyze_saved_samples(args)
        print(json.dumps({"status": "completed", "manifest": str(path)}, indent=2))
    else:
        raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
