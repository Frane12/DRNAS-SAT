"""YM24 checks exact arithmetic and local spin inequalities, not a formal proof."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from itertools import product,combinations
from collections import Counter
from run import run
from operator_verify import verify
from atlas_forest_gauge import solve as forest
import json,sys

def spin_checks():
    spins=[Q(i,2) for i in range(13)]
    count=0
    for j,k in product(spins,repeat=2):
        assert j<=Q(2,3)*j*(j+1)
        for m in range(int(2*abs(j-k)),int(2*(j+k))+1,2):
            l=Q(m,2)
            assert l<=j+k and 1+l<=(1+j)*(1+k)
            count+=1
    return count

def incidence(d,L):
    c=Counter()
    for x in product(range(L),repeat=d):
        for i,j in combinations(range(d),2):
            if x[i]+1>=L or x[j]+1>=L:continue
            a=list(x);a[i]+=1;b=list(x);b[j]+=1
            for e in [(x,i),(tuple(a),j),(tuple(b),i),(x,j)]:c[e]+=1
    return max(c.values())

def main(atlas):
    count=spin_checks()
    with TemporaryDirectory() as tmp:
        root=Path(tmp);cases=[]
        for d in (2,3,4):
            limit=Q(1,576*2*(d-1))
            cases.extend([(d,Q(1),limit,Q(1,3),8,True),
                (d,Q(2),-limit,Q(2,3),16,True),
                (d,Q(1),limit/2,Q(1,4),32,True),
                (d,Q(1),limit*2,Q(1,4),8,False)])
        cases.extend([(3,Q(1),Q(0),Q(1,3),4,True),(3,Q(1),Q(1,4096),Q(1,2),8,False)])
        for i,(d,a,u,g,n,ok) in enumerate(cases):
            s=root/f'{i}.op';c=root/f'{i}.cert'
            s.write_text(f'p op gauge-local-vacuum {d} {a} {a*u} {g} {n}\n')
            r=run(s,c,5)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            if ok:
                assert r['original_KS_uniform_gap'] and not r['coefficients_generated']
                assert Q(r['gap_lower'])==a/3 and Q(r['contraction_factor'])==Q(2,3)
                old=c.read_text();w=old.split();w[-1]=str(Q(w[-1])+1);c.write_text(' '.join(w))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered tail')
                c.write_text(old)
            print('YM24_ROW '+json.dumps(dict(id=i,**r)),flush=True)
        for d,L in product((2,3,4),(2,3,4)):
            assert incidence(d,L)<=2*(d-1)
        # Actual ATLAS/CORE finite-grid control. It does not establish the
        # analytic infinite-order result and uses the prior finite bound.
        r=forest(3,3,2,Q(1),Q(1,4096),Q(1,4),atlas,root/'forest')
        assert r['status']=='PROVED' and r['atlas']['model_verified'],r
        print('YM24_FOREST '+json.dumps(r),flush=True)
    print('YM24_SUMMARY '+json.dumps(dict(cases=len(cases),positive=10,negative=4,spin_checks=count,incidence_checks=9,atlas_controls=1,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
