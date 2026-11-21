#!/usr/bin/env python3
"""Independent source-bound graph/Hall fact validator.

No imports from generator, graph module or proof emitter. Checks ORIGINAL DIMACS
byte SHA, demanded positive clauses and every source-backed same-color mutex.
This checker is project-specific: only external VeriPB validates a standard
UNSAT proof.
"""
import argparse,hashlib,json
from pathlib import Path

class Rejected(ValueError):pass

def require(ok,msg):
    if not ok:raise Rejected(msg)

def parse(raw):
    var=count=None;rows=[];row=[]
    for line in raw.decode("ascii").splitlines():
        words=line.split()
        if not words or words[0]=="c":continue
        if words[0]=="p":
            require(var is None and len(words)==4 and words[1]=="cnf","bad_dimacs_header")
            var,count=int(words[2]),int(words[3]);continue
        require(var is not None,"missing_dimacs_header")
        for token in words:
            x=int(token)
            require(abs(x)<=var,"literal_out_of_bounds")
            if x:row.append(x)
            else:rows.append(frozenset(row));row=[]
    require(var is not None and not row and len(rows)==count,"dimacs_count")
    return var,rows,set(rows)

def verify(raw,facts):
    require(type(facts) is dict and facts.get("format")==
            "DRNAS-GRAPH-COLOR-CAPACITY-EXCHANGE-v1","format")
    require(facts.get("source_sha256")==hashlib.sha256(raw).hexdigest(),"SHA_256_INPUT_MISMATCH")
    require(facts.get("status")=="SOURCE_FACTS_ONLY_NO_SAT_VERDICT","not_graph_facts")
    nv,clauses,source=parse(raw)
    k=facts.get("color_count")
    require(type(k) is int and 3<=k<=32,"bad_color_count")
    aligned=facts.get("aligned_vertices")
    require(type(aligned) is list and len(aligned)==k,"wrong_clique_size")
    require(facts.get("capacity_per_color")==[1]*k,"capacity_claim_changed")
    require(facts.get("source_variables")==nv and facts.get("source_clauses")==len(clauses),
            "dimension_mismatch")
    used=set()
    for group in aligned:
        require(type(group) is list and len(group)==k and all(type(x) is int and 1<=x<=nv for x in group),
                "invalid_vertex_group")
        require(len(set(group))==k and not used.intersection(group),"overlapping_vertex_selectors")
        used.update(group)
        require(frozenset(group) in source,"vertex_ALO_missing_in_source")
    edge_checks=0
    for i in range(k):
        for j in range(i+1,k):
            for color in range(k):
                require(frozenset((-aligned[i][color],-aligned[j][color])) in source,
                        "graph_edge_color_clause_missing")
                edge_checks+=1
    # The PCMAX quota requirement is not supplied by GRAPH. It must be
    # independently FOUND in the original CNF after graph-aligned color recovery.
    chosen=None
    for c in range(k):
        vec=[aligned[i][c] for i in range(k)]
        if all(frozenset(vec[:i]+vec[i+1:]) in source for i in range(k)):
            chosen=(c,vec);break
    require(chosen is not None,"no_2_of_k_source_quota")
    color,vec=chosen
    return {"status":"SOURCE_GRAPH_AND_QUOTA_VERIFIED",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "color_count":k,"edge_checks":edge_checks,"quota_clause_checks":k,
            "quota_vector":vec,"quota_color_index":color,
            "demand_min":2,"capacity_max":1}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("cnf",type=Path);p.add_argument("facts",type=Path)
    a=p.parse_args()
    try: print(json.dumps(verify(a.cnf.read_bytes(),json.loads(a.facts.read_text())),sort_keys=True))
    except (Rejected,ValueError,KeyError,TypeError,UnicodeError,OSError) as e:
        print("SOURCE_CHECK_REJECT "+str(e));raise SystemExit(1)
