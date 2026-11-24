#!/usr/bin/env python3
"""REAL3 one-CPU paired proof and original-RTL/Yosys-CNF baseline runner.

Sources are 3 untouched third-party public RTL modules, not synthetic DUTs.
REAL3 reads their complete source and derives masks WITHOUT source SHA/name
lookup; an independently declared reference is used only for scoring.
Kissat and CaDiCaL receive exactly the same Yosys exported miter DIMACS.
SAT models checked against ALL DIMACS clauses; UNSAT lacks DRAT/LRAT.
No CDCL fallback into REAL3. UNKNOWNs are kept as failures.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
from real3_classifier import classify,Unknown
from real3_harness import configuration,expected_masks,prepare_source
from stress_run import run,dimacs_meta,result_status,verify_sat

CAP=15.0
CNF_CAP=65.0
REPS=2
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def trial(arm,exe,cnf,cpu,work,repeat,expected):
    runinfo=run([exe,cnf],cpu,CAP,work/f"{arm}_{repeat}.log")
    status=result_status(runinfo["stdout"],runinfo["return_code"],runinfo["timeout"])
    checked=verify_sat(cnf,runinfo["stdout"]) if status=="SAT" else None
    if status in ("SAT","UNSAT") and status!=expected:
        raise RuntimeError("BAD_SAT_VERDICT "+arm+" "+status+" expected "+expected)
    if status=="SAT" and checked is not True:
        raise RuntimeError("INVALID_SAT_ASSIGNMENT "+arm)
    return {"arm":arm,"repeat":repeat,"status":status,"seconds":runinfo["seconds"],
            "max_rss_kb":runinfo["max_rss_kb"],"sat_witness_checked":checked,
            "standard_unsat_proof_verified":False}

def bench_case(root,manifest,case,args,cpu):
    t=time.perf_counter()
    work=args.out/case["name"];work.mkdir(parents=True,exist_ok=True)
    pin=next(x for x in manifest["sources"] if x["name"]==case["src"])
    extension=".sv" if pin["path"].endswith(".sv") else ".v"
    source=root/"upstream"/(case["src"]+extension)
    if sha(source)!=pin["sha256"]:
        raise RuntimeError("UNPINNED_ORIGINAL_SOURCE")
    model=prepare_source(work,case)
    row={"id":case["name"],"kind":case["kind"],
         "source_sha256":sha(source),"model_miter_sha256":sha(model),
         "expected":"SAT" if case["fault"] else "UNSAT",
         "proof":{"status":"UNKNOWN","seconds":None,"replayed":False},
         "external_yosys":{"status":"NOT_CHECKED"},
         "cnf_export":{"status":"NOT_ATTEMPTED"},"cnf":None,
         "trials":[]}
    def store(): (work/"result.json").write_text(json.dumps(row,indent=2)+"\n")
    stamp=time.perf_counter()
    try:
        parsed=classify(source.read_bytes(),configuration(case))
        claim=[int(x,16) for x in parsed["output_masks_hex"]]
        expected_masks_list=expected_masks(case)
        if claim!=expected_masks_list:
            row["proof"]={"status":"SPEC_MISMATCH","seconds":round(time.perf_counter()-stamp,6)}
        else:
            cert=work/"real3_certificate.json"
            cert.write_text(json.dumps(parsed,indent=2)+"\n")
            metadata=work/"entry.json";metadata.write_text(json.dumps(case)+"\n")
            result=run([sys.executable,Path(__file__).parent/"real3_replay.py",
                  "--certificate",cert,"--source",source,"--entry",metadata,
                  "--out",work/"replay.json"],cpu,10,work/"replay.log")
            verdict=(work/"replay.json")
            if result["return_code"]==0 and verdict.is_file() and (
                  json.loads(verdict.read_text())["status"]=="REPLAYED_AFFINE_SPEC_COEFFICIENTS"):
                row["proof"]={"status":"RECOGNIZED_AND_REPLAYED","seconds":round(time.perf_counter()-stamp,6),
                              "replayed":True,"source_class":parsed["class"],
                              "certificate_sha256":sha(cert),
                              "input_bits":sum(x["width"] for x in parsed["input_order"]),
                              "output_bits":sum(x["width"] for x in parsed["output_order"])}
            else:row["proof"]={"status":"REPLAY_FAILED","seconds":round(time.perf_counter()-stamp,6)}
    except (Unknown,ValueError,KeyError,TypeError) as exc:
        row["proof"]={"status":"UNKNOWN","reason":str(exc),
                      "seconds":round(time.perf_counter()-stamp,6)}
    store()
    # Same original-source-dependent CNF for both baseline solvers.
    cnf=work/"original.cnf"
    script=("read_verilog -sv "+str(source)+" "+str(model)+
            "; hierarchy -check -top miter; proc; flatten; opt; "
            "sat -timeout 1 -set mismatch 1 -dump_cnf "+str(cnf))
    export=run(["yosys","-p",script],cpu,CNF_CAP,work/"yosys_export.log")
    row["cnf_export"]={"status":"TIMEOUT" if export["timeout"] else (
        "OK" if export["return_code"]==0 else "FAILED"),
        "seconds":export["seconds"],"return_code":export["return_code"],
        "max_rss_kb":export["max_rss_kb"]}
    if row["cnf_export"]["status"]=="OK" and cnf.exists():
        try:row["cnf"]=dimacs_meta(cnf)
        except (ValueError,OSError):row["cnf_export"]["status"]="INVALID_DIMACS"
    store()
    # Yosys independent full-RTL safety check for equivalent examples.
    if row["cnf"] is not None and not case["fault"]:
        check_script=("read_verilog -sv "+str(source)+" "+str(model)+
            "; hierarchy -check -top miter; proc; flatten; opt; "
            "sat -verify -prove mismatch 0 -timeout 12")
        external=run(["yosys","-p",check_script],cpu,23,work/"yosys_formal.log")
        row["external_yosys"]={"status":"VERIFIED_EQUAL" if external["return_code"]==0 and not external["timeout"] else "NOT_VERIFIED",
            "seconds":external["seconds"],"timeout":external["timeout"]}
        if row["external_yosys"]["status"]!="VERIFIED_EQUAL":
            row["proof"]["status"]="UNCONFIRMED_ORIGINAL_RTL"
        store()
    for repeat in range(REPS):
        for arm in (("Kissat","CaDiCaL") if repeat==0 else ("CaDiCaL","Kissat")):
            if row["cnf"] is None:
                info={"arm":arm,"repeat":repeat,"status":"CNF_EXPORT_FAILED",
                      "seconds":0,"sat_witness_checked":None}
            else:
                info=trial(arm,args.kissat if arm=="Kissat" else args.cadical,
                           cnf,cpu,work,repeat,row["expected"])
            row["trials"].append(info);store()
            print("REAL3_BASELINE",case["name"],arm,repeat,
                  info["status"],info["seconds"],flush=True)
    row["elapsed_total_seconds"]=round(time.perf_counter()-t,6)
    store()
    print("REAL3_CASE",case["name"],row["proof"]["status"],
          "Yosys",row["external_yosys"]["status"],flush=True)
    return row

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--external",required=True,type=Path)
    a.add_argument("--out",required=True,type=Path)
    a.add_argument("--shard",required=True,type=int)
    a.add_argument("--shards",type=int,default=3)
    a.add_argument("--kissat",required=True,type=Path)
    a.add_argument("--cadical",required=True,type=Path)
    x=a.parse_args()
    x.external=x.external.resolve()
    x.out=x.out.resolve();x.out.mkdir(parents=True,exist_ok=True)
    x.kissat=x.kissat.resolve();x.cadical=x.cadical.resolve()
    doc=json.loads((x.external/"manifest.json").read_text())
    assert doc["protocol"]=="DRNAS_REAL3_UNSEEN_EXTERNAL_PARITY_20261124"
    cpu=min(os.sched_getaffinity(0))
    data={"protocol":doc["protocol"],"manifest_sha256":sha(x.external/"manifest.json"),
          "shard":x.shard,"shards":x.shards,"cpu":cpu,
          "platform":platform.platform(),"binary_sha256":{
            "Kissat":sha(x.kissat),"CaDiCaL":sha(x.cadical)},"cases":[]}
    for i,case in enumerate(doc["cases"]):
        if i%x.shards!=x.shard:continue
        row=bench_case(x.external,doc,case,x,cpu)
        data["cases"].append(row)
        (x.out/"rows.json").write_text(json.dumps(data,indent=2)+"\n")
    print("REAL3_SHARD_COMPLETE",x.shard,len(data["cases"]),flush=True)
if __name__=="__main__":main()
