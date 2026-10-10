"""H3 mechanism study: paired profiles, state distinguishability and resonance scan.

python -m quantum_reservoir.h3_memory_study
No hardware submission. Full Pauli readout is an ideal diagnostic, not a cheap measurement.
"""
from __future__ import annotations
import os
for key in ("OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","OMP_NUM_THREADS"):
    os.environ.setdefault(key,"1")
import argparse
import hashlib
import itertools
import json
import time
from pathlib import Path
from dataclasses import replace
import numpy as np
from scipy.linalg import expm
from quantum_reservoir.core import ReservoirConfig,QuantumReservoir,hamiltonian_parts,inject_input,exact_unitary
from quantum_reservoir.spectral_h1_h2_study import (
    TRAIN,VAL,TEST,LENGTH,ALPHAS,data_for_block,save_csv,
)

N=4
I=np.eye(2,dtype=complex)
X=np.array([[0,1],[1,0]],complex)
Y=np.array([[0,-1j],[1j,0]],complex)
Z=np.diag([1.,-1.]).astype(complex)


def pauli_basis():
    names=[];ops=[];weights=[]
    for letters in itertools.product("IXYZ",repeat=N):
        if all(s=="I" for s in letters):continue
        op=np.array([[1]],complex)
        for letter in letters:op=np.kron(op,dict(I=I,X=X,Y=Y,Z=Z)[letter])
        names.append("".join(letters));ops.append(op);weights.append(sum(s!="I" for s in letters))
    local=[]
    for i in range(N):
        for letter in "XZ":
            name=["I"]*N;name[i]=letter;local.append(names.index("".join(name)))
    for i,j in ((0,1),(1,2),(2,3),(0,3)):
        name=["I"]*N;name[i]=name[j]="Z";local.append(names.index("".join(name)))
    views={"local_XZ_ZZ":np.array(local),"all_1_2body":np.flatnonzero(np.array(weights)<=2),"full_Pauli":np.arange(255)}
    return names,np.array(ops),views


def unitary(config,kind,r=1):
    if kind=="exact":return exact_unitary(config)
    a,b=hamiltonian_parts(config);dt=config.evolution_time/r
    ea=expm(-1j*dt*a);eb=expm(-1j*dt*b)
    if kind=="AB":step=eb@ea  # chronological A then B
    elif kind=="BA":step=ea@eb
    elif kind=="ABA":
        half=expm(-1j*dt*a/2);step=half@eb@half
    elif kind=="BAB":
        half=expm(-1j*dt*b/2);step=half@ea@half
    else:raise ValueError(kind)
    return np.linalg.matrix_power(step,r)


def states(inputs,u):
    rho=np.zeros((16,16),complex);rho[0,0]=1
    result=np.empty((len(inputs),16,16),complex)
    for t,x in enumerate(inputs):
        rho=u@inject_input(rho,float(x))@u.conj().T
        result[t]=rho
    return result


def features(trajectory,ops):
    return (trajectory.reshape(len(trajectory),256)@ops.transpose(0,2,1).reshape(len(ops),256).T).real


def memory_targets(inputs):
    v=np.sqrt(3)*(2*inputs-1);targets=[];labels=[]
    for family in ("linear","product","quadratic"):
        for d in range(1,21):
            if family=="linear":target=np.roll(v,d)
            elif family=="product":target=np.roll(v,d)*np.roll(v,d+1)
            else:
                x=2*np.roll(inputs,d)-1;target=np.sqrt(5)*(3*x*x-1)/2
            targets.append(target);labels.append((family,d))
    return np.column_stack(targets),labels


def ridge_prepare(x,y,alphas=ALPHAS):
    """Simultaneous targets; per-target validation alpha. Test not accessed."""
    if y.ndim==1:y=y[:,None]
    def parts(ids):
        mu=x[ids].mean(0);sd=x[ids].std(0);sd=np.where(sd<1e-12,1.,sd)
        z=(x[ids]-mu)/sd;bias=y[ids].mean(0)
        ev,v=np.linalg.eigh(z.T@z);rhs=v.T@z.T@(y[ids]-bias)
        return mu,sd,bias,np.maximum(ev,0),v,rhs
    mu,sd,bias,ev,v,rhs=parts(TRAIN)
    zv=((x[VAL]-mu)/sd)@v
    scores=[]
    # Prefer larger alpha on exact ties.
    alphas=np.array(sorted(alphas,reverse=True))
    for alpha in alphas:
        pred=zv@(rhs/(ev[:,None]+alpha))+bias
        scores.append(np.mean((pred-y[VAL])**2,axis=0)/np.var(y[VAL],axis=0))
    scores=np.array(scores);choice=np.argmin(scores,axis=0);best=alphas[choice]
    mu,sd,bias,ev,v,rhs=parts(np.concatenate([TRAIN,VAL]))
    w=v@(rhs/(ev[:,None]+best[None,:]))
    return (mu,sd,w,bias),best,np.sqrt(scores[choice,np.arange(y.shape[1])])


