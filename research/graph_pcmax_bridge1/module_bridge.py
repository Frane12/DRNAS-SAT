#!/usr/bin/env python3
"""GRAPH -> PCMAX modular source-bound exchange (synthetic proof-of-concept).

The GRAPH producer independently reconstructs color-clique capacity facts from
original CNF. The PCMAX consumer rechecks these facts against ORIGINAL CNF,
locates an independent 'at least two selections of one color' quota, and emits
a VeriPB 3.0 cutting-planes contradiction. No SAT result without external check.

Standalone GRAPH and PCMAX commands never claim UNSAT. This experiment is a
restricted constructed *list-color/quota* bridge, not arbitrary graph coloring.
"""
import argparse, collections, hashlib, itertools, json, random, sys, time
from pathlib import Path

class Unsupported(ValueError): pass
def need(ok,reason):
    if not ok: raise Unsupported(reason)

def parse(raw):
    need(len(raw)<=10_000_000,"byte_limit")
    nv=nc=None;pending=[];clauses=[]
    for line in raw.decode("ascii").splitlines():
        toks=line.split()
        if not toks or toks[0]=="c":continue
        if toks[0]=="p":
            need(nv is None and len(toks)==4 and toks[1]=="cnf","header")
            nv,nc=int(toks[2]),int(toks[3])
            need(0<nv<=40000 and 0<nc<=120000,"header_bounds")
            continue
        need(nv is not None,"header_missing")
        for token in toks:
            v=int(token);need(abs(v)<=nv,"literal_range")
            if v:pending.append(v)
            else:clauses.append(tuple(pending));pending=[]
    need(nv is not None and not pending and len(clauses)==nc,"clause_count")
    return nv,clauses

def construct(k,seed,mode):
    need(3<=k<=20,"k_bound")
    need(mode in ("unsat","no_quota","drop_quota","drop_edge"),"mode")
    def v(j,c):return j*k+c+1
    clauses=[]
    for j in range(k):
        group=[v(j,c) for c in range(k)]
        clauses.append(tuple(group))
        for a,b in itertools.combinations(group,2):
            clauses.append((-a,-b))
    for j,h in itertools.combinations(range(k),2):
        for c in range(k):
            if mode=="drop_edge" and (j,h,c)==(0,1,0):continue
            clauses.append((-v(j,c),-v(h,c)))
    if mode!="no_quota":
        for omitted in range(k):
            if mode=="drop_quota" and omitted==0:continue
            clauses.append(tuple(v(j,0) for j in range(k) if j!=omitted))
    a={v(j,c):False for j in range(k) for c in range(k)}
    if mode in ("no_quota","drop_quota"):
        for j in range(k):a[v(j,j)]=True
    elif mode=="drop_edge":
        a[v(0,0)]=a[v(1,0)]=True
        for j in range(2,k):a[v(j,j-1)]=True
    if mode!="unsat":
        need(all(any(a[abs(l)]==(l>0) for l in clause) for clause in clauses),"SAT_control_bad")
    rng=random.Random(seed)
    new=list(range(1,k*k+1));rng.shuffle(new)
    remap={i+1:z for i,z in enumerate(new)}
    clauses=[tuple(rng.sample([remap[abs(l)] if l>0 else -remap[abs(l)] for l in clause],len(clause)))
             for clause in clauses]
    rng.shuffle(clauses)
    if mode!="unsat":
        mapped={remap[x]:val for x,val in a.items()}
        need(all(any(mapped[abs(l)]==(l>0) for l in clause) for clause in clauses),"permuted_SAT_bad")
    raw=(f"p cnf {k*k} {len(clauses)}\n"+
         "".join(" ".join(map(str,c))+" 0\n" for c in clauses)).encode("ascii")
    return raw,{"k":k,"mode":mode,"seed":seed,
                "variables":k*k,"clauses":len(clauses),
                "sha256":hashlib.sha256(raw).hexdigest(),
                "sat_model_verified_by_constructor":mode!="unsat"}

def graph_facts(raw):
    """Source-only k-color clique extractor, no UNSAT claim."""
    started=time.perf_counter()
    nv,clauses=parse(raw)
    src={frozenset(c) for c in clauses}
    positives=collections.defaultdict(list)
    for c in clauses:
        if len(c)>=3 and len(c)<=20 and all(x>0 for x in c) and len(c)==len(set(c)):
            positives[len(c)].append(tuple(c))
    for k in sorted(positives,reverse=True):
        groups=positives[k]
        if len(groups)!=k:continue
        chosen=set()
        if any(chosen.intersection(g) or chosen.update(g) for g in groups):continue
        # Anchor-group orientation is arbitrary; align every other group using
        # ORIGINAL source pairwise negative constraints.
        first=groups[0]
        aligned=[list(first)]
        ok=True
        for g in groups[1:]:
            perm=[]
            for x in first:
                matches=[y for y in g if frozenset((-x,-y)) in src]
                if len(matches)!=1:
                    ok=False;break
                perm.append(matches[0])
            if not ok or len(set(perm))!=k:
                ok=False;break
            aligned.append(perm)
        if not ok:continue
        for i,j in itertools.combinations(range(k),2):
            if any(frozenset((-aligned[i][c],-aligned[j][c])) not in src
                   for c in range(k)):
                ok=False;break
        if not ok:continue
        return {"format":"DRNAS-GRAPH-COLOR-CAPACITY-EXCHANGE-v1",
                "status":"SOURCE_FACTS_ONLY_NO_SAT_VERDICT",
                "source_sha256":hashlib.sha256(raw).hexdigest(),
                "color_count":k,"source_variables":nv,
                "source_clauses":len(clauses),
                "aligned_vertices":aligned,
                "capacity_per_color":[1]*k,
                "edge_clause_checks":k*(k-1)//2*k,
                "graph_only":"UNKNOWN_NO_K_PLUS_ONE_CLIQUE",
                "elapsed_s":time.perf_counter()-started}
    return {"format":"DRNAS-GRAPH-COLOR-CAPACITY-EXCHANGE-v1",
            "status":"UNKNOWN_GRAPH_STRUCTURE_UNSUPPORTED",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "elapsed_s":time.perf_counter()-started}

