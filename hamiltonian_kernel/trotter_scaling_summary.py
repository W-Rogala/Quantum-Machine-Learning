from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _mean(rows: list[dict[str, str]], field: str) -> float:
    return float(np.mean([float(row[field]) for row in rows]))


def _median(rows: list[dict[str, str]], field: str) -> float:
    return float(np.median([float(row[field]) for row in rows]))


def _aggregate(rows: list[dict[str, str]]) -> dict[str, int | float]:
    orders = np.asarray([int(row["order"]) for row in rows], dtype=int)
    return {
        "rows": len(rows),
        "order_mean": float(np.mean(orders)),
        "order_1_share": float(np.mean(orders == 1)),
        "order_2_share": float(np.mean(orders == 2)),
        "order_4_share": float(np.mean(orders == 4)),
        "delta_t_mean": _mean(rows, "delta_t"),
        "delta_t_median": _median(rows, "delta_t"),
        "transpiled_depth_mean": _mean(rows, "transpiled_depth"),
        "shots_per_circuit_median": _median(rows, "shots_per_circuit"),
        "outer_test_ba_mean": _mean(rows, "outer_test_balanced_accuracy"),
        "exact_outer_test_ba_mean": _mean(
            rows, "exact_outer_test_balanced_accuracy"
        ),
        "trotter_minus_exact_ba_mean": _mean(
            [
                {
                    "difference": str(
                        float(row["outer_test_balanced_accuracy"])
                        - float(row["exact_outer_test_balanced_accuracy"])
                    )
                }
                for row in rows
            ],
            "difference",
        ),
        "mean_state_infidelity": _mean(rows, "mean_state_infidelity"),
        "kernel_relative_frobenius_error": _mean(
            rows, "kernel_relative_frobenius_error"
        ),
        "circuit_budget_utilization_mean": float(
            np.mean(
                [
                    int(row["circuit_shots_used"])
                    / int(row["circuit_shot_budget"])
                    for row in rows
                ]
            )
        ),
        "two_qubit_budget_utilization_mean": float(
            np.mean(
                [
                    int(row["two_qubit_gate_shots_used"])
                    / int(row["two_qubit_gate_shot_budget"])
                    for row in rows
                ]
            )
        ),
    }


def _group(
    rows: list[dict[str, str]], fields: tuple[str, ...]
) -> dict[tuple[str, ...], list[dict[str, str]]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)
    return groups


def _write_group_table(
    path: Path,
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
    order_maps: tuple[dict[str, int], ...],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key, members in sorted(
        _group(rows, fields).items(),
        key=lambda item: tuple(
            order_maps[index].get(value, int(value) if value.isdigit() else 10_000)
            for index, value in enumerate(item[0])
        ),
    ):
        result.append({**dict(zip(fields, key, strict=True)), **_aggregate(members)})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result[0]))
        writer.writeheader()
        writer.writerows(result)
    return result


def _replicate_agreement(rows: list[dict[str, str]]) -> dict[str, float | int] | None:
    groups = _group(
        rows,
        (
            "n_qubits",
            "topology",
            "hamiltonian_seed",
            "hamiltonian_profile",
            "outer_repeat",
            "outer_fold",
            "budget_tier",
        ),
    )
    exact_comparisons: list[bool] = []
    order_comparisons: list[bool] = []
    delta_differences: list[float] = []
    for members in groups.values():
        by_replicate = {int(row["shot_replicate"]): row for row in members}
        if 0 in by_replicate and 1 in by_replicate:
            left, right = by_replicate[0], by_replicate[1]
            exact_comparisons.append(
                left["order"] == right["order"]
                and left["delta_t"] == right["delta_t"]
            )
            order_comparisons.append(left["order"] == right["order"])
            delta_differences.append(
                abs(float(left["delta_t"]) - float(right["delta_t"]))
            )
    if not exact_comparisons:
        return None
    delta = np.asarray(delta_differences, dtype=float)
    return {
        "comparisons": len(exact_comparisons),
        "exact_policy_agreement": float(np.mean(exact_comparisons)),
        "order_agreement": float(np.mean(order_comparisons)),
        "delta_t_absolute_difference_mean": float(np.mean(delta)),
        "delta_t_absolute_difference_median": float(np.median(delta)),
        "delta_t_within_0_05_share": float(np.mean(delta <= 0.05 + 1e-12)),
        "delta_t_within_0_10_share": float(np.mean(delta <= 0.10 + 1e-12)),
    }


