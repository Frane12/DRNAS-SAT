#!/usr/bin/env python3
"""HYBRID10 extended source-generation audit. No proof emitter is imported."""
from pathlib import Path
from random import Random
from generate_cases import construct,write
import sys,hashlib

out=Path(sys.argv[1] if len(sys.argv)>1 else "/tmp/h10extended")
out.mkdir(parents=True,exist_ok=True)

def shuffled(n,C,seed):
    rng=Random(seed);old=list(range(1,n+1));new=old.copy();rng.shuffle(new)
    mapping=dict(zip(old,new))
    outc=[tuple((1 if l>0 else -1)*mapping[abs(l)] for l in c) for c in C]
    outc=[tuple(rng.sample(c,len(c))) for c in outc]
    rng.shuffle(outc)
    return outc

for size in (10,12,16,20):
    N,C=construct(size)
    p=out/f"graph{size}.cnf"
    write(p,N,C)
    print("GENERATED",p.name,len(C),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)

N,C=construct(12)
for seed in (0,1,2,3):
    p=out/f"perm12_{seed}.cnf"
    write(p,N,shuffled(N,C,seed))
    print("PERMUTED",p.name,len(C),hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)

N,C=construct(12,True)
p=out/"sat12.cnf";write(p,N,C)
assignment={i:False for i in range(1,N+1)}
for i in (1,13,25,26):assignment[i]=True
assert all(any(assignment[abs(l)]==(l>0) for l in c) for c in C)
print("SAT12_EXPLICIT_MODEL_VERIFIED",flush=True)

# Remove a source XOR4 clause, while preserving DIMACS count and bytes otherwise.
N,C=construct(12)
target=next(i for i,c in enumerate(C) if len(c)==4)
bad=C[:target]+C[target+1:]
write(out/"missing_xor_clause.cnf",N,bad)
print("MUTATED_XOR_CLAUSE",flush=True)
