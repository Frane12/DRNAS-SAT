"""Automatic series, exact recurrence, tampering and native CORE cross-check."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from vacuum_series import solve,series
from vacuum_series_verify import verify
from run import run
import json

def main():
    v=series(3)
    assert v==[{0:Q(2,3)},{1:-Q(1,9)},{0:-Q(4,135),2:Q(4,135)}],v
    with TemporaryDirectory() as tmp:
        d=Path(tmp);i=0
        for lam in (Q(1,4),Q(-1,4),Q(1,16),Q(19,64),Q(0)):
            for n in (4,8,16):
                i+=1;s=d/f'{i}.json';c=d/f'{i}.cert'
                s.write_text(json.dumps(dict(electric='2',ratio=str(lam),target='2',order=n)))
                r=solve(s,c);assert r['status']=='PROVED' and verify(s,c)==r,r
                old=c.read_text();a=json.loads(old);a['coefficients'][0]['0']='1';c.write_text(json.dumps(a))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered coefficient')
                c.write_text(old)
                print('YM23_ROW '+json.dumps(r),flush=True)
        for lam,target in [('1/2','1'),('1/4','3')]:
            i+=1;s=d/f'{i}.json';c=d/f'{i}.cert'
            s.write_text(json.dumps(dict(electric='2',ratio=lam,target=target,order=8)))
            assert solve(s,c)['status']=='UNKNOWN' and not c.exists()
        # Physical loop of length 4, a=1, g^2=4 -> e=2,k=1/2, k/e=1/4.
        # Separate native CORE infinite-tail Sturm/Schur certificate.
        s=d/'physical.op';c=d/'physical.cert';s.write_text('p op ks-loop-gap 4 24 1 4 5/2\n')
        r=run(s,c,15,audit_seconds=25)
        assert r['status']=='PROVED' and Q(r['gap_lower'])>=Q(5,2),r
        print('YM23_NATIVE '+json.dumps(r),flush=True)
    print('YM23_SUMMARY '+json.dumps(dict(series_cases=15,negative=2,native=1,continuum=False)),flush=True)
if __name__=='__main__':main()