def make_proof(raw,facts):
    from source_check import verify
    checked=verify(raw,facts)
    _,clauses=parse(raw)
    src={frozenset(c):i for i,c in enumerate(clauses,1)}
    vector=checked["quota_vector"]
    k=len(vector)
    proof=["pseudo-Boolean proof version 3.0",f"f {len(clauses)} ;"]
    last=len(clauses)
    prior=src[frozenset((-vector[0],-vector[1]))]
    for r in range(3,k+1):
        new=vector[r-1]
        ops=[str(prior)]
        if r-2>1:ops.extend((str(r-2),"*"))
        for x in vector[:r-1]:
            ops.extend((str(src[frozenset((-x,-new))]),"+"))
        ops.extend((str(r-1),"d"))
        proof.append("pol "+" ".join(ops)+" ;")
        last+=1;prior=last
    # Every (k-1)-of-k quota clause must be source-present: together they imply
    # (k-1)*sum(x)>=k, hence sum(x)>=2 by cutting-planes division.
    quota=[src[frozenset(x for j,x in enumerate(vector) if j!=missing)]
           for missing in range(k)]
    ops=[str(quota[0])]
    for idx in quota[1:]:ops.extend((str(idx),"+"))
    ops.extend((str(k-1),"d"))
    proof.append("pol "+" ".join(ops)+" ;")
    last+=1
    quota_row=last
    # color resource upper bound sum(~x)>=k-1 + quota lower sum(x)>=2,
    # so 0>=1, with no search.
    proof.append(f"pol {prior} {quota_row} + ;")
    proof.extend(("output NONE ;","conclusion UNSAT ;","end pseudo-Boolean proof ;"))
    data="\n".join(proof)+"\n"
    return data,{"status":"EMITTED_UNCHECKED_REQUIRES_VERIPB",
                 "source_sha256":hashlib.sha256(raw).hexdigest(),
                 "quota_color_index":checked["quota_color_index"],
                 "demand_min":2,"graph_capacity_max":1,
                 "clique_vertices":k,"source_edge_checks":checked["edge_checks"],
                 "quota_clause_checks":checked["quota_clause_checks"],
                 "proof_bytes":len(data.encode()),
                 "proof_steps":len(proof)-5}

def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="command",required=True)
    g=sub.add_parser("generate")
    g.add_argument("--k",type=int,required=True)
    g.add_argument("--seed",type=int,required=True)
    g.add_argument("--mode",choices=("unsat","no_quota","drop_quota","drop_edge"),default="unsat")
    g.add_argument("--cnf",type=Path,required=True)
    g.add_argument("--meta",type=Path,required=True)
    x=sub.add_parser("graph")
    x.add_argument("--cnf",type=Path,required=True)
    x.add_argument("--facts",type=Path,required=True)
    y=sub.add_parser("capacity")
    y.add_argument("--cnf",type=Path,required=True)
    y.add_argument("--facts",type=Path)
    y.add_argument("--proof",type=Path,required=True)
    y.add_argument("--meta",type=Path,required=True)
    a=ap.parse_args()
    if a.command=="generate":
        raw,meta=construct(a.k,a.seed,a.mode)
        a.cnf.parent.mkdir(parents=True,exist_ok=True)
        a.cnf.write_bytes(raw);a.meta.write_text(json.dumps(meta,sort_keys=True,indent=2)+"\n")
        print("SOURCE_GENERATED "+json.dumps(meta,sort_keys=True))
        return 0
    raw=a.cnf.read_bytes()
    if a.command=="graph":
        out=graph_facts(raw)
        a.facts.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
        print("GRAPH "+json.dumps(out,sort_keys=True))
        return 0
    if a.command=="capacity":
        try:
            need(a.facts is not None,"NO_GRAPH_FACTS_TRANSPORT_OFF")
            facts=json.loads(a.facts.read_text())
            proof,meta=make_proof(raw,facts)
            a.proof.write_text(proof);a.meta.write_text(json.dumps(meta,sort_keys=True,indent=2)+"\n")
            print("CAPACITY "+json.dumps(meta,sort_keys=True))
            return 0
        except (Unsupported,ValueError,KeyError,TypeError,OverflowError,UnicodeError,OSError) as err:
            a.proof.unlink(missing_ok=True);a.meta.unlink(missing_ok=True)
            print("CAPACITY_UNKNOWN "+str(err),flush=True)
            return 2

if __name__=="__main__":
    sys.exit(main())
