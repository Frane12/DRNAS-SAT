"""YM26 checks the exact inverse certificate; analytic premises are documented."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from operator_verify import verify
import json

def main():
    cases=[]
    for d in (2,3,4):
        lim=Q(1,160*2*(d-1))
        cases.extend([(d,Q(1),lim,Q(5,12),16,True),
                      (d,Q(2),-lim,Q(5,6),32,True),
                      (d,Q(1),lim/2,Q(11,24),8,True),
                      (d,Q(1),lim*2,Q(1,10),8,False)])
    cases += [(3,Q(1),Q(0),Q(1,2),4,True),
              (3,Q(1),Q(1,640),Q(1,2),8,False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,a,u,g,n,ok) in enumerate(cases):
            s=root/f'{i}.op';c=root/f'{i}.cert'
            s.write_text(f'p op gauge-vacuum-inverse {d} {a} {a*u} {g} {n}\n')
            r=run(s,c,5)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            if ok:
                assert Q(r['gap_lower'])>=g and Q(r['inverse_norm_upper'])<=3
                assert Q(r['contraction_factor'])<=Q(9,10)
                assert Q(r['max_ratio'])/Q(r['previous_max_ratio'])==Q(3,2)
                if i%4==0 and i<12:
                    assert Q(r['gap_lower'])==Q(5,12)
                    assert Q(r['inverse_norm_upper'])==3
                    old=root/f'old{i}.op';p=root/f'old{i}.cert'
                    old.write_text(f'p op gauge-vacuum-continue {d} {a} {a*u} 1/10 {n}\n')
                    assert run(old,p,5)['status']=='UNKNOWN'
                original=c.read_text();z=original.split();z[5]='1';c.write_text(' '.join(z))
                if Q(r['inverse_norm_upper'])!=1:
                    try:verify(s,c)
                    except ValueError:pass
                    else:raise AssertionError('tampered inverse accepted')
                c.write_text(original)
                assert verify(s,c)['status']=='PROVED'
            print('YM26_ROW '+json.dumps(dict(id=i,**r)),flush=True)
    print('YM26_SUMMARY '+json.dumps(dict(cases=len(cases),positive=10,negative=4,previous_range_controls=3,continuum=False)),flush=True)
if __name__=='__main__':main()
