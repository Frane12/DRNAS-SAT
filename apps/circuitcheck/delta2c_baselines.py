#!/usr/bin/env python3
"""Kissat + CaDiCaL always-on controls for DELTA2-C inductive-step study.

The SAT baselines receive *the same unchanged frozen RTL* via a Yosys miter
CNF; local 1/2/4/8-step comparisons receive Yosys miter CNFs constructed
from DELTA2-C's proven block RTL. This is an application-level comparison
only: DELTA2-C sees a strict source grammar and gate nets, SAT solvers see
the derived DIMACS. Never assert same-DIMACS speedup.

Single logical CPU per attempt, two repeats with reverse arm order on full
original, 30s per SAT solver invocation, 10s per local block solver.
SAT witnesses must satisfy EVERY original DIMACS clause; bare UNSAT is not
independently certified until DRAT/LRAT is supplied.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from stress_run import run, dimacs_meta, result_status, verify_sat

CAP=30
BLOCK_CAP=10

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def export(source:Path,cnf:Path,top:str,cpu:int,log:Path):
    script=("read_verilog -sv "+str(source.resolve())+
            "; hierarchy -check -top "+top+
            "; proc; flatten; opt; sat -timeout 1 -set mismatch 1 -dump_cnf "+
            str(cnf.resolve()))
    r=run(["yosys","-p",script],cpu,120,log)
    meta={"seconds":r["seconds"],"timeout":r["timeout"],"return_code":r["return_code"],
          "max_rss_kb":r["max_rss_kb"]}
    if r["return_code"]!=0 or r["timeout"] or not cnf.is_file():
        return meta,None
    try:
        info=dimacs_meta(cnf)
        return meta,info
    except (ValueError,OSError):
        return meta,None

def trial(arm:str,exe:Path,cnf:Path,cpu:int,cap:float,log:Path,expected:str):
    r=run([exe,cnf],cpu,cap,log)
    status=result_status(r["stdout"],r["return_code"],r["timeout"])
    checked=(verify_sat(cnf,r["stdout"]) if status=="SAT" else None)
    if status=="SAT" and checked is not True:
        raise RuntimeError("INVALID_SAT_WITNESS "+arm)
    if status in ("SAT","UNSAT") and status!=expected:
        raise RuntimeError("INCORRECT_SAT_VERDICT "+arm+" "+status+" expected "+expected)
    return {"arm":arm,"status":status,"seconds":r["seconds"],
            "timeout":r["timeout"],"max_rss_kb":r["max_rss_kb"],
            "return_code":r["return_code"],"sat_witness_checked":checked,
            "standard_unsat_proof_checked":False}

def case_main(args):
    out=args.out.resolve();out.mkdir(exist_ok=True,parents=True)
    source=args.rtl.resolve()
    checks=args.proofs.resolve()
    if not source.is_file():
        raise RuntimeError("MISSING_FROZEN_SOURCE")
    if not checks.is_dir():
        raise RuntimeError("MISSING_DELTA2C_PROOFS")
    result={"protocol":"DRNAS_DELTA2C_SAT_BASELINE_V1",
            "source_sha256":sha(source),"source_name":source.name,
            "proof_report_sha256":sha(checks/"delta2c_report.json"),
            "single_cpu":min(os.sched_getaffinity(0)),
            "full_limit_s":CAP,"block_limit_s":BLOCK_CAP,
            "binary_sha256":{"kissat":sha(args.kissat),"cadical":sha(args.cadical)},
            "full":{},"blocks":{}}
    cpu=result["single_cpu"]
    # Yosys miter from the ORIGINAL full RTL. No source-rewriting or
    # reuse of the generated linear model for SAT baseline.
    gen_dir=out/"original";gen_dir.mkdir(exist_ok=True)
    target=gen_dir/"original.v"
    target.write_bytes(source.read_bytes())
    cnf=gen_dir/"original.cnf"
    export_time,meta=export(target,cnf,"miter",cpu,gen_dir/"yosys.log")
    result["full"]["cnf_export"]=export_time
    result["full"]["cnf"]=meta
    result["full"]["trials"]=[]
    if meta is None:
        result["full"]["status"]="CNF_EXPORT_FAILED"
    else:
        for rep in range(2):
            order=["Kissat","CaDiCaL"] if rep==0 else ["CaDiCaL","Kissat"]
            for arm in order:
                exe=args.kissat if arm=="Kissat" else args.cadical
                t=trial(arm,exe,cnf,cpu,CAP,
                        gen_dir/f"{arm}_r{rep}.log",args.expected)
                t["repeat"]=rep
                result["full"]["trials"].append(t)
                (out/"baseline.json").write_text(json.dumps(result,indent=2)+"\n")
                print("DELTA2C_FULL_BASELINE",source.name,arm,rep,t["status"],t["seconds"],
                      "SAT_witness",t["sat_witness_checked"],flush=True)
    # The local "block" SAT formula compares two independently synthesized
    # representations of one, two, four or eight transitions, with
    # arbitrary initial register bits and arbitrary K input bits.
    for k in (1,2,4,8):
        proof=checks/f"k{k}"
        local=proof/"block.v"
        if not local.is_file():
            raise RuntimeError("BLOCK_PROOF_MISSING "+str(k))
        width=json.loads((checks/"delta2c_report.json").read_text())["state_bits"]
        work=out/f"block_{k}";work.mkdir(exist_ok=True)
        raw=local.read_text()
        miter=(
            f"module miter(input wire [{width-1}:0] a_state_in,"
            f" input wire [{k-1}:0] b_data, output wire mismatch);\n"
            f"wire [{width-1}:0] a, b;\n"
            f"delta2c_raw_{k} r(.a_state_in(a_state_in),.b_data(b_data),.y_state(a));\n"
            f"delta2c_math_{k} c(.a_state_in(a_state_in),.b_data(b_data),.y_state(b));\n"
            f"assign mismatch = |(a ^ b);\nendmodule\n"
        )
        (work/"local.v").write_text(raw+"\n"+miter)
        cl=work/"local.cnf"
        gentime,info=export(work/"local.v",cl,"miter",cpu,work/"yosys.log")
        block={"size":k,"original_block_sha256":sha(local),
               "cnf_export":gentime,"cnf":info,"trials":[]}
        result["blocks"][str(k)]=block
        if info is None:
            block["status"]="CNF_EXPORT_FAILED"
        else:
            for arm in ("Kissat","CaDiCaL"):
                exe=args.kissat if arm=="Kissat" else args.cadical
                runinfo=trial(arm,exe,cl,cpu,BLOCK_CAP,
                    work/f"{arm}.log","UNSAT")
                block["trials"].append(runinfo)
                print("DELTA2C_BLOCK_BASELINE",k,arm,runinfo["status"],
                      runinfo["seconds"],flush=True)
        (out/"baseline.json").write_text(json.dumps(result,indent=2)+"\n")
    (out/"baseline.json").write_text(json.dumps(result,indent=2)+"\n")
    print("DELTA2C_SAT_BASELINE_COMPLETE",source.name,flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rtl",type=Path,required=True)
    p.add_argument("--proofs",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--kissat",type=Path,required=True)
    p.add_argument("--cadical",type=Path,required=True)
    p.add_argument("--expected",choices=["SAT","UNSAT"],required=True)
    args=p.parse_args()
    args.kissat=args.kissat.resolve();args.cadical=args.cadical.resolve()
    case_main(args)

if __name__=="__main__":
    main()
