from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .core import (
    X8_MODES,
    config_from_dict,
    gbs_distribution,
    sample_record_from_array,
    x8_interferometer,
)
from .experiment import analyze_records, workload_identifier


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "analysis_output" / "photonic_kernel_x8_remote"
PUBLIC_XANADU_CLOUD_AVAILABLE = False
CLOUD_STATUS_CHECKED_UTC = "2026-08-17"
OFFICIAL_CLOUD_STATUS_URL = (
    "https://strawberryfields.readthedocs.io/en/latest/introduction/circuits.html#compilation"
)
COMPLETED_STATUSES = {"complete", "completed", "success", "succeeded"}
FAILED_STATUS_FRAGMENTS = ("fail", "error", "cancel", "lost")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _matrix_from_entry(entry: dict[str, Any]) -> np.ndarray:
    payload = entry["interferometer"]
    matrix = np.asarray(payload["real"], dtype=float) + 1j * np.asarray(
        payload["imag"], dtype=float
    )
    if matrix.shape != (4, 4):
        raise ValueError(
            f"Circuit {entry.get('circuit_id')} has interferometer shape {matrix.shape}"
        )
    return matrix


def program_specification(
    entry: dict[str, Any],
    workload: dict[str, Any],
) -> dict[str, Any]:
    config = config_from_dict(workload["model"]["config"])
    unitary = _matrix_from_entry(entry)
    return {
        "modes": X8_MODES,
        "operations": [
            *[
                {
                    "gate": "S2gate",
                    "modes": [mode, mode + 4],
                    "parameters": [float(squeezing), 0.0],
                }
                for mode, squeezing in enumerate(config.squeezing)
            ],
            {
                "gate": "Interferometer",
                "modes": [0, 1, 2, 3],
                "matrix": entry["interferometer"],
            },
            {
                "gate": "Interferometer",
                "modes": [4, 5, 6, 7],
                "matrix": entry["interferometer"],
            },
            {
                "gate": "MeasureFock",
                "modes": list(range(X8_MODES)),
            },
        ],
    }


