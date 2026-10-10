"""Inventory project-owned files without walking installed dependencies."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".agents", ".codex", ".pnpm-store", "node_modules", "__pycache__",
            ".pytest_cache", ".mypy_cache", ".next", "tmp", "personal-project-crm"}


def files(root: Path):
    for directory, names, filenames in os.walk(root):
        names[:] = sorted(n for n in names if n not in EXCLUDED and not n.startswith((".venv", "venv")))
        for name in sorted(filenames):
            path = Path(directory) / name
            if path.suffix not in {".pyc", ".pyo"}:
                yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "audit" / "inventory.csv")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in files(ROOT):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("docs/audit/"):
            continue  # Audit products are not their own evidence.
        stat = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        rows.append({"path": relative, "bytes": stat.st_size, "sha256": digest.hexdigest()})
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    summary = {"files": len(rows), "bytes": sum(r["bytes"] for r in rows),
               "by_root": dict(Counter(r["path"].split("/")[0] for r in rows)),
               "excluded_directories": sorted(EXCLUDED)}
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
