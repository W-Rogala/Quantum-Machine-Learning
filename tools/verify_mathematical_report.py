"""Independent small-matrix checks for derivations, plus document integrity.

These are algebraic examples, not new scientific benchmark experiments.
No external service, training or QPU execution is performed.
"""
from __future__ import annotations
import hashlib, importlib.util, json, math, sqlite3, sys
from pathlib import Path
import numpy as np
from scipy.linalg import expm

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hamiltonian_kernel.core import EvolutionConfig, evolve_trotter
DOC=ROOT/'docs/mathematical_report'

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module

def main():
    checks=[]
    def check(name,ok,details):
        checks.append(dict(name=name,passed=bool(ok),classification='algebraic-check',details=details))
        if not ok:raise AssertionError(name+': '+str(details))
    rng=np.random.default_rng(5102026)
    X=np.array([[0,1],[1,0]],complex);Y=np.array([[0,-1j],[1j,0]]);Z=np.diag([1,-1]);I=np.eye(2)
    kron=np.kron;norm=lambda m:float(np.linalg.norm(m,2))
    scar=load_module('experiments/legacy/vqe_scar_ansatz_experiment.py','report_scar')
    max_gate=max_unit=max_phase=0.
    H0=(kron(X,X)+kron(Y,Y))/2
    for theta,delta,phi in rng.normal(size=(16,3)):
        H=(np.cos(delta)*(kron(X,X)+kron(Y,Y))+np.sin(delta)*(kron(Y,X)-kron(X,Y)))/2
        D=kron(expm(-1j*delta*Z/4),expm(1j*delta*Z/4))
        expected=expm(-1j*phi*kron(Z,Z)/2)@expm(-1j*theta*H)
        actual=scar.scar(theta,delta,phi)
        max_gate=max(max_gate,norm(actual-expected));max_unit=max(max_unit,norm(actual.conj().T@actual-np.eye(4)))
        max_phase=max(max_phase,norm(H-D@H0@D.conj().T))
    check('SCAR exact generator, unitarity and local XY conjugacy',max(max_gate,max_unit,max_phase)<1e-12,dict(cases=16,max_gate=max_gate,max_unit=max_unit,max_conjugacy=max_phase))
    collapse=[]
    x=np.array([.1,.4,-.8]);z=np.array([-.3,.7,.2]);t=.83
    expected=float(np.prod(np.cos(t*(x-z))**2))
    for topology in ('chain','ring','all_to_all'):
        for coupling,field in ((0.,0.),(.3,.7),(1.2,-.2)):
            conf=EvolutionConfig(3,evolution_time=t,interaction_strength=coupling,transverse_field=field,topology=topology,trotter_order=1,trotter_steps=1)
            overlap=float(abs(np.vdot(evolve_trotter(x,conf),evolve_trotter(z,conf)))**2)
            collapse.append(abs(overlap-expected))
    check('One-slice first-order fidelity cancellation',max(collapse)<1e-12,dict(cases=9,max_error=max(collapse),expected=expected))
    comm=lambda a,b:a@b-b@a
    errors=[]
    for r in (1,2,4,8,16):
        t=.9;h=t/r;A=.7*X;B=1.1*Z;exact=expm(-1j*t*(A+B))
        lie=np.linalg.matrix_power(expm(-1j*h*A)@expm(-1j*h*B),r)
        strang=np.linalg.matrix_power(expm(-1j*h*A/2)@expm(-1j*h*B)@expm(-1j*h*A/2),r)
        b1=t*t*norm(comm(A,B))/(2*r)
        b2=t**3*(norm(comm(A,comm(A,B)))/24+norm(comm(B,comm(A,B)))/12)/r**2
        e1=norm(lie-exact);e2=norm(strang-exact);errors.append(dict(r=r,lie=e1,strang=e2,lie_bound=b1,strang_bound=b2))
        check('Finite matrix Trotter bounds r='+str(r),e1<=b1+1e-12 and e2<=b2+1e-12,errors[-1])
    K=np.array([[1,.9,.9],[.9,1,0],[.9,0,1]])
    mu=float(np.linalg.eigvalsh(K)[0]);coefficient=mu*(mu+.3)
    check('Indefinite KRR counterexample despite shifted positive matrix',mu<0 and mu+.3>0 and coefficient<0,dict(min_eigenvalue=mu,lambda_=.3,quadratic_coefficient=coefficient))
    F=rng.normal(size=(9,4));y=rng.normal(size=9);lam=.15
    w=np.linalg.solve(F.T@F+lam*np.eye(4),F.T@y);a=np.linalg.solve(F@F.T+lam*np.eye(9),y)
    check('Ridge primal-dual on rank deficient Gram',np.max(np.abs(w-F.T@a))<1e-12,dict(max_error=float(np.max(np.abs(w-F.T@a))),rank=int(np.linalg.matrix_rank(F@F.T))))
    # Even QSVT: positive singular directions plus the kernel exactly once.
    A=np.array([[2.,0.,0.],[0.,0.,0.]])
    _,sv,Vh=np.linalg.svd(A,full_matrices=True);V=Vh.T;positive=sv>1e-12
    support=V[:,:len(sv)][:,positive];kernel=V[:,int(positive.sum()):]
    constant=support@support.T+kernel@kernel.T
    square=support@np.diag((sv[positive]/2)**2)@support.T
    check('Even QSVT zero singular subspace counted once',norm(constant-np.eye(3))<1e-12 and norm(square-A.T@A/4)<1e-12,dict(constant_error=norm(constant-np.eye(3)),square_error=norm(square-A.T@A/4)))
    omega=1.;h=3.;eta=.8;G=np.array([[0,1],[-omega**2,0]])
    SA=lambda h:np.array([[1,h],[0,1]])
    SB=lambda h:np.array([[1,0],[-omega**2*h,1]])
    exact=expm(h*G);strang=SA(h/2)@SB(h)@SA(h/2)
    rex=float(max(abs(np.linalg.eigvals(np.sqrt(eta)*exact))));rst=float(max(abs(np.linalg.eigvals(np.sqrt(eta)*strang))))
    check('CV symplectic but unstable Strang',abs(np.linalg.det(strang)-1)<1e-12 and rex<1 and rst>1,dict(exact_radius=rex,strang_radius=rst,strang_trace=float(np.trace(strang))))
    eps=.1;cov=np.array([[1,(1-eps**2)/(1+eps**2)],[(1-eps**2)/(1+eps**2),1]])
    vals,vecs=np.linalg.eigh(cov);signal=np.array([1,-1])*eps/np.sqrt(1+eps**2)
    check('Standardized PCA retains variance and loses all label signal',abs(vecs[:,-1]@signal)<1e-12 and vals[-1]/sum(vals)>.99,dict(retained_variance=float(vals[-1]/sum(vals)),label_projection=float(vecs[:,-1]@signal)))
    n=2;eta=.5;p=sum(math.comb(n,k)*eta**k*(1-eta)**(n-k) for k in range(1,n+1))
    check('Loss and threshold do not commute',abs(p-.75)<1e-12 and eta==.5,dict(correct=p,threshold_first=eta))
    for d in (2,4,8):
        a=np.diag(np.sqrt(np.arange(1,d)),1);target=np.eye(d);target[-1,-1]-=d
        check('Cutoff commutator d='+str(d),norm(comm(a,a.T)-target)<1e-12,dict(operator_error_from_identity=norm(comm(a,a.T)-np.eye(d))))
    # Same injected qubit, orthogonal memory: reset preserves trace distance 1.
    v=np.array([np.sqrt(.3),np.sqrt(.7)]);state=np.outer(v,v)
    rho=kron(np.diag([1,0]),np.diag([1,0]));sigma=kron(np.diag([1,0]),np.diag([0,1]))
    trace_distance=lambda a,b:float(np.linalg.svd(a-b,compute_uv=False).sum()/2)
    before=trace_distance(rho,sigma);after=trace_distance(kron(state,np.diag([1,0])),kron(state,np.diag([0,1])))
    check('One-qubit reset coefficient is one for n>=2',before==after==1.,dict(before=before,after=after))
    p=14/35;n=35;z=1.959963984540054;den=1+z*z/n
    centre=(p+z*z/(2*n))/den;half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    check('Wilson accuracy interval',.255<centre-half<.257 and .563<centre+half<.565,dict(estimate=p,low=float(centre-half),high=float(centre+half)))
    manifest=json.loads((DOC/'source_manifest.json').read_text(encoding='utf8'));bad=[]
    for r in manifest:
        p=ROOT/r['path']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256'] and hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=r.get('sha256_lf'):bad.append(r['path'])
    check('Source snapshot integrity',not bad,dict(files=len(manifest),changed=bad))
    refs=json.loads((DOC/'bibliography/references.json').read_text(encoding='utf8'));cit=json.loads((DOC/'citations.json').read_text(encoding='utf8'))
    ids={r['id'] for r in refs}
    check('Bibliographic keys resolve',all(r['key'] in ids for r in cit),dict(sources=len(ids),citations=len(cit)))
    with sqlite3.connect(DOC/'bibliography/report.sqlite') as con:
        n=con.execute('SELECT count(*) FROM sources').fetchone()[0]
        count=con.execute('SELECT count(*) FROM hypotheses').fetchone()[0]
    check('SQLite matches reviewed sources and hypotheses',n==len(refs) and count==21,dict(sources=n,hypotheses=count))
    queries=json.loads((DOC/'snapshot.json').read_text(encoding='utf8'))['queries']
    check('Chart rows exist and memory components are paired',len(queries['memory-components']['rows'])==9,dict(rows={k:len(v['rows']) for k,v in queries.items() if k in ('hk-comparison','qrc-spectral','memory-components','noise-ratio','noise-difference','memory-contrast')}))
    result=dict(status='PASS',classification='algebraic-and-document-integrity-checks',not_benchmark=True,checks=checks)
    (DOC/'verification').mkdir(exist_ok=True)
    (DOC/'verification/algebra_and_integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(status='PASS',checks=len(checks)),ensure_ascii=False))

if __name__=='__main__':main()
