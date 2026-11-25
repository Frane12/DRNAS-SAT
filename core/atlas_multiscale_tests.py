"""YM16: multiple genuine ATLAS calls, exact CORE and independent audit."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction as Q
from atlas_multiscale import solve
from operator_verify import verify
import sys,json

def chain(n,spacing=4,hop=1):
    return [[Q(i*spacing) if i==j else -Q(hop) if abs(i-j)==1 else Q(0) for j in range(n)] for i in range(n)]
def main(atlas):
    a=chain(12);p=[7,0,11,2,5,1,9,3,4,10,8,6]
    b=[[a[i][j] for j in p] for i in p]
    deg=chain(12,4,0);deg[1][1]=Q(0)
    cases=[('chain',a,Q(3),True),('permuted',b,Q(3),True),
           ('fractional',chain(14,5,Q(1,2)),Q(4),True),
           ('degenerate',deg,Q(1),False),('overshoot',a,Q(6),False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for name,h,g,ok in cases:
            out=root/name;r=solve(h,g,atlas,out)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),(name,r)
            assert len(r['plan_layers'])>=2 and all(x['model_verified'] for x in r['atlas_plans']),r
            if ok:
                assert Q(r['gap_lower'])>=g and r['dimensions'][-1]<len(h),r
                c=out/'gap.cert';src=out/'matrix.op';old=c.read_text();w=old.split();w[-1]=str(Q(w[-1])+1000);c.write_text(' '.join(w))
                try:verify(src,c)
                except ValueError:pass
                else:raise AssertionError('tampered spectral cut')
                c.write_text(old)
            print('YM16_ROW '+json.dumps(dict(id=name,**r)),flush=True)
        print('YM16_SUMMARY '+json.dumps(dict(cases=len(cases),positive=3,negative=2,finite_only=True)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
