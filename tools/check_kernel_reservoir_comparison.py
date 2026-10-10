"""Algebraic sanity checks for the comparison report; not an ML benchmark."""
import os
for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import json,itertools,hashlib
import numpy as np
from scipy.linalg import expm

out=Path('analysis_output/kernel_reservoir_comparison');out.mkdir(parents=True,exist_ok=True)
i=np.eye(2);x=np.array([[0,1],[1,0]]);y=np.array([[0,-1j],[1j,0]]);z=np.diag([1,-1])
ops=np.array([np.kron(a,b) for a,b in itertools.product((i,x,y,z),repeat=2)])[1:]
rng=np.random.default_rng(20260907)
psi=rng.normal(size=(9,4))+1j*rng.normal(size=(9,4));psi/=np.linalg.norm(psi,axis=1,keepdims=True)
rho=np.einsum('ni,nj->nij',psi,psi.conj())
def gram(r):return np.einsum('aij,bji->ab',r,r).real
def feat(r,obs):return np.einsum('aij,kji->ak',r,obs).real
a=.7*np.kron(z,z)+.3*np.kron(z,i);b=.9*np.kron(x,i)+.6*np.kron(i,x)
v=expm(-1j*.7*a)@expm(-1j*1.4*b)@expm(-1j*.7*a)
changed=v@rho@v.conj().T
invariance=float(np.max(abs(gram(changed)-gram(rho))))
local=np.array([np.kron(z,i),np.kron(i,z)])
projection=float(np.linalg.norm(feat(changed,local)@feat(changed,local).T-feat(rho,local)@feat(rho,local).T))
f=feat(rho,ops);hs_error=float(np.max(abs(gram(rho)-(1+f@f.T)/4)))
# Pure states suffice to test the identity; also check genuinely mixed states.
mix=.6*rho+.4*np.eye(4)[None]/4;mf=feat(mix,ops)
mixed_error=float(np.max(abs(gram(mix)-(1+mf@mf.T)/4)))
ztrain=rng.normal(size=(35,12));ztest=rng.normal(size=(8,12));target=rng.normal(size=35)
mu=ztrain.mean(0);scale=ztrain.std(0);zt=(ztrain-mu)/scale;zs=(ztest-mu)/scale;yc=target-target.mean();lam=.7
pred1=zs@np.linalg.solve(zt.T@zt+lam*np.eye(12),zt.T@yc)+target.mean()
pred2=zs@zt.T@np.linalg.solve(zt@zt.T+lam*np.eye(35),yc)+target.mean()
dual=float(np.max(abs(pred1-pred2)))
def encoding(order):
    states=[]
    for u in np.linspace(.1,.9,9):
        aa=u*np.kron(z,i)+.6*np.kron(z,z);bb=.9*np.kron(x,i)+.8*np.kron(i,x)
        if order==0:uu=expm(-1j*1.2*(aa+bb))
        else:
            dt=1.2/order;h=expm(-1j*dt*aa/2);step=h@expm(-1j*dt*bb)@h;uu=np.linalg.matrix_power(step,order)
        v=uu[:,0];states.append(np.outer(v,v.conj()))
    return np.array(states)
k0=gram(encoding(0));k1=gram(encoding(1));k8=gram(encoding(8))
assert invariance<1e-12 and hs_error<1e-12 and mixed_error<1e-12 and dual<1e-11 and projection>.01
result={'status':'executed algebraic sanity checks; no predictive kernel benchmark',
 'common_unitary_HS_max_error':invariance,'projected_linear_gram_change_F':projection,
 'pauli_identity_pure_max_error':hs_error,'pauli_identity_mixed_max_error':mixed_error,
 'primal_dual_prediction_max_error':dual,
 'data_dependent_encoding_relative_gram_error_r1':float(np.linalg.norm(k1-k0)/np.linalg.norm(k0)),
 'data_dependent_encoding_relative_gram_error_r8':float(np.linalg.norm(k8-k0)/np.linalg.norm(k0)),
 'seed':20260907,'qubits':2,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'mathematical_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
