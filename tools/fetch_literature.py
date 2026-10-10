"""Download the catalogued public full texts for personal use; never bypass access controls."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output/literature')
    parser.add_argument('--redistributable-only', action='store_true')
    parser.add_argument('--work-id', help='Download only this catalog ID')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT / 'docs/literature/catalog.json').read_text(encoding='utf-8'))
    results = []
    for work in catalog['works']:
        if args.work_id and work['id'] != args.work_id:
            continue
        for index, version in enumerate(work['versions']):
            if args.redistributable_only and not version.get('repository_file'):
                continue
            url = version.get('pdf_url') or version.get('source_url')
            if not url or not version.get('sha256'):
                continue
            name = work['id'].replace('/', '-') + f'-{index + 1}.pdf'
            target = args.output_dir / name
            result = {'work_id': work['id'], 'url': url, 'file': str(target)}
            try:
                if target.exists():
                    data = target.read_bytes()
                else:
                    request = urllib.request.Request(url, headers={'User-Agent': 'QML-Literature-Library/1.0'})
                    with urllib.request.urlopen(request, timeout=90) as response:
                        data = response.read(40 * 1024 * 1024 + 1)
                    time.sleep(3 if 'arxiv.org' in url else 1)
                if not data.startswith(b'%PDF-') or len(data) > 40 * 1024 * 1024:
                    raise ValueError('Response is not a PDF or exceeds 40 MiB')
                digest = hashlib.sha256(data).hexdigest()
                if digest != version['sha256']:
                    raise ValueError('PDF differs from checked edition; inspect source and license before accepting')
                if not target.exists():
                    target.write_bytes(data)
                result.update(status='verified', sha256=digest)
            except Exception as error:
                result.update(status='failed', error=str(error))
            results.append(result)
    if args.work_id and not any(w['id'] == args.work_id for w in catalog['works']):
        parser.error('Unknown catalog work ID')
    (args.output_dir / 'download_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'verified': sum(r['status'] == 'verified' for r in results), 'failed': sum(r['status'] == 'failed' for r in results)}, indent=2))
    raise SystemExit(any(r['status'] == 'failed' for r in results))

if __name__ == '__main__':
    main()
