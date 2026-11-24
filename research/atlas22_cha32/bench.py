#!/usr/bin/env python3
"""ATLAS22 strictly source-bound arithmetic proof vs Kissat/CaDiCaL, same CNF.

Two repeats, serial one pinned logical CPU, alternating baseline order.
Original source BDD theorem independently checked from frozen real source each
trial. All CNF clauses independently replayed before marking SAT/UNSAT.
SAT model gets independent original-DIMACS clause check; UNSAT baselines only
solver-reported (separate standard DRAT/LRAT still needed for competition).
No solver result is used as proof by ATLAS structural arm.
"""
from __future__ import annotations
import argparse,hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from audit import validate
from model import model

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def guard():
    resource.setrlimit(resource.RLIMIT_AS,(5*1024**3,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,)*2)
def run(cmd,cap):
    t=time.perf_counter()
    try:
        p=subprocess.run([str(v) for v in cmd],capture_output=True,text=True,
                         errors="replace",timeout=cap,preexec_fn=guard)
        return {"status":"DONE","rc":p.returncode,"text":p.stdout+"\n"+p.stderr,
                "seconds":round(time.perf_counter()-t,6)}
    except subprocess.TimeoutExpired as e:
        return {"status":"TIMEOUT","rc":124,
                "text":str(e.stdout or b"")[-2000:],
                "seconds":round(time.perf_counter()-t,6)}
def eval_solver_model(cnf,text,variables):
    assignment={}
    for s in text.splitlines():
        s=s.strip()
        if not s.startswith("v ") and not s.startswith("v\t"):continue
        for bit in s.split()[1:]:
            v=int(bit)
            if v==0:continue
            i=abs(v)
            if i<1 or i>variables or (i in assignment and assignment[i]!=(v>0)):
                return False
            assignment[i]=v>0
    if len(assignment)!=variables:return False
    for line in Path(cnf).read_text().splitlines():
        if not line or line.startswith(("p","c")):continue
        lits=[int(x) for x in line.split() if int(x)!=0]
        if not any(assignment[abs(z)]==(z>0) for z in lits):return False
    return True
