#!/usr/bin/env python3
"""ATLAS19 source-frozen real clique-coloring proof router and regression.

Target is the preselected public 2025 original from ATLAS17. 2 paired
repetitions, 15s strictly per attempt including independent VeriPB/DRAT checks.
Serial one-logical-CPU, source SHA checked before/after; other source controls
are independent regression runs. No CDCL fallback in DRNAS router.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas19_results"
OUT.mkdir(parents=True,exist_ok=True)
MANIFEST=json.loads((ROOT/"atlas17_original_inputs/manifest.json").read_text())
assert MANIFEST["status"]=="FROZEN_BEFORE_ANY_SOLVER"
assert MANIFEST["public_downloaded"]==6 and not MANIFEST["failures"]
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
CAP=15.0
MAX_PROOF_BYTES=256*1024*1024
TARGET_SHA="92d69a56836e0abbc2381d8ad1f00d5b409e4627685080e869c4432b8de36188"
BINS={"Kissat4.0.4":ROOT/"kissat-src/build/kissat",
      "CaDiCaL2.1.3":ROOT/"cadical-src/build/cadical"}
def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(131072),b""):
            digest.update(chunk)
    return digest.hexdigest()
def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(4*1024*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_PROOF_BYTES,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(20,23))
def run(cmd,deadline,output):
    before=time.perf_counter()
    remain=deadline-before
    if remain<=.03:
        return {"status":"TIMEOUT","reason":"END_TO_END_DEADLINE","elapsed":0}
    try:
        p=subprocess.run([str(x) for x in cmd],
               capture_output=True,text=True,errors="replace",
               timeout=remain,preexec_fn=limits)
        stdout=p.stdout+"\n"+p.stderr
        output.write_text(output.read_text()+f"\nCOMMAND={str(cmd)}\nRC={p.returncode}\n"+stdout[-5000:])
        return {"status":"RETURNED","rc":p.returncode,
                "elapsed":round(time.perf_counter()-before,6),
                "tail":stdout[-1000:]}
    except subprocess.TimeoutExpired:
        output.write_text(output.read_text()+f"\nCOMMAND={str(cmd)}\nTIMEOUT\n")
        return {"status":"TIMEOUT","reason":"PROCESS_TIMEOUT",
                "elapsed":round(time.perf_counter()-before,6)}
def proof_checker(source,proof,deadline,log,kind):
    args=(["veripb","--cnf",source,proof] if kind=="PBP" else
          [ROOT/"drat-trim-src/drat-trim",source,proof,"-f"])
    ck=run(args,deadline,log)
    if ck["status"]!="RETURNED":
        return "UNKNOWN_CHECKER_TIMEOUT"
    if ck["rc"]==0 and (
            "s VERIFIED UNSATISFIABLE" in ck["tail"] if kind=="PBP" else
            "s VERIFIED" in ck["tail"] and "s NOT VERIFIED" not in ck["tail"]):
        return "ACCEPTED"
    raise RuntimeError("EXTERNAL_ORIGINAL_PROOF_INVALID "+kind+" "+str(ck)[-650:])
def router_arm(source,expected,arm,rep):
    dest=OUT/"paired"/arm/f"rep-{rep}"
    dest.mkdir(parents=True,exist_ok=True)
    log=dest/"trial.log"
    log.write_text("")
    start=time.perf_counter()
    script=(ROOT/"research/atlas18_probe/router.py" if arm=="ATLAS19" else
            ROOT/"research/atlas19_clique/router_atlas18_frozen.py")
    args=[sys.executable,script,"--cnf",source,"--out",dest/"out"]
    x=run(args,start+CAP,log)
    if x["status"]!="RETURNED" or x["rc"]!=0:
        raise RuntimeError("ROUTER_EXECUTION_FAILURE "+str(x))
    result=json.loads((dest/"out"/"result.json").read_text())
    assert result["source_sha256"]==expected and result["source_original_not_modified"]
    assert result["CDCL_fallback_called"] is False
    if result["status"]=="UNSAT_VERIFIED":
        proof=dest/"out"/"result.pbp"
        assert proof.is_file() and sha(proof)==result["selected"]["proof_sha256"]
        assert (result["selected"]["proof_bytes"]==proof.stat().st_size and
                result["selected"]["stage"]=="CLIQUE_COLOR_EXTENDED_PBP") if arm=="ATLAS19" else True
        # Existing router already ran external VeriPB with its same E2E cap.
        # Independently rerun once more OUTSIDE the timed score and label it replay.
        replay_log=dest/"replay.log";replay_log.write_text("")
        result["independent_replay"]=proof_checker(source,proof,
                          time.perf_counter()+18,replay_log,"PBP")
        if result["independent_replay"]!="ACCEPTED":
            raise RuntimeError("INDEPENDENT_REPLAY_FAILED")
    if sha(source)!=expected:raise RuntimeError("ORIGINAL_SOURCE_CHANGED")
    row={"arm":arm,"rep":rep,"status":result["status"],
         "e2e_s":result["router_E2E_s"],
         "selected":result["selected"],
         "source_sha256":expected,
         "gate":result.get("clique_color_source_gate"),
         "stages":result["stages"],
         "external_replay":result.get("independent_replay")}
    dump(dest/"trial.json",row)
    print("ATLAS19_PAIRED "+json.dumps(row,sort_keys=True),flush=True)
    return row
def reference(source,expected,arm,rep):
    dest=OUT/"references"/arm/f"rep-{rep}"
    dest.mkdir(parents=True,exist_ok=True)
    log=dest/"trial.log";log.write_text("")
    proof=dest/"reference.drat"
    proof.unlink(missing_ok=True)
    started=time.perf_counter()
    deadline=started+CAP
    cmd=[BINS[arm],"--no-binary",source,proof]
    r=run(cmd,deadline,log)
    result="UNKNOWN";reason="UNRESOLVED"
    if r["status"]=="TIMEOUT":
        reason="PRODUCER_TIMEOUT"
    elif r["rc"]==20:
        if proof.exists() and proof.stat().st_size:
            checked=proof_checker(source,proof,deadline,log,"DRAT")
            if checked=="ACCEPTED":
                result="UNSAT_VERIFIED";reason="ORIGINAL_DRAT_CHECKED"
            else:reason=checked
        else:reason="UNSAT_REPORTED_NO_PROOF"
    elif r["rc"]==10:
        # No SAT claim without an independent model, and this original has
        # a known externally verified UNSAT proof. Treat as critical conflict.
        raise RuntimeError("REFERENCE_REPORTED_SAT_ON_PROVEN_UNSAT")
    elif r["rc"] in (-25,153):
        reason="PROOF_FILE_SIZE_LIMIT"
    else:reason=f"UNKNOWN_RC_{r['rc']}"
    elapsed=round(time.perf_counter()-started,6)
    if elapsed>CAP:result="UNKNOWN";reason="E2E_OVER_15S"
    if sha(source)!=expected:raise RuntimeError("REFERENCE_SOURCE_HASH_CHANGED")
    row={"arm":arm,"rep":rep,"status":result,"reason":reason,
         "e2e_s":elapsed,"proof_bytes":proof.stat().st_size if proof.is_file() else 0,
         "source_sha256":expected}
    dump(dest/"trial.json",row)
    print("ATLAS19_REFERENCE "+json.dumps(row,sort_keys=True),flush=True)
    return row
def safety_control(case):
    source=ROOT/case["path"]
    assert sha(source)==case["sha256"]
    dest=OUT/"control"/case["name"];dest.mkdir(parents=True,exist_ok=True)
    log=dest/"trial.log";log.write_text("")
    start=time.perf_counter()
    r=run([sys.executable,ROOT/"research/atlas18_probe/router.py",
           "--cnf",source,"--out",dest/"out"],
          start+CAP,log)
    if r.get("status")!="RETURNED" or r.get("rc")!=0:
        raise RuntimeError("CONTROL_ROUTER_CRASH "+str(r))
    output=json.loads((dest/"out"/"result.json").read_text())
    if output["source_sha256"]!=case["sha256"]:
        raise RuntimeError("CONTROL_SOURCE_MISMATCH")
    if output["status"]=="UNSAT_VERIFIED":
        # Other public originals can be UNSAT; still enforce checker source.
        proof=dest/"out"/"result.pbp"
        replay=dest/"replay.log";replay.write_text("")
        if proof_checker(source,proof,time.perf_counter()+20,
                         replay,"PBP")!="ACCEPTED":
            raise RuntimeError("CONTROL_PROOF_REPLAY_REJECTED")
    row={"name":case["name"],"status":output["status"],
         "gate":output.get("clique_color_source_gate"),
         "e2e_s":output["router_E2E_s"],
         "stage":output.get("selected",{}).get("stage") if output.get("selected") else None}
    dump(dest/"result.json",row)
    print("ATLAS19_CONTROL "+json.dumps(row,sort_keys=True),flush=True)
    return row

target=[p for p in MANIFEST["sources"] if p["sha256"]==TARGET_SHA]
assert len(target)==1 and target[0]["name"]=="clique-color-2025"
source=ROOT/target[0]["path"]
assert sha(source)==TARGET_SHA
from sys import path
path.insert(0,str(ROOT/"research/atlas19_clique"))
from source_gate import sniff
gate=sniff(source)
assert gate["candidate"] and gate["clique_size_hypothesis"]==6
assert gate["colors_hypothesis"]==5 and gate["n_vertices_hypothesis"]==100
dump(OUT/"frozen_target_gate.json",gate)
rows=[]
for rep in range(2):
    order=("ATLAS18","ATLAS19") if rep==0 else ("ATLAS19","ATLAS18")
    for arm in order:
        rows.append(router_arm(source,TARGET_SHA,arm,rep))
    for arm in ("Kissat4.0.4","CaDiCaL2.1.3"):
        rows.append(reference(source,TARGET_SHA,arm,rep))
controls=[]
for c in MANIFEST["sources"]:
    if c["sha256"]!=TARGET_SHA and c["cohort"]=="public_preselected":
        controls.append(safety_control(c))
summary={"status":"COMPLETE","original_sha256":TARGET_SHA,
         "original_variables":target[0]["variables"],
         "original_clauses":target[0]["clauses"],
         "repetitions":2,"strict_e2e_cap_s":CAP,
         "single_logical_cpu":CPU,
         "standard_original_external_proofs_only":True,
         "replayed_external_proofs":sum(r.get("external_replay")=="ACCEPTED" for r in rows),
         "ATLAS19_strict_success":sum(r["status"]=="UNSAT_VERIFIED" for r in rows if r["arm"]=="ATLAS19"),
         "ATLAS18_strict_success":sum(r["status"]=="UNSAT_VERIFIED" for r in rows if r["arm"]=="ATLAS18"),
         "Kissat_strict_success":sum(r["status"]=="UNSAT_VERIFIED" for r in rows if r["arm"]=="Kissat4.0.4"),
         "CaDiCaL_strict_success":sum(r["status"]=="UNSAT_VERIFIED" for r in rows if r["arm"]=="CaDiCaL2.1.3"),
         "no_cdcl_fallback_in_atlas":True,
         "retrospective_known_clique_color_source":True,
         "no_general_speed_claim":True,"main_unmodified":True,
         "rows":rows,"controls":controls}
dump(OUT/"summary.json",summary)
print("ATLAS19_FINAL "+json.dumps({k:v for k,v in summary.items() if k not in ("rows","controls")},sort_keys=True),flush=True)
