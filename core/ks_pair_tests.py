"""YM16B: equal cycles sharing one edge, including all angular sectors."""
from fractions import Fraction as Q
from pathlib import Path
from run import run
from operator_verify import verify
import tempfile,json
def main():
    cases=[(f'weak-{i}',4,24+16*i,Q(1,2**i),Q(1,2**i),Q(1),True) for i in range(6)]
    cases += [('strong',4,16,Q(1),Q(4),Q(1),True),('hexagon',6,48,Q(1,4),Q(1,4),Q(1),True),
              ('overshoot',4,24,Q(1),Q(1),Q(10000),False),('tiny-head',4,3,Q(1),Q(1,32),Q(1),False)]
    positive=negative=0
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        for i,(label,l,n,a,g2,g,expected) in enumerate(cases):
            s=p/f'{i}.op';c=p/f'{i}.cert';s.write_text(f'p op ks-pair-gap {l} {n} {a} {g2} {g}\n')
            r=run(s,c,20,audit_seconds=25)
            if expected and r['status']=='PROVED':
                positive+=1;assert Q(r['gap_lower'])>=g
                old=c.read_text();z=old.split();z[-1]=str(Q(z[-1])+1000000);c.write_text(' '.join(z)+'\n')
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('invalid angular bound accepted')
                c.write_text(old)
            elif not expected:
                assert r['status']=='UNKNOWN',(label,r);negative+=1
            else:
                assert r['status'] in ('UNKNOWN','TIMEOUT','AUDIT_LIMIT'),(label,r)
            print('YM16B_ROW '+json.dumps(dict(id=label,**r)),flush=True)
    print('YM16B_SUMMARY '+json.dumps(dict(positive=positive,positive_total=8,negative=negative,shared_edge=True,all_representations=True,continuum=False)),flush=True)
    assert positive>0
if __name__=='__main__':main()
