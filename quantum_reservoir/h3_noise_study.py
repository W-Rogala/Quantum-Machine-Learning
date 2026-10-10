"""Exploratory H3 robustness: native CX noise, grouped shots and replay cost.

Run: python -m quantum_reservoir.h3_noise_study --blocks 8
Synthetic parameters; no QPU submission. Independent block is the statistical unit.
"""
from __future__ import annotations
import os
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
    os.environ[key]='1'
import argparse, hashlib, itertools, json, time
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import depolarizing_error, thermal_relaxation_error
from quantum_reservoir.core import ReservoirConfig, _local_fields, interaction_edges
from quantum_reservoir.h3_memory_study import pauli_basis, features, memory_targets, ridge_prepare as _ridge_prepare, ridge_test, unitary, states
from quantum_reservoir.spectral_h1_h2_study import LENGTH, TRAIN, VAL, TEST, data_for_block, save_csv

@dataclass(frozen=True)
class Noise:
    p1: float=0.
    p2: float=0.
    t1_us: float=100.
    t2_us: float=80.
    thermal: bool=False
    angle_scale: float=0.
    reset_excited: float=0.
    read01: float=0.
    read10: float=0.

NOISES={
    'ideal':Noise(),
    'mild':Noise(p1=.0001,p2=.001,thermal=True,angle_scale=.005,reset_excited=.01,read01=.01,read10=.02),
    'stress':Noise(p1=.001,p2=.01,t1_us=50.,t2_us=40.,thermal=True,angle_scale=.02,reset_excited=.03,read01=.03,read10=.05),
}
CASES={'coarse_ABA2':(3.2,'ABA',2),'coarse_BAB2':(3.2,'BAB',2),
       'coarse_ABA16':(3.2,'ABA',16),'resonance_ABA2':(np.pi/.9,'ABA',2)}

NOISE_ALPHAS=(1e-8,1e-6,1e-4,1e-2,1.,100.,1e3,1e4,1e6,1e8,1e12)
def ridge_prepare(x,y):
    # Very noisy 255-feature readouts need access to the constant-predictor limit.
    return _ridge_prepare(x,y,alphas=NOISE_ALPHAS)

def thermal(qc,wires,noise,duration_us):
    if noise.thermal:
        err=thermal_relaxation_error(noise.t1_us,noise.t2_us,duration_us).to_instruction()
        for wire in wires:qc.append(err,[wire])

def gate(qc,name,wires,noise,angle=None):
    if name=='cx':qc.cx(*wires)
    else:getattr(qc,name)(angle*(1+noise.angle_scale),*wires)
    p=noise.p2 if name=='cx' else (noise.p1 if name=='rx' else 0.)
    if p:qc.append(depolarizing_error(p,len(wires)).to_instruction(),wires)
    # Explicit serial schedule: other qubits idle during each physical gate.
    # RZ is a virtual, instantaneous rotation; RX=35 ns, CX=300 ns.
    if name!='rz':thermal(qc,range(4),noise,.3 if name=='cx' else .035)

def make_channel(cfg,kind,r,noise):
    qc=QuantumCircuit(4);fields=_local_fields(cfg);edges=interaction_edges(4,cfg.topology)
    def a(dt):
        for q,h in enumerate(fields):gate(qc,'rz',[3-q],noise,2*h*dt)
        for i,j in edges:
            if cfg.interaction_strength==0:continue
            gate(qc,'cx',[3-i,3-j],noise)
            gate(qc,'rz',[3-j],noise,2*cfg.interaction_strength*dt)
            gate(qc,'cx',[3-i,3-j],noise)
    def b(dt):
        for q in range(4):gate(qc,'rx',[3-q],noise,2*cfg.transverse_field*dt)
    dt=cfg.evolution_time/r
    first,second=(a,b) if kind=='ABA' else (b,a)
    first(dt/2)
    for step in range(r):
        second(dt);first(dt/2 if step==r-1 else dt)
    counts=dict(qc.count_ops());qc.save_superop()
    backend=AerSimulator(method='superop',max_parallel_threads=1)
    channel=np.asarray(backend.run(qc).result().data(0)['superop'].data)
    return channel,{'cx_per_step':int(counts.get('cx',0)),
                    'rx_per_step':int(counts.get('rx',0)),
                    'rz_per_step':int(counts.get('rz',0))}

