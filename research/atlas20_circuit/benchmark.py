#!/usr/bin/env python3
"""ATLAS20 paired reproducible SAT circuit pilot (source-frozen, original model).

The XOR shifting source is the exact preselected ATLAS17 public CNF, SHA-bound.
The circuit recognizer/search receives original DIMACS bytes only (no prior
solution/key); all full SAT model checks are independent of the recognizer.
Two serial single-CPU repetitions, controls, pinned Kissat/CaDiCaL references.
No DRNAS CDCL fallback, no false UNSAT, no P=NP claims. Runtime bounded.
"""
import hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from extract import recover,Unsupported
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas20_results";OUT.mkdir(exist_ok=True)
M=json.loads((ROOT/"atlas17_original_inputs/manifest.json").read_text())
EXPECTED_SHA="450b963e0ebebe3c08049067e2c954304712b1601711223bbfff1807c74b236e"
candidates=[r for r in M["sources"] if r["sha256"]==EXPECTED_SHA]
assert len(candidates)==1 and candidates[0]["name"]=="xor-shift-2026"
S=ROOT/candidates[0]["path"]
assert hashlib.sha256(S.read_bytes()).hexdigest()==EXPECTED_SHA
if hasattr(os,"sched_setaffinity"):
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
CPU=min(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else None
def hashfile(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1<<18),b""):h.update(b)
    return h.hexdigest()
