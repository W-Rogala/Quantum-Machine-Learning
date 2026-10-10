"""Run the Trotterized quantum reservoir on Aer, a fake IBM target, or IBM QPU.

Examples
--------
Local shot-based smoke test:
    python tools/qrc_ibm_hardware.py --provider aer --length 80

Compile against IBM Fez's ISA without submitting a cloud job:
    python tools/qrc_ibm_hardware.py --provider fake-ibm --dry-run --length 20

Submit to an IBM QPU after configuring credentials:
    python tools/qrc_ibm_hardware.py --provider ibm --submit --backend ibm_torino --length 80
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum_reservoir.benchmarks import mackey_glass, narma10
from quantum_reservoir.core import ReservoirConfig
from quantum_reservoir.ibm_hardware import (
    HardwareExecutionConfig,
    build_feature_circuits,
    compilation_summary,
    compile_for_backend,
    decode_feature_counts,
    ridge_readout,
    run_ibm_sampler,
    run_local_sampler,
    save_feature_artifacts,
    select_ibm_backend,
    write_json,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--provider", choices=("aer", "fake-ibm", "ibm"), default="aer")
    value.add_argument("--benchmark", choices=("narma10", "mackey-glass"), default="narma10")
    value.add_argument("--length", type=int, default=80)
    value.add_argument("--benchmark-seed", type=int, default=1234)
    value.add_argument("--reservoir-seed", type=int, default=7)
    value.add_argument("--qubits", type=int, default=4)
    value.add_argument("--trotter-order", type=int, choices=(1, 2), default=2)
    value.add_argument("--trotter-steps", type=int, default=2)
    value.add_argument(
        "--history-window",
        type=int,
        default=12,
        help="Maximum replayed inputs per circuit; use 0 for the exact full prefix.",
    )
    value.add_argument("--shots", type=int, default=4096)
    value.add_argument("--optimization-level", type=int, choices=(0, 1, 2, 3), default=3)
    value.add_argument("--seed-transpiler", type=int, default=1234)
    value.add_argument("--seed-sampler", type=int, default=1234)
    value.add_argument("--max-circuits-per-job", type=int, default=50)
    value.add_argument("--backend", default=None)
    value.add_argument("--instance", default=None)
    value.add_argument("--dry-run", action="store_true")
    value.add_argument(
        "--submit",
        action="store_true",
        help="Required to submit IBM cloud jobs; without it provider=ibm only compiles.",
    )
    value.add_argument("--washout", type=int, default=10)
    value.add_argument("--train", type=int, default=40)
    value.add_argument("--validation", type=int, default=15)
    value.add_argument("--test", type=int, default=15)
    value.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "analysis_output" / "qrc_ibm_hardware",
    )
    return value


def _benchmark(name: str, length: int, seed: int):
    if name == "narma10":
        return narma10(length=length, seed=seed)
    return mackey_glass(length=length, horizon=5)


def _backend_name(backend: object) -> str:
    name = getattr(backend, "name", None)
    return str(name() if callable(name) else name if name is not None else backend)


def _save_circuits(output_dir: Path, logical: list[object], compiled: list[object] | None) -> None:
    from qiskit import qpy

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "logical_circuits.qpy").open("wb") as handle:
        qpy.dump(logical, handle)
    if compiled is not None:
        with (output_dir / "isa_circuits.qpy").open("wb") as handle:
            qpy.dump(compiled, handle)


def main() -> None:
    args = parser().parse_args()
    if args.submit and args.provider != "ibm":
        raise SystemExit("--submit is only valid with --provider ibm")
    if args.submit and args.dry_run:
        raise SystemExit("--submit and --dry-run are mutually exclusive")
    effective_dry_run = bool(args.dry_run or (args.provider == "ibm" and not args.submit))
    if args.length < 1:
        raise SystemExit("--length must be positive")
    split = (args.washout, args.train, args.validation, args.test)
    if not effective_dry_run and sum(split) > args.length:
        raise SystemExit("washout + train + validation + test exceeds --length")
    history_window = None if args.history_window == 0 else args.history_window
    reservoir = ReservoirConfig(
        n_qubits=args.qubits,
        disorder_seed=args.reservoir_seed,
        method="trotter",
        trotter_order=args.trotter_order,
        trotter_steps=args.trotter_steps,
    )
    execution = HardwareExecutionConfig(
        shots=args.shots,
        history_window=history_window,
        optimization_level=args.optimization_level,
        seed_transpiler=args.seed_transpiler,
        seed_sampler=args.seed_sampler,
        max_circuits_per_job=args.max_circuits_per_job,
        backend_name=args.backend,
        instance=args.instance,
    )
    reservoir.validate()
    execution.validate()
    benchmark = _benchmark(args.benchmark, args.length, args.benchmark_seed)
    logical, records = build_feature_circuits(benchmark.inputs, reservoir, history_window)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    compiled = None
    backend = None
    service = None
    if args.provider == "fake-ibm":
        from qiskit_ibm_runtime.fake_provider import FakeFez

        backend = FakeFez()
        compiled = compile_for_backend(
            logical,
            backend,
            optimization_level=execution.optimization_level,
            seed_transpiler=execution.seed_transpiler,
        )
    elif args.provider == "ibm":
        service, backend = select_ibm_backend(execution)
        compiled = compile_for_backend(
            logical,
            backend,
            optimization_level=execution.optimization_level,
            seed_transpiler=execution.seed_transpiler,
        )

    _save_circuits(args.output_dir, logical, compiled)
    manifest = {
        "schema": "qrc.ibm-hardware-workload.v1",
        "provider": args.provider,
        "backend": None if backend is None else _backend_name(backend),
        "benchmark": args.benchmark,
        "length": args.length,
        "measurement_circuits": len(logical),
        "reservoir": asdict(reservoir),
        "execution": asdict(execution),
        "logical_compilation": compilation_summary(logical),
        "isa_compilation": None if compiled is None else compilation_summary(compiled),
        "records": records,
    }
    write_json(args.output_dir / "workload_manifest.json", manifest)

    if effective_dry_run:
        print(
            json.dumps(
                {
                    key: manifest[key]
                    for key in (
                        "schema",
                        "provider",
                        "backend",
                        "benchmark",
                        "length",
                        "measurement_circuits",
                        "logical_compilation",
                        "isa_compilation",
                    )
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"Dry run complete: {args.output_dir}")
        return

    job_ids: list[str] = []
    if args.provider == "ibm":
        assert backend is not None and compiled is not None and service is not None
        counts, job_ids = run_ibm_sampler(compiled, backend, execution, args.output_dir)
    elif args.provider == "fake-ibm":
        assert compiled is not None
        counts = run_local_sampler(compiled, execution.shots, execution.seed_sampler)
    else:
        counts = run_local_sampler(logical, execution.shots, execution.seed_sampler)

    features, errors = decode_feature_counts(counts, records, reservoir)
    metrics, prediction = ridge_readout(
        benchmark.inputs,
        features,
        benchmark.targets,
        split,
    )
    test_start = args.washout + args.train + args.validation
    test_targets = benchmark.targets[test_start : test_start + args.test]
    metadata = {
        "provider": args.provider,
        "backend": None if backend is None else _backend_name(backend),
        "benchmark": args.benchmark,
        "job_ids": job_ids,
        "readout_split": {
            "washout": args.washout,
            "train": args.train,
            "validation": args.validation,
            "test": args.test,
        },
        "readout_metrics": metrics,
        "logical_compilation": compilation_summary(logical),
        "isa_compilation": None if compiled is None else compilation_summary(compiled),
    }
    save_feature_artifacts(
        args.output_dir,
        benchmark.inputs,
        benchmark.targets,
        features,
        errors,
        reservoir,
        execution,
        metadata,
        prediction=prediction,
        test_targets=test_targets,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"Completed: {args.output_dir}")


if __name__ == "__main__":
    main()
