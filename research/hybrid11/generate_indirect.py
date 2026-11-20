#!/usr/bin/env python3
"""Source-only HYBRID-11 benchmark constructor.
Outputs DIMACS CNF with no hints/metadata used by the proof emitter.
Produces fresh connected cubic topologies, split XOR3 gates, sign-flipped
2SAT equality paths, and source-mutated / model-verified SAT controls.
"""
import argparse,hashlib,itertools,json,random
from pathlib import Path
from collections import deque

def cubic(n,seed):
    if n==4:return [(i,j) for i in range(4) for j in range(i+1,4)]
    assert n>=6 and n%2==0
    rng=random.Random(seed)
    ring={tuple(sorted((i,(i+1)%n))) for i in range(n)}
    for _ in range(2000):
        vs=list(range(n));rng.shuffle(vs)
        matching={tuple(sorted((vs[i],vs[i+1]))) for i in range(0,n,2)}
        if not ring.intersection(matching):return sorted(ring|matching)
    raise ValueError("failed to construct cubic graph")

def generate(n,seed,mode="unsat",structure="split",permute=False,noise=False):
    assert n%2==0 and n>=4 and structure in ("split","mixed","direct")
    edges=cubic(n,seed)
    N=2*n
    xs=list(range(1,n+1));ys=list(range(n+1,2*n+1));cs=[tuple(xs)]
    cs += [(-x,-y) for i,x in enumerate(xs) for y in xs[i+1:]]
    def alloc():
        nonlocal N
        N+=1;return N
    flip=[(i+seed)%3==0 for i in range(n)]
    if not any(flip):flip[0]=True
    link_units=[]
    for i,(x,y) in enumerate(zip(xs,ys)):
        p,q=alloc(),alloc()
        if flip[i]:
            paths=[(-x,p),(-p,-y),(y,q),(-q,x)]
        else:
            paths=[(-x,p),(-p,y),(-y,q),(-q,x)]
        link_units.append((p,q))
        cs.extend(paths)

    incidence=[[] for _ in range(n)]
    for a,b in edges:
        z=alloc();incidence[a].append((z,b));incidence[b].append((z,a))
    charge=[0]*n
    charge[0]=sum(flip)%2
    if mode=="sat":charge[0]^=1
    xor_gates=[]
    def parity(vars,rhs):
        for bits in itertools.product((0,1),repeat=len(vars)):
            if sum(bits)%2!=rhs:
                cs.append(tuple(-v if bit else v for v,bit in zip(vars,bits)))
    for i,y in enumerate(ys):
        z=[t[0] for t in incidence[i]]
        assert len(z)==3
        split=structure=="split" or (structure=="mixed" and (i+seed)%3!=0)
        if not split:
            parity((y,*z),charge[i])
            xor_gates.append(("direct",i,None,z))
        else:
            t=alloc()
            if (i+seed)%2==0:
                parity((y,z[0],t),0)
                parity((t,z[1],z[2]),charge[i])
                xor_gates.append(("split_y_edge",i,t,z))
            else:
                parity((z[0],z[1],t),0)
                parity((y,t,z[2]),charge[i])
                xor_gates.append(("split_edges",i,t,z))

    if noise:
        a,b,c=alloc(),alloc(),alloc()
        parity((a,b,c),0)

    if mode=="missing_gate":
        # First XOR3 gate loses a source assignment-exclusion clause;
        # no longer a recognized full XOR row.
        ix=next(i for i,c in enumerate(cs) if len(c)==3)
        del cs[ix]
    elif mode=="broken_link":
        # The first link source implication is removed, so its SCC relation
        # is no longer guaranteed.
        ix=next(i for i,c in enumerate(cs) if c==((-xs[0],link_units[0][0])))
        del cs[ix]
    elif mode=="missing_amo":
        ix=next(i for i,c in enumerate(cs) if frozenset(c)==frozenset((-xs[0],-xs[1])))
        del cs[ix]
    elif mode not in ("sat","unsat"):
        raise ValueError("unknown mode")

    assignment=None
    if mode=="sat":
        # Exact satisfying model: x1=1, others=0; y=x XOR flip.
        A={i:False for i in range(1,N+1)}
        for i,(x,y) in enumerate(zip(xs,ys)):
            vx=int(i==0)
            A[x]=bool(vx);A[y]=bool(vx^int(flip[i]))
            p,q=link_units[i];A[p]=A[q]=bool(vx)
        # Find GF(2) solution to edge-parity constraints using a spanning tree.
        adjacency=[[] for _ in range(n)]
        for a,b in edges:
            za=next(z for z,other in incidence[a] if other==b)
            adjacency[a].append((b,za));adjacency[b].append((a,za))
        parent=[-1]*n; parentedge=[None]*n;parent[0]=0;order=[0]
        for v in order:
            for w,z in adjacency[v]:
                if parent[w]<0:parent[w]=v;parentedge[w]=z;order.append(w)
        assert len(order)==n
        target=[charge[i]^int(A[ys[i]]) for i in range(n)]
        for v in reversed(order[1:]):
            z=parentedge[v]
            A[z]=bool(target[v]^sum(int(A[e]) for w,e in adjacency[v] if e!=z)%2)
        assert (sum(int(A[e]) for w,e in adjacency[0])%2)==target[0]
        for kind,i,t,z in xor_gates:
            if t is None:continue
            if kind=="split_y_edge":A[t]=A[ys[i]]^A[z[0]]
            else:A[t]=A[z[0]]^A[z[1]]
        assert all(any(A[abs(l)]==(l>0) for l in c) for c in cs)
        assignment=A

    if permute:
        rng=random.Random(seed+110117)
        old=list(range(1,N+1));new=old.copy();rng.shuffle(new)
        rename=dict(zip(old,new))
        cs=[tuple((1 if v>0 else -1)*rename[abs(v)] for v in c) for c in cs]
        cs=[tuple(rng.sample(c,len(c))) for c in cs]
        rng.shuffle(cs)
        if assignment is not None:
            assignment={rename[i]:value for i,value in assignment.items()}
            assert all(any(assignment[abs(l)]==(l>0) for l in c) for c in cs)
    meta={"vertices":n,"variables":N,"source_clauses":len(cs),
          "source_gate_splits":sum(t is not None for _,_,t,_ in xor_gates),
          "negated_2sat_links":sum(flip),"mode":mode,"topology_seed":seed,
          "structure":structure,"permuted":permute,"noise":noise}
    return N,cs,assignment,meta

def output(path,n,C):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(f"p cnf {n} {len(C)}\n"+"".join(" ".join(map(str,c))+" 0\n" for c in C))
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--n",type=int,required=True)
    a.add_argument("--seed",type=int,default=101)
    a.add_argument("--structure",choices=("split","mixed","direct"),default="split")
    a.add_argument("--mode",choices=("unsat","sat","missing_gate","broken_link","missing_amo"),default="unsat")
    a.add_argument("--permute",action="store_true")
    a.add_argument("--noise",action="store_true")
    a.add_argument("--output",required=True)
    o=a.parse_args()
    n,C,model,meta=generate(o.n,o.seed,o.mode,o.structure,o.permute,o.noise)
    meta["source_sha256"]=output(o.output,n,C)
    meta["sat_model_verified"]=model is not None
    print("HYBRID11_SOURCE "+json.dumps(meta,sort_keys=True),flush=True)
if __name__=="__main__":main()
