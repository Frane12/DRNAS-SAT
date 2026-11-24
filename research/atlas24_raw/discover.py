"""Raw CNF scope recovery, exact local relations and bounded relational closure."""
import itertools as I, random, json
from collections import defaultdict
def solve(cnf,budget=100000):
    groups=defaultdict(list)
    for c in cnf:
        if any(-x in c for x in c): continue
        groups[tuple(sorted(set(map(abs,c))))].append(c)
    relations=[]
    for scope,cs in groups.items():
        if len(scope)>8:return "UNKNOWN",[]
        rows=[b for b in I.product((0,1),repeat=len(scope)) if all(any(b[scope.index(abs(l))]==(l>0) for l in c) for c in cs)]
        kind="RELATION"
        if len(scope)==2 and set(rows) in ({(0,0),(1,1)},{(0,1),(1,0)}):kind="GF2"
        elif len(scope)==2 and len(rows)==3:kind="BINARY_EXCLUSION"
        elif len(scope)==4:
            for p in I.permutations(range(4)):
                for k in range(4):
                    if set(rows)=={b for b in I.product((0,1),repeat=4) if (b[p[0]]+2*b[p[1]]+k)%4==b[p[2]]+2*b[p[3]]}:kind="ARITH2"
        relations.append((scope,rows,kind))
    pool=[{}]; steps=0
    for scope,rows,kind in sorted(relations,key=lambda r:len(r[1])):
        out=[]
        for a in pool:
            for b in rows:
                steps+=1
                if steps>budget:return "UNKNOWN",relations
                if all(v not in a or a[v]==x for v,x in zip(scope,b)):
                    out.append(dict(a,**{}) | dict(zip(scope,b)))
        pool=out
        if not pool:return "UNSAT",relations
    return "SAT",relations
def test():
    from pathlib import Path
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"atlas23_closure"))
    from closure import encode
    rng=random.Random(2401); counts=defaultdict(int)
    for cap,inc in I.product(range(3),range(4)):
        _,cs=encode(cap,inc)
        for rep in range(20):
            perm=list(range(1,6));rng.shuffle(perm)
            signs=[rng.choice((-1,1)) for _ in perm]
            raw=[[ (1 if l>0 else -1)*signs[abs(l)-1]*perm[abs(l)-1] for l in c] for c in cs]
            rng.shuffle(raw)
            for c in raw:rng.shuffle(c)
            status,rels=solve(raw)
            truth=any(all(any(b[abs(l)-1]==(l>0) for l in c) for c in raw) for b in I.product((0,1),repeat=5))
            assert status==("SAT" if truth else "UNSAT")
            counts[status]+=1
    print(json.dumps(dict(counts)))
if __name__=="__main__":test()
