#!/usr/bin/env python3
"""ATLAS13 reproducible three-module *joint-inference* regression and controls.

Constructed, NOT public SAT Competition originals. In every positive:
  - GRAPH-only -> UNKNOWN (no complete (k+1) color clique)
  - HALL-only -> UNKNOWN (a required original mutex absent)
  - XOR-only -> UNKNOWN (no GF2 contradiction)
  - XOR2 -> source-RUP missing graph mutex -> Hall => original CNF
    standard external VeriPB VERIFIED UNSAT.
No source labels, generator mapping or SAT status enter the joint detector.

Independently check SAT counterexamples, forged SHA / XOR premises, source
mutation, and an equivalent variable permutation. No main changes.
"""
from pathlib import Path
from itertools import combinations
from collections import Counter
import hashlib,itertools,json,os,random,subprocess,sys,time

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas13_results";OUT.mkdir(parents=True,exist_ok=True)
P=json.loads((HERE/"prespec.json").read_text())
assert P["protocol"]=="DRNAS-ATLAS13-THREE-WAY-ITERATIVE-INFERENCE-V1"
assert P["fixed_before_first_joint_run"]
assert [(c["k"],c["seed"]) for c in P["cases"]]==[(3,1303),(4,1304),(5,1305)]

sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
sys.path.insert(0,str(ROOT/"research/xorlin1"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
from atlas import parse,encoded,transform
from extract import derive as xor_alone_derive
from source_php_real26 import discover as hall_alone_discover
from discover import discover as jointly_discover,facts_only,find_partition,Unsupported
from independent import check as independently_check,Invalid
from emit import compile as emit_veripb
import emit_veripb as graph_only_module

CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
def sha(x):return hashlib.sha256(x).hexdigest()

def allowed(k):
    if k==3:return ((0,1),(0,1),(1,2),(1,2))
    if k==4:return ((0,1),(0,1),(1,2),(2,3),(2,3))
    if k==5:return ((0,1),(0,1),(1,2),(2,3),(3,4),(3,4))
    raise AssertionError("UNREGISTERED_INPUT_CASE")

def make(k,seed,bridge=True):
    """Source generator; its private variable and color labels are never
    supplied to the detector or independent premise checker."""
    opts=allowed(k);group_count=len(opts)
    assert group_count==k+1
    rng=random.Random(seed)
    shuffled=list(range(1,2*group_count+1));rng.shuffle(shuffled)
    local={(g,c):shuffled[2*g+i] for g,colors in enumerate(opts)
           for i,c in enumerate(colors)}
    z=2*group_count+1
    # The selected unknown resource conflict is between two jobs choosing
    # color1; the original direct pairwise mutex will be absent.
    a,b=local[(1,1)],local[(2,1)]
    rows=[]
    for g,colors in enumerate(opts):
        vs=[local[(g,c)] for c in colors]
        rows.append(tuple(vs))
        rows.append((-vs[0],-vs[1]))  # directly source-supported EO
    for color in range(k):
        holders=[local[(g,color)] for g,colors in enumerate(opts) if color in colors]
        for x,y in combinations(holders,2):
            if frozenset((x,y))==frozenset((a,b)):continue
            rows.append((-x,-y))
    # COMPLETE source XOR2 a=z requires BOTH clauses. Neither source
    # includes original direct (-a,-b), so direct Hall has a real gap.
    rows.extend(((-a,z),(a,-z)))
    if bridge:
        rows.append((-z,-b))
    for j in range(len(rows)):rows[j]=tuple(rng.sample(rows[j],len(rows[j])))
    rng.shuffle(rows)
    raw=encoded(z,rows)
    return raw,{"a":a,"b":b,"z":z,"options":opts,"labels":local,
                "raw_sha256":sha(raw),"bridge_present":bridge}

def source_model(raw,private):
    # SAT only when the essential bridge was deleted. Intentionally permit
    # jobs 1 and 2 to share resource1, others use distinct resources.
    k=len(private["options"])-1
    choice=[0,1,1]+list(range(2,k))
    assert len(choice)==k+1
    assignment={v:False for v in range(1,2*(k+1)+2)}
    for (g,c),v in private["labels"].items():
        assignment[v]=choice[g]==c
    assignment[private["z"]]=assignment[private["a"]]
    n,clauses=parse(raw)
    assert n==len(assignment)
    assert all(any(assignment[abs(lit)]==(lit>0) for lit in cl)
               for cl in clauses),"CONTROL_SOURCE_SAT_MODEL_WRONG"
    return assignment

def external_veripb(original,proof,label):
    folder=OUT/label;folder.mkdir(parents=True,exist_ok=True)
    fn=folder/"source.cnf";pb=folder/"proof.pbp"
    fn.write_bytes(original);pb.write_text(proof)
    started=time.perf_counter()
    r=subprocess.run(["taskset","-c",str(CPU),"veripb","--cnf",str(fn),str(pb)],
       capture_output=True,text=True,timeout=25)
    (folder/"veripb.log").write_text(r.stdout+"\n"+r.stderr)
    if r.returncode!=0 or "s VERIFIED UNSATISFIABLE" not in r.stdout+r.stderr:
        raise AssertionError("EXTERNAL_VERIPB_REJECTED_"+label+" "+(r.stdout+r.stderr)[-600:])
    return round(time.perf_counter()-started,6)

def single_mode_ablations(raw,label):
    target=OUT/label;target.mkdir(parents=True,exist_ok=True)
    path=target/"source.cnf";path.write_bytes(raw)
    # Graph-only old module supports a full aligned k+1 clique only.
    try:graph_only_module.compile_source(raw)
    except graph_only_module.Unsupported:graph="UNKNOWN"
    else:raise AssertionError("GRAPH_ALONE_UNEXPECTED_FULL_CLIQUE")
    # Original direct-mutex Hall classifier has no inferred XOR2 edge.
    hall_old=hall_alone_discover(path)
    if hall_old["status"]=="CERTIFICATE_EMITTED_UNCHECKED":
        raise AssertionError("HALL_ALONE_UNEXPECTED_SOURCE_CERTIFICATE")
    # Stronger direct-Hall counterfactual: even when extra XOR aux is
    # ignored, the resource graph still lacks an original pairwise mutex.
    n,cs,s,g,owner,xors,eo=facts_only(raw)
    resources=find_partition(cs,g,owner)
    missing=sum(frozenset((-a,-b)) not in s for r in resources for a,b in combinations(r,2))
    assert missing>=1
    # XOR-only GF(2) over ALL source complete XOR2..6 rows remains consistent.
    cert,metadata=xor_alone_derive(raw)
    assert cert is None and metadata["status"]=="UNKNOWN_NO_GF2_CONTRADICTION"
    return {
      "GRAPH_ONLY":graph,"HALL_DIRECT_ONLY":"UNKNOWN",
      "HALL_direct_mutex_missing":missing,
      "HALL_old_reason":hall_old.get("reason"),
      "XOR_ALONE":"UNKNOWN_NO_GF2_CONTRADICTION",
      "XOR_extracted_source_rows":metadata["complete_source_xor_rows"],
      "source_EO_groups":eo}

def positive(raw,label,kind):
    began=time.perf_counter()
    ab=single_mode_ablations(raw,label)
    cert,meta=jointly_discover(raw)
    independently=independently_check(raw,cert)
    assert independently["status"]=="ATLAS13_THREE_MODULE_SOURCE_PREMISES_VERIFIED"
    proof,pmeta=emit_veripb(raw,cert)
    assert pmeta["status"]=="EMITTED_EXTERNAL_VERIPB_REQUIRED"
    assert pmeta["source_RUP_mutex"]==independently["xor_dependent_RUP_derived_resource_mutex"]
    ext=external_veripb(raw,proof,label)
    folder=OUT/label
    (folder/"source-certificate.json").write_text(json.dumps(cert,indent=2,sort_keys=True)+"\n")
    (folder/"independent.json").write_text(json.dumps(independently,indent=2,sort_keys=True)+"\n")
    (folder/"proof-meta.json").write_text(json.dumps(pmeta,indent=2,sort_keys=True)+"\n")
    out={
        "label":label,"kind":kind,"source_sha256":sha(raw),
        "status":"STANDARD_ORIGINAL_CNF_VERIPB_VERIFIED_UNSAT",
        "GRAPH_only":ab["GRAPH_ONLY"],"HALL_only":ab["HALL_DIRECT_ONLY"],
        "XOR_only":ab["XOR_ALONE"],"direct_resource_missing":ab["HALL_direct_mutex_missing"],
        "source_XOR2_rows":ab["XOR_extracted_source_rows"],
        "SOURCE_EO_direct":ab["source_EO_groups"],
        "joint_XOR2_derived_resource_mutex":independently["xor_dependent_RUP_derived_resource_mutex"],
        "joint_HALL_demand":independently["demand"],
        "joint_HALL_capacity":independently["capacity"],
        "proof_bytes":pmeta["proof_bytes"],"proof_sha256":pmeta["proof_sha256"],
        "veripb_s":ext,"total_math_proof_check_s":round(time.perf_counter()-began,6),
        "independent_source_premise_checker":independently["status"]}
    (folder/"trial.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("ATLAS13_JOINT_POSITIVE "+json.dumps(out,sort_keys=True),flush=True)
    return out,cert

records=[];checks=[]
for case in P["cases"]:
    k,seed=case["k"],case["seed"]
    raw,private=make(k,seed,True)
    label=f"xor-graph-hall-k{k}-seed{seed}"
    positive_record,cert=positive(raw,label,"synthetic_three_way_joint")
    assert positive_record["joint_HALL_demand"]==k+1
    assert positive_record["joint_HALL_capacity"]==k
    assert positive_record["joint_XOR2_derived_resource_mutex"]==1
    records.append(positive_record)
    if k==3:
        # Signed/inverted labels not requested; bijective variable rename
        # plus clause and literal reordering is enough for exact equivalence.
        n,source=parse(raw)
        t=P["variant"]
        changed,inverse,_=transform(n,source,t["permutation_seed"],
            rename=True,flip=False,shuffle=True)
        assert inverse and sha(changed)!=sha(raw)
        record,_=positive(changed,"xor-graph-hall-k3-renamed","bijective_rename_replay")
        record["exact_inverse_clause_map"]=inverse
        records.append(record)
        # Counterexample: delete required original (~z OR ~b). XOR2 remains
        # source-supported but does NOT imply missing graph conflict.
        altered,modified_private=make(k,seed,False)
        assert modified_private["labels"]==private["labels"]
        explicit=source_model(altered,modified_private)
        negative_label="sat-no-cross-module-bridge"
        (OUT/(negative_label+".cnf")).write_bytes(altered)
        source_model_path=OUT/(negative_label+".model.json")
        source_model_path.write_text(json.dumps({"source_sha256":sha(altered),
                 "assignment":{str(v):bool(bit) for v,bit in explicit.items()}},
                 indent=2,sort_keys=True)+"\n")
        n,m,sl,gl,owner,xr,eo=facts_only(altered)
        try:jointly_discover(altered)
        except Unsupported:checks.append({"control":"delete_one_required_implication",
              "SAT_original_model_checked":len(parse(altered)[1]),
              "joint_output":"SAFE_UNKNOWN"})
        else:raise AssertionError("FALSE_UNSAT_WITHOUT_BRIDGE_IMPLICATION")

        # Forged SHA in source certificate must be rejected.
        forged=json.loads(json.dumps(cert))
        forged["source_sha256"]="0"*64
        try:independently_check(raw,forged)
        except Invalid:checks.append({"control":"source_SHA_forged","outcome":"REJECT"})
        else:raise AssertionError("FORGED_SHA_ACCEPTED")
        # Delete EXACT source XOR truth-table clause and recompute source
        # SHA, to ensure checker rejects a mathematically missing premise.
        nn,cls=parse(raw)
        witness=cert["xor2_derived_mutex"][0]
        missing=frozenset((-witness["a"],witness["z"]))
        reduced=[];deleted=False
        for clause in cls:
            if not deleted and frozenset(clause)==missing:
                deleted=True;continue
            reduced.append(clause)
        assert deleted
        changed_source=encoded(nn,reduced)
        bad=json.loads(json.dumps(cert))
        bad["source_sha256"]=sha(changed_source)
        bad["source_clauses"]=len(reduced)
        try:independently_check(changed_source,bad)
        except Invalid:checks.append({"control":"missing_XOR2_source_clause_updated_SHA",
                            "outcome":"REJECT"})
        else:raise AssertionError("BROKEN_XOR_SOURCE_ACCEPTED")
        # Flip the claimed mathematical XOR parity without changing source.
        bad=json.loads(json.dumps(cert))
        bad["xor2_derived_mutex"][0]["xor_rhs"]=1
        try:independently_check(raw,bad)
        except Invalid:checks.append({"control":"forged_XOR_parity","outcome":"REJECT"})
        else:raise AssertionError("FORGED_XOR_PARITY_ACCEPTED")

summary={
    "status":"PASS",
    "three_distinct_constructed_k":3,
    "permuted_constructed_control":1,
    "accepted_original_source_Veripb_UNSAT":len(records),
    "each_GRAPH_only_UNKNOWN":all(r["GRAPH_only"]=="UNKNOWN" for r in records),
    "each_HALL_only_UNKNOWN":all(r["HALL_only"]=="UNKNOWN" for r in records),
    "each_XOR_only_UNKNOWN":all(r["XOR_only"]=="UNKNOWN_NO_GF2_CONTRADICTION" for r in records),
    "all_independent_original_EO_source_checked":all(r["SOURCE_EO_direct"]==r["joint_HALL_demand"] for r in records),
    "all_derived_mutex_essential_XOR2":all(r["joint_XOR2_derived_resource_mutex"]==1 for r in records),
    "SAT_and_forgery_negative_controls":checks,
    "no_proved_new_math_theorem":True,
    "new_joint_inference_vs_either_individual_mode":True,
    "not_a_public_original_competition_benchmark":True,
    "needs_independent_original_holdout":True,
    "main_untouched":True,
    "cases":records}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("ATLAS13_JOINT_FINAL "+json.dumps({k:v for k,v in summary.items()
     if k not in ("cases","SAT_and_forgery_negative_controls")},sort_keys=True),flush=True)
assert len(records)==4 and len(checks)==4
