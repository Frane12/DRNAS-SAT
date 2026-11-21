#!/usr/bin/env python3
"""Independent proof of reversible masked-CNF AND substitution.

Does NOT import the detector or reuse its quotient implementation. Every
claimed pair is independently expanded from the final quotient, backward,
and the recovered original clauses must be EXACTLY the same multiset.
The original source raw SHA and final quotient raw SHA are also checked.
A SAT witness is separately checked against EVERY original clause.
"""
import argparse, collections,hashlib,json
from pathlib import Path

class Invalid(ValueError):pass
def must(test,why):
    if not test:raise Invalid(why)
def parse(raw):
    n=m=None;clauses=[];partial=[]
    for line in raw.decode("ascii").splitlines():
        fields=line.split()
        if not fields or fields[0]=="c":continue
        if fields[0]=="p":
            must(n is None and len(fields)==4 and fields[1]=="cnf","bad_dimacs_header")
            n,m=map(int,fields[2:])
            must(1<=n<=50000 and 0<=m<=200000,"dimacs_budget")
            continue
        must(n is not None,"missing_header")
        for token in fields:
            v=int(token)
            must(abs(v)<=n,"literal_range")
            if v:partial.append(v)
            else:
                must(len(set(partial))==len(partial),"duplicate_literals")
                clauses.append(tuple(partial));partial=[]
    must(n is not None and not partial and len(clauses)==m,"clause_count")
    return n,clauses

def bag(clauses):
    return collections.Counter(tuple(sorted(c)) for c in clauses)

def independent_expand(quotient,a,b):
    expanded=[]
    for clause in quotient:
        c=set(clause)
        must(not (a in c and -a in c),"tautological_source")
        must(b not in c and -b not in c,"old_secondary_variable_still_used")
        if a in c:
            row=[v for v in clause if v!=a]
            expanded.extend([tuple(row+[a]),tuple(row+[b])])
        elif -a in c:
            row=[v for v in clause if v!=-a]
            expanded.append(tuple(row+[-a,-b]))
        else:
            expanded.append(clause)
    return expanded

def check(source_raw,quotient_raw,witness):
    must(isinstance(witness,dict),"bad_certificate")
    must(witness.get("format")=="DRNAS-ATLAS6-AND-QUOTIENT-v1","wrong_format")
    must(witness.get("source_sha256")==hashlib.sha256(source_raw).hexdigest(),
         "original_source_sha256_mismatch")
    must(witness.get("quotient_sha256")==hashlib.sha256(quotient_raw).hexdigest(),
         "quotient_sha256_mismatch")
    nv,original=parse(source_raw)
    nq,current=parse(quotient_raw)
    must(nv==nq==witness.get("source_vars"),"variable_bound")
    pairs=witness.get("pair_steps")
    must(isinstance(pairs,list) and len(pairs)<=500 and
         len(pairs)==witness.get("collapsed_pairs"),"pair_steps")
    must(len(original)==witness.get("original_clauses") and
         len(current)==witness.get("quotient_clauses"),"clause_header")
    for step in reversed(pairs):
        must(isinstance(step,dict),"bad_step")
        a,b=step.get("a"),step.get("b")
        must(type(a) is int and type(b) is int and
             0<abs(a)<=nv and 0<abs(b)<=nv and abs(a)!=abs(b),"invalid_pair")
        must(len(current)==step.get("clauses_after"),"wrong_after_count")
        current=independent_expand(current,a,b)
        must(len(current)==step.get("clauses_before"),"wrong_before_count")
    must(bag(current)==bag(original),"EXPANSION_NOT_IDENTICAL_TO_SOURCE_CNF")
    return {"status":"SOURCE_MASKING_EQUIVALENCE_VERIFIED",
            "original_source_sha256":hashlib.sha256(source_raw).hexdigest(),
            "quotient_sha256":hashlib.sha256(quotient_raw).hexdigest(),
            "original_variables":nv,
            "original_clauses":len(original),
            "quotient_clauses":len(parse(quotient_raw)[1]),
            "checked_exact_AND_reexpansion_steps":len(pairs),
            "SAT_or_UNSAT_claim":"NONE"}

def check_sat(raw,model):
    nv,clauses=parse(raw)
    must(isinstance(model,dict),"model_type")
    assignment=model.get("assignment")
    must(isinstance(assignment,list) and len(assignment)==nv+1,"model_length")
    must(assignment[0] is None and all(type(b) is bool for b in assignment[1:]),
         "model_bits")
    bad=[]
    for j,clause in enumerate(clauses):
        if not any(assignment[abs(l)] == (l>0) for l in clause):
            bad.append(j+1)
            if len(bad)>=4:break
    must(not bad,"FAILED_ORIGINAL_MODEL_CLAUSES_"+str(bad))
    return {"status":"ORIGINAL_CNFSAT_MODEL_VERIFIED",
            "source_sha256":hashlib.sha256(raw).hexdigest(),
            "variables_checked":nv,
            "clauses_checked":len(clauses)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--quotient",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--model",type=Path)
    a=p.parse_args()
    try:
        raw=a.source.read_bytes()
        result=check(raw,a.quotient.read_bytes(),json.loads(a.certificate.read_text()))
        if a.model:
            result["model"]=check_sat(raw,json.loads(a.model.read_text()))
        print("ATLAS6_INDEPENDENT "+json.dumps(result,sort_keys=True),flush=True)
    except (Invalid,ValueError,KeyError,TypeError,OSError,UnicodeError,MemoryError) as exc:
        print("ATLAS6_REJECT "+str(exc),flush=True)
        raise SystemExit(1)
if __name__=="__main__":main()
