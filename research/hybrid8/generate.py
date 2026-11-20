#!/usr/bin/env python3
"""DRNAS HYBRID8 source-only XOR/2SAT -> DRUP.
Narrow, reproducible witness-to-proof construction; no DPLL/SAT solver.
A produced DRUP is UNVERIFIED until a separate checker accepts it.
"""
from pathlib import Path
from collections import defaultdict
import itertools,random,argparse,json

def make(k,mode='unsat',seed=None):
    assert k>=3
    a=list(range(1,k+1));b=list(range(k+1,2*k+1));n=2*k;C=[]
    def alloc():
        nonlocal n
        n+=1;return n
    def parity(vs,r):
        for bits in itertools.product((0,1),repeat=len(vs)):
            if sum(bits)%2!=r:C.append(tuple(-v if bit else v for v,bit in zip(vs,bits)))
    for i,(x,y) in enumerate(zip(a,b)):
        p,q=alloc(),alloc()
        for j,(u,v) in enumerate([(x,p),(p,y),(y,q),(q,x)]):
            if mode=='broken' and i==0 and j==3:continue
            C.append((-u,v))
    for vs,r in ((a,1),(b,1 if mode=='sat' else 0)):
        z=alloc();parity((vs[0],vs[1],z),0)
        for x in vs[2:-1]:
            nxt=alloc();parity((z,x,nxt),0);z=nxt
        parity((z,vs[-1]),r)
    if seed is not None:
        rng=random.Random(seed);order=list(range(1,n+1));rng.shuffle(order)
        ren={i:order[i-1] for i in range(1,n+1)}
        C=[tuple((1 if x>0 else -1)*ren[abs(x)] for x in c) for c in C]
        C=[tuple(rng.sample(c,len(c))) for c in C];rng.shuffle(C)
    return n,C

def write_cnf(p,n,C):
    Path(p).write_text(f'p cnf {n} {len(C)}\n'+''.join(' '.join(map(str,c))+' 0\n' for c in C))

def parse(path):
    n=m=None;C=[];row=[]
    for line in Path(path).read_text().splitlines():
        s=line.strip()
        if not s or s.startswith('c'):continue
        if s.startswith('p '):
            p=s.split();assert p[1]=='cnf' and len(p)==4
            n,m=map(int,p[2:]);continue
        for token in s.split():
            x=int(token)
            if x==0:C.append(tuple(row));row=[]
            else:row.append(x)
    assert n and len(C)==m and not row
    return n,C

def xors(C):
    g=defaultdict(set)
    for c in C:
        vs=tuple(sorted(map(abs,c)))
        if len(vs) not in (2,3) or len(set(vs))!=len(vs):continue
        bits=tuple(int(next(l for l in c if abs(l)==v)<0) for v in vs)
        g[vs].add(bits)
    out=[]
    for vs,patterns in sorted(g.items()):
        for p in (0,1):
            if sum(sum(t)%2==p for t in patterns)==2**(len(vs)-1):out.append((vs,1-p))
    return out

def scc(n,C):
    G=[[] for _ in range(2*n)];R=[[] for _ in range(2*n)]
    def idx(l):return 2*(abs(l)-1)+(l<0)
    for c in C:
        if len(c)!=2:continue
        for a,b in ((-c[0],c[1]),(-c[1],c[0])):
            v,w=idx(a),idx(b);G[v].append(w);R[w].append(v)
    seen=bytearray(2*n);order=[]
    for root in range(2*n):
        if seen[root]:continue
        st=[(root,0)];seen[root]=1
        while st:
            u,i=st[-1]
            if i==len(G[u]):order.append(u);st.pop();continue
            st[-1]=(u,i+1);v=G[u][i]
            if not seen[v]:seen[v]=1;st.append((v,0))
    comp=[-1]*(2*n);cc=0
    for root in reversed(order):
        if comp[root]>=0:continue
        st=[root];comp[root]=cc
        while st:
            u=st.pop()
            for v in R[u]:
                if comp[v]<0:comp[v]=cc;st.append(v)
        cc+=1
    return comp

