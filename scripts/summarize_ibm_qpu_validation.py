from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def accepted_run(path: Path) -> dict[str, Any]:
    state = read_json(path / "execution.json")
    analysis = read_json(path / "analysis.json")
    diagonal = np.asarray(analysis["kernel_matrices"]["raw_diagonal"], dtype=float)
    matrices = {}
    for matrix_path in sorted(path.glob("kernel_*.csv")):
        matrices[matrix_path.name] = {
            "path": str(matrix_path.resolve()),
            "sha256": sha256(matrix_path),
        }
    return {
        "path": str(path.resolve()),
        "workload_id": state["workload_id"],
        "backend": state["backend"],
        "jobs": [batch["job_id"] for batch in state["batches"]],
        "job_qpu_seconds": [
            batch.get("qpu_usage", {}).get("quantum_seconds")
            for batch in state["batches"]
        ],
        "runtime_options": state.get("runtime_options"),
        "qubit_initialization": state.get("qubit_initialization"),
        "physical_layout": state.get("requested_initial_layout"),
        "resource_axes": state["resource_axes"],
        "classification": analysis["classification"],
        "kernel_error": analysis["kernel_error"],
        "kernel_diagnostics": analysis["train_kernel_diagnostics"],
        "raw_diagonal": {
            "values": diagonal.tolist(),
            "minimum": float(diagonal.min()),
            "mean": float(diagonal.mean()),
            "maximum": float(diagonal.max()),
        },
        "matrix_artifacts": matrices,
    }


