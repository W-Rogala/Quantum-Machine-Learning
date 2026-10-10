"""Rebuild tables, paired exploratory intervals and scientific figures from CSVs."""
import os,tempfile
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'qml-matplotlib'))
import csv,json,hashlib
import numpy as np
from scipy.stats import t,ttest_1samp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from quantum_reservoir.spectral_h1_h2_study import save_csv

OUT=Path('analysis_output/qrc_h3_noise')
def read(name):
    with (OUT/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
_indices={}
def filt(rows,**kw):
    cache=_indices.setdefault(id(rows),{})
    selected=None
    for key,value in kw.items():
        if key not in cache:
            column={}
            for i,row in enumerate(rows):column.setdefault(str(row[key]),set()).add(i)
            cache[key]=column
        ids=cache[key].get(str(value),set())
        selected=ids.copy() if selected is None else selected.intersection(ids)
    return [rows[i] for i in sorted(selected)] if selected is not None else rows
def values(rows,column,**kw):
    return np.array([float(r[column]) for r in sorted(filt(rows,**kw),key=lambda r:int(r['block']))])
def interval(x):
    half=t.ppf(.975,len(x)-1)*np.std(x,ddof=1)/np.sqrt(len(x))
    return float(np.mean(x)),float(np.mean(x)-half),float(np.mean(x)+half)
def main():
    scores=read('scores.csv');profiles=read('profiles.csv');costs=read('costs.csv');checks=read('checks.csv')
    assert len(scores)==2592 and len(profiles)==51840
    keys=['block','case','noise','task','view','budget']
    assert len({tuple(r[k] for k in keys) for r in scores})==len(scores)
    for r in filt(scores,task='memory'):
        pp=filt(profiles,**{k:r[k] for k in keys})
        assert len(pp)==60
        for family in ('linear','product','quadratic'):
            assert abs(sum(float(p['capacity']) for p in pp if p['family']==family)-float(r[family+'20']))<1e-9
    contrasts=[]
    def contrast(name,x,y,ratio=False):
        assert len(x)==len(y)==8
        d=np.log(x/y) if ratio else x-y
        est,lo,hi=interval(d)
        if ratio:est,lo,hi=np.exp([est,lo,hi])
        contrasts.append(dict(contrast=name,estimate=est,ci_low=lo,ci_high=hi,p=float(ttest_1samp(d,0).pvalue),n=8,kind='ratio' if ratio else 'difference'))
    base=dict(case='coarse_BAB2',task='memory',view='full_Pauli')
    contrast('BAB full: finite shots minus ideal expectation',values(scores,'linear20',**base,noise='ideal',budget='equal_CX_budget'),values(scores,'linear20',**base,noise='ideal',budget='expectation'))
    contrast('BAB full: mild minus ideal at matched cost',values(scores,'linear20',**base,noise='mild',budget='equal_CX_budget'),values(scores,'linear20',**base,noise='ideal',budget='equal_CX_budget'))
    for task in ('NARMA10','MG5'):
        kw=dict(task=task,noise='mild',view='local_XZ_ZZ',budget='equal_CX_budget')
        contrast(f'{task}: ABA2 / ABA16 mild matched cost',values(scores,'nrmse',case='coarse_ABA2',**kw),values(scores,'nrmse',case='coarse_ABA16',**kw),True)
    ordered=sorted(range(len(contrasts)),key=lambda j:contrasts[j]['p']);prev=0.
    for rank,j in enumerate(ordered):
        prev=max(prev,min(1.,(len(ordered)-rank)*contrasts[j]['p']));contrasts[j]['p_holm']=prev
    save_csv(OUT/'paired_contrasts.csv',contrasts)
    text=['# H3: odporność na szum i niedoskonałości',
      '', '**Status:** wykonane symulacje macierzy gęstości i pomiarów; parametry syntetyczne, bez uruchomienia na fizycznym QPU. Osiem nowych bloków 500–507. Badanie eksploracyjne, odrębne od pierwotnego protokołu potwierdzającego H1–H5.',
      '', '## Model i kontrolowane warunki',
      '', 'Cztery kubity, ten sam model resetowanego rezerwuaru, losowania pól i danych w sparowanych porównaniach. Przypadki: τ=3.2 dla ABA r=2, BAB r=2 i ABA r=16 oraz τ=π/0.9 dla ABA r=2. Nie dobierano konfiguracji do testu. Ridge dobiera regularyzację wyłącznie na walidacji i następnie uczy się na train+validation. Pamięć: wejścia iid U[0,1], 20 opóźnień dla każdej z trzech rodzin ortogonalnych celów; predykcja: NARMA10 i Mackey–Glass z horyzontem 5.',
      '', 'Po pierwszym przebiegu eksploracyjnym rozszerzono siatkę ridge do α=10^12 (praktycznie predyktor stały) dla wszystkich warunków i powtórzono analizę. Poprzednia górna granica α=100 mogła wymuszać przeuczenie 255 zaszumionych cech. Wybór konkretnego α wykorzystuje wyłącznie walidację, ale zmiana protokołu po inspekcji wyników oznacza, że potrzebna jest niezależna replikacja potwierdzająca.',
      '', '| Parametr | mild | stress |', '|---|---:|---:|',
      '| Depolaryzacja po RX / CX | 0.0001 / 0.001 | 0.001 / 0.01 |',
      '| T1 / T2 [μs] | 100 / 80 | 50 / 40 |',
      '| Względny błąd kąta RX, RZ i kodowania wejścia | +0.5% | +2% |',
      '| Populacja wzbudzona po resecie | 1% | 3% |',
      '| Odczyt P(1 przy 0) / P(0 przy 1) | 1% / 2% | 3% / 5% |',
      '', 'Każde RZZ rozłożono na CX–RZ–CX. Przyjęto szeregowy harmonogram: RX 35 ns, CX 300 ns, RZ wirtualne, reset wejścia 1 μs. Wszystkie kubity podlegają relaksacji podczas RX/CX; pozostałe trzy także podczas resetu wejścia. Jest to jawne założenie harmonogramu, a nie skompilowany harmonogram urządzenia. Depolaryzacja i relaksacja są osobnymi składnikami, zatem p nie oznacza całkowitej infidelity bramki. Model resetu przygotowuje mieszaninę stanów 0/1 przed obrotem; nie opisuje nieudanego resetu zachowującego korelacje.',
      '', 'Kanał relaksacji ma zerową równowagową populację wzbudzoną, zachowuje ograniczenie T2≤2T1. Definicje kanałów: [Qiskit Aer thermal relaxation](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.thermal_relaxation_error.html) i [NoiseModel](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.noise.NoiseModel.html). Podane liczby nie są kalibracją IBM ani innego urządzenia.',
      '', '## Odczyt i koszt',
      '', '12 lokalnych cech X,Z,ZZ: 2 globalne ustawienia pomiaru; 66 cech jedno- i dwukubitowych: 9 ustawień (tablica ortogonalna nad GF(3)); 255 cech Pauliego: 81 ustawień. Każdy operator przypisany jest do jednego zgodnego ustawienia. Losowane są wspólne 4-bitowe wyniki, co zachowuje kowariancję estymatorów. Rotacje zmieniające bazę pomiaru są idealne; nie uwzględniono ich dodatkowych błędów.',
      '', 'Trzy warunki: granica nieskończonej liczby shots (z fizycznym i odczytowym szumem danego scenariusza), 4096 shots na każde ustawienie oraz wspólny budżet CX×shots równy 196608 na krok historii. Dla ostatniego shots=floor(196608/(liczba ustawień × CX na krok)). Limit ten porównuje koszt dwukubitowy, a nie pełny czas wykonania.',
      '', '| Obwód | CX/krok | shots/grupę: 12 cech | 66 cech | 255 cech |', '|---|---:|---:|---:|---:|']
    for case in ('coarse_ABA2','coarse_BAB2','coarse_ABA16'):
        rr=filt(costs,block=500,case=case,noise='ideal',budget='equal_CX_budget')
        v={r['view']:r for r in rr}
        text.append(f"| {case} | {rr[0]['cx_per_step']} | {v['local_XZ_ZZ']['shots_per_group']} | {v['all_1_2body']['shots_per_group']} | {v['full_Pauli']['shots_per_group']} |")
    replay=int(filt(costs,block=500,case='coarse_ABA2',noise='ideal',view='local_XZ_ZZ',budget='equal_CX_budget')[0]['full_replay_CX_shots'])
    text+=['',f'Pełne odtwarzanie historii długości do 1360 daje {replay:,} CX×shots dla jednego takiego zbioru i obwodu ABA2 z lokalnym odczytem. Koszt obejmuje także washout i luki. Sam czas tych bramek przy 300 ns wynosi {replay*.3e-6/3600:.1f} h, bez resetów, pomiarów, kolejki i komunikacji. Symulator propaguje kanał tylko raz i próbkuje końcowe rozkłady, więc nie ponosi fizycznie tego kosztu.',
      '', 'Interpretacja sprzętowa zakłada oddzielne przygotowanie pełnego prefiksu przed każdym pomiarem. Nie zakłada bezinwazyjnego pomiaru jednego stanu. Skrócenie replay do okna W lub przejście na pomiary słabe wymaga osobnego testu pamięci i back-action. Kontekst: [Time-series QRC with weak and projective measurements](https://arxiv.org/abs/2205.06809).',
      '', '## Wyniki pamięci',
      '', 'Średnia suma C_L(d), d=1,…,20; wartości ujemne zachowano jako błąd generalizacji poniżej predyktora stałego. Nie są ujemną ilością informacji. „Ideal ∞” oznacza idealne kanały i dokładne oczekiwania; pozostałe kolumny używają wspólnego budżetu CX×shots.',
      '', '| Obwód / odczyt | Ideal ∞ | Ideal + shots | mild + shots | stress + shots |', '|---|---:|---:|---:|---:|']
    for case in ('coarse_ABA2','coarse_BAB2','coarse_ABA16','resonance_ABA2'):
        for view in ('local_XZ_ZZ','all_1_2body','full_Pauli'):
            kw=dict(case=case,task='memory',view=view)
            vals=[np.mean(values(scores,'linear20',**kw,noise=n,budget=b)) for n,b in [('ideal','expectation'),('ideal','equal_CX_budget'),('mild','equal_CX_budget'),('stress','equal_CX_budget')]]
            text.append('| '+case+' / '+view+' | '+' | '.join(f'{x:.3f}' for x in vals)+' |')
    text+=['', '## Sparowane porównania',
      '', 'Przedziały t 95% liczone po ośmiu niezależnych blokach; dla ilorazów na skali logarytmicznej. P-wartości skorygowano metodą Holma w rodzinie czterech pokazanych kontrastów. Przedziały są marginalne, nie jednoczesne. Jedna realizacja pomiarów na blok; powtórzenia shots ani punkty czasu nie są dodatkowymi niezależnymi próbami. Są to testy eksploracyjne, bez deklaracji mocy lub rozstrzygnięcia wszystkich H1–H5.',
      '', '| Kontrast | Estymata | 95% CI | p Holm |', '|---|---:|---|---:|']
    for c in contrasts:text.append(f"| {c['contrast']} | {c['estimate']:.3f} | [{c['ci_low']:.3f}, {c['ci_high']:.3f}] | {c['p_holm']:.3g} |")
    text+=['', '## Rozdzielenie składowych pamięci',
      '', 'Pełne 60-elementowe profile zapisano w profiles.csv, osobno dla liniowych opóźnień, produktów sąsiednich opóźnień i ortogonalnych celów kwadratowych. Nie wnioskujemy o korzystnym kompromisie na podstawie samej różnicy pojemności. Poniższy wykres pokazuje średnie BAB2 przy τ=3.2, wraz z niekorygowanymi punktowymi przedziałami t 95%.',
      '', '![Profile pamięci](noise_memory_profiles.png)',
      '', '## Rezonans, rozróżnialność stanów i dryf']
    diag=read('noise_ablation_impulses.csv');drift=read('calibration_drift.csv')
    text+=['', 'Dwie historie różnią się wyłącznie jednym wejściem 0.2/0.8 po 220 krokach washout. Następnie wejścia są identyczne. D=||ρa−ρb||1/2 porównano z max|Δ〈O〉|/2 dla tych samych czterech kubitów. Ablacje izolują depolaryzację, relaksację, błąd kąta i reset; szum samego odczytu nie zmienia stanu. Poniżej średnie D po pięciu kolejnych wejściach.',
      '', '| Składnik | τ−π/g = −0.075 | 0 | +0.075 |', '|---|---:|---:|---:|']
    for noise in ('ideal','depolarization_only','thermal_only','coherent_only','reset_only','combined_mild'):
        nums=[np.mean(values(diag,'trace_distance',noise=noise,offset=off,delay=5)) for off in (-.075,0.,.075)]
        text.append('| '+noise+' | '+' | '.join(f'{v:.3g}' for v in nums)+' |')
    text+=['', 'Trzy punkty są kontrolą sąsiedztwa rezonansu, nie dowodem szerokości ciągłego przedziału. Ewentualne zwiększenie D przez perturbację nie oznacza jeszcze poprawy predykcji ani przewagi kwantowej.',
      '', 'Dodatkowo w BAB2 zmieniono kalibrację wyłącznie dla obwodów testowych: błąd kąta +0.5%→+1.5%, odczyt 1%/2%→2.5%/4%. Każdy testowy replay podlega w całości nowej kalibracji. Readout i regularyzacja pozostają zamrożone. Kontrola bez dryfu używa tego samego modelu; niezależne losowania pomiarów dodają wariancję kontrastu.',
      '', '| Zadanie / odczyt | NRMSE dryf / stabilne | 95% CI |', '|---|---:|---|']
    for task in ('NARMA10','MG5'):
        for view in ('local_XZ_ZZ','all_1_2body','full_Pauli'):
            a=values(drift,'nrmse',task=task,view=view,scenario='calibration_shift');b=values(drift,'nrmse',task=task,view=view,scenario='stable')
            est,lo,hi=np.exp(interval(np.log(a/b)))
            text.append(f'| {task} / {view} | {est:.3f} | [{lo:.3f}, {hi:.3f}] |')
    text+=['', 'Przedziały dryfu są opisowe, bez korekty wielokrotnych porównań. Test obejmuje jedną narzuconą zmianę parametrów, nie rozkład rzeczywistych dryfów.',
      '', '## Granice wnioskowania i następny eksperyment',
      '', 'Szum zachowujący mieszanie, relaksacja i błąd koherentny działają inaczej: mogą tłumić pamięć, zmieniać stan stacjonarny albo przesuwać rezonans. Nie wystarczy jedna oś „poziomu szumu”. Dyskretne widmo superoperatora dla czterech kubitów dotyczy skończonego modelu; ten eksperyment nie bada ciągłego widma układów CV.',
      '', 'Nie uwzględniono leakage, crosstalk, błędów zależnych od historii, routingu i kalibrowanych błędów baz pomiarowych. Brakuje ponownego wyboru Trottera i dostrojonego exact pod tym samym szumem oraz kontrolowanego okna W. Wnioski nie rozstrzygają przewagi nad dostrojonym exact ani klasycznym rezerwuarem.',
      '', 'Następny etap sprzętowy: wybór backendu i kalibracji, kompilacja ABA/BAB do tego samego zestawu fizycznych kubitów, model oparty na jego bramkach i harmonogramie, skan W=8/16/32 z kontrolą obciętej pamięci, następnie naprzemienne wykonania metod w blokach kalibracyjnych. Koszt raportować jednocześnie jako CX×shots, reset/measurement counts i czas. Mitigację odczytu ocenić na osobnych danych kalibracyjnych, łącznie z narzutem i wzrostem wariancji.',
      '', '## Weryfikacja i odtwarzanie',
      '', f"Zapisano {len(scores)} wyników agregowanych i {len(profiles)} składowych profili. Maksymalna różnica względem wcześniejszej idealnej ewolucji: {max(float(r['ideal_error']) for r in checks):.2g}; maksymalny błąd śladu: {max(float(r['trace_error']) for r in checks):.2g}. Kontrole obejmują CPTP, zgodność obu splittingów, pomiary wszystkich operatorów i korelacje wyników stanu Bella.",
      '', '```powershell',
      '.venv_qml/Scripts/python.exe -m quantum_reservoir.h3_noise_study --blocks 8',
      '.venv_qml/Scripts/python.exe -m quantum_reservoir.h3_noise_diagnostics',
      '.venv_qml/Scripts/python.exe -m quantum_reservoir.h3_noise_report',
      '.venv_qml/Scripts/python.exe -m unittest tests.test_h3_noise_study tests.test_h3_memory_study',
      '```']
    plt.rcParams.update({'font.size':10})
    fig,axs=plt.subplots(3,3,figsize=(14,10),sharex=True,constrained_layout=True)
    for row,fam in enumerate(('linear','product','quadratic')):
        for col,view in enumerate(('local_XZ_ZZ','all_1_2body','full_Pauli')):
            ax=axs[row,col]
            for noise,budget,label,color in [('ideal','expectation','Ideal expectations','#34495e'),('ideal','equal_CX_budget','Shots only','#2980b9'),('mild','equal_CX_budget','Mild + shots','#d35400'),('stress','equal_CX_budget','Stress + shots','#8e44ad')]:
                ci=np.array([interval(values(profiles,'capacity',case='coarse_BAB2',noise=noise,budget=budget,view=view,family=fam,delay=d)) for d in range(1,21)])
                ax.plot(range(1,21),ci[:,0],color=color,label=label);ax.fill_between(range(1,21),ci[:,1],ci[:,2],color=color,alpha=.10)
            ax.axhline(0,c='gray',lw=.6);ax.set_title(view if row==0 else '')
            if col==0:ax.set_ylabel(f'{fam}: capacity')
            if row==2:ax.set_xlabel('Delay d')
    axs[0,0].legend(fontsize=8);fig.suptitle('BAB r=2, tau=3.2: separate memory profiles; 8 paired blocks\nFinite measurements at equal CX-shot budget; pointwise 95% t intervals')
    fig.savefig(OUT/'noise_memory_profiles.png',dpi=170);fig.savefig(OUT/'noise_memory_profiles.svg');plt.close(fig)
    (OUT/'RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    sources=['quantum_reservoir/h3_memory_study.py','quantum_reservoir/h3_noise_study.py',
             'quantum_reservoir/h3_noise_diagnostics.py','quantum_reservoir/h3_noise_report.py',
             'quantum_reservoir/core.py','quantum_reservoir/spectral_h1_h2_study.py','tests/test_h3_noise_study.py']
    (OUT/'source_hashes.json').write_text(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources},indent=2),encoding='utf-8')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='artifact_hashes.json'}
    (OUT/'artifact_hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    print(json.dumps(contrasts,indent=2));print('Report and figure verified against CSVs.')

if __name__=='__main__':main()
