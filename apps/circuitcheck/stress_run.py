#!/usr/bin/env python3
"""DRNAS CircuitCheck high-variable stress: original RTL vs exported DIMACS SAT.

This is an *unretuned* frozen synthetic stress cohort. CircuitCheck sees a
synthesized Yosys gate netlist; Kissat and CaDiCaL receive the matching RTL's
Yosys-exported miter CNF. We report this representation difference prominently:
a favorable ratio is NOT equivalent to a same-DIMACS algorithmic speedup.

All independent CircuitCheck certificate replay is included in its 30s budget.
SAT witnesses are rechecked on the full original DIMACS; baseline UNSAT is
not described as certified without external DRAT/LRAT verification.
Memory is measured as maximum RSS for each timed process in KiB.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

CAP = 30.0
CNF_EXPORT_CAP = 100.0
REPEATS = 2
ARMS = ("CircuitCheck","Kissat","CaDiCaL")

def sha(path:Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(cmd, cpu, timeout, path:Path):
    path.parent.mkdir(exist_ok=True,parents=True)
    start=time.perf_counter()
    rssfile=path.with_suffix(".rss")
    command=["/usr/bin/time","-f","%M","-o",str(rssfile),
             "taskset","-c",str(cpu)]+[str(s) for s in cmd]
    try:
        p=subprocess.run(command,capture_output=True,text=True,timeout=timeout,check=False)
        record={"seconds":round(time.perf_counter()-start,6),
                "timeout":False,"return_code":p.returncode,
                "stdout":p.stdout,"stderr":p.stderr}
    except subprocess.TimeoutExpired as ex:
        so=ex.stdout.decode(errors="replace") if isinstance(ex.stdout,bytes) else (ex.stdout or "")
        se=ex.stderr.decode(errors="replace") if isinstance(ex.stderr,bytes) else (ex.stderr or "")
        record={"seconds":round(time.perf_counter()-start,6),
                "timeout":True,"return_code":None,"stdout":so,"stderr":se}
    path.write_text(record["stdout"]+"\n[STDERR]\n"+record["stderr"])
    try: record["max_rss_kb"]=int(rssfile.read_text().strip().splitlines()[-1])
    except (OSError,ValueError,IndexError):record["max_rss_kb"]=None
    return record

def dimacs_meta(cnf):
    vars_count=clauses_count=None
    with cnf.open() as f:
        for line in f:
            if line.startswith("p cnf "):
                _,_,nv,nc=line.split()[:4]
                vars_count=int(nv);clauses_count=int(nc)
                break
    if vars_count is None:raise ValueError("no DIMACS header in "+str(cnf))
    return {"vars":vars_count,"clauses":clauses_count,
            "sha256":sha(cnf),"bytes":cnf.stat().st_size}

def result_status(stdout:str,return_code:int|None,timed_out:bool):
    if timed_out:return "TIMEOUT"
    match=re.findall(r"(?m)^s\s+(SATISFIABLE|UNSATISFIABLE|UNKNOWN)\b",stdout)
    if match:
        kind=match[-1]
        if kind=="SATISFIABLE" and return_code==10:return "SAT"
        if kind=="UNSATISFIABLE" and return_code==20:return "UNSAT"
        if kind=="UNKNOWN":return "UNKNOWN"
    return "ERROR"

def verify_sat(cnf:Path,stdout:str):
    truth={}
    saw=False
    for line in stdout.splitlines():
        if not line.startswith("v "):continue
        saw=True
        for t in line[2:].split():
            lit=int(t)
            if not lit:continue
            v=abs(lit); val=lit>0
            if v in truth and truth[v]!=val:return False
            truth[v]=val
    if not saw:return False
    satisfied=0;cl=[]
    with cnf.open() as f:
        for line in f:
            if not line.strip() or line[0] in "cp%":continue
            for t in line.split():
                lit=int(t)
                if lit:
                    cl.append(lit)
                else:
                    if not cl or any(abs(x) not in truth for x in cl):return False
                    if not any(truth[abs(x)]==(x>0) for x in cl):return False
                    satisfied+=1
                    cl=[]
    return satisfied>0 and not cl

def recorded_run(record, stdout):
    return {"status":record["status"],"seconds":record["seconds"],
            "timeout":record.get("timeout"),"return_code":record.get("return_code"),
            "max_rss_kb":record.get("max_rss_kb"),
            "sat_witness_checked":record.get("sat_witness_checked"),
            "netlist_cert_replayed":record.get("netlist_cert_replayed"),
            "standard_unsat_certificate":False}

def run_circuitcheck(source:Path, work:Path, cpu:int, limit:float,
                     index:str, root:Path):
    work.mkdir(parents=True,exist_ok=True)
    output=work/"proof"
    p=run([sys.executable,root/"circuitcheck.py",
           "--rtl",source,"--reference","reference","--candidate","candidate",
           "--out",output],cpu,limit,work/"circuitcheck.log")
    info={"status":"UNKNOWN","seconds":p["seconds"],"timeout":p["timeout"],
          "return_code":p["return_code"],"max_rss_kb":p["max_rss_kb"],
          "netlist_cert_replayed":False}
    if p["timeout"]:
        info["status"]="TIMEOUT";return info
    if not (output/"report.json").exists():return info
    report=json.loads((output/"report.json").read_text())
    status=report.get("status")
    expected_rc={"EQUIVALENT_NETLIST":0,"DIFFERENT_NETLIST":10}
    if status not in expected_rc or p["return_code"]!=expected_rc[status]:
        return info
    remaining=max(0.0,limit-p["seconds"])
    if remaining<=0.05:
        info["status"]="TIMEOUT";return info
    v=run([sys.executable,root/"verify_certificate.py",output],cpu,
           remaining,work/"independent_replay.log")
    info["seconds"]=round(p["seconds"]+v["seconds"],6)
    info["max_rss_kb"]=max([x for x in (p["max_rss_kb"],v["max_rss_kb"]) if x is not None],default=None)
    if v["timeout"]:
        info["status"]="TIMEOUT";info["timeout"]=True;return info
    if v["return_code"]!=0 or not (output/"verification.json").exists():
        info["status"]="REPLAY_FAILED";return info
    verdict=json.loads((output/"verification.json").read_text())
    should="CHECKED_EQUIVALENT_NETLIST" if status=="EQUIVALENT_NETLIST" else "CHECKED_DIFFERENT_NETLIST"
    if verdict["status"]!=should:
        info["status"]="REPLAY_FAILED";return info
    info["status"]="EQUIVALENT" if status=="EQUIVALENT_NETLIST" else "DIFFERENT"
    info["netlist_cert_replayed"]=True
    info["proof_sha256"]=sha(output/"certificate.json")
    return info

def shard(args):
    frozen=json.loads(args.manifest.read_text())
    assert frozen["protocol"]=="CIRCUITCHECK_STRESS_FIXED_20261123"
    assert len(frozen["cases"])==20
    cpu=sorted(os.sched_getaffinity(0))[0]
    root=Path(__file__).resolve().parent
    args.out.mkdir(parents=True,exist_ok=True)
    data={"protocol":frozen["protocol"],"frozen_manifest_sha256":sha(args.manifest),
          "shard":args.shard,"shards":args.shards,"cpu":cpu,
          "limit_seconds":CAP,"repeats":REPEATS,
          "platform":platform.platform(),
          "circuitcheck_source_hashes":{p:sha(root/p) for p in
              ["circuitcheck.py","proof_engine.py","verify_certificate.py"]},
          "baselines_binary_sha256":{"kissat":sha(args.kissat),"cadical":sha(args.cadical)},
          "cases":[]}
    def persist():
        (args.out/"rows.json").write_text(json.dumps(data,indent=2)+"\n")
    for idx,case in enumerate(frozen["cases"]):
        if idx%args.shards!=args.shard:continue
        source=Path(case["rtl"])
        if not source.exists() or sha(source)!=case["sha256"]:
            raise RuntimeError("SOURCE_TAMPERED "+str(source))
        cnf=args.out/(case["id"]+".cnf")
        case_record={k:case[k] for k in ("id","family","input_bits","output_bits","expected","fault","sha256")}
        case_record["trials"]=[];case_record["cnf"]=None
        case_record["original_rtl_sha256"]=sha(source)
        data["cases"].append(case_record);persist()
        cmd=("read_verilog -sv "+str(source)+"; hierarchy -check -top miter; "
             "proc; flatten; opt; sat -timeout 1 -set mismatch 1 -dump_cnf "+str(cnf))
        gen=run(["yosys","-p",cmd],cpu,CNF_EXPORT_CAP,args.out/(case["id"]+".yosys.log"))
        case_record["cnf_export"]={"seconds":gen["seconds"],"timeout":gen["timeout"],
                                   "return_code":gen["return_code"],"max_rss_kb":gen["max_rss_kb"]}
        if cnf.exists() and cnf.stat().st_size>0:
            try:case_record["cnf"]=dimacs_meta(cnf)
            except ValueError:case_record["cnf"]=None
        print("STRESS_SOURCE",case["id"],"width",case["input_bits"],
              "CNF",case_record["cnf"],"export_s",gen["seconds"],flush=True)
        persist()
        for repeat in range(REPEATS):
            order=list(ARMS) if repeat==0 else list(reversed(ARMS))
            for arm in order:
                logname=args.out/(case["id"]+"_"+arm+"_r"+str(repeat)+".log")
                if arm=="CircuitCheck":
                    r=run_circuitcheck(source,
                        args.out/(case["id"]+"_circuitcheck_r"+str(repeat)),
                        cpu,CAP,case["id"],root)
                elif case_record["cnf"] is None:
                    r={"status":"CNF_EXPORT_FAILED","seconds":0,"timeout":False,
                       "return_code":None,"max_rss_kb":None}
                else:
                    executable=args.kissat if arm=="Kissat" else args.cadical
                    trial=run([executable,cnf],cpu,CAP,logname)
                    stat=result_status(trial["stdout"],trial["return_code"],trial["timeout"])
                    r={"status":stat,"seconds":trial["seconds"],"timeout":trial["timeout"],
                       "return_code":trial["return_code"],"max_rss_kb":trial["max_rss_kb"],
                       "sat_witness_checked":verify_sat(cnf,trial["stdout"]) if stat=="SAT" else None}
                    if stat=="SAT" and r["sat_witness_checked"] is not True:
                        raise RuntimeError("SAT_WITNESS_INVALID "+case["id"]+" "+arm)
                expected=("DIFFERENT" if case["fault"] else "EQUIVALENT") if arm=="CircuitCheck" else (
                    "SAT" if case["fault"] else "UNSAT")
                if r["status"] in ("SAT","UNSAT","DIFFERENT","EQUIVALENT") and r["status"]!=expected:
                    raise RuntimeError("UNSOUND_OR_WRONG_VERDICT "+case["id"]+" "+arm+" "+r["status"])
                row={"arm":arm,"repeat":repeat,"status":r["status"],"seconds":round(r["seconds"],6),
                     "expected":expected,"max_rss_kb":r.get("max_rss_kb"),
                     "timed_out":r.get("timeout"),
                     "sat_witness_checked":r.get("sat_witness_checked"),
                     "netlist_cert_replayed":r.get("netlist_cert_replayed",False),
                     "independent_standard_unsat_certificate":False}
                case_record["trials"].append(row);persist()
                print("STRESS_TRIAL",case["id"],arm,repeat,row["status"],
                      row["seconds"],"s maxrss_kb",row["max_rss_kb"],
                      "cert",row["netlist_cert_replayed"],flush=True)
    print("STRESS_SHARD_COMPLETE",args.shard,len(data["cases"]),flush=True)

def aggregate(args):
    frozen=json.loads(args.manifest.read_text())
    by_id={}
    for shard_id in range(args.shards):
        # Download-artifact retains the full artifact name as its folder.
        base=args.combined/("circuitcheck-stress-shard-"+str(shard_id))
        file=base/"rows.json"
        if not file.exists():file=base/"results"/"rows.json"
        if not file.exists():raise RuntimeError("MISSING_SHARD_FILE "+str(base))
        doc=json.loads(file.read_text())
        if doc["shard"]!=shard_id or doc["frozen_manifest_sha256"]!=sha(args.manifest):
            raise RuntimeError("FROZEN_MANIFEST_MISMATCH "+str(shard_id))
        for row in doc["cases"]:
            if row["id"] in by_id:raise RuntimeError("DUPLICATE_CASE "+row["id"])
            by_id[row["id"]]=row
    if set(by_id)!={r["id"] for r in frozen["cases"]}:
        raise RuntimeError("MISSING_CASES")
    results={"audit_only":True,"original_ci_run_id":45245092918,"protocol":frozen["protocol"],"manifest_sha256":sha(args.manifest),
             "comparison_note":"same RTL, distinct proof-vs-CNF representations; SAT backends exclude Yosys CNF export cost",
             "cases":by_id,"matched":{}}
    report=["# DRNAS CircuitCheck stress: 64..2048 input bits",
        "",
        "Synthetic CRC/LFSR circuits, generated and frozen before solver runs.",
        "All arms pinned to a single logical CPU; two repetitions; limit 30s per arm.",
        "CircuitCheck time includes synthesizing the RTL netlist, ANF analysis AND independent netlist proof replay.",
        "Kissat/CaDiCaL time is solver-only on a pre-exported Yosys DIMACS. CNF export time is reported separately.",
        "**Important: proof and SAT solvers use different representations of the SAME RTL. Ratios are application-pipeline observations, not same-CNF speedups.**",
        "Kissat/CaDiCaL UNSAT statuses lack an independent standard proof in this test; CircuitCheck proofs are Yosys-netlist-level only.",
        "",
        "| Family | Inputs | Type | CNF vars | CNF clauses | DRNAS (2×) | Kissat (2×) | CaDiCaL (2×) | CNF export |",
        "|---|---:|---|---:|---:|---|---|---|---:|"]
    scored={arm:{"par2_s":0,"solved":0,"attempts":0,"timeout":0,"memory_max_kb":0}
            for arm in ARMS}
    total_matched=0
    for case in frozen["cases"]:
        row=by_id[case["id"]]
        trials=row["trials"]
        if len(trials)!=REPEATS*len(ARMS):
            raise RuntimeError("INCOMPLETE_TRIALS "+case["id"])
        string={}
        comparable=(row["cnf"] is not None and
                    row["cnf_export"]["return_code"]==0 and
                    not row["cnf_export"]["timeout"])
        for arm in ARMS:
            arm_trials=sorted([t for t in trials if t["arm"]==arm],key=lambda t:t["repeat"])
            if [t["repeat"] for t in arm_trials]!=list(range(REPEATS)):
                raise RuntimeError("REPEAT_MISSING "+case["id"]+" "+arm)
            rendered=[]
            for t in arm_trials:
                ans=t["status"];seconds=t["seconds"]
                done=(ans==t["expected"] and seconds<=CAP and
                      (arm!="CircuitCheck" or t["netlist_cert_replayed"] is True))
                if arm!="CircuitCheck" and ans=="SAT" and t["sat_witness_checked"] is not True:
                    raise RuntimeError("UNCHECKED_SAT "+case["id"])
                if comparable:
                    scored[arm]["par2_s"]+=seconds if done else 2*CAP
                    scored[arm]["attempts"]+=1
                    scored[arm]["solved"]+=int(done)
                    scored[arm]["timeout"]+=int(ans=="TIMEOUT")
                    scored[arm]["memory_max_kb"]=max(scored[arm]["memory_max_kb"],t["max_rss_kb"] or 0)
                rendered.append(ans+" "+str(round(seconds,3))+"s")
            string[arm]=" / ".join(rendered)
        if comparable:total_matched+=1
        cnf=row["cnf"] or {}
        report.append("| "+case["family"]+" | "+str(case["input_bits"])+" | "+
            ("SAT-control" if case["fault"] else "UNSAT-equivalence")+" | "+
            str(cnf.get("vars","—"))+" | "+str(cnf.get("clauses","—"))+" | "+
            string["CircuitCheck"]+" | "+string["Kissat"]+" | "+string["CaDiCaL"]+" | "+
            str(round(row["cnf_export"]["seconds"],2))+"s |")
    results["matched"]={"comparable_cases":total_matched,"scores":scored}
    report+=["","## Matched-PAR2 of cases with successfully exported CNF",
       "",
       "| Arm | Certified/reported solved | Attempts | PAR-2 (s) | Timeouts | Max RSS (MB) |",
       "|---|---:|---:|---:|---:|---:|"]
    for arm,val in scored.items():
        report.append("| "+arm+" | "+str(val["solved"])+" | "+
                      str(val["attempts"])+" | "+str(round(val["par2_s"],3))+
                      " | "+str(val["timeout"])+" | "+
                      str(round(val["memory_max_kb"]/1024,1))+" |")
    report += ["","A timeout counts as 2×30s in PAR-2, not the actual unknown finish time.",
       "Do not infer 2^n search from input width alone; SAT complexity depends on encoding.",
       "All unknowns, regressions, CNF-export errors and solver timeouts are retained.",
       ""]
    args.output.write_text(json.dumps(results,indent=2)+"\n")
    args.report.write_text("\n".join(report))
    print(args.report.read_text(),flush=True)

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    a=sub.add_parser("shard")
    a.add_argument("--manifest",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    a.add_argument("--shard",type=int,required=True)
    a.add_argument("--shards",type=int,default=4)
    a.add_argument("--kissat",type=Path,required=True)
    a.add_argument("--cadical",type=Path,required=True)
    a=sub.add_parser("aggregate")
    a.add_argument("--manifest",type=Path,required=True)
    a.add_argument("--combined",type=Path,required=True)
    a.add_argument("--shards",type=int,default=4)
    a.add_argument("--output",type=Path,required=True)
    a.add_argument("--report",type=Path,required=True)
    x=p.parse_args()
    if x.mode=="shard":shard(x)
    else:aggregate(x)

if __name__=="__main__":
    main()
