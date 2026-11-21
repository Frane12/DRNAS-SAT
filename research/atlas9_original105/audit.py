#!/usr/bin/env python3
"""ATLAS9: exact public original CNF masked XOR -> standard original VeriPB.

PRE-EXISTING rules only: import frozen ATLAS6 source-only semantic detector,
its independent truth-table checker and ATLAS8 original-CNF proof compiler.
Neither receives filename, provenance, catalog SAT/UNSAT label or GBD id.
UNSAT strict only if external VeriPB 3.0.2 accepts PBP on original bytes.
No source replacement, and every negative or unsupported outcome preserved.
"""
import hashlib,itertools,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas9_original105_results"
OUT.mkdir(exist_ok=True,parents=True)
SPEC=json.loads((HERE/"prespec.json").read_text())
FROZEN=json.loads((ROOT/"atlas9_original105_source/source-frozen.json").read_text())
SOURCE=ROOT/"atlas9_original105_source/original.cnf"
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/atlas6_camouflage"))
sys.path.insert(0,str(ROOT/"research/atlas8_masked_unsat"))
from atlas import parse,transform,encoded
from semantic_and_xor import extract,gauss_model,lift_model,Unsupported
from check_semantic import verify,Invalid
from proof import build_standard_original_proof
cpu=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{cpu})
def digest(x):return hashlib.sha256(x).hexdigest()

def check_standard_cnf(raw,proof,tag):
    cnf=OUT/(tag+".original.cnf")
    pbp=OUT/(tag+".proof.pbp")
    cnf.write_bytes(raw)
    pbp.write_text(proof)
    start=time.perf_counter()
    try:
        r=subprocess.run(["taskset","-c",str(cpu),"veripb","--cnf",str(cnf),str(pbp)],
           capture_output=True,text=True,timeout=45)
        status=("STANDARD_VERIPB_VERIFIED_UNSAT"
            if r.returncode==0 and "s VERIFIED UNSATISFIABLE" in r.stdout+r.stderr
            else "UNVERIFIED_EXTERNAL_PROOF_REJECTED")
        (OUT/(tag+".veripb.log")).write_text(r.stdout+"\n"+r.stderr)
        return {"status":status,"returncode":r.returncode,
                "wall_s":round(time.perf_counter()-start,6)}
    except subprocess.TimeoutExpired:
        return {"status":"UNKNOWN_VERIPB_TIMEOUT",
                "wall_s":round(time.perf_counter()-start,6)}

def trial(raw,tag):
    began=time.perf_counter()
    result={
       "trial":tag,"original_sha256":digest(raw),"status":"UNKNOWN",
       "source_equivalence_independent":False,
       "source_model_independently_verified":False,
       "standard_original_veripb_verified":False,
       "newly_discovered_source_in_ATLAS9":tag=="original"}
    (OUT/(tag+".input.cnf")).write_bytes(raw)
    try:
        quotient,semantic=extract(raw)
        checked=verify(raw,quotient,semantic)
        if checked["status"]!="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED":
            raise ValueError("independent_semantic_rejection")
        result["source_equivalence_independent"]=True
        result["masked_AND_pairs"]=checked["masked_pairs_verified"]
        result["source_clause_count"]=checked["original_clauses"]
        result["virtual_xor_variables"]=checked["virtual_variables"]
        result["virtual_xor_rows"]=len(semantic["rows"])
        (OUT/(tag+".quotient.cnf")).write_bytes(quotient)
        (OUT/(tag+".semantic.json")).write_text(json.dumps(semantic,sort_keys=True,indent=2)+"\n")
        assignment=gauss_model(semantic["rows"],semantic["quotient_variables"])
        if assignment is not None:
            model={
               "source_sha256":digest(raw),
               "assignment":lift_model(semantic,assignment),
               "quotient_assignment":assignment}
            checked_sat=verify(raw,quotient,semantic,model)
            if checked_sat["SAT_status"]!="ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED":
                raise ValueError("model_rejected")
            (OUT/(tag+".original-SAT-model.json")).write_text(json.dumps(model,sort_keys=True)+"\n")
            result["status"]="SAT_MODEL_ORIGINAL_CNF_VERIFIED"
            result["source_model_independently_verified"]=True
            result["source_clauses_verified"]=checked_sat["source_model_all_clauses_checked"]
        else:
            result["GF2_quotient_contradiction"]=True
            # Proof construction itself has no authority for strict UNSAT.
            proof,meta=build_standard_original_proof(raw,quotient,semantic)
            (OUT/(tag+".proof-meta.json")).write_text(json.dumps(meta,sort_keys=True,indent=2)+"\n")
            accepted=check_standard_cnf(raw,proof,tag)
            result["status"]=accepted["status"]
            result["standard_original_veripb_verified"]=(
                 result["status"]=="STANDARD_VERIPB_VERIFIED_UNSAT")
            result["veripb_checker_seconds"]=accepted["wall_s"]
            result["veripb_checker_rc"]=accepted.get("returncode")
            result["veripb_proof_sha256"]=digest(proof.encode())
            result["veripb_proof_bytes"]=len(proof.encode())
    except (Unsupported,Invalid,ValueError,TypeError,KeyError,
            IndexError,MemoryError,UnicodeError,OverflowError) as e:
        result["status"]="UNKNOWN_UNSUPPORTED_OR_UNVERIFIED"
        result["reason"]=str(e)[:350]
    result["total_source_math_proof_check_wall_s"]=round(time.perf_counter()-began,6)
    (OUT/(tag+".trial.json")).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS9_TRIAL "+json.dumps(result,sort_keys=True),flush=True)
    return result

