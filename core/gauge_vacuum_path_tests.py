"""YM27: source-bound adaptive path, exact continuation checks and tamper controls."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from run import run
from operator_verify import verify
import json

def main():
    cases=[(2,153,1,Q(2,5),64,True),(3,154,1,Q(2,5),64,True),
           (4,156,1,Q(2,5),64,True),(3,154,-1,Q(2,5),64,True),
           (3,320,1,Q(2,5),1,True),(3,154,1,Q(2,5),1,False),
           (3,153,1,Q(1,10),64,False),(4,155,1,Q(1,10),64,False),
           (3,154,1,Q(1,2),64,False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,den,sign,g,cap,ok) in enumerate(cases):
            u=Q(sign,den*2*(d-1));s=root/f'{i}.op';c=root/f'{i}.cert'
            s.write_text(f'p op gauge-vacuum-path {d} 1 {u} {g} {cap}\n')
            r=run(s,c,10)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),r
            if ok:
                assert verify(s,c)=={k:v for k,v in r.items() if k in verify(s,c)},r
                assert Q(r['gap_lower'])>=g
                if den<160:
                    assert r['continuation_steps']>0
                    old=root/f'old{i}.op';p=root/f'old{i}.cert'
                    old.write_text(f'p op gauge-vacuum-inverse {d} 1 {u} 1/10 8\n')
                    assert run(old,p,5)['status']=='UNKNOWN'
                original=c.read_text();z=original.split();z[7]='0';c.write_text(' '.join(z))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered radius')
                c.write_text(original)
            print('YM27_ROW '+json.dumps(dict(id=i,**r)),flush=True)
        s=root/'zero.op';c=root/'zero.cert';s.write_text('p op gauge-vacuum-path 3 1 0 1/2 1\n')
        assert run(s,c,5)['status']=='PROVED'
    print('YM27_SUMMARY '+json.dumps(dict(cases=len(cases)+1,positive=6,negative=4,continuum=False)),flush=True)
if __name__=='__main__':main()
