"""Independent, deliberately naive proof replay for new discovery kernels."""
import itertools,sys
from pathlib import Path
def rup(cs,c):
    a={}
    def put(l):
        v=abs(l);b=l>0
        if v in a:return a[v]==b
        a[v]=b;return True
    for l in c:
        if not put(-l):return True
    while True:
        changed=False
        for d in cs:
            if any(a.get(abs(l))==(l>0) for l in d if abs(l) in a):continue
            free=[l for l in d if abs(l) not in a]
            if not free:return True
            if len(free)==1:
                if not put(free[0]):return True
                changed=True
        if not changed:return False
for stem in ('context','region','region_unsat','negative'):
    p=Path(sys.argv[1])/stem
    raw=p.with_suffix('.cnf').read_text().splitlines()
    n=int(raw[0].split()[2])
    source=[tuple(map(int,l.split()[:-1])) for l in raw[1:]]
    cs=source[:]
    proof=[tuple(map(int,l.split()[:-1])) for l in p.with_suffix('.drup').read_text().splitlines()]
    if stem!='negative':assert proof
    for i,c in enumerate(proof):
        assert rup(cs,c),(stem,i,c)
        cs.append(c)
    models=[b for b in itertools.product((False,True),repeat=n)
            if all(any(b[abs(l)-1]==(l>0) for l in c) for c in source)]
    for b in models:
        assert all(any(b[abs(l)-1]==(l>0) for l in c) for c in proof)
    if stem=='region_unsat':assert not models and proof[-1]==()
    else:assert models
    print('UNIFIED3_KERNEL_RUP',stem,len(proof),'models',len(models),flush=True)
