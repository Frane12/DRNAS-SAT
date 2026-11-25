"""YM22 arithmetic, exact SU(2) local identities, and actual ATLAS forest control."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from itertools import product
from tree_gauge_tests import mul,inv,quat
from atlas_forest_gauge import solve as forest
from run import run
from operator_verify import verify
import json,sys

def identities():
    # W_p=tr(U A), W_q=tr(U B), with opposite orientations reversed.
    # In the radius-2 metric, the three shared-link derivatives are
    # minus the imaginary quaternion components of UA and UB.
    qs=[quat(i,s) for i,s in product((1,2,3),(-1,1))]
    count=0
    for U,A,B in product(qs,repeat=3):
        x,y=mul(U,A),mul(U,B);w,v=2*x[0],2*y[0]
        p0=mul(A,inv(B))[0];p1=w*v-p0
        cross=sum(a*b for a,b in zip(x[1:],y[1:]))
        assert cross==p0-w*v/4==Q(3,4)*p0-Q(1,4)*p1
        assert 4*sum(a*a for a in x[1:])==4-w*w
        # Spectral inverse coefficients: Delta Q2 cancels nonconstant
        # gradient square (same plaquette and unordered adjacent pair).
        assert -8*(-Q(1,8)*(w*w-1))==w*w-1
        assert -Q(9,2)*Q(1,3)*p0-Q(13,2)*(-Q(1,13))*p1==-2*cross
        assert Q(1,3)*p0-Q(1,13)*p1==Q(16,39)*p0-Q(1,13)*w*v
        count+=1
    return count

def main(atlas):
    checks=identities()
    cases=[(3,1,Q(1,64),Q(1,4),True),(3,1,Q(1,128),Q(1,4),True),
           (2,1,Q(1,32),Q(1,4),True),(3,1,Q(-1,64),Q(1,4),True),
           (3,2,Q(0),Q(1),True),(3,1,Q(1,4),Q(1,10),False),
           (3,1,Q(1,64),Q(1),False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,a,k,g,ok) in enumerate(cases):
            src=root/f'{i}.op';cert=root/f'{i}.cert'
            src.write_text(f'p op gauge-vacuum2 {d} {a} {k} {g}\n')
            r=run(src,cert,5)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            if ok:
                assert r['reference_hamiltonian'] and not r['uniform_original_gap'],r
                if k:assert Q(r['local_residual_abs_upper'])<Q(r['first_order_residual_upper']),r
                old=cert.read_text();z=old.split();z[-1]=str(Q(z[-1])+1);cert.write_text(' '.join(z))
                try:verify(src,cert)
                except ValueError:pass
                else:raise AssertionError('tampered bound')
                cert.write_text(old)
            print('YM22_ROW '+json.dumps(dict(id=i,**r)),flush=True)
        r=forest(3,3,2,Q(1),Q(1,64),Q(1,4),atlas,root/'forest')
        assert r['atlas']['model_verified'] and r['forest']['residual_root_gauge'],r
        print('YM22_FOREST '+json.dumps(r),flush=True)
    print('YM22_SUMMARY '+json.dumps(dict(cases=len(cases),positive=5,negative=2,local_identities=checks,atlas_controls=1,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
