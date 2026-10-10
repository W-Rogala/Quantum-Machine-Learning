from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .core import EvolutionConfig, circuit_resources
from .protocol import load_frozen_protocol


CORRECTION_SCHEMA = "resource-aware-hamiltonian-kernel.cost-correction.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def correct_cost_rows(
    rows: list[dict[str, str]],
    *,
    n_qubits: int,
    trotter_order: int,
    trotter_steps: int,
) -> tuple[list[dict[str, str]], int]:
    corrected: list[dict[str, str]] = []
    changed = 0
    for source in rows:
        row = dict(source)
        if row.get("family") in {"fidelity", "projected"}:
            configuration = json.loads(row["configuration_json"])
            candidate = configuration["candidate"]
            config = EvolutionConfig(
                n_qubits=n_qubits,
                evolution_time=float(candidate["evolution_time"]),
                interaction_strength=float(candidate["interaction_strength"]),
                transverse_field=float(candidate["transverse_field"]),
                topology=str(candidate["topology"]),
                method="trotter",
                trotter_order=trotter_order,
                trotter_steps=trotter_steps,
            )
            gates_per_map = int(circuit_resources(config)["two_qubit_gates"])
            map_executions = int(row["map_executions"])
            expected_gate_shots = map_executions * gates_per_map
            if (
                int(row["two_qubit_gates_per_map"]) != gates_per_map
                or int(row["two_qubit_gate_shots"]) != expected_gate_shots
            ):
                changed += 1
            row["two_qubit_gates_per_map"] = str(gates_per_map)
            row["two_qubit_gate_shots"] = str(expected_gate_shots)
        corrected.append(row)
    return corrected, changed


def write_correction(
    protocol_path: Path,
    input_path: Path,
    output_path: Path,
    *,
    trotter_order: int = 2,
    trotter_steps: int = 2,
) -> Path:
    protocol, frozen = load_frozen_protocol(protocol_path)
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    corrected, changed = correct_cost_rows(
        rows,
        n_qubits=protocol.n_qubits,
        trotter_order=trotter_order,
        trotter_steps=trotter_steps,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(corrected)
    manifest: dict[str, Any] = {
        "schema": CORRECTION_SCHEMA,
        "status": "completed",
        "protocol_hash": frozen["protocol_hash"],
        "correction": "zero-interaction maps contain no logical two-qubit gates",
        "scope": ["two_qubit_gates_per_map", "two_qubit_gate_shots"],
        "metrics_and_kernel_matrices_changed": False,
        "source_outer_results": str(input_path.resolve()),
        "source_outer_results_sha256": _sha256(input_path),
        "corrected_outer_results": str(output_path.resolve()),
        "corrected_outer_results_sha256": _sha256(output_path),
        "rows": len(rows),
        "rows_corrected": changed,
        "n_qubits": protocol.n_qubits,
        "trotter_order": trotter_order,
        "trotter_steps": trotter_steps,
    }
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Version a resource-cost correction")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trotter-order", type=int, default=2)
    parser.add_argument("--trotter-steps", type=int, default=2)
    args = parser.parse_args()
    manifest = write_correction(
        args.protocol.resolve(),
        args.input.resolve(),
        args.output.resolve(),
        trotter_order=args.trotter_order,
        trotter_steps=args.trotter_steps,
    )
    print(json.dumps({"status": "completed", "manifest": str(manifest)}, indent=2))


if __name__ == "__main__":
    main()
