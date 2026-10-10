from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .core import EvolutionConfig
from .data import load_dataset, prepare_dataset
from .hardware_circuits import (
    analyze_hardware_counts,
    build_measurement_entries,
    build_qiskit_measurement_circuit,
    config_to_dict,
    workload_identifier,
)
from .hardware_providers import (
    execute_aer,
    execute_braket_local,
    execute_pennylane,
    retrieve_remote,
    submit_braket,
    submit_ibm,
    submit_ionq,
    write_json,
)
from .protocol import load_frozen_protocol


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SELECTED_RESULTS = (
    ROOT
    / "analysis_output"
    / "hamiltonian_kernel_grid_full_spectral"
    / "selected_ideal_runs.csv"
)
DEFAULT_HARDWARE_ROOT = ROOT / "analysis_output" / "hamiltonian_kernel_hardware"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validation_benchmark_source(args: argparse.Namespace) -> dict[str, Any]:
    if args.protocol is None or args.benchmark_completion is None:
        raise ValueError(
            "A validation pilot requires --protocol and --benchmark-completion"
        )
    protocol_path = args.protocol.resolve()
    completion_path = args.benchmark_completion.resolve()
    protocol, frozen = load_frozen_protocol(protocol_path)
    completion = _read_json(completion_path)
    if protocol.profile != "full":
        raise ValueError("A validation pilot cannot be bound to a smoke protocol")
    if completion.get("status") != "completed":
        raise ValueError("Benchmark completion manifest is not completed")
    if completion.get("protocol_hash") != frozen["protocol_hash"]:
        raise ValueError("Benchmark completion and frozen protocol hashes differ")
    if completion.get("qpu_gate") != "eligible_for_separate_reproducible_pilot_after_review":
        raise ValueError("Benchmark completion has not opened the QPU validation gate")
    frozen_values = {
        "dataset": protocol.qpu_pilot_dataset,
        "outer_repeat": protocol.qpu_pilot_outer_repeat,
        "outer_fold": protocol.qpu_pilot_outer_fold,
        "budget": protocol.qpu_pilot_circuit_shots_per_kernel,
        "train_per_class": protocol.qpu_pilot_train_per_class,
        "test_per_class": protocol.qpu_pilot_test_per_class,
        "sample_seed": protocol.qpu_pilot_sample_seed,
        "measurement_seed": protocol.qpu_pilot_measurement_seed,
        "n_qubits": protocol.n_qubits,
        "trotter_order": 2,
        "trotter_steps": 2,
    }
    for name, expected in frozen_values.items():
        if getattr(args, name) != expected:
            raise ValueError(
                f"Validation pilot argument --{name.replace('_', '-')}={getattr(args, name)!r} "
                f"differs from frozen value {expected!r}"
            )
    if args.kernel not in protocol.qpu_pilot_kernels:
        raise ValueError("Requested kernel is outside the frozen QPU pilot")
    if any(
        value is not None
        for value in (
            args.evolution_time,
            args.interaction_strength,
            args.transverse_field,
            args.topology,
        )
    ):
        raise ValueError("Validation pilot cannot override the frozen Hamiltonian")

    results_path = (
        args.outer_results.resolve()
        if args.outer_results is not None
        else completion_path.parent / "outer_results.csv"
    )
    with results_path.open("r", encoding="utf-8", newline="") as handle:
        matches = [
            row
            for row in csv.DictReader(handle)
            if row["dataset"] == args.dataset
            and int(row["outer_repeat"]) == args.outer_repeat
            and int(row["outer_fold"]) == args.outer_fold
            and row["family"] == args.kernel
            and row["evaluation_regime"] == "ideal_statevector"
        ]
    if len(matches) != 1:
        raise ValueError(f"Expected one frozen outer-result row, got {len(matches)}")
    result_row = matches[0]
    if result_row["protocol_hash"] != frozen["protocol_hash"]:
        raise ValueError("Selected outer-result row has a different protocol hash")
    configuration = json.loads(result_row["configuration_json"])
    split_path = Path(result_row["split_artifact"]).resolve()
    with np.load(split_path, allow_pickle=False) as split:
        split_hash = str(np.asarray(split["protocol_hash"]).item())
        if split_hash != frozen["protocol_hash"]:
            raise ValueError("Outer-split artifact has a different protocol hash")
        split_payload = {name: np.asarray(split[name]) for name in split.files}
    return {
        "protocol": protocol,
        "protocol_payload": frozen,
        "completion": completion,
        "configuration": configuration,
        "result_row": result_row,
        "split": split_payload,
        "study_binding": {
            "tier": "qpu_validation_of_completed_benchmark",
            "protocol_hash": frozen["protocol_hash"],
            "protocol_path": str(protocol_path),
            "protocol_sha256": _file_sha256(protocol_path),
            "benchmark_completion_path": str(completion_path),
            "benchmark_completion_sha256": _file_sha256(completion_path),
            "outer_results_path": str(results_path),
            "outer_results_sha256": _file_sha256(results_path),
            "outer_split_path": str(split_path),
            "outer_split_sha256": _file_sha256(split_path),
            "configuration_id": result_row["configuration_id"],
            "dataset": args.dataset,
            "outer_repeat": args.outer_repeat,
            "outer_fold": args.outer_fold,
            "transpile_seed": protocol.qpu_pilot_transpile_seed,
            "optimization_level": protocol.qpu_pilot_optimization_level,
        },
    }


