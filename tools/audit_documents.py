"""Read-only extraction of local project PDF/PowerPoint evidence for review."""
from __future__ import annotations
import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / "tmp" / "project_audit_documents"
    destination.mkdir(parents=True, exist_ok=True)
    index = []
    for path in sorted((ROOT / "output").rglob("*")):
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(path)
            parts = [f"PAGE {i + 1}\n{page.extract_text()}" for i, page in enumerate(reader.pages)]
            count = len(parts)
        elif path.suffix.lower() == ".pptx":
            with zipfile.ZipFile(path) as archive:
                names = [n for n in archive.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
                names.sort(key=lambda s: int(s.rsplit("slide", 1)[1][:-4]))
                parts = []
                for i, name in enumerate(names):
                    tree = ET.fromstring(archive.read(name))
                    lines = [e.text for e in tree.iter() if e.tag.endswith("}t") and e.text]
                    parts.append(f"SLIDE {i + 1}\n" + "\n".join(lines))
            count = len(parts)
        else:
            continue
        target = destination / (path.stem + ".txt")
        target.write_text("\n\n".join(parts), encoding="utf-8")
        index.append({"path": path.relative_to(ROOT).as_posix(), "pages_or_slides": count,
                      "extracted_text": target.relative_to(ROOT).as_posix()})
    (ROOT / "docs/audit/document_index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(index, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
