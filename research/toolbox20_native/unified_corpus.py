"""Freeze-dependent fresh inputs; no expected answers given to the solver."""
import itertools,random,hashlib,json,sys
from pathlib import Path
from corpus import fresh,encode,sha
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
freeze=sys.argv[2];cases=[]
def mixed(seed,k):
    rng=random.Random(seed);n=18+4*k;cs=[]
    def add(vs,allowed):
        for m in range(1<<len(vs)):
            if not allowed(tuple((m>>i)&1 for i in range(len(vs)))):
                cs.append([(-v if m>>i&1 else v) for i,v in enumerate(vs)])
    # Randomly overlapping affine and nonlinear constraints on the same symbols.
    for i in range(1,n-2):
        vs=[i,i+1,i+2]
        op=rng.randrange(3)
        if op==0:add(vs,lambda b:b[2]==(b[0]^b[1]))
        elif op==1:add(vs,lambda b:b[2]==(b[0]&b[1]))
        else:add(vs,lambda b:b[2]==(b[0]|b[1]))
    for _ in range(k+2):
        a,b=rng.sample(range(1,n+1),2);cs.append([rng.choice((-1,1))*a,rng.choice((-1,1))*b])
    order=list(range(1,n+1));rng.shuffle(order);rename=[0]+[v*rng.choice((-1,1)) for v in order]
    cs=[[rename[abs(l)]*(1 if l>0 else -1) for l in c] for c in cs]
    for c in cs:rng.shuffle(c)
    rng.shuffle(cs);return n,cs
for family in ('tseitin','random3','colour','circuit','mixed'):
    for k in range(10):
        seed=int(sha(f'{freeze}|unified1|{family}|{k}'.encode())[:16],16)
        n,cs=mixed(seed,k) if family=='mixed' else fresh(family,k%3,seed)
        data=encode(n,cs);cid=f'blind-{family}-{k:02}'
        (root/(cid+'.cnf')).write_bytes(data)
        cases.append(dict(id=cid,group='fresh',family=family,seed=seed,cnf_sha256=sha(data),variables=n,clauses=len(cs)))
(root/'manifest.json').write_text(json.dumps(dict(freeze=freeze,cases=cases),indent=2))
