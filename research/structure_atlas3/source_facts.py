#!/usr/bin/env python3
"""ATLAS3 source facts: signed EXACTLY-ONE and truth-table XOR2-4.
All findings are ORIGINAL CLAUSE premises, not final SAT/UNSAT answers.
This module never reads filenames, known source labels, or status.
"""
import collections,hashlib,itertools,json
from atlas import parse,encoded

def signed_exact_one(source):
    out=[]
    for group in source:
        clause=tuple(group)
        if not (2 <= len(clause) <= 32 and len({abs(x) for x in clause})==len(clause)):
            continue
        if all(frozenset((-a,-b)) in source
               for i,a in enumerate(clause) for b in clause[i+1:]):
            out.append(tuple(sorted(clause,key=lambda x:(abs(x),x<0))))
    # duplicates do not count as new facts; only original-source distinct groups
    return sorted(set(out))

def find_xor(source):
    grouped=collections.defaultdict(set)
    for clause in source:
        if not(2<=len(clause)<=4 and len({abs(x) for x in clause})==len(clause)):
            continue
        vars=tuple(sorted(abs(x) for x in clause))
        neg=frozenset(abs(x) for x in clause if x<0)
        mask=sum(1<<i for i,v in enumerate(vars) if v in neg)
        grouped[vars].add(mask)
    rows=[]
    for vs,patterns in grouped.items():
        n=len(vs)
        for bad_parity in (0,1):
            required={m for m in range(1<<n) if m.bit_count()%2==bad_parity}
            if required <= patterns:
                rows.append((vs,1-bad_parity))
    return sorted(set(rows))

def derive(raw):
    nv,clauses=parse(raw)
    source={frozenset(c) for c in clauses}
    eo=signed_exact_one(source)
    xor=find_xor(source)
    return {"format":"DRNAS-ATLAS3-SOURCE-FACTS-v1",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "source_variables":nv,"source_clauses":len(clauses),
            "exact_one_groups":[list(g) for g in eo],
            "complete_xor_rows":[{"vars":list(vs),"rhs":rhs} for vs,rhs in xor],
            "certification":"REQUIRES_RECHECK_OF_ORIGINAL_SOURCE_NO_SAT_VERDICT"}

def fact_summary(f):
    rows=f["complete_xor_rows"]
    return {"eo_count":len(f["exact_one_groups"]),
            "eo_widths":dict(sorted(collections.Counter(len(g) for g in f["exact_one_groups"]).items())),
            "xor_counts":dict(sorted(collections.Counter(len(r["vars"]) for r in rows).items())),
            "eo_literal_count":sum(map(len,f["exact_one_groups"])),
            "xor_row_count":len(rows)}

def reencode_amo(raw,group):
    """Replace ONE original source-supported pairwise AMO with sequential
    signed-selector AMO and keep the source ALO. New variables are fresh.
    Equisatisfiability under existential auxiliary projection is a theorem
    for this exact encoder, independently checked in audit.
    """
    nv,clauses=parse(raw)
    group=tuple(group)
    if not (2<=len(group)<=12):raise ValueError("rewrite_width_budget")
    orig={frozenset(c) for c in clauses}
    if frozenset(group) not in orig:raise ValueError("missing_ALO")
    blocked={frozenset((-a,-b)) for a,b in itertools.combinations(group,2)}
    if not blocked <= orig:raise ValueError("missing_AMO")
    # Remove *all* copies of the old mutex clauses; any other constraints
    # remain untouched. No original variable or unrelated clause changes.
    kept=[c for c in clauses if frozenset(c) not in blocked]
    s=[nv+1+i for i in range(len(group)-1)]
    sequential=[(-group[0],s[0])]
    for i in range(1,len(group)-1):
        sequential.extend(((-group[i],s[i]),(-s[i-1],s[i]),(-group[i],-s[i-1])))
    sequential.append((-group[-1],-s[-1]))
    return encoded(nv+len(s),kept+sequential),{
        "original_variables":nv,"new_variables":nv+len(s),
        "original_clauses":len(clauses),"replaced_pair_clauses":sum(
            frozenset(c) in blocked for c in clauses),
        "added_auxiliary_clauses":len(sequential),
        "selectors":list(group),"new_auxiliary_variables":s,
        "reencoding":"Sinz sequential AMO signed-literal",
        "equivalence_scope":"exactly same feasible assignments on original variables under exists-aux"}

def evaluate(clause,assignment):
    return any(assignment[abs(x)]==(x>0) for x in clause)

def local_sequential_equivalence(n):
    """Exhaustively test full projected semantics of source ALO + direct AMO
    versus source ALO + Sinz AMO for small n (up to 6); independent of encoding.
    """
    if not(2<=n<=6):raise ValueError("oracle budget")
    import itertools
    src=list(range(1,n+1))
    direct=[tuple(src)]+[(-a,-b) for a,b in itertools.combinations(src,2)]
    raw=encoded(n,direct)
    rewritten,meta=reencode_amo(raw,src)
    n2,seq=parse(rewritten)
    for bits in itertools.product((False,True),repeat=n):
        left={i+1:bits[i] for i in range(n)}
        direct_sat=all(evaluate(cl,left) for cl in direct)
        seq_sat=False
        for aux in itertools.product((False,True),repeat=n2-n):
            A=dict(left)
            A.update({n+i+1:aux[i] for i in range(n2-n)})
            if all(evaluate(cl,A) for cl in seq):
                seq_sat=True;break
        if seq_sat!=direct_sat:return False
    return True

def verify_local_sequential_large(n):
    """For every selection with at most one TRUE, the standard prefix
    assignment satisfies all sequential clauses. For every pair of TRUE
    selections, independent source-only unit propagation gives conflict.
    """
    if not(3<=n<=12):raise ValueError("projection budget")
    x=list(range(1,n+1))
    raw=encoded(n,[tuple(x)]+[(-a,-b) for a,b in itertools.combinations(x,2)])
    altered,meta=reencode_amo(raw,x)
    _,clauses=parse(altered)
    naux=n-1
    for selected in [-1]+list(range(n)):
        A={i+1:(i==selected) for i in range(n)}
        for j in range(naux):A[n+1+j]=(selected>=0 and selected<=j)
        if not all(evaluate(c,A) for c in clauses if c!=tuple(x)):
            return False
    # Every pair is refuted directly by the Sinz sequential clauses via UCP.
    from semantic_eo import unit_conflict
    for a,b in itertools.combinations(x,2):
        if not unit_conflict(clauses,(a,b)):return False
    return True

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("cnf");p.add_argument("--out",required=True)
    a=p.parse_args()
    f=derive(open(a.cnf,"rb").read())
    open(a.out,"w").write(json.dumps(f,sort_keys=True,indent=2)+"\n")
    print(json.dumps(fact_summary(f),sort_keys=True))
