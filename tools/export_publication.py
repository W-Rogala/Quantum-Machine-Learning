"""Export only the reviewed publication scope; never include environments/results bulk."""
from __future__ import annotations
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from check_publication import ROOT, publication_files, main as check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/release/QML-github-ready-2026-10-09.zip")
    args = parser.parse_args()
    try:
        check()
    except SystemExit as result:
        if result.code:
            raise
    target = args.output.resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError("Export must remain inside this workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    paths = sorted(set(publication_files()))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():
            raise ValueError("Corrupt publication archive")
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    target.with_suffix(".sha256.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
    print(json.dumps({"archive": str(target), "files": len(paths), "bytes": target.stat().st_size}))


if __name__ == "__main__":
    main()
