#!/usr/bin/env python3
"""ATLAS22: no-CDCL structural SAT witnesses for source-defined gate CNF controls.

Uses ONLY independently rechecked manifest/gate truth tables and original cut
inputs; NOT a fixed saved answer. Independent checker rereads original DIMACS
every clause, so no unverified model can be accepted.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
def evaluate(op,v):
    if op=="NOT":return 1-v[0]
    if op=="BUF":return v[0]
    if op=="AND":return v[0]&v[1]
    if op=="OR":return v[0]|v[1]
    if op=="XOR":return v[0]^v[1]
    if op=="XNOR":return 1^(v[0]^v[1])
    if op=="NAND":return 1^(v[0]&v[1])
    if op=="NOR":return 1^(v[0]|v[1])
    if op=="MUX":return v[1] if v[2] else v[0]
    raise ValueError("UNKNOWN_GATE_OP")
def check_clause(lines,values):
    count=0
    for line in Path(lines).read_text().splitlines():
        t=line.strip()
        if not t or t[0] in ("c","p"):continue
        literals=[int(x) for x in t.split()]
        assert literals[-1]==0
        if not any((values[abs(x)]==1 if x>0 else values[abs(x)]==0) for x in literals[:-1]):
            raise AssertionError("SAT_MODEL_VIOLATES_ORIGINAL_DIMACS_CLAUSE_"+str(count))
        count+=1
    return count
def model(cnf,manifest,pattern="alternate"):
    d=json.loads(Path(manifest).read_text())
    if d["case"] not in ("correct_equal","wrong_lsb_mismatch"):
        raise ValueError("SAT_CONTROL_ONLY_NOT_UNSAT_MITER")
    varcount=d["variable_count"]
    values=[None]*(varcount+1)
    for i in range(1,65):
        if pattern=="zero":bit=0
        elif pattern=="one":bit=1
        else:bit=(i*7+1)%2
        values[i]=bit
    for gate in d["all_source_gates"]:
        out=gate["output"]
        assert values[out] is None and all(values[i] is not None for i in gate["inputs"])
        values[out]=evaluate(gate["op"],[values[v] for v in gate["inputs"]])
    assert all(x in (0,1) for x in values[1:])
    clause_count=check_clause(cnf,values)
    return values,clause_count

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--pattern",choices=["zero","one","alternate"],default="alternate")
    a=p.parse_args()
    values,clauses=model(a.cnf,a.manifest,a.pattern)
    m=Path(a.output)
    m.write_text("c ATLAS22 forward structural SAT witness verified against original DIMACS\n"+
                 "s SATISFIABLE\n"+
                 "".join("v "+" ".join(str(i if values[i] else -i) for i in range(k,min(k+15,len(values))))+" 0\n"
                         for k in range(1,len(values),15)))
    print("ATLAS22_STRUCTURE_SAT_MODEL_VERIFIED",json.dumps({
        "model_path":str(m),"variables":len(values)-1,"clauses_verified":clauses,
        "pattern":a.pattern}),flush=True)
if __name__=="__main__":main()
