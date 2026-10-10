"""Post-exploration sensitivity to extra warmup; paired input stream and readout."""
from pathlib import Path
import numpy as np
from quantum_reservoir.h3_memory_study import pauli_basis,unitary,states,features,memory_targets,ridge_prepare,ridge_test
from quantum_reservoir.core import ReservoirConfig
from quantum_reservoir.spectral_h1_h2_study import LENGTH,save_csv

def main():
    out=Path("analysis_output/qrc_h3_memory");_,ops,views=pauli_basis();rows=[]
    cases=[("standard_exact",.8,"exact",1),("standard_AB",.8,"AB",1),
           ("coarse_ABA",3.2,"ABA",2),("coarse_BAB",3.2,"BAB",2)]
    for case,tau,kind,r in cases:
        for b in range(300,308):
            cfg=ReservoirConfig(n_qubits=4,evolution_time=tau,disorder_seed=938000+b);u=unitary(cfg,kind,r)
            inputs=np.random.default_rng(958000+b).uniform(0,1,LENGTH);target,labels=memory_targets(inputs)
            prefix=np.random.default_rng(988000+b).uniform(0,1,10000)
            for warmup in (0,2000,10000):
                history=np.r_[prefix[:warmup],inputs]
                trajectory=states(history,u)[-LENGTH:];f=features(trajectory,ops)
                for view in ("local_XZ_ZZ","full_Pauli"):
                    ids=views[view];model,alpha,val=ridge_prepare(f[:,ids],target);_,capacity=ridge_test(model,f[:,ids],target)
                    rows.append({"case":case,"block":b,"extra_warmup":warmup,"view":view,
                        "linear20":float(sum(capacity[:20])),"product20":float(sum(capacity[20:40])),
                        "quadratic20":float(sum(capacity[40:]))})
            save_csv(out/"washout_sensitivity.csv",rows)
            print(f"washout {case} {b-299}/8",flush=True)

if __name__=="__main__":main()