def injection_channel(noise):
    qc=QuantumCircuit(4)
    thermal(qc,[0,1,2],noise,1.) # memory idles during 1 us input reset
    if noise.p1:qc.append(depolarizing_error(noise.p1,1).to_instruction(),[3])
    thermal(qc,range(4),noise,.035)
    qc.save_superop()
    return np.asarray(AerSimulator(method='superop',max_parallel_threads=1).run(qc).result().data(0)['superop'].data)

def trajectory(inputs,channel,inj,noise):
    step=channel@inj
    rho=np.zeros((16,16),complex);rho[0,0]=1
    out=np.empty((len(inputs),16,16),complex)
    for t,value in enumerate(inputs):
        theta=np.arcsin(np.sqrt(value))*(1+noise.angle_scale)
        psi=np.array([np.cos(theta),np.sin(theta)]);exc=np.array([-np.sin(theta),np.cos(theta)])
        eta=(1-noise.reset_excited)*np.outer(psi,psi)+noise.reset_excited*np.outer(exc,exc)
        memory=np.trace(rho.reshape(2,8,2,8),axis1=0,axis2=2)
        rho=(step@np.kron(eta,memory).reshape(256,order='F')).reshape(16,16,order='F')
        out[t]=rho
    return out

def measurement_design(names,indices,view):
    if view=='local_XZ_ZZ':settings=['XXXX','ZZZZ']
    elif view=='all_1_2body':
        settings=[''.join('XYZ'[k] for k in (s,t,(s+t)%3,(s+2*t)%3)) for s in range(3) for t in range(3)]
    else:settings=[''.join(x) for x in itertools.product('XYZ',repeat=4)]
    assignment=[]
    for idx in indices:
        assignment.append(next(k for k,s in enumerate(settings) if all(p=='I' or p==q for p,q in zip(names[idx],s))))
    bits=((np.arange(16)[:,None] >> np.arange(3,-1,-1))&1)
    parity=np.array([(-1.)**bits[:,[j for j,p in enumerate(names[i]) if p!='I']].sum(1) for i in indices]).T
    # Projectors, with rows in computational outcome order, matching big-endian names.
    h=np.array([[1,1],[1,-1]],complex)/np.sqrt(2)
    rotations={'Z':np.eye(2),'X':h,'Y':h@np.diag([1,-1j])}
    projectors=[]
    for setting in settings:
        u=np.array([[1]],complex)
        for letter in setting:u=np.kron(u,rotations[letter])
        projectors.extend(np.outer(row.conj(),row) for row in u)
    return settings,np.array(assignment),parity,np.array(projectors)

def probabilities(traj,design,noise):
    settings,assignment,parity,projectors=design
    p=features(traj,projectors).reshape(len(traj),len(settings),16)
    # Independent asymmetric assignment errors; outcome correlations are retained.
    one=np.array([[1-noise.read01,noise.read01],[noise.read10,1-noise.read10]])
    confusion=one
    for _ in range(3):confusion=np.kron(confusion,one)
    p=p@confusion
    if p.min() < -1e-9:raise ValueError('Nonphysical probability')
    p=np.maximum(p,0);p/=p.sum(-1,keepdims=True)
    return p

def sample_features(p,design,shots,rng):
    _,assignment,parity,_=design
    out=np.empty((len(p),len(assignment)))
    for k in range(p.shape[1]):
        ids=np.flatnonzero(assignment==k)
        if not len(ids):continue
        counts=rng.multinomial(shots,p[:,k,:])
        out[:,ids]=(counts@parity[:,ids])/shots
    return out

def evaluate(x,y):
    model,alpha,val=ridge_prepare(x,y)
    nr,cap=ridge_test(model,x,y)
    return nr,cap

