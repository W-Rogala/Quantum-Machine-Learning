"""Distinguish transient AB memory from invariant maximally mixed memory."""
from pathlib import Path
import numpy as np
from quantum_reservoir.h3_memory_study import pauli_basis,unitary,features,memory_targets,ridge_prepare,ridge_test
from quantum_reservoir.core import ReservoirConfig,inject_input
from quantum_reservoir.spectral_h1_h2_study import LENGTH,save_csv

def main():
    _,ops,views=pauli_basis();rows=[]
    for b in range(300,308):
        inputs=np.random.default_rng(958000+b).uniform(0,1,LENGTH)
        u=unitary(ReservoirConfig(n_qubits=4,evolution_time=.8,disorder_seed=938000+b),"AB",1)
        rho=np.kron(np.diag([1.,0.]),np.eye(8)/8).astype(complex)
        traj=[];dist=0
        for val in inputs:
            rho=u@inject_input(rho,float(val))@u.conj().T
            sigma=np.trace(rho.reshape(2,8,2,8),axis1=0,axis2=2)
            dist=max(dist,float(np.linalg.norm(sigma-np.eye(8)/8,ord="nuc")/2))
            traj.append(rho.copy())
        f=features(np.array(traj),ops);target,_=memory_targets(inputs)
        for view in ("local_XZ_ZZ","full_Pauli"):
            ids=views[view];model,alpha,val=ridge_prepare(f[:,ids],target);_,c=ridge_test(model,f[:,ids],target)
            rows.append({"block":b,"view":view,"initial_memory":"I/8","max_distance_memory_from_I8":dist,
                "linear20":float(sum(c[:20])),"product20":float(sum(c[20:40])),"quadratic20":float(sum(c[40:]))})
    save_csv(Path("analysis_output/qrc_h3_memory/stationary_AB_check.csv"),rows)
    print(rows,flush=True)

if __name__=="__main__":main()
