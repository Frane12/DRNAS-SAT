#!/usr/bin/env python3
"""Targeted ID8 old-to-new test; source-only inverse and exact SAT model check.

The source file is the same historical GBD source and must match its prior
raw SHA, no substitutions or outcome-guided choice. 3 deterministically
permuted variants follow, each proving known clause-bijection equivalence.
All computed SAT models independently checked on original variant CNFs.
On unsupported sources, UNKNOWN is a valid honest result.
"""
import hashlib,json,os,sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas6_results"
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/structure_atlas3"))
from atlas import parse,transform
from source_facts import derive as shallow_derive
from check_facts import check as shallow_check
from check_roundtrip import check as independent_roundtrip, check_sat,Invalid
from inverse import recover as inverse_recover
from solve_quotient import solve
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
SOURCE=ROOT/"atlas6_source"/"id08.cnf"
EXPECTED="f9dcbbbcb2abc290439c21978d04cdc44efffbed9b4e5cdee96dd63856a5a156"
GBD="b5431f41e3264c64508c30da215c69c6"

def h(raw):return hashlib.sha256(raw).hexdigest()
assert h(SOURCE.read_bytes())==EXPECTED
original=SOURCE.read_bytes()
nv,cs=parse(original)
assert len(cs)==2492 and nv==352
name="original"
runs=[]
def evaluate(raw,tag,expected_sha=None):
    t=time.perf_counter()
    path=OUT/(tag+".cnf")
    path.write_bytes(raw)
    q,certificate=inverse_recover(raw,max_pairs=500)
    quot=OUT/(tag+".quotient.cnf")
    quot.write_bytes(q)
    certpath=OUT/(tag+".and-masking-cert.json")
    certpath.write_text(json.dumps(certificate,indent=2,sort_keys=True)+"\n")
    proven=independent_roundtrip(raw,q,certificate)
    assert proven["status"]=="SOURCE_MASKING_EQUIVALENCE_VERIFIED"
    shallow=shallow_derive(raw)
    shallow_check(raw,shallow)
    baseline_xor=len(shallow["complete_xor_rows"])
    result,model=solve(raw,q,certificate)
    result.update({"tag":tag,"source_sha256":h(raw),
        "plain_XOR_rows_before_unmasking":baseline_xor,
        "AND_pair_claims_independently_verified":proven["checked_exact_AND_reexpansion_steps"],
        "end_to_end_source_inclusive_wall_s":round(time.perf_counter()-t,6)})
    if model:
        (OUT/(tag+".SATmodel.json")).write_text(json.dumps(model,sort_keys=True)+"\n")
        assert check_sat(raw,model)["status"]=="ORIGINAL_CNFSAT_MODEL_VERIFIED"
    (OUT/(tag+".summary.json")).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("ATLAS6_TRIAL "+json.dumps(result,sort_keys=True),flush=True)
    return result,certificate,q,model

result,certificate,quot,model=evaluate(original,"id08-original")
runs.append(result)
# Safety controls applied regardless of final solver status.
bad=json.loads(json.dumps(certificate))
bad["source_sha256"]="0"*64
try:independent_roundtrip(original,quot,bad)
except Invalid:sha_reject=True
else:raise AssertionError("FORGED_SHA_CERTIFICATE_ACCEPTED")
pair_reject=None
if certificate["pair_steps"]:
    bad=json.loads(json.dumps(certificate))
    bad["pair_steps"][0]["b"]=bad["pair_steps"][0]["a"]
    try:independent_roundtrip(original,quot,bad)
    except Invalid:pair_reject=True
    else:raise AssertionError("TAMPER_PAIR_CERTIFICATE_ACCEPTED")
# Change one exact original clause, claim the new SHA in the certificate,
# ensure it is NOT possible to reuse old quotient as a proof of equivalence.
if certificate["pair_steps"]:
    changed=original.splitlines()
    index=next(i for i,x in enumerate(changed) if x.startswith(b"p cnf "))
    _,old_clauses=parse(original)
    altered=old_clauses[1:]
    alt=Path(OUT/"id08-removed-source-clause.cnf")
    alt.write_bytes((f"p cnf {nv} {len(altered)}\n"+
        "".join(" ".join(map(str,c))+" 0\n" for c in altered)).encode())
    bad=json.loads(json.dumps(certificate))
    bad["source_sha256"]=h(alt.read_bytes())
    bad["original_clauses"]=len(altered)
    try:independent_roundtrip(alt.read_bytes(),quot,bad)
    except Invalid:removed_reject=True
    else:raise AssertionError("SOURCE_CLAUSE_DELETION_ACCEPTED")
else:removed_reject=None
# Variations do NOT run with an original SAT label; the detector is blind
# to it, and independently rebuilds quotient & SAT model each time.
for seed in (101,202,303):
    alternative,known_equiv,method=transform(nv,cs,seed,
        rename=True,flip=(seed!=101),shuffle=True)
    assert known_equiv
    trial,_,_,_=evaluate(alternative,"id08-variant"+str(seed))
    trial["exact_inverse_equivalence_to_original"]=True
    trial["seed"]=seed
    runs.append(trial)

summary={
  "status":"PASS",
  "source":"SAT_COMPETITION_2025_ID8_SOURCE_FROZEN",
  "expected_sha256":EXPECTED,
  "original_vars":nv,"original_clauses":len(cs),
  "original_plain_XOR_rows":runs[0]["plain_XOR_rows_before_unmasking"],
  "original_recovered_AND_pairs":runs[0]["certified_masking_steps"],
  "original_quotient_clauses":runs[0]["quotient_clauses"],
  "original_quotient_complete_XOR_rows":runs[0]["source_xor_rows"],
  "original_source_model_verified":runs[0]["original_model_independently_checked"],
  "original_status":runs[0]["status"],
  "independent_roundtrip_original":True,
  "controlled_variants":3,
  "controlled_variant_SAT_models_verified":sum(r["original_model_independently_checked"] for r in runs[1:]),
  "controlled_variant_inverse_equivalence":3,
  "forged_SHA_rejected":sha_reject,
  "forged_pair_rejected":pair_reject,
  "deleted_source_clause_rejected_even_with_new_SHA":removed_reject,
  "newly_solved_blind_formula_claimed":False,
  "prior_catalog_satisfiable_known":True,
  "math_method":"recognized AND camouflage quotient then source XOR GF(2)",
  "no_UNSAT_claim":True,
  "critical":[],
  "no_main_change":True,
  "novelty_scope":"research regression on known SAT Competition 2005-origin SAT example"}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("ATLAS6_FINAL "+json.dumps(summary,sort_keys=True),flush=True)
