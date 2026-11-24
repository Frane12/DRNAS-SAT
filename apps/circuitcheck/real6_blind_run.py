#!/usr/bin/env python3
"""Prospective REAL6 motif recognition on five untouched new third-party FPGA RTLs.

Prelocked REAL5-Q and REAL6 mathematical engine SHA must be unchanged.
No source-specific tweaks; failed syntax, missing modules, unknown and
zero motif cases remain recorded. Every accepted motif is confirmed via
a mathematically independent 8-assignment truth table and original
Yosys gate-netlist proof. SAT controls: exact original gate cone versus
GF2 polynomial, same DIMACS to Kissat+CaDiCaL, one CPU, two repeats.
That is a local one-step identity check, NOT a whole-core SAT/UNSAT proof.
"""
from __future__ import annotations
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from real5q_anf import analyze as quadratic_analyze,CannotProve
from real5q_verify import check as verify_quadratic
from real6_motifs import generate as motif_generate
from real6_verify import verify as verify_motif
from real5q_miter import create as create_gate_miter,choices as generic_choices,Unsupported as MiterUnsupported
from stress_run import run,dimacs_meta,result_status,verify_sat

LOCKED={
  "real5q_anf.py":"fc0ed0b1a57bd5b0df75ba3f307faccef7a763edb39408e20e278cd09d40d35a",
  "real5q_verify.py":"a7203de8c48148dc24a9bb37f593e1b924b5e3d24c8cdf767e6bbd91c117738b",
  "real6_motifs.py":"f27a4a3f2efc73d0c8aa35fcca8092acf5d973a8b46004de2c1d90706ebb4365",
  "real6_verify.py":"28d660b8486f8590ea3fa2091a18e6df9cec7cd95c76b59d8315ecf5956ab803"
}
YOSYS_CAP=90
SAT_CAP=10
CNF_CAP=35
MAX_CONES=3

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run_original(case,root,output,cpu,solver):
    src=root/case["filename"]
    if not src.is_file() or sha(src)!=case["sha256"]:
        raise RuntimeError("FROZEN_ORIGINAL_FILE_MISMATCH "+case["id"])
    work=output/case["id"];work.mkdir(exist_ok=True,parents=True)
    row={"id":case["id"],"domain":case["domain"],"source_sha256":case["sha256"],
         "original_blob":case["blob"],"source_unchanged":True,
         "synthesis":{"status":"NOT_ATTEMPTED"},"gf2_anf":{"status":"NOT_ATTEMPTED"},
         "real6_motifs":{"status":"NOT_ATTEMPTED"},"real6_independent_replay":{"status":"NOT_ATTEMPTED"},
         "sampled_cone_sat":[]}
    def save(): (work/"case_result.json").write_text(json.dumps(row,indent=2)+"\n")
    netfile=work/"netlist.json"
    yosys=("read_verilog -sv "+str(src.resolve())+
           "; hierarchy -check -top "+case["top"]+
           "; proc; flatten; opt; techmap; opt; write_json "+str(netfile.resolve()))
    r=run(["yosys","-p",yosys],cpu,YOSYS_CAP,work/"original_synthesis.log")
    outcome="TIMEOUT" if r["timeout"] else ("OK" if r["return_code"]==0 and netfile.is_file() else "FRONTEND_OR_DEPENDENCY_UNSUPPORTED")
    row["synthesis"]={"status":outcome,"seconds":r["seconds"],"max_rss_kb":r["max_rss_kb"],"exit_code":r["return_code"]}
    save()
    if outcome!="OK":
        print("REAL6_UNKNOWN_SOURCE",case["id"],outcome,flush=True)
        return row
    row["netlist_sha256"]=sha(netfile)
    try:
        begin=time.perf_counter()
        doc=json.loads(netfile.read_text())
        proof=quadratic_analyze(doc,case["top"])
        proof["netlist_sha256"]=row["netlist_sha256"]
        base=work/"real5q_certificate.json"
        base.write_text(json.dumps(proof,indent=2)+"\n")
        checked=verify_quadratic(work)
        if checked["status"]!="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS":
            raise RuntimeError("UNVERIFIED_POLYNOMIAL_GATE_PROOF")
        row["gf2_anf"]={"status":"CHECKED","seconds":round(time.perf_counter()-begin,6),
                         "metrics":proof["metrics"],"certificate_sha256":sha(base)}
        save()
        candidate=motif_generate(work)
        motif_file=work/"real6_certificate.json"
        motif_file.write_text(json.dumps(candidate,indent=2)+"\n")
        independently=verify_motif(work,motif_file)
        if independently["status"]!="CHECKED_REAL6_MOTIF_TRUTH_TABLES":
            raise RuntimeError("REAL6_MOTIF_NOT_CHECKED")
        row["real6_motifs"]={
            "status":candidate["status"],
            "counts":candidate["counts"],
            "sample_motifs":candidate["motifs"][:8],
            "sample_full_adders":candidate["full_adder_pairs"][:4],
            "certificate_sha256":sha(motif_file)}
        row["real6_independent_replay"]={"status":independently["status"],
                                         "motifs_replayed":independently["motifs_replayed"],
                                         "adder_pairs_replayed":independently["adder_pairs_replayed"]}
    except (CannotProve,ValueError,KeyError,OverflowError,MemoryError,RecursionError,TypeError) as e:
        row["gf2_anf"]["status"]="UNKNOWN"
        row["gf2_anf"]["reason"]=str(e)
        save()
        print("REAL6_BASE_GF2_UNKNOWN",case["id"],str(e),flush=True)
        return row
    save()
    # Select discovered REAL6 motifs first. Only if none are found,
    # sample a generic certified quadratic REAL5-Q cone; label distinctly.
    selected=[]
    already=set()
    for motif in candidate["motifs"]:
        k=motif["probe"]["yosys_bit"]
        if k in already:continue
        already.add(k)
        p=next((p for p in proof["probes"] if p["yosys_bit"]==k and
                p["kind"]==motif["probe"]["kind"] and
                p["name"]==motif["probe"]["name"] and
                p["position"]==motif["probe"]["position"]),None)
        if p is not None:selected.append((p,"REAL6_MOTIF_"+motif["motif"]))
        if len(selected)>=MAX_CONES:break
    if not selected:
        for p in generic_choices(proof,max_samples=MAX_CONES):
            if p["yosys_bit"] in already:continue
            selected.append((p,"GENERIC_REAL5Q_POLYNOMIAL_CONTROL"))
            already.add(p["yosys_bit"])
    for ix,(probe,reason) in enumerate(selected):
        site=work/"local_checks"/("cone_"+str(ix))
        site.mkdir(parents=True,exist_ok=True)
        item={"label":"cone_"+str(ix),"selection_reason":reason,
              "probe_kind":probe["kind"],"probe_bit":probe["yosys_bit"],
              "status":"UNKNOWN","solver_runs":[]}
        row["sampled_cone_sat"].append(item)
        try:
            verilog,meta=create_gate_miter(doc,proof,probe)
            miter=site/"miter.v"
            miter.write_text(verilog)
            item.update({"miter_sha256":sha(miter),**meta})
        except MiterUnsupported as ex:
            item.update(status="UNSUPPORTED_LOCAL_GATE_CONE",reason=str(ex))
            save();continue
        cnf=site/"same_cone.cnf"
        script=("read_verilog -sv "+str(miter.resolve())+
            "; hierarchy -check -top miter; proc; flatten; opt; "
            "sat -timeout 1 -set mismatch 1 -dump_cnf "+str(cnf.resolve()))
        conv=run(["yosys","-p",script],cpu,CNF_CAP,site/"cnf_export.log")
        if conv["timeout"] or conv["return_code"]!=0 or not cnf.is_file():
            item["status"]="CNF_EXPORT_FAILED"
            item["cnf_export_seconds"]=conv["seconds"]
            save();continue
        item["cnf"]=dimacs_meta(cnf)
        item["cnf_export_seconds"]=conv["seconds"]
        item["status"]="CNF_AVAILABLE"
        proof_script=("read_verilog -sv "+str(miter.resolve())+
             "; hierarchy -check -top miter; proc; flatten; opt; "
             "sat -verify -prove mismatch 0 -timeout 10")
        y=run(["yosys","-p",proof_script],cpu,20,site/"yosys_formal.log")
        item["yosys_gate_identity"]={
            "status":"VERIFIED_LOCAL_GATE_IDENTITY" if y["return_code"]==0 and not y["timeout"] else "NOT_VERIFIED",
            "seconds":y["seconds"]}
        for rep in (0,1):
            arms=("Kissat","CaDiCaL") if rep==0 else ("CaDiCaL","Kissat")
            for arm in arms:
                s=run([solver[arm],cnf],cpu,SAT_CAP,site/f"{arm}_r{rep}.log")
                status=result_status(s["stdout"],s["return_code"],s["timeout"])
                witness=verify_sat(cnf,s["stdout"]) if status=="SAT" else None
                item["solver_runs"].append({
                    "arm":arm,"rep":rep,"status":status,
                    "seconds":s["seconds"],"sat_model_checked":witness,
                    "independent_unsat_certificate":False})
                save()
                if status=="SAT":
                    raise RuntimeError("LOCAL_REAL6_POLYNOMIAL_SOUNDNESS_ALARM "+case["id"])
        print("REAL6_LOCAL_SAT",case["id"],item["label"],
              item["yosys_gate_identity"]["status"],
              [t["status"] for t in item["solver_runs"]],flush=True)
    save()
    print("REAL6_BLIND_MODULE",case["id"],candidate["counts"],"sampled",len(selected),flush=True)
    return row

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--shard",type=int,required=True)
    p.add_argument("--shards",type=int,default=3)
    p.add_argument("--kissat",type=Path,required=True)
    p.add_argument("--cadical",type=Path,required=True)
    a=p.parse_args()
    a.frozen=a.frozen.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    code=Path(__file__).resolve().parent
    for name,digest in LOCKED.items():
        if sha(code/name)!=digest:raise RuntimeError("MATHEMATICAL_ENGINE_OR_CHECKER_MODIFIED "+name)
    manifest=json.loads((a.frozen/"manifest.json").read_text())
    if manifest["protocol"]!="DRNAS_REAL6_PROSPECTIVE_FIVE_UNKNOWN_ORIGINAL_RTL":
        raise RuntimeError("BAD_FROZEN_CORPUS")
    if manifest["engine_prelock_run"]!=45347547028 or len(manifest["cases"])!=5:
        raise RuntimeError("UNLOCKED_SOURCE_COHORT")
    if not 0<=a.shard<a.shards:raise RuntimeError("BAD_SHARD")
    cpu=min(os.sched_getaffinity(0))
    solver={"Kissat":a.kissat.resolve(),"CaDiCaL":a.cadical.resolve()}
    output={"protocol":manifest["protocol"],
            "manifest_sha256":sha(a.frozen/"manifest.json"),
            "shard":a.shard,"shards":a.shards,
            "mathematical_engine_sha256":LOCKED,
            "one_logical_cpu":cpu,
            "solver_sha256":{k:sha(v) for k,v in solver.items()},"cases":[]}
    for i,case in enumerate(manifest["cases"]):
        if i%a.shards!=a.shard:continue
        output["cases"].append(run_original(case,a.frozen,a.out,cpu,solver))
        (a.out/"rows.json").write_text(json.dumps(output,indent=2)+"\n")
    print("REAL6_BLIND_SHARD_COMPLETE",a.shard,len(output["cases"]),flush=True)

if __name__=="__main__":main()
