import unittest
import numpy as np
from quantum_reservoir.h3_noise_study import (
    Noise,NOISES,make_channel,injection_channel,trajectory,measurement_design,
    probabilities,sample_features,
)
from quantum_reservoir.core import ReservoirConfig
from quantum_reservoir.h3_memory_study import pauli_basis,states,unitary,features

class NoiseStudyChecks(unittest.TestCase):
    def test_zero_noise_matches_both_strang_orders(self):
        cfg=ReservoirConfig(evolution_time=3.2)
        u=np.random.default_rng(12).uniform(0,1,12)
        for kind in ('ABA','BAB'):
            channel,cost=make_channel(cfg,kind,2,Noise())
            actual=trajectory(u,channel,injection_channel(Noise()),Noise())
            np.testing.assert_allclose(actual,states(u,unitary(cfg,kind,2)),atol=1e-11)
            self.assertEqual(cost['cx_per_step'],24 if kind=='ABA' else 16)

    def test_noisy_channel_complete_positivity_and_trace(self):
        # Independent Qiskit Choi conversion, plus trajectory state validation.
        from qiskit.quantum_info import Choi,SuperOp
        channel,_=make_channel(ReservoirConfig(), 'ABA',2,NOISES['stress'])
        self.assertTrue(Choi(SuperOp(channel)).is_cptp())
        seq=trajectory(np.linspace(.01,.99,30),channel,injection_channel(NOISES['stress']),NOISES['stress'])
        np.testing.assert_allclose(np.trace(seq,axis1=1,axis2=2),1.,atol=1e-10)
        self.assertGreater(np.linalg.eigvalsh(seq).min(),-1e-10)

    def test_all_group_designs_recover_pauli_expectations(self):
        names,ops,views=pauli_basis()
        z=np.random.default_rng(72).normal(size=16)+1j*np.random.default_rng(73).normal(size=16)
        z/=np.linalg.norm(z);rho=np.outer(z,z.conj())[None]
        for view,ids in views.items():
            design=measurement_design(names,ids,view);p=probabilities(rho,design,Noise())
            actual=np.array([(p[0,k]@design[2][:,j]) for j,k in enumerate(design[1])])
            np.testing.assert_allclose(actual,features(rho,ops[ids])[0],atol=1e-12)

    def test_shared_bitstrings_preserve_bell_correlations(self):
        # Bell pair on q0/q1; Z0 and Z1 estimates must match exactly in each shot batch.
        names,ops,views=pauli_basis();ids=views['local_XZ_ZZ']
        vec=np.zeros(16);vec[0]=vec[12]=1/np.sqrt(2)
        design=measurement_design(names,ids,'local_XZ_ZZ')
        p=probabilities(np.repeat(np.outer(vec,vec)[None],100,axis=0),design,Noise())
        f=sample_features(p,design,17,np.random.default_rng(99))
        idx=[names[i] for i in ids]
        np.testing.assert_array_equal(f[:,idx.index('ZIII')],f[:,idx.index('IZII')])
        np.testing.assert_allclose(f[:,idx.index('ZZII')],1.)

    def test_asymmetric_readout_on_zero_state(self):
        names,ops,views=pauli_basis();ids=views['local_XZ_ZZ']
        rho=np.zeros((1,16,16));rho[0,0,0]=1
        design=measurement_design(names,ids,'local_XZ_ZZ')
        p=probabilities(rho,design,Noise(read01=.1,read10=.3))
        idx=[names[i] for i in ids].index('ZIII');k=design[1][idx]
        self.assertAlmostEqual(float(p[0,k]@design[2][:,idx]),.8)

if __name__=='__main__':unittest.main()