def run(out,blocks):
    out.mkdir(parents=True,exist_ok=True)
    names,ops,views=pauli_basis()
    designs={v:measurement_design(names,ids,v) for v,ids in views.items()}
    rows=[];profiles=[];costs=[];checks=[]
    manifest={'status':'exploratory; synthetic noise; no physical QPU',
        'blocks':list(range(500,500+blocks)),'noises':{k:asdict(v) for k,v in NOISES.items()},
        'cases':CASES,'length':LENGTH,'train':TRAIN.tolist(),'validation':VAL.tolist(),'test':TEST.tolist(),
        'shots_per_group_equal':4096,'matched_CX_shots_per_step':2*4096*24,
        'ridge_alphas':NOISE_ALPHAS,'analysis_revision':'extended validation-only regularization after exploratory diagnostics; not confirmatory',
        'measurement_groups':{v:len(d[0]) for v,d in designs.items()},
        'measurement':'independent full-prefix replay per group and shot; no in-place nondestructive readout',
        'schedule':'serial; RX35ns,CX300ns,RZvirtual; all qubits relax during RX/CX; memory idle during reset1us',
        'limitations':['ideal measurement basis rotations','no crosstalk/leakage/drift or routing','no backend calibration','one shot realization per independent block','CX-shot budget excludes wall-clock/reset overhead'],
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    injections={k:injection_channel(n) for k,n in NOISES.items()}
    start=time.time()
    for block in range(500,500+blocks):
        data,_=data_for_block(block)
        ui=np.random.default_rng(958000+block).uniform(0,1,LENGTH)
        targets,labels=memory_targets(ui)
        datasets={'memory':(ui,targets),**data}
        for case,(tau,kind,r) in CASES.items():
            cfg=ReservoirConfig(n_qubits=4,evolution_time=tau,disorder_seed=938000+block)
            for noisename,noise in NOISES.items():
                channel,resource=make_channel(cfg,kind,r,noise)
                for task,(inputs,target) in datasets.items():
                    traj=trajectory(inputs,channel,injections[noisename],noise)
                    sample=traj[::100]
                    herm=float(np.max(abs(sample-sample.conj().transpose(0,2,1))))
                    eigmin=float(np.linalg.eigvalsh(sample).min());traceerr=float(np.max(abs(np.trace(traj,axis1=1,axis2=2)-1)))
                    assert herm<1e-8 and eigmin>-1e-8 and traceerr<1e-8
                    err=0.
                    if noisename=='ideal':
                        ref=states(inputs[:30],unitary(cfg,kind,r))
                        err=float(np.max(abs(traj[:30]-ref)));assert err<1e-9
                    checks.append(dict(block=block,case=case,noise=noisename,task=task,hermiticity=herm,min_eigenvalue=eigmin,trace_error=traceerr,ideal_error=err))
                    for vi,(view,ids) in enumerate(views.items()):
                        design=designs[view];p=probabilities(traj,design,noise)
                        for budget in ('expectation','equal_shots','equal_CX_budget'):
                            group_count=len(design[0])
                            shots=0 if budget=='expectation' else (4096 if budget=='equal_shots' else (2*4096*24)//(group_count*resource['cx_per_step']))
                            if budget=='expectation':
                                # Still contains assignment errors for noisy scenarios.
                                f=np.empty((LENGTH,len(ids)))
                                for k in range(group_count):
                                    which=np.flatnonzero(design[1]==k)
                                    f[:,which]=p[:,k,:]@design[2][:,which]
                            else:
                                rng=np.random.default_rng(12300000+block*100+list(CASES).index(case)*10+vi)
                                f=sample_features(p,design,shots,rng)
                            x=f if task=='memory' else np.column_stack([inputs,f])
                            nr,cap=evaluate(x,target)
                            common=dict(block=block,case=case,noise=noisename,task=task,view=view,budget=budget,shots_per_group=shots)
                            if task=='memory':
                                for j,(family,d) in enumerate(labels):profiles.append(dict(**common,family=family,delay=d,capacity=float(cap[j])))
                                summary={family+'20':float(cap[20*k:20*(k+1)].sum()) for k,family in enumerate(('linear','product','quadratic'))}
                                rows.append(dict(**common,nrmse='',**summary))
                            else:rows.append(dict(**common,nrmse=float(nr[0]),linear20='',product20='',quadratic20=''))
                            # Include every replayed prefix, including washout/gaps (conservative).
                            if task=='memory':costs.append(dict(**common,**resource,groups=group_count,
                                circuit_shots=shots*group_count*LENGTH,
                                full_replay_CX_shots=shots*group_count*resource['cx_per_step']*LENGTH*(LENGTH+1)//2))
                print(f'block={block} {case} {noisename} elapsed={time.time()-start:.1f}s',flush=True)
        save_csv(out/'scores.csv',rows);save_csv(out/'profiles.csv',profiles);save_csv(out/'costs.csv',costs);save_csv(out/'checks.csv',checks)
    print(f'DONE {len(rows)} scores {len(profiles)} profile entries',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--blocks',type=int,default=8);p.add_argument('--out',type=Path,default=Path('analysis_output/qrc_h3_noise'))
    a=p.parse_args();run(a.out,a.blocks)
