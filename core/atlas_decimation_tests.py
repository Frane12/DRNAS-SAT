"""Paired CORE and ATLAS30 integration tests, including false claims."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
import json,sys
from atlas_decimation import solve
from run import run
from operator_verify import verify

def chain(diag,c):
    return [[Q(x) if i==j else -Q(c) if abs(i-j)==1 else Q(0) for j in range(len(diag))] for i,x in enumerate(diag)]
def main(atlas):
    h=chain([0,3,6,9,15,16,17,18],1)
    perm=[6,3,0,7,2,4,1,5]
    changed=[[h[i][j] for j in perm] for i in perm]
    deg=chain([0,0,5,6,10,12],0)
    cases=[('chain',h,Q(2),True),('permuted',changed,Q(2),True),
           ('fractional',chain([0,4,8,12,16,20],Q(1,2)),Q(3),True),
           ('degenerate',deg,Q(1),False),('overshoot',h,Q(4),False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for name,h,g,ok in cases:
            out=root/name;r=solve(h,g,atlas,out)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),(name,r)
            assert r['atlas']['model_verified'],r
            if ok:
                assert Q(r['gap_lower'])>=g and r['remaining']<len(h),r
                c=out/'gap.cert';s=out/'matrix.op';old=c.read_text();w=old.split();w[5]=str(Q(w[5])+1000);c.write_text(' '.join(w))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered cut accepted')
                c.write_text(old)
            print('YM15_ROW '+json.dumps(dict(id=name,**r)),flush=True)
        # A malicious candidate cannot remove a coupled pair as diagonal.
        s=root/'bad.op';c=root/'bad.cert';s.write_text('p op decimation-gap 3 1 2 1 2\n0 0 0\n0 5 1\n0 1 6\n')
        assert run(s,c,5)['status']=='ERROR' and not c.exists()
    print('YM15_SUMMARY '+json.dumps(dict(cases=6,atlas_planner=True,finite_only=True)),flush=True)
if __name__=='__main__':main(Path(sys.argv[1]).resolve())
