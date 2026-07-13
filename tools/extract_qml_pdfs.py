from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "analysis_output"

PDFS = [
    {
        "id": "lecture_notes_2025_26",
        "title": "2025/26 Quantum Machine Learning Lecture Notes",
        "path": Path(r"D:\LLM\Openscience\QML\2025_26_Quantum_Machine_Learning_Lecture_Notes.pdf"),
    },
    {
        "id": "practical_guide_qml_qo",
        "title": "A Practical Guide to Quantum Machine Learning and Quantum Optimization",
        "path": Path(r"D:\LLM\Openscience\QML\A-Practival-Guide-to-Quantum-Machine-Learning-and-Quantum-Optimization.pdf"),
    },
    {
        "id": "quantum_machine_learning_book",
        "title": "Quantum Machine Learning",
        "path": Path(r"D:\LLM\Openscience\QML\Quantum Machine Learning.pdf"),
    },
    {
        "id": "algorithms_applications_limitations",
        "title": "Quantum Machine Learning Algorithms Applications and Limitations",
        "path": Path(r"D:\LLM\Openscience\QML\Quantum_Machine_Learning_Algorithms_Applications_a.pdf"),
    },
]

TERMS = {
    "qsvm": [
        r"\bQSVM\b",
        r"support vector",
        r"quantum support vector",
        r"kernel method",
        r"quantum kernel",
    ],
    "qnn": [
        r"quantum neural",
        r"\bQNN\b",
        r"variational quantum",
        r"parameteri[sz]ed quantum",
        r"parameterized quantum",
        r"ansatz",
    ],
    "vqc": [
        r"variational quantum classifier",
        r"\bVQC\b",
        r"quantum classifier",
    ],
    "qml_regression": [
        r"regression",
        r"linear regression",
        r"least squares",
        r"curve fitting",
    ],
    "qknn": [
        r"k[- ]nearest",
        r"\bQKNN\b",
        r"nearest neighbor",
    ],
    "qkmeans": [
        r"k[- ]means",
        r"clustering",
        r"quantum clustering",
    ],
    "qgan": [
        r"\bQGAN\b",
        r"generative adversarial",
        r"Born machine",
        r"generative model",
    ],
    "qbnn": [
        r"Bayesian",
        r"Bayes",
        r"probabilistic",
    ],
    "qaoa": [
        r"\bQAOA\b",
        r"quantum approximate optimization",
        r"approximate optimization",
    ],
    "vqe": [
        r"\bVQE\b",
        r"variational quantum eigensolver",
        r"ground state",
    ],
    "hhl": [
        r"\bHHL\b",
        r"linear systems",
        r"matrix inversion",
    ],
    "qpe": [
        r"phase estimation",
        r"\bQPE\b",
    ],
    "grover": [
        r"Grover",
        r"amplitude amplification",
    ],
    "pca": [
        r"principal component",
        r"\bPCA\b",
        r"qPCA",
    ],
    "quantum_boltzmann": [
        r"Boltzmann",
        r"quantum Boltzmann",
    ],
    "annealing": [
        r"anneal",
        r"Ising",
        r"QUBO",
        r"adiabatic",
    ],
}


def flatten_outline(items, reader: PdfReader, level: int = 0) -> list[dict]:
    output = []
    for item in items:
        if isinstance(item, list):
            output.extend(flatten_outline(item, reader, level + 1))
            continue
        try:
            page = reader.get_destination_page_number(item) + 1
        except Exception:
            page = None
        title = getattr(item, "title", str(item))
        output.append({"level": level, "title": title, "page": page})
    return output


def normalize(text: str) -> str:
    cleaned = "".join(ch for ch in (text or "") if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return re.sub(r"\s+", " ", cleaned).strip()


def snippets_for(text: str, patterns: list[str], window: int = 260) -> list[str]:
    snippets = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            snippet = normalize(text[start:end])
            if snippet and snippet not in snippets:
                snippets.append(snippet)
            if len(snippets) >= 5:
                return snippets
    return snippets


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    pages_out = []
    manifest = []
    hits = {term: [] for term in TERMS}

    for spec in PDFS:
        reader = PdfReader(str(spec["path"]))
        metadata = {k: str(v) for k, v in (reader.metadata or {}).items()}
        outline = []
        try:
            outline = flatten_outline(reader.outline, reader)
        except Exception:
            outline = []

        doc_pages = []
        doc_text_parts = []
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                text = f"[EXTRACTION_ERROR: {exc}]"
            clean = normalize(text)
            doc_pages.append({"page": idx, "text": clean})
            doc_text_parts.append(f"\n\n=== PAGE {idx} ===\n{clean}")
            pages_out.append(
                {
                    "doc_id": spec["id"],
                    "doc_title": spec["title"],
                    "page": idx,
                    "text": clean,
                }
            )
            for term, patterns in TERMS.items():
                snippets = snippets_for(clean, patterns)
                if snippets:
                    hits[term].append(
                        {
                            "doc_id": spec["id"],
                            "doc_title": spec["title"],
                            "page": idx,
                            "snippets": snippets,
                        }
                    )

        (OUT_DIR / f"{spec['id']}.txt").write_text(
            "\n".join(doc_text_parts), encoding="utf-8"
        )
        manifest.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "path": str(spec["path"]),
                "pages": len(reader.pages),
                "metadata": metadata,
                "outline": outline,
                "extracted_pages": doc_pages,
            }
        )

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "pages.json").write_text(
        json.dumps(pages_out, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / "keyword_hits.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Extracted {sum(item['pages'] for item in manifest)} pages")
    for item in manifest:
        print(f"- {item['id']}: {item['pages']} pages")
    for term, term_hits in hits.items():
        print(f"{term}: {len(term_hits)} page hits")


if __name__ == "__main__":
    main()
