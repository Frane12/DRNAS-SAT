"""YM18B: exact energy cancellation for a restricted uniform family."""
from fractions import Fraction as Q
from pathlib import Path
from run import run
from operator_verify import verify
import tempfile,json
def main():
    cases=[(f'weak-{i}',4,24+16*i,Q(1,2**i),Q(1,2**i),Q(1),True) for i in range(6)]
    cases += [('strong',4,16,Q(1),Q(4),Q(1),True),('fixed-a-weak',4,104,Q(1),Q(1,32),Q(1,10),True),
              ('overshoot',4,24,Q(1),Q(1),Q(10000),False),('tiny-head',4,3,Q(1),Q(1,32),Q(1),False)]
    pos=neg=0
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        for i,(label,length,n,a,g2,g,expected) in enumerate(cases):
            s=p/f'{i}.op';c=p/f'{i}.cert';s.write_text(f'p op ks-bouquet-gap {length} {n} {a} {g2} {g}\n')
            r=run(s,c,20,audit_seconds=25)
            if expected and r['status']=='PROVED':
                pos+=1;assert Q(r['gap_lower'])>=g and r['applies_to_all_finite_bouquets_m_ge_2'] and not r['shared_edges']
                old=c.read_text();z=old.split();z[-1]=str(Q(z[-1])+1000000);c.write_text(' '.join(z)+'\n')
                try:verify(s,c)
                except ValueError:pass
                else:raise AssertionError('invalid angular cut accepted')
                c.write_text(old)
            elif not expected:
                assert r['status']=='UNKNOWN',(label,r);neg+=1
            else:assert r['status'] in ('UNKNOWN','TIMEOUT','AUDIT_LIMIT'),(label,r)
            print('YM18B_ROW '+json.dumps(dict(id=label,**r)),flush=True)
    print('YM18B_SUMMARY '+json.dumps(dict(positive=pos,positive_total=8,negative=neg,uniform_bouquet_only=True,shared_edge=False,continuum=False)),flush=True)
    assert pos>0
if __name__=='__main__':main()
