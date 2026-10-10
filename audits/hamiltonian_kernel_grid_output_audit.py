from __future__ import annotations

import argparse
import ast
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def expected_candidates(profile: str) -> set[tuple[float, float, float, str]]:
    if profile == "smoke":
        times = (0.6, 1.0)
        interactions = (0.0, 0.6)
        fields = (0.4, 0.8)
        topologies = ("chain", "ring")
    elif profile == "full":
        times = (0.5, 1.0, 1.5)
        interactions = (0.0, 0.4, 0.8)
        fields = (0.3, 0.7, 1.1)
        topologies = ("chain", "ring", "all_to_all")
    else:
        raise ValueError(f"Unsupported profile: {profile}")

    return {
        (time, interaction, field, topology)
        for time in times
        for interaction in interactions
        for field in fields
        for topology in (("chain",) if interaction == 0.0 else topologies)
    }


def unique_count(rows: list[dict[str, str]], fields: tuple[str, ...]) -> int:
    return len({tuple(row[field] for field in fields) for row in rows})


def run_audit(output_dir: Path) -> tuple[list[Check], dict[str, object]]:
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    arguments = summary["arguments"]
    datasets = [str(value) for value in arguments["datasets"]]
    seeds = [int(value) for value in arguments["seeds"]]
    budgets = [int(value) for value in arguments["budgets"]]
    noise_replicates = int(arguments["noise_replicates"])
    top_k = int(arguments["top_k"])
    profile = str(arguments["profile"])

    screening = load_csv(output_dir / "grid_screening.csv")
    finalists = load_csv(output_dir / "validation_finalists.csv")
    ideal = load_csv(output_dir / "selected_ideal_runs.csv")
    budget_rows = load_csv(output_dir / "equal_budget_runs.csv")

    checks: list[Check] = []

    def record(name: str, condition: bool, detail: str) -> None:
        checks.append(Check(name, bool(condition), detail))

    expected_grid = expected_candidates(profile)
    observed_grid = {
        (
            float(candidate["evolution_time"]),
            float(candidate["interaction_strength"]),
            float(candidate["transverse_field"]),
            str(candidate["topology"]),
        )
        for candidate in summary["candidates"]
    }
    record(
        "independent_grid_reconstruction",
        observed_grid == expected_grid,
        f"observed={len(observed_grid)}, expected={len(expected_grid)}",
    )

    expected_screening = len(datasets) * len(seeds) * len(expected_grid) * 2
    screening_keys = ("dataset", "seed", "kernel", "candidate")
    record(
        "screening_complete_and_unique",
        len(screening) == expected_screening
        and unique_count(screening, screening_keys) == expected_screening,
        f"rows={len(screening)}, expected={expected_screening}",
    )

    finalist_count = min(top_k, len(expected_grid))
    expected_finalists = len(datasets) * len(seeds) * finalist_count * 2
    finalist_keys = ("dataset", "seed", "kernel", "candidate")
    record(
        "validation_finalists_complete_and_unique",
        len(finalists) == expected_finalists
        and unique_count(finalists, finalist_keys) == expected_finalists,
        f"rows={len(finalists)}, expected={expected_finalists}",
    )

    forbidden_columns = {
        column
        for rows in (screening, finalists)
        for column in (rows[0].keys() if rows else ())
        if column.startswith("test_") or column in {"x_test", "y_test"}
    }
    record(
        "selection_artifacts_exclude_test_fields",
        not forbidden_columns,
        f"forbidden_columns={sorted(forbidden_columns)}",
    )

    expected_ideal = len(datasets) * len(seeds) * 3
    ideal_keys = ("dataset", "seed", "kernel")
    record(
        "single_final_test_evaluation_per_model",
        len(ideal) == expected_ideal and unique_count(ideal, ideal_keys) == expected_ideal,
        f"rows={len(ideal)}, expected={expected_ideal}",
    )
    validation_errors = [
        abs(
            float(row["selected_validation_balanced_accuracy"])
            - float(row["recomputed_validation_balanced_accuracy"])
        )
        for row in ideal
        if row["kernel"] in {"fidelity", "projected"}
    ]
    max_validation_error = max(validation_errors, default=math.inf)
    record(
        "selected_validation_score_reproduced",
        max_validation_error <= 1e-12,
        f"max_abs_error={max_validation_error:.3e}",
    )

    expected_budget_rows = (
        len(datasets) * len(seeds) * len(budgets) * noise_replicates * 2
    )
    budget_keys = (
        "dataset",
        "seed",
        "noise_replicate",
        "total_measurement_budget",
        "kernel",
    )
    record(
        "budget_rows_complete_and_unique",
        len(budget_rows) == expected_budget_rows
        and unique_count(budget_rows, budget_keys) == expected_budget_rows,
        f"rows={len(budget_rows)}, expected={expected_budget_rows}",
    )

    paired_cells: dict[tuple[str, int, int, int], set[str]] = {}
    budget_formula_ok = True
    psd_ok = True
    full_train_fidelity_ok = True
    projected_circuit_counts: dict[tuple[str, int, int, int], int] = {}
    for row in budget_rows:
        dataset = str(row["dataset"])
        seed = int(row["seed"])
        replicate = int(row["noise_replicate"])
        budget = int(row["total_measurement_budget"])
        kernel = str(row["kernel"])
        cell = (dataset, seed, replicate, budget)
        paired_cells.setdefault(cell, set()).add(kernel)

        circuit_count = int(row["circuit_count"])
        minimum = int(row["shots_per_circuit_min"])
        maximum = int(row["shots_per_circuit_max"])
        expected_minimum = budget // circuit_count
        expected_maximum = math.ceil(budget / circuit_count)
        expected_maps = budget * (2 if kernel == "fidelity" else 1)
        budget_formula_ok &= (
            int(row["total_budget"]) == budget
            and minimum == expected_minimum
            and maximum == expected_maximum
            and int(row["map_executions"]) == expected_maps
        )
        psd_ok &= (
            float(row["kernel_min_eigenvalue"]) >= -1e-10
            and float(row["kernel_negative_eigenmass"]) <= 1e-9
        )
        if kernel == "projected":
            projected_circuit_counts[cell] = circuit_count

    record(
        "fidelity_projected_pairs_complete",
        all(kernels == {"fidelity", "projected"} for kernels in paired_cells.values()),
        f"paired_cells={len(paired_cells)}",
    )
    record(
        "exact_common_budget_accounting",
        budget_formula_ok,
        "min/max shots and map executions match independent integer formulas",
    )
    record(
        "training_kernels_psd_within_tolerance",
        psd_ok,
        "required min_eigenvalue >= -1e-10 and negative_eigenmass <= 1e-9",
    )

    if int(arguments["landmarks"]) == 0:
        for row in budget_rows:
            if row["kernel"] != "fidelity":
                continue
            cell = (
                str(row["dataset"]),
                int(row["seed"]),
                int(row["noise_replicate"]),
                int(row["total_measurement_budget"]),
            )
            total_samples = projected_circuit_counts[cell] // 3
            train_count = int(row["landmark_count"])
            expected_circuits = (
                train_count * (train_count - 1) // 2
                + (total_samples - train_count) * train_count
            )
            full_train_fidelity_ok &= (
                row["estimator"] == "normalized_full_train_spectral_fidelity"
                and int(row["circuit_count"]) == expected_circuits
            )
        record(
            "full_train_spectral_fidelity_formula",
            full_train_fidelity_ok,
            "fidelity circuits = train upper triangle + all non-train/train overlaps",
        )

    source = (ROOT / "hamiltonian_kernel" / "grid_experiment.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    selection_function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "screen_and_select_candidates"
    )
    selection_arguments = {argument.arg for argument in selection_function.args.args}
    selection_names = {
        node.id for node in ast.walk(selection_function) if isinstance(node, ast.Name)
    }
    forbidden_names = {"x_test", "y_test", "test_data", "test_labels"}
    record(
        "static_selection_boundary",
        not (selection_arguments | selection_names) & forbidden_names,
        f"forbidden_names_found={sorted((selection_arguments | selection_names) & forbidden_names)}",
    )

    required_artifacts = (
        "report.md",
        "summary.json",
        "equal_budget_performance.png",
        "selection_frequency.png",
    )
    missing = [name for name in required_artifacts if not (output_dir / name).is_file()]
    empty = [name for name in required_artifacts if (output_dir / name).is_file() and not (output_dir / name).stat().st_size]
    record(
        "required_artifacts_present",
        not missing and not empty,
        f"missing={missing}, empty={empty}",
    )

    metadata = {
        "profile": profile,
        "datasets": datasets,
        "seeds": seeds,
        "budgets": budgets,
        "noise_replicates": noise_replicates,
        "candidate_count": len(expected_grid),
        "screening_rows": len(screening),
        "ideal_rows": len(ideal),
        "budget_rows": len(budget_rows),
    }
    return checks, metadata