def validate_workload(workload: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []
    if workload.get("schema") != "photonic_kernel.x8_gbs.v1":
        problems.append(f"unsupported schema: {workload.get('schema')!r}")
    if workload.get("workload_id") != workload_identifier(workload):
        problems.append("workload_id does not match the canonical payload")
    try:
        config = config_from_dict(workload["model"]["config"])
    except Exception as exc:
        problems.append(f"invalid model config: {exc}")
        config = None
    if not workload.get("model", {}).get("not_a_qubit_backend_port", False):
        problems.append("workload does not identify itself as a separate photonic model")
    if workload.get("model", {}).get("target_topology") != "X8/Xunitary":
        problems.append("target topology is not X8/Xunitary")

    measurement = workload.get("measurement", {})
    entries = measurement.get("entries", [])
    if int(measurement.get("circuit_count", -1)) != len(entries):
        problems.append("circuit_count differs from the number of entries")
    shots = [int(entry.get("shots", 0)) for entry in entries]
    if any(value < 1 for value in shots):
        problems.append("each circuit must receive at least one shot")
    if sum(shots) != int(measurement.get("total_budget", -1)):
        problems.append("entry shots do not equal the total raw PNR budget")
    circuit_ids = [str(entry.get("circuit_id")) for entry in entries]
    if len(circuit_ids) != len(set(circuit_ids)):
        problems.append("circuit IDs are not unique")

    train_count = len(workload.get("samples", {}).get("train", {}).get("x", []))
    test_count = len(workload.get("samples", {}).get("test", {}).get("x", []))
    if len(entries) != train_count + test_count:
        problems.append("circuit entries do not match train plus test sample counts")

    maximum_unitarity_error = 0.0
    maximum_serialization_error = 0.0
    if config is not None:
        for entry in entries:
            try:
                unitary = _matrix_from_entry(entry)
                unitarity_error = float(
                    np.linalg.norm(unitary.conj().T @ unitary - np.eye(4), "fro")
                )
                maximum_unitarity_error = max(maximum_unitarity_error, unitarity_error)
                expected = x8_interferometer(
                    np.asarray(entry["x"], dtype=float),
                    config,
                )
                serialization_error = float(np.linalg.norm(unitary - expected, "fro"))
                maximum_serialization_error = max(
                    maximum_serialization_error,
                    serialization_error,
                )
                specification = program_specification(entry, workload)
                operations = specification["operations"]
                if [row["modes"] for row in operations[:4]] != [
                    [0, 4],
                    [1, 5],
                    [2, 6],
                    [3, 7],
                ]:
                    problems.append(
                        f"{entry.get('circuit_id')}: invalid two-mode squeezing topology"
                    )
                if operations[4]["modes"] != [0, 1, 2, 3] or operations[5][
                    "modes"
                ] != [4, 5, 6, 7]:
                    problems.append(
                        f"{entry.get('circuit_id')}: invalid repeated-unitary topology"
                    )
                if operations[4]["matrix"] != operations[5]["matrix"]:
                    problems.append(
                        f"{entry.get('circuit_id')}: the two X8 halves use different matrices"
                    )
            except Exception as exc:
                problems.append(f"{entry.get('circuit_id')}: {exc}")
    if maximum_unitarity_error > 1e-10:
        problems.append(
            f"maximum interferometer unitarity error is {maximum_unitarity_error:.3e}"
        )
    if maximum_serialization_error > 1e-12:
        problems.append(
            f"maximum serialized-unitary error is {maximum_serialization_error:.3e}"
        )
    return {
        "passed": not problems,
        "problems": problems,
        "workload_id": workload.get("workload_id"),
        "circuit_count": len(entries),
        "total_budget": sum(shots),
        "maximum_unitarity_error": maximum_unitarity_error,
        "maximum_serialization_error": maximum_serialization_error,
        "x8_constraints": {
            "two_mode_squeezing_pairs": [[0, 4], [1, 5], [2, 6], [3, 7]],
            "repeated_interferometer_halves": [[0, 1, 2, 3], [4, 5, 6, 7]],
            "all_modes_measured_with_pnr": True,
        },
    }


def _load_strawberry_fields() -> tuple[Any, Any]:
    try:
        import strawberryfields as sf
        from strawberryfields import ops
    except Exception as exc:
        raise RuntimeError(
            "Strawberry Fields is unavailable. Use the isolated Python 3.10 "
            "environment from requirements-xanadu-x8.txt."
        ) from exc
    return sf, ops


def _require_supported_remote_runtime() -> None:
    if not ((3, 8) <= sys.version_info[:2] <= (3, 10)):
        raise RuntimeError(
            "Remote X8 submission is intentionally restricted to Python 3.8-3.10, "
            "the supported range of Strawberry Fields 0.23. Use an isolated Python 3.10 environment."
        )


def build_sf_program(
    entry: dict[str, Any],
    workload: dict[str, Any],
) -> Any:
    sf, ops = _load_strawberry_fields()
    config = config_from_dict(workload["model"]["config"])
    unitary = _matrix_from_entry(entry)
    program = sf.Program(X8_MODES, name=str(entry["circuit_id"]))
    with program.context as modes:
        for mode, squeezing in enumerate(config.squeezing):
            ops.S2gate(float(squeezing), 0.0) | (modes[mode], modes[mode + 4])
        ops.Interferometer(unitary) | tuple(modes[:4])
        ops.Interferometer(unitary) | tuple(modes[4:])
        ops.MeasureFock() | tuple(modes)
    return program


def compile_sf_program(entry: dict[str, Any], workload: dict[str, Any]) -> Any:
    program = build_sf_program(entry, workload)
    return program.compile(compiler="Xunitary")


def _compiled_summary(program: Any) -> dict[str, Any]:
    circuit = list(getattr(program, "circuit", []))
    operation_names: list[str] = []
    for command in circuit:
        operation = getattr(command, "op", None)
        operation_names.append(type(operation).__name__)
    return {
        "command_count": len(circuit),
        "operation_names": operation_names,
    }


def validate_command(args: argparse.Namespace) -> Path:
    workload_path = args.workload.resolve()
    workload = _read_json(workload_path)
    validation = validate_workload(workload)
    validation.update(
        {
            "schema": "photonic_kernel.x8_validation.v1",
            "created_utc": _utc_now(),
            "not_a_qpu_execution": True,
            "python": platform.python_version(),
            "strawberry_fields": {},
            "remote_service": {
                "public_xanadu_cloud_available": PUBLIC_XANADU_CLOUD_AVAILABLE,
                "status_checked_utc": CLOUD_STATUS_CHECKED_UTC,
                "official_status_url": OFFICIAL_CLOUD_STATUS_URL,
                "submission_supported_by_default": False,
            },
        }
    )
    if validation["passed"]:
        if importlib.util.find_spec("strawberryfields") is None:
            validation["strawberry_fields"] = {
                "available": False,
                "compiled": False,
                "reason": (
                    "The current environment has no Strawberry Fields installation; "
                    "static X8 validation completed."
                ),
            }
        else:
            try:
                summaries = [
                    _compiled_summary(compile_sf_program(entry, workload))
                    for entry in workload["measurement"]["entries"]
                ]
                validation["strawberry_fields"] = {
                    "available": True,
                    "compiled": True,
                    "compiler": "Xunitary",
                    "programs": summaries,
                }
            except Exception as exc:
                validation["strawberry_fields"] = {
                    "available": True,
                    "compiled": False,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
                if args.require_compiler:
                    validation["passed"] = False
                    validation["problems"].append(
                        "Strawberry Fields Xunitary compilation failed"
                    )
    if args.require_compiler and not validation["strawberry_fields"].get(
        "compiled", False
    ):
        validation["passed"] = False
        if "Xunitary compiler was required but unavailable" not in validation["problems"]:
            validation["problems"].append(
                "Xunitary compiler was required but unavailable"
            )
    output = (args.output or workload_path.with_name("xanadu_validation.json")).resolve()
    _write_json_atomic(output, validation)
    if not validation["passed"]:
        raise RuntimeError("X8 validation failed: " + "; ".join(validation["problems"]))
    return output


def _initial_execution(
    workload: dict[str, Any],
    workload_path: Path,
    target: str,
) -> dict[str, Any]:
    return {
        "schema": "photonic_kernel.x8_execution.v1",
        "workload_id": workload["workload_id"],
        "workload_path": str(workload_path),
        "provider": "legacy/private Xanadu Cloud through Strawberry Fields RemoteEngine",
        "target": target,
        "status": "prepared",
        "created_utc": _utc_now(),
        "updated_utc": _utc_now(),
        "qpu_execution_verified": False,
        "credentials_persisted": False,
        "jobs": [
            {
                "circuit_id": entry["circuit_id"],
                "shots": int(entry["shots"]),
                "status": "prepared",
                "job_id": None,
            }
            for entry in workload["measurement"]["entries"]
        ],
    }


def _load_or_create_execution(
    state_path: Path,
    workload: dict[str, Any],
    workload_path: Path,
    target: str,
    allow_existing: bool,
) -> dict[str, Any]:
    if state_path.exists():
        if not allow_existing:
            raise FileExistsError(
                f"Execution state already exists: {state_path}. Use --allow-existing to resume."
            )
        state = _read_json(state_path)
        if state.get("workload_id") != workload["workload_id"]:
            raise ValueError("Existing execution belongs to a different workload")
        if state.get("target") != target:
            raise ValueError("Existing execution uses a different Xanadu target")
        if state.get("status") == "submission_unknown":
            raise RuntimeError(
                "A previous submission has unknown status. Inspect the Xanadu dashboard "
                "before retrying to avoid a duplicate paid job."
            )
        return state
    state = _initial_execution(workload, workload_path, target)
    _write_json_atomic(state_path, state)
    return state


def _job_identifier(job: Any) -> str:
    for attribute in ("id", "job_id", "id_"):
        value = getattr(job, attribute, None)
        if callable(value):
            value = value()
        if value:
            return str(value)
    raise RuntimeError("Xanadu submission returned a job without an identifier")


def submit_command(args: argparse.Namespace) -> Path:
    if not args.confirm_submit:
        raise RuntimeError(
            "Remote submission can consume restricted hardware allocation. Add --confirm-submit."
        )
    if args.target != "X8":
        raise ValueError("This adapter only supports the physical X8 target")
    if not args.allow_retired_cloud_endpoint:
        raise RuntimeError(
            "Official Strawberry Fields documentation states that Xanadu Quantum Cloud "
            "is no longer available. Submission is disabled by default. Use "
            "--allow-retired-cloud-endpoint only if Xanadu has separately confirmed a "
            "working private or legacy endpoint for this account."
        )
    _require_supported_remote_runtime()
    sf, _ = _load_strawberry_fields()
    workload_path = args.workload.resolve()
    workload = _read_json(workload_path)
    validation = validate_workload(workload)
    if not validation["passed"]:
        raise ValueError("Invalid workload: " + "; ".join(validation["problems"]))

    output_dir = (args.output_dir or DEFAULT_OUTPUT_ROOT / workload["workload_id"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "execution.json"
    state = _load_or_create_execution(
        state_path,
        workload,
        workload_path,
        args.target,
        args.allow_existing,
    )
    entries = {
        str(entry["circuit_id"]): entry
        for entry in workload["measurement"]["entries"]
    }
    engine = sf.RemoteEngine(args.target)
    for job_state in state["jobs"]:
        if job_state.get("job_id"):
            continue
        circuit_id = str(job_state["circuit_id"])
        program = build_sf_program(entries[circuit_id], workload)
        compile_sf_program(entries[circuit_id], workload)
        job_state["status"] = "submitting"
        state["status"] = "submitting"
        state["updated_utc"] = _utc_now()
        _write_json_atomic(state_path, state)
        try:
            job = engine.run_async(program, shots=int(job_state["shots"]))
            job_id = _job_identifier(job)
        except Exception as exc:
            job_state["status"] = "submission_unknown"
            job_state["error"] = f"{type(exc).__name__}: {exc}"
            state["status"] = "submission_unknown"
            state["updated_utc"] = _utc_now()
            _write_json_atomic(state_path, state)
            raise RuntimeError(
                f"Submission status for {circuit_id} is unknown. Inspect the Xanadu "
                "dashboard before retrying."
            ) from exc
        job_state["job_id"] = job_id
        job_state["status"] = "submitted"
        job_state["submitted_utc"] = _utc_now()
        state["updated_utc"] = _utc_now()
        _write_json_atomic(state_path, state)
    state["status"] = "submitted"
    state["updated_utc"] = _utc_now()
    _write_json_atomic(state_path, state)
    return state_path


def _load_xcc() -> Any:
    try:
        import xcc
    except Exception as exc:
        raise RuntimeError(
            "xanadu-cloud-client is unavailable. Use requirements-xanadu-x8.txt."
        ) from exc
    return xcc


def _status_text(job: Any) -> str:
    value = getattr(job, "status", "unknown")
    if callable(value):
        value = value()
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip().lower()


def _result_samples(job: Any) -> np.ndarray:
    result = getattr(job, "result", None)
    if callable(result):
        result = result()
    if not isinstance(result, dict) or "output" not in result:
        raise RuntimeError("Xanadu job result has no output array")
    output = result["output"]
    if not isinstance(output, (list, tuple)) or not output:
        raise RuntimeError("Xanadu job output is empty")
    samples = np.asarray(output[0])
    if samples.ndim != 2 or samples.shape[1] != X8_MODES:
        raise RuntimeError(f"Unexpected Xanadu sample shape: {samples.shape}")
    return samples


def _analyze_and_write(
    workload: dict[str, Any],
    records: dict[str, dict[str, Any]],
    output_dir: Path,
    source: str,
    qpu_execution: bool,
) -> Path:
    config = config_from_dict(workload["model"]["config"])
    ideal = [
        gbs_distribution(np.asarray(entry["x"], dtype=float), config)
        for entry in workload["measurement"]["entries"]
    ]
    analysis = analyze_records(workload, records, ideal)
    analysis["source"] = source
    analysis["qpu_execution"] = bool(qpu_execution)
    path = output_dir / "analysis.json"
    _write_json_atomic(path, analysis)
    for kernel_name, matrices in analysis["kernels"].items():
        for matrix_name, values in matrices.items():
            np.savetxt(
                output_dir / f"{kernel_name}_{matrix_name}.csv",
                np.asarray(values, dtype=float),
                delimiter=",",
                fmt="%.12g",
            )
    return path


def retrieve_command(args: argparse.Namespace) -> Path:
    _require_supported_remote_runtime()
    xcc = _load_xcc()
    workload_path = args.workload.resolve()
    state_path = args.state.resolve()
    workload = _read_json(workload_path)
    state = _read_json(state_path)
    if state.get("workload_id") != workload.get("workload_id"):
        raise ValueError("Execution state and workload IDs differ")
    if state.get("target") != "X8":
        raise ValueError("Execution state is not for X8")
    connection = xcc.Connection.load()
    records: dict[str, dict[str, Any]] = {}
    all_completed = True
    any_failed = False
    for job_state in state["jobs"]:
        job_id = job_state.get("job_id")
        if not job_id:
            all_completed = False
            continue
        job = xcc.Job(str(job_id), connection)
        if args.wait:
            job.wait()
        status = _status_text(job)
        job_state["remote_status"] = status
        if status in COMPLETED_STATUSES:
            samples = _result_samples(job)
            expected_shots = int(job_state["shots"])
            if len(samples) != expected_shots:
                raise RuntimeError(
                    f"Job {job_id} returned {len(samples)} shots, expected {expected_shots}"
                )
            records[str(job_state["circuit_id"])] = sample_record_from_array(
                samples,
                int(workload["measurement"]["max_total_photons"]),
            )
            job_state["status"] = "completed"
            job_state["completed_utc"] = _utc_now()
        elif any(fragment in status for fragment in FAILED_STATUS_FRAGMENTS):
            job_state["status"] = "failed"
            any_failed = True
            all_completed = False
        else:
            job_state["status"] = "running"
            all_completed = False

    output_dir = state_path.parent
    state["updated_utc"] = _utc_now()
    if any_failed:
        state["status"] = "failed"
    elif all_completed and len(records) == len(state["jobs"]):
        state["status"] = "completed"
        state["qpu_execution_verified"] = True
        state["not_a_qpu_execution"] = False
        counts_path = output_dir / "counts.json"
        _write_json_atomic(
            counts_path,
            {
                "schema": "photonic_kernel.sample_records.v1",
                "workload_id": workload["workload_id"],
                "source": "Xanadu Cloud X8",
                "not_a_qpu_execution": False,
                "records": records,
            },
        )
        state["counts_path"] = str(counts_path)
        state["analysis_path"] = str(
            _analyze_and_write(
                workload,
                records,
                output_dir,
                source="Xanadu Cloud X8",
                qpu_execution=True,
            )
        )
    else:
        state["status"] = "running"
        state["qpu_execution_verified"] = False
    _write_json_atomic(state_path, state)
    return state_path


def analyze_command(args: argparse.Namespace) -> Path:
    workload = _read_json(args.workload.resolve())
    counts = _read_json(args.counts.resolve())
    if counts.get("workload_id") != workload.get("workload_id"):
        raise ValueError("Counts and workload IDs differ")
    records = counts.get("records")
    if not isinstance(records, dict):
        raise ValueError("Counts file has no sample-record dictionary")
    output_dir = (args.output_dir or args.counts.resolve().parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return _analyze_and_write(
        workload,
        records,
        output_dir,
        source=str(counts.get("source", "external sample records")),
        qpu_execution=not bool(counts.get("not_a_qpu_execution", True)),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, submit, retrieve, and analyze Xanadu X8 GBS workloads"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate X8 topology and optionally compile")
    validate.add_argument("--workload", type=Path, required=True)
    validate.add_argument("--output", type=Path)
    validate.add_argument("--require-compiler", action="store_true")
    validate.set_defaults(handler=validate_command)

    submit = subparsers.add_parser("submit", help="submit one X8 job per frozen sample")
    submit.add_argument("--workload", type=Path, required=True)
    submit.add_argument("--target", default="X8")
    submit.add_argument("--output-dir", type=Path)
    submit.add_argument("--confirm-submit", action="store_true")
    submit.add_argument("--allow-retired-cloud-endpoint", action="store_true")
    submit.add_argument("--allow-existing", action="store_true")
    submit.set_defaults(handler=submit_command)

    retrieve = subparsers.add_parser("retrieve", help="retrieve X8 jobs from execution state")
    retrieve.add_argument("--workload", type=Path, required=True)
    retrieve.add_argument("--state", type=Path, required=True)
    retrieve.add_argument("--wait", action="store_true")
    retrieve.set_defaults(handler=retrieve_command)

    analyze = subparsers.add_parser("analyze", help="analyze local or X8 PNR sample records")
    analyze.add_argument("--workload", type=Path, required=True)
    analyze.add_argument("--counts", type=Path, required=True)
    analyze.add_argument("--output-dir", type=Path)
    analyze.set_defaults(handler=analyze_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.handler(args)
    print(result)


if __name__ == "__main__":
    main()
