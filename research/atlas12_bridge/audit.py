#!/usr/bin/env python3
"""ATLAS12 strict source-coupled GRAPH -> HALL/PCMAX modular proof audit.

Retrospective source GRAPH-K11 and PCMAX orig05/15; small deterministic K4
generated SAT/UNSAT controls; K4 variable/clause permutation controls.
No model/certificate accepted solely from detector output. Successful
UNSAT ONLY after original-CNF Veripb 3.0.2 external check.
"""
from __future__ import annotations
import hashlib,json,os,random,subprocess,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas12_results";OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
from atlas import parse as source_parse,encoded,transform
from bridge import choose,graph_to_hall
from check_php_partition import check as independent_hall_check
from emit_veripb_source_clique import emit as pcmax_emit
from emit_veripb import compile_source as existing_graph_proof
from emit_veripb import Unsupported as GraphUnsupported
from selftest import make_source,model_ok

CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
def sha(raw):return hashlib.sha256(raw).hexdigest()
def run_checker(cnf,pbp,label,limit=25):
    try:
        p=subprocess.run(["taskset","-c",str(CPU),"veripb","--cnf",str(cnf),str(pbp)],
                         capture_output=True,text=True,timeout=limit)
        log=p.stdout+"\n"+p.stderr
        (OUT/(label+".veripb.log")).write_text(log)
        return p.returncode==0 and "s VERIFIED UNSATISFIABLE" in log
    except subprocess.TimeoutExpired:
        (OUT/(label+".veripb.log")).write_text("UNKNOWN_TIMEOUT")
        return False

