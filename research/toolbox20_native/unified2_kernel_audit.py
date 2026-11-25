"""Independent, naive RUP replay of each targeted derived clause."""
import sys
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
for stem in ('gate','wide','resolution'):
    p=Path(sys.argv[1])/stem
    cs=[tuple(map(int,l.split()[:-1])) for l in p.with_suffix('.cnf').read_text().splitlines()[1:]]
    proof=[tuple(map(int,l.split()[:-1])) for l in p.with_suffix('.drup').read_text().splitlines()]
    assert proof
    for i,c in enumerate(proof):
        assert rup(cs,c),(stem,i,c)
        cs.append(c)
    print('UNIFIED2_KERNEL_RUP',stem,len(proof),flush=True)
