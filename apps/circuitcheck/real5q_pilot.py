#!/usr/bin/env python3
"""REAL5-Q development replay on five already seen public FPGA netlists.

PREVIOUSLY SEEN corpus; no blind-performance claim. Real RTL gate-netlists
from REAL4 frozen run are read without any source rewriting. Fail-closed
bounded exact degree2 GF2 ANFs, independently verified via monomial-sets
implementation. Keep original HDMI FRONTEND_UNSUPPORTED in report.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path

CASES=("aes_sbox","uart_tx","axis_fifo","picorv32","sha256_w_mem")
CAP=90

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run(cmd,limit):
    start=time.perf_counter()
    try:
        r=subprocess.run([str(x) for x in cmd],capture_output=True,
                         text=True,timeout=limit,check=False)
        return {"seconds":round(time.perf_counter()-start,6),
                "exit_code":r.returncode,"timed_out":False,
                "stdout":r.stdout[-2000:],"stderr":r.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        return {"seconds":round(time.perf_counter()-start,6),
                "exit_code":None,"timed_out":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--originals",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args();x.out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parent
    outcome={"experiment":"REAL5Q_DEVELOPMENT_PREVIOUS_REAL4_NOT_BLIND",
             "original_run":45341226748,
             "degree_limit":2,"monomial_cap":96,
             "cases":{},"known_html_frontend_failure":"HDMI: FRONTEND_UNSUPPORTED"}
    for name in CASES:
        matches=list(x.originals.glob("real4-shard-*/results/"+name+"/netlist.json"))
        if len(matches)!=1:raise RuntimeError("ORIGINAL_REAL4_GATE_NETLIST_NOT_FOUND "+name)
        net=matches[0]
        source_dir=net.parent
        original=json.loads((source_dir/"real4_certificate.json").read_text())
        if sha(net)!=original["netlist_sha256"]:
            raise RuntimeError("REAL4_GATE_SHA_CHANGED")
        out=x.out/name;out.mkdir(exist_ok=True)
        shutil.copyfile(net,out/"netlist.json")
        top=original["top"]
        ana=run([sys.executable,root/"real5q_anf.py",
                 "--netlist",out/"netlist.json",
                 "--top",top,"--out",out/"real5q_certificate.json"],CAP)
        rec={"original_gate_sha256":sha(net),"top":top,"engine":ana,
             "status":"UNKNOWN","verification":None}
        if not ana["timed_out"] and ana["exit_code"]==0:
            c=json.loads((out/"real5q_certificate.json").read_text())
            rec["metrics"]=c.get("metrics",{})
            independent=run([sys.executable,root/"real5q_verify.py",out],CAP)
            rec["verification"]=independent
            if independent["exit_code"]!=0 or independent["timed_out"]:
                raise RuntimeError("BAD_REAL5Q_CERTIFICATE "+name+" "+repr(independent))
            rec["status"]="CHECKED_EXACT_QUADRATIC_ANF"
        outcome["cases"][name]=rec
        (x.out/"pilot.json").write_text(json.dumps(outcome,indent=2)+"\n")
        print("REAL5Q_DEVELOPMENT_CASE",name,rec["status"],
              rec.get("metrics",{}),"analysis_seconds",ana["seconds"],flush=True)
    if set(outcome["cases"])!=set(CASES):
        raise RuntimeError("EXCLUDED_PRIOR_FROZEN_CASE")
    lines=["# REAL5-Q exact quadratic Boolean algebra development corpus",
           "", "NOT BLIND. The five source gate-netlists are from the",
           "previous REAL4 experiment and were available before this algorithm.",
           "Each source is SHA matched and every successful polynomial",
           "is independently recomputed by a separate checker.",
           "",
           "| Original RTL | Analysis | Gate cells | Full input/FF state bits | Cut outputs | Global exact quadratic external probes | Local ANF probes | Internal sampled quadratic probes |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name in CASES:
        rec=outcome["cases"][name];m=rec.get("metrics",{})
        lines.append(f"| {name} | {rec['status']} | {m.get('cells','—')} | {m.get('input_basis_bits','—')} | "
                     f"{m.get('cut_outputs','—')} | {m.get('global_degree2_probes','—')} | "
                     f"{m.get('local_polynomial_probes','—')} | {m.get('sampled_internal_global_degree2','—')} |")
    lines+=["","Interpretation: degree2 gate identities are not a new",
            "whole-system SAT/UNSAT proof, temporal verification, or protocol signoff.",
            "Every nonaffine/cubic unresolved Boolean gate is a physical free cutpoint.",
            "Failed preprocessing or unsupported source remains an explicit outcome."]
    (x.out/"PILOT.md").write_text("\n".join(lines)+"\n")
    print("REAL5Q_FIVE_ORIGINAL_EXTERNAL_DEVELOPMENT_CASES_COMPLETE",flush=True)

if __name__=="__main__":main()
