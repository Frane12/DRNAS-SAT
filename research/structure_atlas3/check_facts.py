#!/usr/bin/env python3
"""Independent SOURCE-premise checker for ATLAS3 fact sets.

Original DIMACS clause set is the only authority. It never trusts labels,
counts, expected results, source-family provenance or a producer's verdict.
It cannot prove final SAT/UNSAT and MUST NOT be interpreted as VeriPB.
"""
import hashlib,itertools,json
from pathlib import Path
from atlas import parse
class Invalid(ValueError):pass
def require(x,why):
    if not x:raise Invalid(why)

def check(raw,claims):
    require(type(claims) is dict and claims.get("format")==
            "DRNAS-ATLAS3-SOURCE-FACTS-v1","fact_format")
    require(claims.get("source_sha256")==hashlib.sha256(raw).hexdigest(),"SOURCE_HASH")
    nv,clauses=parse(raw)
    require(claims.get("source_variables")==nv and
            claims.get("source_clauses")==len(clauses),"source_header")
    original={frozenset(c) for c in clauses}
    groups=claims.get("exact_one_groups")
    xors=claims.get("complete_xor_rows")
    require(type(groups) is list and type(xors) is list,"facts_type")
    require(len(groups)<=len(clauses) and len(xors)<=len(clauses)*2,"fact_budget")
    groups_seen=set();xor_seen=set()
    pair_checks=0;xor_clause_checks=0
    for group in groups:
        require(type(group) is list and 2<=len(group)<=32 and
                all(type(v) is int and 0<abs(v)<=nv for v in group) and
                len(set(map(abs,group)))==len(group),"malformed_group")
        g=tuple(group)
        require(g not in groups_seen,"duplicate_group")
        groups_seen.add(g)
        require(frozenset(g) in original,"ALO_NOT_IN_ORIGINAL")
        for a,b in itertools.combinations(g,2):
            pair_checks+=1
            require(frozenset((-a,-b)) in original,"PAIR_MUTEX_NOT_IN_ORIGINAL")
    for row in xors:
        require(type(row) is dict and set(row)=={"vars","rhs"},"bad_xor_row")
        vs=row["vars"];rhs=row["rhs"]
        require(type(vs) is list and 2<=len(vs)<=4 and
                all(type(v) is int and 1<=v<=nv for v in vs) and
                len(set(vs))==len(vs) and
                type(rhs) is int and rhs in (0,1),"bad_xor_fields")
        key=(tuple(vs),rhs)
        require(key not in xor_seen,"duplicate_xor");xor_seen.add(key)
        # Every forbidden assignment clause must be literally in the
        # source, even after arbitrary sign flips, ordering and renaming.
        for bits in itertools.product((0,1),repeat=len(vs)):
            if sum(bits)%2==rhs:continue
            c=[-v if bits[i] else v for i,v in enumerate(vs)]
            xor_clause_checks+=1
            require(frozenset(c) in original,"XOR_TABLE_INCOMPLETE")
    return {"status":"SOURCE_FACTS_INDEPENDENTLY_VERIFIED",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "eo_groups_checked":len(groups),"xor_rows_checked":len(xors),
            "mutex_pairs_verified":pair_checks,"xor_clauses_verified":xor_clause_checks,
            "sat_unsat_result":"NONE"}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("cnf",type=Path);p.add_argument("facts",type=Path)
    a=p.parse_args()
    try:
        print(json.dumps(check(a.cnf.read_bytes(),json.loads(a.facts.read_text())),sort_keys=True))
    except (Invalid,ValueError,UnicodeError,TypeError,KeyError,OSError) as e:
        print("SOURCE_FACT_REJECT "+str(e));raise SystemExit(1)
