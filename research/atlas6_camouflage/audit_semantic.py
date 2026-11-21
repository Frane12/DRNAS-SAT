#!/usr/bin/env python3
"""ATLAS6 independent semantic masked-XOR benchmark on frozen real ID8.

SOURCE-ONLY: detector sees only raw source bytes, NEVER filename or known
SAT status. Exact unchanged historic raw SHA is checked by harness only.
3 predetermined bijective variants are recreated and independently solved.
All source assignment claims must pass exhaustive small truth table checks
of each local masked relation and original-source SAT model verification.
"""
import hashlib,json,os,time,itertools,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
from atlas import parse,encoded,transform
from semantic_and_xor import extract,gauss_model,lift_model,Unsupported
from check_semantic import verify, Invalid
OUT=ROOT/"atlas6_semantic_results"
OUT.mkdir(exist_ok=True)
SOURCE=ROOT/"atlas6_source/id08.cnf"
EXPECTED="f9dcbbbcb2abc290439c21978d04cdc44efffbed9b4e5cdee96dd63856a5a156"
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
def digest(v):return hashlib.sha256(v).hexdigest()

def run_case(raw,name):
    began=time.perf_counter()
    p=OUT/(name+".cnf")
    p.write_bytes(raw)
    virtual,cert=extract(raw)
    vmodel=gauss_model(cert["rows"],cert["quotient_variables"])
    assert vmodel is not None,("GF2_CONTRADICTS_KNOWN_MODEL",name)
    model={"source_sha256":digest(raw),
           "quotient_assignment":vmodel,
           "assignment":lift_model(cert,vmodel)}
    independent=verify(raw,virtual,cert,model)
    assert independent["status"]=="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED"
    assert independent["SAT_status"]=="ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED"
    (OUT/(name+".quotient.cnf")).write_bytes(virtual)
    (OUT/(name+".certificate.json")).write_text(json.dumps(cert,sort_keys=True,indent=2)+"\n")
    (OUT/(name+".model.json")).write_text(json.dumps(model,sort_keys=True)+"\n")
    (OUT/(name+".verifier.json")).write_text(json.dumps(independent,sort_keys=True,indent=2)+"\n")
    row={"tag":name,"status":"ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED",
         "source_sha256":digest(raw),"source_variables":cert["source_vars"],
         "source_clauses":cert["source_clauses"],
         "AND_pair_count":cert["camouflaged_AND_pairs"],
         "virtual_variables":cert["quotient_variables"],
         "source_truth_tables":cert["source_supports"],
         "recovered_GF2_equations":len(cert["rows"]),
         "quotient_clauses":cert["quotient_clauses"],
         "virtual_masked_variable_model_verified":True,
         "full_original_clause_model_verified":True,
         "math_elapsed_including_independent_checks_s":round(time.perf_counter()-began,6)}
    (OUT/(name+".summary.json")).write_text(json.dumps(row,sort_keys=True,indent=2)+"\n")
    print("ATLAS6_VERIFIED_TRIAL "+json.dumps(row,sort_keys=True),flush=True)
    return row,(virtual,cert,model)

raw=SOURCE.read_bytes()
assert digest(raw)==EXPECTED
nv,clauses=parse(raw)
assert nv==352 and len(clauses)==2492
rows=[]
first,art=run_case(raw,"original")
rows.append(first)
v,certificate,model=art

# Independent negative control with source SHA updated: changing one full
# source assignment clause must break the exact local truth-table proof.
altered=encoded(nv,clauses[1:])
changed=json.loads(json.dumps(certificate))
changed["source_sha256"]=digest(altered)
changed["source_clauses"]=len(clauses)-1
try:verify(altered,v,changed)
except Invalid:source_clause_rejected=True
else:raise AssertionError("SOURCE_CLAUSE_TAMPER_ACCEPTED")
# Wrong signed orientation for AND in one token must be rejected.
incorrect=json.loads(json.dumps(certificate))
pair=next(t for t in incorrect["tokens"] if len(t["members"])==2)
pair["true_if"][0]^=1
try:verify(raw,v,incorrect)
except Invalid:orientation_rejected=True
else:raise AssertionError("WRONG_AND_ORIENTATION_ACCEPTED")
# Forge a model assignment bit (search deterministic first failing bit).
bad_rejected=False
for variable in range(1,nv+1):
    forged=json.loads(json.dumps(model))
    forged["assignment"][variable]=not forged["assignment"][variable]
    try:verify(raw,v,certificate,forged)
    except Invalid:
        bad_rejected=True;break
assert bad_rejected
# Source SHA must be bound even if contents happen to be logically equivalent.
badsha=json.loads(json.dumps(certificate))
badsha["source_sha256"]="0"*64
try:verify(raw,v,badsha)
except Invalid:sha_rejected=True
else:raise AssertionError("FORGED_SOURCE_SHA_ACCEPTED")

for seed in (101,202,303):
    variant,bijective,method=transform(nv,clauses,seed,
        rename=True,flip=(seed!=101),shuffle=True)
    assert bijective and digest(variant)!=EXPECTED
    row,trialart=run_case(variant,"variant"+str(seed))
    row["known_exact_inverse_clause_equivalence"]=bijective
    row["seed"]=seed
    rows.append(row)

summary={
  "status":"PASS","original_sha256":EXPECTED,
  "original_vars":nv,"original_clauses":len(clauses),
  "original_source":first,
  "controlled_variants":3,
  "controlled_variant_results":[{"seed":r["seed"],"status":r["status"],
        "AND_pairs":r["AND_pair_count"],
        "GF2_equations":r["recovered_GF2_equations"],
        "model_verified":r["full_original_clause_model_verified"]}
        for r in rows[1:]],
  "all_four_original_source_model_verified":all(r["full_original_clause_model_verified"] for r in rows),
  "source_clause_mutation_with_updated_SHA_rejected":source_clause_rejected,
  "wrong_signed_AND_orientation_rejected":orientation_rejected,
  "wrong_model_rejected":bad_rejected,
  "forged_source_SHA_rejected":sha_rejected,
  "independent_full_truth_table_checks":sum(r["source_truth_tables"] for r in rows),
  "full_original_clause_model_checks":sum(r["source_clauses"] for r in rows),
  "expected_catalog_status":"SAT_PRIOR_KNOWN_NOT_USED_BY_DETECTOR",
  "scientific_scope":"retrospective source-only recovery of AND-camouflaged GF2 in SAT05-origin benchmark",
  "not_general_unsat_solver":True,"not_new_blind_formula":True,"main_untouched":True
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("ATLAS6_SEMANTIC_FINAL "+json.dumps(summary,sort_keys=True),flush=True)
