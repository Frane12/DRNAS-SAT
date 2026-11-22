#!/usr/bin/env python3
"""Independent original-CNF checker for ATLAS13 three-module inference.

DOES NOT import the detector, its derivation, or the proof compiler. Re-reads
original DIMACS, validates SHA, source positive exactly-one groups (ALO +
all their AMO pairs), resource partition, original direct mutex clauses and
ALL missing mutex clauses one by one via complete source XOR2 a=z
plus original (-z OR -b). It independently performs bounded RUP/UP under
a=b=TRUE. No source label, known model or generator mapping is accepted.
This checker is a premise verifier, not an external standard UNSAT proof.
"""
import hashlib,itertools,json
from pathlib import Path
class Invalid(ValueError):pass
def need(ok,reason):
    if not ok:raise Invalid(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def parse(raw):
    declared=None;rows=[];pending=[]
    for line in raw.decode("ascii").splitlines():
        words=line.split()
        if not words or words[0]=="c":continue
        if words[0]=="p":
            need(declared is None and len(words)==4 and words[1]=="cnf","HEADER")
            nv,nc=map(int,words[2:])
            need(1<=nv<=300 and 0<nc<=3000,"LIMIT")
            declared=(nv,nc);continue
        need(declared is not None,"HEADER_MISSING")
        for word in words:
            lit=int(word)
            need(abs(lit)<=declared[0],"LITERAL_RANGE")
            if lit:pending.append(lit)
            else:
                need(len(set(map(abs,pending)))==len(pending),"DUPLICATE_ABS_LIT")
                rows.append(tuple(pending));pending=[]
    need(declared is not None and len(rows)==declared[1] and not pending,"CNF_COUNT")
    return declared[0],rows

def unit_conflict(rows,assumptions):
    """Independent fixed point of unit propagation from raw source."""
    setting={}
    for lit in assumptions:
        v=abs(lit);want=lit>0
        if v in setting and setting[v]!=want:return True
        setting[v]=want
    while True:
        change=False
        for clause in rows:
            unresolved=[]
            satisfied=False
            for lit in clause:
                value=setting.get(abs(lit))
                if value is None:unresolved.append(lit)
                elif value==(lit>0):
                    satisfied=True;break
            if satisfied:continue
            if not unresolved:return True
            if len(unresolved)==1:
                v=abs(unresolved[0]);val=unresolved[0]>0
                if v in setting and setting[v]!=val:return True
                if v not in setting:
                    setting[v]=val;change=True
        if not change:return False

def check(raw,cert):
    need(type(cert) is dict and cert.get("format")==
         "DRNAS-ATLAS13-XOR2-GRAPH-HALL-CERT-v1","FORMAT")
    need(cert.get("source_sha256")==sha(raw),"SOURCE_SHA")
    nv,rows=parse(raw)
    need(cert.get("source_variables")==nv and
         cert.get("source_clauses")==len(rows),"SOURCE_HEADER")
    idx={frozenset(r) for r in rows}
    groups=cert.get("alo_groups");resources=cert.get("resource_cliques")
    witnesses=cert.get("xor2_derived_mutex")
    need(type(groups) is list and type(resources) is list and
         type(witnesses) is list,"CLAIMS_TYPE")
    need(3<=len(groups)<=16 and 1<=len(resources)<len(groups),"HALL_BUDGET")
    need(cert.get("demand")==len(groups) and
         cert.get("capacity")==len(resources),"HALL_CLAIM_COUNT")
    owner={};source_amo_pairs=0
    for gi,g in enumerate(groups):
        need(type(g) is list and 2<=len(g)<=8 and
             len(g)==len(set(g)) and all(type(v) is int and 1<=v<=nv for v in g),
             "SOURCE_ALO_GROUP_FIELD")
        need(frozenset(g) in idx,"SOURCE_ALO_CLAUSE_MISSING")
        for v in g:
            need(v not in owner,"ALO_GROUPS_OVERLAP")
            owner[v]=gi
        for a,b in itertools.combinations(g,2):
            need(frozenset((-a,-b)) in idx,"SOURCE_EXACTLY_ONE_AMO_MISSING")
            source_amo_pairs+=1
    cover=set()
    missing=set()
    direct_mutex=0
    for r in resources:
        need(type(r) is list and 2<=len(r)<=100 and
             len(r)==len(set(r)) and
             all(type(v) is int and v in owner for v in r),"RESOURCE_CLIQUE_FIELDS")
        need(not cover.intersection(r),"RESOURCE_CLIQUES_OVERLAP")
        cover.update(r)
        for a,b in itertools.combinations(r,2):
            need(owner[a]!=owner[b],"RESOURCE_WITHIN_SAME_ALO_GROUP")
            if frozenset((-a,-b)) in idx:direct_mutex+=1
            else:missing.add(tuple(sorted((a,b))))
    need(cover==set(owner),"RESOURCE_CLIQUES_DO_NOT_COVER_DEMAND")
    need(1<=len(missing)<=3,"MISSING_PAIR_COUNT")
    seen={}
    all_bridge_clauses=set()
    for w in witnesses:
        need(type(w) is dict and w.get("relation")==
             "XOR2_EQUALITY_AND_DIRECT_BINARY_IMPLICATION","BRIDGE_FORMAT")
        a,b,z=w.get("a"),w.get("b"),w.get("z")
        need(all(type(v) is int and 1<=v<=nv for v in (a,b,z)) and
             len({a,b,z})==3,"BRIDGE_VARIABLES")
        key=tuple(sorted((a,b)))
        need(key in missing and key not in seen,"BRIDGE_NOT_MISSING_PAIR")
        need(z not in cover,"BRIDGE_AUX_NOT_OUTSIDE_ALO_GROUPS")
        need(w.get("xor_vars")==sorted((a,z)) and
             w.get("xor_rhs")==0,"NOT_COMPLETE_XOR2_EQUALITY")
        need(frozenset((-a,z)) in idx and frozenset((a,-z)) in idx,
             "XOR2_SOURCE_TRUTH_TABLE_INCOMPLETE")
        need(frozenset((-z,-b)) in idx,"MISSING_SOURCE_IMPLICATION")
        need(unit_conflict(rows,(a,b)),"DERIVED_MUTEX_NOT_SOURCE_RUP")
        # Does removal of the XOR equality clauses break this RUP?
        # This tests that the XOR relation is actually used for the gap.
        removed={frozenset((-a,z)),frozenset((a,-z))}
        without=[cl for cl in rows if frozenset(cl) not in removed]
        need(not unit_conflict(without,(a,b)),
             "XOR2_NOT_NEEDED_FOR_RUP_BRIDGE")
        all_bridge_clauses.update(removed)
        seen[key]=True
    need(set(seen)==missing,"SOME_MISSING_MUTEX_UNJUSTIFIED")
    return {
        "status":"ATLAS13_THREE_MODULE_SOURCE_PREMISES_VERIFIED",
        "source_sha256":sha(raw),"source_variables":nv,
        "source_clauses":len(rows),
        "source_EO_groups":len(groups),"source_AMO_pairs_checked":source_amo_pairs,
        "demand":len(groups),"capacity":len(resources),
        "source_direct_resource_mutex":direct_mutex,
        "xor_dependent_RUP_derived_resource_mutex":len(missing),
        "selected_variable_count":len(cover),
        "not_a_final_UNSAT_verdict":True
    }

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    a=p.parse_args()
    try:print("ATLAS13_INDEPENDENT "+json.dumps(check(a.source.read_bytes(),
              json.loads(a.certificate.read_text())),sort_keys=True))
    except (Invalid,ValueError,KeyError,TypeError,MemoryError,OSError,UnicodeError) as exc:
        print("ATLAS13_SOURCE_REJECT "+str(exc),flush=True)
        raise SystemExit(1)
if __name__=="__main__":main()
