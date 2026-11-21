#!/usr/bin/env python3
"""ATLAS7: fixed unchanged detector from ATLAS6 on 3 separately frozen sources.

No source metadata or catalog status enters detection, GF2 or checker.
SAT only when every ORIGINAL CNF clause is satisfied.
GF2 contradiction of the recovered quotient is source-certified
STRUCTURAL_ONLY, NOT original-source VeriPB/DRAT proof.
No tuning or candidate replacement after seeing outcomes.
"""
import hashlib,json,os,sys,time,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas7_two_results";OUT.mkdir(exist_ok=True,parents=True)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/xorlin1"))
sys.path.insert(0,str(ROOT/"research/atlas6_camouflage"))
from atlas import parse,transform,encoded
from semantic_and_xor import extract,gauss_model,lift_model,Unsupported
from check_semantic import verify,Invalid
from extract import gaussian
PRE=json.loads((HERE/"prespec.json").read_text())
MAN=json.loads((ROOT/"atlas7_two_sources/manifest.json").read_text())
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
assert PRE["protocol"]=="DRNAS-ATLAS7B-TWO-ACCESSIBLE-SAT-SOURCES-20261121"
assert MAN["format"]=="ATLAS7B-FROZEN-ORIGINAL-CNF-v1"
assert len(MAN["sources"])==len(PRE["sources"])==2
assert MAN["prespec_sha256"]==hashlib.sha256((HERE/"prespec.json").read_bytes()).hexdigest()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def check_one(raw,key):
    started=time.perf_counter()
    row={"key":key,"source_sha256":digest(raw),
         "status":"UNKNOWN","strict_original_veripb_unsat":False,
         "original_SAT_model_verified":False,"GF2_quotient_structural_contradiction":False}
    try:
        quotient,certificate=extract(raw)
        exact=verify(raw,quotient,certificate)
        assert exact["status"]=="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED"
        row.update({"equivalence_independent":True,
           "camouflaged_AND_pairs":exact["masked_pairs_verified"],
           "source_truth_tables":exact["source_truth_tables_checked"],
           "virtual_variables":exact["virtual_variables"],
           "xor_equations":len(certificate["rows"]),
           "source_clauses":exact["original_clauses"],
           "quotient_clauses":exact["quotient_clauses_checked"]})
        # Save every exact original source and its fully independently source-
        # validated AND/XOR quotient before inference.
        (OUT/(key+".original.cnf")).write_bytes(raw)
        (OUT/(key+".quotient.cnf")).write_bytes(quotient)
        (OUT/(key+".semantic-certificate.json")).write_text(
            json.dumps(certificate,indent=2,sort_keys=True)+"\n")
        assignment=gauss_model(certificate["rows"],certificate["quotient_variables"])
        if assignment is None:
            equations=[{"vars":r["tokens"],"forbidden_parity":1-r["rhs"]}
                       for r in certificate["rows"]]
            subset=gaussian(equations)
            if subset is None:
                row["status"]="UNKNOWN_NO_REPRODUCIBLE_GF2_WITNESS"
            else:
                seen=collections.Counter()
                rhs=0
                for index in subset:
                    rhs^=certificate["rows"][index]["rhs"]
                    seen.update(certificate["rows"][index]["tokens"])
                assert rhs==1 and all(v%2==0 for v in seen.values())
                row["status"]="STRUCTURAL_GF2_CONTRADICTION_CHECKED_NOT_STANDARD_ORIGINAL_PROOF"
                row["GF2_quotient_structural_contradiction"]=True
                row["contradiction_rows"]=len(subset)
                (OUT/(key+".gf2-witness.json")).write_text(json.dumps({
                    "source_sha256":digest(raw),
                    "quotient_sha256":digest(quotient),
                    "selected_row_indices":subset,
                    "source_proof_required_for_strict_unsat":True},
                    sort_keys=True,indent=2)+"\n")
        else:
            model={"source_sha256":digest(raw),
                   "quotient_assignment":assignment,
                   "assignment":lift_model(certificate,assignment)}
            independent=verify(raw,quotient,certificate,model)
            assert independent["SAT_status"]=="ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED"
            row["status"]="ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED"
            row["original_SAT_model_verified"]=True
            row["original_model_clauses_checked"]=independent["source_model_all_clauses_checked"]
            (OUT/(key+".model.json")).write_text(json.dumps(model,sort_keys=True)+"\n")
        row["elapsed_s"]=round(time.perf_counter()-started,6)
    except (Unsupported,Invalid,ValueError,TypeError,UnicodeError,MemoryError,OverflowError) as exc:
        row["status"]="UNKNOWN_UNSUPPORTED_SOURCE_OR_EQUIVALENCE"
        row["reason"]=str(exc)[:250]
        row["elapsed_s"]=round(time.perf_counter()-started,6)
    (OUT/(key+".result.json")).write_text(json.dumps(row,indent=2,sort_keys=True)+"\n")
    print("ATLAS7B_SOURCE "+json.dumps(row,sort_keys=True),flush=True)
    return row

