"""Separate audit calculations; no imports from report-generating code."""
import os
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
import csv,json,hashlib,itertools,platform
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from scipy.stats import t,binomtest

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis_output/qrc_independent_audit'
def read(folder,name):
    with (ROOT/'analysis_output'/folder/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def select(rows,**kw):return [r for r in rows if all(str(r[k])==str(v) for k,v in kw.items())]
def vec(rows,col,**kw):return np.array([float(r[col]) for r in sorted(select(rows,**kw),key=lambda r:int(r['block']))])
def stats(x,ratio=False):
    n=len(x);m=np.mean(x);h=t.ppf(.975,n-1)*np.std(x,ddof=1)/np.sqrt(n)
    rng=np.random.default_rng(20260907)
    boot=np.mean(x[rng.integers(0,n,(20000,n))],axis=1)
    ci=np.percentile(boot,[2.5,97.5])
    lod=np.array([np.mean(np.delete(x,j)) for j in range(n)])
    vals=np.array([m,m-h,m+h,*ci,lod.min(),lod.max()])
    if ratio:vals=np.exp(vals)
    nz=x[abs(x)>1e-12]
    return dict(zip(('estimate','t_low','t_high','bootstrap_low','bootstrap_high','loo_low','loo_high'),map(float,vals)),
                sign_p=float(binomtest(int(sum(nz>0)),len(nz),.5).pvalue) if len(nz) else 1.,n=n)

def main():
    OUT.mkdir(parents=True,exist_ok=True);audit={};integrity=[]
    for folder in ('qrc_spectral_h1_h2','qrc_h3_memory','qrc_h3_noise'):
        base=ROOT/'analysis_output'/folder
        for name,digest in json.loads((base/'artifact_hashes.json').read_text()).items():
            p=base/name
            if name=='study_source_current':p=ROOT/'quantum_reservoir/spectral_h1_h2_study.py'
            if name=='report_source':p=ROOT/'quantum_reservoir'/('spectral_h1_h2_report.py' if folder=='qrc_spectral_h1_h2' else 'h3_report.py')
            integrity.append(dict(folder=folder,file=name,exists=p.exists(),matches=p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==digest))
    audit['integrity']=integrity
    audit['integrity_failures']=[r for r in integrity if not r['matches']]
    print('Integrity discrepancies:',json.dumps(audit['integrity_failures']),flush=True)
    q=read('qrc_spectral_h1_h2','qubit_results.csv');summary=read('qrc_spectral_h1_h2','qubit_summary.csv')
    rec=[]
    for case in sorted({r['case'] for r in q}):
        for kind in ('H1_fixed_p2r2','H2_val_selected'):
            effects=[]
            for b in range(8):
                dd=[]
                for task in ('NARMA10','MG5'):
                    rr=select(q,case=case,block=b,task=task)
                    ref=next(r for r in rr if r['p']=='0')
                    chosen=next(r for r in rr if (r['p']=='2' and r['r']=='2') if kind=='H1_fixed_p2r2') if kind=='H1_fixed_p2r2' else next(r for r in rr if r['selected']=='True')
                    dd.append(np.log(float(chosen['test_nrmse'])/float(ref['test_nrmse'])))
                effects.append(np.mean(dd))
            ss=stats(np.array(effects),True);old=select(summary,case=case,hypothesis=kind)[0]
            assert abs(ss['estimate']-float(old['geomean_error_ratio']))<1e-11
            rec.append(dict(case=case,hypothesis=kind,**ss))
    audit['H1_H2']=rec
    follow=read('qrc_spectral_h1_h2','followup_results.csv');ff=[]
    for family in ('fixed_exact','tuned_exact','lag_ridge','polynomial_lags'):
        effects=[]
        for block in range(100,108):
            e=[]
            for task in ('NARMA10','MG5'):
                a=vec(follow,'test_nrmse',block=block,task=task,family='selected_trotter')[0]
                b=vec(follow,'test_nrmse',block=block,task=task,family=family)[0];e.append(np.log(a/b))
            effects.append(np.mean(e))
        ff.append(dict(reference=family,**stats(np.array(effects),True)))
    audit['followup']=ff
    profiles=read('qrc_h3_memory','profiles.csv');sums={}
    for r in profiles:
        key=tuple(r[k] for k in ('phase','regime','block','method','view'))
        rr=sums.setdefault(key,dict(linear20=0.,product20=0.,quadratic20=0.,T=0.,count=0))
        rr[r['target']+'20']+=float(r['capacity']);rr['count']+=1
        if int(r['delay'])<=10 and r['target'] in ('linear','product'):
            rr['T']+=float(r['capacity'])*(.1 if r['target']=='product' else -.1)
    assert all(s['count']==60 for s in sums.values())
    h3=[]
    for regime in ('standard','coarse','resonance'):
        effects=np.array([sums[('core',regime,str(b),'AB_r1','local_XZ_ZZ')]['T']-sums[('core',regime,str(b),'fixed_exact','local_XZ_ZZ')]['T'] for b in range(300,308)])
        h3.append(dict(regime=regime,**stats(effects)))
    audit['H3']=h3
    noise=read('qrc_h3_noise','scores.csv');cost=read('qrc_h3_noise','costs.csv')
    nstats=[]
    for task in ('NARMA10','MG5'):
        for budget in ('equal_shots','equal_CX_budget'):
            kw=dict(task=task,noise='mild',view='local_XZ_ZZ',budget=budget)
            a=vec(noise,'nrmse',case='coarse_ABA2',**kw);b=vec(noise,'nrmse',case='coarse_ABA16',**kw)
            nstats.append(dict(task=task,budget=budget,**stats(np.log(a/b),True)))
    audit['noise_prediction']=nstats
    audit['noise_memory']=[]
    for case in ('coarse_ABA2','coarse_BAB2','coarse_ABA16','resonance_ABA2'):
        for view in ('local_XZ_ZZ','all_1_2body','full_Pauli'):
            row=dict(case=case,view=view)
            for nn,budget,label in [('ideal','expectation','ideal_expectation'),('ideal','equal_CX_budget','shots'),('mild','equal_CX_budget','mild'),('stress','equal_CX_budget','stress')]:
                row[label]=float(np.mean(vec(noise,'linear20',case=case,view=view,task='memory',noise=nn,budget=budget)))
            audit['noise_memory'].append(row)
    for row in cost:
        shots=int(row['shots_per_group']);g=int(row['groups']);cx=int(row['cx_per_step'])
        assert int(row['full_replay_CX_shots'])==shots*g*cx*1360*1361//2
        if row['budget']=='equal_CX_budget':assert 0<=196608-shots*g*cx<g*cx
    audit['cost_rows_checked']=len(cost)
    # Independent Hamiltonian and partial trace, compared with production implementation.
    import sys
    sys.path.insert(0,str(ROOT))
    from quantum_reservoir.core import ReservoirConfig
    from quantum_reservoir.h3_memory_study import unitary,states,reduced_channel
    cfg=ReservoirConfig(evolution_time=3.2,disorder_seed=441)
    ident=np.eye(2);px=np.array([[0,1],[1,0]]);pz=np.diag([1,-1])
    def embed(mat,k):
        op=np.array([[1.]])
        for j in range(4):op=np.kron(op,mat if j==k else ident)
        return op
    zs=[embed(pz,k) for k in range(4)];xs=[embed(px,k) for k in range(4)]
    fields=np.random.default_rng(441).uniform(-.5,.5,4)
    aa=sum(h*z for h,z in zip(fields,zs))+.7*sum(zs[i]@zs[j] for i,j in [(0,1),(1,2),(2,3),(3,0)])
    bb=.9*sum(xs);errors=[]
    for kind in ('exact','ABA','BAB'):
        if kind=='exact':uu=expm(-1j*3.2*(aa+bb))
        else:
            first,second=(aa,bb) if kind=='ABA' else (bb,aa)
            half=expm(-1j*.8*first);middle=expm(-1j*1.6*second);ss=half@middle@half;uu=ss@ss
        errors.append(float(np.max(abs(uu-unitary(cfg,kind,2)))))
        rho=np.zeros((16,16),complex);rho[0,0]=1
        seq=np.random.default_rng(719).uniform(0,1,30);manual=[]
        for u in seq:
            memory=rho[:8,:8]+rho[8:,8:];psi=np.array([np.sqrt(1-u),np.sqrt(u)])
            rho=uu@np.kron(np.outer(psi,psi),memory)@uu.conj().T;manual.append(rho)
        errors.append(float(np.max(abs(np.array(manual)-states(seq,unitary(cfg,kind,2))))))
    assert max(errors)<1e-10
    audit['independent_dense_max_error']=max(errors)
    # Gaussian oscillator stability from explicit shear matrices, not production helper.
    dt=3.;shear_q=np.array([[1,dt/2],[0,1]]);shear_p=np.array([[1,0],[-dt,1]])
    symp=shear_q@shear_p@shear_q
    audit['CV_large_step_radius']=float(max(abs(np.linalg.eigvals(np.sqrt(.8)*symp))))
    # Repeated channels: frozen-input spectral radius does not establish switching ESP.
    audit['scope']={'independent_reporting':True,'independent_implementation_spot_checks':True,
       'full_independent_reimplementation':False,'external_reviewer':False,
       'all_training_runs_repeated_for_audit':False,'physical_QPU':False}
    audit['environment']={'python':platform.python_version(),'numpy':np.__version__}
    audit['source_hash']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ('integrity','H1_H2','noise_memory')},indent=2))
    print('Integrity entries checked:',len(integrity))

if __name__=='__main__':main()