def main():
    assert SPEC["protocol"]=="DRNAS-ATLAS9-GBD-ORIGINAL-UNSAT105-3-20261121"
    assert FROZEN["source_gbd_id"]==SPEC["source_id"]
    assert FROZEN["source_isohash"]==SPEC["isohash"]
    assert FROZEN["selection_prespec_sha256"]==digest((HERE/"prespec.json").read_bytes())
    raw=SOURCE.read_bytes()
    assert digest(raw)==FROZEN["source_original_raw_sha256"]
    n,cls=parse(raw)
    assert n==FROZEN["source_dimensions"]["variables"]
    assert len(cls)==FROZEN["source_dimensions"]["clauses"]
    original=trial(raw,"original")
    runs=[original]
    for seed in SPEC["variants_seeds"]:
        altered,inverse,details=transform(n,cls,seed,rename=True,
                            flip=seed==SPEC["variants_seeds"][-1],shuffle=True)
        assert inverse and digest(altered)!=digest(raw)
        row=trial(altered,f"perm-{seed}")
        row["exact_inverse_original_clause_equivalence"]=inverse
        runs.append(row)
    # Forged source hash + modified source actual clause, with SHA updated,
    # both must be rejected independent of any existing GF2 contradiction.
    tamper={"wrong_source_SHA_rejected":False,
            "removed_clause_with_updated_SHA_rejected":False,
            "wrong_AND_orientation_rejected":False}
    if original["source_equivalence_independent"]:
        q=(OUT/"original.quotient.cnf").read_bytes()
        cert=json.loads((OUT/"original.semantic.json").read_text())
        forged=json.loads(json.dumps(cert))
        forged["source_sha256"]="0"*64
        try:verify(raw,q,forged)
        except Invalid:tamper["wrong_source_SHA_rejected"]=True
        altered=encoded(n,cls[1:])
        forged=json.loads(json.dumps(cert))
        forged["source_sha256"]=digest(altered)
        forged["source_clauses"]=len(cls)-1
        try:verify(altered,q,forged)
        except Invalid:tamper["removed_clause_with_updated_SHA_rejected"]=True
        pair=next((item for item in cert["tokens"] if len(item["members"])==2),None)
        if pair:
            forged=json.loads(json.dumps(cert))
            other=next(item for item in forged["tokens"] if item["id"]==pair["id"])
            other["true_if"][0]^=1
            try:verify(raw,q,forged)
            except Invalid:tamper["wrong_AND_orientation_rejected"]=True
    summary={
        "status":"COMPLETE",
        "source_gbd_id":SPEC["source_id"],"original_raw_sha256":digest(raw),
        "catalog_known_unsat_for_reporting_only":True,
        "source_vars":n,"source_clauses":len(cls),
        "original_semantic_recovered":original["source_equivalence_independent"],
        "original_status":original["status"],
        "original_veripb_strict":original["standard_original_veripb_verified"],
        "original_SAT_model_checked":original["source_model_independently_verified"],
        "permutations":len(runs)-1,
        "permutation_strict_Veripb":sum(x["standard_original_veripb_verified"] for x in runs[1:]),
        "permutation_valid_SAT":sum(x["source_model_independently_verified"] for x in runs[1:]),
        "tamper_controls":tamper,
        "trials":runs,
        "retrospective_known_family":"SAT05 original family with prior catalog UNSAT label; current detector/proof method frozen from Atlas8",
        "no_changed_main":True,
        "only_standard_veripb_on_exact_source_as_strict_unsat":True,
        "caveat":"No Kissat paired speed comparison in this audit; known source expected status not supplied to solver"
    }
    (OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
    print("ATLAS9_FINAL "+json.dumps({k:v for k,v in summary.items() if k!="trials"},sort_keys=True),flush=True)
    # A failed standard proof must make the audit conspicuously red.
    if (not original["original_veripb_strict"] or 
        sum(x["standard_original_veripb_verified"] for x in runs[1:])!=len(runs)-1):
        print("ATLAS9_STRICT_ORIGINAL_UNSAT_NOT_YET_PROVED",flush=True)
        raise SystemExit(2)
    if not all(tamper.values()):raise SystemExit(3)

if __name__=="__main__":
    main()