allrows=[]
for index,meta in enumerate(MAN["sources"]):
    s=PRE["sources"][index]
    assert s["gbd_hash"]==meta["gbd_hash"] and s["id"]==meta["id"]
    raw=(ROOT/meta["path"]).read_bytes()
    assert digest(raw)==meta["source_sha256"]
    original=check_one(raw,meta["id"])
    original["catalog_group_for_reporting_only"]=s["catalog_status_for_posthoc_report_only"]
    allrows.append(original)
    nv,cs=parse(raw)
    for variant_id,seed in enumerate(PRE["variant_seeds"],1):
        variation,equivalent,details=transform(nv,cs,seed+index*200,
                      rename=True,flip=(variant_id==2),shuffle=True)
        assert equivalent
        rec=check_one(variation,meta["id"]+"-v"+str(variant_id))
        rec["exact_known_bijection_to_original"]=equivalent
        rec["catalog_group_for_reporting_only"]=s["catalog_status_for_posthoc_report_only"]
        allrows.append(rec)
(OUT/"all-trials.json").write_text(json.dumps(allrows,sort_keys=True,indent=2)+"\n")
originals=[r for r in allrows if "-v" not in r["key"]]
variants=[r for r in allrows if "-v" in r["key"]]
summary={
 "status":"COMPLETE",
 "frozen_original_sources":len(originals),
 "independent_formula_origins":len({r["source_sha256"] for r in originals}),
 "controlled_permutations":len(variants),
 "source_semantics_independently_verified":sum(r.get("equivalence_independent",False) for r in allrows),
 "full_original_SAT_models_verified":sum(r["original_SAT_model_verified"] for r in allrows),
 "original_SAT_model_verified_count":sum(r["original_SAT_model_verified"] for r in originals),
 "replayed_SAT_model_verified_count":sum(r["original_SAT_model_verified"] for r in variants),
 "structural_quotient_GF2_contradictions_nonstandard":sum(r["GF2_quotient_structural_contradiction"] for r in allrows),
 "original_structural_GF2_contradictions_nonstandard":sum(r["GF2_quotient_structural_contradiction"] for r in originals),
 "unknown_trials":sum(r["status"].startswith("UNKNOWN") for r in allrows),
 "strict_original_VERIPB_UNSAT":0,
 "no_false_original_sat_model_claims":True,
 "no_source_outcome_input_to_detector":True,
 "known_source_family_coding":"AND camouflaged XOR original public benchmark",
 "not_new_competition_blind_generalization":True,
 "original_source_summaries":originals,
 "main_untouched":True}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS7B_FINAL "+json.dumps({
 k:v for k,v in summary.items() if k!="original_source_summaries"},sort_keys=True),flush=True)
