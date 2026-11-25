"""YM19: actual ATLAS and CORE, exact locality and scaling obstruction."""
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from collections import Counter
import json,sys
from tree_gauge_tests import grid
from atlas_tree_locality import solve
from tree_locality_verify import obstruction,verify_locality

def congestion(d,L):
    # Independent exhaustive test of the analytic path-load estimate.
    points=list(product(range(L),repeat=d));loads=Counter()
    for x,y in product(points,repeat=2):
        u=list(x)
        for i in range(d):
            while u[i]!=y[i]:
                a=tuple(u);u[i]+=1 if u[i]<y[i] else -1
                loads[tuple(sorted((a,tuple(u))))]+=1
    assert 2*max(loads.values())<=L**(d+1)
    return max(loads.values())

def main(atlas):
    for d,L in [(2,2),(2,3),(3,2),(3,3)]:
        congestion(d,L)
    with TemporaryDirectory() as tmp:
        work=Path(tmp)
        for d,L in [(2,3),(3,2),(3,3),(3,4)]:
            n,edges,loops=grid(d,L,Q(1,256))
            r=solve(n,edges,loops,Q(1),Q(1),atlas,work/f'{d}-{L}',[0,n//2,n-1])
            assert r['status']=='PROVED',r
            assert len(r['candidates'])==3,r
            a=r['best']['locality'];b=r['candidates'][0]['locality']
            assert a['reduced']['max_row']<=b['reduced']['max_row']
            bound=obstruction(d,L)
            for x in r['candidates']:
                p=x['locality']
                assert p['reduced']['max_row']>=bound and p['reduced']['cross_pairs']<=p['original']['cross_pairs'],r
                assert x['atlas']['model_verified']
            root=r['best']['root'];folder=work/f'{d}-{L}'/f'root{root}'
            c=folder/'locality.json';old=c.read_text();z=json.loads(old)
            i=next(i for i,row in enumerate(z['rows']) if row)
            z['rows'][i][0][2]*=-1;c.write_text(json.dumps(z))
            try:verify_locality(folder/'graph.json',folder/'tree.json',c)
            except ValueError:pass
            else:raise AssertionError('tampered sign accepted')
            c.write_text(old)
            print('YM19_ROW '+json.dumps(dict(d=d,L=L,lower_bound=bound,**r)),flush=True)
    print('YM19_OBSTRUCTION '+json.dumps([dict(L=L,min_row=obstruction(3,L)) for L in (4,8,16,32,64)]),flush=True)
    print('YM19_SUMMARY '+json.dumps(dict(grid_cases=4,atlas_candidates=12,path_controls=4,continuum=False)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
