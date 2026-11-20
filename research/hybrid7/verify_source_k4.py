#!/usr/bin/env python3
"""Independent source-CNF audit of HYBRID-7's k=4 example.
It does not import the discovery code or trust generated witness metadata.
DRAT certification is performed separately by the GitHub workflow.
"""
from pathlib import Path
from collections import defaultdict,deque

HERE=Path(__file__).parent

def load(path):
    n=m=None;cl=[];row=[]
    for raw in path.read_text().splitlines():
        s=raw.strip()
        if not s or s.startswith('c'):continue
        if s.startswith('p '):
            p=s.split();n=int(p[2]);m=int(p[3]);continue
        for st in s.split():
            x=int(st)
            if x==0:cl.append(tuple(row));row=[]
            else:row.append(x)
    assert n and len(cl)==m and not row
    return n,cl

n,cs=load(HERE/'k4-mixed-unsat.cnf')
nc,ctrl=load(HERE/'k4-parity-control-sat.cnf')
assert n==nc==20 and len(cs)==len(ctrl)==36

def sat(cl,truth):
    return all(any(truth[abs(l)]==(l>0) for l in c) for c in cl)
# Independently show that each side has a satisfying assignment.
binary=[c for c in cs if len(c)==2]
xor_only=cs[16:]
M={i:False for i in range(1,21)}
M[18]=True
assert sat(binary,M)
M={i:False for i in range(1,21)}
M[1]=M[17]=M[18]=True
assert sat(xor_only,M)
M={i:False for i in range(1,21)}
for i in [1,5,9,10,17,18,19,20]:M[i]=True
assert sat(ctrl,M)
print('BINARY_ONLY_SAT XOR_ONLY_SAT CONTROL_FULL_SAT')

# Independent XOR extraction directly from source clause groups.
groups=defaultdict(set)
for c in cs:
    vs=tuple(sorted(map(abs,c)))
    if 2<=len(vs)<=4 and len(set(vs))==len(vs):
        bits=tuple(int(next(l for l in c if abs(l)==v)<0) for v in vs)
        groups[vs].add(bits)
rows=[]
for vs,patterns in groups.items():
    for p in (0,1):
        matched={t for t in patterns if sum(t)%2==p}
        if len(matched)==2**(len(vs)-1):rows.append((sum(1<<(v-1) for v in vs),1-p))
assert len(rows)==6

def inconsistent(R):
    piv={}
    for mask,rhs in R:
        while mask:
            i=mask.bit_length()-1
            if i not in piv:piv[i]=(mask,rhs);break
            m,r=piv[i];mask^=m;rhs^=r
        else:
            if rhs:return True
    return False

assert not inconsistent(rows)
# Walk actual binary implication edges, never trust source comments.
G=defaultdict(list)
for c in cs:
    if len(c)==2:
        x,y=c
        G[-x].append(y)
        G[-y].append(x)
def reachable(start,end):
    todo=deque([start]);seen={start}
    while todo:
        x=todo.popleft()
        if x==end:return True
        for y in G[x]:
            if y not in seen:seen.add(y);todo.append(y)
    return False
relations=[]
for i in range(1,5):
    assert reachable(i,i+4) and reachable(i+4,i)
    assert not any(set(map(abs,c))=={i,i+4} for c in cs if len(c)==2)
    relations.append(((1<<(i-1))^(1<<(i+3)),0))
assert not inconsistent(relations)
assert inconsistent(rows+relations)
print('SOURCE_XOR_EQUIVALENCE_GF2_CONTRADICTION_VERIFIED')
