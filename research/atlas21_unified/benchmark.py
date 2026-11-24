#!/usr/bin/env python3
"""ATLAS21 six-original paired SAT/UNSAT cross-family model+proof coverage test."""
import hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas21_results";OUT.mkdir(exist_ok=True)
M=json.loads((ROOT/"atlas17_original_inputs/manifest.json").read_text())
assert M["status"]=="FROZEN_BEFORE_ANY_SOLVER" and M["public_downloaded"]==6
assert not M["failures"]
CASES=[x for x in M["sources"] if x["cohort"]=="public_preselected"]
assert len(CASES)==6 and len({x["sha256"] for x in CASES})==6
if hasattr(os,"sched_setaffinity"):
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
CPU=min(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else None
def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as file:
        for part in iter(lambda:file.read(1<<18),b""):h.update(part)
    return h.hexdigest()
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
def cap():
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,)*2)
def call(cmd,seconds):
    try:
        p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,
                         errors="replace",timeout=seconds,preexec_fn=cap)
    except subprocess.TimeoutExpired:
        raise AssertionError("ATLAS21_ROUTER_PROCESS_TIMEOUT")
    return p.returncode,p.stdout+"\n"+p.stderr

# Known historical labels only in evaluation assertions, never sent to solver.
# SAT model and original VeriPB proof determine status, not this table.
historical={"graph-color-2026":"UNSAT_VERIFIED",
    "exam-scheduling-2026":"UNSAT_VERIFIED",
    "clique-color-2025":"UNSAT_VERIFIED",
    "php-mixed-2023":"UNSAT_VERIFIED",
    "xor-shift-2026":"SAT_MODEL_VERIFIED",
    "boxfolding-2026":"UNKNOWN"}
assert set(historical)=={x["name"] for x in CASES}
rows=[]
for rep in range(2):
    series=CASES if rep==0 else list(reversed(CASES))
    for entry in series:
        name=entry["name"];cnf=ROOT/entry["path"]
        assert sha(cnf)==entry["sha256"]
        dest=OUT/f"rep{rep}"/name;dest.mkdir(parents=True,exist_ok=True)
        before=time.perf_counter()
        rc,text=call([sys.executable,ROOT/"research/atlas21_unified/router.py",
            "--cnf",cnf,"--out",dest],145)
        (dest/"process.log").write_text(text[-15000:])
        if rc!=0 or not (dest/"result.json").is_file():
            raise AssertionError("SOURCE_ROUTER_CRASH:"+text[-1000:])
        r=json.loads((dest/"result.json").read_text())
        if sha(cnf)!=entry["sha256"] or r["source_sha256"]!=entry["sha256"]:
            raise AssertionError("SOURCE_CHANGED")
        if r["status"]!=historical[name]:
            raise AssertionError("STATUS_REGRESSION:"+name+":"+r["status"])
        if not r["no_CDCL_fallback"] or not r["no_unverified_SAT_or_UNSAT"]:
            raise AssertionError("TRUST_BOUNDARY")
        if r["status"]=="SAT_MODEL_VERIFIED":
            model=dest/"circuit/full_model.dimacs"
            assert model.is_file()
            result=call([sys.executable,ROOT/"research/atlas20_circuit/check_model.py",
                "--cnf",cnf,"--model",model,
                "--output",dest/"third_party_replay.json"],15)
            assert result[0]==0
            chk=json.loads((dest/"third_party_replay.json").read_text())
            assert chk["status"]=="SAT_MODEL_VERIFIED"
        if r["status"]=="UNSAT_VERIFIED":
            proof=dest/"structure/result.pbp"
            assert proof.is_file()
            result=call(["veripb","--cnf",cnf,proof],20)
            assert result[0]==0 and "s VERIFIED UNSATISFIABLE" in result[1]
            (dest/"external_replay.log").write_text(result[1][-3000:])
        row={"rep":rep,"source_name":name,
            "source_sha256":entry["sha256"],"status":r["status"],
            "E2E_s":r["E2E_s"],
            "selected":r["selected"],
            "independent_full_model_or_veripb_replay":
                 r["status"]!="UNKNOWN",
            "single_logical_cpu":CPU}
        rows.append(row)
        save(OUT/"summary.json",{"status":"IN_PROGRESS","rows":rows})
        print("ATLAS21_TRIAL "+json.dumps(row,sort_keys=True),flush=True)

summary={"status":"COMPLETE","source_originals":6,"repetitions":2,
 "serial_trials":12,"strict_independent_replays":sum(
    x["independent_full_model_or_veripb_replay"] for x in rows),
 "verified_SAT":sum(x["status"]=="SAT_MODEL_VERIFIED" for x in rows),
 "verified_UNSAT":sum(x["status"]=="UNSAT_VERIFIED" for x in rows),
 "UNKNOWN":sum(x["status"]=="UNKNOWN" for x in rows),
 "solved_unique_originals":sum(
    any(x["source_name"]==name and x["status"]!="UNKNOWN" for x in rows) for name in historical),
 "baseline_ATLAS19_unique_verifiable_originals":4,
 "one_logical_cpu":CPU,"main_untouched":True,"no_CDCL_fallback":True,
 "external_original_source_proofs_or_models_only":True,
 "not_new_blind_not_global_speed_claim":True,"rows":rows}
save(OUT/"summary.json",summary)
print("ATLAS21_FINAL "+json.dumps({k:v for k,v in summary.items() if k!="rows"},sort_keys=True),flush=True)
