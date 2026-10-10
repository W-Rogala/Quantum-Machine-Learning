"""Check identities, bibliography coverage and bytes of the curated literature library."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    lib = ROOT / 'docs/literature'
    catalog = json.loads((lib / 'catalog.json').read_text(encoding='utf-8'))['works']
    assets = json.loads((lib / 'manifest.json').read_text(encoding='utf-8'))['assets']
    references = json.loads((ROOT / 'docs/mathematical_report/bibliography/references.json').read_text(encoding='utf-8'))
    works = {w['id']: w for w in catalog}
    assert len(works) == len(catalog), 'Duplicate work IDs'
    assert {r['id'] for r in references} <= {b for w in catalog for b in w['bibliography_ids']}, 'Missing monograph citation'
    files = set()
    for asset in assets:
        path = (ROOT / asset['path']).resolve()
        assert path.is_relative_to((lib / 'pdf').resolve()), 'PDF outside curated library'
        assert path not in files, 'Duplicate PDF'
        files.add(path)
        data = path.read_bytes()
        assert data.startswith(b'%PDF-'), asset['path']
        assert len(data) == asset['bytes'], asset['path']
        assert hashlib.sha256(data).hexdigest() == asset['sha256'], asset['path']
        assert 'creativecommons.org/licenses/' in asset['license_url'], asset['path']
        assert asset['authors'] and asset['license_evidence'].get('url'), asset['path']
        assert any(v.get('repository_file') == asset['path'] and v.get('sha256') == asset['sha256'] for v in works[asset['work_id']]['versions']), asset['path']
    assert files == {p.resolve() for p in (lib / 'pdf').glob('*.pdf')}, 'Unlisted PDF'
    with sqlite3.connect(f'file:{(lib / "library.sqlite").as_posix()}?mode=ro', uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        rows = db.execute('SELECT id,metadata_json FROM works').fetchall()
        assert {key for key, _ in rows} == set(works)
        assert all(json.loads(value) == works[key] for key, value in rows)
        assert db.execute('SELECT COUNT(*) FROM versions').fetchone()[0] == sum(len(w['versions']) for w in catalog)
        assert db.execute('SELECT COUNT(*) FROM citations').fetchone()[0] == sum(len(w['cited_in']) for w in catalog)
    print(json.dumps({'status': 'passed', 'works': len(works), 'verified_pdfs': len(files), 'bibliography_entries': len(references)}, indent=2))

if __name__ == '__main__':
    main()
