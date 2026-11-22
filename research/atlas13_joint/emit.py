#!/usr/bin/env python3
"""ATLAS13 original-source standard VeriPB proof from independently checked
GRAPH + source XOR2 + HALL inference, with NO virtual-source substitution.

1. Validate all exact source premises independently in independent.py.
2. Add each XOR2-derived resource mutex as source-RUP in VeriPB.
3. Use the source and newly RUP-proved mutex constraints in the existing
   restricted clique-capacity cutting-planes argument.
4. Emit PBP *only*, never claim UNSAT until external VeriPB 3.0.2 accepts.
"""
import hashlib,itertools,json,sys,time
from pathlib import Path
from independent import check as independent_original_check,parse

class Unsupported(ValueError):pass
def need(ok,msg):
    if not ok:raise Unsupported(msg)
def clause_text(xs):
    return " ".join(("1 "+("~" if x<0 else "")+"x"+str(abs(x)))
                    for x in xs)+" >= 1"

def compile(raw,certificate):
    began=time.perf_counter()
    checked=independent_original_check(raw,certificate)
    need(checked["status"]=="ATLAS13_THREE_MODULE_SOURCE_PREMISES_VERIFIED",
         "SOURCE_PREMISE_REJECTED")
    n,source=parse(raw)
    lines=["pseudo-Boolean proof version 3.0",f"f {len(source)} ;"]
    index={}
    for i,row in enumerate(source,1):
        index.setdefault(frozenset(row),i)
    current=len(source)
    steps={"source_RUP_derived_mutex":0,"CP_clique_bounds":0,"CP_final":0}
    def rup(c):
        nonlocal current
        lines.append("rup "+clause_text(c)+" ;")
        current+=1
        index[frozenset(c)]=current
        steps["source_RUP_derived_mutex"]+=1
        return current
    def pol(ids,scale_last=1,divide=1):
        nonlocal current
        need(bool(ids) and scale_last>=1 and divide>=1,"BAD_PB_COMBINATION")
        parts=[str(ids[0])]
        for j,cid in enumerate(ids[1:],1):
            parts.append(str(cid))
            if j==len(ids)-1 and scale_last>1:parts.extend((str(scale_last),"*"))
            parts.append("+")
        if divide>1:parts.extend((str(divide),"d"))
        lines.append("pol "+" ".join(parts)+" ;")
        current+=1
        steps["CP_clique_bounds"]+=1
        return current
    # Exact missing clauses: formal checker must verify source-RUP directly.
    for witness in certificate["xor2_derived_mutex"]:
        a,b=witness["a"],witness["b"]
        need(frozenset((-a,-b)) not in index,
             "ATTEMPTING_DUPLICATE_DERIVED_SOURCE_MUTEX")
        rup((-a,-b))
    def get_mutex(a,b):
        key=frozenset((-a,-b))
        need(key in index,"MISSING_SOURCE_OR_RUP_MUTEX")
        return index[key]
    capacity_ids=[]
    for clique in certificate["resource_cliques"]:
        xs=sorted(clique)
        need(len(xs)>=2,"UNSUPPORTED_SINGLETON_RESOURCE")
        previous=get_mutex(xs[0],xs[1])
        for j in range(2,len(xs)):
            newest=xs[j]
            pairs=[get_mutex(v,newest) for v in xs[:j]]
            previous=pol([*pairs,previous],scale_last=j-1,divide=j)
        capacity_ids.append(previous)
    demands=[]
    for group in certificate["alo_groups"]:
        clause=frozenset(group)
        need(clause in index,"MISSING_ORIGINAL_ALO")
        demands.append(index[clause])
    # Adding each positive ALO and each resource upper bound cancels all
    # selected Boolean variables, leaving 0 >= d-c with d>c.
    pol([*demands,*capacity_ids])
    steps["CP_final"]=1
    lines.extend(("output NONE ;","conclusion UNSAT ;",
                  "end pseudo-Boolean proof ;"))
    proof="\n".join(lines)+"\n"
    need(len(proof.encode())<=1_000_000,"PROOF_BYTE_BUDGET")
    meta={
       "status":"EMITTED_EXTERNAL_VERIPB_REQUIRED",
       "format":"VeriPB 3.0",
       "original_sha256":hashlib.sha256(raw).hexdigest(),
       "proof_sha256":hashlib.sha256(proof.encode()).hexdigest(),
       "proof_bytes":len(proof.encode()),
       "original_clause_count":len(source),
       "independent_source_checker":checked["status"],
       "demand":certificate["demand"],"capacity":certificate["capacity"],
       "source_RUP_mutex":len(certificate["xor2_derived_mutex"]),
       "proof_steps":steps,
       "producer_including_independent_source_check_s":
                     round(time.perf_counter()-began,6),
       "NOT_UNSAT_VERIFIED_UNTIL_EXTERNAL_VERIPB":True}
    return proof,meta

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--certificate",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--meta",required=True,type=Path)
    a=p.parse_args()
    try:
        raw=a.source.read_bytes()
        cert=json.loads(a.certificate.read_text())
        pb,meta=compile(raw,cert)
        a.output.write_text(pb)
        a.meta.write_text(json.dumps(meta,sort_keys=True,indent=2)+"\n")
        print("ATLAS13_PBP_EMITTED "+json.dumps(meta,sort_keys=True),flush=True)
    except (ValueError,Unsupported,TypeError,IndexError,KeyError,
            MemoryError,UnicodeError,OSError) as exc:
        a.output.unlink(missing_ok=True)
        a.meta.unlink(missing_ok=True)
        print("ATLAS13_NO_PROOF "+str(exc),flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
