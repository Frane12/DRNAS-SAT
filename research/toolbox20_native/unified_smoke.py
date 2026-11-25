"""Exhaustive truth oracle on 160 small random CNFs; verify each answer."""
import itertools,random,subprocess,sys,tempfile
from pathlib import Path
from corpus import encode
from verify import check_model,check_unsat
solver=Path(sys.argv[1]).resolve();checker=Path(sys.argv[2]).resolve()
rng=random.Random(6112501);count={10:0,20:0,0:0}
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'input.cnf';q=Path(td)/'proof'
    for i in range(160):
        n=2+i%7;cs=[]
        for j in range(rng.randrange(n,6*n+1)):
            vs=rng.sample(range(1,n+1),rng.randint(1,min(n,4)))
            cs.append([v*rng.choice((-1,1)) for v in vs])
        raw=encode(n,cs);p.write_bytes(raw);q.unlink(missing_ok=True)
        expected=any(all(any(bool(mask>>(abs(l)-1)&1)==(l>0) for l in c) for c in cs) for mask in range(1<<n))
        r=subprocess.run([solver,p,q,'2'],capture_output=True,text=True,timeout=3)
        if r.returncode==10: assert expected;check_model(raw,r.stdout)
        elif r.returncode==20: assert not expected;check_unsat(p,q,checker)
        elif r.returncode!=0: raise RuntimeError((i,r.returncode,r.stderr))
        count[r.returncode]+=1
print('UNIFIED1_EXHAUSTIVE',count,flush=True)
assert count[10]+count[20]>=150,'unexpected small-CNF coverage regression'
