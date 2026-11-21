#!/usr/bin/env python3
"""Single-source ATLAS4 mathematical premise probe.

Metadata-free: consumes only DIMACS bytes; never reads benchmark names,
solver statuses or expected family. Source-bound selected EO/XOR facts are
rechecked using a separately implemented original-CNF checker.
No mere fact/candidate is a SAT or UNSAT verdict.
"""
import argparse,hashlib,json,os,pathlib,sys,time,resource,collections
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
from source_facts import derive,fact_summary
from check_facts import check
from atlas import parse,scan,transform,exact_multiset
def main():
    p=argparse.ArgumentParser()
    p.add_argument("source",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path,required=True)
    p.add_argument("--variant",type=int,default=0)
    a=p.parse_args()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    # Bound parser/hash-table memory on large original competition sources.
    resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000))
    began=time.perf_counter()
    raw=a.source.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    original_sha=sha
    known_inversion=None
    if a.variant:
        nv,cls=parse(raw)
        raw,known_inversion,_=transform(nv,cls,70000+a.variant,rename=True,flip=(a.variant%2==0),shuffle=True)
        assert known_inversion
        sha=hashlib.sha256(raw).hexdigest()
        assert sha!=original_sha
    facts=derive(raw)
    verified=check(raw,facts)
    assert verified["status"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
    groups=facts["exact_one_groups"];xors=facts["complete_xor_rows"]
    owner={}
    for g in groups:
        for v in g: owner[abs(v)]=owner.get(abs(v),0)+1
    related=[r for r in xors if any(abs(v) in owner for v in r["vars"])]
    # EO-to-GRAPH fact communication: existing original binary clauses
    # block simultaneously selecting two literals from DIFFERENT EO groups.
    # This counts a source-backed connection only; it is not an UNSAT proof.
    selected=collections.defaultdict(set)
    for gnum,g in enumerate(groups):
        for lit in g:selected[lit].add(gnum)
    _,source_clauses=parse(raw)
    cross_graph=0
    for clause in source_clauses:
        if len(clause)!=2:continue
        left=selected.get(-clause[0],set())
        right=selected.get(-clause[1],set())
        if left and right and any(x!=y for x in left for y in right):
            cross_graph+=1

    # This is a potential fact handoff, not a proof or contradiction.
    out={"status":"SOURCE_FACTS_VERIFIED","input_sha256":original_sha,
         "current_source_sha256":sha,"changed_by_known_bijection":a.variant!=0,
         "inverse_clause_multiset_equivalent":known_inversion if a.variant else True,
         "variable_count":facts["source_variables"],
         "clause_count":facts["source_clauses"],
         "module_EO_facts":len(groups),
         "module_XOR_facts":len(xors),
         "xor_widths":{str(k):v for k,v in fact_summary(facts)["xor_counts"].items()},
         "eo_widths":{str(k):v for k,v in fact_summary(facts)["eo_widths"].items()},
         "module_exchange_candidates_EO_XOR":len(related),
         "module_exchange_candidates_EO_GRAPH_binary_conflicts":cross_graph,
         "exchange_status":"FACTS_ONLY_NO_JOINT_UNSAT_PROOF",
         "independent_checker":verified["status"],
         "source_bound_premise_checker":"check_facts.py",
         "elapsed_seconds":round(time.perf_counter()-began,6)}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("ATLAS4_SOURCE_FACTS "+json.dumps(out,sort_keys=True),flush=True)
if __name__=="__main__":main()
