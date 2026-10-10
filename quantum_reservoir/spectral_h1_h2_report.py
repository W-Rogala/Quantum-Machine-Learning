"""Summarize saved exploratory data; reproducible static research figures."""
from pathlib import Path
import os
import tempfile
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir())/"qml-matplotlib"))
import csv
import json
import hashlib
import numpy as np
from scipy.stats import t
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path("analysis_output/qrc_spectral_h1_h2")

def read(name):
    with (ROOT/name).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))

def interval(values):
    a=np.asarray(values);mean=a.mean();se=a.std(ddof=1)/np.sqrt(len(a))
    return np.exp([mean,mean-t.ppf(.975,len(a)-1)*se,mean+t.ppf(.975,len(a)-1)*se])

def table(headers,rows):
    return "| "+" | ".join(headers)+" |\n|"+"|".join(["---"]*len(headers))+"|\n"+"\n".join("| "+" | ".join(map(str,row))+" |" for row in rows)+"\n"

def main():
    mainrows=read("qubit_results.csv");summary=read("qubit_summary.csv")
    cv=read("cv_results.csv");follow=read("followup_results.csv")
    assert len(mainrows)==864 and len(cv)==720 and len(follow)==80
    assert all(np.isfinite(float(r["test_nrmse"])) for r in mainrows)
    # Validate selected flags and summaries independently from the study helper.
    for s in summary:
        vals=[]
        for b in range(8):
            ratios=[]
            for task in ("NARMA10","MG5"):
                rr=[r for r in mainrows if r["case"]==s["case"] and int(r["block"])==b and r["task"]==task]
                ref=next(r for r in rr if r["p"]=="0")
                sel=next(r for r in rr if ((r["p"]=="2" and r["r"]=="2") if s["hypothesis"].startswith("H1") else r["selected"]=="True"))
                ratios.append(np.log(float(sel["test_nrmse"])/float(ref["test_nrmse"])))
            vals.append(np.mean(ratios))
        assert abs(interval(vals)[0]-float(s["geomean_error_ratio"]))<1e-12
    lines=["# Wyniki eksploracyjnego badania H1/H2 — 6 września 2026\n",
        "Wykonano 864 oceny kubitowych konfiguracji (6 przypadków × 8 bloków × 2 zadania × 9 metod), "
        "720 przypadków CV (w tym jawnie niestabilne), 24 diagnostyki widma/pamięci, 24 kontrole truncacji Focka "
        "oraz dodatkową kontrolę na 8 nowych blokach. Dane nie stanowią pełnego potwierdzenia protokołu H1–H5. "
        "Na fizycznym QPU nie wykonano żadnego zadania.\n",
        "## 1. Kubity: iloraz NRMSE wobec exact\n",
        "Wartości <1 oznaczają mniejszy błąd; równoważona średnia geometryczna NARMA10 i MG5. "
        "Przedziały 95% t na poziomie 8 sparowanych bloków są niejednoczesne. "
        "H1 wymaga ilorazu <1.02, H2 <0.98; p_Holm obejmuje 12 kontrastów stresowych.\n"]
    lines.append(table(["Przypadek","Schemat","Iloraz","95% CI","p Holm (ekspl.)"],[
        [s["case"],s["hypothesis"],f'{float(s["geomean_error_ratio"]):.4f}',
         f'[{float(s["ci95_low"]):.4f}, {float(s["ci95_high"]):.4f}]',f'{float(s["p_holm_stress_family"]):.4g}'] for s in summary]))
    lines.append("Przemienny przypadek ma identyczne predykcje i zerową wariancję kontrastu. "
        "Zapis p=0 dla H1 jest konwencją gałęzi deterministycznej kodu, a nie wiarygodnym zerowym prawdopodobieństwem statystycznym. "
        "To kontrola analitycznej równości. Dla J=0 nie można uzasadniać redukcji realnych bramek 2Q historycznym proxy: "
        "kąty RZZ są zerowe i kompilator może usunąć te operacje.\n")
    lines.append("Standard tau=0.8: H1 i H2 pozostają nierozstrzygnięte w małej próbie. "
        "Rezonans obala bezwarunkową użyteczność p=2,r=2. Mały tau zachowuje jakość, "
        "ale diagnostyka wykazuje słabą dostępną pamięć i wolne zapominanie — zgodność z exact nie oznacza dobrego rezerwuaru.\n")
    lines.append("## 2. Nowe bloki: kontrola dostrojonego exact i klasycznych modeli\n")
    comparisons=[]
    for ref in ("fixed_exact","tuned_exact","lag_ridge","polynomial_lags"):
        effects=[]
        for b in range(100,108):
            es=[]
            for task in ("NARMA10","MG5"):
                rr=[r for r in follow if int(r["block"])==b and r["task"]==task]
                c=float(next(r for r in rr if r["family"]=="selected_trotter")["test_nrmse"])
                e=float(next(r for r in rr if r["family"]==ref)["test_nrmse"])
                es.append(np.log(c/e))
            effects.append(np.mean(es))
        mean,lo,hi=interval(effects)
        comparisons.append([ref,f"{mean:.4f}",f"[{lo:.4f}, {hi:.4f}]"])
    lines.append(table(["Odniesienie","Trotter / odniesienie","95% CI"],comparisons))
    lines.append("Kontrolę zaprojektowano po początkowej eksploracji, ale wykonano na nowych blokach 100–107. "
        "Exact ma 8 konfiguracji (tau=0.4/0.8/1.6/3.2 × g=0.6/0.9); Trotter ma 8 konfiguracji przy tau=3.2. "
        "Wybór wyłącznie na validation. Porównanie nie wyrównuje kosztu symulacji ani liczby parametrów. "
        "To dodatkowa replikacja i ablacja, nie pierwotny test potwierdzający H2.\n")
    bytask=[]
    for task in ("NARMA10","MG5"):
        for family in sorted({r["family"] for r in follow}):
            errs=[float(r["test_nrmse"]) for r in follow if r["task"]==task and r["family"]==family]
            bytask.append([task,family,f"{np.mean(errs):.5f}"])
    lines.append(table(["Zadanie","Rodzina","Średni NRMSE"],bytask))
    lines.append("## 3. CV: stabilność i błędy\n")
    cvtable=[]
    for case in sorted({r["case"] for r in cv}):
        for p,r in ((0,0),(1,1),(2,1),(2,2)):
            ss=[x for x in cv if x["case"]==case and int(x["p"])==p and int(x["r"])==r]
            valid=[float(x["test_nrmse"]) for x in ss if x["test_nrmse"]]
            cvtable.append([case,f"p{p}r{r}",f'{float(ss[0]["mean_map_radius"]):.4f}',
                f'{len(valid)}/{len(ss)}',f'{np.mean(valid):.4f}' if valid else "NA"])
    lines.append(table(["Model","Schemat","rho(sqrt(eta) S)","Oceny skończone","Śr. NRMSE"],cvtable))
    lines.append("Średnia CV obejmuje obie ustalone rodziny zadań i ma charakter opisowy. "
        "rho>=1 jest diagnozą braku asymptotycznej stabilności; przekroczenie energii 1e9 przerywa propagację. "
        "Wszystkie gaussowskie modele są klasycznie symulowalne.\n")
    cutoff=read("cv_cutoff_checks.csv")
    lines.append("## 4. Truncacja Focka: alpha=2.5\n")
    lines.append(table(["Cutoff","Schemat","Masa końcowa na brzegu (2 poziomy)","Błąd <q²> wobec Gaussa"],[
        [r["cutoff"],f'p{r["p"]}r{r["r"]}',f'{float(r["boundary_mass_last2"]):.3g}',f'{float(r["q2_error_vs_gaussian"]):.3g}']
        for r in cutoff if r["alpha"]=="2.5"]))
    lines.append("Masa początkowa poza cutoff=8 wynosi około 29.1%; taki model nie jest wiernym przybliżeniem. "
        "Dla r=1 pierwszego rzędu cutoff=16 daje dużo większy błąd niż exact przy tym samym cutoff. "
        "Zbieżność trzeba sprawdzać osobno dla każdego schematu. Ujemna masa ogona rzędu 1e-15 w danych jest błędem zaokrągleń.\n")
    lines.append("## 5. Kompilacja i syntetyczny szum\n")
    hw=read("hardware_compile.csv");noise=read("hardware_noise_checks.csv")
    lines.append(table(["W","r","CX po routingu","Głębokość","Resety"],[[r["window"],r["r"],r["cx"],r["depth"],r["resets"]] for r in hw]))
    lines.append("Target: syntetyczna linia 4 kubitów; brak kalibracji QPU. Aer wykonuje obwód logiczny bez routingu "
        "dla niezależnego sprawdzenia zgodności i modelu szumu; nie należy mnożyć jego błędu przez liczbę routowanych CX jako wyniku zmierzonego.\n")
    lines.append(table(["W","r","Siła depolaryzacji CX","Odległość śladowa od własnej idealnej dynamiki"],[[r["window"],r["r"],r["cx_depolarizing"],f'{float(r["trace_distance_to_ideal_window"]):.4g}'] for r in noise]))
    lines.append("Każdy zaszumiony wariant porównano z jego własnym idealnym odpowiednikiem, nie z exact. "
        "Niższa odległość nie dowodzi lepszego NRMSE. Idealny Aer zgadza się z modelem macierzowym do <4e-13 w odległości śladowej.\n")
    lines.append("## 6. Kontrole i ograniczenia\n")
    lines.append("14 istniejących testów QRC i adaptera IBM przeszło. Dodatkowe asercje runtime sprawdziły "
        "granicę przemienną, dokładność swobodnego splittingu, niestabilność oscylatora przy grubym kroku i brak ścisłej "
        "kontrakcji po jednym resecie. Agregaty H1/H2 przeliczono niezależnie w skrypcie raportującym. "
        "Nie wykonano pełnego benchmarku skończonych shots na QPU, nieliniowego Kerr ani dowodu przewagi kwantowej.\n")
    lines.append("## 7. Wykresy\n\n![Ilorazy błędów](h1_h2_ratios.png)\n\n![Stabilność CV](cv_stability.png)\n")
    (ROOT/"RESULTS.md").write_text("\n".join(lines),encoding="utf-8")

    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    cases=["weak_tau","standard","coarse_tau","kick_resonance","commuting","uncoupled"]
    labels=["Mały czas (0.1)","Standard (0.8)","Duży czas (3.2)","Rezonans (π/0.9)","Przemienny B=0","Bez sprzężeń J=0"]
    fig,axes=plt.subplots(1,2,figsize=(12,5),sharey=True,layout="constrained")
    for ax,h,title in zip(axes,["H1_fixed_p2r2","H2_val_selected"],["H1: Strang r=2; próg 1.02 (linia przerywana)","H2: wybór na walidacji; próg 0.98"]):
        ss=[next(s for s in summary if s["case"]==c and s["hypothesis"]==h) for c in cases]
        means=np.array([float(s["geomean_error_ratio"]) for s in ss]);lo=np.array([float(s["ci95_low"]) for s in ss]);hi=np.array([float(s["ci95_high"]) for s in ss])
        ax.errorbar(means,np.arange(6),xerr=[means-lo,hi-means],fmt="o",color="#275D8C",capsize=3)
        ax.axvline(1,color="#333333",lw=1);ax.axvline(1.02 if h.startswith("H1") else .98,color="#B77824",ls="--",lw=1)
        ax.set_title(title);ax.set_xlabel("NRMSE / NRMSE exact (mniej = lepiej)")
        ax.set_yticks(range(6),labels);ax.grid(axis="x",alpha=.18)
        ax.set_xlim(.78,1.9 if h.startswith("H1") else 1.10)
    axes[0].invert_yaxis()
    fig.suptitle("QRC: ilorazy błędów predykcji\n8 sparowanych bloków; NARMA10 + MG5; 95% CI t; analiza eksploracyjna",fontsize=12)
    fig.savefig(ROOT/"h1_h2_ratios.png",dpi=180);fig.savefig(ROOT/"h1_h2_ratios.svg");plt.close(fig)
    from quantum_reservoir.spectral_h1_h2_study import gaussian_step
    times=np.linspace(.05,4.,250)
    fig,ax=plt.subplots(figsize=(8,4.7),layout="constrained")
    for p,r,label,color,style in [(0,0,"Exact", "#333333","-"),(2,1,"Strang r=1","#275D8C","-"),(2,2,"Strang r=2","#B77824","--")]:
        radii=[max(abs(np.linalg.eigvals(np.sqrt(.8)*gaussian_step(x,1.,p,r)))) for x in times]
        ax.plot(times,radii,label=label,color=color,ls=style,lw=1.8)
    ax.axhline(1,color="#777777",ls=":",label="Granica stabilności")
    ax.set_yscale("log");ax.set_xlabel("Czas ewolucji między wejściami τ");ax.set_ylabel("Promień spektralny mapy średnich")
    ax.set_title("CV: stabilność tłumionego oscylatora\nω=1, η=0.8; exact i Strang r=2 pokrywają się w tym zakresie")
    ax.legend();ax.grid(alpha=.15);fig.savefig(ROOT/"cv_stability.png",dpi=180);fig.savefig(ROOT/"cv_stability.svg");plt.close(fig)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.name!="artifact_hashes.json"}
    hashes["study_source_current"]=hashlib.sha256(Path("quantum_reservoir/spectral_h1_h2_study.py").read_bytes()).hexdigest()
    hashes["report_source"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (ROOT/"artifact_hashes.json").write_text(json.dumps(hashes,indent=2),encoding="utf-8")
    print("Follow-up ratios:",comparisons)
    print("CV:",cvtable)

if __name__=="__main__":main()
