#!/usr/bin/env python3
"""ATLAS13 controlled proof of JOINT inference beyond either component alone.

Construct three distinct list-coloring/Hall shapes with ALO width 3/4/5
(non-2SAT overall) and 1,2,3 independently masked resource-mutex clauses.
Each hidden mutex is REPLACED (not added) by original source implications:
  (-a or t), (-t or -b), with auxiliary t and source variable shuffle.
Neither the original GRAPH aligned-clique scout nor a direct-mutex Hall
scout recognizes UNSAT. The 2-SAT implication subformula is explicitly
satisfiable (all-false) and supplies only new graph lemmas.
Only transmitting those proven lemmas into Hall results in an accepted
standard VeriPB proof of the unchanged original.

All controls are synthetically constructed; no claim of competitive gains
or new real-world UNSAT sources. External VeriPB is the last authority.
"""
import hashlib,itertools,json,os,random,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas13_results"
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
sys.path.insert(0,str(ROOT/"research/atlas12_graph_hall"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
from atlas import parse,encoded,transform
from source_facts import derive as eo_facts
from check_facts import check as eo_source_checker
from source_php_real26 import discover as old_hall
from check_php_partition import check as hall_independent
from bridge import compile_original,baseline_status,hall_partition,derived_two_hop_graph_lemmas,Unknown,sha
from witness_checker import check_witness,Invalid

CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
def options(k):
    if k==4:return [(0,1,2),(0,1,2),(1,2,3),(1,2,3),(0,2,3)]
    if k==5:return [(0,1,2,3),(0,1,2,3),(1,2,3,4),
                   (1,2,3,4),(0,2,3,4),(0,2,3,4)]
    if k==6:return [(0,1,2,3,4),(0,1,2,3,4),(1,2,3,4,5),
                   (1,2,3,4,5),(0,2,3,4,5),(0,2,3,4,5),
                   (0,2,3,4,5)]
    raise ValueError("unknown_control_k")

def mask_targets(k):
    if k==4:return [(0,1,0)]
    if k==5:return [(0,1,0),(4,5,4)]
    if k==6:return [(0,1,0),(2,3,1),(4,5,5)]
    raise ValueError("unknown_control_k")

def make(k,seed,drop_implication_index=None):
    rng=random.Random(seed)
    groups=options(k);n=len(groups)
    assert n==k+1
    options_count=sum(len(z) for z in groups)
    choices=list(range(1,options_count+1))
    rng.shuffle(choices)
    symbols={}
    cursor=iter(choices)
    for gi,allowed in enumerate(groups):
        for c in allowed:symbols[(gi,c)]=next(cursor)
    masked={tuple(sorted((symbols[(i,c)],symbols[(j,c)]))):q
            for q,(i,j,c) in enumerate(mask_targets(k))}
    cs=[]
    for gi,allowed in enumerate(groups):
        row=[symbols[(gi,c)] for c in allowed]
        cs.append(tuple(row))
        cs.extend([(-a,-b) for a,b in itertools.combinations(row,2)])
    for color in range(k):
        holders=[symbols[(i,color)] for i,g in enumerate(groups) if color in g]
        for a,b in itertools.combinations(holders,2):
            if tuple(sorted((a,b))) not in masked:
                cs.append((-a,-b))
    # Every masked pair receives a fresh auxiliary t, located outside all
    # positive source ALO clauses. No list/group labels reach detector.
    auxiliaries={}
    for pair,ordinal in sorted(masked.items(),key=lambda x:x[1]):
        a,b=pair
        t=options_count+ordinal+1
        auxiliaries[(a,b)]=t
        cs.append((-a,t))
        if ordinal!=drop_implication_index:cs.append((-t,-b))
    cs=[tuple(rng.sample(row,len(row))) for row in cs]
    rng.shuffle(cs)
    raw=encoded(options_count+len(masked),cs)
    return raw,{"symbols":symbols,"masked":masked,
                "auxiliaries":auxiliaries,"selected_original_groups":groups,
                "source_sha256":sha(raw),"source_vars":options_count+len(masked),
                "source_clauses":len(cs),"source_graph_k":k,
                "source_graph_n":n,"replaced_source_conflicts":len(masked),
                "source_only_no_catalog_hint":True}

def full_model(raw,model):
    nv,cls=parse(raw)
    return (len(model)==nv and
            all(any(model[abs(l)]==(l>0) for l in row) for row in cls))

def external_veripb(cnf,proof,key):
    start=time.perf_counter()
    response=subprocess.run(["taskset","-c",str(CPU),"veripb","--cnf",str(cnf),str(proof)],
        capture_output=True,text=True,timeout=25)
    (OUT/(key+".veripb.log")).write_text(response.stdout+"\n"+response.stderr)
    if response.returncode!=0 or "s VERIFIED UNSATISFIABLE" not in response.stdout+response.stderr:
        raise AssertionError("EXTERNAL_VERIPB_REJECTED_"+key+" "+
                             (response.stdout+response.stderr)[-700:])
    return round(time.perf_counter()-start,6)

def audit_one(raw,key,category,expected_lemmas):
    folder=OUT/key
    folder.mkdir(exist_ok=False,parents=True)
    source=folder/"original.cnf";source.write_bytes(raw)
    baseline=baseline_status(source)
    assert baseline["GRAPH_CLIQUE_ONLY"]=="UNKNOWN",baseline
    assert baseline["HALL_DIRECT_ONLY"]=="UNKNOWN",baseline
    assert baseline["binary_implication_subsystem_has_all_false_model"],baseline
    prior=old_hall(source)
    assert prior["status"]=="UNKNOWN",prior
    # Direct original facts: exact-one groups must be independently verified
    # without the hidden resource mutexes.
    facts=eo_facts(raw)
    checked_eo=eo_source_checker(raw,facts)
    assert checked_eo["status"]=="SOURCE_FACTS_INDEPENDENTLY_VERIFIED"
    positive={frozenset(row) for row in parse(raw)[1] if
              len(row)>=3 and all(v>0 for v in row)}
    actual_eo={frozenset(g) for g in facts["exact_one_groups"]}
    assert positive <= actual_eo
    # No graph fact by itself yields original UNSAT; Hall remains UNKNOWN
    # until all source-derived graph lemmas are added.
    lemmas=derived_two_hop_graph_lemmas(raw)
    assert len(lemmas)==expected_lemmas,(key,len(lemmas),expected_lemmas)
    provisional={"format":"DRNAS-ATLAS13-GRAPH-IMPLICATION-v1",
                 "source_sha256":sha(raw),
                 "original_clause_count":len(parse(raw)[1]),"lemmas":lemmas}
    witness=check_witness(raw,provisional)
    assert witness["status"]=="GRAPH_IMPLICATION_LEMMAS_SOURCE_VERIFIED"
    # Critical joint-inference ablation: even if all BUT LAST message
    # arrive, Hall must stay UNKNOWN (for k=5 or k=6 multi-message cases).
    if len(lemmas)>1:
        try:hall_partition(raw,lemmas[:-1])
        except Unknown:pass
        else:raise AssertionError("HALL_ALREADY_SOLVED_BEFORE_LAST_GRAPH_MESSAGE")
    cert=folder/"source-graph-lemmas-and-hall.json"
    pbp=folder/"standard-original-source.pbp"
    meta=folder/"bridge-result.json"
    result=compile_original(source,cert,pbp,meta)
    assert result["derived_source_RUP_lemmas"]==len(lemmas)
    checker_s=external_veripb(source,pbp,key)
    result.update({
        "case":key,"case_kind":category,
        "strict_original_unsat_veripb":True,
        "standard_checker_s":checker_s,
        "source_direct_exact_one_groups":len(positive),
        "strict_status":"STANDARD_ORIGINAL_CNF_VERIPB_VERIFIED_UNSAT"})
    (folder/"trial.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS13_JOINT_VERIFIED "+json.dumps({
       "case":key,"source_sha256":sha(raw),
       "source_EO_groups":len(positive),
       "graph_only":baseline["GRAPH_CLIQUE_ONLY"],
       "hall_only":baseline["HALL_DIRECT_ONLY"],
       "transferred_RUP_lemmas":len(lemmas),
       "demand":result["ALO_demand"],
       "capacity":result["HALL_capacity"],
       "proof_bytes":result["proof_bytes"],
       "veripb_s":checker_s},sort_keys=True),flush=True)
    return result

cases=[]
for k in (4,5,6):
    raw,details=make(k,seed=20261122+37*k)
    cases.append(audit_one(raw,f"exchange-k{k}-n{k+1}",
                    "generated_original_graph_hall_joint",len(mask_targets(k))))
    if k==4:
        # One known-equivalent rename preserving positive original clauses;
        # detector never gets the original variable map.
        nv,original=parse(raw)
        altered,equivalent,_=transform(nv,original,512991,rename=True,flip=False,shuffle=True)
        assert equivalent and altered!=raw
        cases.append(audit_one(altered,"exchange-k4-renamed",
                     "generated_bijective_relabel",1))
        # Explicit SAT from removing ONE source implication (not just
        # updating SHA): two jobs can now share one resource, so no Hall
        # contradiction survives.
        sat,sat_info=make(k,seed=20261122+37*k,drop_implication_index=0)
        assert sat_info["symbols"]==details["symbols"]
        symbols=sat_info["symbols"]
        chosen=[0,0,1,2,3]
        model={v:(c==chosen[g]) for (g,c),v in symbols.items()}
        for pair,t in sat_info["auxiliaries"].items():
            # Path first clause remains: (-a or t); select t TRUE as
            # requested if a is TRUE, while missing second implication.
            a,b=pair
            model[t]=model[a]
        assert full_model(sat,model),"EXPLICIT_SAT_MODEL_BROKEN"
        sfolder=OUT/"removed-graph-implication-SAT"
        sfolder.mkdir(exist_ok=True)
        satpath=sfolder/"source.cnf";satpath.write_bytes(sat)
        status=baseline_status(satpath)
        assert status["GRAPH_CLIQUE_ONLY"]=="UNKNOWN"
        assert status["HALL_DIRECT_ONLY"]=="UNKNOWN"
        try:derived_two_hop_graph_lemmas(sat)
        except Unknown:safe_no_transfer=True
        else:raise AssertionError("BAD_SOURCE_GRAPH_LEMMA_ON_EXPLICIT_SAT_SOURCE")
        # Forge unchanged lemma with *updated* new original SHA, and
        # independently reject its now missing source implication edge.
        original_claim=json.loads((OUT/"exchange-k4-n5"/
                        "source-graph-lemmas-and-hall.json").read_text())
        forged={k:v for k,v in original_claim.items() if k in
                ("format","source_sha256","original_clause_count","lemmas")}
        forged["source_sha256"]=sha(sat)
        forged["original_clause_count"]=len(parse(sat)[1])
        try:check_witness(sat,forged)
        except Invalid:rejected_changed_SHA=True
        else:raise AssertionError("FORGED_SOURCE_PROOF_ACCEPTED")
        # Mutation of an original path without updating SHA also rejected.
        wrong=dict(forged,source_sha256="0"*64)
        try:check_witness(sat,wrong)
        except Invalid:rejected_bad_SHA=True
        else:raise AssertionError("FORGED_SHA_WAS_ACCEPTED")
        controls={"source_sha256":sha(sat),
             "source_clauses_checked":len(parse(sat)[1]),
             "explicit_original_SAT_model_verified":True,
             "graph_clique_only_unknown":True,
             "hall_direct_only_unknown":True,
             "joint_lemmas_not_derivable":safe_no_transfer,
             "stale_bridge_certificate_with_updated_SHA_rejected":rejected_changed_SHA,
             "forged_source_sha_rejected":rejected_bad_SHA}
        (sfolder/"safety.json").write_text(json.dumps(controls,sort_keys=True,indent=2)+"\n")
        print("ATLAS13_NEGATIVE_CONTROL "+json.dumps(controls,sort_keys=True),flush=True)
summary={"status":"COMPLETE","scope":"Controlled synthetic graph+2SAT implication+Hall source-inference communication, not new untested competition sources",
  "source_only_semantics":True,
  "generated_distinct_graph_instances":3,
  "renamed_variants":1,
  "baseline_both_UNKNOWN_all":all(x["baseline_modes"]["GRAPH_CLIQUE_ONLY"]=="UNKNOWN"
          and x["baseline_modes"]["HALL_DIRECT_ONLY"]=="UNKNOWN" for x in cases),
  "original_external_VERIPB_accepted":sum(x["strict_original_unsat_veripb"] for x in cases),
  "total_proven_transferred_lemmas":sum(x["derived_source_RUP_lemmas"] for x in cases),
  "multi_lemma_full_information_required":True,
  "negative_controls":controls,
  "full_source_proof_on_unmodified_CNF":True,
  "known_Hall_and_2SAT_theorems_not_new_complexity_class":True,
  "not_yet_prospective_real_original_generalization":True,
  "no_main_promotion":True,
  "cases":cases}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS13_FINAL "+json.dumps({k:v for k,v in summary.items() if k not in ("cases","negative_controls")},sort_keys=True),flush=True)
assert summary["original_external_VERIPB_accepted"]==4
assert summary["total_proven_transferred_lemmas"]==7 # 1+2+3+1
assert summary["baseline_both_UNKNOWN_all"]
assert all(controls[k] for k in ("explicit_original_SAT_model_verified",
            "stale_bridge_certificate_with_updated_SHA_rejected",
            "forged_source_sha_rejected"))
