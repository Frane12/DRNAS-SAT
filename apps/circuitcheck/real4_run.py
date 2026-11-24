#!/usr/bin/env python3
"""REAL4 blind six-project experiment, no family-specific tuning.

A previously locked gate-netlist detector is run verbatim on six untouched
public FPGA/CPU/crypto HDL files frozen AFTER the detector was tested.
Record synthesis failures and UNKNOWN honestly; do not remove them.
For each independently replayed affine cone, generate an exact Yosys-gate
identity miter, feed the SAME DIMACS to Kissat/CaDiCaL, two repeats, one CPU.
SAT reported on an affine identity constitutes a verification alarm.
A CDCL result is never treated as a REAL4 structural success.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,sys,time
from pathlib import Path
from stress_run import run,dimacs_meta,result_status,verify_sat

SYNTH_LIMIT=100
ENGINE_LIMIT=35
REPLAY_LIMIT=35
CNF_LIMIT=25
SAT_LIMIT=10
REPS=2

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run_source(entry,args,root,cpu):
    name=entry["id"]
    src=args.sources/(name+".sv")
    if sha(src)!=entry["sha256"]:
        raise RuntimeError("FROZEN_ORIGINAL_CHANGED "+name)
    work=args.out/name
    work.mkdir(exist_ok=True,parents=True)
    report={
       "id":name,"source_repo":entry["repo"],"source_commit":entry["commit"],
       "original_sha256":entry["sha256"],"source_git_blob_sha1":entry["blob"],
       "top":entry["top"],"domain":entry["domain"],"protocol":"REAL4_BLIND_SOURCE_V1",
       "synthesis":{"status":"NOT_RUN"},
       "affine_analysis":{"status":"NOT_RUN"},
       "independent_replay":{"status":"NOT_RUN"},
       "cones":[],"baseline_attempts":0,
       "supported_gate_certificate_is_not_full_source_equivalence":True}
    def store():
        (work/"result.json").write_text(json.dumps(report,indent=2)+"\n")
    def external(command,seconds,log):
        return run(command,cpu,seconds,work/log)
    print("REAL4_ATTEMPT_ORIGINAL",name,entry["sha256"],flush=True)
    start=time.perf_counter()
    netfile=work/"netlist.json"
    # This pass does not impose any source-specific macro, parameters,
    # rewrite, wrapper, hidden reference or special submodule handling.
    script=("read_verilog -sv "+str(src)+"; "
            "hierarchy -check -top "+entry["top"]+"; "
            "proc; flatten; opt; techmap; opt; write_json "+str(netfile))
    synth=external(["yosys","-p",script],SYNTH_LIMIT,"yosys.log")
    report["synthesis"]={"status":"TIMEOUT" if synth["timeout"] else
       ("OK" if synth["return_code"]==0 and netfile.exists() else "FRONTEND_UNSUPPORTED"),
       "seconds":synth["seconds"],"max_rss_kb":synth["max_rss_kb"],
       "return_code":synth["return_code"]}
    store()
    if report["synthesis"]["status"]!="OK":
        report["elapsed_seconds"]=round(time.perf_counter()-start,5)
        store()
        print("REAL4_SOURCE_FAILED_PREPROCESS",name,report["synthesis"]["status"],flush=True)
        return report
    report["netlist_sha256"]=sha(netfile)
    certificate=work/"real4_certificate.json"
    ana=external([sys.executable,root/"real4_islands.py",
                  "--netlist",netfile,"--top",entry["top"],
                  "--out",certificate],ENGINE_LIMIT,"real4_analyze.log")
    if not certificate.exists():
        report["affine_analysis"]={"status":"ERROR","seconds":ana["seconds"]}
        store()
        return report
    cert=json.loads(certificate.read_text())
    report["affine_analysis"]={
       "status":"TIMEOUT" if ana["timeout"] else cert["status"],
       "seconds":ana["seconds"],"netlist_sha256":report["netlist_sha256"],
       "metrics":cert.get("metrics",{}),"reason":cert.get("reason")}
    store()
    if ana["return_code"]!=0 or ana["timeout"] or cert["status"]=="UNKNOWN":
        report["elapsed_seconds"]=round(time.perf_counter()-start,5)
        store()
        return report
    replay=external([sys.executable,root/"real4_verify.py",work],
                    REPLAY_LIMIT,"real4_replay.log")
    status="CHECKED" if replay["return_code"]==0 and not replay["timeout"] else "REPLAY_FAILURE"
    report["independent_replay"]={"status":status,"seconds":replay["seconds"],
           "verified_file_sha256":sha(work/"real4_verification.json") if (
               work/"real4_verification.json").is_file() else None}
    store()
    if status!="CHECKED":
        raise RuntimeError("UNTRUSTED_AFFINE_CERTIFICATE "+name)
    generator=external([sys.executable,root/"real4_miter.py",
                        "--folder",work,"--out",work/"cones"],20,"real4_miter.log")
    if generator["return_code"]!=0:
        report["cone_generation_status"]="FAILED"
        store()
        return report
    manifest=json.loads((work/"cones/cones.json").read_text())
    for c in manifest:
        record=dict(c)
        record["cnf_export"]={"status":"NOT_RUN"}
        record["baselines"]=[]
        report["cones"].append(record)
        if c["status"]!="GENERATED":
            store()
            continue
        cwd=work/"cones"/c["name"]
        miter_file=cwd/"miter.v"
        cnf=cwd/"miter.cnf"
        if sha(miter_file)!=c["miter_sha256"]:
            raise RuntimeError("LOCAL_CONE_MITER_MUTATED")
        cy=("read_verilog -sv "+str(miter_file)+"; hierarchy -check -top miter; "
            "proc; flatten; opt; sat -timeout 1 -set mismatch 1 -dump_cnf "+str(cnf))
        export=external(["yosys","-p",cy],CNF_LIMIT,"cones/"+c["name"]+"/yosys_cnf.log")
        record["cnf_export"]={"seconds":export["seconds"],
                             "status":"TIMEOUT" if export["timeout"] else
                              ("OK" if export["return_code"]==0 and cnf.is_file() else "FAILED")}
        if record["cnf_export"]["status"]=="OK":
            try:record["cnf"]=dimacs_meta(cnf)
            except (ValueError,OSError):record["cnf_export"]["status"]="BAD_DIMACS"
        store()
        if record["cnf_export"]["status"]!="OK":continue
        for repeat in range(REPS):
            order=("Kissat","CaDiCaL") if repeat==0 else ("CaDiCaL","Kissat")
            for arm in order:
                exe=args.kissat if arm=="Kissat" else args.cadical
                trial=external([exe,cnf],SAT_LIMIT,f"cones/{c['name']}/{arm}_{repeat}.log")
                decision=result_status(trial["stdout"],trial["return_code"],trial["timeout"])
                witness=verify_sat(cnf,trial["stdout"]) if decision=="SAT" else None
                if decision=="SAT":
                    record["baselines"].append({
                        "arm":arm,"repeat":repeat,"status":"SOUNDNESS_ALARM_SAT",
                        "seconds":trial["seconds"],"sat_model_verified":witness})
                    store()
                    raise RuntimeError("AFFINE_IDENTITY_CONTRADICTED_BY_SAT "+name)
                record["baselines"].append({
                    "arm":arm,"repeat":repeat,"status":decision,
                    "seconds":trial["seconds"],"sat_witness_checked":witness,
                    "standard_unsat_certificate_checked":False})
                report["baseline_attempts"]+=1
                store()
                print("REAL4_CUT_MITER",name,c["name"],arm,repeat,
                      decision,trial["seconds"],flush=True)
    report["elapsed_seconds"]=round(time.perf_counter()-start,5)
    store()
    summary=report["affine_analysis"].get("metrics",{})
    print("REAL4_SOURCE_COMPLETE",name,"global",summary.get("global_affine_external_and_state_probes"),
          "local",summary.get("local_affine_external_and_state_probes"),
          "cuts",summary.get("cutpoints"),"state_Q",summary.get("state_Q_bits"),
          "SAT_trials",report["baseline_attempts"],flush=True)
    return report

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--manifest",required=True,type=Path)
    a.add_argument("--sources",required=True,type=Path)
    a.add_argument("--out",required=True,type=Path)
    a.add_argument("--shard",type=int,required=True)
    a.add_argument("--shards",type=int,default=3)
    a.add_argument("--kissat",required=True,type=Path)
    a.add_argument("--cadical",required=True,type=Path)
    x=a.parse_args()
    x.sources=x.sources.resolve();x.out=x.out.resolve()
    x.out.mkdir(exist_ok=True,parents=True)
    x.kissat=x.kissat.resolve();x.cadical=x.cadical.resolve()
    doc=json.loads(x.manifest.read_text())
    assert doc["protocol"]=="DRNAS_REAL4_BLIND_EXTERNAL_6_V1"
    assert len(doc["cases"])==6 and doc["prelock_run_id"]==45339922757
    cpu=min(os.sched_getaffinity(0))
    root=Path(__file__).resolve().parent
    record={"protocol":doc["protocol"],"source_manifest_sha256":sha(x.manifest),
            "shard":x.shard,"shards":x.shards,"cpu":cpu,
            "binary_sha256":{"Kissat":sha(x.kissat),"CaDiCaL":sha(x.cadical)},
            "engine_sha256":{"real4_islands":sha(root/"real4_islands.py"),
                            "real4_verify":sha(root/"real4_verify.py")},
            "platform":platform.platform(),"cases":[]}
    for i,case in enumerate(doc["cases"]):
        if i%x.shards!=x.shard:continue
        result=run_source(case,x,root,cpu)
        record["cases"].append(result)
        (x.out/"rows.json").write_text(json.dumps(record,indent=2)+"\n")
    print("REAL4_SHARD_COMPLETE",x.shard,len(record["cases"]),flush=True)
if __name__=="__main__":main()
