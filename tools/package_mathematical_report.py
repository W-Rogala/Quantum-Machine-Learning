"""Bundle the verified offline report, source evidence and bibliography."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/mathematical_report'
APP=ROOT/'output/mathematical_report_app_20261005'
OUT=ROOT/'output/reports'
HTML=OUT/'QML_monografia_matematyczna_2026-10-05.html'

def main():
    checks=json.loads((DOC/'build_checks.json').read_text(encoding='utf8'))
    if checks['unresolved']:raise ValueError('Unresolved report references')
    if json.loads((APP/'src/data.json').read_text(encoding='utf8'))['buildStatus']!='complete':raise ValueError('Incomplete report')
    qa=json.loads((ROOT/'output/math_report_qa/browser_offline.json').read_text(encoding='utf8'))
    if qa['errors'] or qa['remoteRequests'] or qa['mobileOverflow']:raise ValueError('Offline QA did not pass')
    files={'START_RAPORT.html':HTML,'CZYTAJ_NAJPIERW.md':DOC/'README.md'}
    for p in DOC.rglob('*'):
        if p.is_file():files['docs/mathematical_report/'+p.relative_to(DOC).as_posix()]=p
    source=json.loads((DOC/'source_manifest.json').read_text(encoding='utf8'))
    for r in source:
        p=ROOT/r['path']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256'] and hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=r.get('sha256_lf'):raise ValueError('Changed source: '+r['path'])
        files['code/'+r['path']]=p
    for p in (APP/'src/content/report').glob('*'):
        if p.suffix in ('.jsx','.css'):files['app_content/'+p.name]=p
    snap=json.loads((DOC/'snapshot.json').read_text(encoding='utf8'))
    for query in snap['queries'].values():
        for name in query.get('source',{}).get('files',[]):
            p=(ROOT/name).resolve()
            if p.is_relative_to(ROOT) and p.is_file() and not p.is_relative_to(DOC):files['evidence/'+name]=p
    for name in ('tools/render_report_math.cjs','tools/verify_math_report_browser.cjs'):
        files[name]=ROOT/name
    for name in ('browser_offline.json','browser_preview.json'):
        p=ROOT/'output/math_report_qa'/name
        if p.exists():files['verification/'+name]=p
    for name in ('LICENSE','NOTICE.md'):
        p=ROOT/name
        if p.exists():files[name]=p
    sums={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in sorted(files.items())}
    package=OUT/'QML_monografia_matematyczna_2026-10-05.zip'
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(files.items()):z.write(p,name)
        z.writestr('SHA256SUMS.json',json.dumps(sums,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(package) as z:
        if z.testzip():raise ValueError('ZIP integrity error')
        if any(hashlib.sha256(z.read(name)).hexdigest()!=h for name,h in sums.items()):raise ValueError('SHA mismatch in package')
    result=dict(html=str(HTML),html_sha256=sums['START_RAPORT.html'],zip=str(package),zip_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),files=len(files)+1,zip_bytes=package.stat().st_size,content=checks)
    (OUT/'QML_monografia_matematyczna_2026-10-05_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
