"""Independent RUP replay of every composition-kernel proof line."""
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
total=0;cases=0
for p in sorted(Path(sys.argv[1]).glob('*.cnf')):
    cs=[tuple(map(int,l.split()[:-1])) for l in p.read_text().splitlines()[1:]]
    proof=[tuple(map(int,l.split()[:-1])) for l in p.with_suffix('.drup').read_text().splitlines()]
    if p.stem=='cube':assert proof and proof[-1]==()
    if p.stem=='guarded':assert proof and proof[-1]==(1,)
    for i,c in enumerate(proof):
        assert rup(cs,c),(p.stem,i,c)
        cs.append(c)
    cases+=1;total+=len(proof)
assert cases==67
print('UNIFIED4_KERNEL_RUP',cases,total,flush=True)
