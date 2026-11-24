#!/usr/bin/env python3
"""ATLAS23 bounded proof-bus prototype: GF2, PCMAX and 2-bit arithmetic."""
import argparse, hashlib, itertools, json
from pathlib import Path

NAMES=("x","y0","y1","z0","z1")
SCOPE={"GF2":("x","y0"),"PCMAX":("x","z0"),"ARITH2":("y0","y1","z0","z1")}
ORDER=("GF2","ARITH2","PCMAX")

def valid(m,a,cap,add):
    if m=="GF2": return (a["x"]^a["y0"])==0
    if m=="PCMAX": return a["x"]+a["z0"]<=cap
    if m=="ARITH2":
        return (a["z0"]+2*a["z1"])==(a["y0"]+2*a["y1"]+add)%4
    raise ValueError("unknown module")

def rows(m,cap,add):
    return [dict(zip(SCOPE[m],b)) for b in itertools.product((0,1),repeat=len(SCOPE[m]))
            if valid(m,dict(zip(SCOPE[m],b)),cap,add)]

def encode(cap,add):
    clauses=[]
    for m in ORDER:
        for b in itertools.product((0,1),repeat=len(SCOPE[m])):
            a=dict(zip(SCOPE[m],b))
            if not valid(m,a,cap,add):
                clauses.append(tuple(-(NAMES.index(n)+1) if a[n] else NAMES.index(n)+1
                                     for n in SCOPE[m]))
    cnf="c ATLAS23 exact three-module synthetic encoding\np cnf 5 %d\n"%len(clauses)
    cnf+="".join(" ".join(map(str,c))+" 0\n" for c in clauses)
    return cnf,clauses

def propagate(m,facts,cap,add):
    available=[r for r in rows(m,cap,add)
               if all(r[n]==v for n,v in facts.items() if n in r)]
    if not available: return None
    return {n:available[0][n] for n in SCOPE[m] if n not in facts
            and all(r[n]==available[0][n] for r in available)}

def join(cap,add,budget):
    pool=[{}]; explored=0
    for m in ORDER:
        out=[]
        for partial in pool:
            for row in rows(m,cap,add):
                explored+=1
                if explored>budget: return None,explored
                if all(partial[k]==v for k,v in row.items() if k in partial):
                    out.append({**partial,**row})
        pool=out
        if not pool: return False,explored
    return pool[0],explored

def run(cap=0,add=1,budget=10000):
    if cap not in (0,1,2) or add not in (0,1,2,3) or budget<0:
        raise ValueError("out-of-range parameter")
    cnf,clauses=encode(cap,add);facts={};events=[];status="UNKNOWN";model=None;rounds=0
    while True:
        rounds+=1
        assert rounds<=6
        changed=False
        for m in ORDER:
            derived=propagate(m,facts,cap,add)
            premises={n:facts[n] for n in SCOPE[m] if n in facts}
            if derived is None:
                events.append({"kind":"contradiction","module":m,"premises":premises})
                status="UNSAT_STRUCTURAL_TRACE";break
            for n,v in derived.items():
                premises={k:facts[k] for k in SCOPE[m] if k in facts}
                events.append({"kind":"infer","module":m,"premises":premises,"variable":n,"value":v})
                facts[n]=v;changed=True
        if status!="UNKNOWN" or not changed:break
    explored=0
    if status=="UNKNOWN":
        model,explored=join(cap,add,budget)
        if isinstance(model,dict):
            assert set(model)==set(NAMES)
            assert all(any(model[NAMES[abs(l)-1]]==int(l>0) for l in c) for c in clauses)
            status="SAT_MODEL_CHECKED"
    if not isinstance(model,dict):model=None
    cert={"version":"ATLAS23-v1","type":"synthetic-structured","capacity":cap,
          "increment":add,"variables":list(NAMES),"scopes":SCOPE,
          "module_order":list(ORDER),"cnf_sha256":hashlib.sha256(cnf.encode()).hexdigest(),
          "clause_count":len(clauses),"events":events,"facts":facts,"status":status,
          "sat_model":model,"rounds":rounds,"join_expansions":explored,
          "no_cdcl_fallback":True,"standard_drat_lrat_veripb_proof":False}
    return cnf,cert

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--capacity",type=int,default=0)
    p.add_argument("--increment",type=int,default=1)
    p.add_argument("--join-budget",type=int,default=10000)
    p.add_argument("--out",type=Path,default=Path("atlas23_artifacts"))
    a=p.parse_args();cnf,result=run(a.capacity,a.increment,a.join_budget)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"source.cnf").write_text(cnf)
    (a.out/"trace.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"events":len(result["events"]),
                      "clauses":result["clause_count"],"out":str(a.out)},sort_keys=True))
