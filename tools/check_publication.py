"""Check the explicit publication scope without reading or printing credentials."""
from __future__ import annotations
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ("hamiltonian_kernel", "quantum_reservoir", "photonic_kernel", "experiments",
               "tests", "audits", "tools", "scripts", "qml_model_modules", "docs", "results", ".github")
SUFFIXES = {".py", ".md", ".json", ".csv", ".toml", ".yml", ".yaml", ".mmd", ".svg", ".html", ".js", ".txt", ".cjs", ".mjs", ".jsx", ".css", ".bib"}
REVIEWED_EVIDENCE = (
    "analysis_output/qrc_spectral_h1_h2/qubit_summary.csv",
    "analysis_output/qrc_h3_memory/h3_contrasts.csv",
    "analysis_output/qrc_h3_memory/profile_summaries.csv",
    "analysis_output/scar_wine_ibm_qpu_report.md",
    "analysis_output/h2_mathematical_description_proof.md",
)
BINARY_ASSETS = ("docs/mathematical_report/bibliography/report.sqlite",)

SECRET = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-proj-[A-Za-z0-9_-]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def publication_files():
    for directory in DIRECTORIES:
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and path.suffix in SUFFIXES and "__pycache__" not in path.parts:
                if path.name == "publication_check.json" or path.name.startswith("test_run"):
                    continue
                yield path
    for name in REVIEWED_EVIDENCE + BINARY_ASSETS:
        path = ROOT / name
        if not path.is_file():
            raise FileNotFoundError("Required publication asset: " + name)
        yield path
    yield ROOT / "docs/mathematical_report/vendor/katex/LICENSE"
    yield from sorted((ROOT / "docs/mathematical_report/vendor/katex/fonts").glob("*.woff2"))
    for path in sorted(ROOT.iterdir()):
        if path.is_file() and (path.suffix in SUFFIXES or path.name in {".gitignore", ".gitattributes", "LICENSE", "NOTICE"}):
            yield path
    for path in sorted((ROOT / "analysis_output").glob("*.py")):
        yield path
    if (ROOT / "analysis_output/README.md").exists():
        yield ROOT / "analysis_output/README.md"
    for folder in ("wine", "optdigits", "breast_cancer_wisconsin_diagnostic"):
        yield from sorted(p for p in (ROOT / "datasets/qml_benchmarks" / folder).glob("*") if p.is_file())
    if (ROOT / "datasets/README.md").exists():
        yield ROOT / "datasets/README.md"


def main():
    paths = sorted(set(publication_files()))
    issues = []
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        if path.stat().st_size > 10 * 1024 * 1024:
            issues.append({"path": rel, "issue": "publication file exceeds 10 MiB"})
        if path.suffix in {".woff2", ".sqlite"}:
            continue
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        if SECRET.search(content):
            issues.append({"path": rel, "issue": "possible credential; value suppressed"})
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=rel)
            except SyntaxError as error:
                issues.append({"path": rel, "issue": f"syntax error on line {error.lineno}"})
    result = {"scope": "explicit publication allowlist; not a proof of absence of all secrets",
              "file_count": len(paths), "total_bytes": sum(p.stat().st_size for p in paths),
              "issues": issues, "status": "passed" if not issues else "failed"}
    output = ROOT / "docs/audit/publication_check.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(issues))


if __name__ == "__main__":
    main()
