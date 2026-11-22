#!/usr/bin/env python3
"""ATLAS12B additional coverage where GRAPH-clique alone safely UNKNOWN.

Construct list-coloring/assignment systems with n=k+1 jobs and k resources,
but *heterogeneous allowed resources*: no fully matched group-level (k+1)
clique exists. Known Hall capacity argument is reconstructed from original
mutual exclusion clauses. Assert exact source EO for every demand, two
individual module statuses, and external VeriPB proof on exact original.
This is a controlled complementarity demonstration, NOT a new complexity
result nor a new competition benchmark.
"""
import hashlib,itertools,json,os,random,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas12b_results";OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
from atlas import encoded,parse,transform
from source_facts import derive as source_eo_facts
from check_facts import check as independent_eo_source_check
from check_php_partition import check as independent_hall_source_check
from source_php_real26 import discover as original_hall_detector
from bridge import discover as original_graph_detector
from unified import run as both_modes
import emit_veripb as graph_module

CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
def sha(raw):return hashlib.sha256(raw).hexdigest()
def allowed(k):
    if k==3:return [(0,1),(0,1),(1,2),(1,2)]
    if k==4:return [(0,1),(0,1),(1,2),(2,3),(2,3)]
    if k==5:return [(0,1),(0,1),(1,2),(2,3),(3,4),(3,4)]
    raise ValueError("unknown_input")

def make(k,seed,remove_pair=None):
    lists=allowed(k);n=len(lists)
    assert n==k+1
    rng=random.Random(seed)
    numbers=list(range(1,2*n+1));rng.shuffle(numbers)
    choices={(g,c):numbers[2*g+j] for g,opts in enumerate(lists)
             for j,c in enumerate(opts)}
    clauses=[]
    for g,opts in enumerate(lists):
        lits=[choices[(g,c)] for c in opts]
        clauses.append(tuple(lits))
        clauses.extend([(-a,-b) for a,b in itertools.combinations(lits,2)])
    for c in range(k):
        holders=[choices[(g,c)] for g,opts in enumerate(lists) if c in opts]
        assert len(holders)>=2
        for a,b in itertools.combinations(holders,2):
            if remove_pair is not None and frozenset([a,b])==frozenset(remove_pair):
                continue
            clauses.append((-a,-b))
    clauses=[tuple(rng.sample(row,len(row))) for row in clauses]
    rng.shuffle(clauses)
    return encoded(2*n,clauses),choices

def check_model(raw,model):
    n,cs=parse(raw)
    return len(model)==n and all(any(model[abs(lit)]==(lit>0) for lit in cl) for cl in cs)

def external_veripb(source,proof,key):
    t=time.perf_counter()
    r=subprocess.run(["taskset","-c",str(CPU),"veripb","--cnf",str(source),str(proof)],
        text=True,capture_output=True,timeout=25)
    accepted=r.returncode==0 and "s VERIFIED UNSATISFIABLE" in r.stdout+r.stderr
    (OUT/(key+".veripb.log")).write_text(r.stdout+"\n"+r.stderr)
    if not accepted:raise AssertionError("EXTERNAL_VERIPB_REJECTED_"+key+" "+(r.stdout+r.stderr)[-350:])
    return round(time.perf_counter()-t,6)

