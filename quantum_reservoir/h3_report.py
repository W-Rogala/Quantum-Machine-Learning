"""Recompute aggregates and produce static H3 figures/report from saved data."""
import os
import tempfile
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR",str(Path(tempfile.gettempdir())/"qml-matplotlib"))
import csv
import json
import hashlib
import numpy as np
from scipy.stats import t,spearmanr,ttest_1samp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from quantum_reservoir.spectral_h1_h2_study import save_csv

ROOT=Path("analysis_output/qrc_h3_memory")

def read(name):
    with (ROOT/name).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))

def table(headers,rows):
    return "| "+" | ".join(headers)+" |\n|"+"|".join(["---"]*len(headers))+"|\n"+"\n".join("| "+" | ".join(map(str,r))+" |" for r in rows)+"\n"

def ci(values):
    v=np.asarray(values,dtype=float);m=v.mean();h=t.ppf(.975,len(v)-1)*v.std(ddof=1)/np.sqrt(len(v))
    return float(m),float(m-h),float(m+h)

def mean(rows,key):return float(np.mean([float(r[key]) for r in rows]))

def select(rows,**kwargs):return [r for r in rows if all(str(r[k])==str(v) for k,v in kwargs.items())]

def main():
    manifest=json.loads((ROOT/"manifest.json").read_text())
    assert manifest["status"]=="complete" and manifest["n_total"]==4
    prof=read("profiles.csv");sums=read("profile_summaries.csv");channel=read("channels.csv")
    structure=read("channel_structure.csv");imp=read("impulses.csv")
    pred=read("predictions.csv");selections=read("selections.csv");readouts=read("readout_predictions.csv")
    assert len(channel)==len(structure),"Structure must cover the completed scan"
    assert len(readouts)==432
    # Check complete target sets, source sums and unique rows.
    keys=[tuple(r[k] for k in ("phase","regime","block","method","view","target","delay")) for r in prof]
    assert len(set(keys))==len(keys)
    grouped={}
    for r in prof:
        key=tuple(r[k] for k in ("phase","regime","block","method","view"))
        grouped.setdefault(key,[]).append(r)
    for s in sums:
        key=tuple(s[k] for k in ("phase","regime","block","method","view"));rr=grouped[key]
        assert len(rr)==60
        for family in ("linear","product","quadratic"):
            value=sum(float(r["capacity"]) for r in rr if r["target"]==family)
            assert abs(value-float(s[family+"20"]))<1e-9
    # Frozen-selection baseline predictions match independent original helper path.
    for p in pred:
        r=select(readouts,regime=p["regime"],block=p["block"],task=p["task"],family=p["family"],view="local_XZ_ZZ")[0]
        assert abs(float(p["nrmse"])-float(r["nrmse"]))<1e-8
    lines=["# H3: pamięć, odczyt i otoczenie rezonansu\n\nData: 7 września 2026 r.\n",
        "**Wykonane badanie eksploracyjne, nie pełna próba potwierdzająca H3.** "
        "Wszystkie modele mają 4 kubity. Główna seria: 8 nowych sparowanych bloków 300–307, "
        "trzy reżimy (tau=0.8, tau=3.2, tau=pi/0.9). Skan: 11 przesunięć czasu × 4 kolejne bloki 400–403 × 5 schematów. "
        "Odczyty: 12 lokalnych cech X/Z/ZZ; 66 obserwabli Pauliego wagi <=2; 255 nieidentycznościowych obserwabli Pauliego. "
        "Pełny odczyt jest idealizowaną diagnostyką o wykładniczym koszcie, nie propozycją efektywnego hardware'u.\n",
        f"Zapisano {len(prof)} wyników rekonstrukcji celów, {len(channel)} diagnostyk kanału, "
        f"{len(imp)} ocen par historii i {len(readouts)} ocen predykcji po zmianie odczytu. "
        "Wybory konfiguracji pochodzą wyłącznie z walidacji. Nie uruchomiono fizycznego QPU.\n",
        "## 1. Profile pamięci — składowe osobno\n",
        "Cele: liniowe v_(t-d), iloczynowe v_(t-d)v_(t-d-1), kwadratowe sqrt(5) P2(2u_(t-d)-1), "
        "dla d=1,...,20, v=sqrt(3)(2u-1), wejścia iid U[0,1]. Maksymalne opóźnienie użyte w iloczynie to 21. "
        "C=1-NRMSE²; ujemne wyniki zachowano. Sumy są zdolnością rekonstrukcji przy danym readoucie, "
        "nie pełną information processing capacity ani ilością kubitów pamięci.\n"]
    coretable=[]
    for regime in ("standard","coarse","resonance"):
        for method in ("fixed_exact","AB_r1","ABA_r2","BAB_r2"):
            rr=select(sums,phase="core",regime=regime,method=method,view="local_XZ_ZZ")
            coretable.append([regime,method,*[f"{mean(rr,k):.3f}" for k in ("linear20","product20","quadratic20")]])
    lines.append(table(["Reżim","Schemat","Suma liniowa","Suma iloczynowa","Suma kwadratowa"],coretable))
    lines.append("### Kontrast H3 z zachowaną definicją\n")
    h3=[]
    for regime in ("standard","coarse","resonance"):
        delta=[]
        for b in range(300,308):
            a=select(sums,phase="core",regime=regime,block=b,method="AB_r1",view="local_XZ_ZZ")[0]
            ref=select(sums,phase="core",regime=regime,block=b,method="fixed_exact",view="local_XZ_ZZ")[0]
            delta.append(float(a["T"])-float(ref["T"]))
        m,lo,hi=ci(delta);pv=float(ttest_1samp(delta,0).pvalue)
        h3.append({"regime":regime,"delta_T":m,"ci95_low":lo,"ci95_high":hi,"p_raw":pv})
    running=0
    for rank,j in enumerate(sorted(range(3),key=lambda j:h3[j]["p_raw"])):
        running=max(running,min(1.,(3-rank)*h3[j]["p_raw"]));h3[j]["p_holm_3_regimes"]=running
    save_csv(ROOT/"h3_contrasts.csv",h3)
    lines.append(table(["Reżim","Delta T","95% CI t","p Holm, eksploracyjne"],[[r["regime"],f'{r["delta_T"]:.4f}',f'[{r["ci95_low"]:.4f}, {r["ci95_high"]:.4f}]',f'{r["p_holm_3_regimes"]:.4g}'] for r in h3]))
    lines.append("T=(suma C_product(d=1..10)-suma C_linear(d=1..10))/10. "
        "Dodatnia delta T nie oznacza poprawy nieliniowości: może powstać głównie przez utratę pamięci liniowej. "
        "Pierwotny H3 dotyczy standardowego reżimu; dodatkowe reżimy i ich korekta stanowią odrębną analizę eksploracyjną. "
        "Nie używamy tych p-values jako potwierdzenia pierwotnego protokołu 20 bloków.\n")
    lines.append("## 2. Informacja w stanie a dostępność odczytu\n")
    viewtable=[]
    for regime in ("standard","coarse","resonance"):
        for method in ("fixed_exact","AB_r1","ABA_r2","BAB_r2"):
            row=[regime,method]
            for view in ("local_XZ_ZZ","all_1_2body","full_Pauli"):
                rr=select(sums,phase="core",regime=regime,method=method,view=view)
                row.append(f"{mean(rr,'linear20'):.3f}")
            viewtable.append(row)
    lines.append(table(["Reżim","Schemat","L20: lokalny","L20: waga<=2","L20: pełny"],viewtable))
    lines.append("Pełna baza zawiera lokalną, ale testowa jakość dopasowanego ridge nie musi rosnąć: "
        "więcej cech zwiększa wariancję, zmienia regularizację i może pogarszać generalizację. "
        "Różnica wyników nie jest czystą miarą kwantowej informacji. Pełne oczekiwania opisują stan, "
        "natomiast liniowy readout nadal nie obejmuje wszystkich dekoderów.\n")
    statetable=[]
    for regime in ("standard","coarse","resonance"):
        for method in ("fixed_exact","AB_r1","ABA_r2","BAB_r2"):
            rr=select(imp,phase="core",regime=regime,method=method,delay=5)
            st=select(structure,phase="core",regime=regime,method=method)
            statetable.append([regime,method,f"{mean(rr,'trace_distance'):.3g}",f"{mean(rr,'local_observable_lower_bound'):.3g}",
                f"{mean(st,'unitality_defect_u05'):.3g}",f"{mean(st,'subradius'):.4f}"])
    lines.append(table(["Reżim","Schemat","D stanu, d=5","Dolna granica lokalna, d=5","Defekt unitalności","rho resztowe, u=0.5"],statetable))
    lines.append("Pary historii różnią się jednym wejściem 0.2 vs 0.8 po 220 wspólnych krokach; późniejsze wejścia są identyczne. "
        "D=||rho_a-rho_b||_1/2 określa optymalną rozróżnialność tej pary. Lokalna dolna granica to max_j |Delta<O_j>|/2. "
        "D>0 dowodzi zachowania śladu dla tej pary, nie zdolności rekonstrukcji wszystkich wejść. "
        "D bliskie zeru dotyczy badanych historii; poza przypadkami analitycznymi nie jest dowodem uniwersalnej utraty informacji. "
        "Plik impulses.csv zawiera również udział rzutu Hilberta–Schmidta na lokalne obserwable; nie nazywamy go procentem dostępnej informacji.\n")
    lines.append("### Wyjaśnienie strukturalne: jednokrokowy AB/BA\n\n"
        "Przy jednym diagonalnym bloku A na wejście i lokalnym bloku B, zredukowany kanał pamięci jest mieszaniną "
        "sprzężeń unitarnych: T_u(sigma)=sum_z p_z(u) V_z sigma V_z†. Jest unitalny i ma wspólny stan stały I/8, "
        "niezależny od u. Jeśli sekwencja kanałów miesza do tego stanu, pamięć dawnych wejść zanika także dla pełnego odczytu. "
        "AB i BA różnią się wagami oraz kolejnością unitarnych operacji, ale obie konstrukcje mają tę własność dla r=1. "
        "Samą unitalność sprawdzono numerycznie; zbieżności dla wszystkich sekwencji wejść nie dowiedziono. "
        "Wynik wskazuje ograniczenie architektury, a nie jedynie brak odpowiednich obserwabli.\n")
    lines.append("Kanał jest liczony dla tego samego fizycznego układu n=4. Użyta macierz 64×64 działa na "
        "operatorach trzykubitowej pamięci po wyeliminowaniu resetowanego wejścia. Jej niezerowe widmo zgadza się "
        "z niezerowym widmem pełnego kanału 256×256; sprawdzono to osobnym testem. "
        "To redukcja reprezentacji tego samego układu, nie mieszanie wyników n=3 i n=4. "
        "Widmo przy u=0.5 pozostaje diagnostyką zamrożonego wejścia, nie certyfikatem ESP przy przełączaniu.\n")
    lines.append("## 3. Otoczenie rezonansu\n")
    offsets=sorted({float(r["regime"]) for r in sums if r["phase"]=="sweep"})
    methods=("exact_r1","AB_r1","BA_r1","ABA_r2","BAB_r2")
    sweep=[]
    for off in offsets:
        row=[f"{off:+.3f}"]
        for method in methods:
            rr=select(sums,phase="sweep",regime=off,method=method,view="local_XZ_ZZ")
            row.append(f"{mean(rr,'linear20'):.3f}")
        sweep.append(row)
    lines.append(table(["tau-pi/g",*methods],sweep))
    lines.append("Tabela: średnia suma liniowej rekonstrukcji d=1..20, 4 sparowane bloki, nieskończone idealne shots. "
        "Nie wyznaczamy ciągłej szerokości pasma na podstawie rzadkiej siatki; podajemy punkty próbkowane. "
        "AB oznacza chronologicznie A, potem B; macierzowo U_B U_A. ABA/BAB są symetrycznymi formułami z r=2. "
        "Zmiana kolejności zachowuje n,tau,r i dane, ale ABA/BAB nie muszą mieć identycznego kosztu sprzętowego "
        "(blok A zawiera bramki 2Q, B tylko lokalne).\n")
    lines.append("## 4. Powiązanie z predykcją na nowych blokach\n")
    ratios=[]
    for regime in ("standard","coarse","resonance"):
        for task in ("NARMA10","MG5"):
            for ref in ("fixed_exact","tuned_exact"):
                effects=[]
                for b in range(300,308):
                    a=select(pred,regime=regime,block=b,task=task,family="selected_trotter")[0]
                    r=select(pred,regime=regime,block=b,task=task,family=ref)[0]
                    effects.append(np.log(float(a["nrmse"])/float(r["nrmse"])))
                m,lo,hi=np.exp(ci(effects));ratios.append([regime,task,ref,f"{m:.3f}",f"[{lo:.3f}, {hi:.3f}]"])
    lines.append(table(["Reżim","Zadanie","Odniesienie","Iloraz NRMSE","95% CI t"],ratios))
    lines.append("Wybrany Trotter: AB/ABA × r=1,2,4,8. Dostrojone exact: tau=0.4,0.8,1.6,3.2 × g=0.6,0.9. "
        "Obie rodziny mają po 8 konfiguracji, ale równa liczba kandydatów nie wyrównuje kosztu fizycznego. "
        "Dynamika została wybrana przy lokalnym odczycie. Następnie, bez ponownego wyboru dynamiki, "
        "sprawdzono bogatsze readouty z alpha dobieranym wyłącznie na validation.\n")
    rtable=[]
    for regime in ("standard","coarse","resonance"):
        for task in ("NARMA10","MG5"):
            row=[regime,task]
            for view in ("local_XZ_ZZ","all_1_2body","full_Pauli"):
                rr=select(readouts,regime=regime,task=task,family="selected_trotter",view=view)
                row.append(f"{mean(rr,'nrmse'):.4f}")
            rtable.append(row)
    lines.append(table(["Reżim","Zadanie","Lokalny NRMSE","Waga<=2 NRMSE","Pełny NRMSE"],rtable))
    correlations=[]
    for regime in ("standard","coarse","resonance"):
        for task in ("NARMA10","MG5"):
            for metric in ("linear20","product20","quadratic20"):
                dx=[];dy=[]
                for b in range(300,308):
                    chosen=select(selections,regime=regime,block=b,task=task,family="selected_trotter")[0]["configuration"]
                    a=select(sums,phase="core",regime=regime,block=b,method=chosen,view="local_XZ_ZZ")[0]
                    r=select(sums,phase="core",regime=regime,block=b,method="fixed_exact",view="local_XZ_ZZ")[0]
                    pa=select(pred,regime=regime,block=b,task=task,family="selected_trotter")[0]
                    pr=select(pred,regime=regime,block=b,task=task,family="fixed_exact")[0]
                    dx.append(float(a[metric])-float(r[metric]));dy.append(np.log(float(pa["nrmse"])/float(pr["nrmse"])))
                rho=float(spearmanr(dx,dy).statistic)
                correlations.append({"regime":regime,"task":task,"metric":metric,"blocks":8,"spearman_rho":rho})
    save_csv(ROOT/"memory_prediction_correlations.csv",correlations)
    lines.append(table(["Reżim","Zadanie","Zmiana profilu","Spearman rho"],[[r["regime"],r["task"],r["metric"],f'{r["spearman_rho"]:.3f}'] for r in correlations]))
    lines.append("Korelacje dotyczą sparowanych zmian wobec exact, osobno dla reżimu i zadania, n=8. "
        "Nie raportujemy ich jako dowodu mediacji ani niezależnych potwierdzających testów. "
        "Diagnostyka pamięci używa strumienia iid, a MG innego rozkładu wejść; to kolejny powód ostrożnej interpretacji.\n")
    lines.append("### Kontrola długiej rozgrzewki i stanu stałego\n")
    warm=read("washout_sensitivity.csv");stationary=read("stationary_AB_check.csv")
    assert len(warm)==192 and len(stationary)==16
    wtable=[]
    for case in ("standard_exact","standard_AB","coarse_ABA","coarse_BAB"):
        row=[case]
        for extra in (0,2000,10000):
            rr=select(warm,case=case,extra_warmup=extra,view="full_Pauli")
            row.append(f"{mean(rr,'linear20'):.3f}")
        wtable.append(row)
    lines.append(table(["Model","L20: dodatkowe 0","L20: dodatkowe 2000","L20: dodatkowe 10000"],wtable))
    lines.append("Kontrola post hoc używa tego samego ocenianego strumienia i tych samych celów, "
        "poprzedzonych dodatkowym prefiksem iid. Jest analizą wrażliwości, nie zmianą głównego eksperymentu. "
        "Wynik BAB przy tau=3.2 utrzymuje się po długiej rozgrzewce. W AB długi prefiks nie usuwa wszystkich "
        "rekonstruowalnych śladów: bardzo wolne mody i odczyt idealnych małych sygnałów wymagają dodatkowej kontroli.\n")
    lines.append(f"Po inicjalizacji pamięci AB bezpośrednio w I/8 maksymalne odchylenie od I/8 w całej serii "
        f"wynosi {max(float(r['max_distance_memory_from_I8']) for r in stationary):.3g}. "
        f"Średnia suma liniowej rekonstrukcji pełnego readoutu wynosi {mean(select(stationary,view='full_Pauli'),'linear20'):.3f}. "
        "To zgodne z analitycznym brakiem zapisu historii w tym stanie. Pozostałą pamięć z czystej inicjalizacji "
        "należy więc opisywać jako zależną od inicjalizacji, a nie udowodnioną stacjonarną zdolność AB. "
        "Standaryzacja i idealne oczekiwania mogą wykorzystywać bardzo małe sygnały; finite shots mogą je usunąć.\n")
    lines.append("### Interpretacja końcowa\n\n"
        "1. **H3 wykrywa zmianę, nie automatycznie korzystny kompromis.** Dodatnia delta T dla AB_r1 "
        "wynika głównie z utraty pamięci liniowej; profile iloczynowe również nie poprawiają się.\n"
        "2. **Odczyt bywa istotnym ograniczeniem.** W standardowym exact suma liniowa rośnie z około 3.0 "
        "dla 12 cech do 6.7 dla pełnej bazy. Jest to efekt idealnego bogatszego odczytu, nie bezkosztowa korzyść sprzętowa.\n"
        "3. **Rezonans niszczy ślad, a jego otoczenie pogarsza dostępność odczytu.** W samym punkcie "
        "nie pomaga pełna baza; w pobliżu część pamięci pozostaje widoczna dla bogatszego readoutu. "
        "Nie utożsamiamy całej doliny predykcyjnej z całkowitą utratą informacji kwantowej.\n"
        "4. **Kolejność ABA/BAB jest obiecującym parametrem projektu.** Przy tau=3.2 ABA daje średnio "
        "mniejszą sumę liniową (2.188 vs 2.691 exact) i większą iloczynową (0.800 vs 0.444). "
        "Są to kierunki średnich, nie dowód obu przeciwnych efektów po korekcie wielokrotności. "
        "BAB z pełnym odczytem daje 9.253 wobec 5.934 exact w liniowej rekonstrukcji i zachowuje ten efekt "
        "w kontroli długiej rozgrzewki. BAB nie należał do selektora predykcji — jego przewaga w prognozowaniu pozostaje otwarta.\n"
        "5. **Brak jednolitej zależności ‘więcej pamięci = mniejszy NRMSE’.** Korelacje zmieniają znak "
        "między zadaniami. Korzyści wybranego Trottera wobec fixed exact słabną wobec tuned exact. "
        "Najbardziej uzasadniony następny eksperyment to ograniczony odczyt i skończone shots (H4), "
        "z BAB jako z góry dodanym kandydatem oraz kontrolą kosztu.\n")
    lines.append("## 5. Wykonanie, kontrola jakości i ograniczenia\n")
    lines.append("Nowe seedy danych i pól są rozłączne z poprzednią serią H1/H2. Chronologia: 200 washout, "
        "600 train, 5 przerwy, 250 validation, 5 przerwy, 300 test. Jest to skrócona próba eksploracyjna, "
        "a nie zamrożony wcześniej protokół. Skalowanie MG dopasowano wyłącznie na train. "
        "Utrzymywany stan przechodzi przez granice segmentów jako część jednego strumienia. "
        "Testy nie są traktowane jako niezależne próbki czasowe; agregacja i CI używają bloków.\n")
    lines.append("6 nowych testów sprawdziło zgodność cech z istniejącym modułem, równoważność spektralną redukcji kanału, "
        "przypadek rezonansowy, ridge względem bezpośredniego rozwiązania, przyczynowość celów i brak wpływu testu na selekcję. "
        "Raport dodatkowo sprawdza unikalność i kompletność 60 celów każdej konfiguracji, przelicza sumy oraz "
        "kontroluje zgodność lokalnych predykcji w niezależnej ablacji readoutu. "
        "Wyniki nie zawierają szumu sprzętowego, finite shots, porównania z nowymi klasycznymi baseline'ami ani wykonania QPU.\n")
    lines.append("## 6. Wykresy\n\n![Profile pamięci](memory_profiles.png)\n\n![Skan rezonansu](resonance_scan.png)\n\n![Ślad w stanie i odczyt](state_vs_readout.png)\n")
    (ROOT/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")

    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.spines.top":False,"axes.spines.right":False})
    colors={"fixed_exact":"#333333","AB_r1":"#AD7624","ABA_r2":"#275D8C","BAB_r2":"#B85C83"}
    styles={"fixed_exact":"-","AB_r1":":","ABA_r2":"--","BAB_r2":"-."}
    fig,axes=plt.subplots(3,3,figsize=(13,9),layout="constrained",sharex=True)
    for i,regime in enumerate(("standard","coarse","resonance")):
        for j,target in enumerate(("linear","product","quadratic")):
            ax=axes[i,j]
            for method in colors:
                rr=select(prof,phase="core",regime=regime,method=method,view="local_XZ_ZZ",target=target)
                ys=[mean(select(rr,delay=d),"capacity") for d in range(1,21)]
                ax.plot(range(1,21),ys,label=method,color=colors[method],ls=styles[method],lw=1.5)
            ax.axhline(0,color="#999999",lw=.7);ax.set_title(f"{regime} · {target}");ax.grid(alpha=.15)
            if i==2:ax.set_xlabel("Opóźnienie d")
            if j==0:ax.set_ylabel("C = 1 − NRMSE²")
            ax.set_xticks([1,5,10,15,20])
    axes[0,0].legend(fontsize=8)
    fig.suptitle("QRC: profile rekonstrukcji historii\n4 kubity; lokalny odczyt; średnie z 8 bloków; analiza eksploracyjna",fontsize=13)
    fig.savefig(ROOT/"memory_profiles.png",dpi=180);fig.savefig(ROOT/"memory_profiles.svg");plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout="constrained")
    sweep_colors={"exact_r1":"#333333","AB_r1":"#AD7624","BA_r1":"#757E37","ABA_r2":"#275D8C","BAB_r2":"#B85C83"}
    sweep_styles={"exact_r1":"-","AB_r1":":","BA_r1":"--","ABA_r2":"-","BAB_r2":"-."}
    for ax,view in zip(axes,("local_XZ_ZZ","full_Pauli")):
        for method in methods:
            yy=[mean(select(sums,phase="sweep",regime=off,method=method,view=view),"linear20") for off in offsets]
            ax.plot(offsets,yy,marker="o",ms=3,label=method,color=sweep_colors[method],ls=sweep_styles[method])
        ax.axvline(0,color="#999999",lw=.8);ax.axhline(0,color="#999999",lw=.7)
        ax.set_xlabel("τ − π/g");ax.set_ylabel("Suma C liniowego, d=1…20");ax.set_title(view);ax.grid(alpha=.15)
    axes[1].legend(fontsize=8)
    fig.suptitle("QRC: otoczenie rezonansu i kolejność operacji\n4 kubity; 11 punktów czasu; średnie z 4 sparowanych bloków",fontsize=12)
    fig.savefig(ROOT/"resonance_scan.png",dpi=180);fig.savefig(ROOT/"resonance_scan.svg");plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4.6),layout="constrained")
    for ax,regime in zip(axes,("standard","coarse","resonance")):
        for method in ("fixed_exact","ABA_r2"):
            rr=select(imp,phase="core",regime=regime,method=method)
            for key,style in (("trace_distance","-"),("local_observable_lower_bound","--")):
                ys=[max(mean(select(rr,delay=d),key),1e-16) for d in range(1,21)]
                ax.plot(range(1,21),ys,color=colors[method],ls=style,label=f"{method}: {'stan' if style=='-' else 'lokalny'}")
        ax.set_yscale("log");ax.set_title(regime);ax.set_xlabel("Opóźnienie d");ax.set_ylabel("Rozróżnialność pary wejść");ax.grid(alpha=.15)
    axes[0].legend(fontsize=7)
    fig.suptitle("QRC: ślad wejścia w stanie i lokalnych obserwablach\n8 bloków × 4 pary historii; dolna granica lokalna; wartości <1e−16 pokazane na 1e−16",fontsize=12)
    fig.savefig(ROOT/"state_vs_readout.png",dpi=180);fig.savefig(ROOT/"state_vs_readout.svg");plt.close(fig)
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.name!="artifact_hashes.json"}
    artifacts["report_source"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (ROOT/"artifact_hashes.json").write_text(json.dumps(artifacts,indent=2),encoding="utf-8")
    print("H3:",h3);print("Profiles:",coretable);print("Views:",viewtable);print("State:",statetable);print("Sweep:",sweep)

if __name__=="__main__":main()