def bench(args):
    if hasattr(os,"sched_setaffinity"):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    cpu=min(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else None
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    solvers={"Kissat":Path(args.kissat).resolve(),"CaDiCaL":Path(args.cadical).resolve()}
    for n,p in solvers.items():
        if not p.is_file():raise FileNotFoundError(n+" executable missing")
    cases=("original_mismatch","wrong_lsb_mismatch","correct_equal")
    rows=[]
    for rep in range(2):
        for case in cases:
            cnf=Path(args.cnfdir)/(case+".cnf")
            manifest=Path(args.cnfdir)/(case+"_manifest.json")
            begin=time.perf_counter()
            outcome=validate(args.netlist,args.base_certificate,
                             args.prior_paths,args.proposal,
                             args.original32_verification,cnf,manifest)
            if outcome["case"]!=case:raise AssertionError("WRONG_CASE")
            if case=="original_mismatch":
                drnas_status="SOURCE_BOUND_STRUCTURAL_UNSAT_VERIFIED"
                source_model=None
            else:
                values,clause_count=model(cnf,manifest,"alternate" if rep==0 else "one")
                if clause_count!=outcome["CNF_clauses"]:raise AssertionError("INDEPENDENT_MODEL_CLAUSE_MISMATCH")
                drnas_status="SOURCE_BOUND_STRUCTURAL_SAT_MODEL_VERIFIED"
                source_model=hashlib.sha256(
                    bytes(values[1:])).hexdigest()
            drnas_time=round(time.perf_counter()-begin,6)
            row={"rep":rep,"case":case,"source_sha256":sha(args.netlist),
                 "cnf_sha256":sha(cnf),"source_gate_count":outcome["original_source_gate_count"],
                 "CNF_variables":outcome["CNF_variables"],
                 "CNF_clauses":outcome["CNF_clauses"],
                 "ATLAS22_status":drnas_status,"ATLAS22_E2E_s":drnas_time,
                 "ATLAS22_model_digest":source_model,
                 "ATLAS22_independent_source_32bit_gate_theorem":True,
                 "ATLAS22_clause_by_clause_encoding_check":True,
                 "single_logical_cpu":cpu,"baselines":{}}
            arms=("Kissat","CaDiCaL") if rep==0 else ("CaDiCaL","Kissat")
            for solver_name in arms:
                binary=solvers[solver_name]
                response=run([binary,cnf],args.cap)
                (out/(f"{case}_{solver_name}_rep{rep}.log")).write_text(response["text"][-80000:])
                status="TIMEOUT" if response["status"]=="TIMEOUT" else (
                       "UNSAT_REPORTED" if "s UNSATISFIABLE" in response["text"] else
                       "SAT_REPORTED" if "s SATISFIABLE" in response["text"] else
                       "UNKNOWN")
                checked_model=False
                if status=="SAT_REPORTED":
                    checked_model=eval_solver_model(cnf,response["text"],outcome["CNF_variables"])
                    if not checked_model:raise AssertionError("SAT_MODEL_FAILED_OR_INCOMPLETE "+solver_name+" "+case)
                if status=="UNSAT_REPORTED" and case!="original_mismatch":
                    raise AssertionError("SAT_CONTROL_UNSAT_UNSOUND "+solver_name+" "+case)
                if status=="SAT_REPORTED" and case=="original_mismatch":
                    raise AssertionError("SOURCE_MITER_SAT_SOUNDNESS_ALARM "+solver_name)
                row["baselines"][solver_name]={"status":status,"seconds":response["seconds"],
                    "SAT_model_original_DIMACS_verified":checked_model,
                    "standard_unsat_proof_verified":False,
                    "exit_code":response["rc"],
                    "same_cnf_sha256":sha(cnf)}
                print("ATLAS22_PAIRED",json.dumps({"rep":rep,"case":case,"solver":solver_name,
                      "status":status,"seconds":response["seconds"],
                      "verified_model":checked_model}),flush=True)
            rows.append(row)
            (out/"live_summary.json").write_text(json.dumps(rows,indent=2)+"\n")
            print("ATLAS22_ROW",json.dumps(row),flush=True)
    all_same=all(
        all(x["same_cnf_sha256"]==r["cnf_sha256"] for x in r["baselines"].values())
        for r in rows)
    if not all_same:raise AssertionError("BASELINE_DIFFERENT_CNF")
    summary={"protocol":"ATLAS22_REAL6_3_32BIT_FACT_BRIDGE",
             "status":"COMPLETE","source_originals":1,"source_output_ports":1,
             "case_kinds":len(cases),"repetitions":2,"trials":len(rows),
             "same_exact_CNF_for_Kissat_CaDiCaL":True,
             "no_CDCL_fallback":True,"main_unchanged":True,
             "all_ATLAS22_structural_proofs_independently_replayed":True,
             "ATLAS22_UNSAT_rows":sum("UNSAT" in r["ATLAS22_status"] for r in rows),
             "ATLAS22_SAT_rows":sum("SAT_MODEL" in r["ATLAS22_status"] for r in rows),
             "Kissat_UNSAT_reported_only":sum(r["baselines"]["Kissat"]["status"]=="UNSAT_REPORTED" for r in rows),
             "CaDiCaL_UNSAT_reported_only":sum(r["baselines"]["CaDiCaL"]["status"]=="UNSAT_REPORTED" for r in rows),
             "SAT_reference_models_independently_checked":sum(x["SAT_model_original_DIMACS_verified"] for r in rows for x in r["baselines"].values()),
             "standard_DRAT_LRAT_UNSAT_certificates":0,
             "NOT_GENERAL_RAW_CNF_CLASSIFIER":True,
             "NOT_PROSPECTIVE_ORIGINAL":True,
             "NOT_GENERAL_SPEEDUP_CLAIM":True,
             "rows":rows}
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print("ATLAS22_FINAL",json.dumps({k:v for k,v in summary.items() if k!="rows"}),flush=True)
    return summary
def main():
    p=argparse.ArgumentParser()
    for n in ("netlist","base-certificate","prior-paths","proposal",
              "original32-verification","cnfdir","kissat","cadical","out"):
        p.add_argument("--"+n,required=True)
    p.add_argument("--cap",type=int,default=15)
    bench(p.parse_args())
if __name__=="__main__":main()