def _selected_model(
    path: Path,
    dataset: str,
    seed: int,
    kernel: str,
) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Selected-model table not found: {path}. Run grid_experiment first."
        )
    with path.open("r", encoding="utf-8", newline="") as handle:
        matches = [
            row
            for row in csv.DictReader(handle)
            if row["dataset"] == dataset
            and int(row["seed"]) == seed
            and row["kernel"] == kernel
        ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one selected model for {dataset}/seed={seed}/{kernel}, got {len(matches)}"
        )
    return matches[0]


def _balanced_subset_indices(y: np.ndarray, per_class: int, seed: int) -> np.ndarray:
    if per_class < 1:
        raise ValueError("per_class must be positive")
    rng = np.random.default_rng(seed)
    selected: list[int] = []
    for label in np.unique(y):
        indices = np.flatnonzero(y == label)
        if len(indices) < per_class:
            raise ValueError(
                f"Class {label} has only {len(indices)} samples, requested {per_class}"
            )
        selected.extend(rng.permutation(indices)[:per_class].tolist())
    selected_array = np.asarray(selected, dtype=int)
    return selected_array[rng.permutation(len(selected_array))]


def _float_override(value: float | None, fallback: Any) -> float:
    return float(fallback if value is None else value)


def _xanadu_compatibility() -> dict[str, Any]:
    return {
        "direct_qubit_hamiltonian_kernel_supported": False,
        "status": "requires_separate_photonic_reformulation",
        "reason": (
            "The selected model is a gate-model qubit Ising evolution. Xanadu X8 is an "
            "eight-mode photonic Gaussian-boson-sampling device and does not accept this gate set."
        ),
        "software_validation": {
            "provider": "pennylane",
            "recommended_device": "default.qubit",
            "is_physical_xanadu_qpu": False,
        },
        "physical_x8_track": {
            "access": "separate Xanadu hardware approval and cloud token required",
            "software": "isolated legacy environment with Strawberry Fields / PennyLane-SF",
            "compatibility": "PennyLane-SF remote plugin supports PennyLane only up to 0.29",
            "research_change": (
                "Define and validate a CV/GBS feature map and a photon-count kernel as a new model; "
                "do not compare it as if it were the same Hamiltonian fidelity kernel."
            ),
        },
    }


