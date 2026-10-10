"""Prepare authored content/data for the local detailed-report app.

Use after build_report_relations.py; compile with the installed Data app builder.
This script changes only src/data.json and src/content/report in a prepared app.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

SOURCES={
1:['docs/audit/README.md','results/hamiltonian/publication_summary.csv','results/trotter_v3/full_summary.json'],
2:['docs/audit/inventory.json','docs/audit/source_catalog.json','docs/audit/validation.json','docs/audit/document_index.json'],
3:['docs/project_map.md','docs/audit/source_catalog.json','docs/audit/README.md'],
4:['hamiltonian_kernel/core.py','hamiltonian_kernel/learning.py','quantum_reservoir/core.py','photonic_kernel/core.py'],
5:['hamiltonian_kernel/PUBLICATION_BENCHMARK.md','hamiltonian_kernel/core.py','hamiltonian_kernel/learning.py','hamiltonian_kernel/estimation.py','results/hamiltonian/publication_summary.csv','docs/audit/hamiltonian_review.md'],
6:['hamiltonian_kernel/TROTTER_SCALING_V3.md','hamiltonian_kernel/trotter_scaling_v3.py','results/trotter_v3/full_summary.json','docs/audit/hamiltonian_review.md'],
7:['quantum_reservoir/RESEARCH_PROTOCOL_H1_H5.md','quantum_reservoir/H1_H2_SPECTRAL_ANALYSIS.md','docs/audit/reservoir_review.md','results/qrc/spectral_checks.json'],
8:['photonic_kernel/core.py','photonic_kernel/ROBUSTNESS.md','photonic_kernel/strawberry_fields_robustness.py','docs/audit/photonic_theory_review.md'],
9:['docs/audit/legacy_review.md','docs/audit/source_migration.json','experiments/legacy/README.md'],
10:['qml_model_modules/00_INDEX.md','docs/audit/photonic_theory_review.md','qml_algorithms_data.js'],
11:['datasets/README.md','docs/audit/legacy_review.md','docs/audit/reservoir_review.md'],
12:['hamiltonian_kernel/learning.py','hamiltonian_kernel/PUBLICATION_BENCHMARK.md','quantum_reservoir/RESEARCH_PROTOCOL_H1_H5.md','hamiltonian_kernel/TROTTER_SCALING_V3.md'],
13:['docs/report/graph_relations.json','qml_relation_metrics.md','qml_interactive_graph.html'],
14:['docs/audit/README.md','docs/audit/review_checks.json','docs/audit/photonic_theory_review.md'],
15:['docs/GITHUB_PREPARATION.md','docs/REPRODUCIBILITY.md','docs/audit/validation.json','results/provenance.json','LICENSE_STATUS.md'],
16:['docs/audit/README.md','hamiltonian_kernel/TROTTER_SCALING_V3.md','quantum_reservoir/RESEARCH_PROTOCOL_H1_H5.md'],
17:['docs/report/QML_REPORT.md','docs/report/graph_relations.json'],
18:['docs/project_branches.mmd','docs/theory_branches.mmd']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--complete',action='store_true')
    args=parser.parse_args()
    app=args.app.resolve()
    if not app.is_relative_to(ROOT): raise ValueError('App must be inside this workspace')
    snapshot=json.loads((app/'src/data.json').read_text(encoding='utf-8'))
    relation=json.loads((ROOT/'docs/report/graph_relations.json').read_text(encoding='utf-8'))
    markdown=(ROOT/'docs/report/QML_REPORT.md').read_text(encoding='utf-8')
    sections=[]
    chunks=re.split(r'(?=^## \d+\.)',markdown,flags=re.M)[1:]
    for text in chunks:
        title=text.splitlines()[0].removeprefix('## ')
        number=int(title.split('.')[0]); query=f'chapter_{number:02}'
        # Local links remain actionable in the Markdown deliverable. The portable
        # app contains file references as text rather than broken HTTP links.
        text=re.sub(r'\[([^\]]+)\]\((?!https?://)([^)]+)\)',lambda m:f'{m[1]} (`{m[2]}`)',text)
        if number==18:
            text='## 18. Diagramy referencyjne\n\nPełne mapy struktury projektu i taksonomii znajdują się poniżej. Kliknięcie węzła otwiera jego relacje. W rozdziale 13 można przełączyć warstwę i przeglądać także relacje kuratorskie oraz importy. Układ węzłów nie mierzy odległości naukowej.'
        blocks=[]; pending=[]; table_count=0
        lines=text.strip().splitlines(); position=0
        while position<len(lines):
            if lines[position].startswith('|') and position+1<len(lines) and re.match(r'^\|[\s:|\-]+\|$',lines[position+1]):
                if pending:
                    blocks.append({'kind':'narrative','text':'\n'.join(pending).strip()});pending=[]
                headers=[v.strip() for v in lines[position].strip('|').split('|')]
                position+=2; table_rows=[]
                while position<len(lines) and lines[position].startswith('|'):
                    values=[v.strip().replace('`','') for v in lines[position].strip('|').split('|')]
                    assert len(values)==len(headers),(number,values,headers)
                    table_rows.append({f'c{i}':v for i,v in enumerate(values)})
                    position+=1
                table_count+=1; tid=f'chapter-{number:02}-table-{table_count}'
                table_rows=[{**row,'_id':f'{tid}-row-{i+1}'} for i,row in enumerate(table_rows)]
                blocks.append({'kind':'table','id':tid,'queryId':tid,'headers':headers})
                snapshot['queries'][tid]={'rows':table_rows,'source':{'label':f'Tabela rozdziału {number}: {headers[0]}','files':SOURCES[number],'evidenceFlow':[{'title':'Tabela raportu','detail':'Wartości i opisy przepisane bez zmiany z tabeli Markdown raportu; ich źródła wymieniono poniżej.'}]}}
            else:
                pending.append(lines[position]);position+=1
        if pending: blocks.append({'kind':'narrative','text':'\n'.join(pending).strip()})
        sections.append(dict(id=f'chapter-{number:02}',number=number,title=title,markdown=text.strip(),queryId=query,blocks=blocks))
        rows=[]
        for file in SOURCES[number]:
            data=(ROOT/file).read_bytes()
            rows.append({'file':file,'sha256':hashlib.sha256(data).hexdigest(),'role':'lokalne źródło rozdziału'})
        snapshot['queries'][query]={'rows':rows,'source':{'label':f'Źródła rozdziału {number}','files':SOURCES[number],'evidenceFlow':[{'title':'Odczyt i interpretacja','detail':'Synteza lokalnych źródeł, rachunków i audytu z 22.09.2026; rozwinięcie objaśnień 23.09.2026. Bez nowych treningów i uruchomień QPU.'}],'caveats':['Lista źródeł dokumentuje pochodzenie narracji, nie jest nowym pomiarem.']}}
    snapshot['queries']['relations']={'rows':relation['relations'],'source':{'label':'235 objaśnionych krawędzi czterech grafów','files':[x['path'] for x in relation['provenance']],'evidenceFlow':[{'title':'Ekstrakcja i objaśnienia','detail':'49 krawędzi projektu, 30 taksonomii, 19 relacji kuratorskich i 137 importów. Ręczne objaśnienia sprawdzone na kompletność; importy przypisane do linii AST.'}],'caveats':['Kierunek ma inne znaczenie w poszczególnych warstwach. Statyczny graf importów jest niepełnym modelem zależności wykonania.']}}
    snapshot['queries']['similarities']={'rows':[{**r,'shared_text':'; '.join(r['shared_values']),'calculation':' + '.join('1/'+str(c['df']) for c in r['contributions'])} for r in relation['automatic_relations']], 'source':{'label':'Wszystkie dodatnie podobieństwa atlasu w 9 cechach','files':['qml_algorithms_data.js','qml_interactive_graph.html','qml_relation_metrics.md'],'metricDefinitions':[{'label':'Score podobieństwa','definition':'Suma 1/df(v) dla wspólnych etykiet wybranej cechy. Waga wizualna jest ograniczana do przedziału 1–5.','formula':'score = sum(1/df); weight = min(5, max(1,1+5*score))','componentIds':['similarity-explorer']}],'caveats':['To 506 wpisów para×cecha, nie 506 różnych par. Score nie jest metryką odległości ani oceną przewagi kwantowej.']}}
    snapshot['buildStatus']='complete' if args.complete else 'creating'
    snapshot['report']['asOf']='2026-09-22'
    (app/'src/data.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    content=app/'src/content/report'
    (content/'chapters.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2),encoding='utf-8')
    (content/'graphs.json').write_text(json.dumps({k:{'nodes':v['nodes'],'edges':v['edges']} for k,v in relation['graphs'].items()},ensure_ascii=False,indent=2),encoding='utf-8')
    (content/'facets.json').write_text(json.dumps(relation['facets'],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'chapters':len(sections),'words':len(markdown.split()),'graph_edges':len(relation['relations']),'similarities':len(relation['automatic_relations']),'status':snapshot['buildStatus']}))


if __name__=='__main__': main()
