"""Exploratory H1/H2 stress tests. No QPU submission; independent of legacy MG scaling.

Run: python -m quantum_reservoir.spectral_h1_h2_study --blocks 8
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(_name, "1")
import argparse
import csv
import hashlib
import json
import platform
from dataclasses import replace, asdict
from pathlib import Path
import time
import numpy as np
from scipy.linalg import expm
from scipy.stats import t as student_t
from quantum_reservoir.core import (
    ReservoirConfig, QuantumReservoir, exact_unitary, trotter_unitary,
    hamiltonian_parts, inject_input, process_infidelity, circuit_resources,
)
from quantum_reservoir.benchmarks import narma10

TRAIN = np.arange(200, 800)
VAL = np.arange(805, 1055)
TEST = np.arange(1060, 1360)
LENGTH = 1360
ALPHAS = (1e-8, 1e-6, 1e-4, 1e-2, 1.0, 100.0)
METHODS = [(0, 0)] + [(p, r) for p in (1, 2) for r in (1, 2, 4, 8)]


def save_csv(path, rows):
    path = Path(path)
    if rows:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def fit(x, y, alpha):
    mu, scale = x.mean(0), x.std(0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    z = (x-mu)/scale
    bias = y.mean()
    w = np.linalg.solve(z.T@z + alpha*np.eye(z.shape[1]), z.T@(y-bias))
    return mu, scale, w, bias


def predict(model, x):
    mu, scale, w, bias = model
    return ((x-mu)/scale)@w+bias


def error(y, pred):
    return float(np.sqrt(np.mean((y-pred)**2))/np.std(y))


def choose_alpha(x, y):
    scores = [(error(y[VAL], predict(fit(x[TRAIN], y[TRAIN], a), x[VAL])), -a)
              for a in ALPHAS]
    e, neg_a = min(scores)
    return -neg_a, e


def evaluate(x, y, alpha):
    ids = np.concatenate([TRAIN, VAL])
    pred = predict(fit(x[ids], y[ids], alpha), x[TEST])
    return error(y[TEST], pred), pred


def mg_data(seed):
    rng = np.random.default_rng(seed)
    v = np.empty(1000+LENGTH+5+18)
    v[:18] = rng.uniform(1.1, 1.3, 18)
    for t in range(17, len(v)-1):
        d = v[t-17]
        v[t+1] = v[t]+0.2*d/(1+d**10)-0.1*v[t]
    raw = v[1000:1000+LENGTH+5]
    lo, hi = raw[TRAIN].min(), raw[TRAIN].max()
    scaled = (raw[:LENGTH]-lo)/(hi-lo)
    return np.clip(scaled, 0, 1), raw[5:], float(np.mean((scaled[TEST]<0)|(scaled[TEST]>1)))


def data_for_block(b):
    n = narma10(LENGTH, seed=918000+b)
    u, y, clipping = mg_data(928000+b)
    return {"NARMA10": (n.inputs, n.targets), "MG5": (u, y)}, clipping


def spectral_metrics(config, unitary):
    """Frozen-input channel; not an ESP certificate for switching inputs."""
    d = len(unitary)
    cols = []
    for j in range(d*d):
        basis = np.zeros((d,d), complex)
        basis.flat[j] = 1
        cols.append((unitary@inject_input(basis, 0.5)@unitary.conj().T).reshape(-1))
    channel = np.column_stack(cols)
    eigs = np.linalg.eigvals(channel)
    stationary = np.argmin(abs(eigs-1))
    rho_sub = float(np.max(abs(np.delete(eigs, stationary))))
    initial = np.zeros((d,d), complex)
    initial[0,0] = 1
    diff = initial-np.eye(d)/d
    max_dist = 0.
    for u in np.random.default_rng(981).uniform(0,1,100):
        diff = unitary@inject_input(diff, float(u))@unitary.conj().T
        max_dist = max(max_dist, float(np.linalg.norm(diff, ord="nuc")/2))
    final_dist = float(np.linalg.norm(diff, ord="nuc")/2)
    a,b = hamiltonian_parts(config)
    return {"frozen_subradius":rho_sub, "frozen_unit_modes":int(np.sum(abs(abs(eigs)-1)<1e-8)),
            "trace_distance_after100":final_dist, "max_trace_distance":max_dist,
            "commutator_norm":float(np.linalg.norm(a@b-b@a,2)),
            "energy_bandwidth":float(np.ptp(np.linalg.eigvalsh(a+b)))}


def memory_metrics(features):
    rng = np.random.default_rng(771)
    u = rng.uniform(0,1,LENGTH)
    v = np.sqrt(3)*(2*u-1)
    lin, nonlin = [], []
    for delay in range(1,11):
        for dest, y in ((lin,np.roll(v,delay)), (nonlin,np.roll(v,delay)*np.roll(v,delay+1))):
            alpha,_ = choose_alpha(features, y)
            err,_ = evaluate(features,y,alpha)
            dest.append(1-err**2)
    return {"memory_linear10":float(sum(lin)),"memory_product10":float(sum(nonlin))}


def run_qubits(out, blocks):
    cases = {
        "standard":{}, "weak_tau":{"evolution_time":0.1},
        "commuting":{"transverse_field":0.0},
        "uncoupled":{"interaction_strength":0.0},
        "coarse_tau":{"evolution_time":3.2},
        "kick_resonance":{"evolution_time":float(np.pi/0.9)},
    }
    rows, sels, diagnostics = [], [], []
    for case, kw in cases.items():
        for b in range(blocks):
            datasets, clipping = data_for_block(b)
            base = ReservoirConfig(n_qubits=4, disorder_seed=938000+b, **kw)
            reference = exact_unitary(base)
            candidates = {}
            for p,r in METHODS:
                cfg = base if p==0 else replace(base,method="trotter",trotter_order=p,trotter_steps=r)
                res = QuantumReservoir(cfg)
                for task,(u,y) in datasets.items():
                    f,_ = res.transform(u)
                    x = np.column_stack([u,f])
                    alpha, val = choose_alpha(x,y)
                    candidates[(task,p,r)] = (x,alpha,val)
                if b==0 and (p,r) in ((0,0),(1,1),(2,2),(2,8)):
                    # Small n=3 channel spectrum, same physical coefficients and seed.
                    small = replace(cfg,n_qubits=3)
                    small_res=QuantumReservoir(small)
                    f,_=res.transform(np.random.default_rng(771).uniform(0,1,LENGTH))
                    diagnostics.append({"case":case,"p":p,"r":r,"spectral_n":3,"memory_n":4,
                        **spectral_metrics(small,small_res.unitary),**memory_metrics(f)})
            # Selection record is persisted before test predictions for this block.
            chosen={}
            for task in datasets:
                chosen[task]=min([(p,r) for p,r in METHODS if p],
                    key=lambda pr:(candidates[(task,*pr)][2],
                    circuit_resources(replace(base,method="trotter",trotter_order=pr[0],trotter_steps=pr[1]))["two_qubit_gates"],*pr))
                sels.append({"case":case,"block":b,"task":task,"p":chosen[task][0],"r":chosen[task][1]})
            save_csv(out/"qubit_selections.csv",sels)
            for (task,p,r),(x,alpha,val) in candidates.items():
                e,pred=evaluate(x,datasets[task][1],alpha)
                cfg=base if p==0 else replace(base,method="trotter",trotter_order=p,trotter_steps=r)
                u=reference if p==0 else trotter_unitary(cfg)
                rows.append({"case":case,"block":b,"task":task,"p":p,"r":r,"alpha":alpha,
                    "validation_nrmse":val,"test_nrmse":e,"infidelity":process_infidelity(reference,u),
                    "selected":(p,r)==chosen[task],"mg_test_clipping":clipping})
            save_csv(out/"qubit_results.csv",rows)
            save_csv(out/"qubit_diagnostics.csv",diagnostics)
            print(f"qubits {case} {b+1}/{blocks}",flush=True)
    return rows


def summarize_qubits(rows,out):
    summary=[]
    for case in sorted({r["case"] for r in rows}):
        subset=[r for r in rows if r["case"]==case]
        for hypothesis in ("H1_fixed_p2r2","H2_val_selected"):
            effects=[]
            for b in sorted({r["block"] for r in subset}):
                es=[]
                for task in ("NARMA10","MG5"):
                    rr=[r for r in subset if r["block"]==b and r["task"]==task]
                    ref=next(r for r in rr if r["p"]==0)["test_nrmse"]
                    c=next(r for r in rr if ((r["p"]==2 and r["r"]==2) if hypothesis.startswith("H1") else r["selected"]))
                    es.append(np.log(c["test_nrmse"]/ref))
                effects.append(np.mean(es))
            e=np.array(effects); mean=float(e.mean()); se=float(e.std(ddof=1)/np.sqrt(len(e)))
            margin=np.log(1.02 if hypothesis.startswith("H1") else .98)
            if se>1e-14:
                pval=float(student_t.cdf((mean-margin)/se,len(e)-1))
                lo,hi=mean-student_t.ppf(.975,len(e)-1)*se,mean+student_t.ppf(.975,len(e)-1)*se
            else:
                pval=0. if mean<margin else 1.; lo=hi=mean
            summary.append({"case":case,"hypothesis":hypothesis,"blocks":len(e),
                "geomean_error_ratio":float(np.exp(mean)),"ci95_low":float(np.exp(lo)),"ci95_high":float(np.exp(hi)),
                "p_raw_exploratory":pval})
    # Holm over all case x hypothesis stress tests, not the original confirmatory protocol.
    order=sorted(range(len(summary)),key=lambda i:summary[i]["p_raw_exploratory"])
    current=0.
    for rank,i in enumerate(order):
        current=max(current,min(1.,(len(order)-rank)*summary[i]["p_raw_exploratory"]))
        summary[i]["p_holm_stress_family"]=current
    save_csv(out/"qubit_summary.csv",summary)
    return summary


def gaussian_step(tau,omega2,p,r):
    # H=A+B, A=p^2/2, B=omega2*q^2/2; hbar=1.
    a=np.array([[0.,1.],[0.,0.]])
    b=np.array([[0.,0.],[-omega2,0.]])
    if p==0: return expm(tau*(a+b))
    dt=tau/r
    step=expm(dt*b)@expm(dt*a) if p==1 else expm(dt*a/2)@expm(dt*b)@expm(dt*a/2)
    return np.linalg.matrix_power(step,r)


def gaussian_features(u,s,eta):
    m=np.zeros(2); cov=np.eye(2)/2; rows=[]; peak=0.
    for val in u:
        m=m+np.array([.25*(2*val-1),0.])
        m=np.sqrt(eta)*(s@m)
        cov=eta*s@cov@s.T+(1-eta)*np.eye(2)/2
        photons=(np.trace(cov)+m@m-1)/2
        peak=max(peak,float(photons))
        if not np.isfinite(photons) or photons>1e9:
            return None,peak
        rows.append([*m,cov[0,0]+m[0]**2,cov[1,1]+m[1]**2,cov[0,1]+m[0]*m[1]])
    return np.array(rows),peak


def run_cv(out,blocks):
    cases={"oscillator":(.8,1.,.8),"oscillator_large_step":(3.,1.,.8),
           "free_particle":(.8,0.,.8),"inverted_unstable":(.8,-1.,.8),
           "inverted_damped":(.8,-1.,.1)}
    rows=[]
    for case,(tau,w2,eta) in cases.items():
        for p,r in METHODS:
            s=gaussian_step(tau,w2,p,r)
            radius=float(max(abs(np.linalg.eigvals(np.sqrt(eta)*s))))
            for b in range(blocks):
                datasets,_=data_for_block(b)
                for task,(u,y) in datasets.items():
                    x,energy=gaussian_features(u,s,eta)
                    if x is None: alpha=val=e=None
                    else:
                        x=np.column_stack([u,x]); alpha,val=choose_alpha(x,y); e,_=evaluate(x,y,alpha)
                    rows.append({"case":case,"block":b,"task":task,"p":p,"r":r,"tau":tau,
                        "omega2":w2,"eta":eta,"mean_map_radius":radius,"stable":radius<1-1e-10,
                        "peak_photons":energy,"alpha":alpha,"validation_nrmse":val,"test_nrmse":e})
        print(f"CV {case}",flush=True)
    save_csv(out/"cv_results.csv",rows)
    return rows


def cutoff_checks(out):
    rows=[]
    for alpha in (.4,2.5):
        for cutoff in (8,16,32,64):
            a=np.diag(np.sqrt(np.arange(1,cutoff)),1).astype(complex)
            q=(a+a.conj().T)/np.sqrt(2); p=(a-a.conj().T)/(1j*np.sqrt(2))
            coeff=np.empty(cutoff,complex); coeff[0]=np.exp(-alpha**2/2)
            for k in range(1,cutoff): coeff[k]=coeff[k-1]*alpha/np.sqrt(k)
            lost=1-float(np.vdot(coeff,coeff).real); coeff/=np.linalg.norm(coeff)
            for order,r in ((0,0),(1,1),(2,2)):
                aa=p@p/2; bb=q@q/2
                if not order: u=expm(-1j*.8*(aa+bb))
                elif order==1: u=expm(-1j*.8*bb)@expm(-1j*.8*aa)
                else:
                    st=expm(-1j*.2*aa)@expm(-1j*.4*bb)@expm(-1j*.2*aa)
                    u=st@st
                psi=u@coeff
                second=float(np.vdot(psi,q@q@psi).real)
                s=gaussian_step(.8,1.,order,r)
                m=s@np.array([np.sqrt(2)*alpha,0.]); cov=s@(np.eye(2)/2)@s.T
                target=cov[0,0]+m[0]**2
                rows.append({"alpha":alpha,"cutoff":cutoff,"p":order,"r":r,
                    "initial_tail_mass":lost,"boundary_mass_last2":float(sum(abs(psi[-2:])**2)),
                    "q2_error_vs_gaussian":abs(second-target)})
    save_csv(out/"cv_cutoff_checks.csv",rows)


def hardware_checks(out):
    """Compile to an explicit synthetic line, validate ideal and noisy density evolution."""
    from qiskit import transpile, qpy
    from qiskit.quantum_info import DensityMatrix
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, depolarizing_error
    from quantum_reservoir.ibm_hardware import build_replay_circuit
    rows=[]; circuits=[]; checks=[]
    inputs=np.random.default_rng(567).uniform(0,1,32)
    coupling=[[0,1],[1,0],[1,2],[2,1],[2,3],[3,2]]
    for window in (8,32):
        for r in (2,16):
            cfg=ReservoirConfig(n_qubits=4,method="trotter",trotter_order=2,trotter_steps=r)
            qc=build_replay_circuit(inputs,31,cfg,history_window=window)
            compiled=transpile(qc,basis_gates=["rz","sx","x","cx","reset"],coupling_map=coupling,
                               initial_layout=[0,1,2,3],optimization_level=2,seed_transpiler=71)
            circuits.append(compiled)
            rows.append({"window":window,"r":r,"cx":compiled.count_ops().get("cx",0),
                "depth":compiled.depth(),"resets":compiled.count_ops().get("reset",0),
                "operations":sum(compiled.count_ops().values()),"target":"synthetic_4qubit_line_not_QPU"})
            # Validate the original logical circuit to avoid output-layout ambiguity.
            logical=transpile(qc,basis_gates=["rz","sx","x","cx","reset"],optimization_level=0)
            logical.save_density_matrix()
            for strength in (0.,.001,.01):
                noise=NoiseModel()
                if strength: noise.add_all_qubit_quantum_error(depolarizing_error(strength,2),["cx"])
                result=AerSimulator(method="density_matrix",noise_model=noise).run(logical,shots=1).result()
                rho=np.asarray(result.data(0)["density_matrix"])
                dense=np.zeros((16,16),complex);dense[0,0]=1
                u=trotter_unitary(cfg)
                for val in inputs[-window:]:dense=u@inject_input(dense,float(val))@u.conj().T
                dist=float(np.linalg.norm(rho-dense,ord="nuc")/2)
                checks.append({"window":window,"r":r,"cx_depolarizing":strength,
                    "trace_distance_to_ideal_window":dist,"purity":float(np.trace(rho@rho).real),
                    "logical_cx":logical.count_ops().get("cx",0)})
                if strength==0: assert dist<1e-9, dist
    with (out/"hardware_synthetic_line.qpy").open("wb") as handle:qpy.dump(circuits,handle)
    save_csv(out/"hardware_compile.csv",rows);save_csv(out/"hardware_noise_checks.csv",checks)


def mathematical_checks(out):
    cfg=ReservoirConfig(n_qubits=3,transverse_field=0,method="trotter",trotter_order=2,trotter_steps=2)
    commute=float(np.linalg.norm(exact_unitary(cfg)-trotter_unitary(cfg),2))
    assert commute<1e-10
    stable=max(abs(np.linalg.eigvals(np.sqrt(.8)*gaussian_step(3.,1.,0,0))))
    unstable=max(abs(np.linalg.eigvals(np.sqrt(.8)*gaussian_step(3.,1.,2,1))))
    assert stable<1 and unstable>1
    free=float(np.linalg.norm(gaussian_step(.8,0.,0,0)-gaussian_step(.8,0.,2,2)))
    assert free<1e-12
    # Critical one-step contraction: untouched environment preserves distinguishability.
    cfg=ReservoirConfig(n_qubits=3)
    u=exact_unitary(cfg)
    r0=np.zeros((8,8),complex);r1=r0.copy();r0[0,0]=1;r1[1,1]=1
    diff=u@inject_input(r0-r1,.5)@u.conj().T
    trace_distance=float(np.linalg.norm(diff,ord="nuc")/2)
    assert abs(trace_distance-1)<1e-10
    result={"commuting_operator_error":commute,"cv_exact_radius_tau3":float(stable),
        "cv_strang_r1_radius_tau3":float(unstable),"free_particle_split_error":free,
        "reset_channel_one_step_contraction_counterexample":trace_distance}
    (out/"mathematical_checks.json").write_text(json.dumps(result,indent=2),encoding="utf-8")


def followup_controls(out, blocks):
    """New independent blocks, fixed control grid after initial exploratory findings."""
    results=[];selections=[]
    for block in range(100,100+blocks):
        datasets,_=data_for_block(block)
        base=ReservoirConfig(n_qubits=4,evolution_time=3.2,disorder_seed=938000+block)
        pools={task:[] for task in datasets}
        for p,r in METHODS:
            cfg=base if not p else replace(base,method="trotter",trotter_order=p,trotter_steps=r)
            res=QuantumReservoir(cfg)
            for task,(u,y) in datasets.items():
                f,_=res.transform(u);x=np.column_stack([u,f]);alpha,val=choose_alpha(x,y)
                pools[task].append(("fixed_exact" if not p else "selected_trotter",f"p{p}r{r}",x,alpha,val))
        for tau in (.4,.8,1.6,3.2):
            for g in (.6,.9):
                res=QuantumReservoir(replace(base,evolution_time=tau,transverse_field=g))
                for task,(u,y) in datasets.items():
                    f,_=res.transform(u);x=np.column_stack([u,f]);alpha,val=choose_alpha(x,y)
                    pools[task].append(("tuned_exact",f"tau{tau}g{g}",x,alpha,val))
        for task,(u,y) in datasets.items():
            for lag in (8,16,32):
                x=np.column_stack([np.roll(u,j) for j in range(lag)])
                alpha,val=choose_alpha(x,y)
                pools[task].append(("lag_ridge",f"L{lag}",x,alpha,val))
                if lag<=16:
                    columns=[x]+[(x[:,i]*x[:,j])[:,None] for i in range(lag) for j in range(i,lag)]
                    poly=np.column_stack(columns);alpha,val=choose_alpha(poly,y)
                    pools[task].append(("polynomial_lags",f"L{lag}",poly,alpha,val))
        chosen={}
        for task,pool in pools.items():
            for family in sorted({r[0] for r in pool}):
                best=min([r for r in pool if r[0]==family],key=lambda r:(r[4],r[1]))
                chosen[(task,family)]=best
                selections.append({"block":block,"task":task,"family":family,"configuration":best[1],"validation_nrmse":best[4]})
        save_csv(out/"followup_selections.csv",selections)
        for (task,family),(_,name,x,alpha,val) in chosen.items():
            e,_=evaluate(x,datasets[task][1],alpha)
            results.append({"block":block,"task":task,"family":family,"configuration":name,"test_nrmse":e,"alpha":alpha})
        save_csv(out/"followup_results.csv",results)
        print(f"new-block control {block-99}/{blocks}",flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--blocks",type=int,default=8)
    parser.add_argument("--output",default="analysis_output/qrc_spectral_h1_h2")
    parser.add_argument("--hardware-only",action="store_true")
    parser.add_argument("--followup-only",action="store_true")
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if args.hardware_only:hardware_checks(out);return
    if args.followup_only:followup_controls(out,args.blocks);return
    started=time.time()
    manifest={"status":"running_exploratory_not_confirmatory","blocks":args.blocks,
        "train":TRAIN.tolist(),"validation":VAL.tolist(),"test":TEST.tolist(),"methods":METHODS,
        "python":platform.python_version(),"numpy":np.__version__,
        "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"qpu_executed":False}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    mathematical_checks(out)
    rows=run_qubits(out,args.blocks);summary=summarize_qubits(rows,out)
    run_cv(out,args.blocks);cutoff_checks(out)
    manifest.update(status="completed_exploratory",elapsed_seconds=time.time()-started)
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)


if __name__=="__main__":main()