def summarize(output_dir: Path) -> dict[str, Any]:
    from .trotter_scaling_full import analyze_hypothesis, load_protocol

    protocol_payload = json.loads((output_dir / "protocol.json").read_text("utf-8"))
    protocol = protocol_payload["protocol"]
    completion = json.loads((output_dir / "completion.json").read_text("utf-8"))
    analysis = json.loads(
        (output_dir / "hypothesis_analysis.json").read_text("utf-8")
    )
    audit = json.loads((output_dir / "independent_audit.json").read_text("utf-8"))
    rows = _read_csv(output_dir / "outer_results.csv")
    budget_order = {
        tier["name"]: index for index, tier in enumerate(protocol["budget_tiers"])
    }
    n_order = {str(value): index for index, value in enumerate(protocol["qubit_counts"])}
    profile_order = {
        value: index for index, value in enumerate(protocol["hamiltonian_profiles"])
    }
    by_n_budget = _write_group_table(
        output_dir / "aggregate_by_n_budget.csv",
        rows,
        ("n_qubits", "budget_tier"),
        (n_order, budget_order),
    )
    by_profile_budget = _write_group_table(
        output_dir / "aggregate_by_profile_budget.csv",
        rows,
        ("hamiltonian_profile", "budget_tier"),
        (profile_order, budget_order),
    )
    budget_groups = _group(rows, ("budget_tier",))
    by_budget = {
        budget: _aggregate(budget_groups[(budget,)]) for budget in budget_order
    }
    replicate_stability = _replicate_agreement(rows)
    sensitivity: dict[str, Any] | None = None
    if int(protocol["shot_replicates"]) > 1:
        protocol_object, _ = load_protocol(output_dir / "protocol.json")
        sensitivity = analyze_hypothesis(
            rows, protocol_object, shot_replicate=1
        )
        sensitivity["analysis_role"] = "post_hoc_shot_replicate_sensitivity"
        (output_dir / "hypothesis_sensitivity_shot_replicate_1.json").write_text(
            json.dumps(sensitivity, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    package_dir = Path(__file__).resolve().parent
    project_dir = package_dir.parent
    source_paths = (
        package_dir / "trotter_scaling_full.py",
        package_dir / "universal_hamiltonian.py",
        package_dir / "estimation.py",
        package_dir / "learning.py",
        package_dir / "trotter_scaling.py",
        package_dir / "trotter_scaling_summary.py",
        project_dir / "audits" / "trotter_scaling_full_audit.py",
    )
    implementation_manifest: dict[str, Any] = {
        "schema": "trotter-scaling-full.implementation-manifest.v2",
        "protocol_hash": protocol_payload["protocol_hash"],
        "completion_result_hash": completion["result_hash"],
        "source_sha256": {
            path.relative_to(project_dir).as_posix(): _file_hash(path)
            for path in source_paths
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": _package_version("numpy"),
            "scipy": _package_version("scipy"),
            "scikit_learn": _package_version("scikit-learn"),
            "qiskit": _package_version("qiskit"),
        },
        "capture_note": (
            "Captured after the verified rerun that reused hash-validated numerical shards."
        ),
    }
    implementation_manifest["manifest_hash"] = hashlib.sha256(
        _canonical_json(implementation_manifest).encode("utf-8")
    ).hexdigest()
    (output_dir / "implementation_manifest.json").write_text(
        json.dumps(implementation_manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    summary: dict[str, Any] = {
        "schema": "trotter-scaling-full.scientific-summary.v2",
        "protocol_hash": protocol_payload["protocol_hash"],
        "audit_status": audit["status"],
        "conditions": completion["condition_count"],
        "grid_rows": completion["grid_rows"],
        "outer_rows": completion["outer_rows"],
        "primary_permutation_p_value": analysis["permutation_p_value"],
        "primary_statistic": analysis["primary_statistic"],
        "hypothesis_supported": analysis["hypothesis_supported"],
        "primary_effects": {
            response: {
                term: analysis["coefficient_intervals"][response][term]
                for term in analysis["primary_terms"]
            }
            for response in analysis["multivariate_response"]
        },
        "by_budget": by_budget,
        "shot_replicate_stability": replicate_stability,
        "shot_replicate_1_sensitivity": (
            {
                "artifact": "hypothesis_sensitivity_shot_replicate_1.json",
                "permutation_p_value": sensitivity["permutation_p_value"],
                "primary_statistic": sensitivity["primary_statistic"],
                "hypothesis_supported": sensitivity["hypothesis_supported"],
                "primary_effects": {
                    response: {
                        term: sensitivity["coefficient_intervals"][response][term]
                        for term in sensitivity["primary_terms"]
                    }
                    for response in sensitivity["multivariate_response"]
                },
            }
            if sensitivity is not None
            else None
        ),
        "total_simulated_resources": {
            "circuit_shots": sum(int(row["circuit_shots_used"]) for row in rows),
            "map_executions": sum(int(row["map_executions_used"]) for row in rows),
            "two_qubit_gate_shots": sum(
                int(row["two_qubit_gate_shots_used"]) for row in rows
            ),
            "qpu_time_or_credits": None,
        },
        "aggregate_tables": {
            "by_n_budget": "aggregate_by_n_budget.csv",
            "by_profile_budget": "aggregate_by_profile_budget.csv",
        },
        "implementation_manifest": "implementation_manifest.json",
        "interpretation_guardrails": [
            "The test concerns a resource-conditioned selected policy, not a causal depth effect.",
            "Depth, circuit-shot and 2Q-gate-shot budgets vary together in three tiers and are not separately identifiable.",
            "The benchmark uses synthetic perfectly annotated data and ideal state evolution with finite-shot kernel sampling.",
            "Transpilation targets frozen synthetic coupling maps, not calibration-aware physical IBM backends.",
        ],
    }
    summary["summary_hash"] = hashlib.sha256(
        _canonical_json(summary).encode("utf-8")
    ).hexdigest()
    (output_dir / "scientific_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    delta_effect = summary["primary_effects"]["log_delta_t"]
    order_effect = summary["primary_effects"]["trotter_order"]
    lines = [
        "# Scientific summary of the preregistered Trotter-scaling experiment",
        "",
        f"- Independent audit: `{audit['status']}` ({audit['checks_passed']}/{audit['checks_total']}).",
        f"- Protocol hash: `{protocol_payload['protocol_hash']}`.",
        f"- Conditions/grid/outer rows: `{completion['condition_count']}` / `{completion['grid_rows']}` / `{completion['outer_rows']}`.",
        f"- Joint Freedman-Lane test: `p={analysis['permutation_p_value']:.6g}` with `{analysis['permutation_resamples']}` permutations.",
        f"- Exact shot-replicate policy agreement: `{replicate_stability['exact_policy_agreement']:.3f}`.",
        f"- Shot-replicate order agreement: `{replicate_stability['order_agreement']:.3f}`; median |delta_t difference|: `{replicate_stability['delta_t_absolute_difference_median']:.3f}`.",
        "",
        "## Primary effects",
        "",
        "Coefficients are expressed in standard-deviation units after adjustment for Hamiltonian profile, topology, commutator norm, spectral radius and outer split.",
        "",
        f"- Larger depth/resource tier selects a finer step: log(delta_t) coefficient `{delta_effect['log_depth_budget']['estimate']:.3f}`, 95% cluster CI `{delta_effect['log_depth_budget']['ci95']}`.",
        f"- Larger depth/resource tier selects a higher order: coefficient `{order_effect['log_depth_budget']['estimate']:.3f}`, 95% cluster CI `{order_effect['log_depth_budget']['ci95']}`.",
        f"- More qubits select a slightly coarser step: coefficient `{delta_effect['n_qubits']['estimate']:.3f}`, 95% cluster CI `{delta_effect['n_qubits']['ci95']}`.",
        f"- More qubits select a slightly lower order: coefficient `{order_effect['n_qubits']['estimate']:.3f}`, 95% cluster CI `{order_effect['n_qubits']['ci95']}`.",
        f"- The n-by-depth interaction CIs include zero for both responses: `{delta_effect['n_qubits_x_log_depth_budget']['ci95']}` and `{order_effect['n_qubits_x_log_depth_budget']['ci95']}`.",
        "",
        "## Budget-level descriptive results",
        "",
        "| tier | mean order | mean delta_t | order-4 share | BA | exact BA | infidelity | kernel error |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for budget in budget_order:
        values = by_budget[budget]
        lines.append(
            f"| {budget} | {values['order_mean']:.3f} | {values['delta_t_mean']:.3f} | "
            f"{values['order_4_share']:.3f} | {values['outer_test_ba_mean']:.3f} | "
            f"{values['exact_outer_test_ba_mean']:.3f} | {values['mean_state_infidelity']:.4f} | "
            f"{values['kernel_relative_frobenius_error']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "The joint null is rejected, supporting dependence of the selected policy on qubit count and the bundled resource tier. The interaction itself is not resolved. This is not evidence that physical circuit depth alone causes the policy change, because the three resource budgets co-vary and the selected policy determines realized depth.",
            "",
            f"Exact policy agreement between the two finite-shot replicates is only `{replicate_stability['exact_policy_agreement']:.3f}`. Order agreement is `{replicate_stability['order_agreement']:.3f}`, and only `{replicate_stability['delta_t_within_0_10_share']:.3f}` of paired selections differ in delta_t by at most 0.10. The primary significance result must therefore be interpreted together with the post-hoc replicate-1 sensitivity, not as evidence of a sharply identified unique optimum.",
            "",
            "The experiment is a simulator benchmark with synthetic, noiseless labels. Finite shots are applied to fidelity-kernel entries, while device noise, calibration drift, queue time and QPU credits are outside this result. A calibration-aware QPU replication is therefore a validation stage, not part of the present hypothesis test.",
        ]
    )
    (output_dir / "results_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize full Trotter scaling outputs")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
