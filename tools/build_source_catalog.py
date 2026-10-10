"""Generate a mechanical source catalogue and module import graph."""
from __future__ import annotations
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("hamiltonian_kernel", "quantum_reservoir", "photonic_kernel", "experiments", "tools", "scripts", "audits", "tests")


def main():
    paths = sorted({p for d in FOLDERS for p in (ROOT/d).rglob("*.py") if "__pycache__" not in p.parts}
                   | set((ROOT / "analysis_output").glob("*.py")) | set(ROOT.glob("*.py")))
    modules = {p.relative_to(ROOT).with_suffix("").as_posix().replace("/", "."): p for p in paths}
    nodes = {m: f"n{i}" for i, m in enumerate(modules)}
    rows, edges = [], set()
    for module, path in modules.items():
        content = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(content)
        defs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package = module.split(".")[:-node.level]
                    base = ".".join(package + ([base] if base else []))
                imports.add(base)
            elif isinstance(node, ast.Import):
                imports.update(n.name for n in node.names)
        for dependency in imports:
            if dependency in nodes:
                edges.add((module, dependency))
        rows.append({"path": path.relative_to(ROOT).as_posix(), "lines": len(content.splitlines()),
                     "definitions": defs, "imports": sorted(imports)})
    out = ROOT / "docs/audit"
    (out/"source_catalog.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    text = ["# Katalog plików źródłowych\n", "Automatyczna analiza AST: składnia, deklaracje i importy. To indeks pokrycia, nie dowód przeglądu każdej instrukcji ani poprawności semantycznej. Importy dynamiczne i zależności przez pliki nie występują w grafie importów.\n",
            "| Plik | Linie | Deklaracje na poziomie modułu |", "|---|---:|---|"]
    for row in rows:
        text.append(f"| [{row['path']}](../../{row['path']}) | {row['lines']} | {', '.join(row['definitions']) or 'inicjalizacja / adapter'} |")
    (out/"source_catalog.md").write_text("\n".join(text)+"\n", encoding="utf-8")
    graph = ["flowchart LR"]
    for module, node in nodes.items():
        graph.append(f'  {node}["{module}"]')
    graph.extend(f"  {nodes[a]} --> {nodes[b]}" for a,b in sorted(edges))
    (ROOT/"docs/source_imports.mmd").write_text("\n".join(graph)+"\n", encoding="utf-8")
    print(f"Catalogued {len(rows)} Python files and {len(edges)} static local imports.")


if __name__ == "__main__":
    main()