def development_cost(roots: list[Path], controls_root: Path) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = {}
    run_count = 0
    circuit_shots = 0
    map_executions = 0
    two_qubit_gate_shots = 0
    for root in roots:
        for state_path in sorted(root.glob("*/execution.json")):
            state = read_json(state_path)
            if state.get("provider") != "ibm" or state.get("dry_run"):
                continue
            run_count += 1
            axes = state.get("resource_axes", {})
            circuit_shots += int(axes.get("circuit_shots") or 0)
            map_executions += int(axes.get("map_executions") or 0)
            two_qubit_gate_shots += int(axes.get("two_qubit_gate_shots") or 0)
            for batch in state.get("batches", []):
                job_id = batch.get("job_id")
                if job_id:
                    jobs[job_id] = {
                        "job_id": job_id,
                        "path": str(state_path.parent.resolve()),
                        "quantum_seconds": batch.get("qpu_usage", {}).get(
                            "quantum_seconds"
                        ),
                    }
    control_circuit_shots = 0
    for result_path in sorted(controls_root.glob("*/result.json")):
        result = read_json(result_path)
        execution_path = result_path.with_name("execution.json")
        execution = read_json(execution_path)
        job_id = execution["job_id"]
        jobs[job_id] = {
            "job_id": job_id,
            "path": str(result_path.parent.resolve()),
            "quantum_seconds": execution.get("qpu_usage", {}).get("quantum_seconds"),
        }
        shots = int(result["shots_per_circuit"]) * len(result["counts"])
        control_circuit_shots += shots
    return {
        "benchmark_run_count": run_count,
        "unique_qpu_job_count_including_controls": len(jobs),
        "benchmark_circuit_shots": circuit_shots,
        "control_circuit_shots": control_circuit_shots,
        "total_circuit_shots": circuit_shots + control_circuit_shots,
        "benchmark_map_executions": map_executions,
        "benchmark_two_qubit_gate_shots": two_qubit_gate_shots,
        "total_qpu_time_seconds": float(
            sum(float(job["quantum_seconds"] or 0.0) for job in jobs.values())
        ),
        "qpu_credits": None,
        "qpu_credit_status": "not_reported_by_runtime_jobs",
        "jobs": list(jobs.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fidelity-dir", type=Path, required=True)
    parser.add_argument("--projected-dir", type=Path, required=True)
    parser.add_argument("--layout-selection", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--controls-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    fidelity = accepted_run(args.fidelity_dir.resolve())
    projected = accepted_run(args.projected_dir.resolve())
    if fidelity["physical_layout"] != projected["physical_layout"]:
        raise ValueError("Accepted kernels do not use the same physical layout")
    if fidelity["resource_axes"]["circuit_shots"] != projected["resource_axes"][
        "circuit_shots"
    ]:
        raise ValueError("Accepted kernels do not use the same circuit-shot budget")

    layout = read_json(args.layout_selection.resolve())
    audit = read_json(args.audit.resolve())
    cost = development_cost(
        [args.fidelity_dir.resolve().parent, args.projected_dir.resolve().parent],
        args.controls_root.resolve(),
    )
    payload = {
        "schema": "ibm-resource-aware-kernel-validation-v1",
        "scientific_status": (
            "accepted_as_a_small QPU validation pilot; not an estimate of population-level "
            "model superiority"
        ),
        "hypothesis_status": "benchmark hypothesis and circuit-shot budget remained frozen",
        "sample_size": {"train": 6, "test": 4},
        "layout_selection": layout,
        "independent_audit": {
            "path": str(args.audit.resolve()),
            "status": audit["status"],
            "passed": audit["passed"],
            "total": audit["total"],
        },
        "accepted": {"fidelity": fidelity, "projected": projected},
        "comparison": {
            "equal_circuit_shot_budget": True,
            "circuit_shots_each": fidelity["resource_axes"]["circuit_shots"],
            "balanced_accuracy_difference_projected_minus_fidelity": (
                projected["classification"]["test_balanced_accuracy"]
                - fidelity["classification"]["test_balanced_accuracy"]
            ),
            "qpu_time_difference_seconds_projected_minus_fidelity": (
                projected["resource_axes"]["qpu_time_seconds"]
                - fidelity["resource_axes"]["qpu_time_seconds"]
            ),
            "interpretation": (
                "The four-sample test set is too small for a comparative efficacy claim. "
                "The QPU run validates execution and resource accounting only."
            ),
        },
        "development_cost_including_rejected_diagnostics": cost,
        "rejected_attempt_policy": (
            "Earlier executions remain in the audit trail but are excluded because they did "
            "not use the accepted common physical layout or failed the fidelity identity-diagonal control."
        ),
    }
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json = output_dir / "summary.json"
    summary_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    f_axes = fidelity["resource_axes"]
    p_axes = projected["resource_axes"]
    lines = [
        "# IBM Quantum validation: accepted pilot",
        "",
        "## Status",
        "",
        "The accepted pilot ran on `ibm_kingston` with the common physical layout "
        "`[89, 90, 91, 98]`, explicit reset gates, Runtime `init_qubits=true`, "
        "transpile seed `20260903`, and 20,000 circuit-shots per kernel.",
        "",
        f"Independent audit: **{audit['status']} ({audit['passed']}/{audit['total']})**.",
        "",
        "## Accepted results",
        "",
        "| kernel | balanced accuracy | train/test rel. Frobenius error | circuit-shots | map executions | 2Q-gate-shots | QPU seconds |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| fidelity | {fidelity['classification']['test_balanced_accuracy']:.3f} | "
            f"{fidelity['kernel_error']['train_relative_frobenius']:.4f} / "
            f"{fidelity['kernel_error']['test_relative_frobenius']:.4f} | "
            f"{f_axes['circuit_shots']} | {f_axes['map_executions']} | "
            f"{f_axes['two_qubit_gate_shots']} | {f_axes['qpu_time_seconds']:.3f} |"
        ),
        (
            f"| projected | {projected['classification']['test_balanced_accuracy']:.3f} | "
            f"{projected['kernel_error']['train_relative_frobenius']:.4f} / "
            f"{projected['kernel_error']['test_relative_frobenius']:.4f} | "
            f"{p_axes['circuit_shots']} | {p_axes['map_executions']} | "
            f"{p_axes['two_qubit_gate_shots']} | {p_axes['qpu_time_seconds']:.3f} |"
        ),
        "",
        (
            "Fidelity raw diagonal: min/mean/max = "
            f"{fidelity['raw_diagonal']['minimum']:.4f} / "
            f"{fidelity['raw_diagonal']['mean']:.4f} / "
            f"{fidelity['raw_diagonal']['maximum']:.4f}."
        ),
        "",
        "## Interpretation",
        "",
        "The test set contains only four balanced samples. The observed 1.0 versus 0.5 "
        "balanced accuracy must not be reported as evidence that projected kernels are "
        "superior. The defensible result is successful hardware validation, physically "
        "consistent fidelity diagonals, and complete resource accounting.",
        "",
        "Earlier QPU attempts are retained but rejected from scientific comparison. "
        "Their diagnostic cost is reported separately in `summary.json`.",
        "",
    ]
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"summary": str(summary_json), "audit": audit["status"]}, indent=2))


if __name__ == "__main__":
    main()
