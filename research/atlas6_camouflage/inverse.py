#!/usr/bin/env python3
"""ATLAS6 — reversible inversion of a camouflaged CNF AND-substitution.

Input: unmodified DIMACS. No filename, family label, SAT catalog verdict, graph
or hidden mapping is read by the detector. An eligible signed pair (a,b)
has two invariants:
  (i) source clauses containing ~a and ~b occur together in the same rows;
  (ii) source clauses containing positive a and positive b have identical
       multisets of the remaining literals, with exactly one per clause.
Then quotient a,b into q=a where q is interpreted as (a AND b).

An independent checker RE-EXPANDS every quotient step and requires exact
clause MULTISET equality to the original source. This gives semantic
equivalence under q=a AND b, not a general SAT/UNSAT assertion.
"""
from collections import Counter, defaultdict
from pathlib import Path
import itertools, hashlib, argparse, json, time, os

def parse(raw):
    n=m=None; cs=[];pending=[]
    for line in raw.decode("ascii").splitlines():
        f=line.split()
        if not f or f[0]=="c":continue
        if f[0]=="p":
            if n is not None or len(f)!=4 or f[1]!="cnf":raise ValueError("header")
            n,m=map(int,f[2:])
            if not (1<=n<=50000 and 0<=m<=200000):raise ValueError("bounds")
            continue
        if n is None:raise ValueError("missing_header")
        for word in f:
            lit=int(word)
            if abs(lit)>n:raise ValueError("literal_range")
            if lit:pending.append(lit)
            else:
                if len(pending)>32:raise ValueError("width")
                cs.append(tuple(pending));pending=[]
    if n is None or pending or len(cs)!=m:raise ValueError("clause_count")
    return n,cs

def encode(n,cs):
    return (f"p cnf {n} {len(cs)}\n"+
            "".join(" ".join(map(str,c))+" 0\n" for c in cs)).encode("ascii")

def canon(cs):
    return Counter(tuple(sorted(c)) for c in cs)

def candidates(clauses):
    occurrence=defaultdict(list)
    for idx,clause in enumerate(clauses):
        if len(set(clause))!=len(clause):raise ValueError("duplicate_literal_unsupported")
        for lit in clause:occurrence[lit].append(idx)
    grouped=defaultdict(list)
    for lit,indices in occurrence.items():
        grouped[tuple(indices)].append(lit)
    result=[]
    for signature,literals in grouped.items():
        if not signature or len(literals)<2:continue
        for neg_a,neg_b in itertools.combinations(literals,2):
            if abs(neg_a)==abs(neg_b):continue
            a,b=-neg_a,-neg_b
            if a not in occurrence or b not in occurrence:continue
            if len(occurrence[a])!=len(occurrence[b]):continue
            ca=Counter(tuple(sorted(set(clauses[i])-{a}))
                       for i in occurrence[a]
                       if b not in clauses[i] and -b not in clauses[i])
            cb=Counter(tuple(sorted(set(clauses[i])-{b}))
                       for i in occurrence[b]
                       if a not in clauses[i] and -a not in clauses[i])
            if ca and ca==cb and sum(ca.values())==len(occurrence[a])==len(occurrence[b]):
                result.append((a,b,len(signature),len(occurrence[a])))
    return sorted(result,key=lambda p:(-(p[2]+p[3]),min(abs(p[0]),abs(p[1])),
                                         max(abs(p[0]),abs(p[1]))))

def quotient(clauses,a,b):
    source=canon(clauses)
    out=Counter()
    for row,k in source.items():
        c=set(row)
        if -a in c or -b in c:
            if not(-a in c and -b in c):raise ValueError("unpaired_negative")
            c.remove(-b)
            out[tuple(sorted(c))]+=k
        elif a in c or b in c:
            if a in c:
                if b in c or -b in c:raise ValueError("both_positive")
                partner=tuple(sorted((c-{a})|{b}))
                if source[partner]!=k:raise ValueError("unmatched_positive")
                out[tuple(sorted(c))]+=k
            else:
                if a in c or -a in c:raise ValueError("both_positive")
                partner=tuple(sorted((c-{b})|{a}))
                if source[partner]!=k:raise ValueError("unmatched_positive")
        else:out[row]+=k
    return list(itertools.chain.from_iterable([row]*count for row,count in out.items()))

def expand(clauses,a,b):
    out=[]
    for row in clauses:
        c=set(row)
        if a in c:
            out.append(tuple(sorted(c)))
            out.append(tuple(sorted((c-{a})|{b})))
        elif -a in c:
            out.append(tuple(sorted(c|{-b})))
        else:out.append(tuple(sorted(c))
        )
    return out

def recover(raw,max_pairs=500):
    started=time.perf_counter()
    n,original=parse(raw)
    current=original
    steps=[];diagnostics=[]
    for iteration in range(max_pairs):
        found=candidates(current)
        if not found:break
        chosen=None
        for a,b,neg_count,pos_count in found:
            try:new=quotient(current,a,b)
            except ValueError:continue
            # Safety precheck, independently rechecked by checker.py
            if canon(expand(new,a,b))!=canon(current):continue
            chosen=(a,b,new,neg_count,pos_count)
            break
        if chosen is None:break
        a,b,new,negative,positive=chosen
        steps.append({"a":a,"b":b,"clauses_before":len(current),
                      "clauses_after":len(new),"neg_contexts":negative,
                      "positive_contexts":positive})
        current=new
    final=encode(n,current)
    return final,{"format":"DRNAS-ATLAS6-AND-QUOTIENT-v1",
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "quotient_sha256":hashlib.sha256(final).hexdigest(),
        "source_vars":n,"original_clauses":len(original),
        "quotient_clauses":len(current),"collapsed_pairs":len(steps),
        "pair_steps":steps,"no_sat_unsat_claim":True,
        "source_only_no_family_hints":True,
        "elapsed_s":round(time.perf_counter()-started,6)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",required=True,type=Path)
    p.add_argument("--quotient",required=True,type=Path)
    p.add_argument("--certificate",required=True,type=Path)
    a=p.parse_args()
    raw=a.cnf.read_bytes()
    try:
        q,meta=recover(raw)
        a.quotient.parent.mkdir(exist_ok=True,parents=True)
        a.quotient.write_bytes(q)
        a.certificate.write_text(json.dumps(meta,sort_keys=True,indent=2)+"\n")
        print("ATLAS6_RECOVER "+json.dumps({
            "source_sha256":meta["source_sha256"],
            "collapsed_pairs":meta["collapsed_pairs"],
            "original_clauses":meta["original_clauses"],
            "quotient_clauses":meta["quotient_clauses"],
            "elapsed_s":meta["elapsed_s"]},sort_keys=True),flush=True)
    except (ValueError,TypeError,UnicodeError,MemoryError,OverflowError) as err:
        a.quotient.unlink(missing_ok=True)
        a.certificate.unlink(missing_ok=True)
        print("ATLAS6_UNKNOWN "+str(err),flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