def save(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE,(80*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2)
def run(cmd,seconds):
    t=time.perf_counter()
    try:
        p=subprocess.run([str(x) for x in cmd],capture_output=True,
                         text=True,errors="replace",
                         timeout=seconds,preexec_fn=limits)
        return {"returncode":p.returncode,
             "wall_s":round(time.perf_counter()-t,6),
             "output":p.stdout+"\n"+p.stderr}
    except subprocess.TimeoutExpired:
        return {"returncode":124,"wall_s":round(time.perf_counter()-t,6),
                "output":"TIMEOUT"}
def new_arm(rep):
    dest=OUT/f"atlas20_rep{rep}";dest.mkdir(exist_ok=True)
    t=time.perf_counter()
    result=run([sys.executable,ROOT/"research/atlas20_circuit/run.py",
                 "--cnf",S,"--out",dest,
                 "--maximum-search-seconds","100"],130)
    (dest/"harness.log").write_text(result["output"][-5000:])
    if result["returncode"]!=0 or not (dest/"result.json").exists():
        raise AssertionError("ATLAS20_SOLVER_AUDIT_FAILED:"+result["output"][-1500:])
    report=json.loads((dest/"result.json").read_text())
    if report["status"]!="SAT_MODEL_VERIFIED":
        raise AssertionError("EXPECTED_SAT_MODEL_NOT_REPRODUCED:"+str(report))
    if report["source_sha256"]!=EXPECTED_SHA:
        raise AssertionError("ORIGINAL_SHA_MISMATCH")
    model=dest/"full_model.dimacs"
    assert model.exists() and report["model_sha256"]==hashfile(model)
    # Distinct fresh-process independent audit, outside the timed score, labeled replay.
    check=run([sys.executable,ROOT/"research/atlas20_circuit/check_model.py",
               "--cnf",S,"--model",model,
               "--output",dest/"independent_replay.json"],15)
    if check["returncode"]!=0:raise AssertionError("INDEPENDENT_REPLAY_FAILED")
    evidence=json.loads((dest/"independent_replay.json").read_text())
    assert evidence["original_clauses_verified"]==8868
    assert evidence["complete_assignment_variables"]==2430
    assert evidence["status"]=="SAT_MODEL_VERIFIED"
    out={"arm":"ATLAS20_CIRCUIT_BITSLICE","rep":rep,"status":report["status"],
         "method":"source-backed_exact_gate_reconstruction_plus_2^32_enumeration",
         "model_sha256":report["model_sha256"],
         "input_hex":report.get("input_hex"),
         "keys_tested":report.get("native_keys_tested"),
         "native_search_s":report["native_search_s"],
         "E2E_s":report["whole_E2E_s"],
         "harness_wall_s":round(time.perf_counter()-t,6),
         "replay":"SAT_MODEL_VERIFIED",
         "source_sha256":EXPECTED_SHA}
    save(dest/"trial.json",out)
    print("ATLAS20_PAIRED "+json.dumps(out,sort_keys=True),flush=True)
    return out
def reference(arm,rep):
    exe=(ROOT/"kissat-src/build/kissat" if arm=="Kissat4.0.4"
         else ROOT/"cadical-src/build/cadical")
    dest=OUT/f"{arm}_rep{rep}";dest.mkdir(exist_ok=True)
    started=time.perf_counter()
    r=run([exe,S],45)
    (dest/"solver.log").write_text(r["output"][-25000:])
    status="UNKNOWN";reason="UNKNOWN";modelhash=None
    if r["returncode"]==10:
        model=dest/"candidate.dimacs"
        model.write_text(r["output"])
        verification=run([sys.executable,
                ROOT/"research/atlas20_circuit/check_model.py",
                "--cnf",S,"--model",model,
                "--output",dest/"model_checker.json"],12)
        if verification["returncode"]==0:
            status="SAT_MODEL_VERIFIED";reason="COMPLETE_ORIGINAL_MODEL_ACCEPTED"
            modelhash=hashfile(model)
        else:
            reason="SOLVER_SAT_BUT_NOT_FULLY_CHECKED"
            (dest/"checker_failure.log").write_text(verification["output"])
    elif r["returncode"]==20:
        # Strict UNSAT is impossible on an original with an independently
        # checked SAT model; this is a fatal correctness contradiction.
        raise AssertionError("REFERENCE_UNSAT_CONFLICTS_WITH_VERIFIED_SAT_WITNESS")
    elif r["returncode"]==124:reason="45_SECOND_TIMEOUT"
    else:reason="UNRESOLVED_RC_"+str(r["returncode"])
    out={"arm":arm,"rep":rep,"status":status,"reason":reason,
         "E2E_s":round(time.perf_counter()-started,6),
         "model_sha256":modelhash,"source_sha256":EXPECTED_SHA}
    save(dest/"trial.json",out)
    print("ATLAS20_REFERENCE "+json.dumps(out,sort_keys=True),flush=True)
    return out
def safety():
    raw=S.read_bytes()
    recovered=recover(raw)
    assert recovered["variables"]==2430 and recovered["clauses"]==8868
    assert recovered["input_count"]==32 and recovered["gate_count"]==2398
    assert recovered["gate_kinds"]=={"XOR":1642,"AND":378,"OR":378}
    assert len(recovered["unit_literals"])==32
    # Remove one of the four source clauses defining one XOR gate. Preserve
    # valid DIMACS syntax but force the parser to reject its missing premise.
    parts=raw.decode("ascii").splitlines()
    assert parts[0]=="p cnf 2430 8868"
    tampered=["p cnf 2430 8867"]+parts[2:]
    broken=("\n".join(tampered)+"\n").encode("ascii")
    try:recover(broken)
    except Unsupported:source_clause_tamper_rejected=True
    else:raise AssertionError("MISSING_SOURCE_XOR_CLAUSE_ACCEPTED")
    # Flip variable 1 in a previously checked full SAT witness. This should
    # contradict its source-backed gate outputs.
    original=OUT/"atlas20_rep0/full_model.dimacs"
    chunks=original.read_text().splitlines()
    changed=False
    for i,line in enumerate(chunks):
        if line.startswith("v "):
            ls=line.split()
            for j,lit in enumerate(ls):
                if lit in ("1","-1"):
                    ls[j]=str(-int(lit));chunks[i]=" ".join(ls);changed=True;break
            if changed:break
    assert changed
    mutant=OUT/"source_model_mutation.dimacs"
    mutant.write_text("\n".join(chunks)+"\n")
    check=run([sys.executable,ROOT/"research/atlas20_circuit/check_model.py",
        "--cnf",S,"--model",mutant,
        "--output",OUT/"invalid_model_check.json"],12)
    if check["returncode"]==0:raise AssertionError("FALSE_SAT_MODEL_ACCEPTED")
    assert not (OUT/"invalid_model_check.json").exists()
    outcome={"gate_definitions_from_original_clauses":True,
       "source_clause_mutation_rejected":source_clause_tamper_rejected,
       "wrong_full_model_rejected":True,
       "original_source_sha256":EXPECTED_SHA,
       "original_clauses":8868,
       "primary_input_bits":32,
       "gate_kinds":recovered["gate_kinds"]}
    save(OUT/"negative_controls.json",outcome)
    print("ATLAS20_NEGATIVE_CONTROLS "+json.dumps(outcome,sort_keys=True),flush=True)
    return outcome

results=[]
for rep in range(2):
    results.append(new_arm(rep))
    for arm in ("Kissat4.0.4","CaDiCaL2.1.3"):
        results.append(reference(arm,rep))
check=safety()
summary={"status":"COMPLETE","original_source_sha256":EXPECTED_SHA,
 "source_vars":2430,"source_clauses":8868,
 "original_syntactic_status":"PREVIOUSLY_CATALOG_UNKNOWN",
 "verified_models":sum(x["status"]=="SAT_MODEL_VERIFIED" for x in results if x["arm"]=="ATLAS20_CIRCUIT_BITSLICE"),
 "Kissat_verified_models":sum(x["status"]=="SAT_MODEL_VERIFIED" for x in results if x["arm"]=="Kissat4.0.4"),
 "CaDiCaL_verified_models":sum(x["status"]=="SAT_MODEL_VERIFIED" for x in results if x["arm"]=="CaDiCaL2.1.3"),
 "repetitions":2,"single_logical_cpu":CPU,
 "no_cdcl_fallback":True,
 "source_grammar_exact":True,
 "full_original_model_check":True,
 "source_clause_and_model_negative_controls_passed":True,
 "exhaustive_primary_input_search_not_a_polynomial_algorithm":True,
 "not_a_blind_holdout":True,
 "main_unmodified":True,
 "rows":results}
save(OUT/"summary.json",summary)
print("ATLAS20_FINAL "+json.dumps({k:v for k,v in summary.items() if k!="rows"},sort_keys=True),flush=True)
