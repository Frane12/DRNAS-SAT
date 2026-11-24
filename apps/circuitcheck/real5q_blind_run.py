#!/usr/bin/env python3
"""REAL5Q prospective 5 new external RTL modules, no retuning.

The mathematical GF2-ANF engine and its independent checker are SHA-pinned
BEFORE selection. All source outcomes remain in the cohort: Yosys failure,
no affine/quadratic structure, timeout, or certified exact bounded polynomials.
Kissat + CaDiCaL controls are run only on actual gate-cone SAT miters
whose source gate certificates have been independently replayed.
This is not a full-module SAT/UNSAT comparison or temporal verification.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
from stress_run import run
ENGINE="fc0ed0b1a57bd5b0df75ba3f307faccef7a763edb39408e20e278cd09d40d35a"
CHECKER="a7203de8c48148dc24a9bb37f593e1b924b5e3d24c8cdf767e6bbd91c117738b"
YOSYS_CAP=100
ANF_CAP=50
CHECK_CAP=50

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def bounded(cmd,cpu,limit,log):
    return run(cmd,cpu,limit,log)

def analyze_case(entry,root,output,engine,cpu):
    name=entry["id"]
    src=root/entry["source_filename"]
    if sha(src)!=entry["sha256"]:raise RuntimeError("ORIGINAL_RTL_SHA_CHANGED "+name)
    where=output/"cases"/name;where.mkdir(parents=True,exist_ok=True)
    row={"id":name,"original_commit":entry["commit"],
         "original_sha256":entry["sha256"],
         "source_git_blob_sha1":entry["blob"],
         "top":entry["top"],"synthesis":{"status":"NOT_RUN"},
         "polynomial":{"status":"NOT_RUN"},"verification":{"status":"NOT_RUN"}}
    def record(): (where/"case.json").write_text(json.dumps(row,indent=2)+"\n")
    raw=where/"netlist.json"
    yosys=("read_verilog -sv "+str(src.resolve())+
           "; hierarchy -check -top "+entry["top"]+
           "; proc; flatten; opt; techmap; opt; write_json "+str(raw))
    t=bounded(["yosys","-p",yosys],cpu,YOSYS_CAP,where/"yosys-original.log")
    row["synthesis"]={"status":"TIMEOUT" if t["timeout"] else (
          "OK" if t["return_code"]==0 and raw.is_file() else "FRONTEND_UNSUPPORTED"),
          "seconds":t["seconds"],"max_rss_kb":t["max_rss_kb"]}
    record()
    if row["synthesis"]["status"]!="OK":
        print("REAL5Q_BLIND_UNSUPPORTED",name,row["synthesis"]["status"],flush=True)
        return row
    row["netlist_sha256"]=sha(raw)
    cert=where/"real5q_certificate.json"
    t=bounded([sys.executable,engine/"real5q_anf.py",
               "--netlist",raw,"--top",entry["top"],
               "--out",cert],cpu,ANF_CAP,where/"polynomial-engine.log")
    if t["timeout"] or t["return_code"]!=0 or not cert.is_file():
        row["polynomial"]={"status":"TIMEOUT" if t["timeout"] else "UNKNOWN",
                           "seconds":t["seconds"]}
        record()
        return row
    result=json.loads(cert.read_text())
    row["polynomial"]={"status":result["status"],"seconds":t["seconds"],
                       "metrics":result.get("metrics",{}),
                       "certificate_sha256":sha(cert)}
    if result["status"]!="EXACT_BOUNDED_POLYNOMIAL_CERTIFICATE_NOT_SAT_UNSAT":
        record()
        return row
    checked=bounded([sys.executable,engine/"real5q_verify.py",
              where],cpu,CHECK_CAP,where/"independent-replay.log")
    if checked["return_code"]!=0 or checked["timeout"]:
        row["verification"]={"status":"FAILED","seconds":checked["seconds"]}
        record()
        raise RuntimeError("FALSE_GF2_POLYNOMIAL_PROOF "+name)
    row["verification"]={"status":"CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS",
                         "seconds":checked["seconds"]}
    record()
    print("REAL5Q_BLIND_CERT_PASS",name,row["polynomial"]["metrics"],flush=True)
    return row

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--shard",required=True,type=int)
    p.add_argument("--shards",type=int,default=3)
    p.add_argument("--kissat",required=True,type=Path)
    p.add_argument("--cadical",required=True,type=Path)
    a=p.parse_args()
    a.frozen=a.frozen.resolve();a.out=a.out.resolve()
    a.out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parent
    if sha(root/"real5q_anf.py")!=ENGINE or sha(root/"real5q_verify.py")!=CHECKER:
        raise RuntimeError("PRELOCKED_MATH_ENGINE_MODIFIED")
    corpus=json.loads((a.frozen/"manifest.json").read_text())
    if corpus["protocol"]!="DRNAS_REAL5Q_PROSPECTIVE_5_NEW_UNCHANGED_RTL_20261124":
        raise RuntimeError("WRONG_PROSPECTIVE_COHORT")
    if len(corpus["cases"])!=5 or corpus["prelock_run"]!=45344568141:
        raise RuntimeError("UNEXPECTED_BLIND_COHORT")
    if a.shard<0 or a.shard>=a.shards:raise RuntimeError("BAD_SHARD")
    cpu=min(os.sched_getaffinity(0))
    result={"protocol":corpus["protocol"],"shard":a.shard,"shards":a.shards,
            "source_manifest_sha256":sha(a.frozen/"manifest.json"),
            "prelocked_anf_sha256":ENGINE,"prelocked_verifier_sha256":CHECKER,
            "one_cpu":cpu,"cases":[],"sat_control":{"status":"NOT_RUN"}}
    success=[]
    for i,entry in enumerate(corpus["cases"]):
        if i%a.shards!=a.shard:continue
        row=analyze_case(entry,a.frozen,a.out,root,cpu)
        result["cases"].append(row)
        if row["verification"]["status"]=="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS":
            success.append(row["id"])
        (a.out/"rows.json").write_text(json.dumps(result,indent=2)+"\n")
    if success:
        # Proven netlists live under cases/<name>, whereas paired SAT helper
        # expects direct children of a corpus folder; copy the immutable
        # original cert/netlist without synthesizing a replacement circuit.
        target=a.out/"for_sat";target.mkdir(exist_ok=True)
        for name in success:
            src=a.out/"cases"/name;dst=target/name;dst.mkdir(exist_ok=True)
            for file in ("netlist.json","real5q_certificate.json","real5q_verification.json"):
                shutil.copyfile(src/file,dst/file)
        runlog=bounded([sys.executable,root/"real5q_sat.py",
                "--originals",target,"--out",a.out/"quadratic_sat",
                "--only",",".join(success),
                "--kissat",a.kissat.resolve(),"--cadical",a.cadical.resolve()],
                cpu,480,a.out/"sat-controls.log")
        result["sat_control"]={"status":"SUCCESS" if runlog["return_code"]==0 and
            not runlog["timeout"] else "FAILED","seconds":runlog["seconds"],
            "input_projects":success}
        if result["sat_control"]["status"]!="SUCCESS":
            (a.out/"rows.json").write_text(json.dumps(result,indent=2)+"\n")
            raise RuntimeError("MISSING_MANDATORY_SAT_CONTROLS")
    else:
        result["sat_control"]={"status":"NO_VERIFIED_QUADRATIC_SOURCE","input_projects":[]}
    (a.out/"rows.json").write_text(json.dumps(result,indent=2)+"\n")
    print("REAL5Q_BLIND_SHARD_FINISHED",a.shard,len(result["cases"]),success,flush=True)

if __name__=="__main__":main()
