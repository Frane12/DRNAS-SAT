#!/usr/bin/env python3
"""Independent 2-CNF implication module: export source-clause-backed signed links.
No SAT/UNSAT result is claimed. The recipient must validate all claims anew.
"""
import argparse, collections, hashlib, json
from pathlib import Path
from itertools import product
from emit_veripb_indirect import ordered_dimacs

def make_exchange(raw):
    nv,clauses=ordered_dimacs(raw)
    original={frozenset(c) for c in clauses}
    candidates=[tuple(c) for c in clauses if 3<=len(c)<=64 and all(x>0 for x in c)
                and len(set(c))==len(c) and all(frozenset((-a,-b)) in original
                for i,a in enumerate(c) for b in c[i+1:])]
    xorvars=set()
    rows=collections.defaultdict(set)
    for c in clauses:
        v=tuple(sorted(abs(x) for x in c))
        if len(v) not in (3,4) or len(set(v))!=len(v):continue
        rows[v].add(tuple(int(next(z for z in c if abs(z)==x)<0) for x in v))
    for v,patterns in rows.items():
        if any({bits for bits in product((0,1),repeat=len(v)) if sum(bits)%2==p} <= patterns for p in (0,1)):
            xorvars.update(v)
    G=collections.defaultdict(list)
    for c in clauses:
        if len(c)==2:
            a,b=c
            G[-a].append(b);G[-b].append(a)
    for v in G:G[v]=sorted(set(G[v]))
    def path(a,b):
        parent={a:None};queue=collections.deque([a])
        while queue and b not in parent:
            u=queue.popleft()
            for v in G[u]:
                if v not in parent:parent[v]=u;queue.append(v)
        if b not in parent:return None
        trace=[];cur=b
        while cur is not None:trace.append(cur);cur=parent[cur]
        return trace[::-1]
    for group in candidates:
        allowed=sorted(xorvars-set(group));links=[];used=set()
        for x in group:
            opts=[]
            for y in allowed:
                for bit in (0,1):
                    target=y if bit==0 else -y
                    p=path(x,target);q=path(target,x)
                    if p and q:opts.append((y,bit,p,q))
            if len(opts)!=1:break
            y,bit,p,q=opts[0]
            if y in used:break
            used.add(y)
            links.append({"x":x,"y":y,"xor_bit":bit,
                          "path_xy":p,"path_yx":q})
        if len(links)==len(group):
            return {"format":"DRNAS-2SAT-SIGNED-LINKS-v1",
                    "source_sha256":hashlib.sha256(raw).hexdigest(),
                    "onehot":list(group),"links":links,
                    "producer":"2-CNF source implication paths, no SAT oracle",
                    "verdict":"FACTS_ONLY_UNCHECKED"}
    return {"format":"DRNAS-2SAT-SIGNED-LINKS-v1",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "verdict":"UNKNOWN_NO_COMPLETE_LINK_MAP",
            "onehot":[],"links":[]}

def main():
    p=argparse.ArgumentParser();p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();r=make_exchange(a.cnf.read_bytes())
    a.output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"verdict":r["verdict"],"links":len(r["links"]),
                      "source_sha256":r["source_sha256"]},sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
