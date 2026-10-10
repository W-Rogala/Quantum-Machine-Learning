"""Frozen-selection readout ablation and same-n channel structure diagnostics."""
from pathlib import Path
import csv
import json
import hashlib
import numpy as np
from dataclasses import replace
from quantum_reservoir.h3_memory_study import (
    pauli_basis,unitary,states,features,ridge_prepare,ridge_test,
)
from quantum_reservoir.core import ReservoirConfig
from quantum_reservoir.spectral_h1_h2_study import data_for_block,save_csv

ROOT=Path("analysis_output/qrc_h3_memory")

def read(name):
    with (ROOT/name).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))

def resolve(regime,block,name,phase="core"):
    tau={"standard":.8,"coarse":3.2,"resonance":np.pi/.9}.get(regime)
    if phase=="sweep":tau=np.pi/.9+float(regime)
    cfg=ReservoirConfig(n_qubits=4,evolution_time=tau,disorder_seed=938000+int(block))
    if name.startswith("tuned_"):
        tt,gg=name.removeprefix("tuned_tau").split("_g")
        return unitary(replace(cfg,evolution_time=float(tt),transverse_field=float(gg)),"exact")
    if name=="fixed_exact":return unitary(cfg,"exact")
    kind,r=name.split("_r");return unitary(cfg,kind,int(r))

def channel_apply(u,value,rho):
    psi=np.array([np.sqrt(1-value),np.sqrt(value)])
    ks=np.einsum("aibj,b->aij",u.reshape(2,8,2,8),psi)
    return sum(k@rho@k.conj().T for k in ks)

def main():
    selected=read("selections.csv")
    _,ops,views=pauli_basis();rows=[]
    for regime in ("standard","coarse","resonance"):
        for b in range(300,308):
            datasets,_=data_for_block(b);cache={}
            for record in [r for r in selected if r["regime"]==regime and int(r["block"])==b]:
                task,name=record["task"],record["configuration"]
                if (task,name) not in cache:
                    inputs,target=datasets[task];u=resolve(regime,b,name)
                    full=features(states(inputs,u),ops)
                    for view,indices in views.items():
                        x=np.column_stack([inputs,full[:,indices]])
                        model,alpha,val=ridge_prepare(x,target);e,_=ridge_test(model,x,target)
                        cache[(task,name,view)]=(float(e[0]),float(alpha[0]),float(val[0]))
                    cache[(task,name)]=True
                for view in views:
                    e,alpha,val=cache[(task,name,view)]
                    rows.append({"regime":regime,"block":b,"task":task,"family":record["family"],"configuration":name,
                        "view":view,"nrmse":e,"alpha":alpha,"validation_nrmse":val})
            save_csv(ROOT/"readout_predictions.csv",rows)
            print(f"readout control {regime} {b-299}/8",flush=True)
    # This script can run while the resonance scan is finishing; structure is computed separately on final rerun.
    structure=[]
    for row in read("channels.csv"):
        u=resolve(row["regime"],row["block"],row["method"],row["phase"])
        maximix=np.eye(8)/8
        a=channel_apply(u,.2,maximix);b=channel_apply(u,.8,maximix)
        structure.append({**row,"unitality_defect_u05":float(np.linalg.norm(channel_apply(u,.5,np.eye(8))-np.eye(8),"fro")/np.sqrt(8)),
            "input_response_at_maxmix":float(np.linalg.norm(a-b,"nuc")/2)})
    save_csv(ROOT/"channel_structure.csv",structure)
    meta={"selection_sha256":hashlib.sha256((ROOT/"selections.csv").read_bytes()).hexdigest(),
        "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "readout_rows":len(rows),"structure_rows":len(structure),"status":"complete"}
    (ROOT/"readout_control_manifest.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")

if __name__=="__main__":main()