def emit(c,controls):
    out=[]
    for j in range(len(controls),-1,-1):
        for bits in itertools.product((False,True),repeat=j):
            out.append(tuple(c)+tuple(-x if bit else x for x,bit in zip(controls[:j],bits)))
    return out

def relation_clauses(a,b,d):
    return [(-a,b if d==0 else -b),(a,-b if d==0 else b)]

def solve(n,C):
    eq=xors(C);co=scc(n,C)
    if any(co[2*i]==co[2*i+1] for i in range(n)):return None
    vars=sorted({v for vs,_ in eq for v in vs});rel={};proof=[]
    for i,a in enumerate(vars):
        for b in vars[i+1:]:
            d=(0 if co[2*(a-1)]==co[2*(b-1)] else
               1 if co[2*(a-1)]==co[2*(b-1)+1] else None)
            if d is None:continue
            rel[(a,b)]=d;proof.extend(relation_clauses(a,b,d))
    initial=len(proof)//2;triples=[q for q in eq if len(q[0])==3];pairs=[q for q in eq if len(q[0])==2];derived=0
    def get(a,b):return 0 if a==b else rel.get(tuple(sorted((a,b))))
    def paired(a,b):
        for is_ in itertools.permutations(range(3),2):
            for js in itertools.permutations(range(3),2):
                d=[get(a[i],b[j]) for i,j in zip(is_,js)]
                if all(x is not None for x in d):
                    x=a[({0,1,2}-set(is_)).pop()];y=b[({0,1,2}-set(js)).pop()]
                    return x,y,d,[a[i] for i in is_]
        return None
    while True:
        updated=False
        for i,(a,ra) in enumerate(triples):
            for b,rb in triples[i+1:]:
                hit=paired(a,b)
                if hit is None:continue
                u,v,ds,controls=hit
                if u==v:continue
                d=ra^rb^ds[0]^ds[1];key=tuple(sorted((u,v)))
                if key in rel:
                    if rel[key]!=d:
                        proof.extend(emit((),controls))
                        return proof,dict(initial=initial,gates=derived,rows=len(eq))
                    continue
                for c in relation_clauses(u,v,d):proof.extend(emit(c,controls))
                rel[key]=d;derived+=1;updated=True;break
            if updated:break
        if not updated:break
    for i,(a,ra) in enumerate(pairs):
        for b,rb in pairs[i+1:]:
            for ordered in (b,b[::-1]):
                d0=get(a[0],ordered[0]);d1=get(a[1],ordered[1])
                if d0 is not None and d1 is not None and ra^rb^d0^d1==1:
                    proof.extend(emit((),a))
                    return proof,dict(initial=initial,gates=derived,rows=len(eq))
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--k',type=int,required=True);p.add_argument('--mode',choices=['unsat','sat','broken'],default='unsat')
    p.add_argument('--seed',type=int);p.add_argument('--prefix',required=True)
    a=p.parse_args();n,C=make(a.k,a.mode,a.seed)
    prefix=Path(a.prefix);prefix.parent.mkdir(parents=True,exist_ok=True)
    write_cnf(str(prefix)+'.cnf',n,C)
    found=solve(*parse(str(prefix)+'.cnf'))
    if found is None:
        print(json.dumps({'status':'UNKNOWN','k':a.k,'mode':a.mode,'seed':a.seed}));return
    proof,stats=found
    Path(str(prefix)+'.drup').write_text(''.join(' '.join(map(str,c))+' 0\n' if c else '0\n' for c in proof))
    print(json.dumps({'status':'EMITTED_UNCHECKED','k':a.k,'mode':a.mode,'seed':a.seed,'nvars':n,'nclauses':len(C),'steps':len(proof),**stats}))

if __name__=='__main__':main()
