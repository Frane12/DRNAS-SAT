#!/usr/bin/env python3
"""REAL5Q independent local polynomial gate-cone SAT baseline experiment.

The source is each ORIGINAL REAL4 Yosys gate netlist, not a synthetic
quadratic design. Exact gate cones are checked against independently
replayed REAL5Q polynomials. Identical exported CNF for Kissat and CaDiCaL
(two repeats, one logical CPU, 10s per attempt), plus Yosys SAT verification.
The original gate-level / netlist->source trust boundary is explicit.
UNSAT statuses from SAT solvers have no separate DRAT/LRAT checker.
"""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from stress_run import run,dimacs_meta,result_status,verify_sat

CAP=10.0
CNF_CAP=30.0
PROVE_CAP=30.0
CASES=("aes_sbox","uart_tx","axis_fifo","picorv32","sha256_w_mem")

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--originals",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--kissat",required=True,type=Path)
    p.add_argument("--cadical",required=True,type=Path)
    a=p.parse_args()
    root=a.originals.resolve()
    a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    kissat=a.kissat.resolve();cadical=a.cadical.resolve()
    cpu=min(os.sched_getaffinity(0))
    summary={"protocol":"REAL5Q_PREVIOUS_REAL4_DEVELOPMENT_SAME_CNF_SAT",
             "provenance_run":45344738069,
             "one_cpu":cpu,"per_sat_limit_seconds":CAP,
             "binary_sha256":{"Kissat":sha(kissat),"CaDiCaL":sha(cadical)},
             "cases":{}}
    for name in CASES:
        source=root/name
        assert source.is_dir() and (source/"real5q_certificate.json").is_file(),name
        assert (source/"netlist.json").is_file()
        work=a.out/name;work.mkdir(exist_ok=True)
        generator=run([sys.executable,Path(__file__).parent/"real5q_miter.py",
                       "--folder",source,"--out",work/"candidate_cones"],
                      cpu,35,work/"candidate_generation.log")
        if generator["return_code"]!=0 or generator["timeout"]:
            raise RuntimeError("POLYNOMIAL_CERT_NOT_VALIDATED "+name)
        manifest=json.loads((work/"candidate_cones/candidate_manifest.json").read_text())
        record={"original_gate_netlist_sha256":sha(source/"netlist.json"),
                "source_polynomial_certificate_sha256":sha(source/"real5q_certificate.json"),
                "selected_cones":manifest,
                "trials":[]}
        summary["cases"][name]=record
        def persist():
            (a.out/"results.json").write_text(json.dumps(summary,indent=2)+"\n")
        for c in manifest:
            if c["status"]!="GENERATED":continue
            cone=work/"candidate_cones"/c["id"]
            miter=cone/"miter.v"
            if sha(miter)!=c["miter_sha256"]:
                raise RuntimeError("MUTATED_REAL_GATE_CONE")
            cnf=cone/"identity.cnf"
            expression=("read_verilog -sv "+str(miter)+"; hierarchy -check -top miter; "
                        "proc; flatten; opt; sat -timeout 1 -set mismatch 1 -dump_cnf "+str(cnf))
            export=run(["yosys","-p",expression],cpu,CNF_CAP,cone/"yosys_cnf_export.log")
            c["export_time_s"]=export["seconds"]
            c["cnf_status"]="TIMEOUT" if export["timeout"] else (
                 "EXPORTED" if export["return_code"]==0 and cnf.is_file() else "CNF_FAILED")
            if c["cnf_status"]!="EXPORTED":
                persist()
                continue
            c["cnf"]=dimacs_meta(cnf)
            # This is an independent original-gate-cone Yosys SAT check,
            # not a proof about the full original source HDL.
            checker=("read_verilog -sv "+str(miter)+"; hierarchy -check -top miter; "
                     "proc; flatten; opt; sat -verify -prove mismatch 0 -timeout 12")
            verified=run(["yosys","-p",checker],cpu,PROVE_CAP,cone/"yosys_prove.log")
            c["yosys_formal"]={
                "status":"VERIFIED_LOCAL_EQUAL" if (verified["return_code"]==0 and
                      not verified["timeout"]) else "UNKNOWN",
                "seconds":verified["seconds"]}
            for repeat in (0,1):
                arms=("Kissat","CaDiCaL") if repeat==0 else ("CaDiCaL","Kissat")
                for arm in arms:
                    executable=kissat if arm=="Kissat" else cadical
                    result=run([executable,cnf],cpu,CAP,cone/(arm+"_r"+str(repeat)+".log"))
                    status=result_status(result["stdout"],result["return_code"],result["timeout"])
                    witness=verify_sat(cnf,result["stdout"]) if status=="SAT" else None
                    if status=="SAT":
                        raise RuntimeError("REAL5Q_FALSE_QUADRATIC_RELATION_SAT "+name+" "+c["id"])
                    trial={"source":name,"cone":c["id"],"arm":arm,"repeat":repeat,
                           "status":status,"seconds":result["seconds"],
                           "sat_witness_checked":witness,
                           "standard_unsat_proof_checked":False}
                    record["trials"].append(trial)
                    persist()
                    print("REAL5Q_ORIGINAL_GATE_CNF",name,c["id"],
                          arm,repeat,status,result["seconds"],flush=True)
        persist()
        print("REAL5Q_SAT_DEVELOPMENT_CASE_COMPLETE",name,
              "sampled",len(manifest),"solver_attempts",len(record["trials"]),flush=True)
    assert set(summary["cases"])==set(CASES)
    lines=["# REAL5-Q real ORIGINAL gate-cone SAT check (development, not blind)",
           "",
           "REAL5Q examines Yosys 0.9 originally frozen external RTL gate-netlists.",
           "For each up to 3 candidate outputs, SAME local gate miter and CNF goes",
           "to Kissat and CaDiCaL (2 repeats, one CPU, 10s per attempt),",
           "with additional Yosys prove mismatch=0. Source synthesis not rerun.",
           "No full original FPGA SAT/UNSAT inference; cut outputs freely variable.",
           "",
           "| Original HDL | Sampled quadratic identities | Verified by Yosys | Kissat UNSAT | CaDiCaL UNSAT | Other |",
           "|---|---:|---:|---:|---:|---|"]
    for name,row in summary["cases"].items():
        candidate=row["selected_cones"]
        proved=sum(x.get("yosys_formal",{}).get("status")=="VERIFIED_LOCAL_EQUAL" for x in candidate)
        counts={arm:sum(x["status"]=="UNSAT" and x["arm"]==arm for x in row["trials"])
                for arm in ("Kissat","CaDiCaL")}
        other=sum(x["status"]!="UNSAT" for x in row["trials"])
        lines.append(f"| {name} | {len(candidate)} | {proved} | {counts['Kissat']} | {counts['CaDiCaL']} | {other} |")
    lines+=["","## What this DOES NOT prove",
            "These are local exact degree2 polynomial identities on selected",
            "frozen Yosys cones, not whole-project equivalence, hardware",
            "performance, inter-cycle invariants or solver-comparable",
            "same input SAT proof speedups. Zero successes stay visible."]
    (a.out/"SAT_REPORT.md").write_text("\n".join(lines))
    print("REAL5Q_FINAL_SAT_SAME_CNF_DEVELOPMENT_AUDIT",flush=True)

if __name__=="__main__":main()
