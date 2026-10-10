"""Vendor MIT KaTeX fonts and inspect primary bibliographic metadata."""
import pathlib,re,urllib.request,base64,json,html,concurrent.futures,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
DOC=ROOT/'docs/mathematical_report'
def request(url):
    req=urllib.request.Request(url,headers={'User-Agent':'QML-mathematical-report/1.0 (bibliography verification)'})
    return urllib.request.urlopen(req,timeout=20).read()
def fonts():
    p=DOC/'vendor/katex';css=(p/'katex.min.css').read_text()
    names=set(re.findall(r'url\((fonts/[^)]+\.woff2)\)',css))
    def load(n):
        dest=p/n;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():dest.write_bytes(request('https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/'+n))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(load,sorted(names)))
    css=re.sub(r'src:url\(fonts/([^)]+)\.woff2\) format\("woff2"\)[^;]*;',lambda m:'src:url(data:font/woff2;base64,'+base64.b64encode((p/('fonts/'+m.group(1)+'.woff2')).read_bytes()).decode()+') format("woff2");',css)
    css=css.replace('body{counter-reset:katexEqnNo mmlEqnNo}', '.qml-math{counter-reset:katexEqnNo mmlEqnNo}')
    dest=ROOT/'output/mathematical_report_app_20261005/src/content/report/katex-offline.css';dest.write_text(css)
    if re.search(r'url\((?!data:)',css):raise ValueError('External font URL remains')
    (DOC/'vendor/README.md').write_text('KaTeX 0.16.22, MIT License. Distribution and font files from https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/ . KaTeX official documentation: https://katex.org/docs/node . Mathematical HTML generated locally; offline CSS embeds WOFF2. No remote runtime request.',encoding='utf8')
    print('embedded',len(names),'fonts',dest.stat().st_size,flush=True)
def metadata():
    refs=json.loads((DOC/'bibliography/references.json').read_text(encoding='utf8'))
    dest=DOC/'bibliography/metadata_checks.json';checks=json.loads(dest.read_text(encoding='utf8')) if dest.exists() else {}
    def inspect(r):
        if 'arxiv.org/abs/' not in r['url'] or (r['id'] in checks and checks[r['id']].get('url')==r['url']):return None
        try:
            txt=request(r['url']).decode('utf8')
            values={}
            for tag in re.findall(r'<meta\s+[^>]+>',txt):
                at={k.lower():html.unescape(v) for k,v in re.findall(r'(\w+)=["\']([^"\']*)["\']',tag)}
                if at.get('name','').startswith('citation_'):values.setdefault(at['name'],[]).append(at.get('content',''))
            title=values.get('citation_title',[''])[0];authors=values.get('citation_author',[])
            return r['id'],dict(url=r['url'],title=title,authors=authors,checked='2026-10-05',status='verified-primary-metadata' if title else 'retrieved-no-citation-meta',sha256=__import__('hashlib').sha256(txt.encode()).hexdigest())
        except Exception as e:return r['id'],dict(url=r['url'],status='unavailable',error=str(e))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(inspect,refs):
            if result:checks[result[0]]=result[1];print(result[0],result[1]['status'],flush=True)
    dest.write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':
    if 'fonts' in sys.argv:fonts()
    if 'metadata' in sys.argv:metadata()