def _workload_report(workload: dict[str, Any]) -> str:
    measurement = workload["measurement"]
    model = workload["model"]
    samples = workload["samples"]
    return "\n".join(
        [
            "# Hamiltonian kernel: workload sprzętowy",
            "",
            f"Workload ID: `{workload['workload_id']}`.",
            "",
            "## Zamrożony model",
            "",
            f"- Dataset: `{workload['dataset']['name']}`, seed `{workload['dataset']['seed']}`.",
            f"- Kernel: `{measurement['kernel']}`.",
            f"- Kandydat: `{model['candidate']}`.",
            f"- Konfiguracja: `{model['evolution_config']}`.",
            f"- Gamma: `{model['gamma']}`, regularyzacja: `{model['regularization']}`.",
            "- Parametry wybrano przed przygotowaniem benchmarku QPU; etykiety testowe nie stroją modelu.",
            "",
            "## Pomiar",
            "",
            f"- Train: `{len(samples['train']['y'])}` próbek.",
            f"- Test: `{len(samples['test']['y'])}` próbek.",
            f"- Obwody: `{measurement['circuit_count']}`.",
            f"- Całkowity budżet: `{measurement['total_budget']}` circuit-shots.",
            f"- Zakres strzałów na obwód: `{measurement['shots_per_circuit_min']}-{measurement['shots_per_circuit_max']}`.",
            "",
            "## Xanadu",
            "",
            "Ten qubitowy workload można zweryfikować w PennyLane, ale nie jest on programem dla fotonicznego X8.",
            "Fizyczny eksperyment Xanadu wymaga osobnej mapy CV/GBS i stanowi nową hipotezę badawczą.",
            "",
        ]
    )