def write_results(output_dir: Path, checks: list[Check], metadata: dict[str, object]) -> None:
    passed = sum(check.passed for check in checks)
    status = "PASS" if passed == len(checks) else "FAIL"
    payload = {
        "status": status,
        "passed": passed,
        "total": len(checks),
        "metadata": metadata,
        "checks": [asdict(check) for check in checks],
    }
    (output_dir / "independent_audit.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Niezależny audyt artefaktów eksperymentu siatkowego",
        "",
        f"Status: **{status}** ({passed}/{len(checks)})",
        "",
        "| kontrola | wynik | szczegóły |",
        "|---|---|---|",
    ]
    for check in checks:
        result = "PASS" if check.passed else "FAIL"
        detail = check.detail.replace("|", "\\|")
        lines.append(f"| {check.name} | {result} | {detail} |")
    (output_dir / "independent_audit.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently audit Hamiltonian-grid output artifacts")
    parser.add_argument("output_dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    checks, metadata = run_audit(output_dir)
    write_results(output_dir, checks, metadata)
    failed = [check for check in checks if not check.passed]
    print(
        json.dumps(
            {
                "status": "PASS" if not failed else "FAIL",
                "passed": len(checks) - len(failed),
                "total": len(checks),
                "failed": [check.name for check in failed],
            },
            indent=2,
        )
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
