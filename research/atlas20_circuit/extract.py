#!/usr/bin/env python3
"""ATLAS20: independently source-backed 2-input Boolean circuit extraction.

A gate is accepted ONLY if its complete XOR/XNOR four-clause table or
AND/OR triple-plus-two-binary truth table appears in the original DIMACS.
ALL original clauses must be accounted for exactly, including unit outputs.
The present bounded encoding requires every gate output number > both inputs;
this is a recognized source-encoding restriction, NOT general CNF solving.
No SAT/UNSAT verdict is emitted here.
"""
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

class Unsupported(ValueError): pass

def need(flag,msg):
    if not flag:raise Unsupported(msg)

def parse(raw):
    need(len(raw)<=20_000_000,"INPUT_BYTES_GATE")
    nv=nc=None;clauses=[];partial=[]
    for line in raw.decode("ascii").splitlines():
        parts=line.split()
        if not parts or parts[0]=="c":continue
        if parts[0]=="p":
            need(nv is None and len(parts)==4 and parts[1]=="cnf","DIMACS_HEADER")
            nv,nc=map(int,parts[2:])
            need(0<nv<=60000 and 0<=nc<=400000,"DIMACS_BUDGET")
            continue
        need(nv is not None,"MISSING_DIMACS_HEADER")
        for chunk in parts:
            lit=int(chunk)
            need(abs(lit)<=nv,"LITERAL_OUTSIDE_HEADER")
            if lit:
                partial.append(lit)
            else:
                need(len(partial)==len(set(partial)) and not any(-v in partial for v in partial),
                     "DUPLICATE_OR_TAUTOLOGICAL_CLAUSE")
                need(1<=len(partial)<=3,"UNSUPPORTED_CLAUSE_WIDTH")
                clauses.append(tuple(partial));partial=[]
    need(nv is not None and not partial and len(clauses)==nc,"DIMACS_CLAUSE_COUNT")
    return nv,clauses

def xorset(a,b,z,inv=0):
    return [
        frozenset((-a if av else a,-b if bv else b,-z if zv else z))
        for av,bv,zv in itertools.product((0,1),repeat=3)
        if zv != ((av^bv)^inv)
    ]

def gate_clauses(op,a,b,z):
    if op=="XOR":return xorset(a,b,z,0)
    if op=="XNOR":return xorset(a,b,z,1)
    if op=="AND":return [frozenset(row) for row in
            [(-a,-b,z),(a,-z),(b,-z)]]
    if op=="OR":return [frozenset(row) for row in
            [(a,b,-z),(-a,z),(-b,z)]]
    raise Unsupported("INVALID_GATE_OP")

def recover(raw):
    n,cs=parse(raw)
    source=Counter(frozenset(c) for c in cs)
    need(all(count==1 for count in source.values()),"REPEATED_SOURCE_CLAUSES")
    supports=defaultdict(list)
    units=[]
    for c in cs:
        if len(c)==3:
            support=tuple(sorted(abs(x) for x in c))
            need(len(set(support))==3,"REPEATED_GATE_VARIABLE")
            supports[support].append(frozenset(c))
        elif len(c)==1:
            units.append(c[0])
    gates={}
    expected=Counter()
    for support,table in supports.items():
        a,b,z=support
        need(z not in gates and z>a and z>b,"GATE_OUTPUT_ORDER_OR_DUPLICATE")
        options=("XOR","XNOR") if len(table)==4 else ("AND","OR") if len(table)==1 else ()
        matches=[op for op in options if
                 (set(table)==set(gate_clauses(op,a,b,z)[:len(table)])
                  if op in ("XOR","XNOR") else
                  frozenset(table[0])==gate_clauses(op,a,b,z)[0])]
        # No inference by family name; a gate type must satisfy its literal truth table.
        need(len(matches)==1,"MISSING_OR_AMBIGUOUS_GATE_TRUTH_TABLE")
        op=matches[0]
        for cl in gate_clauses(op,a,b,z):expected[cl]+=1
        gates[z]={"op":op,"a":a,"b":b}
    for u in units:expected[frozenset((u,))]+=1
    need(source==expected,"ORIGINAL_SOURCE_GRAMMAR_NOT_EXACT")
    outputs=set(gates)
    input_ids=sorted(set(range(1,n+1))-outputs)
    need(1<=len(input_ids)<=32,"INPUT_GATE_COUNT_OUTSIDE_BUDGET")
    need(len(gates)+len(input_ids)==n,"INCOMPLETE_DEFINITION")
    for z,info in gates.items():
        need(info["a"]<z and info["b"]<z,"NON_TOPOLOGICAL_GATE")
    need(len(units)>0,"NO_FIXED_OUTPUTS")
    need(len(units)<=128,"TOO_MANY_FIXED_OUTPUTS")
    kinds=Counter(g["op"] for g in gates.values())
    return {"status":"SOURCE_EXACT_CIRCUIT_RECONSTRUCTED_NOT_SAT_PROOF",
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "variables":n,"clauses":len(cs),
        "inputs":input_ids,"input_count":len(input_ids),
        "gate_count":len(gates),
        "gates":[{"z":z,**gates[z]} for z in sorted(gates)],
        "gate_kinds":dict(sorted(kinds.items())),
        "unit_literals":units,
        "all_original_clauses_accounted_for":True,
        "no_CDCL_or_SAT_oracle_used":True}

def evaluate(circuit,key):
    n=circuit["variables"]
    inputs=circuit["inputs"]
    if key<0 or key>=(1<<len(inputs)):
        raise ValueError("INPUT_KEY_OUT_OF_RANGE")
    value=[False]*(n+1)
    for i,v in enumerate(inputs):
        value[v]=bool(key>>i&1)
    for gate in circuit["gates"]:
        a=value[gate["a"]];b=value[gate["b"]];op=gate["op"]
        value[gate["z"]]=(
            a^b if op=="XOR" else not(a^b) if op=="XNOR" else
            a and b if op=="AND" else a or b)
    return value

def write_model(circuit,key,path):
    values=evaluate(circuit,key)
    n=circuit["variables"]
    lines=["c ATLAS20 source-backed complete Boolean model",
           "c original_sha256 "+circuit["source_sha256"],
           "s SATISFIABLE"]
    for start in range(1,n+1,16):
        line=[str(v if values[v] else -v) for v in range(start,min(start+16,n+1))]
        lines.append("v "+" ".join(line)+" 0")
    Path(path).write_text("\n".join(lines)+"\n")
    return values

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    try:
        r=recover(a.cnf.read_bytes())
        a.output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
        print("ATLAS20_SOURCE_CIRCUIT "+json.dumps({k:v for k,v in r.items() if k!="gates"},sort_keys=True),flush=True)
    except (OSError,UnicodeError,ValueError,AssertionError,TypeError,OverflowError) as e:
        a.output.unlink(missing_ok=True)
        print("ATLAS20_SOURCE_UNKNOWN "+str(e),flush=True)
        raise SystemExit(2)
