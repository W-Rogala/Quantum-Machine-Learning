"""Post-selection v3 summary and descriptive compatibility sets."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from .trotter_scaling_v3 import _write_csv, _write_json, load_protocol


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _condition_seed(condition_id: str) -> int:
    return int(condition_id.rsplit("_s", 1)[1])


def compatible_set(rows: list[dict[str, str]], bootstrap_resamples: int = 2000, seed: int = 20261005) -> list[dict[str, Any]]:
    """Paired split-cluster bootstrap; descriptive after empirical-best selection."""
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["condition_id"], row["cell_id"])].append(row)
    output: list[dict[str, Any]] = []
    for (condition_id, cell_id), group in grouped.items():
        scores: dict[tuple[int, float], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for row in group:
            key = (int(row["order"]), float(row["delta_t"]))
            scores[key][row["split_id"]].append(float(row["inner_ba"]))
        split_ids = sorted(set.intersection(*(set(by_split) for by_split in scores.values())))
        if not split_ids:
            continue
        means_by_key = {
            key: np.asarray([np.mean(by_split[split_id]) for split_id in split_ids], dtype=float)
            for key, by_split in scores.items()
        }
        best = max(means_by_key, key=lambda key: (float(np.mean(means_by_key[key])), -key[0], key[1]))
        rng = np.random.default_rng(seed + _condition_seed(condition_id) + len(cell_id))
        draws = rng.integers(0, len(split_ids), size=(bootstrap_resamples, len(split_ids)))
        comparison_count = max(len(means_by_key) - 1, 1)
        for key, per_split in means_by_key.items():
            difference = means_by_key[best] - per_split
            boot = np.mean(difference[draws], axis=1)
            # Bonferroni lower bound; small split count makes this descriptive.
            lower = float(np.quantile(boot, 0.025 / comparison_count))
            upper = float(np.quantile(boot, 1 - 0.025 / comparison_count))
            output.append({
                "condition_id": condition_id, "cell_id": cell_id,
                "order": key[0], "delta_t": f"{key[1]:.2f}",
                "mean_inner_ba": float(np.mean(per_split)),
                "empirical_best_order": best[0],
                "empirical_best_delta_t": f"{best[1]:.2f}",
                "mean_ba_deficit_to_best": float(np.mean(difference)),
                "simultaneous_bootstrap_lower_deficit": lower,
                "simultaneous_bootstrap_upper_deficit": upper,
                "compatible_with_best": lower <= 0.0,
                "split_clusters": len(split_ids),
                "interpretation": "descriptive_post_selection_not_confirmatory_test",
            })
    return output


def _seed_cluster_interval(rows: list[dict[str, str]], field: str, baseline: str, seed: int, resamples: int = 2000) -> dict[str, float]:
    by_seed_split: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_seed_split[_condition_seed(row["condition_id"])][row["split_id"]].append(
            float(row[baseline]) - float(row[field])
        )
    if not by_seed_split:
        return {"mean": float("nan"), "lower_95": float("nan"), "upper_95": float("nan"), "seed_clusters": 0}
    per_seed = [
        np.asarray([np.mean(values) for _, values in sorted(splits.items())], dtype=float)
        for _, splits in sorted(by_seed_split.items())
    ]
    seed_values = np.asarray([np.mean(values) for values in per_seed])
    rng = np.random.default_rng(seed)
    seed_draws = rng.integers(0, len(per_seed), size=(resamples, len(per_seed)))
    means = np.empty(resamples, dtype=float)
    for index, drawn_seeds in enumerate(seed_draws):
        means[index] = np.mean([
            float(np.mean(per_seed[seed_index][rng.integers(0, len(per_seed[seed_index]), size=len(per_seed[seed_index]))]))
            for seed_index in drawn_seeds
        ])
    return {
        "mean": float(np.mean(seed_values)),
        "lower_95": float(np.quantile(means, 0.025)),
        "upper_95": float(np.quantile(means, 0.975)),
        "seed_clusters": len(seed_values),
    }


def hypothesis_intervals(rows: list[dict[str, str]], protocol: Any, resamples: int = 10000) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fourteen preregistered OLS contrasts, clustered by Hamiltonian seed."""
    blocks: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        blocks[(row["condition_id"], row["split_id"], row["replicate"])].append(row)
    complete_rows = [row for block in blocks.values() if len({item["cell_id"] for item in block}) == 8 for row in block]
    by_seed: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in complete_rows:
        by_seed[_condition_seed(row["condition_id"])].append(row)
    status = {
        "complete_factorial_blocks": len(complete_rows) // 8,
        "excluded_incomplete_blocks": len(blocks) - len(complete_rows) // 8,
        "seed_clusters": len(by_seed),
    }
    if len(by_seed) < 20:
        return [], {**status, "status": "insufficient_seed_clusters_not_confirmatory"}
    effects = ("n", "depth", "circuit_shots", "two_qubit_gate_shots", "n_x_depth", "n_x_circuit_shots", "n_x_two_qubit_gate_shots")
    seed_coefficients: dict[str, list[np.ndarray]] = {"log_delta_t": [], "log2_order": []}
    for seed, seed_rows in sorted(by_seed.items()):
        design = []
        outcomes = {"log_delta_t": [], "log2_order": []}
        for row in seed_rows:
            condition = row["condition_id"]
            n = int(condition.split("_", 1)[0][1:]) - 4
            depth = float(int(row["depth"]) == max(protocol.depth_budgets)) - 0.5
            shots = float(int(row["circuit_shots"]) == max(protocol.shot_budgets)) - 0.5
            two_qubit = float(int(row["two_qubit_gate_shots"]) == max(protocol.two_qubit_gate_shot_budgets)) - 0.5
            family = next(profile for profile in protocol.hamiltonian_profiles if f"_{profile}_s" in condition)
            topology = condition.split("_", 1)[1].split(f"_{family}_s", 1)[0]
            fixed_family = [float(family == item) for item in protocol.hamiltonian_profiles[1:]]
            fixed_topology = [float(topology == item) for item in protocol.topologies[1:]]
            design.append([1.0, n, depth, shots, two_qubit, n * depth, n * shots, n * two_qubit, *fixed_family, *fixed_topology])
            outcomes["log_delta_t"].append(np.log(float(row["selected_delta_t"])))
            outcomes["log2_order"].append(np.log2(float(row["selected_order"])))
        matrix = np.asarray(design, dtype=float)
        if np.linalg.matrix_rank(matrix[:, :8]) < 8:
            return [], {**status, "status": f"design_rank_deficient_seed_{seed}_not_confirmatory"}
        for outcome, values in outcomes.items():
            coefficients = np.linalg.lstsq(matrix, np.asarray(values), rcond=None)[0]
            seed_coefficients[outcome].append(coefficients[1:8])
    rng = np.random.default_rng(20261010)
    n_seeds = len(by_seed)
    draws = rng.integers(0, n_seeds, size=(resamples, n_seeds))
    alpha = 0.05 / 14
    inference: list[dict[str, Any]] = []
    for outcome, values in seed_coefficients.items():
        matrix = np.asarray(values, dtype=float)
        bootstrap_means = matrix[draws].mean(axis=1)
        for index, effect in enumerate(effects):
            low, high = np.quantile(bootstrap_means[:, index], [alpha / 2, 1 - alpha / 2])
            inference.append({
                "outcome": outcome, "effect": effect,
                "coefficient": float(np.mean(matrix[:, index])),
                "familywise_95_lower": float(low),
                "familywise_95_upper": float(high),
                "excludes_zero": bool(low > 0 or high < 0),
                "seed_clusters": n_seeds,
                "bootstrap_resamples": resamples,
                "multiplicity": "Bonferroni_14_endpoints",
            })
    return inference, {**status, "status": "computed"}


