#!/usr/bin/env python3
"""ATLAS18 structural-only router with an externally checked original proof.

Fixed sequence (content-only, no labels): GRAPH -> broad HALL ->
XOR source parity -> weighted PCMAX -> subset-HALL ->
subset+GRAPH/XOR fact exchange. Every successful stage is verified against the
unchanged original CNF. A structural miss remains an annotated UNKNOWN, never
a CDCL fallback. All modules run serially on one logical CPU.
"""
import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/atlas19_clique"))
from source_gate import sniff as clique_color_source_gate
CAP=15.0
class Unsafe(Exception):pass
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def child_limits():
    resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_AS,(4*1024*1024*1024,)*2)
def shell(cmd,deadline):
    remain=deadline-time.perf_counter()
    if remain<=0.04:return {"status":"TIMEOUT","note":"overall-budget"}
    try:
        r=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,
                         errors="replace",preexec_fn=child_limits,timeout=remain)
    except subprocess.TimeoutExpired:return {"status":"TIMEOUT","note":"stage-budget"}
    return {"status":"RETURNED","code":r.returncode,
            "out":r.stdout[-1800:],"err":r.stderr[-600:]}
def run(cnf,out):
    cnf=Path(cnf).resolve()
    started=time.perf_counter()
    deadline=started+CAP
    original=sha(cnf)
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    proof=out/"result.pbp";proof.unlink(missing_ok=True)
    meta=out/"result.json"
    py=sys.executable
    stages=[
      ("GRAPH_ORIGINAL",[py,ROOT/"research/atlas14_five/modes.py",
           "--mode","GRAPH_ONLY","--cnf",cnf,"--proof",proof,"--meta",out/"graph.json"]),
      ("HALL_BROAD_ORIGINAL",[py,ROOT/"research/atlas14_five/modes.py",
           "--mode","HALL_ONLY","--cnf",cnf,"--proof",proof,"--meta",out/"hall.json"]),
      ("XOR_SOURCE",[py,ROOT/"research/xorlin1/extract.py",
           "--cnf",cnf,"--certificate",out/"xor.cert.json","--meta",out/"xor.stats.json"]),
      ("PCMAX_NATIVE",[ROOT/"build/drnas-pcmax",cnf,"--mode","core","--time","7",
           "--pcmax-only","--pcmax-capacity","--pcmax-budget-ms","5000",
           "--pcmax-certificate",out/"pcmax.cert.json"]),
      ("HALL_SUBSET_SOURCE",[py,ROOT/"research/atlas18_probe/hall_subset.py",
           "--cnf",cnf,"--mode","DIRECT","--proof",proof,"--meta",out/"subset.json"]),
      ("HALL_PROOF_BUS",[py,ROOT/"research/atlas18_probe/hall_subset.py",
           "--cnf",cnf,"--mode","JOINT","--proof",proof,"--meta",out/"bus.json"]),
      ("HALL_UP_PROPAGATION",[py,ROOT/"research/atlas18_probe/hall_subset.py",
           "--cnf",cnf,"--mode","UCP","--proof",proof,"--meta",out/"ucp.json"]),
      ("HALL_GRAPH_XOR_UP_BUS",[py,ROOT/"research/atlas18_probe/hall_subset.py",
           "--cnf",cnf,"--mode","JOINT_UCP","--proof",proof,"--meta",out/"joint_ucp.json"])
    ]
    # Content-only classifier: NO filename, family metadata or expected status.
    # It only routes to a source-verified RED/RUP/CP producer; never asserts UNSAT.
    clique_gate=clique_color_source_gate(cnf)
    (out/"clique_color_gate.json").write_text(json.dumps(clique_gate,sort_keys=True,indent=2)+"\n")
    if clique_gate["candidate"]:
        stages.insert(0,("CLIQUE_COLOR_EXTENDED_PBP",[
             py,ROOT/"research/clique_color_er/emit_veripb.py",
             "--cnf",cnf,"--pbp",proof,"--meta",out/"clique_color_emitter.json"]))
    records=[]
    selected=None
    for name,cmd in stages:
        proof.unlink(missing_ok=True)
        t=time.perf_counter()
        found=shell(cmd,deadline)
        if found["status"]!="RETURNED":
            records.append({"stage":name,"status":"UNKNOWN","reason":found["note"],
                            "s":round(time.perf_counter()-t,6)})
            if time.perf_counter()>=deadline:break
            continue
        produced=found["code"] in (0,20)
        if name=="XOR_SOURCE" and found["code"]==0 and (out/"xor.cert.json").is_file():
            found=shell([py,ROOT/"research/xorlin1/emit_veripb.py",
                   "--cnf",cnf,"--certificate",out/"xor.cert.json",
                   "--output",proof,"--meta",out/"xor.emitter.json"],deadline)
            produced=found.get("code")==0
        elif name=="PCMAX_NATIVE" and found["code"]==20:
            cert=out/"pcmax.cert.json"
            if not cert.exists():raise Unsafe("PCMAX_REPORTED_UNSAT_WITHOUT_CERTIFICATE")
            checked=shell([py,ROOT/"research/pcmax_capacity/check_capacity.py",
                           cnf,cert],deadline)
            if checked.get("code")!=0:raise Unsafe("PCMAX_CERTIFICATE_NOT_SOURCE_VALID")
            found=shell([py,ROOT/"research/pcmax_capacity/emit_veripb_capacity_weighted2.py",
                         "--cnf",cnf,"--certificate",cert,"--output",proof],deadline)
            produced=found.get("code")==0
        elif name=="PCMAX_NATIVE":
            produced=False
        if produced and proof.exists() and proof.stat().st_size:
            if sha(cnf)!=original:raise Unsafe("SOURCE_CHANGED")
            v=shell(["veripb","--cnf",cnf,proof],deadline)
            if v.get("status")=="TIMEOUT":
                records.append({"stage":name,"status":"UNKNOWN",
                    "reason":"EXTERNAL_PROOF_CHECK_TIMEOUT",
                    "s":round(time.perf_counter()-t,6)})
                continue
            if v.get("code")!=0 or "s VERIFIED UNSATISFIABLE" not in v.get("out","")+v.get("err",""):
                raise Unsafe(f"EXTERNAL_ORIGINAL_PROOF_REJECTED:{name}:{str(v)[-280:]}")
            selected={"stage":name,"proof_bytes":proof.stat().st_size,
                    "proof_sha256":sha(proof)}
            records.append({"stage":name,"status":"UNSAT_VERIFIED",
                           "s":round(time.perf_counter()-t,6)})
            break
        records.append({"stage":name,"status":"UNKNOWN",
                        "reason":("STRUCTURE_UNSUPPORTED" if found.get("code")==2 else
                                  "NOT_PROVED_WITHIN_BUDGET"),
                        "s":round(time.perf_counter()-t,6)})
    elapsed=round(time.perf_counter()-started,6)
    status="UNSAT_VERIFIED" if selected and elapsed<=CAP else "UNKNOWN"
    result={"status":status,"source_sha256":original,"source_original_not_modified":True,
            "clique_color_source_gate":clique_gate,
            "router_E2E_s":elapsed,"strict_wall_cap_s":CAP,
            "CDCL_fallback_called":False,"selected":selected if status=="UNSAT_VERIFIED" else None,
            "stages":records}
    if status!="UNSAT_VERIFIED":proof.unlink(missing_ok=True)
    meta.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS18_ROUTER "+json.dumps(result,sort_keys=True),flush=True)
    return status
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--cnf",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    try:run(a.cnf,a.out)
    except Unsafe as e:
        print("ATLAS18_FATAL_PROOF_SAFETY "+str(e),flush=True)
        raise SystemExit(1)