def prepare_workload(args: argparse.Namespace) -> Path:
    validation_source = (
        _validation_benchmark_source(args)
        if args.pilot_tier == "validation"
        else None
    )
    if validation_source is not None:
        configuration = validation_source["configuration"]
        candidate = configuration["candidate"]
        selected = {
            "candidate": configuration["candidate_name"],
            "evolution_time": candidate["evolution_time"],
            "interaction_strength": candidate["interaction_strength"],
            "transverse_field": candidate["transverse_field"],
            "topology": candidate["topology"],
            "gamma": configuration["gamma"],
            "regularization": configuration["regularization"],
        }
        split = validation_source["split"]
        outer_train_y = np.asarray(split["y_train"], dtype=int)
        outer_test_y = np.asarray(split["y_test"], dtype=int)
        train_local = _balanced_subset_indices(
            outer_train_y,
            args.train_per_class,
            args.sample_seed,
        )
        test_local = _balanced_subset_indices(
            outer_test_y,
            args.test_per_class,
            args.sample_seed + 1,
        )
        train_indices = np.asarray(split["train_indices"], dtype=int)[train_local]
        test_indices = np.asarray(split["test_indices"], dtype=int)[test_local]
        train_x = np.asarray(split["x_train"], dtype=float)[train_local]
        test_x = np.asarray(split["x_test"], dtype=float)[test_local]
        train_y = outer_train_y[train_local]
        test_y = outer_test_y[test_local]
        dataset_name = args.dataset
        preprocessing_description = (
            "exact fold-local standardization, PCA and min-max scaling from frozen outer split"
        )
        pca_explained_ratio = None
        source_selected_results = validation_source["study_binding"]["outer_results_path"]
        study_binding = validation_source["study_binding"]
    else:
        selected = _selected_model(
            args.selected_results.resolve(),
            args.dataset,
            args.seed,
            args.kernel,
        )
        raw = load_dataset(args.dataset, seed=args.seed, smoke=False)
        data = prepare_dataset(raw, n_components=args.n_qubits, seed=args.seed)
        train_indices = _balanced_subset_indices(
            data.y_train, args.train_per_class, args.sample_seed
        )
        test_indices = _balanced_subset_indices(
            data.y_test, args.test_per_class, args.sample_seed + 1
        )
        train_x = data.x_train[train_indices]
        test_x = data.x_test[test_indices]
        train_y = data.y_train[train_indices]
        test_y = data.y_test[test_indices]
        dataset_name = data.name
        preprocessing_description = (
            "standardization, PCA and min-max scaling fitted on full split train"
        )
        pca_explained_ratio = data.pca_explained_ratio
        source_selected_results = str(args.selected_results.resolve())
        study_binding = {
            "tier": "exploratory",
            "excluded_from_confirmatory_benchmark": True,
        }

    config = EvolutionConfig(
        n_qubits=args.n_qubits,
        evolution_time=_float_override(args.evolution_time, selected["evolution_time"]),
        interaction_strength=_float_override(
            args.interaction_strength, selected["interaction_strength"]
        ),
        transverse_field=_float_override(
            args.transverse_field, selected["transverse_field"]
        ),
        topology=args.topology or selected["topology"],
        method="trotter",
        trotter_order=args.trotter_order,
        trotter_steps=args.trotter_steps,
    )
    config.validate()
    all_x = np.vstack((train_x, test_x))
    entries = build_measurement_entries(
        args.kernel,
        train_count=len(train_x),
        total_count=len(all_x),
        total_budget=args.budget,
        seed=args.measurement_seed,
    )

    output_dir = (
        args.output_dir
        or DEFAULT_HARDWARE_ROOT
        / f"{args.dataset}_seed{args.seed}_{args.kernel}_b{args.budget}"
    ).resolve()
    qasm_dir = output_dir / "logical_qasm"
    qasm_dir.mkdir(parents=True, exist_ok=True)
    entry_rows: list[dict[str, Any]] = []
    for entry in entries:
        row = asdict(entry)
        circuit = build_qiskit_measurement_circuit(row, all_x, config)
        try:
            from qiskit import qasm3

            qasm = qasm3.dumps(circuit)
            qasm_path = qasm_dir / f"{entry.circuit_id}.qasm"
            qasm_path.write_text(qasm, encoding="utf-8")
            row["logical_qasm"] = str(qasm_path.relative_to(output_dir))
        except Exception as exc:
            row["logical_qasm"] = None
            row["qasm_export_error"] = str(exc)
        entry_rows.append(row)

    gamma = None if args.kernel == "fidelity" else float(selected["gamma"])
    core_payload: dict[str, Any] = {
        "dataset": {
            "name": dataset_name,
            "seed": args.seed,
            "preprocessing": preprocessing_description,
            "pca_explained_ratio": pca_explained_ratio,
        },
        "model": {
            "candidate": selected["candidate"],
            "kernel": args.kernel,
            "gamma": gamma,
            "regularization": float(selected["regularization"]),
            "source_selected_results": source_selected_results,
            "evolution_config": config_to_dict(config),
        },
        "samples": {
            "selection": "balanced deterministic subset of the frozen outer split",
            "sample_seed": args.sample_seed,
            "train": {
                "split_indices": train_indices.tolist(),
                "x": train_x.tolist(),
                "y": train_y.tolist(),
            },
            "test": {
                "split_indices": test_indices.tolist(),
                "x": test_x.tolist(),
                "y": test_y.tolist(),
            },
        },
        "measurement": {
            "kernel": args.kernel,
            "protocol": (
                "compute-uncompute all-zero probability"
                if args.kernel == "fidelity"
                else "simultaneous local X/Y/Z Pauli measurements"
            ),
            "total_budget": args.budget,
            "circuit_count": len(entries),
            "shots_per_circuit_min": min(entry.shots for entry in entries),
            "shots_per_circuit_max": max(entry.shots for entry in entries),
            "measurement_seed": args.measurement_seed,
            "entries": entry_rows,
        },
        "study_binding": study_binding,
        "xanadu_compatibility": _xanadu_compatibility(),
    }
    workload = {
        "schema": "hamiltonian-kernel-workload-v1",
        "workload_id": workload_identifier(core_payload),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        **core_payload,
    }
    manifest_path = output_dir / "workload.json"
    write_json(manifest_path, workload)
    (output_dir / "workload_report.md").write_text(
        _workload_report(workload), encoding="utf-8"
    )
    write_json(output_dir / "xanadu_compatibility.json", workload["xanadu_compatibility"])
    return manifest_path


def _counts_payload(
    workload: dict[str, Any],
    state: dict[str, Any],
    counts: dict[str, dict[str, int]],
) -> dict[str, Any]:
    return {
        "schema": "hamiltonian-kernel-counts-v1",
        "workload_id": workload["workload_id"],
        "provider": state["provider"],
        "backend": state["backend"],
        "counts": counts,
    }