def analyze(protocol_path: Path, output_dir: Path) -> dict[str, Any]:
    protocol, payload = load_protocol(protocol_path)
    progress = json.loads((output_dir / "progress.json").read_text(encoding="utf-8"))
    if progress.get("protocol_hash") != payload["protocol_hash"]:
        raise ValueError("result/protocol hash mismatch")
    outer_rows: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []
    for condition in progress["conditions"]:
        condition_id = condition["condition_id"]
        outer_rows.extend(_read_csv(output_dir / "conditions" / f"{condition_id}_outer.csv"))
        candidate_rows.extend(_read_csv(output_dir / "conditions" / f"{condition_id}_candidates.csv"))
    compatibility = compatible_set(candidate_rows)
    _write_csv(output_dir / "compatible_policies.csv", compatibility)
    cells: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in outer_rows:
        cells[row["cell_id"]].append(row)
    cell_summary = []
    for cell_id, rows in sorted(cells.items()):
        finite_gap = _seed_cluster_interval(rows, "trotter_finite_ba", "exact_finite_equal_per_circuit_ba", 20261006)
        total_gap = _seed_cluster_interval(rows, "trotter_finite_ba", "exact_finite_equal_total_circuit_shots_ba", 20261007)
        noiseless_gap = _seed_cluster_interval(rows, "trotter_noiseless_ba", "exact_noiseless_ba", 20261008)
        cell_summary.append({
            "cell_id": cell_id,
            "depth_budget": int(rows[0]["depth"]),
            "circuit_shot_budget": int(rows[0]["circuit_shots"]),
            "two_qubit_gate_shot_budget": int(rows[0]["two_qubit_gate_shots"]),
            "mean_actual_circuit_shots": float(np.mean([float(x["circuit_shots_used"]) for x in rows])),
            "mean_actual_two_qubit_gate_shots": float(np.mean([float(x["two_qubit_gate_shots_used"]) for x in rows])),
            "mean_actual_full_circuit_depth": float(np.mean([float(x["selected_full_circuit_depth"]) for x in rows])),
            "mean_trotter_finite_ba": float(np.mean([float(x["trotter_finite_ba"]) for x in rows])),
            "mean_exact_finite_equal_per_circuit_ba": float(np.mean([float(x["exact_finite_equal_per_circuit_ba"]) for x in rows])),
            "mean_trotter_noiseless_ba": float(np.mean([float(x["trotter_noiseless_ba"]) for x in rows])),
            "mean_exact_noiseless_ba": float(np.mean([float(x["exact_noiseless_ba"]) for x in rows])),
            "finite_per_circuit_gap": finite_gap["mean"],
            "finite_gap_cluster_ci_low": finite_gap["lower_95"],
            "finite_gap_cluster_ci_high": finite_gap["upper_95"],
            "finite_equal_total_gap": total_gap["mean"],
            "noiseless_gap": noiseless_gap["mean"],
            "noiseless_gap_cluster_ci_low": noiseless_gap["lower_95"],
            "noiseless_gap_cluster_ci_high": noiseless_gap["upper_95"],
            "seed_clusters": finite_gap["seed_clusters"],
            "outer_rows": len(rows),
        })
    _write_csv(output_dir / "resource_factorial_summary.csv", cell_summary)
    complete = progress["status"] == "complete"
    holdout_complete = (output_dir / "holdout_progress.json").exists()
    inference, inference_status = hypothesis_intervals(outer_rows, protocol) if complete and holdout_complete and protocol.profile == "full" else ([], {"status": "requires_complete_full_development_and_holdout"})
    _write_csv(output_dir / "preregistered_inference.csv", inference)
    summary = {
        "schema": "trotter-scaling.summary.v3",
        "protocol_hash": payload["protocol_hash"],
        "development_complete": complete,
        "holdout_complete": holdout_complete,
        "confirmatory_status": "inference_computed" if inference_status["status"] == "computed" else "not_confirmatory",
        "inference_status": inference_status,
        "v2_p_value_status": "exploratory_not_confirmation",
        "conditions_completed": progress["completed_conditions"],
        "conditions_expected": progress["expected_conditions"],
        "outer_rows": len(outer_rows),
        "candidate_rows": len(candidate_rows),
        "compatible_rows": len(compatibility),
        "resource_cells": len(cell_summary),
        "limitations": [
            "0.01 grid is resource-screened before inner CV, not exhaustively numerically evaluated",
            "Exact evolution is a simulator oracle, not an ISA-equivalent QPU circuit",
            "Shot-matched comparisons isolate measurement noise but do not equalize exact-oracle gate cost",
            "Split-level compatible sets are descriptive post-selection with only six outer split clusters",
        ],
    }
    _write_json(output_dir / "v3_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.output_dir / "protocol.json", args.output_dir)))


if __name__ == "__main__":
    main()
