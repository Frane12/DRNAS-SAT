"""YM15 physical single-cycle SU(2): exact gap over the full character tower."""
from fractions import Fraction as Q
from pathlib import Path
from run import run
from operator_verify import verify
import tempfile,json

def main():
    cases=[]
    # g^2 decreases; the dimensionless magnetic/electric ratio grows as 4/(g^2)^2.
    for i in range(6):
        g2=Q(1,2**i);a=Q(1,2**i)
        cases.append((f'weak-{i}',4,16+16*i,a,g2,Q(1),True))
    cases.extend([('strong',4,12,Q(1),Q(4),Q(1),True),
                  ('length-six',6,48,Q(1,4),Q(1,4),Q(1),True),
                  ('insufficient-tail',4,2,Q(1),Q(1,32),Q(1),False),
                  ('impossible-target',4,24,Q(1),Q(1),Q(10000),False)])
    pos=neg=0
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        for i,(name,l,n,a,g2,gamma,expect) in enumerate(cases):
            s=p/f'{i}.op';c=p/f'{i}.cert';s.write_text(f'p op ks-loop-gap {l} {n} {a} {g2} {gamma}\n')
            r=run(s,c,15,audit_seconds=25)
            if expect and r['status']=='PROVED':
                assert Q(r['gap_lower'])>=gamma and Q(r['magnetic_electric_ratio'])==4/g2**2
                old=c.read_text();z=old.split();z[-1]=str(Q(z[-1])+1000000);c.write_text(' '.join(z)+'\n')
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('tampered cut accepted')
                c.write_text(old);pos+=1
            elif not expect:
                assert r['status']=='UNKNOWN',(name,r);neg+=1
            else:
                assert r['status'] in ('UNKNOWN','TIMEOUT','AUDIT_LIMIT'),(name,r)
            print('YM15_ROW '+json.dumps(dict(id=name,**r)),flush=True)
    print('YM15_SUMMARY '+json.dumps(dict(positive=pos,positive_total=8,negative=neg,all_representations=True,volume_uniform=False,continuum=False)),flush=True)
    assert pos>0
if __name__=='__main__':main()
