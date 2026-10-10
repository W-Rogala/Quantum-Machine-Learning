"""Noise ablation around resonance and calibration drift; exploratory fixed models."""
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='1'
from dataclasses import replace,asdict
from pathlib import Path
import json
import numpy as np
from quantum_reservoir.h3_noise_study import *

def main():
    out=Path('analysis_output/qrc_h3_noise');out.mkdir(exist_ok=True,parents=True)
    names,ops,views=pauli_basis();diag=[];drift=[]
    mild=NOISES['mild']
    ablations={'ideal':Noise(),'depolarization_only':Noise(p1=mild.p1,p2=mild.p2),
       'thermal_only':Noise(thermal=True),'coherent_only':Noise(angle_scale=mild.angle_scale),
       'reset_only':Noise(reset_excited=mild.reset_excited),'combined_mild':mild}
    injections={key:injection_channel(n) for key,n in ablations.items()}
    for block in range(500,508):
        past=np.random.default_rng(765000+block).uniform(0,1,220)
        future=np.random.default_rng(766000+block).uniform(0,1,21)
        # Histories differ only at the probe input; two resets .2/.8 follow identical past.
        for offset in (-.075,0.,.075):
            cfg=ReservoirConfig(evolution_time=np.pi/.9+offset,disorder_seed=938000+block)
            for key,noise in ablations.items():
                ch,_=make_channel(cfg,'ABA',2,noise)
                xa=np.concatenate([past,[.2],future]);xb=np.concatenate([past,[.8],future])
                a=trajectory(xa,ch,injections[key],noise)[220:]
                b=trajectory(xb,ch,injections[key],noise)[220:]
                for d,delta in enumerate(a-b):
                    trace_d=float(np.linalg.norm(delta,ord='nuc')/2)
                    signal=float(np.max(abs(features(delta[None],ops[views['local_XZ_ZZ']])))/2)
                    assert signal<=trace_d+1e-10
                    diag.append(dict(block=block,offset=offset,noise=key,delay=d,trace_distance=trace_d,local_lower_bound=signal))
        # Abrupt calibration mismatch at test boundary. Each circuit replays its full
        # history using current calibration; switch entire replay, not historical time t.
        cfg=ReservoirConfig(evolution_time=3.2,disorder_seed=938000+block)
        normal=mild;changed=replace(mild,angle_scale=.015,read01=.025,read10=.04)
        ch,_=make_channel(cfg,'BAB',2,normal);ch2,_=make_channel(cfg,'BAB',2,changed)
        inj=injection_channel(normal);inj2=injection_channel(changed)
        datasets,_=data_for_block(block)
        for task,(inputs,target) in datasets.items():
            tr=trajectory(inputs,ch,inj,normal);tr2=trajectory(inputs,ch2,inj2,changed)
            for view in ('local_XZ_ZZ','all_1_2body','full_Pauli'):
                design=measurement_design(names,views[view],view)
                shots=(2*4096*24)//(len(design[0])*16)
                stable=sample_features(probabilities(tr,design,normal),design,shots,np.random.default_rng(897000+block))
                moved=sample_features(probabilities(tr2,design,changed),design,shots,np.random.default_rng(898000+block))
                x=np.column_stack([inputs,stable]);xd=x.copy();xd[TEST,1:]=moved[TEST]
                # Same fitted readout; changed test features cannot influence alpha.
                model,_,_=ridge_prepare(x,target)
                for label,xx in (('stable',x),('calibration_shift',xd)):
                    nr,_=ridge_test(model,xx,target)
                    drift.append(dict(block=block,task=task,view=view,scenario=label,nrmse=float(nr[0]),shots_per_group=shots))
        print('diagnostics block',block,flush=True)
    save_csv(out/'noise_ablation_impulses.csv',diag);save_csv(out/'calibration_drift.csv',drift)
    (out/'diagnostics_manifest.json').write_text(json.dumps({'ablations':{k:asdict(n) for k,n in ablations.items()},
       'drift_before':asdict(normal),'drift_after':asdict(changed),
       'drift_policy':'train/validation stationary mild; test circuits replay full prefix under shifted calibration; no retraining',
       'offsets':[-.075,0.,.075],'blocks':list(range(500,508))},indent=2),encoding='utf-8')

if __name__=='__main__':main()
