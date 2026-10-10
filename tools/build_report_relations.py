"""Rebuild the detailed report's graph annexes from the reviewed source graphs.

Usage: python tools/build_report_relations.py --node /path/to/node
The imported source catalogue is the audit snapshot, not an assertion that
every current source line has undergone a new scientific review.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/report'

PROJECT = {
'Q>T': ('organizacja', 'Atlas teorii dostarcza definicji i kryteriów oceny pozostałych gałęzi.', 'Nie oznacza implementacji wszystkich opisanych algorytmów.'),
'Q>L': ('organizacja', 'Starsze eksperymenty dokumentują genezę pytań o mapę cech, szum i ansatz.', 'Historyczne H1/H2/H3 nie są hipotezami QRC o tych samych numerach.'),
'Q>H': ('organizacja', 'Gałąź statyczna bada zależne od danych Hamiltoniany i kernele klasyfikacyjne.', 'Nie jest to rezerwuar z historią wejściową.'),
'Q>R': ('organizacja', 'Gałąź czasowa bada stan pamiętający poprzednie wejścia oraz klasyczny odczyt.', 'Jej NRMSE nie porównuje się bezpośrednio z BA klasyfikacji.'),
'Q>P': ('organizacja', 'Gałąź fotoniczna koduje dane w układzie modów i rozkładach detekcji.', 'Osiem modów nie oznacza ośmiu kubitów.'),
'T>G': ('reprezentacja', 'Karty i opisy algorytmów dostarczają pojęć użytych w atlasie HTML/JS.', 'Dane atlasu są osobno zapisane i mogą wymagać synchronizacji z kartami.'),
'D>L': ('dane', 'Historyczne modele pobierają wybrane zadania klasyfikacyjne z puli danych.', 'Nie każdy moduł wykorzystuje każdy zbiór.'),
'D>H': ('dane', 'Benchmark Hamiltonowski przekształca dane klasyfikacyjne w parametry map.', 'Główny profil publikacyjny obejmuje moons, WDBC i Wine, nie całą pulę.'),
'D>P': ('dane', 'Wybrane próbki klasyczne sterują parametrami kodowania optycznego.', 'To wspólna rodzina źródeł danych, nie gwarancja identycznego preprocessingu.'),
'L>L1': ('organizacja', 'QSVM jest początkiem historycznej analizy PCA, alignmentu i liczby kubitów.', 'Część implementacji używa ridge lub LS-SVM; nazwa rodziny jest szersza niż solver.'),
'L1>L2': ('rozszerzenie', 'Analiza NISQ dodaje tłumienie, normalizację i finite-shot do wcześniejszych map.', 'Zmiana profilu szumu nie stanowi nowego niezależnego zbioru danych.'),
'L>L3': ('organizacja', 'SCAR bada strukturę ansatzu i jego zastosowanie w QNN.', 'Deskryptory ansatzu nie dowodzą energii VQE ani nowości bramki.'),
'L>L4': ('organizacja', 'HPO rozszerza porównanie na 14 adaptacji ansatzów i profile wykonania.', 'Adaptacja nazwanego ansatzu nie zawsze realizuje jego pełne pierwotne zastosowanie.'),
'L4>HW': ('implementacja warunkowa', 'Wybrany przypadek HPO może zostać zbudowany i wykonany przez adapter.', 'Wybór przypadku po testowej BA jest post-selection; patrz L-03.'),
'L3>HW': ('implementacja warunkowa', 'Obwód SCAR jest tłumaczony na instrukcje obsługiwane przez backend.', 'Kompilacja, symulacja i fizyczny job to różne statusy.'),
'H>HC': ('model', 'Hamiltonian zależny od x definiuje ewolucję mapy cech.', 'Parametry, stan początkowy i konwencja kubitów należą do definicji modelu.'),
'HC>HK': ('cechy i estymacja', 'Stany po ewolucji dostarczają overlapów lub lokalnych oczekiwań dla kernela.', 'Raw finite-shot Gram i PSD feature kernel nie są zamienne bez transformacji.'),
'HK>HB': ('eksperyment', 'Rodziny estymatorów są oceniane od pilota do kontrolowanego benchmarku.', 'Strzałka opisuje rozwój badań, nie automatyczną zależność wszystkich plików.'),
'HC>TS': ('pytanie badawcze', 'Wybór aproksymacji U prowadzi do badania rzędu i kroku Trottera.', 'Mniejszy błąd operatorowy nie gwarantuje większej BA.'),
'TS>V3': ('wersjonowanie', 'V3 rozdziela selekcję zadaniową, diagnostykę exact i osie kosztu.', 'Nowszy protokół nie przekształca wyników v2 w dane potwierdzające v3.'),
'HB>HW': ('implementacja warunkowa', 'Benchmark ma ścieżkę pilota sprzętowego i zapisu obwodów.', 'Pilot nie ma tej samej skali ani mocy co benchmark symulacyjny.'),
'V3>HW': ('zaplanowany etap', 'Adapter IBM v3 ma bramkę po zakończeniu wymaganej analizy development i holdout.', 'Obecny pełny run 1/1600 nie spełnia tej bramki; krawędź nie oznacza wykonania QPU.'),
'B>R': ('dane sekwencyjne', 'NARMA, Mackey–Glass i cele pamięci określają strumienie i targety QRC.', 'Cele mają różne horyzonty i znaczenie; wspólny generator nie daje wspólnej hipotezy.'),
'R>RC': ('model', 'QRC jest realizowane przez reset, ewolucję, pomiar cech i ridge.', 'Dynamika wewnętrzna pozostaje ustalona; odczyt jest uczony klasycznie.'),
'RC>RS': ('diagnostyka', 'Model kanału pozwala analizować spektrum, przemienność, rezonanse i predykcję.', 'Widmo przy zamrożonym wejściu nie dowodzi ESP dla dowolnej sekwencji.'),
'RS>RM': ('rozwój badań', 'Pytania o dynamikę motywują testy tego, którą pamięć widzi readout.', 'Nie oznacza logicznego wynikania H3 z potwierdzenia H1 lub H2.'),
'RM>RN': ('kontrola odporności', 'Profile pamięci są sprawdzane wobec szumu, washout i stacjonarności.', 'Poprawa zapominania może współwystępować z utratą użytecznej informacji.'),
'RC>RH': ('implementacja warunkowa', 'Odczyt trajektorii jest odwzorowywany na obwody odtwarzające okno historii.', 'Obcięta historia daje inne stany niż pełna; koszt odtworzenia jest częścią pomiaru.'),
'RH>HW': ('wykonanie', 'Ścieżka IBM korzysta z kompilacji i obsługi backendu.', 'Węzeł zbiorczy HW nie oznacza, że QRC działa przez wszystkich wymienionych dostawców.'),
'P>PC': ('model', 'Układ TMSV i interferometr określają rozkłady PNR.', 'Hafnian w małym symulatorze jest obliczeniem klasycznym.'),
'PC>PK': ('reprezentacja', 'Rozkłady lub próbki stają się histogramami, momentami i kernelami.', 'Agregacja event/orbit może usuwać informację potrzebną w zadaniu.'),
'PK>PR': ('kontrola odporności', 'Sprawdzany jest wpływ cutoff, strat i detektora na cechy oraz wynik.', 'To zależność analityczna; fizyczne straty i detekcja zachodzą przed zbudowaniem cech.'),
'PR>SF': ('implementacja warunkowa', 'Modele odporności mają opcjonalną realizację w Strawberry Fields.', 'Obecny audyt nie potwierdza runtime SF ani fizycznego X8; obowiązuje P-01.'),
'HK>BR': ('matematyczna', 'Iloczyn skalarny cech i ridge mają równoważny zapis dualny przez kernel.', 'Wymagane są te same cechy, centrowanie, bias i regularizacja.'),
'RC>BR': ('matematyczna', 'Historię wejść można traktować jako argument mapy cech rezerwuaru.', 'Kernel na historiach nie jest automatycznie statycznym fidelity kernelem na x_t.'),
'PC>BR': ('porównawcza', 'Fotonika jest inną fizyczną realizacją mapy danych do cech.', 'Aktualny statyczny kernel optyczny nie ma automatycznie pamięci QRC.'),
'HW>E': ('artefakty', 'Adaptery zapisują obwody, job metadata, zliczenia i analizy wykonania.', 'Sam katalog lub job ID nie zastępuje sprawdzonego statusu completion.'),
'HB>E': ('artefakty', 'Benchmark zapisuje protokół, splity, macierze, wyniki i koszty.', 'Raport zbiorczy powinien wskazywać właściwą wersję skorygowanych kosztów.'),
'V3>E': ('artefakty', 'V3 zapisuje postęp, wybory, outer rows, holdout i audyt.', 'Niepełne pliki muszą zachować status not_confirmatory.'),
'RN>E': ('artefakty', 'Podbadania QRC zapisują kontrole szumu i pamięci.', 'Współdzielone bloki i replikacje pomiarów nie są nowymi niezależnymi zadaniami.'),
'PK>E': ('artefakty', 'Fotoniczne estymatory zapisują cechy, zliczenia i metryki.', 'Wersja schematu overflow i detektora musi być częścią proweniencji.'),
'L1>E': ('artefakty', 'Historyczne QSVM zapisują wyniki selekcji i klasyfikacji.', 'Brak narysowanej krawędzi z innej gałęzi legacy nie oznacza braku jej wyników.'),
'E>A': ('kontrola', 'Artefakty są wejściem do sprawdzania integralności i zgodności z protokołem.', 'Nie każdy test jednostkowy czyta artefakty; część sprawdza sam kod.'),
'A>O': ('komunikacja', 'Sprawdzone wyniki powinny zasilać raporty, prezentacje i notebooki.', 'To zalecany przepływ; nie gwarancja, że każdy historyczny dokument przeszedł ten audyt.'),
'A>REV': ('ocena', 'Wyniki kontroli są jednym z dowodów dla audytu całości.', 'Audyt obejmuje również rachunki i teksty; nie jest prostym przepisaniem statusu tests passed.'),
'E>PUB': ('kuracja', 'Wybrane małe zestawienia skopiowano do results z hashami oryginałów.', 'Wycinek nie zawiera pełnego pakietu odtwarzania wszystkich runów.'),
'REV>GH': ('dokumentacja', 'Errata i ograniczenia stają się częścią czytelnego zakresu publikacji.', 'Gotowość repo nie oznacza usunięcia wszystkich P1.'),
'PUB>GH': ('publikacja lokalna', 'Małe wyniki i proweniencja mogą być wersjonowane razem z kodem.', 'Nie wykonano zdalnego opublikowania przez tę krawędź.'),
'X>Q': ('sąsiedztwo, wyłączenie', 'CRM/SPLOT współistnieje lokalnie z QML i został wyłączony z jego repo.', 'To nie jest naukowa ani programistyczna zależność projektu QML.'),
}

THEORY = {
'QML>K':'Metody jądrowe są jedną z rodzin opisu modeli QML.',
'K>QSVM':'Kernelowy QSVM używa klasyfikatora działającego na macierzy podobieństw.',
'QML>V':'Modele wariacyjne dobierają parametry obwodu przez optymalizację.',
'V>PQC':'PQC jest obiektem obwodowym używanym w wielu modelach QNN.',
'PQC>VQC':'VQC realizuje zadanie klasyfikacji za pomocą uczonego obwodu i pomiaru.',
'PQC>HYB':'Warstwa PQC może być składnikiem modelu klasyczno-kwantowego.',
'PQC>QCNN':'QCNN używa trenowanych operacji lokalnych; pooling wymaga także kanałów.',
'PQC>AE':'Autoenkoder używa trenowanej transformacji do kompresji określonej rodziny stanów.',
'PQC>QRL':'Niektóre polityki lub modele wartości QRL są realizowane obwodem parametryzowanym.',
'QML>GEN':'Modele generatywne opisują i próbkują rozkłady lub stany.',
'GEN>QGAN':'QGAN używa schematu adwersarialnego w zadaniu generatywnym.',
'GEN>QCBM':'QCBM generuje próbki z rozkładu Borna.',
'GEN>QBM':'QBM jest modelem energetycznym rozkładu lub stanu.',
'PQC>QGAN':'PQC może realizować generator albo dyskryminator.',
'PQC>QCBM':'PQC parametryzuje stan wyznaczający rozkład Borna.',
'QML>LA':'Algebra liniowa dostarcza podprogramów dla wybranych konstrukcji QML.',
'LA>HHL':'HHL rozwiązuje układ liniowy w postaci stanu przy określonym dostępie do danych.',
'LA>QSVT':'QSVT realizuje dopuszczalne przekształcenia wartości singularnych bloków.',
'LA>QPCA':'qPCA uzyskuje informację o spektrum przy zadeklarowanym modelu dostępu.',
'QSVT>QT':'Wybrana opisana konstrukcja transformera FTQC korzysta z tej rodziny narzędzi.',
'QML>CL':'Klasteryzacja grupuje dane według zdefiniowanego podobieństwa.',
'K>CL':'Kernel może definiować geometrię klastrów; nie każda klasteryzacja go wymaga.',
'QML>OPT':'Optymalizacja i wyszukiwanie są grupą narzędzi oraz zadań sąsiednich QML.',
'OPT>QAOA':'QAOA stosuje wariacyjny obwód problem–mikser do optymalizacji.',
'OPT>VQE':'VQE minimalizuje energię oczekiwaną znormalizowanego stanu próbnego.',
'OPT>QA':'Annealing realizuje czasową zmianę Hamiltonianu problemu.',
'OPT>GAS':'GAS używa adaptacyjnego progu i wzmacniania amplitudy.',
'V>QAOA':'Kąty QAOA są dobierane klasycznym optymalizatorem w ramie wariacyjnej.',
'V>VQE':'Parametry ansatzu VQE są dobierane do funkcji energii.',
'QA>QBM':'Annealer może być badanym samplerem modelu energetycznego, bez gwarancji docelowego Gibbsa.',
}

CURATED = {
'qsvm>quantum_kernels':('definicyjna w wariancie kernelowym','QSVM używa macierzy kernela estymowanej z map kwantowych.','Nie obejmuje bez rozróżnienia wszystkich algorytmów nazywanych FTQC QSVM.'),
'vqc>qnn':('przynależność rodziny','VQC to model klasyfikacyjny z rodziny modeli obwodowych QNN.','Nie każda QNN jest klasyfikatorem.'),
'hybrid_qnn>qnn':('kompozycja','Model hybrydowy zawiera kwantową warstwę uczoną lub parametryzowaną.','Wynik może być zdominowany przez część klasyczną; potrzebna ablacja.'),
'qgan>qnn':('możliwa implementacja','Generator lub dyskryminator może być obwodem QNN.','Krawędź nie oznacza, że oba elementy każdego QGAN są kwantowe.'),
'qcbm>qnn':('wspólny obwód','Obwód parametryzowany uczy rozkładu Borna.','Funkcja celu generatywna różni się od klasyfikacji VQC.'),
'qbm>annealing':('warunkowe próbkowanie','Oba podejścia operują na modelach energetycznych, np. Ising.','Annealer nie zapewnia automatycznie dokładnego samplera stanu Gibbsa.'),
'qcnn>qnn':('architektura','QCNN jest ustrukturyzowanym modelem obwodowym z redukcją rejestru.','Pooling wymaga kanałów; nie jest synonimem quanvolution.'),
'qae>qnn':('architektura','Autoenkoder używa uczonej transformacji stanu.','Nie daje bezstratnej kompresji dowolnej rodziny stanów.'),
'q_transformer>qsvt':('podprogram wybranej konstrukcji','Opisywany model FTQC korzysta z block encoding i przekształceń singularnych.','Nie jest to definicja wszystkich quantum transformers; odczyt tokenów wymaga osobnej konstrukcji.'),
'hhl_qla>qsvt':('pokrewieństwo algorytmiczne','Obie rodziny umożliwiają operacje algebry liniowej; QSVT pozwala budować nowoczesne solvery.','Oryginalny HHL nie wywołuje QSVT. Strzałka nie powinna oznaczać zależności implementacyjnej.'),
'qpca>hhl_qla':('pokrewieństwo algebry liniowej','Metody wymagają kontrolowanego dostępu do operatorów i informacji spektralnej.','HHL nie jest obowiązkowym etapem qPCA. Zalecana relacja nieskierowana: wspólna rodzina.'),
'qsvm>hhl_qla':('podprogram wariantu FTQC','Niektóre liniowo-algebraiczne konstrukcje LS-SVM używają solwera układu.','Kernelowy QSVM z klasycznym solverem w tym projekcie nie wymaga HHL.'),
'q_clustering>quantum_kernels':('możliwa geometria','Overlapy lub kernel mogą określać podobieństwo i odległości klastrów.','Średnia w przestrzeni danych nie musi być centroidem przestrzeni cech.'),
'qaoa>annealing':('inspiracja i związek graniczny','Naprzemienne operacje mają związek z dyskretyzacją pewnych ścieżek Hamiltonianowych.','Waga 5 jest oceną kuratorską; małe p i dowolne kąty nie dają ogólnej równoważności z annealingiem.'),
'qaoa>vqe':('wspólna rama wariacyjna','Oba podejścia dobierają parametry przez klasyczną optymalizację wartości oczekiwanej.','Inne są typowe ansatze, problemy i funkcje celu.'),
'gas>qaoa':('alternatywy zadaniowe','Obie rodziny mogą służyć do wybranych problemów optymalizacji dyskretnej.','GAS nie używa QAOA jako obowiązkowego podprogramu.'),
'gas>hhl_qla':('luźna analogia zasobowa','Porównanie wskazuje znaczenie kosztownych podprogramów, przygotowania danych i arytmetyki.','Nie ma tu konkretnej zależności GAS od HHL. Rozważyć usunięcie krawędzi albo oznaczenie jej wyłącznie jako analogii.'),
'vqe>qnn':('wspólne narzędzia','PQC, pomiary i optymalizator występują w obu rodzinach.','VQE optymalizuje energię; nie musi wykonywać zadania uczenia z etykietami.'),
'qrl>gas':('wybrany wariant','W pewnych konstrukcjach można rozważać Grover-like wyszukiwanie akcji.','Nie jest to zależność ogólnej polityki QRL; potrzebne założenia oracle i kosztów.'),
}


def parse_graph(path):
    content=path.read_text(encoding='utf-8')
    nodes=dict(re.findall(r'(\w+)\["([^"]+)"\]',content))
    edges=[]
    for line in content.splitlines():
        clean=re.sub(r'\["[^"]*"\]','',line).strip()
        match=re.match(r'^(\w+)\s+(-->|-\.\s+"[^"]*"\s+\.->)\s+(\w+)$',clean)
        if match:
            a,arrow,b=match.groups()
            nodes.setdefault(a,a); nodes.setdefault(b,b)
            edges.append((a,b,'przerywana' if arrow!='-->' else 'ciągła'))
    return nodes,edges


def import_sites(source, target):
    module=source.removesuffix('.py').replace('/','.')
    tree=ast.parse((ROOT/source).read_text(encoding='utf-8-sig'))
    sites=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom):
            base=node.module or ''
            if node.level:
                base='.'.join(module.split('.')[:-node.level]+([base] if base else []))
            if base==target:
                sites.append({'line':node.lineno,'names':[n.name for n in node.names]})
        elif isinstance(node,ast.Import):
            for name in node.names:
                if name.name==target: sites.append({'line':node.lineno,'names':[name.name]})
    return sites


def write_md(path,title,rows,fields):
    lines=['# '+title,'',
        'Stan źródeł: audyt 22.09.2026, objaśnienia 23.09.2026. Krawędzie są opisem zasobów i pojęć, nie nowymi wynikami eksperymentalnymi.','',
        '| '+' | '.join(label for key,label in fields)+' |',
        '| '+' | '.join('---' for _ in fields)+' |']
    for row in rows:
        lines.append('| '+' | '.join(str(row.get(key,'')).replace('|','∣').replace('\n',' ') for key,label in fields)+' |')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',default=shutil.which('node'))
    args=parser.parse_args()
    if not args.node: parser.error('--node is required when Node is not on PATH')
    code="const fs=require('fs'),vm=require('vm');const c={window:{}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),c,{timeout:1000});process.stdout.write(JSON.stringify(c.window.QML_DATA));"
    atlas=json.loads(subprocess.check_output([args.node,'-e',code,str(ROOT/'qml_algorithms_data.js')],encoding='utf-8'))
    OUT.mkdir(parents=True,exist_ok=True)
    allrows=[]; graphs={}
    for name,file,descriptions,prefix in [('project','project_branches.mmd',PROJECT,'P'),('theory','theory_branches.mmd',THEORY,'T')]:
        nodes,edges=parse_graph(ROOT/'docs'/file)
        assert {a+'>'+b for a,b,_ in edges}==set(descriptions),name
        rows=[]
        for i,(a,b,style) in enumerate(edges,1):
            value=descriptions[a+'>'+b]
            if isinstance(value,str): value=('taksonomia lub warunkowy związek',value,'Nie oznacza importu kodu, wykonania eksperymentu ani gwarancji przewagi.')
            kind,explanation,limit=value
            rows.append(dict(id=f'{prefix}{i:02}',layer=name,source=a,target=b,source_label=nodes[a],target_label=nodes[b],style=style,kind=kind,explanation=explanation,limit=limit,evidence='docs/'+file))
        graphs[name]={'nodes':[dict(id=k,label=v) for k,v in nodes.items()],'edges':rows}
        allrows.extend(rows)
    labels={n['id']:n['label'] for n in atlas['nodes']}
    curated=[]
    assert {e['source']+'>'+e['target'] for e in atlas['curatedEdges']}==set(CURATED)
    for i,edge in enumerate(atlas['curatedEdges'],1):
        kind,explanation,limit=CURATED[edge['source']+'>'+edge['target']]
        curated.append(dict(id=f'C{i:02}',layer='curated',source=edge['source'],target=edge['target'],source_label=labels[edge['source']],target_label=labels[edge['target']],kind=kind,explanation=explanation,limit=limit,weight=edge['weight'],original_label=edge['label'],evidence='qml_algorithms_data.js:curatedEdges'))
    graphs['curated']={'nodes':[dict(id=k,label=v) for k,v in labels.items()],'edges':curated}
    allrows.extend(curated)
    nodes,edges=parse_graph(ROOT/'docs/source_imports.mmd')
    imports=[]
    for i,(a,b,style) in enumerate(edges,1):
        source=nodes[a].replace('.','/')+'.py'; target=nodes[b]
        sites=import_sites(source,target)
        assert sites,(source,target)
        names=', '.join(sorted({n for s in sites for n in s['names']}))
        if source.startswith('tests/'): purpose='Test odwołuje się do importowanych elementów badanego modułu; sam import nie dowodzi zakresu asercji.'
        elif source.startswith('audits/'): purpose='Audyt wykorzystuje wskazany moduł. Współdzielenie kodu trzeba uwzględnić przy ocenie niezależności kontroli.'
        elif source.startswith('tools/'): purpose='Narzędzie uruchomienia, adapter lub generator dokumentów wykorzystuje wskazany moduł; nie stanowi przez to nowej replikacji.'
        else: purpose='Moduł pobiera wskazane symbole do swojego namespace. O tym, które ścieżki je wywołują, decyduje przepływ wykonania.'
        imports.append(dict(id=f'I{i:03}',layer='imports',source=nodes[a],target=target,source_label=nodes[a],target_label=target,kind='statyczny import',explanation=purpose+' Importowane: '+names,limit='Kierunek to importer → importowany moduł; import może być warunkowy. Graf pomija część importów dynamicznych i zależności przez pliki.',evidence=source+':'+','.join(str(s['line']) for s in sites),sites=sites))
    allrows.extend(imports)
    graphs['imports']={'nodes':[dict(id=v,label=v) for v in nodes.values()],'edges':imports}
    automatic=[]; facets=[]
    for facet in atlas['relationFacets']:
        key=facet['key']
        if key=='curated': continue
        counts=Counter(v.lower() for n in atlas['nodes'] for v in n.get(key,[]))
        rows=[]
        for i,a in enumerate(atlas['nodes']):
            left={v.lower() for v in a.get(key,[])}
            for b in atlas['nodes'][i+1:]:
                shared=[v for v in b.get(key,[]) if v.lower() in left]
                if not shared: continue
                contributions=[{'value':v,'df':counts[v.lower()],'contribution':1/counts[v.lower()]} for v in shared]
                score=sum(c['contribution'] for c in contributions)
                rows.append(dict(facet=key,facet_label=facet['label'],source=a['id'],target=b['id'],source_label=a['label'],target_label=b['label'],shared_values=shared,contributions=contributions,score=score,weight=max(1,min(5,1+5*score))))
        rows.sort(key=lambda x:-x['score'])
        for rank,row in enumerate(rows,1): row.update(rank=rank,visible_at_default_limit_58=rank<=58,id=f'S-{key}-{rank:03}')
        automatic.extend(rows)
        facets.append(dict(id=key,label=facet['label'],all_edges=len(rows),shown_at_limit_58=min(58,len(rows))))
    inputs=['docs/project_branches.mmd','docs/theory_branches.mmd','docs/source_imports.mmd','docs/audit/source_catalog.json','qml_algorithms_data.js','qml_interactive_graph.html','qml_relation_metrics.md']
    result={'prepared':'2026-09-23','audit_snapshot':'2026-09-22','counts':{k:len(v['edges']) for k,v in graphs.items()},'graphs':graphs,'relations':allrows,'automatic_relations':automatic,'facets':facets,'provenance':[{'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in inputs]}
    (OUT/'graph_relations.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    fields=[('id','ID'),('source_label','Od'),('target_label','Do'),('kind','Rodzaj'),('explanation','Znaczenie'),('limit','Granica interpretacji'),('evidence','Źródło')]
    write_md(OUT/'GRAPH_RELATIONS.md','Pełny katalog relacji mapy projektu i taksonomii',[r for r in allrows if r['layer'] in {'project','theory'}],fields)
    write_md(OUT/'CURATED_RELATIONS.md','Wszystkie relacje kuratorskie oryginalnego atlasu',curated,fields[:3]+[('weight','Waga kuratorska')]+fields[3:])
    write_md(OUT/'IMPORT_RELATIONS.md','Wszystkie krawędzie statycznego grafu importów',imports,fields)
    with (OUT/'similarity_relations.csv').open('w',encoding='utf-8-sig',newline='') as f:
        keys=['id','facet','source_label','target_label','shared_values','score','weight','rank','visible_at_default_limit_58']
        writer=csv.DictWriter(f,fieldnames=keys); writer.writeheader()
        for row in automatic: writer.writerow({k:'; '.join(row[k]) if isinstance(row[k],list) else row[k] for k in keys})
    manifest={'counts':result['counts'],'automatic_relations':len(automatic),'facets':facets,'atlas_nodes':len(labels),'import_nodes':len(nodes)}
    (OUT/'graph_counts.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__': main()