def one(cnf,label,mode):
    started=time.perf_counter()
    raw=cnf.read_bytes()
    certificate,meta=choose(raw,cnf,mode)
    row={"label":label,"mode":mode,"source_sha256":sha(raw),
         "source_bytes":len(raw),"status":"UNKNOWN","standard_veripb_verified":False,
         "source_independent_checked":False,
         "legacy_solution_used_as_input":False,
         "detector":meta}
    if certificate is None:
        row["reason"]=meta.get("status","NO_CERTIFICATE")
    else:
        assert certificate["source_sha256"]==sha(raw)
        cert_path=OUT/(label+".hall-certificate.json")
        cert_path.write_text(json.dumps(certificate,indent=2,sort_keys=True)+"\n")
        checked=independent_hall_check(cnf,cert_path)
        assert checked["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED"
        row["source_independent_checked"]=True
        row["checked"]={k:v for k,v in checked.items() if k not in ("sha256",)}
        proof_path=OUT/(label+".proof.pbp")
        meta_pb=pcmax_emit(cnf,cert_path,proof_path)
        assert meta_pb["source_sha256"]==sha(raw)
        accepted=run_checker(cnf,proof_path,label)
        if accepted:
            row["status"]="STANDARD_VERIPB_VERIFIED_UNSAT"
            row["standard_veripb_verified"]=True
        else:
            row["status"]="UNKNOWN_EXTERNAL_VERIPB_REJECTED_OR_TIMEOUT"
        row["proof_bytes"]=meta_pb["proof_bytes"]
        row["proof_sha256"]=meta_pb["proof_sha256"]
        row["proof_pol_steps"]=meta_pb["proof_pol_steps"]
    row["e2e_s"]=round(time.perf_counter()-started,6)
    (OUT/(label+".result.json")).write_text(json.dumps(row,sort_keys=True,indent=2)+"\n")
    print("ATLAS12_BRIDGE_TRIAL "+json.dumps({
       "label":label,"mode":mode,"status":row["status"],
       "standard_veripb_verified":row["standard_veripb_verified"],
       "source_independent_checked":row["source_independent_checked"],
       "e2e_s":row["e2e_s"],
       "demand":row.get("checked",{}).get("required_groups"),
       "capacity":row.get("checked",{}).get("capacity_resources")
       },sort_keys=True),flush=True)
    return row

def main():
    records=[]
    k=3;n=4;edges={(i,j) for i in range(n) for j in range(i+1,n)}
    original,coord=make_source(k,n,edges,5511,shuffle_ids=True)
    orig=OUT/"K4-UNSAT-original.cnf";orig.write_bytes(original)
    records.append(one(orig,"K4-UNSAT-bridge","GRAPH_HALL_EO"))
    assert records[-1]["standard_veripb_verified"],"K4 original standard proof failed"

    # Independent source-reconstruction for two true signed-ID renamings
    # (NO polarity flip: the source clique/positive-ALO certificate does not
    # support arbitrary signed source ALO groups yet; safe UNKNOWN for flips).
    nvar,clauses=source_parse(original)
    for seed in (101,202):
        changed,equivalence,_=transform(nvar,clauses,seed,rename=True,flip=False,shuffle=True)
        assert equivalence
        path=OUT/(f"K4-UNSAT-var{seed}.cnf")
        path.write_bytes(changed)
        records.append(one(path,f"K4-var{seed}","GRAPH_HALL_EO"))
        assert records[-1]["standard_veripb_verified"],"renamed K4 failed"

    # SAT K4 with one missing same-color conflict: 0 and 1 can share color0,
    # while vertices 2 and 3 use colors 1 and 2. Both original CNF model and
    # refusal of the source-backed UNSAT bridge are independently checked.
    original_rows=source_parse(original)[1]
    hole=frozenset((-coord[0,0],-coord[1,0]))
    trimmed=[c for c in original_rows if frozenset(c)!=hole]
    assert len(trimmed)==len(original_rows)-1
    raw_sat=encoded(nvar,trimmed)
    SATpath=OUT/"K4-SAT-minus-1-mutex.cnf"
    SATpath.write_bytes(raw_sat)
    model={coord[v,c]:(c==(0 if v in (0,1) else v-1))
           for v in range(4) for c in range(3)}
    assert model_ok(raw_sat,model)
    controls={"SAT_model_original_clauses_checked":len(trimmed),
              "SAT_one_essential_mutex_removed":True}
    try:
        records.append(one(SATpath,"K4-SAT-minus-1","GRAPH_HALL_EO"))
        controls["SAT_structural_no_false_UNSAT"]=not records[-1]["standard_veripb_verified"]
    except GraphUnsupported:
        controls["SAT_structural_no_false_UNSAT"]=True
    assert controls["SAT_structural_no_false_UNSAT"]
    # Forge a valid-looking source/counter claim with the CORRECT NEW SHA.
    cert=json.loads((OUT/"K4-UNSAT-bridge.hall-certificate.json").read_text())
    cert["source_sha256"]=sha(raw_sat)
    cert["source_clauses"]=len(trimmed)
    forged=OUT/"K4-SAT-forged-updated-SHA.json"
    forged.write_text(json.dumps(cert,sort_keys=True)+"\n")
    try:independent_hall_check(SATpath,forged)
    except ValueError:controls["forged_premise_with_updated_SHA_rejected"]=True
    else:controls["forged_premise_with_updated_SHA_rejected"]=False
    assert controls["forged_premise_with_updated_SHA_rejected"]
    print("ATLAS12_SAFETY "+json.dumps(controls,sort_keys=True),flush=True)

    # Retrospective original graph formula from repository, unchanged source.
    graph_original=ROOT/"evidence/graph-k11/original.cnf"
    records.append(one(graph_original,"original-graph-K11","GRAPH_HALL_EO"))

    # Two existing original PCMAX models: we evaluate the *direct* source-only
    # clique detector and never confuse UNKNOWN with failed proof. Independently
    # verify the original stored PCMAX weighted proof as an independent
    # positive regression, but it is NOT a cross-module bridge result.
    existing_pcmax_verified=0
    for id in ("05","15"):
        source=ROOT/f"evidence/pcmax-weighted2/{id}/original.cnf"
        row=one(source,f"pcmax-{id}-direct","PCMAX_DIRECT")
        records.append(row)
        known_pbp=ROOT/f"evidence/pcmax-weighted2/{id}/weighted.pbp"
        if known_pbp.is_file():
            accepted=run_checker(source,known_pbp,"pcmax-"+id+"-legacy-regression")
            existing_pcmax_verified+=int(accepted)
            print("ATLAS12_PREVIOUS_PCMAX_PROOF_REGRESSION "+json.dumps({
                 "id":id,"external_original_VERIPB_accepted":accepted,
                 "existing_pre_ATLAS12_pbp_sha256":sha(known_pbp.read_bytes())},sort_keys=True),flush=True)

    verified=[r["label"] for r in records if r["standard_veripb_verified"]]
    unknown=[r["label"] for r in records if not r["standard_veripb_verified"]]
    summary={
        "status":"COMPLETE",
        "source_bridge_kind":"GRAPH source clique -> HALL/PCMAX verified demand capacity -> original standard VeriPB",
        "known_math_not_new_theorem":True,
        "bridge_proofs_verified":len(verified),
        "bridge_verified_labels":verified,
        "bridge_unknown_labels":unknown,
        "source_independent_checked":sum(r["source_independent_checked"] for r in records),
        "synthetic_K4_standard_proofs":sum(r["standard_veripb_verified"] for r in records if r["label"].startswith("K4-") and "SAT-minus" not in r["label"]),
        "real_original_graph_K11_verified":next(r for r in records if r["label"]=="original-graph-K11")["standard_veripb_verified"],
        "previous_PCMax_stored_proof_regression_accepted":existing_pcmax_verified,
        "controls":controls,
        "no_false_UNSAT":True,
        "no_main_change":True,
        "only_standard_veripb_as_final_UNSAT":True,
        "not_yet_joint_unique_gain":"This joins existing verified GRAPH candidate fact with existing HALL/PCMAX proof rules. It does not establish solving cases neither prior module alone could solve.",
        "comparisons_not_claimed":"No fair paired Kissat performance trial in ATLAS12."
    }
    (OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
    print("ATLAS12_FINAL "+json.dumps(summary,sort_keys=True),flush=True)
    assert summary["synthetic_K4_standard_proofs"]==3
    assert summary["real_original_graph_K11_verified"],"original graph K11 bridge unknown: inspect source"
    assert summary["previous_PCMax_stored_proof_regression_accepted"]==2
    assert all(controls.values())

if __name__=="__main__":main()
