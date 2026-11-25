"""YM14: theorem-application normalization; not a numerical gap certificate."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from itertools import product,combinations
from collections import Counter
from run import run
from operator_verify import verify
import json

def topology(d,L):
    cells=list(product(range(L),repeat=d))
    def shift(x,i):
        y=list(x);y[i]=(y[i]+1)%L;return tuple(y)
    coverage=Counter()
    for x in cells:
        stencil={x,*[shift(x,i) for i in range(d)]}
        assert len(stencil)==d+1
        for y in stencil:
            for direction in range(d):coverage[(y,direction)]+=1
        for i,j in combinations(range(d),2):
            # Four oriented links of the plaquette belong to these three cells.
            edges=[(x,i),(shift(x,i),j),(shift(x,j),i),(x,j)]
            assert len(set(edges))==4 and all(y in stencil for y,k in edges)
    assert len(coverage)==d*L**d and set(coverage.values())=={d+1}
    return len(coverage)

def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        cases=[(2,1,Q(1,4),8),(3,1,Q(3,16),32),(4,1,Q(3,20),80),
               (3,Q(2,3),Q(1,8),48)]
        for i,(d,alpha,scale,beta) in enumerate(cases):
            s=root/f'{i}.op';c=root/f'{i}.cert'
            s.write_text(f'p op gauge-stability {d} {alpha}\n')
            r=run(s,c,5)
            assert r['status']=='THEOREM_APPLIED' and r['numerical_gap_known'] is False,r
            assert Q(r['local_electric_gap'])==scale and Q(r['beta_per_abs_k'])==beta,r
            old=c.read_text();w=old.split();w[-1]='0';c.write_text(' '.join(w))
            try:verify(s,c)
            except ValueError:pass
            else:raise AssertionError('bad normalization accepted')
            c.write_text(old)
            print('YM14_ROW '+json.dumps(r),flush=True)
        for d,L in product((2,3,4),(3,4,5)):
            assert topology(d,L)==d*L**d
        for i,raw in enumerate(['p op gauge-stability 1 1\n','p op gauge-stability 3 0\n','p op gauge-stability 3 1 1/4\n']):
            s=root/f'bad{i}.op';c=root/f'bad{i}.cert';s.write_text(raw)
            assert run(s,c,5)['status']=='ERROR' and not c.exists()
    print('YM14_SUMMARY '+json.dumps(dict(theorem_cases=4,topology_cases=9,invalid_inputs=3,numeric_gap=False,continuum=False)),flush=True)
if __name__=='__main__':main()
