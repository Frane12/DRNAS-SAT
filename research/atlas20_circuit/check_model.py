#!/usr/bin/env python3
"""Independent original-DIMACS SAT model checker for ATLAS20.

Does not import the gate extractor, generated C++, or any external solver.
Requires a complete assignment for all variables; checks every original clause.
Returns status SAT_MODEL_VERIFIED only after all original clauses are satisfied.
"""
import argparse
import hashlib
import json
from pathlib import Path

def verify(cnf,model):
    raw=Path(cnf).read_bytes()
    data=Path(model).read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    n=nc=None
    counts=0
    assignment={}
    declared_status=False
    for line in data.decode("ascii").splitlines():
        cols=line.split()
        if not cols or cols[0]=="c":continue
        if cols[:2]==["s","SATISFIABLE"]:
            if declared_status:raise ValueError("MULTIPLE_STATUS_LINES")
            declared_status=True
            continue
        if cols[0]!="v":raise ValueError("UNEXPECTED_MODEL_LINE")
        for w in cols[1:]:
            lit=int(w)
            if not lit:continue
            key=abs(lit)
            if key in assignment:raise ValueError("DUPLICATE_MODEL_VARIABLE")
            assignment[key]=lit>0
    if not declared_status:raise ValueError("MISSING_SAT_STATUS")
    partial=[]
    for line in raw.decode("ascii").splitlines():
        cols=line.split()
        if not cols or cols[0]=="c":continue
        if cols[0]=="p":
            if n is not None or len(cols)!=4 or cols[1]!="cnf":
                raise ValueError("MALFORMED_SOURCE_HEADER")
            n,nc=int(cols[2]),int(cols[3])
            if n<1 or nc<0:raise ValueError("SOURCE_DIMENSIONS")
            if len(assignment)!=n or set(assignment)!=set(range(1,n+1)):
                raise ValueError("ASSIGNMENT_INCOMPLETE_OR_OUTSIDE_HEADER")
            continue
        if n is None:raise ValueError("SOURCE_HEADER_MISSING")
        for tok in cols:
            lit=int(tok)
            if abs(lit)>n:raise ValueError("SOURCE_LITERAL_OUT_OF_RANGE")
            if lit:partial.append(lit)
            else:
                counts+=1
                if not any(assignment[abs(v)]==(v>0) for v in partial):
                    raise ValueError(f"UNSATISFIED_SOURCE_CLAUSE_{counts}")
                partial=[]
    if n is None or counts!=nc or partial:
        raise ValueError("SOURCE_CLAUSE_COUNT_MISMATCH")
    return {"status":"SAT_MODEL_VERIFIED",
            "source_sha256":digest,
            "model_sha256":hashlib.sha256(data).hexdigest(),
            "complete_assignment_variables":n,
            "original_clauses_verified":counts,
            "independent_of_circuit_extractor":True}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    try:
        result=verify(a.cnf,a.model)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        print("ATLAS20_INDEPENDENT_SAT "+json.dumps(result,sort_keys=True),flush=True)
    except (OSError,ValueError,UnicodeError,OverflowError,TypeError) as e:
        a.output.unlink(missing_ok=True)
        print("ATLAS20_INVALID_MODEL "+str(e),flush=True)
        raise SystemExit(1)
