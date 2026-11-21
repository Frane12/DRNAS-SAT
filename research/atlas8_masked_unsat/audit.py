#!/usr/bin/env python3
"""Fixed original-CNF masked XOR SAT/UNSAT evidence, no cherry picking.

Three *constructed* source graph structures (K4, triangular prism, K3,3),
two frozen seeds, one SAT and one mathematically odd-charge UNSAT for each.
For each UNSAT, only external VeriPB 3.0.2 on exact original qualifies.
All satisfiable controls carry original-source checked SAT models. Three
source-equivalent permuted UNSAT controls test reconstruction robustness.

No claim of new original competition UNSAT proof; these are proof-transport
and source-equivalence regression controls, not benchmark comparisons.
"""
import hashlib,json,os,sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas8_out"
OUT.mkdir(exist_ok=True)
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/atlas6_camouflage"))
from atlas import parse,transform,encoded
from check_semantic import verify,Invalid
from proof import make_case,build_standard_original_proof
from semantic_and_xor import extract,gauss_model

cpu=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{cpu})
def h(x):return hashlib.sha256(x).hexdigest()
def check_veripb(source,proof,tag,accepted=True):
    cnf=OUT/(tag+".cnf");pbp=OUT/(tag+".pbp")
    cnf.write_bytes(source);pbp.write_text(proof)
    t=time.perf_counter()
    r=subprocess.run(["taskset","-c",str(cpu),"veripb","--cnf",str(cnf),str(pbp)],
      text=True,capture_output=True,timeout=25)
    wall=time.perf_counter()-t
    (OUT/(tag+".veripb.log")).write_text(r.stdout+"\n"+r.stderr)
    ok=r.returncode==0 and "s VERIFIED UNSATISFIABLE" in (r.stdout+r.stderr)
    if ok!=accepted:raise AssertionError((tag,"external_veripb_result",r.returncode,
                             (r.stdout+r.stderr)[-800:]))
    return wall
results=[]
for kind in ("k4","prism","k33"):
    for seed in (111,222):
        for mode in ("sat","unsat"):
            tag=f"{kind}-{seed}-{mode}"
            raw,q,cert,metadata,proof,proofmeta=make_case(kind,seed,mode=="unsat")
            full=verify(raw,q,cert)
            assert full["status"]=="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED"
            folder=OUT/tag;folder.mkdir(exist_ok=True)
            (folder/"original.cnf").write_bytes(raw)
            (folder/"quotient.cnf").write_bytes(q)
            (folder/"source-certificate.json").write_text(json.dumps(cert,indent=2,sort_keys=True)+"\n")
            if mode=="unsat":
                sec=check_veripb(raw,proof,tag)
                (folder/"original.veripb.pbp").write_text(proof)
                proofstatus="ORIGINAL_UNSAT_EXTERNAL_VERIPB_VERIFIED"
            else:
                sec=0
                model=proofmeta["model"]
                independent=verify(raw,q,cert,model)
                assert independent["SAT_status"]=="ORIGINAL_SAT_MODEL_INDEPENDENTLY_VERIFIED"
                (folder/"original.model.json").write_text(json.dumps(model,sort_keys=True)+"\n")
                proofstatus="ORIGINAL_SAT_MODEL_SOURCE_VERIFIED"
            result={
                "kind":kind,"seed":seed,"mode":mode,"source_sha256":h(raw),
                "original_vars":metadata["source_vars"],"original_clauses":metadata["source_clauses"],
                "source_tables_checked":full["source_truth_tables_checked"],
                "camouflaged_tokens":full["masked_pairs_verified"],
                "virtual_xor_rows":len(cert["rows"]),"status":proofstatus,
                "veripb_wall_s":round(sec,6)}
            results.append(result)
            print("ATLAS8_CONTROL "+json.dumps(result,sort_keys=True),flush=True)

# Re-check the source-mutation safety of original mathematical premises, even
# when a malicious certificate recomputes the changed CNF SHA.
original,q,cert,meta,proof,pmeta=make_case("k4",111,True)
_,c=parse(original)
mutated=encoded(meta["source_vars"],c[1:])
forged=json.loads(json.dumps(cert))
forged["source_sha256"]=h(mutated)
forged["source_clauses"]=len(c)-1
rejections=0
try:verify(mutated,q,forged)
except Invalid:rejections+=1
else:raise AssertionError("SOURCE_PREMISE_MUTATION_ACCEPTED")
check_veripb(mutated,proof,"source-mutated-proof",accepted=False)
rejections+=1
# Test three reversible source permutations (original exact source first,
# then perform source-only detector, source verification, external PBP).
nv,clauses=parse(original)
variant_proofs=[]
for seed in (301,402,503):
    changed,equivalent,variant_meta=transform(nv,clauses,seed,
         rename=True,flip=(seed!=301),shuffle=True)
    assert equivalent and changed!=original
    quotient,certificate=extract(changed)
    assert verify(changed,quotient,certificate)["status"]=="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED"
    assert gauss_model(certificate["rows"],certificate["quotient_variables"]) is None
    proof,proof_meta=build_standard_original_proof(changed,quotient,certificate)
    sec=check_veripb(changed,proof,f"variant-{seed}")
    variant_proofs.append({"seed":seed,"source_sha256":h(changed),
          "exact_inverse_clause_equivalence":equivalent,
          "veripb_proof_sha256":h(proof.encode()),
          "proof_bytes":len(proof.encode()),"veripb_wall_s":round(sec,6),
          "status":"ORIGINAL_UNSAT_EXTERNAL_VERIPB_VERIFIED"})
    print("ATLAS8_VARIANT "+json.dumps(variant_proofs[-1],sort_keys=True),flush=True)
summary={
  "status":"PASS","scope":"Synthetic SOURCE proof compiler controls only, not unseen original benchmark",
  "fixed_graphs":["k4","prism","k33"],"seeds":[111,222],
  "originals_unsat_veripb_verified":sum(r["mode"]=="unsat" for r in results),
  "originals_sat_models_verified":sum(r["mode"]=="sat" for r in results),
  "permuted_unsat_veripb_verified":len(variant_proofs),
  "source_mutation_proof_rejections":rejections,
  "cases":results,"variants":variant_proofs,
  "source_provenance":"Generated mathematically equivalent AND-masked parity constraints",
  "veripb_checker_version":"3.0.2",
  "all_unsat_evidence_on_exact_original_cnf":True,
  "all_sat_evidence_independently_checked":True,
  "benchmark_claims":False,"main_untouched":True
}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS8_FINAL "+json.dumps({k:v for k,v in summary.items() if k not in ("cases","variants")},sort_keys=True),flush=True)
