#!/usr/bin/env python3
"""ATLAS21 unified SAT+UNSAT proof-first source-only router.

Content-only gate structure => ATLAS20 circuit model, accepted ONLY if
independent original-DIMACS checker verifies every clause.
Otherwise => unchanged ATLAS19 structural UNSAT router, accepted ONLY if
external standard VeriPB verifies the unchanged original source.
Unknown remains UNKNOWN, never a CDCL fallback or guessed answer.
"""
import argparse,hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/atlas20_circuit"))
from extract import recover,Unsupported
MAX_TOTAL=130.0
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def limits():
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(96*1024**2,)*2)
def run(command,deadline):
    remain=deadline-time.perf_counter()
    if remain<=0.03:return {"rc":124,"text":"TOTAL_BUDGET_EXHAUSTED"}
    try:
        p=subprocess.run([str(x) for x in command],capture_output=True,
                         text=True,errors="replace",timeout=remain,
                         preexec_fn=limits)
        return {"rc":p.returncode,"text":p.stdout+"\n"+p.stderr}
    except subprocess.TimeoutExpired:
        return {"rc":124,"text":"TIMEOUT"}
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
def solve(cnf,out):
    if hasattr(os,"sched_setaffinity"):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    cnf=Path(cnf).resolve()
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();deadline=started+MAX_TOTAL
    digest=sha(cnf)
    gate_info={"candidate":False,"status":"UNKNOWN"}
    try:
        circuit=recover(cnf.read_bytes())
        gate_info={"candidate":True,"inputs":circuit["input_count"],
                   "gate_kinds":circuit["gate_kinds"],
                   "source_sha256":circuit["source_sha256"]}
    except (Unsupported,ValueError,TypeError,OSError,UnicodeError) as e:
        gate_info={"candidate":False,"reason":str(e)[:210]}
    save(out/"circuit_gate.json",gate_info)
    stages=[];selected=None;status="UNKNOWN"
    if gate_info["candidate"]:
        stage_start=time.perf_counter()
        sat_dir=out/"circuit"
        sat_run=run([sys.executable,ROOT/"research/atlas20_circuit/run.py",
                   "--cnf",cnf,"--out",sat_dir,
                   "--maximum-search-seconds","95"],deadline)
        (out/"circuit.log").write_text(sat_run["text"][-6000:])
        if sat_run["rc"] not in (0,124):
            raise RuntimeError("CIRCUIT_SEARCH_CRASH:"+sat_run["text"][-800:])
        if sat_run["rc"]==0 and (sat_dir/"result.json").exists():
            meta=json.loads((sat_dir/"result.json").read_text())
            if meta["status"]=="SAT_MODEL_VERIFIED":
                model=sat_dir/"full_model.dimacs"
                assert model.is_file() and sha(model)==meta["model_sha256"]
                replay=run([sys.executable,
                    ROOT/"research/atlas20_circuit/check_model.py",
                    "--cnf",cnf,"--model",model,
                    "--output",out/"independent_replay.json"],deadline)
                if replay["rc"]!=0:
                    raise RuntimeError("SAT_REPLAY_FAILED:"+replay["text"][-500:])
                checker=json.loads((out/"independent_replay.json").read_text())
                if checker["status"]!="SAT_MODEL_VERIFIED" or checker["source_sha256"]!=digest:
                    raise RuntimeError("SAT_SOURCE_VERIFIER_REJECTED")
                status="SAT_MODEL_VERIFIED"
                selected={"stage":"EXACT_CIRCUIT_BITSLICE_MODEL",
                          "witness_sha256":sha(model),"inputs":circuit["input_count"],
                          "input_hex":meta.get("input_hex")}
        stages.append({"stage":"EXACT_CIRCUIT","status":status if status!="UNKNOWN" else "UNKNOWN",
                       "elapsed_s":round(time.perf_counter()-stage_start,6)})
    if status=="UNKNOWN":
        # Fall back only to *mathematical proof modules*, NEVER to CDCL.
        stage_start=time.perf_counter()
        old=out/"structure"
        result=run([sys.executable,ROOT/"research/atlas18_probe/router.py",
                    "--cnf",cnf,"--out",old],deadline)
        (out/"structural.log").write_text(result["text"][-5000:])
        if result["rc"]!=0:raise RuntimeError("STRUCTURAL_PROOF_ROUTER_FAILED:"+result["text"][-600:])
        prior=json.loads((old/"result.json").read_text())
        if prior["source_sha256"]!=digest:
            raise RuntimeError("STRUCTURAL_PROOF_SOURCE_SHA_MISMATCH")
        if prior["status"]=="UNSAT_VERIFIED":
            proof=old/"result.pbp"
            if not proof.is_file() or sha(proof)!=prior["selected"]["proof_sha256"]:
                raise RuntimeError("UNSAT_SOURCE_PROOF_MISSING_OR_CHANGED")
            status="UNSAT_VERIFIED"
            selected={"stage":"VERIPB_ORIGINAL_STRUCTURAL",
                      "submodule":prior["selected"]["stage"],
                      "proof_sha256":sha(proof)}
        stages.append({"stage":"SOURCE_STRUCTURAL_UNSAT","status":prior["status"],
                       "elapsed_s":round(time.perf_counter()-stage_start,6),
                       "original_structural_trace":prior["stages"]})
    if sha(cnf)!=digest:raise RuntimeError("ORIGINAL_SOURCE_CHANGED")
    final={"status":status,"source_sha256":digest,"source_unchanged":True,
           "selected":selected,
           "source_gate":gate_info,
           "E2E_s":round(time.perf_counter()-started,6),
           "strict_total_cap_s":MAX_TOTAL,
           "no_CDCL_fallback":True,"stages":stages,
           "no_unverified_SAT_or_UNSAT":True}
    save(out/"result.json",final)
    print("ATLAS21_RESULT "+json.dumps(final,sort_keys=True),flush=True)
    return final
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--cnf",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    try:solve(a.cnf,a.out)
    except (RuntimeError,AssertionError,ValueError,OSError,KeyError) as exc:
        print("ATLAS21_FATAL_EVIDENCE_ERROR "+str(exc),flush=True)
        raise SystemExit(1)