def ridge_test(model,x,y):
    if y.ndim==1:y=y[:,None]
    mu,sd,w,bias=model
    pred=((x[TEST]-mu)/sd)@w+bias
    nrmse=np.sqrt(np.mean((pred-y[TEST])**2,axis=0)/np.var(y[TEST],axis=0))
    return nrmse,1-nrmse**2


def reduced_channel(u,value=.5):
    """Nonzero spectrum of physical 4-qubit reset channel via 8x8 memory Kraus ops."""
    psi=np.array([np.sqrt(1-value),np.sqrt(value)])
    tensor=u.reshape(2,8,2,8)
    kraus=np.einsum("aibj,b->aij",tensor,psi)
    assert np.linalg.norm(sum(k.conj().T@k for k in kraus)-np.eye(8))<1e-9
    channel=sum(np.kron(k.conj(),k) for k in kraus)
    ev=np.linalg.eigvals(channel);j=np.argmin(abs(ev-1))
    return {"n_total":4,"memory_dimension":8,"fixed_input":value,
        "subradius":float(max(abs(np.delete(ev,j)))),"unit_modes":int(sum(abs(abs(ev)-1)<1e-8))}


def impulse(u,ops,local_indices,seed,repetitions=6):
    """Two histories differ at one input (.2 vs .8); later inputs identical."""
    rng=np.random.default_rng(seed);collected=[]
    for rep in range(repetitions):
        past=rng.uniform(0,1,220)
        rho=states(past,u)[-1]
        rho_a=u@inject_input(rho,.2)@u.conj().T
        rho_b=u@inject_input(rho,.8)@u.conj().T
        for d,val in enumerate(rng.uniform(0,1,21)):
            if d:
                rho_a=u@inject_input(rho_a,float(val))@u.conj().T
                rho_b=u@inject_input(rho_b,float(val))@u.conj().T
            delta=rho_a-rho_b;tr=float(np.linalg.norm(delta,ord="nuc")/2)
            dz=features(delta[None],ops)[0]
            local=float(max(abs(dz[local_indices]))/2)
            denominator=float(dz@dz)
            fraction=float(dz[local_indices]@dz[local_indices]/denominator) if denominator>1e-20 else None
            assert local<=tr+1e-10
            assert abs(denominator/16-np.trace(delta@delta).real)<1e-9
            collected.append({"rep":rep,"delay":d,"trace_distance":tr,"local_observable_lower_bound":local,
                "local_HS_fraction":fraction})
    return collected


def summarize_profiles(profile_rows):
    out=[];keys=sorted({tuple(r[k] for k in ("phase","regime","block","method","view")) for r in profile_rows})
    for key in keys:
        rr=[r for r in profile_rows if tuple(r[k] for k in ("phase","regime","block","method","view"))==key]
        row=dict(zip(("phase","regime","block","method","view"),key))
        for family in ("linear","product","quadratic"):
            row[family+"20"]=sum(r["capacity"] for r in rr if r["target"]==family)
            row[family+"10"]=sum(r["capacity"] for r in rr if r["target"]==family and r["delay"]<=10)
        row["T"]=(row["product10"]-row["linear10"])/10
        out.append(row)
    return out


