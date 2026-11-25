"""YM29 rational bounds, independent audit, previous method controls."""
from fractions import Fraction as Q
from pathlib import Path
from tempfile import TemporaryDirectory
from itertools import product
from run import run
from operator_verify import verify
import json

def hessian_controls():
    # Exact rational Cauchy-Schwarz controls; not a proof of the analytic premise.
    cases=0
    for spins in product((Q(0),Q(1,2),Q(1),Q(3,2),Q(2)),repeat=3):
        energy=sum(j*(j+1) for j in spins)
        for speed in product((Q(0),Q(1,3),Q(1),Q(2)),repeat=3):
            assert sum(j*v for j,v in zip(spins,speed))**2<=energy*sum(v*v for j,v in zip(spins,speed) if j)
            cases+=1
    return cases

def main():
    cases=[(2,74,1,Q(2,5),True),(3,77,1,Q(39,100),True),
           (4,78,1,Q(38,100),True),(3,77,-1,Q(39,100),True),
           (3,85,1,Q(2,5),True),(3,76,1,Q(1,100),False),
           (2,73,1,Q(1,100),False),(4,77,1,Q(1,100),False),
           (3,77,1,Q(1,2),False)]
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,(d,den,sign,g,ok) in enumerate(cases):
            u=Q(sign,den*2*(d-1));s=root/f'{i}.op';c=root/f'{i}.cert'
            s.write_text(f'p op gauge-direct-hessian {d} 1 {u} {g}\n')
            r=run(s,c,10)
            assert r['status']==('PROVED' if ok else 'UNKNOWN'),(i,r)
            if ok:
                assert verify(s,c)['gap_lower']==r['gap_lower'] and Q(r['gap_lower'])>=g
                old=root/f'old{i}.op';p=root/f'old{i}.cert'
                old.write_text(f'p op gauge-dual-norm {d} 1 {u} {g}\n')
                assert run(old,p,5)['status']=='UNKNOWN'
                original=c.read_text();z=original.split();z[6]='0';c.write_text(' '.join(z))
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered radius')
                c.write_text(original)
            print('YM29_ROW '+json.dumps(dict(id=i,**r)),flush=True)
        s=root/'zero.op';c=root/'zero.cert';s.write_text('p op gauge-direct-hessian 3 1 0 1/2\n')
        assert run(s,c,5)['status']=='PROVED'
    print('YM29_SUMMARY '+json.dumps(dict(cases=len(cases)+1,positive=6,negative=4,hessian_controls=hessian_controls(),continuum=False)),flush=True)
if __name__=='__main__':main()
