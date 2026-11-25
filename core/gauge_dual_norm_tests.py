"""YM28: exact dual-norm arithmetic, previous-range controls and tampering."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from operator_verify import verify
import json

def main():
    cases=[(2,80,1,Q(1,10),True),(3,85,1,Q(1,10),True),
           (4,85,1,Q(1,20),True),(3,90,-1,Q(1,4),True),
           (4,90,1,Q(1,5),True),(3,80,1,Q(1,100),False),
           (4,80,1,Q(1,100),False),(3,85,1,Q(1,2),False),
           (3,20,1,Q(1,100),False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,den,sign,g,ok) in enumerate(cases):
            u=Q(sign,den*2*(d-1));s=root/f'{i}.op';c=root/f'{i}.cert'
            s.write_text(f'p op gauge-dual-norm {d} 1 {u} {g}\n')
            r=run(s,c,10)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            if ok:
                assert verify(s,c)['gap_lower']==r['gap_lower'],r
                assert Q(r['gap_lower'])>=g and Q(r['contraction_factor'])<1
                old=root/f'old{i}.op';p=root/f'old{i}.cert'
                old.write_text(f'p op gauge-vacuum-path {d} 1 {u} 1/100 64\n')
                assert run(old,p,5)['status']=='UNKNOWN'
                original=c.read_text();z=original.split();z[8]='0';c.write_text(' '.join(z))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered strong radius')
                c.write_text(original)
            print('YM28_ROW '+json.dumps(dict(id=i,**r)),flush=True)
        s=root/'zero.op';c=root/'zero.cert';s.write_text('p op gauge-dual-norm 3 1 0 1/2\n')
        assert run(s,c,5)['status']=='PROVED'
    print('YM28_SUMMARY '+json.dumps(dict(cases=len(cases)+1,positive=6,negative=4,continuum=False)),flush=True)
if __name__=='__main__':main()