def run(out,blocks,sweep_blocks):
    names,ops,views=pauli_basis();profiles=[];channels=[];impulses=[];predictions=[];selections=[]
    checks={"pauli_orthogonality_max_error":float(np.max(abs(ops.reshape(255,256).conj()@ops.reshape(255,256).T/16-np.eye(255))))}
    assert checks["pauli_orthogonality_max_error"]<1e-12
    regimes={"standard":.8,"coarse":3.2,"resonance":np.pi/.9}
    for regime,tau in regimes.items():
        for b in range(300,300+blocks):
            base=ReservoirConfig(n_qubits=4,evolution_time=tau,disorder_seed=938000+b)
            datasets,clipping=data_for_block(b)
            candidate_configs={"fixed_exact":("exact",1,base)}
            for kind in ("AB","ABA"):
                for r in (1,2,4,8):candidate_configs[f"{kind}_r{r}"]=(kind,r,base)
            for tt in (.4,.8,1.6,3.2):
                for g in (.6,.9):candidate_configs[f"tuned_tau{tt}_g{g}"]=("exact",1,replace(base,evolution_time=tt,transverse_field=g))
            prediction_cache={};unitaries={}
            for name,(kind,r,cfg) in candidate_configs.items():
                u=unitary(cfg,kind,r);unitaries[name]=u
                for task,(inputs,target) in datasets.items():
                    # Only original readout used for selection.
                    f=features(states(inputs,u),ops[views["local_XZ_ZZ"]])
                    x=np.column_stack([inputs,f]);model,alpha,val=ridge_prepare(x,target)
                    prediction_cache[(task,name)]=(x,model,float(alpha[0]),float(val[0]))
            selected={}
            for task in datasets:
                selected[(task,"selected_trotter")]=min([name for name in candidate_configs if name.startswith(("AB_","ABA_"))],key=lambda name:(prediction_cache[(task,name)][3],name))
                selected[(task,"tuned_exact")]=min([name for name in candidate_configs if name.startswith("tuned_")],key=lambda name:(prediction_cache[(task,name)][3],name))
                selected[(task,"fixed_exact")]="fixed_exact"
                for family in ("selected_trotter","tuned_exact","fixed_exact"):
                    name=selected[(task,family)]
                    selections.append({"regime":regime,"block":b,"task":task,"family":family,"configuration":name,
                        "validation_nrmse":prediction_cache[(task,name)][3]})
            save_csv(out/"selections.csv",selections)
            for (task,family),name in selected.items():
                x,model,alpha,val=prediction_cache[(task,name)]
                err,_=ridge_test(model,x,datasets[task][1])
                predictions.append({"regime":regime,"block":b,"task":task,"family":family,"configuration":name,
                    "nrmse":float(err[0]),"alpha":alpha,"mg_test_clipping":clipping})
            memory_configs={"fixed_exact":("exact",1,base),"AB_r1":("AB",1,base),
                "ABA_r2":("ABA",2,base),"BAB_r2":("BAB",2,base)}
            for name in selected.values():memory_configs[name]=candidate_configs[name]
            inputs=np.random.default_rng(958000+b).uniform(0,1,LENGTH)
            target,labels=memory_targets(inputs)
            for name,(kind,r,cfg) in memory_configs.items():
                u=unitaries.get(name)
                if u is None:u=unitary(cfg,kind,r)
                trajectory=states(inputs,u);f=features(trajectory,ops)
                assert abs(np.trace(trajectory[-1])-1)<1e-9
                for view,indices in views.items():
                    model,alpha,val=ridge_prepare(f[:,indices],target)
                    _,capacity=ridge_test(model,f[:,indices],target)
                    for j,(family,d) in enumerate(labels):
                        profiles.append({"phase":"core","regime":regime,"block":b,"method":name,"view":view,
                            "target":family,"delay":d,"capacity":float(capacity[j]),"alpha":float(alpha[j]),
                            "validation_nrmse":float(val[j])})
                channels.append({"phase":"core","regime":regime,"block":b,"method":name,**reduced_channel(u)})
                for row in impulse(u,ops,views["local_XZ_ZZ"],968000+b,repetitions=4):
                    impulses.append({"phase":"core","regime":regime,"block":b,"method":name,**row})
            save_csv(out/"profiles.csv",profiles);save_csv(out/"channels.csv",channels)
            save_csv(out/"impulses.csv",impulses);save_csv(out/"predictions.csv",predictions)
            print(f"core {regime} {b-299}/{blocks}",flush=True)
    offsets=(-.3,-.15,-.075,-.03,-.01,0.,.01,.03,.075,.15,.3)
    for offset in offsets:
        for b in range(400,400+sweep_blocks):
            base=ReservoirConfig(n_qubits=4,evolution_time=np.pi/.9+offset,disorder_seed=938000+b)
            inputs=np.random.default_rng(958000+b).uniform(0,1,LENGTH)
            target,labels=memory_targets(inputs)
            for kind,r in (("exact",1),("AB",1),("BA",1),("ABA",2),("BAB",2)):
                name=f"{kind}_r{r}";u=unitary(base,kind,r);f=features(states(inputs,u),ops)
                for view,indices in views.items():
                    model,alpha,val=ridge_prepare(f[:,indices],target);_,capacity=ridge_test(model,f[:,indices],target)
                    for j,(family,d) in enumerate(labels):
                        profiles.append({"phase":"sweep","regime":offset,"block":b,"method":name,"view":view,
                            "target":family,"delay":d,"capacity":float(capacity[j]),"alpha":float(alpha[j]),
                            "validation_nrmse":float(val[j])})
                channels.append({"phase":"sweep","regime":offset,"block":b,"method":name,**reduced_channel(u)})
                for row in impulse(u,ops,views["local_XZ_ZZ"],968000+b,repetitions=2):
                    impulses.append({"phase":"sweep","regime":offset,"block":b,"method":name,**row})
        save_csv(out/"profiles.csv",profiles);save_csv(out/"channels.csv",channels);save_csv(out/"impulses.csv",impulses)
        print(f"sweep offset {offset:+.3f}",flush=True)
    save_csv(out/"profile_summaries.csv",summarize_profiles(profiles))
    (out/"checks.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--blocks",type=int,default=8)
    parser.add_argument("--sweep-blocks",type=int,default=4)
    parser.add_argument("--output",default="analysis_output/qrc_h3_memory")
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    manifest={"status":"running","exploratory":True,"n_total":4,"blocks":list(range(300,300+args.blocks)),
        "sweep_blocks":list(range(400,400+args.sweep_blocks)),"source_hash":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "length":LENGTH,"train":[int(TRAIN[0]),int(TRAIN[-1])],"validation":[int(VAL[0]),int(VAL[-1])],"test":[int(TEST[0]),int(TEST[-1])],
        "shots":"infinite_ideal_expectations","qpu_executed":False,"state_views":[12,66,255]}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    started=time.time();run(out,args.blocks,args.sweep_blocks)
    manifest.update(status="complete",elapsed_seconds=time.time()-started)
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")

if __name__=="__main__":main()
