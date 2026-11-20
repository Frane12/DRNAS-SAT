#!/usr/bin/env python3
"""Independent ordinary-resolution baseline; no hybrid-witness producer import."""
from itertools import product
from collections import defaultdict
from pathlib import Path
import hashlib,sys,json

def construct(n,parity_control=False):
    assert n==4 or (n%2==0 and n>=6)
    N=2*n; xs=list(range(1,n+1));ys=list(range(n+1,2*n+1))
    C=[tuple(xs)]+[(-a,-b) for i,a in enumerate(xs) for b in xs[i+1:]]
    for x,y in zip(xs,ys):
        p=N+1;q=N+2;N+=2
        C.extend([(-a,b) for a,b in ((x,p),(p,y),(y,q),(q,x))])
    if n==4:edges=[(i,j) for i in range(4) for j in range(i+1,4)]
    else:
        k=n//2
        edges=[(i,(i+1)%k) for i in range(k)]+[(i+k,(i+1)%k+k) for i in range(k)]+[(i,i+k) for i in range(k)]
    adjacent=defaultdict(list)
    for a,b in edges:
        N+=1;adjacent[a].append(N);adjacent[b].append(N)
    for i,y in enumerate(ys):
        variables=(y,*adjacent[i]);rhs=int(parity_control and i==0)
        for bits in product((0,1),repeat=len(variables)):
            if sum(bits)%2!=rhs:C.append(tuple(-v if bit else v for v,bit in zip(variables,bits)))
    return N,C

def write(path,N,C):
    Path(path).write_text(f'p cnf {N} {len(C)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in C))

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def norm(C):
    C=set(C)
    return None if any(-v in C for v in C) else tuple(sorted(C,key=lambda v:(abs(v),v)))

def resolution(C,limit=6000):
    active=set(norm(c) for c in C);proof=[]
    while active:
        pos=defaultdict(list);neg=defaultdict(list)
        for c in active:
            for lit in c:(pos if lit>0 else neg)[abs(lit)].append(c)
        both=set(pos)&set(neg)
        if not both:raise RuntimeError('source not refuted')
        v=min(both,key=lambda x:(len(pos[x])*len(neg[x]),sum(map(len,pos[x]+neg[x])),x))
        new=set()
        for a in pos[v]:
            aa=set(a)-{v}
            for b in neg[v]:
                c=norm(aa.union(set(b)-{-v}))
                if c is None or c in active or c in new:continue
                new.add(c)
                if len(proof)+len(new)>limit:raise RuntimeError('proof budget exceeded')
                if c==():
                    proof.extend(sorted(new,key=lambda z:(len(z),z)))
                    return proof[:proof.index(())+1]
        active.difference_update(pos[v]);active.difference_update(neg[v]);active.update(new)
        proof.extend(sorted(new,key=lambda z:(len(z),z)))
    raise RuntimeError('no empty clause')

def main(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    hashes={4:'9958ed99d3c0f32a2d62ac804a08c39c20024e6aa30704abdddb59b8f06f60c6',
            6:'ebd64629dec735e51d05864167ce953c488c9315520be188e3b618d2b41cb1ed',
            8:'02fa54d500330d425c9bf3eada10cb7f5e983d6852a81e9f31b7e97207595219'}
    summary=[]
    for n in (4,6,8):
        N,C=construct(n);path=root/f'graph{n}.cnf';write(path,N,C)
        if digest(path)!=hashes[n]:raise RuntimeError('source differs from local experimental bytes')
        P=resolution(C);out=root/f'graph{n}.drup'
        out.write_text(''.join(' '.join(map(str,c))+' 0\n' for c in P))
        summary.append(dict(vertices=n,variables=N,source_clauses=len(C),drup_steps=len(P),sha256=digest(path)))
        print('GENERATED',n,len(P),flush=True)
    N,C=construct(6,True);control=root/'graph6-sat.cnf';write(control,N,C)
    truth={i:False for i in range(1,N+1)}
    for i in (1,7,13,14):truth[i]=True
    if not all(any(truth[abs(l)]==(l>0) for l in c) for c in C):raise RuntimeError('SAT control model not valid')
    print('SAT_MODEL_VERIFIED',flush=True)
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else '/tmp/hybrid9')
