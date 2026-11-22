#!/usr/bin/env python3
"""ATLAS12: prove GRAPH + demand (ALO) -> Hall/clique-capacity contradiction.

Three independently audited roles:
  GRAPH: source-only aligned k+1 clique from source binary mutex clauses;
  DEMAND: k+1 original positive at-least-one clauses, optional source EO;
  HALL: source-verified k covering mutex cliques give upper bound k.
Compiler is EXISTING source-PHP VeriPB emitter; independent external VeriPB
on unmodified CNF is the ONLY accepted UNSAT authority.

No source family labels, predeclared graph, solver result or filename hints
are used. The system is a reusable implementation of a *known* pigeonhole
cutting-planes argument, not an undiscovered general SAT complexity theorem.
"""
import argparse,hashlib,json,os,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/graphclique"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
import emit_veripb as graph_module
from check_php_partition import check as independent_hall_check
from emit_veripb_source_clique import emit as existing_hall_veripb_compiler

def source_sha(raw):return hashlib.sha256(raw).hexdigest()

def discover(source, budget=250000):
    started=time.perf_counter()
    raw=Path(source).read_bytes()
    nv,clauses=graph_module.parse(raw)
    alo,k,index=graph_module.collect(clauses)
    edges,matches=graph_module.graph(alo,k,clauses)
    clique,aligned,visited=graph_module.clique_search(
        edges,k+1,
        lambda nodes:graph_module.clique_alignment(nodes,alo,index,matches),
        max_trials=budget)
    if clique is None:raise graph_module.Unsupported("NO_KPLUS1_SOURCE_CLIQUE")
    demanded=[sorted(alo[v]) for v in clique]
    resources=[sorted(aligned[v][c] for v in clique) for c in range(k)]
    selected={v for g in demanded for v in g}
    assert len(demanded)==k+1 and len(resources)==k
    assert len(selected)==k*(k+1)
    assert sorted(v for r in resources for v in r)==sorted(selected)
    source_clauses={frozenset(c) for c in clauses}
    eo_direct=sum(all(frozenset((-a,-b)) in source_clauses
                      for i,a in enumerate(group) for b in group[i+1:])
                  for group in demanded)
    cert={"format":"DRNAS-source-clique-capacity-v1",
      "source_sha256":source_sha(raw),
      "source_variables":nv,"source_clauses":len(clauses),
      "selected_groups":demanded,"capacity_cliques":resources,
      "demand":len(demanded),"capacity":len(resources)}
    facts={"status":"HALL_PREMISES_SOURCE_ONLY_UNVERIFIED",
      "source_sha256":source_sha(raw),
      "source_variables":nv,"source_clauses":len(clauses),
      "ALO_source_groups":len(demanded),"GRAPH_aligned_clique":len(clique),
      "color_options_per_group":k,"HALL_resources":len(resources),
      "HALL_deficit":len(demanded)-len(resources),
      "direct_source_exact_one_groups":eo_direct,
      "exact_one_status":("SOURCE_PAIRWISE_AMO_CONFIRMED" if eo_direct==len(demanded)
                          else "ALO_VERIFIED_AMO_SEQUENTIAL_OR_UNPROVED"),
      "graph_search_nodes":visited,
      "search_s":round(time.perf_counter()-started,6),
      "not_assume_general_graph_sat_polynomial":True}
    return cert,facts

def run(cnf,certificate,proof,meta,budget=250000):
    cnf=Path(cnf);certificate=Path(certificate);proof=Path(proof);meta=Path(meta)
    started=time.perf_counter()
    cert,reported=discover(cnf,budget)
    certificate.parent.mkdir(parents=True,exist_ok=True)
    certificate.write_text(json.dumps(cert,sort_keys=True,indent=2)+"\n")
    # The independent Hall source checker does not import the graph module.
    checked=independent_hall_check(cnf,certificate)
    assert checked["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED"
    if checked["sha256"]!=cert["source_sha256"]:
        raise AssertionError("CERTIFICATE_SOURCE_MISMATCH")
    # Independent emitter also re-reads and verifies original clauses/claims.
    produced=existing_hall_veripb_compiler(cnf,certificate,proof)
    assert produced["status"]=="EMITTED_UNCHECKED"
    assert produced["source_sha256"]==cert["source_sha256"]
    result={**reported,
      "status":"PROOF_EMITTED_EXTERNAL_VERIPB_REQUIRED",
      "independent_source_checker":checked["status"],
      "separate_proof_emitter":produced["status"],
      "proof_sha256":produced["proof_sha256"],
      "proof_bytes":produced["proof_bytes"],
      "proof_pol_steps":produced["proof_pol_steps"],
      "end_to_end_without_external_checker_s":round(time.perf_counter()-started,6)}
    meta.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS12_SOURCE_BRIDGE "+json.dumps(result,sort_keys=True),flush=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",required=True,type=Path)
    p.add_argument("--certificate",required=True,type=Path)
    p.add_argument("--proof",required=True,type=Path)
    p.add_argument("--meta",required=True,type=Path)
    p.add_argument("--budget",type=int,default=250000)
    args=p.parse_args()
    try:
        run(args.cnf,args.certificate,args.proof,args.meta,args.budget)
    except (ValueError,AssertionError,TypeError,KeyError,graph_module.Unsupported,
            UnicodeError,OSError,OverflowError,MemoryError) as e:
        args.proof.unlink(missing_ok=True)
        args.meta.unlink(missing_ok=True)
        args.certificate.unlink(missing_ok=True)
        print("ATLAS12_SAFE_UNKNOWN "+str(e)[:300],flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