def _analysis_report(
    analysis: dict[str, Any],
    state: dict[str, Any] | None,
) -> str:
    classification = analysis["classification"]
    error = analysis["kernel_error"]
    provider = "external counts" if state is None else state["provider"]
    backend = "unknown" if state is None else state["backend"]
    qpu_note = (
        "Wynik pochodzi z fizycznego lub zdalnego backendu zadeklarowanego w execution.json."
        if state is not None and not state.get("not_a_qpu_execution", False)
        else "To wykonanie lokalne lub dry-run, nie wynik fizycznego QPU."
    )
    return "\n".join(
        [
            "# Hamiltonian kernel: wynik wykonania",
            "",
            f"- Workload: `{analysis['workload_id']}`.",
            f"- Provider: `{provider}`.",
            f"- Backend: `{backend}`.",
            f"- Kernel: `{analysis['kernel']}`.",
            f"- Budżet: `{analysis['measurement_budget']}` circuit-shots.",
            f"- {qpu_note}",
            "",
            "## Klasyfikacja",
            "",
            f"- Accuracy: {classification['test_accuracy']:.3f}.",
            f"- Balanced accuracy: {classification['test_balanced_accuracy']:.3f}.",
            f"- Macro-F1: {classification['test_macro_f1']:.3f}.",
            f"- Idealna balanced accuracy na tym podzbiorze: {classification['ideal_test_balanced_accuracy']:.3f}.",
            "",
            "## Błąd kernela",
            "",
            f"- Train relative Frobenius: {error['train_relative_frobenius']:.3e}.",
            f"- Test relative Frobenius: {error['test_relative_frobenius']:.3e}.",
            "",
        ]
    )


def analyze_and_write(
    workload: dict[str, Any],
    counts: dict[str, dict[str, int]],
    output_dir: Path,
    state: dict[str, Any] | None,
) -> dict[str, Any]:
    analysis = analyze_hardware_counts(workload, counts)
    write_json(output_dir / "analysis.json", analysis)
    (output_dir / "report.md").write_text(
        _analysis_report(analysis, state), encoding="utf-8"
    )
    np.savetxt(
        output_dir / "train_kernel.csv",
        np.asarray(analysis["train_kernel"]),
        delimiter=",",
    )
    np.savetxt(
        output_dir / "test_kernel.csv",
        np.asarray(analysis["test_kernel"]),
        delimiter=",",
    )
    for matrix_name in (
        "raw_train",
        "raw_test",
        "raw_diagonal",
        "psd_train",
        "spectral_train",
        "spectral_test",
        "raw_eigenvalues",
        "psd_eigenvalues",
        "spectral_eigenvalues",
    ):
        np.savetxt(
            output_dir / f"kernel_{matrix_name}.csv",
            np.asarray(analysis["kernel_matrices"][matrix_name]),
            delimiter=",",
        )
    return analysis


