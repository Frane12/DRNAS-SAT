#!/usr/bin/env python3
"""Real RTL holdout: DELTA1 affine netlist equivalence vs Kissat and CaDiCaL.

The *unchanged third-party lfsr.v* is used for all arms. We only generate
external harnesses that instantiate its two native RTL implementation styles.
Synthesis Yosys 0.33 on GitHub Ubuntu; one logical CPU per arm, two repeats,
30s wall cap. SAT models are checked on every clause of the original miter
CNF. UNSAT solver statuses are not independently DRAT/LRAT checked.
The affine engine sees Yosys gate JSON, baselines see Yosys miter DIMACS,
so results are NOT algorithmic speedups on identical CNF representations.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
from stress_run import run,dimacs_meta,result_status,verify_sat

LIMIT=30.0
EXPORT_LIMIT=120.0
REPS=2
ARMS=["DRNAS_DELTA1","Kissat","CaDiCaL"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_d1(upstream,src,root,cpu,repeat):
    folder=root/f"delta1_{repeat}"
    folder.mkdir(exist_ok=True)
    result=run([sys.executable,Path(__file__).parent/"delta1.py",
                "--rtl",upstream,src,"--reference","reference",
                "--candidate","candidate","--out",folder/"proof"],
               cpu,LIMIT,folder/"delta1.log")
    output={"status":"TIMEOUT" if result["timeout"] else "UNKNOWN",
            "seconds":result["seconds"],"memory_kb":result["max_rss_kb"],
            "proof_replayed":False}
    if result["timeout"]:return output
    rpath=folder/"proof/delta1_report.json"
    if not rpath.exists():return output
    rep=json.loads(rpath.read_text())
    verdict=rep["status"]
    code={"EQUIVALENT_NETLIST":0,"DIFFERENT_NETLIST":10}
    if verdict not in code or result["return_code"]!=code[verdict]:
        output["reason"]=rep.get("reason","invalid status")
        return output
    remaining=LIMIT-result["seconds"]
    if remaining<0.08:
        output["status"]="TIMEOUT";return output
    proof=run([sys.executable,Path(__file__).parent/"delta1_verify.py",
               folder/"proof"],cpu,remaining,folder/"replay.log")
    output["seconds"]=round(result["seconds"]+proof["seconds"],6)
    output["memory_kb"]=max(result["max_rss_kb"] or 0,proof["max_rss_kb"] or 0)
    if proof["timeout"]:
        output["status"]="TIMEOUT";return output
    vpath=folder/"proof/delta1_verification.json"
    if proof["return_code"] or not vpath.exists():
        output["status"]="REPLAY_FAILED";return output
    verified=json.loads(vpath.read_text())
    check=("CHECKED_EQUIVALENT_NETLIST" if verdict=="EQUIVALENT_NETLIST"
           else "CHECKED_DIFFERENT_NETLIST")
    if verified["status"]!=check:
        output["status"]="REPLAY_FAILED";return output
    output["status"]="EQUIVALENT" if verdict=="EQUIVALENT_NETLIST" else "DIFFERENT"
    output["proof_replayed"]=True
    output["certificate_sha256"]=sha(folder/"proof/delta1_certificate.json")
    output["gate_netlist_sha256"]=sha(folder/"proof/netlist.json")
    return output


def export_cnf(upstream,src,out,cpu):
    cnf=out/"original.cnf"
    script=("read_verilog -sv "+str(upstream)+" "+str(src)+
            "; hierarchy -check -top miter; proc; flatten; opt; "
            "sat -timeout 1 -set mismatch 1 -dump_cnf "+str(cnf))
    p=run(["yosys","-p",script],cpu,EXPORT_LIMIT,out/"yosys_cnf_export.log")
    value={"export_seconds":p["seconds"],
           "returncode":p["return_code"],"timeout":p["timeout"],
           "memory_kb":p["max_rss_kb"],"cnf":None}
    if p["return_code"]==0 and not p["timeout"] and cnf.exists():
        value["cnf"]=dimacs_meta(cnf)
    return value,cnf


def run_case(entry,manifest,args,cpu):
    label=entry["id"]
    src=Path(entry["path"]).resolve()
    library=next(i for i in manifest["upstream"] if i["id"]==entry["source_id"])
    upstream=Path(library["local_path"]).resolve()
    if not src.exists() or sha(src)!=entry["sha256"]:
        raise RuntimeError("WRAPPER_CHANGED "+label)
    if not upstream.exists() or subprocess.run(
        ["git","hash-object",str(upstream)],capture_output=True,text=True
    ).stdout.strip()!=library["blob_sha1"]:
        raise RuntimeError("UNPINNED_UPSTREAM "+label)
    folder=args.out/(label)
    folder.mkdir(exist_ok=True)
    source_state={"case":label,"entry":entry,"upstream":library,
                  "cnf":None,"cnf_export":None,"trials":[]}
    def save():
        (folder/"results.json").write_text(json.dumps(source_state,indent=2)+"\n")
    exp,cnf=export_cnf(upstream,src,folder,cpu)
    source_state["cnf"]=exp["cnf"]
    source_state["cnf_export"]={k:v for k,v in exp.items() if k!="cnf"}
    save()
    print("REAL1_CNF",label,source_state["cnf"],
          "export_seconds",exp["export_seconds"],flush=True)
    for rep in range(REPS):
        arms=ARMS if rep==0 else ARMS[::-1]
        for arm in arms:
            if arm=="DRNAS_DELTA1":
                t=compare_d1(upstream,src,folder,cpu,rep)
            elif source_state["cnf"] is None:
                t={"status":"CNF_EXPORT_FAILED","seconds":0,"memory_kb":None}
            else:
                executable=args.kissat if arm=="Kissat" else args.cadical
                p=run([executable,cnf],cpu,LIMIT,folder/f"{arm}_{rep}.log")
                status=result_status(p["stdout"],p["return_code"],p["timeout"])
                witness=verify_sat(cnf,p["stdout"]) if status=="SAT" else None
                if status=="SAT" and witness is not True:
                    raise RuntimeError("BAD_SAT_WITNESS "+label+" "+arm)
                t={"status":status,"seconds":p["seconds"],"memory_kb":p["max_rss_kb"],
                   "sat_witness_checked":witness,"proof_replayed":False,
                   "standard_unsat_proof_checked":False}
            expected=("DIFFERENT" if entry["fault"] else "EQUIVALENT") if arm=="DRNAS_DELTA1" else (
                "SAT" if entry["fault"] else "UNSAT")
            if t["status"] in ("SAT","UNSAT","DIFFERENT","EQUIVALENT") and t["status"]!=expected:
                raise RuntimeError("INCORRECT_VERDICT "+label+" "+arm+" "+t["status"])
            if arm=="DRNAS_DELTA1" and t["status"]==expected and t.get("proof_replayed") is not True:
                raise RuntimeError("UNCHECKED_DRNAS_PROOF")
            row={"arm":arm,"repeat":rep,"expected":expected,**t}
            source_state["trials"].append(row)
            save()
            print("REAL1_TRIAL",label,arm,rep,row["status"],
                  round(row["seconds"],6),"s",flush=True)
    return source_state


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--shards",type=int,default=4)
    p.add_argument("--kissat",type=Path,required=True)
    p.add_argument("--cadical",type=Path,required=True)
    args=p.parse_args()
    args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.manifest.read_text())
    assert manifest["protocol"]=="DELTA_REAL1_UPSTREAM_VERILOG_20261124"
    if not (0<=args.shard<args.shards):
        raise RuntimeError("invalid shard")
    cpu=min(os.sched_getaffinity(0))
    summary={"protocol":manifest["protocol"],"manifest_sha256":sha(args.manifest),
             "shard":args.shard,"shards":args.shards,"cpu":cpu,
             "runner":platform.platform(),
             "binary_sha256":{"Kissat":sha(args.kissat),
                              "CaDiCaL":sha(args.cadical)},
             "tool_sha256":{name:sha(Path(__file__).parent/name)
                for name in ("delta1.py","delta1_engine.py","delta1_verify.py")},
             "cases":[]}
    for i,case in enumerate(manifest["cases"]):
        if i%args.shards != args.shard:continue
        result=run_case(case,manifest,args,cpu)
        summary["cases"].append(result)
        (args.out/"rows.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("REAL1_SHARD_COMPLETE",args.shard,len(summary["cases"]),flush=True)


if __name__=="__main__":
    main()
