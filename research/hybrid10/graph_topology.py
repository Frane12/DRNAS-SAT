#!/usr/bin/env python3
"""Different connected 3-regular graph topologies in SOURCE CNF format.
The separate proof generator receives only the CNF file, no graph labels.
"""
from pathlib import Path
from itertools import product
from random import Random
def shuffled(n,C,seed):
    rng=Random(seed)
    order=list(range(1,n+1));rng.shuffle(order)
    ren={i:order[i-1] for i in range(1,n+1)}
    out=[tuple((1 if lit>0 else -1)*ren[abs(lit)] for lit in c) for c in C]
    out=[tuple(rng.sample(c,len(c))) for c in out]
    rng.shuffle(out)
    return out
import sys,hashlib

def cubic(n,seed):
    assert n>=6 and n%2==0
    rng=Random(seed)
    ring={tuple(sorted((i,(i+1)%n))) for i in range(n)}
    for _ in range(2000):
        vs=list(range(n));rng.shuffle(vs)
        matching={tuple(sorted((vs[i],vs[i+1]))) for i in range(0,n,2)}
        if not matching.intersection(ring):
            edges=sorted(ring|matching)
            assert len(edges)==3*n//2
            assert all(sum(v in e for e in edges)==3 for v in range(n))
            return edges
    raise RuntimeError("no admissible perfect matching")

def make(n,seed,sat_control=False):
    edges=cubic(n,seed)
    N=2*n;xs=list(range(1,n+1));ys=list(range(n+1,2*n+1))
    C=[tuple(xs)]+[(-a,-b) for i,a in enumerate(xs) for b in xs[i+1:]]
    for x,y in zip(xs,ys):
        p=N+1;q=N+2;N+=2
        C.extend([(-x,p),(-p,y),(-y,q),(-q,x)])
    adj=[[] for _ in range(n)]
    for a,b in edges:
        N+=1;adj[a].append(N);adj[b].append(N)
    for v,y in enumerate(ys):
        vars=(y,*adj[v]);rhs=1 if sat_control and v==0 else 0
        for bits in product((0,1),repeat=4):
            if sum(bits)%2!=rhs:
                C.append(tuple(-x if b else x for x,b in zip(vars,bits)))
    assert len(C)==1+n*(n-1)//2+4*n+8*n
    return N,C

def write(path,N,C):
    path.write_text(f'p cnf {N} {len(C)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in C))

def main(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for n,seed in ((10,101),(10,202),(12,303),(12,404),(16,505),(20,606)):
        N,C=make(n,seed)
        p=out/f"cubic{n}_seed{seed}.cnf"
        write(p,N,shuffled(N,C,seed+10000))
        print("CUBIC_SOURCE",n,seed,len(C),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
    N,C=make(12,707,True)
    sat=out/"cubic12_sat_control.cnf";write(sat,N,C)
    vals={i:False for i in range(1,N+1)}
    for i in (1,13,25,26):vals[i]=True
    assert all(any(vals[abs(l)]==(l>0) for l in c) for c in C)
    print("CUBIC_SAT_MODEL_VERIFIED",flush=True)

if __name__=="__main__":main(sys.argv[1] if len(sys.argv)>1 else "/tmp/hybrid10-cubic")
