#!/usr/bin/env python3
"""Re-run DELTA1 on original SHA-frozen 20 RTL stress cases (same source set).

Compare using the original 2026-11-23 CircuitCheck/Kissat/CaDiCaL
JSON artifact (run 45247995613) without re-running or retuning their
results. Four independently pinned one-CPU shards, 30s cap inclusive of
Yosys RTL synthesis + affine proof + independently replayed certificate.
No source names, fault flag or expected result enter solver arguments.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

CAP = 30.
REPEATS = 2
SOURCE_RUN = 45245092918
BASELINE_AUDIT_RUN = 45247995613

def sha(path:Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def bounded(cmd, cwd, seconds, path):
    cwd=Path(cwd).resolve()
    path=Path(path).resolve()
    start=time.perf_counter()
    path.parent.mkdir(exist_ok=True,parents=True)
    rssfile=path.with_suffix(".rss")
    cpu=sorted(os.sched_getaffinity(0))[0]
    run=["/usr/bin/time","-f","%M","-o",str(rssfile),
         "taskset","-c",str(cpu)]+list(map(str,cmd))
    p=subprocess.Popen(run,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       start_new_session=True)
    timedout=False
    try:
        out,err=p.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        timedout=True
        os.killpg(p.pid,signal.SIGKILL)
        out,err=p.communicate()
    elapsed=time.perf_counter()-start
    out=out.decode(errors="replace")
    err=err.decode(errors="replace")
    path.write_text(out+"\n[STDERR]\n"+err)
    try:rss=int(rssfile.read_text().splitlines()[-1])
    except (OSError,IndexError,ValueError):rss=None
    return {"elapsed":round(elapsed,6),"timeout":timedout,
            "returncode":None if timedout else p.returncode,
            "max_rss_kb":rss,"stdout":out,"stderr":err}

def trial(case,source,args,root,repeat):
    work=args.out/"cases"/case["id"]/str(repeat)
    work.mkdir(parents=True,exist_ok=True)
    p=bounded([sys.executable,root/"delta1.py","--rtl",source,
               "--reference","reference","--candidate","candidate",
               "--out",work/"proof"],work,CAP,work/"delta1.log")
    info={"status":"TIMEOUT" if p["timeout"] else "UNKNOWN",
          "seconds":p["elapsed"],"max_rss_kb":p["max_rss_kb"],
          "returncode":p["returncode"],"timeout":p["timeout"],
          "cert_replay":False,"proof_sha256":None}
    certdir=work/"proof"
    if info["status"]=="TIMEOUT":return info
    reportfile=certdir/"delta1_report.json"
    if not reportfile.is_file():return info
    report=json.loads(reportfile.read_text())
    state=report["status"]
    if state not in ("EQUIVALENT_NETLIST","DIFFERENT_NETLIST"):return info
    code=0 if state=="EQUIVALENT_NETLIST" else 10
    if p["returncode"]!=code:return info
    left=CAP-p["elapsed"]
    if left<0.1:
        info["status"]="TIMEOUT";return info
    v=bounded([sys.executable,root/"delta1_verify.py",certdir],work,left,
              work/"delta1-replay.log")
    info["seconds"]=round(p["elapsed"]+v["elapsed"],6)
    if v["max_rss_kb"] is not None:
        info["max_rss_kb"]=max(info["max_rss_kb"] or 0,v["max_rss_kb"])
    if v["timeout"]:
        info.update(status="TIMEOUT",timeout=True)
        return info
    if v["returncode"]!=0:
        info["status"]="REPLAY_FAILED"
        info["checker_error"]=v["stdout"][-1000:]
        return info
    proof=json.loads((certdir/"delta1_verification.json").read_text())
    expected_checker=("CHECKED_EQUIVALENT_NETLIST" if state=="EQUIVALENT_NETLIST"
                      else "CHECKED_DIFFERENT_NETLIST")
    if proof["status"]!=expected_checker:
        info["status"]="REPLAY_FAILED"
        return info
    info["status"]="EQUIVALENT" if state=="EQUIVALENT_NETLIST" else "DIFFERENT"
    info["cert_replay"]=True
    info["proof_sha256"]=sha(certdir/"delta1_certificate.json")
    info["engine_metrics"]=report.get("metrics",{})
    info["netlist_sha256"]=report.get("netlist_sha256")
    return info

def shard(args):
    frozen=json.loads(args.manifest.read_text())
    assert frozen["protocol"]=="CIRCUITCHECK_STRESS_FIXED_20261123"
    assert len(frozen["cases"])==20
    root=Path(__file__).resolve().parent
    args.out=args.out.resolve()
    args.out.mkdir(parents=True,exist_ok=True)
    manifest_sha=sha(args.manifest)
    report={"protocol":"DRNAS_DELTA1_AFFINE_STRESS_V1",
            "source_run":SOURCE_RUN,"manifest_sha256":manifest_sha,
            "shard":args.shard,"shards":args.shards,"repeats":REPEATS,"cap":CAP,
            "platform":platform.platform(),
            "engine_hashes":{name:sha(root/name) for name in
              ["delta1_engine.py","delta1.py","delta1_verify.py",
               "circuitcheck.py"]},
            "cases":[]}
    def persist():
        (args.out/"rows.json").write_text(json.dumps(report,indent=2)+"\n")
    for i,case in enumerate(frozen["cases"]):
        if i%args.shards!=args.shard:continue
        src=Path(case["rtl"]).resolve()
        if not src.is_file() or sha(src)!=case["sha256"]:
            raise RuntimeError("MISMATCHED_FROZEN_INPUT "+str(src))
        row={"id":case["id"],"family":case["family"],
             "input_bits":case["input_bits"],"expected":case["expected"],
             "source_sha256":sha(src),"trials":[]}
        report["cases"].append(row);persist()
        for repeat in range(REPEATS):
            t=trial(case,src,args,root,repeat)
            expected="DIFFERENT" if case["fault"] else "EQUIVALENT"
            if t["status"] in ("DIFFERENT","EQUIVALENT") and t["status"]!=expected:
                raise RuntimeError("INCORRECT_VERDICT "+case["id"]+" "+t["status"])
            if t["status"] in ("DIFFERENT","EQUIVALENT") and not t["cert_replay"]:
                raise RuntimeError("UNVERIFIED_PROOF "+case["id"])
            record={"repeat":repeat,"expected":expected,**t}
            row["trials"].append(record);persist()
            print("DELTA1_TRIAL",case["id"],repeat,t["status"],
                  t["seconds"],"s rss_kb",t["max_rss_kb"],
                  "proof_replayed",t["cert_replay"],flush=True)
    print("DELTA1_SHARD_COMPLETE",args.shard,flush=True)

def aggregate(args):
    frozen=json.loads(args.manifest.read_text())
    old=json.loads(args.baseline.read_text())
    if old["protocol"]!=frozen["protocol"]:
        raise RuntimeError("BASELINE_PROTOCOL_MISMATCH")
    if old["manifest_sha256"]!=sha(args.manifest):
        raise RuntimeError("BASELINE_FROZEN_SHA_MISMATCH")
    rows={}
    for i in range(args.shards):
        base=args.combined/("delta1-shard-"+str(i))
        f=base/"rows.json"
        if not f.is_file():f=base/"results"/"rows.json"
        if not f.is_file():raise RuntimeError("MISSING_SHARD "+str(i))
        doc=json.loads(f.read_text())
        if doc["shard"]!=i or doc["manifest_sha256"]!=sha(args.manifest):
            raise RuntimeError("BAD_SHARD_SOURCE_SHA "+str(i))
        for case in doc["cases"]:
            if case["id"] in rows:raise RuntimeError("DUPLICATE_CASE")
            rows[case["id"]]=case
    if set(rows)!={x["id"] for x in frozen["cases"]}:
        raise RuntimeError("MISSING_CASES")
    ref=old["cases"]
    totals={"DELTA1":{"solved":0,"timeout":0,"par2_s":0,"attempts":0},
            "CircuitCheck_v01":{"solved":0,"timeout":0,"par2_s":0,"attempts":0},
            "Kissat_CNF":{"solved":0,"timeout":0,"par2_s":0,"attempts":0},
            "CaDiCaL_CNF":{"solved":0,"timeout":0,"par2_s":0,"attempts":0}}
    lines=["# DRNAS DELTA1 v1 — original 64..2048-bit stress RTL",
        "",
        "**Original SHA-frozen cohort:** GitHub Actions run "+str(SOURCE_RUN)+
        ". Same 20 Verilog files, 2 repetitions; each result capped at 30s.",
        "DELTA1 includes Yosys synthesis, compact GF(2) coefficient propagation and separate exact gate-netlist certificate replay.",
        "Baselines are imported UNCHANGED from earlier original stress audit "+str(BASELINE_AUDIT_RUN)+
        "; they were not rerun, so machine/runner variation may affect precise timing.",
        "**Unlike the SAT baselines, DELTA1 operates on Yosys gate-level JSON, not the unchanged CNF. Never claim same-CNF speedup.**",
        "SAT/UNSAT bare solver statuses on original DIMACS are not standard externally certified UNSAT proofs.",
        "",
        "| Family | Input bits | Expected | DELTA1 2× | Old CircuitCheck 2× | Kissat 2× | CaDiCaL 2× |",
        "|---|---:|---|---|---|---|---|"]
    for case in frozen["cases"]:
        key=case["id"]
        now=rows[key]; before=ref[key]
        if now["source_sha256"]!=case["sha256"] or before["sha256"]!=case["sha256"]:
            raise RuntimeError("RTL_CASE_SHA_MISMATCH "+key)
        series={
           "DELTA1":sorted(now["trials"],key=lambda x:x["repeat"]),
           "CircuitCheck_v01":sorted([x for x in before["trials"] if x["arm"]=="CircuitCheck"],key=lambda x:x["repeat"]),
           "Kissat_CNF":sorted([x for x in before["trials"] if x["arm"]=="Kissat"],key=lambda x:x["repeat"]),
           "CaDiCaL_CNF":sorted([x for x in before["trials"] if x["arm"]=="CaDiCaL"],key=lambda x:x["repeat"])
        }
        fmt={}
        for arm,ts in series.items():
            if len(ts)!=2:raise RuntimeError("MISSING_REPETITION "+key+" "+arm)
            fmt[arm]=" / ".join(f"{t['status']} {t['seconds']:.3f}s" for t in ts)
            for t in ts:
                expected = ("DIFFERENT" if case["fault"] else "EQUIVALENT") if arm in ("DELTA1","CircuitCheck_v01") else (
                    "SAT" if case["fault"] else "UNSAT")
                good=t["status"]==expected and t["seconds"]<=CAP
                if arm=="DELTA1" and good and not t.get("cert_replay"):
                    raise RuntimeError("NO_CERT_REPLAY "+key)
                if arm=="CircuitCheck_v01" and good and not t.get("netlist_cert_replayed"):
                    raise RuntimeError("OLD_UNREPLAYED_PROOF "+key)
                if arm in ("Kissat_CNF","CaDiCaL_CNF") and good and expected=="SAT" and not t.get("sat_witness_checked"):
                    raise RuntimeError("UNVERIFIED_SAT "+key)
                totals[arm]["attempts"]+=1
                totals[arm]["solved"]+=int(good)
                totals[arm]["timeout"]+=int(t["status"]=="TIMEOUT")
                totals[arm]["par2_s"]+=t["seconds"] if good else CAP*2
        lines.append("| "+case["family"]+" | "+str(case["input_bits"])+
            " | "+("SAT-control" if case["fault"] else "EQUIVALENCE")+
            " | "+fmt["DELTA1"]+" | "+fmt["CircuitCheck_v01"]+
            " | "+fmt["Kissat_CNF"]+" | "+fmt["CaDiCaL_CNF"]+" |")
    lines+=["","## PAR-2 of 40 attempts per arm (timeout=60 s)","",
            "| Arm | Solved/40 | Timeouts | PAR-2 (s) |",
            "|---|---:|---:|---:|"]
    for arm,score in totals.items():
        lines.append(f"| {arm} | {score['solved']}/40 | {score['timeout']} | {score['par2_s']:.3f} |")
    lines.extend(["",
        "## Limits",
        "",
        "Only synthetic CRC/LFSR workload, no real third-party RTL. No all-SAT performance claim.",
        "Proof is for synthesized 2-state netlist with Yosys trusted. For UNKNOWN no claim.",
        "DNF/CNF standard UNSAT certificate and source-level equivalence remain separate validation needs."])
    result={"original_stress_run":SOURCE_RUN,"baseline_audit_run":BASELINE_AUDIT_RUN,
            "manifest_sha256":sha(args.manifest),"cases":rows,
            "scores":totals}
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    args.report.write_text("\n".join(lines)+"\n")
    print(args.report.read_text())

def main():
    p=argparse.ArgumentParser()
    subs=p.add_subparsers(dest="mode",required=True)
    a=subs.add_parser("shard")
    a.add_argument("--manifest",required=True,type=Path)
    a.add_argument("--out",required=True,type=Path)
    a.add_argument("--shard",required=True,type=int)
    a.add_argument("--shards",default=4,type=int)
    a=subs.add_parser("aggregate")
    a.add_argument("--manifest",required=True,type=Path)
    a.add_argument("--combined",required=True,type=Path)
    a.add_argument("--baseline",required=True,type=Path)
    a.add_argument("--output",required=True,type=Path)
    a.add_argument("--report",required=True,type=Path)
    a.add_argument("--shards",default=4,type=int)
    args=p.parse_args()
    if args.mode=="shard":shard(args)
    else:aggregate(args)

if __name__=="__main__":main()
