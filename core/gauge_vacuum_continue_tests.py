"""YM25 exact coefficient audit, beyond-YM24 controls; analytic premises separate."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from operator_verify import verify
from gauge_vacuum2_tests import identities
import json

def main():
    cases=[]
    for d in (2,3,4):
        q=2*(d-1);lim=Q(1,240*q)
        cases.extend([(d,Q(1),lim,Q(4,15),16,True),
                      (d,Q(2),-lim,Q(8,15),32,True),
                      (d,Q(1),lim/2,Q(1,3),8,True),
                      (d,Q(1),lim*2,Q(1,10),8,False)])
    cases.extend([(3,Q(1),Q(0),Q(1,2),4,True),
                  (3,Q(1),Q(1,960),Q(1,3),8,False)])
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,a,u,g,n,ok) in enumerate(cases):
            s=root/f'{i}.op';c=root/f'{i}.cert'
            s.write_text(f'p op gauge-vacuum-continue {d} {a} {a*u} {g} {n}\n')
            r=run(s,c,5)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            if ok:
                assert Q(r['gap_lower'])>=g and Q(r['contraction_factor'])<1
                assert Q(r['max_ratio'])/Q(r['old_max_ratio'])==Q(12,5)
                if i%4==0 and i<12:
                    assert Q(r['contraction_factor'])==Q(14,15)
                    old=root/f'old{i}.op';proof=root/f'old{i}.cert'
                    old.write_text(f'p op gauge-local-vacuum {d} {a} {a*u} {g} {n}\n')
                    assert run(old,proof,5)['status']=='UNKNOWN'
                original=c.read_text();z=original.split();z[-1]=str(Q(z[-1])+1);c.write_text(' '.join(z))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered tail')
                c.write_text(original)
            print('YM25_ROW '+json.dumps(dict(id=i,**r)),flush=True)
    print('YM25_SUMMARY '+json.dumps(dict(cases=len(cases),positive=10,negative=4,old_range_controls=3,
        quaternion_identities=identities(),continuum=False)),flush=True)
if __name__=='__main__':main()
