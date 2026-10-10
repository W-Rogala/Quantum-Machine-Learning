import unittest
from dataclasses import replace
import numpy as np
from quantum_reservoir.core import ReservoirConfig,QuantumReservoir,inject_input
from quantum_reservoir.h3_memory_study import (
    pauli_basis,states,features,unitary,reduced_channel,memory_targets,ridge_prepare,ridge_test,
)
from quantum_reservoir.spectral_h1_h2_study import TRAIN,VAL,TEST,LENGTH,fit,predict


class H3Checks(unittest.TestCase):
    def test_local_features_match_existing_module(self):
        _,ops,views=pauli_basis();cfg=ReservoirConfig(n_qubits=4,method="trotter",trotter_order=2,trotter_steps=2)
        inputs=np.random.default_rng(81).uniform(0,1,30)
        expected,_=QuantumReservoir(cfg).transform(inputs)
        actual=features(states(inputs,unitary(cfg,"ABA",2)),ops[views["local_XZ_ZZ"]])
        np.testing.assert_allclose(actual,expected,atol=1e-11)

    def test_reduced_and_full_nonzero_channel_spectra(self):
        cfg=ReservoirConfig(n_qubits=4);u=unitary(cfg,"exact")
        cols=[]
        for k in range(256):
            e=np.zeros((16,16),complex);e.flat[k]=1
            cols.append((u@inject_input(e,.5)@u.conj().T).reshape(-1))
        ev=np.linalg.eigvals(np.column_stack(cols));idx=np.argmin(abs(ev-1))
        radius=max(abs(np.delete(ev,idx)))
        self.assertAlmostEqual(radius,reduced_channel(u)["subradius"],places=9)

    def test_resonance_has_no_delayed_signal_in_initial_zero_environment(self):
        cfg=ReservoirConfig(n_qubits=4,evolution_time=np.pi/.9)
        u=unitary(cfg,"ABA",2)
        a=states([.2,.4,.7],u)[-1];b=states([.8,.9,.7],u)[-1]
        np.testing.assert_allclose(a,b,atol=1e-11)

    def test_multitarget_ridge_matches_direct_solver(self):
        rng=np.random.default_rng(54);x=rng.normal(size=(LENGTH,7));y=rng.normal(size=(LENGTH,3))
        model,alpha,_=ridge_prepare(x,y);err,_=ridge_test(model,x,y)
        for j in range(3):
            ids=np.r_[TRAIN,VAL];pred=predict(fit(x[ids],y[ids,j],alpha[j]),x[TEST])
            ref=np.sqrt(np.mean((pred-y[TEST,j])**2)/np.var(y[TEST,j]))
            self.assertAlmostEqual(float(err[j]),float(ref),places=11)

    def test_targets_use_only_past_inputs(self):
        u=np.random.default_rng(9).uniform(0,1,LENGTH);a,labels=memory_targets(u)
        changed=u.copy();changed[900:]=.5;b,_=memory_targets(changed)
        np.testing.assert_array_equal(a[21:900],b[21:900])
        self.assertEqual(len(labels),60)

    def test_test_tail_does_not_affect_validation_choice(self):
        rng=np.random.default_rng(20);x=rng.normal(size=(LENGTH,9));y=rng.normal(size=(LENGTH,2))
        model,a,v=ridge_prepare(x,y);x[TEST]*=100;y[TEST]*=100
        model2,a2,v2=ridge_prepare(x,y)
        np.testing.assert_array_equal(a,a2);np.testing.assert_allclose(v,v2)
        for first,second in zip(model,model2):np.testing.assert_allclose(first,second)


if __name__=="__main__":unittest.main()