cases=[]
controls=[]
for k in (3,4,5):
    raw,choices=make(k,313+k)
    key=f"list-hall-n{k+1}-r{k}"
    folder=OUT/key;folder.mkdir(parents=True,exist_ok=True)
    cnf=folder/"original.cnf";cnf.write_bytes(raw)
    facts=source_eo_facts(raw)
    independently=independent_eo_source_check(raw,facts)
    assert independently["status"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
    all_eo={frozenset(e) for e in facts["exact_one_groups"]}
    assert all(frozenset(choices[(g,c)] for c in opts) in all_eo
               for g,opts in enumerate(allowed(k)))
    # GRAPH only must not see an entire k+1 full aligned clique.
    try:original_graph_detector(cnf,max(12000,500*k))
    except graph_module.Unsupported:graph_only="UNKNOWN_NO_FULL_GRAPH_CLIQUE"
    else:raise AssertionError("GRAPH_ONLY_UNEXPECTEDLY_PROVED_NONCLIQUE_"+key)
    h=original_hall_detector(cnf)
    assert h["status"]=="CERTIFICATE_EMITTED_UNCHECKED",h
    independent=folder/"standalone-hall.json"
    independent.write_text(json.dumps(h["certificate"],sort_keys=True)+"\n")
    assert independent_hall_source_check(cnf,independent)["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED"
    cert=folder/"combined-source-certificate.json"
    pbp=folder/"original-veripb.pbp"
    metadata=folder/"bridge-result.json"
    record=both_modes(cnf,cert,pbp,metadata)
    assert record["inference_mode"]=="HALL_RESOURCE_GRAPH"
    assert independent_hall_source_check(cnf,cert)["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED"
    verifier_s=external_veripb(cnf,pbp,key)
    entry={"key":key,"source_sha256":sha(raw),"status":"UNSAT_ORIGINAL_VERIPB_VERIFIED",
      "GROUP_EO_source_checked":len(allowed(k)),
      "GRAPH_ONLY":graph_only,"GRAPH_HALL_mode":record["inference_mode"],
      "HALL_capacity":record["hall_capacity"],
      "ALO_demand":record["alo_demand"],
      "UNSAT_deficit":record["alo_demand"]-record["hall_capacity"],
      "proof_bytes":record["proof_bytes"],
      "external_Veripb_wall_s":verifier_s}
    cases.append(entry)
    print("ATLAS12B_NONCLIQUE "+json.dumps(entry,sort_keys=True),flush=True)

    if k==3:
        # Same nonclique relation under deterministic variable rename/shuffle.
        nn,clauses=parse(raw)
        alt,invert,_=transform(nn,clauses,97113,rename=True,flip=False,shuffle=True)
        assert invert
        variant=folder/"source-renamed.cnf";variant.write_bytes(alt)
        meta=both_modes(variant,folder/"rename-cert.json",
                        folder/"rename-proof.pbp",folder/"rename-meta.json")
        assert meta["inference_mode"]=="HALL_RESOURCE_GRAPH"
        sec=external_veripb(variant,folder/"rename-proof.pbp","nonclique-var")
        entry={"key":"list-hall-n4-renamed","source_sha256":sha(alt),
               "status":"UNSAT_ORIGINAL_VERIPB_VERIFIED",
               "source_equivalent_by_inverse_clause_map":invert,
               "GRAPH_HALL_mode":meta["inference_mode"],
               "external_Veripb_wall_s":sec}
        cases.append(entry)
        print("ATLAS12B_NONCLIQUE "+json.dumps(entry,sort_keys=True),flush=True)
        # SAT control: delete precisely ONE source conflict between groups 1
        # and 2 sharing resource 1. Then 4 demands can use only 3 resources
        # by allowing groups 1 and 2 to share resource 1.
        oldpair=(choices[(1,1)],choices[(2,1)])
        sat,choices_s=make(k,313+k,remove_pair=oldpair)
        # make(k, seed) uses deterministic generator and preserves mapping.
        assert choices_s==choices
        assignment_color=[0,1,1,2]
        sat_assignment={v:(assignment_color[g]==c) for (g,c),v in choices_s.items()}
        assert check_model(sat,sat_assignment),"SAT_CONTROL_MODEL_INVALID"
        satpath=folder/"one-mutex-deleted-SAT.cnf";satpath.write_bytes(sat)
        try:original_graph_detector(satpath)
        except graph_module.Unsupported:pass
        else:raise AssertionError("GRAPH_FALSE_UNSAT_ON_SAT_CONTROL")
        hall=original_hall_detector(satpath)
        assert hall["status"]=="UNKNOWN",hall
        controls.append({"control":"deleted_one_essential_mutex","status":"SAT_MODEL_VERIFIED",
                         "GRAPH_mode":"UNKNOWN","HALL_mode":"UNKNOWN",
                         "original_sat_clauses_checked":len(parse(sat)[1])})
        # Negative source-premise with SHA updated for the same removed clause:
        forged=json.loads((folder/"combined-source-certificate.json").read_text())
        forged["source_sha256"]=sha(sat)
        forged["source_clauses"]=len(parse(sat)[1])
        certfake=folder/"source-mutated-updated-SHA.json"
        certfake.write_text(json.dumps(forged,sort_keys=True)+"\n")
        try:independent_hall_source_check(satpath,certfake)
        except ValueError:controls.append({"control":"deleted_source_mutex_SHA_updated",
               "status":"INDEPENDENT_HALL_CHECK_REJECTED"})
        else:raise AssertionError("FORGED_PREMISE_ACCEPTED")
        # Explicitly wrong original source SHA must also fail independently.
        forged=json.loads((folder/"combined-source-certificate.json").read_text())
        forged["source_sha256"]="0"*64
        certfake=folder/"forged-SHA-certificate.json"
        certfake.write_text(json.dumps(forged,sort_keys=True)+"\n")
        try:independent_hall_source_check(cnf,certfake)
        except ValueError:controls.append({"control":"forged_original_SHA",
              "status":"INDEPENDENT_HALL_CHECK_REJECTED"})
        else:raise AssertionError("FORGED_ORIGINAL_SHA_ACCEPTED")

summary={"status":"PASS",
 "nonclique_original_constructed_sources":3,
 "renamed_nonclique_variants":1,
 "nonclique_external_standard_Veripb":sum(c["status"]=="UNSAT_ORIGINAL_VERIPB_VERIFIED" for c in cases),
 "true_EO_sources_independently_checked":3,
 "GRAPH_alone_safe_unknown":3,
 "HALL_resource_mode_accepted":4,
 "negative_controls":controls,
 "cases":cases,
 "novelty_scope":"Known Hall theorem, newly integrated complementary source modes; not new graph theorem or competition benchmark",
 "genuinely_new_coverage_for_graph_only_mode":True,
 "new_synergy_neither_original_module_could_solve":False,
 "original_main_untouched":True}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("ATLAS12B_FINAL "+json.dumps({k:v for k,v in summary.items()
  if k not in ("negative_controls","cases")},sort_keys=True),flush=True)
assert summary["nonclique_external_standard_Veripb"]==4
assert len(controls)==3