def run_workload(args: argparse.Namespace) -> None:
    workload_path = args.workload.resolve()
    workload = _read_json(workload_path)
    output_dir = (args.output_dir or workload_path.parent / args.provider).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "execution.json"
    if state_path.exists() and not args.allow_existing:
        raise FileExistsError(
            f"Execution state already exists: {state_path}. Use retrieve or a new output directory."
        )
    if args.provider in {"ibm", "ionq", "braket"} and not args.dry_run:
        if not args.confirm_submit:
            raise ValueError(
                "Remote execution can consume QPU quota or funds. "
                "Pass --confirm-submit to submit intentionally."
            )
    binding = workload.get("study_binding", {})
    if args.provider == "ibm" and binding.get("tier") == "qpu_validation_of_completed_benchmark":
        if args.seed != int(binding["transpile_seed"]):
            raise ValueError("IBM transpile seed differs from the frozen validation pilot")
        if args.optimization_level != int(binding["optimization_level"]):
            raise ValueError("IBM optimization level differs from the frozen validation pilot")

    counts: dict[str, dict[str, int]] | None = None
    if args.provider == "aer":
        state, counts = execute_aer(workload, args.seed, args.optimization_level)
    elif args.provider == "pennylane":
        state, counts = execute_pennylane(workload, args.device, seed=args.seed)
    elif args.provider == "braket-local":
        state, counts = execute_braket_local(workload)
    elif args.provider == "ibm":
        state = submit_ibm(
            workload,
            backend_name=args.backend or "least_busy",
            channel=args.ibm_channel,
            optimization_level=args.optimization_level,
            max_circuits_per_job=args.max_circuits_per_job,
            dry_run=args.dry_run,
            state_path=state_path,
            transpile_seed=args.seed,
            initial_layout=args.ibm_initial_layout,
        )
    elif args.provider == "ionq":
        if args.optimization_level > 1:
            raise ValueError("IonQ recommends Qiskit optimization level 0 or 1")
        state = submit_ionq(
            workload,
            backend_name=args.backend or "simulator",
            gateset=args.ionq_gateset,
            optimization_level=args.optimization_level,
            max_circuits_per_job=args.max_circuits_per_job,
            dry_run=args.dry_run,
            state_path=state_path,
        )
    elif args.provider == "braket":
        if not args.backend:
            raise ValueError("Braket requires --backend with a device ARN")
        state = submit_braket(
            workload,
            device_arn=args.backend,
            s3_bucket=args.s3_bucket,
            s3_prefix=args.s3_prefix,
            dry_run=args.dry_run,
            state_path=state_path,
        )
    else:
        raise ValueError(f"Unsupported provider: {args.provider}")

    write_json(state_path, state)
    if counts is not None:
        write_json(output_dir / "counts.json", _counts_payload(workload, state, counts))
        analysis = analyze_and_write(workload, counts, output_dir, state)
        print(
            json.dumps(
                {
                    "status": state["status"],
                    "provider": state["provider"],
                    "backend": state["backend"],
                    "test_balanced_accuracy": analysis["classification"][
                        "test_balanced_accuracy"
                    ],
                    "output_dir": str(output_dir),
                },
                indent=2,
            )
        )
    else:
        print(json.dumps(state, indent=2))


def retrieve_workload(args: argparse.Namespace) -> None:
    workload = _read_json(args.workload.resolve())
    state_path = args.state.resolve()
    state = _read_json(state_path)
    state, counts = retrieve_remote(
        workload,
        state,
        wait=args.wait,
        state_path=state_path,
        ionq_gateset=args.ionq_gateset,
        ibm_channel=args.ibm_channel,
    )
    output_dir = state_path.parent
    if state["status"] == "completed":
        write_json(output_dir / "counts.json", _counts_payload(workload, state, counts))
        analysis = analyze_and_write(workload, counts, output_dir, state)
        print(
            json.dumps(
                {
                    "status": "completed",
                    "test_balanced_accuracy": analysis["classification"][
                        "test_balanced_accuracy"
                    ],
                    "output_dir": str(output_dir),
                },
                indent=2,
            )
        )
    else:
        print(json.dumps({"status": state["status"], "state": str(state_path)}, indent=2))


