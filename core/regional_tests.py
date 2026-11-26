"""Regional projection: large connected/disconnected cases and proof tamper controls."""
import hashlib
import json
import pathlib
import random
import tempfile
from run import run
from tests import write, hide, truth
from verify import verify

def equality_chain(n,contradiction):
    cs=[]
    for v in range(1,n):
        cs.extend(((-v,v+1),(v,-v-1)))
    cs.extend(((1,n),(-1,-n)) if contradiction else ((1,),))
    return cs

def main():
    rng=random.Random(2611202617)
    with tempfile.TemporaryDirectory() as tmp:
        d=pathlib.Path(tmp);cases=[]
        for n in (100,12000,50000,100000):
            for unsat in (False,True):
                nn,cs=hide(rng,n,equality_chain(n,unsat))
                cases.append((f'chain-{n}-{unsat}',nn,cs,'UNSAT' if unsat else 'SAT'))
        n=50000
        cs=[c for v in range(1,n,2) for c in ((v,v+1),(-v,-v-1))]
        nn,cs=hide(rng,n,cs);cases.append(('independent-pairs',nn,cs,'SAT'))
        for i in range(32):
            n=8
            cs=[tuple(rng.choice((-1,1))*v for v in rng.sample(range(1,n+1),rng.randint(1,4))) for _ in range(24)]
            cases.append((f'exhaustive-{i}',n,cs,'SAT' if truth(n,cs) else 'UNSAT'))
        rows=[];large_native=0
        for i,(name,n,cs,expected) in enumerate(cases):
            source=d/f'{i}.cnf';cert=d/f'{i}.cert';write(source,n,cs)
            result=run(str(source),str(cert),10.0,'regional',10.0)
            assert result['status'] in (expected,'UNKNOWN','TIMEOUT','AUDIT_LIMIT'),(name,result)
            if n>=12000 and result['status']==expected and result.get('telemetry',{}).get('method','').startswith('regional_'):large_native+=1
            if n<=100:assert result['status']==expected,(name,result)
            row=dict(id=name,n=n,m=len(cs),expected=expected,**result)
            rows.append(row);print('REGIONAL_ROW '+json.dumps(row),flush=True)
        assert large_native>0,'no accepted large regional result'
        # Independent checker control: source includes a tautology and duplicates.
        src=d/'control.cnf';write(src,12000,[(1,-1),(2,2),(-2,)])
        good='drnas-regional-resolution-v1 '+hashlib.sha256(src.read_bytes()).hexdigest()+'\nr 0 1 2\nend 2\n'
        cert=d/'control.cert';cert.write_text(good)
        assert verify(src,cert,20,10)==('UNSAT','REGIONAL-RES')
        for bad in (good.replace('r 0 1 2','r 0 1 3'),good.replace('end 2','end 0'),good.replace('r 0 1 2','r 3 1 2'),good.replace(hashlib.sha256(src.read_bytes()).hexdigest(),'0'*64)):
            cert.write_text(bad)
            try:verify(src,cert,20,10)
            except ValueError:pass
            else:raise AssertionError('bad regional proof accepted')
        print('REGIONAL_SUMMARY '+json.dumps(dict(cases=len(rows),solved=sum(r['status'] in ('SAT','UNSAT') for r in rows),large_native=large_native,tamper_rejected=4)),flush=True)

if __name__=='__main__':main()
