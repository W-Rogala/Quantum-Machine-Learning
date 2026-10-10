from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metric(rows: list[dict[str, Any]], name: str, fallback: float = 1.0) -> float:
    for row in rows:
        if row.get("name") == name and row.get("value") is not None:
            return float(row["value"])
    return fallback


def simple_paths(adjacency: dict[int, set[int]], length: int) -> list[tuple[int, ...]]:
    paths: set[tuple[int, ...]] = set()

    def visit(path: tuple[int, ...]) -> None:
        if len(path) == length:
            paths.add(min(path, tuple(reversed(path))))
            return
        for neighbor in sorted(adjacency[path[-1]]):
            if neighbor not in path:
                visit(path + (neighbor,))

    for start in sorted(adjacency):
        visit((start,))
    return sorted(paths)


def rank_layouts(
    snapshot: dict[str, Any],
    length: int,
    two_qubit_weight: float,
) -> list[dict[str, Any]]:
    properties = snapshot["properties"]
    qubit_metrics = {
        index: {
            "readout_error": metric(rows, "readout_error"),
            "init_error": metric(rows, "init_error"),
        }
        for index, rows in enumerate(properties["qubits"])
    }
    adjacency: dict[int, set[int]] = defaultdict(set)
    edge_error: dict[tuple[int, int], float] = {}
    for gate in properties["gates"]:
        if gate.get("gate") != "cz":
            continue
        left, right = (int(value) for value in gate["qubits"])
        edge = tuple(sorted((left, right)))
        error = metric(gate["parameters"], "gate_error")
        edge_error[edge] = min(error, edge_error.get(edge, 1.0))
        adjacency[left].add(right)
        adjacency[right].add(left)

    ranked = []
    for path in simple_paths(adjacency, length):
        readout = sum(qubit_metrics[qubit]["readout_error"] for qubit in path)
        initialization = sum(qubit_metrics[qubit]["init_error"] for qubit in path)
        edges = [edge_error[tuple(sorted(edge))] for edge in zip(path, path[1:])]
        score = readout + initialization + two_qubit_weight * sum(edges)
        ranked.append(
            {
                "layout": list(path),
                "score": score,
                "readout_error_sum": readout,
                "init_error_sum": initialization,
                "cz_gate_errors": edges,
                "cz_error_sum": sum(edges),
            }
        )
    return sorted(ranked, key=lambda row: (row["score"], row["layout"]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select a calibration-only connected IBM initial layout"
    )
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--length", type=int, default=4)
    parser.add_argument("--two-qubit-weight", type=float, default=8.0)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    snapshot_path = args.snapshot.resolve()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ranked = rank_layouts(snapshot, args.length, args.two_qubit_weight)
    if not ranked:
        raise ValueError("No connected layout candidates found")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "ibm-calibration-layout-selection-v1",
        "backend": snapshot.get("backend"),
        "snapshot": str(snapshot_path),
        "snapshot_sha256": sha256(snapshot_path),
        "selection_uses_labels_or_qpu_outcomes": False,
        "path_length": args.length,
        "two_qubit_weight": args.two_qubit_weight,
        "score_formula": (
            "sum(readout_error) + sum(init_error) + "
            "two_qubit_weight * sum(cz_gate_error)"
        ),
        "selected": ranked[0],
        "candidate_count": len(ranked),
        "top_candidates": ranked[: args.top],
    }
    (output_dir / "selection.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    selected = ranked[0]
    markdown = [
        "# IBM calibration-only layout selection",
        "",
        f"- Backend: `{payload['backend']}`.",
        f"- Selected physical layout: `{selected['layout']}`.",
        f"- Score: `{selected['score']:.9f}`.",
        f"- Candidate paths: `{len(ranked)}`.",
        f"- Two-qubit weight: `{args.two_qubit_weight:g}`.",
        "- Labels and QPU classification outcomes were not used.",
        "",
        "The score is the sum of readout and initialization errors plus the weighted "
        "sum of calibrated CZ errors along the connected path.",
        "",
    ]
    (output_dir / "selection.md").write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps(payload["selected"], indent=2))


if __name__ == "__main__":
    main()
