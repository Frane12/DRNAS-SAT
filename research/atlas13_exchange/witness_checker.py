#!/usr/bin/env python3
"""Independent ATLAS13 original-source 2-SAT GRAPH inference checker.

This script imports NONE of the discovery, Hall, or proof-emitter modules.
It independently reparses the exact raw source CNF and requires a literal
two-edge implication path
      a -> t -> -b
so the transferred pair (-a OR -b) is RUP derivable under assumptions a,b.
Each graph lemma is distinct, crosses separate original ALO groups, and
travels via an auxiliary variable outside those groups.

An externally accepted VeriPB proof is still required for final UNSAT.
"""
import hashlib,json
from pathlib import Path
class Invalid(ValueError):pass
def need(p,msg):
    if not p:raise Invalid(msg)
def parse_original(raw):
    n=m=None;source=[];pending=[]
    for line in raw.decode("ascii").splitlines():
        words=line.split()
        if not words or words[0]=="c":continue
        if words[0]=="p":
            need(n is None and len(words)==4 and words[1]=="cnf","HEADER")
            n,m=map(int,words[2:])
            need(1<=n<=200000 and 1<=m<=500000,"SOURCE_BOUNDS")
            continue
        need(n is not None,"NO_HEADER")
        for word in words:
            lit=int(word)
            need(abs(lit)<=n,"LITERAL_RANGE")
            if lit:pending.append(lit)
            else:
                need(not any(-l in pending for l in pending),"TAUTOLOGICAL_SOURCE")
                need(len(set(pending))==len(pending),"DUPLICATE_SOURCE_LITERALS")
                source.append(tuple(pending));pending=[]
    need(n is not None and not pending and len(source)==m,"SOURCE_CLAUSES")
    return n,source

def check_witness(raw,claims):
    need(type(claims) is dict and
         claims.get("format")=="DRNAS-ATLAS13-GRAPH-IMPLICATION-v1","CERT_FORMAT")
    need(claims.get("source_sha256")==hashlib.sha256(raw).hexdigest(),
         "SOURCE_SHA_MISMATCH")
    n,original=parse_original(raw)
    need(claims.get("original_clause_count")==len(original),"CLAUSE_COUNT")
    clauses={frozenset(row) for row in original}
    groups={tuple(sorted(row)) for row in original
       if 3<=len(row)<=12 and all(l>0 for l in row)
       and len(set(row))==len(row)}
    owners={}
    for i,group in enumerate(sorted(groups)):
        for v in group:
            need(v not in owners,"ALO_GROUP_OVERLAP")
            owners[v]=i
    need(len(groups)>=3,"SOURCE_TOO_FEW_ALO_GROUPS")
    lemmas=claims.get("lemmas")
    need(type(lemmas) is list and 0<len(lemmas)<=24,"LEMMA_COUNT")
    seen=set();checked=[]
    for lemma in lemmas:
        need(type(lemma) is dict and
             set(lemma)=={"a","b","path","input_clause_1","input_clause_2"},
             "LEMMA_FIELDS")
        a,b=lemma["a"],lemma["b"]
        path=lemma["path"]
        need(type(a) is int and type(b) is int
             and a in owners and b in owners and a<b
             and owners[a]!=owners[b],"INVALID_CROSS_GROUP_PAIR")
        need(type(path) is list and len(path)==3 and
             all(type(x) is int and x!=0 and abs(x)<=n for x in path),
             "BAD_IMPLICATION_PATH")
        start,middle,end=path
        need(start in (a,b) and end in (-a,-b) and
             end != -start, "PATH_ENDPOINT_MISMATCH")
        # The endpoint can be a->-b or b->-a. Both yield (-a or -b).
        need({start,-end}=={a,b},"IMPLICATION_NOT_FOR_THE_CLAIMED_PAIR")
        need(abs(middle) not in owners,
             "MIDDLE_NODE_MUST_BE_NONSELECTOR_AUX")
        c1=frozenset((-start,middle))
        c2=frozenset((-middle,end))
        need(c1 in clauses and c2 in clauses,
             "MISSING_REAL_SOURCE_IMPLICATION_CLAUSE")
        need(lemma["input_clause_1"]==sorted(c1) and
             lemma["input_clause_2"]==sorted(c2),
             "INCORRECT_PROVENANCE_CLAUSES")
        need(frozenset((-a,-b)) not in clauses,
             "TRANSFER_ALREADY_SOURCE_MUTEX")
        need((a,b) not in seen,"DUPLICATED_TRANSFER")
        seen.add((a,b))
        checked.append({"pair":[a,b],"path":path})
    return {"status":"GRAPH_IMPLICATION_LEMMAS_SOURCE_VERIFIED",
            "source_original_sha256":hashlib.sha256(raw).hexdigest(),
            "original_clauses_checked":len(original),
            "source_ALO_groups":len(groups),
            "original_literal_two_edge_paths_verified":len(checked),
            "transfer_lemmas":checked,
            "SAT_UNSAT_result":"NONE_REQUIRES_ORIGINAL_STANDARD_PROOF"}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path);p.add_argument("certificate",type=Path)
    a=p.parse_args()
    try:
        d=check_witness(a.source.read_bytes(),json.loads(a.certificate.read_text()))
        print("ATLAS13_INDEPENDENT_LEMMA_PASS "+json.dumps(d,sort_keys=True))
    except (Invalid,ValueError,TypeError,KeyError,OSError) as e:
        print("ATLAS13_LEMMA_REJECT "+str(e))
        raise SystemExit(1)
if __name__=="__main__":main()
