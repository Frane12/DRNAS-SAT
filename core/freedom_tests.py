"""Paired truth-table pilot: default vs opt-in freedom, no reference solver."""
import itertools
import json
import pathlib
import random
import tempfile
from run import run
from tests import truth, hide, write

def main():
    rng=random.Random(26112026)
    cases=[]
    for n in (3,4,5,6):
        full=[tuple(v if bit else -v for v,bit in zip(range(1,n+1),bits))
              for bits in itertools.product((0,1),repeat=n)]
        for j in range(5):
            cases.append(('cube-unsat',*hide(rng,n,full)))
            missing=rng.randrange(len(full))
            cases.append(('cube-sat',*hide(rng,n,[c for i,c in enumerate(full) if i!=missing])))
    for j in range(80):
        n=5+j%6
        cs=[tuple(rng.choice((-1,1))*v for v in rng.sample(range(1,n+1),rng.randint(2,min(n,5))))
            for _ in range(rng.randint(n,6*n))]
        cases.append(('random',n,cs))
    totals={m:dict(solved=0,unknown=0,errors=0,solve_s=0.0,novel=0,rounds=0,revisits=0) for m in ('default','freedom')}
    paired={'both':0,'freedom_only':0,'default_only':0,'neither':0}
    terminal=0
    with tempfile.TemporaryDirectory() as tmp:
        d=pathlib.Path(tmp)
        for i,(family,n,cs) in enumerate(cases):
            src=d/f'{i}.cnf';write(src,n,cs)
            expected='SAT' if truth(n,cs) else 'UNSAT'
            solved={}
            for mode in (('default','freedom') if i%2==0 else ('freedom','default')):
                result=run(str(src),str(d/f'{i}-{mode}.cert'),1.0,mode,5)
                status=result['status'];t=result.get('telemetry',{})
                assert status in (expected,'UNKNOWN','TIMEOUT','AUDIT_LIMIT'),(i,expected,mode,result)
                solved[mode]=status==expected
                z=totals[mode];z['solved']+=int(solved[mode]);z['unknown']+=int(not solved[mode])
                z['solve_s']+=result.get('solve_s',0.0)
                for key,field in [('novel','freedom_novel'),('rounds','freedom_rounds'),('revisits','freedom_revisits')]:
                    z[key]+=t.get(field,0)
                if mode=='freedom' and solved[mode] and t.get('method','').startswith('freedom_'):terminal+=1
                print('CORE_FREEDOM_ROW '+json.dumps(dict(id=i,family=family,expected=expected,**result)),flush=True)
            a,b=solved['default'],solved['freedom']
            paired['both' if a and b else 'default_only' if a else 'freedom_only' if b else 'neither']+=1
    assert terminal>0,'new native path was never exercised'
    print('CORE_FREEDOM_SUMMARY '+json.dumps(dict(cases=len(cases),totals=totals,paired=paired,freedom_terminal=terminal)),flush=True)

if __name__=='__main__':main()
