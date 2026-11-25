"""YM21: exact uniform gap for the auxiliary interacting model, not KS."""
from fractions import Fraction as Q
from itertools import product,combinations
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from run import run
from operator_verify import verify

def incidence(d,L,periodic):
    sites=list(product(range(L),repeat=d));cnt=Counter()
    def shift(x,i):
        a=list(x);a[i]=(a[i]+1)%L;return tuple(a)
    for x in sites:
        for i,j in combinations(range(d),2):
            if not periodic and (x[i]==L-1 or x[j]==L-1):continue
            for e in [(x,i),(shift(x,i),j),(shift(x,j),i),(x,j)]:cnt[e]+=1
    return max(cnt.values())

def main():
    cases=[(3,1,Q(1,32),Q(1,3),Q(1,3)),(3,1,Q(1,16),Q(1,6),Q(1,6)),
           (3,1,Q(-1,32),Q(1,3),Q(1,3)),(2,1,Q(1,16),Q(1,3),Q(1,3)),
           (4,2,Q(1,32),Q(3,4),Q(3,4)),(3,1,0,Q(1,2),Q(1,2)),
           (3,1,Q(3,32),Q(1,100),None),(3,1,Q(1,32),Q(2,5),None)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,a,k,g,expected) in enumerate(cases):
            s=root/f'{i}.op';c=root/f'{i}.cert';s.write_text(f'p op gauge-parent-gap {d} {a} {k} {g}\n')
            r=run(s,c,5);assert r['status']==('PROVED' if expected is not None else 'UNKNOWN'),r
            if expected is not None:
                assert Q(r['gap_lower'])==expected and not r['original_KS_uniform_gap'],r
                assert Q(r['residual_per_edge_upper'])==a*(2*(d-1)*Q(k)/(3*a))**2,r
                old=c.read_text();z=old.split();z[-1]='-1';c.write_text(' '.join(z))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('invalid residual accepted')
                c.write_text(old)
            print('YM21_ROW '+json.dumps(dict(id=i,d=d,alpha=str(a),k=str(k),**r)),flush=True)
    for d,L in product((2,3,4),(3,4,5)):
        assert incidence(d,L,True)==2*(d-1) and incidence(d,L,False)<=2*(d-1)
    print('YM21_SUMMARY '+json.dumps(dict(cases=len(cases),positive=6,negative=2,incidence_checks=18,parent_only=True,continuum=False)),flush=True)
if __name__=='__main__':main()
