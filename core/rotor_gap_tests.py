"""YM12: infinite rotor-index gap, exact source-bound certificates."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fractions import Fraction as Q
from run import run
from operator_verify import verify
import json

def main():
    cases=[
        (1,4,'17/5',1,0,True),
        (2,4,'17/5',1,0,True),
        (2,4,'69/20',1,'1/4',True),
        (2,4,'349/100',1,'1/2',True),
        (2,4,'357/100',1,1,True),
        (2,4,'9/2',2,'1/2',True),
        (2,3,'349/100',1,'1/2',True),
        (1,4,4,0,0,False),
        (2,4,4,0,0,False),
    ]
    with TemporaryDirectory() as tmp:
        p=Path(tmp)
        for i,(d,n,g,k,c,expected) in enumerate(cases):
            src=p/f'{i}.op';cert=p/f'{i}.cert'
            src.write_text(f'p op rotor-gap {d} {n} {g} {k} {c}\n')
            r=run(src,cert,15,audit_seconds=30)
            assert r['status']==('PROVED' if expected else 'UNKNOWN'),(i,r)
            if expected:
                assert r['infinite_representation'] and Q(r['gap_lower'])>=Q(g),r
                old=cert.read_text();w=old.split();w[5]=str(Q(r['tail_lower'])+1)
                cert.write_text('\n'.join(w)+'\n')
                try:verify(src,cert)
                except ValueError:pass
                else:raise AssertionError('invalid tail cut accepted')
                cert.write_text(old)
            print('YM12_ROW '+json.dumps(dict(id=i,**r)),flush=True)
    print('YM12_SUMMARY '+json.dumps(dict(cases=len(cases),positive=sum(x[-1] for x in cases),infinite_representation=True,full_gauge_theory=False)),flush=True)
if __name__=='__main__':main()