def analyze_command(args: argparse.Namespace) -> None:
    workload = _read_json(args.workload.resolve())
    counts_payload = _read_json(args.counts.resolve())
    if counts_payload["workload_id"] != workload["workload_id"]:
        raise ValueError("Counts belong to a different workload")
    state = _read_json(args.state.resolve()) if args.state else None
    output_dir = (args.output_dir or args.counts.resolve().parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = analyze_and_write(workload, counts_payload["counts"], output_dir, state)
    print(json.dumps(analysis["classification"], indent=2))


def xanadu_plan(args: argparse.Namespace) -> None:
    compatibility = _xanadu_compatibility()
    if args.workload:
        workload = _read_json(args.workload.resolve())
        compatibility = workload["xanadu_compatibility"]
    output = args.output.resolve()
    write_json(output, compatibility)
    print(json.dumps(compatibility, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare, submit, retrieve and analyze Hamiltonian-kernel hardware workloads"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Freeze samples and generate logical circuits")
    prepare.add_argument("--dataset", choices=("moons", "wdbc", "wine"), default="moons")
    prepare.add_argument("--pilot-tier", choices=("exploratory", "validation"), default="exploratory")
    prepare.add_argument("--protocol", type=Path)
    prepare.add_argument("--benchmark-completion", type=Path)
    prepare.add_argument("--outer-results", type=Path)
    prepare.add_argument("--outer-repeat", type=int, default=0)
    prepare.add_argument("--outer-fold", type=int, default=0)
    prepare.add_argument("--seed", type=int, default=0)
    prepare.add_argument("--kernel", choices=("fidelity", "projected"), default="projected")
    prepare.add_argument("--budget", type=int, default=20_000)
    prepare.add_argument("--train-per-class", type=int, default=3)
    prepare.add_argument("--test-per-class", type=int, default=2)
    prepare.add_argument("--sample-seed", type=int, default=20260901)
    prepare.add_argument("--measurement-seed", type=int, default=20260902)
    prepare.add_argument("--n-qubits", type=int, default=4)
    prepare.add_argument("--trotter-order", type=int, choices=(1, 2), default=2)
    prepare.add_argument("--trotter-steps", type=int, default=2)
    prepare.add_argument("--evolution-time", type=float)
    prepare.add_argument("--interaction-strength", type=float)
    prepare.add_argument("--transverse-field", type=float)
    prepare.add_argument("--topology", choices=("chain", "ring", "all_to_all"))
    prepare.add_argument("--selected-results", type=Path, default=DEFAULT_SELECTED_RESULTS)
    prepare.add_argument("--output-dir", type=Path)

    run = subparsers.add_parser("run", help="Execute locally or submit to a remote provider")
    run.add_argument("--workload", type=Path, required=True)
    run.add_argument(
        "--provider",
        choices=("aer", "pennylane", "braket-local", "ibm", "ionq", "braket"),
        default="aer",
    )
    run.add_argument("--backend")
    run.add_argument("--device", default="default.qubit")
    run.add_argument("--seed", type=int, default=20260903)
    run.add_argument("--optimization-level", type=int, choices=(0, 1, 2, 3), default=1)
    run.add_argument("--max-circuits-per-job", type=int, default=100)
    run.add_argument("--ibm-channel", default="ibm_quantum_platform")
    run.add_argument(
        "--ibm-initial-layout",
        type=lambda value: [int(item.strip()) for item in value.split(",")],
        help="Comma-separated physical qubits used as the fixed IBM initial layout",
    )
    run.add_argument("--ionq-gateset", choices=("qis", "native"), default="qis")
    run.add_argument("--s3-bucket")
    run.add_argument("--s3-prefix", default="hamiltonian-kernel")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument(
        "--confirm-submit",
        action="store_true",
        help="Acknowledge that a remote run may consume QPU quota or funds",
    )
    run.add_argument(
        "--allow-existing",
        action="store_true",
        help="Resume a remote submission or deliberately replace local/dry-run output",
    )
    run.add_argument("--output-dir", type=Path)

    retrieve = subparsers.add_parser("retrieve", help="Retrieve submitted remote jobs")
    retrieve.add_argument("--workload", type=Path, required=True)
    retrieve.add_argument("--state", type=Path, required=True)
    retrieve.add_argument("--wait", action="store_true")
    retrieve.add_argument("--ibm-channel", default="ibm_quantum_platform")
    retrieve.add_argument("--ionq-gateset", choices=("qis", "native"), default="qis")

    analyze = subparsers.add_parser("analyze", help="Analyze a completed counts file")
    analyze.add_argument("--workload", type=Path, required=True)
    analyze.add_argument("--counts", type=Path, required=True)
    analyze.add_argument("--state", type=Path)
    analyze.add_argument("--output-dir", type=Path)

    xanadu = subparsers.add_parser(
        "xanadu-plan", help="Write the explicit qubit-to-photonic compatibility decision"
    )
    xanadu.add_argument("--workload", type=Path)
    xanadu.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_HARDWARE_ROOT / "xanadu_compatibility.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        manifest = prepare_workload(args)
        print(json.dumps({"status": "prepared", "workload": str(manifest)}, indent=2))
    elif args.command == "run":
        run_workload(args)
    elif args.command == "retrieve":
        retrieve_workload(args)
    elif args.command == "analyze":
        analyze_command(args)
    elif args.command == "xanadu-plan":
        xanadu_plan(args)
    else:
        raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
