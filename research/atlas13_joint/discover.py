#!/usr/bin/env python3
"""ATLAS13 source-only XOR2 -> GRAPH conflict -> HALL proof candidate producer.

The CNF alone is the input. No source label, generator mapping, SAT/UNSAT
status, predefined list coloring, variable numbering or expected answer is
passed here. The source-only procedure joins:
  - disjoint original positive ALO groups (and independent direct EO check)
  - resource graph connected components of ORIGINAL cross-group mutex clauses
  - one missing resource mutex supported by an ORIGINAL complete XOR2
    equality a=z and original implication (~z or ~b)
  - Hall contradiction demand groups > fully verified resource mutex cliques.

The producer cannot claim UNSAT. The independent source fact checker and then
EXTERNAL original-source VeriPB are both required.
"""
from collections import defaultdict
from pathlib import Path
import argparse,hashlib,itertools,json,sys,time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
from atlas import parse
from source_facts import derive as derive_facts
from check_facts import check as independently_check_source_facts

class Unsupported(ValueError):pass
def require(ok,msg):
    if not ok:raise Unsupported(msg)
def sha(raw):return hashlib.sha256(raw).hexdigest()

def facts_only(raw):
    n,rows=parse(raw)
    require(len(raw)<=1_000_000 and n<=300 and len(rows)<=3000,"SOURCE_RESOURCE_LIMIT")
    source={frozenset(clause) for clause in rows}
    groups=sorted({tuple(sorted(clause)) for clause in rows
          if 2<=len(clause)<=8 and all(lit>0 for lit in clause)
          and len(set(clause))==len(clause)})
    require(3<=len(groups)<=16,"SOURCE_POSITIVE_ALO_COUNT_GATE")
    owner={}
    for i,g in enumerate(groups):
        for v in g:
            require(v not in owner,"SOURCE_ALO_GROUPS_OVERLAP")
            owner[v]=i
    xor=derive_facts(raw)
    checked=independently_check_source_facts(raw,xor)
    require(checked["status"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED","INDEPENDENT_FACTS_CHECK_FAIL")
    eo={frozenset(g) for g in xor["exact_one_groups"]}
    selected_eo=sum(frozenset(g) in eo for g in groups)
    xorrows=[r for r in xor["complete_xor_rows"] if len(r["vars"])==2]
    return n,rows,source,groups,owner,xorrows,selected_eo

def find_partition(rows,groups,owner):
    # Source-only resource graph: connect selectors from DIFFERENT ALO
    # groups whenever the original has a direct negative binary mutex.
    selected=sorted(owner)
    parent={v:v for v in selected}
    def find(v):
        while parent[v]!=v:
            parent[v]=parent[parent[v]]
            v=parent[v]
        return v
    for clause in rows:
        if len(clause)!=2 or any(x>=0 for x in clause):continue
        a,b=-clause[0],-clause[1]
        if a in owner and b in owner and owner[a]!=owner[b]:
            pa,pb=find(a),find(b)
            if pa!=pb:parent[pb]=pa
    comps=defaultdict(list)
    for v in selected:comps[find(v)].append(v)
    resources=sorted((sorted(c) for c in comps.values()),key=lambda x:(min(x),len(x)))
    require(all(len(r)>=2 for r in resources),"ISOLATED_RESOURCE_OPTION")
    require(len(groups)>len(resources)>0,"NO_HALL_DEFICIT")
    return resources

def bridge_for_pair(a,b,source,xorrows,selected):
    # Valid XOR2 equality a=z is present as BOTH (a OR ~z) and
    # (~a OR z). Together with (~z OR ~b), unit propagation under
    # a=b=TRUE derives a contradiction; so (~a OR ~b) is source-RUP.
    # Try both orientations of the missing resource mutex.
    for u,v in ((a,b),(b,a)):
        for x in xorrows:
            if x["rhs"]!=0 or u not in x["vars"]:continue
            z=next(t for t in x["vars"] if t!=u)
            if z in selected:continue
            if (frozenset((-u,z)) in source and
                frozenset((u,-z)) in source and
                frozenset((-z,-v)) in source):
                return {"a":u,"b":v,"z":z,
                    "xor_vars":sorted([u,z]),"xor_rhs":0,
                    "relation":"XOR2_EQUALITY_AND_DIRECT_BINARY_IMPLICATION",
                    "required_source_clauses":[[-u,z],[u,-z],[-z,-v]]}
    return None

def discover(raw):
    t=time.perf_counter()
    nv,rows,source,groups,owner,xorrows,eo=facts_only(raw)
    resources=find_partition(rows,groups,owner)
    gap=[]
    for r in resources:
        for a,b in itertools.combinations(r,2):
            if frozenset((-a,-b)) not in source:gap.append((a,b))
    require(bool(gap),"HALL_DIRECTLY_SOURCE_COMPLETE_NO_XOR_SYNERGY")
    require(len(gap)<=3,"TOO_MANY_UNPROVED_CROSS_RESOURCE_MUTEX")
    selected=set(owner)
    witnesses=[]
    for a,b in gap:
        found=bridge_for_pair(a,b,source,xorrows,selected)
        require(found is not None,"MISSING_XOR2_BRIDGE_FOR_RESOURCE_MUTEX")
        witnesses.append(found)
    cert={
        "format":"DRNAS-ATLAS13-XOR2-GRAPH-HALL-CERT-v1",
        "source_sha256":sha(raw),"source_variables":nv,
        "source_clauses":len(rows),
        "alo_groups":[list(g) for g in groups],
        "resource_cliques":resources,
        "xor2_derived_mutex":witnesses,
        "demand":len(groups),"capacity":len(resources)}
    report={
        "status":"CANDIDATE_SOURCE_PREMISES_NOT_FINAL_UNSAT",
        "original_sha256":sha(raw),
        "source_ALO_groups":len(groups),"direct_source_EO_groups":eo,
        "source_XOR2_rows":len(xorrows),
        "resource_cliques":len(resources),"missing_direct_mutex":len(gap),
        "XOR2_bridges":len(witnesses),
        "HALL_deficit":len(groups)-len(resources),
        "source_variables":nv,"source_clauses":len(rows),
        "math_s":round(time.perf_counter()-t,6)}
    return cert,report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--meta",type=Path,required=True)
    a=p.parse_args()
    try:
        cert,report=discover(a.cnf.read_bytes())
        a.certificate.parent.mkdir(exist_ok=True,parents=True)
        a.certificate.write_text(json.dumps(cert,sort_keys=True,indent=2)+"\n")
        a.meta.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
        print("ATLAS13_SOURCE_CANDIDATE "+json.dumps(report,sort_keys=True),flush=True)
    except (Unsupported,ValueError,TypeError,IndexError,KeyError,UnicodeError,OverflowError) as exc:
        a.certificate.unlink(missing_ok=True)
        a.meta.unlink(missing_ok=True)
        print("ATLAS13_UNKNOWN "+str(exc),flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
