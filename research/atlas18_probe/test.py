#!/usr/bin/env python3
"""ATLAS18 strict pilot on ATLAS17 original sources and ATLAS16 controls.

The public corpus was frozen by the previous step before this script starts.
Each UNSAT result requires fresh external VeriPB against the unchanged CNF.
Distinct original and synthetic cohorts are NEVER pooled for new generalization.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
FREEZE=ROOT/"atlas17_original_inputs/manifest.json"
MANIFEST=json.loads(FREEZE.read_text())
assert MANIFEST["status"]=="FROZEN_BEFORE_ANY_SOLVER"
assert MANIFEST["public_downloaded"]==6
OUT=ROOT/"atlas18_pilot_results";OUT.mkdir(exist_ok=True)
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
CPU=list(os.sched_getaffinity(0))[0]
CAP=15.0
def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
def restrictions():
    resource.setrlimit(resource.RLIMIT_FSIZE,(96*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_AS,(4*1024*1024*1024,)*2)
def call(cmd,remaining):
    if remaining<=0.02:return {"rc":124,"timeout":True,"text":""}
    try:
        r=subprocess.run([str(x) for x in cmd],capture_output=True,
            text=True,errors="replace",timeout=remaining,preexec_fn=restrictions)
    except subprocess.TimeoutExpired:
        return {"rc":124,"timeout":True,"text":""}
    return {"rc":r.returncode,"timeout":False,"text":r.stdout+"\n"+r.stderr}
def check_veripb(cnf,proof,deadline):
    r=call(["veripb","--cnf",cnf,proof],deadline-time.perf_counter())
    if r["timeout"]:return "CHECK_TIMEOUT"
    if r["rc"]==0 and "s VERIFIED UNSATISFIABLE" in r["text"]:return "VERIFIED"
    raise AssertionError("UNSAFE_ORIGINAL_VERIPB_REJECTED "+str(r)[-1000:])
def bench_subset(cnf,mode,out):
    out.mkdir(parents=True,exist_ok=True)
    proof=out/"proposed.pbp";meta=out/"proposed.json"
    proof.unlink(missing_ok=True)
    started=time.perf_counter();deadline=started+CAP
    r=call([sys.executable,ROOT/"research/atlas18_probe/hall_subset.py",
          "--cnf",cnf,"--mode",mode,"--proof",proof,"--meta",meta],
          deadline-time.perf_counter())
    (out/"producer.log").write_text(r["text"][-5500:])
    if r["timeout"]:status="UNKNOWN";reason="DETECTOR_TIMEOUT"
    elif r["rc"]==2:status="UNKNOWN";reason=r["text"][-580:]
    elif r["rc"]==0 and proof.exists():
        ck=check_veripb(cnf,proof,deadline)
        status="UNSAT_VERIFIED" if ck=="VERIFIED" else "UNKNOWN";reason=ck
    else:raise AssertionError("UNEXPECTED_SUBSET_GENERATOR_ERROR "+str(r)[-850:])
    elapsed=round(time.perf_counter()-started,6)
    if elapsed>CAP:status="UNKNOWN";reason="OVER_E2E_CAP"
    details=json.loads(meta.read_text()) if meta.is_file() else {}
    row={"mode":mode,"status":status,"reason":reason,"e2e_s":elapsed,
         "original_source_sha256":sha_file(cnf),
         "proof_bytes":proof.stat().st_size if proof.exists() else 0,
         "derived":details.get("derived_RUP_lemmata"),
         "graph_RUP_used":details.get("graph_RUP_used"),
         "xor_RUP_used":details.get("xor_RUP_used"),
         "ucp_RUP_used":details.get("ucp_RUP_used"),
         "groups":details.get("required_groups"),
         "capacity":details.get("capacity_resources")}
    save(out/"result.json",row)
    return row
def existing_hall(cnf,out):
    out.mkdir(parents=True,exist_ok=True)
    proof=out/"hall.pbp";meta=out/"hall.json"
    start=time.perf_counter();deadline=start+CAP
    r=call([sys.executable,ROOT/"research/atlas14_five/modes.py",
        "--mode","HALL_ONLY","--cnf",cnf,"--proof",proof,"--meta",meta],
        deadline-time.perf_counter())
    if r["timeout"]:status="UNKNOWN";reason="TIMEOUT"
    elif r["rc"]==2:status="UNKNOWN";reason=r["text"][-300:]
    elif r["rc"]==0 and proof.exists():
        verified=check_veripb(cnf,proof,deadline)
        status="UNSAT_VERIFIED" if verified=="VERIFIED" else "UNKNOWN"
        reason=verified
    else:raise AssertionError("UNEXPECTED_HALL_BASELINE_ERROR "+str(r)[-500:])
    row={"status":status,"reason":reason,
         "e2e_s":round(time.perf_counter()-start,6)}
    save(out/"result.json",row)
    return row
def router(cnf,out):
    started=time.perf_counter()
    r=call([sys.executable,ROOT/"research/atlas18_probe/router.py",
             "--cnf",cnf,"--out",out],CAP+2.0)
    if r["timeout"] or r["rc"]!=0:raise AssertionError("ATLAS18_ROUTER_CRASH "+str(r)[-700:])
    row=json.loads((out/"result.json").read_text())
    if sha_file(cnf)!=row["source_sha256"]:raise AssertionError("ROUTER_SOURCE_CHANGED")
    return row
def synthetic():
    spec=importlib.util.spec_from_file_location("atlas16_test_fixtures",
             ROOT/"research/atlas16_pilot/run.py")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    old=mod.sources()
    return [{"name":item["name"],"cohort":item["type"],
             "path":str(item["source"].relative_to(ROOT)),
             "sha256":item["sha256"]}
            for item in old if item["type"] in ("constructed_joint","constructed_SAT_control")]
def reference(name,cnf,out):
    out.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();deadline=start+CAP
    proof=out/"proposed.drat"
    binary=(ROOT/"kissat-src/build/kissat" if name=="Kissat4.0.4"
            else ROOT/"cadical-src/build/cadical")
    arg=[binary,"--no-binary",cnf,proof]
    r=call(arg,deadline-time.perf_counter())
    if r["timeout"]:status="UNKNOWN";reason="TIMEOUT"
    elif r["rc"]==20 and proof.exists():
        checked=call([ROOT/"drat-trim-src/drat-trim",cnf,proof,"-f"],
                     deadline-time.perf_counter())
        if checked["timeout"]:status="UNKNOWN";reason="CHECK_TIMEOUT"
        elif checked["rc"]==0 and "s VERIFIED" in checked["text"] and "s NOT VERIFIED" not in checked["text"]:
            status="UNSAT_VERIFIED";reason="DRAT_ACCEPTED"
        else:raise AssertionError("INVALID_REFERENCE_UNSAT_PROOF "+checked["text"][-400:])
    else:status="UNKNOWN";reason=f"NO_VERIFIED_UNSAT_OR_MODEL_rc={r['rc']}"
    elapsed=round(time.perf_counter()-start,6)
    if elapsed>CAP:status="UNKNOWN";reason="E2E_OVER_CAP"
    result={"status":status,"reason":reason,"e2e_s":elapsed}
    save(out/"result.json",result)
    return result
frozen=[{"name":s["name"],"cohort":s["cohort"],"path":s["path"],"sha256":s["sha256"]}
        for s in MANIFEST["sources"]]
frozen.extend(synthetic())
assert len(frozen)==16 and len({x["sha256"] for x in frozen})==16
save(OUT/"frozen_inputs.json",frozen)
records=[]
for case in frozen:
    cnf=ROOT/case["path"]
    assert sha_file(cnf)==case["sha256"]
    name=case["name"]
    row={"name":name,"cohort":case["cohort"],"source_sha256":case["sha256"]}
    for mode in ("DIRECT","GRAPH","XOR","JOINT","UCP","JOINT_UCP"):
        row[mode]=bench_subset(cnf,mode,OUT/"subsets"/name/mode)
    row["BASE_HALL"]=existing_hall(cnf,OUT/"baseline"/name)
    row["ROUTER"]=router(cnf,OUT/"router"/name)
    if row["JOINT"]["status"]=="UNSAT_VERIFIED":
        assert row["JOINT_UCP"]["status"]=="UNSAT_VERIFIED", "JOINT_PROOF_REGRESSION"
    row["UCP_HALL_SYNERGY"]=(row["UCP"]["status"]=="UNSAT_VERIFIED" and
         all(row[k]["status"]!="UNSAT_VERIFIED" for k in
            ("DIRECT","GRAPH","XOR","JOINT","BASE_HALL")))
    row["new_shared_synergy"]=(
        row["JOINT"]["status"]=="UNSAT_VERIFIED" and
        all(row[k]["status"]!="UNSAT_VERIFIED" for k in
            ("DIRECT","GRAPH","XOR","BASE_HALL")))
    if name=="php-mixed-2023":
        for comp in ("Kissat4.0.4","CaDiCaL2.1.3"):
            row[comp]=reference(comp,cnf,OUT/"reference"/name/comp)
    if case["cohort"]=="constructed_SAT_control":
        assert all(row[k]["status"]=="UNKNOWN" for k in
            ("DIRECT","GRAPH","XOR","JOINT","UCP","JOINT_UCP","BASE_HALL","ROUTER"))
    records.append(row)
    save(OUT/"summary.json",{"status":"IN_PROGRESS","rows":records})
    print("ATLAS18_TRIAL "+json.dumps({"name":name,"cohort":case["cohort"],
        "proofs":{k:row[k]["status"] for k in ("DIRECT","GRAPH","XOR","JOINT","UCP","JOINT_UCP","BASE_HALL","ROUTER")},
        "router":row["ROUTER"]["selected"],"true_shared_synergy":row["new_shared_synergy"],
        "UCP_HALL_synergy":row["UCP_HALL_SYNERGY"],
        "UCP_fact_count":row["UCP"].get("derived"),
        "UCP_RUP_used":row["UCP"].get("ucp_RUP_used"),
        "direct_details":{k:row["DIRECT"].get(k) for k in ("groups","capacity","e2e_s")},
        "reference":{k:row.get(k) for k in ("Kissat4.0.4","CaDiCaL2.1.3") if row.get(k)}},
        sort_keys=True),flush=True)
public=[r for r in records if r["cohort"]=="public_preselected"]
synth=[r for r in records if r["cohort"]=="constructed_joint"]
known=[r for r in records if r["cohort"]=="retrospective_known"]
summary={"status":"COMPLETE","total_cases":len(records),"public_originals":len(public),
         "known_retrospective":len(known),"generated_joint":len(synth),
         "SAT_controls":1,"public_new_subset_direct_verified":sum(
               x["DIRECT"]["status"]=="UNSAT_VERIFIED" for x in public),
         "public_previous_hall_verified":sum(
               x["BASE_HALL"]["status"]=="UNSAT_VERIFIED" for x in public),
         "public_router_verified":sum(
               x["ROUTER"]["status"]=="UNSAT_VERIFIED" for x in public),
         "public_new_shared_synergy":sum(x["new_shared_synergy"] for x in public),
         "public_ucp_hall_synergy":sum(x["UCP_HALL_SYNERGY"] for x in public),
         "constructed_joint_new_shared_synergy":sum(x["new_shared_synergy"] for x in synth),
         "no_main_changes":True,"no_CDCL_fallback":True,
         "external_standard_original_proofs_only":True,
         "single_logical_CPU":CPU,"cap_per_arm_s":CAP,
         "rows":records}
save(OUT/"summary.json",summary)
print("ATLAS18_FINAL "+json.dumps({k:v for k,v in summary.items() if k!="rows"},
    sort_keys=True),flush=True)
