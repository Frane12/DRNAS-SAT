#!/usr/bin/env python3
"""ATLAS10 serial, single-logical-CPU strict original-CNF proof benchmark.

One historical GBD masked-XOR UNSAT ORIGINAL plus two known-equivalent
permutations, three repeats, three arms = 27 trials; NOT nine independent
originals. A strict success requires independent external standard VeriPB
(Atlas) or DRAT-trim (references), reading the exact unchanged trial CNF.
Wall measurement includes original SHA check, solver/proof emission, external
checker and process startup, but not binary compilation or GitHub setup.
"""
from __future__ import annotations
import csv,hashlib,json,os,random,resource,subprocess,sys,time
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas10_paired_results"
OUT.mkdir(exist_ok=True)
PRE=json.loads((HERE/"prespec.json").read_text())
MAN=json.loads((ROOT/"atlas10_frozen/manifest.json").read_text())
assert MAN["status"]=="FROZEN_BEFORE_SOLVER_TESTS"
assert MAN["prespec_sha256"]==hashlib.sha256((HERE/"prespec.json").read_bytes()).hexdigest()
assert MAN["distinct_original_sources"]==1
assert len(MAN["inputs"])==3
ARMS=PRE["experimental_arm_scope"]
assert len(ARMS)==3 and PRE["repetitions"]==3
CAP=PRE["time_cap_e2e_s"]
SOLVE_CAP=PRE["solver_internal_wall_budget_s"]
assert CAP==30 and SOLVE_CAP==24
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
if len(os.sched_getaffinity(0))!=1:raise RuntimeError("CPU affinity missing")
BIN={
  "ATLAS9_SOURCE_VERIPB":None,
  "Kissat4.0.4_DRAT":ROOT/"kissat-src/build/kissat",
  "CaDiCaL2.1.3_DRAT":ROOT/"cadical-src/build/cadical"
}
DRAT=ROOT/"drat-trim-src/drat-trim"
assert all(p.exists() for p in BIN.values() if p is not None) and DRAT.exists()
def sha_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def child(cmd,limit,tag):
    """Bound time, memory, generated proof size, all inherited on single CPU."""
    started=time.perf_counter()
    def preexec():
        resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024**2,128*1024**2))
        resource.setrlimit(resource.RLIMIT_CPU,(38,40))
        os.sched_setaffinity(0,{CPU})
    try:
        proc=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,
             timeout=max(.1,limit),preexec_fn=preexec)
        output=proc.stdout+"\n"+proc.stderr
        (OUT/(tag+".log")).write_text(output[-15000:])
        return {"returncode":proc.returncode,"timeout":False,
                "stdout":proc.stdout,"stderr":proc.stderr,
                "seconds":round(time.perf_counter()-started,6)}
    except subprocess.TimeoutExpired:
        (OUT/(tag+".log")).write_text("TIMEOUT at "+str(limit))
        return {"returncode":None,"timeout":True,"stdout":"","stderr":"",
                "seconds":round(time.perf_counter()-started,6)}
def model_ok(source,out):
    n,cs=read_cnf(source)
    assignment={}
    for line in out.splitlines():
        if not line.startswith("v "):continue
        for v in line.split()[1:]:
            lit=int(v)
            if lit==0:continue
            if not 1<=abs(lit)<=n:return False
            if abs(lit) in assignment and assignment[abs(lit)]!=(lit>0):return False
            assignment[abs(lit)]=lit>0
    if len(assignment)!=n:return False
    return all(any(assignment[abs(lit)]==(lit>0) for lit in clause) for clause in cs)
def read_cnf(source):
    header=None;clauses=[];part=[]
    for line in Path(source).read_text().splitlines():
        w=line.split()
        if not w or w[0]=="c":continue
        if w[0]=="p":
            if header is not None:raise ValueError("two DIMACS headers")
            header=(int(w[2]),int(w[3]))
            continue
        for word in w:
            lit=int(word)
            if lit:part.append(lit)
            else:
                clauses.append(tuple(part));part=[]
    if header is None or part or len(clauses)!=header[1]:
        raise ValueError("invalid CNF source")
    return header[0],clauses

rows=[]
for src in MAN["inputs"]:
    filename=ROOT/src["path"]
    for rep in range(PRE["repetitions"]):
        sequence=list(ARMS)
        random.Random(f"ATLAS10_FIXED_ORDER:{src['raw_sha256']}:{rep}").shuffle(sequence)
        for arm in sequence:
            trialid=f"{src['label']}-rep{rep}-{arm}"
            start=time.perf_counter()
            # Source integrity is inside E2E budget.
            if sha_file(filename)!=src["raw_sha256"]:
                raise RuntimeError("SOURCE_CHANGED_"+src["label"])
            proof=OUT/(trialid+".proof")
            meta=OUT/(trialid+".meta.json")
            if arm=="ATLAS9_SOURCE_VERIPB":
                solver=child([sys.executable,HERE/"emit.py","--cnf",filename,
                    "--proof",proof,"--meta",meta],SOLVE_CAP,trialid+"-solve")
                emitted=(solver["returncode"]==0 and proof.is_file() and meta.is_file())
                if solver["returncode"]==0 and not emitted:
                    raise RuntimeError("PROOF_EMITTER_CLAIM_WITHOUT_PROOF")
            elif arm=="Kissat4.0.4_DRAT":
                solver=child([BIN[arm],"--no-binary",filename,proof],SOLVE_CAP,trialid+"-solve")
                emitted=(solver["returncode"]==20 and
                         "s UNSATISFIABLE" in solver["stdout"])
            else:
                solver=child([BIN[arm],"-q","--no-binary",filename,proof],SOLVE_CAP,trialid+"-solve")
                emitted=(solver["returncode"]==20 and
                         "s UNSATISFIABLE" in solver["stdout"])
            accepted=False;checker_s=0;reason="UNKNOWN"
            checker_rc=None;proof_sha=None;proof_size=0;checker_text=""
            critical=False
            if solver["timeout"]:
                reason="SOLVER_TIME_LIMIT"
            elif solver["returncode"]==10 and "s SATISFIABLE" in solver["stdout"]:
                if model_ok(filename,solver["stdout"]):
                    reason="SAT_MODEL_VERIFIED_CONTRADICTS_ORIGINAL_UNSAT_PROOF"
                    critical=True
                else:
                    reason="INVALID_SAT_MODEL"
                    critical=True
            elif emitted:
                if not proof.is_file() or proof.stat().st_size==0:
                    reason="SOLVER_UNSAT_WITHOUT_PROOF";critical=True
                else:
                    proof_size=proof.stat().st_size
                    proof_sha=sha_file(proof)
                    remaining=CAP-(time.perf_counter()-start)
                    if remaining<0.1:
                        reason="NO_EXTERNAL_CHECKER_TIME"
                    else:
                        check_args=([ "veripb","--cnf",filename,proof]
                                    if arm=="ATLAS9_SOURCE_VERIPB" else
                                    [DRAT,filename,proof,"-f"])
                        checker=child(check_args,remaining,trialid+"-check")
                        checker_s=checker["seconds"]
                        checker_rc=checker["returncode"]
                        checker_text=checker["stdout"]+checker["stderr"]
                        if checker["timeout"]:
                            reason="CHECKER_TIMEOUT"
                        else:
                            if arm=="ATLAS9_SOURCE_VERIPB":
                                accepted=(checker_rc==0 and
                                     "s VERIFIED UNSATISFIABLE" in checker_text)
                            else:
                                accepted=(checker_rc==0 and
                                      "s VERIFIED" in checker_text and
                                      "s NOT VERIFIED" not in checker_text)
                            if accepted:
                                reason="STRICT_EXTERNAL_PROOF_VERIFIED"
                            else:
                                reason="EXTERNAL_PROOF_REJECTED"
                                critical=True
            elif solver["returncode"] in (0,2):
                reason="UNKNOWN_SOLVER_NO_RESULT"
            elif solver["returncode"]==20:
                reason="SOLVER_UNSAT_STATUS_OR_PROOF_MISSING"
                critical=True
            elif solver["returncode"] in (None,-9,-24,-25):
                reason="UNKNOWN_RESOURCE_LIMIT"
            else:
                reason="UNKNOWN_SOLVER_EXIT_"+str(solver["returncode"])
            elapsed=time.perf_counter()-start
            strict=bool(accepted and elapsed<=CAP)
            if accepted and elapsed>CAP:
                reason="OVER_E2E_CAP"
            row={
              "source_label":src["label"],
              "original_source_sha256":MAN["source_original_sha256"],
              "trial_source_sha256":src["raw_sha256"],
              "underlying_original_independent_sources":1,
              "rep":rep,"arm":arm,"execution_order":sequence.index(arm),
              "solver_returncode":solver["returncode"],"solver_timeout":solver["timeout"],
              "solver_s":solver["seconds"],"checker_s":checker_s,
              "checker_returncode":checker_rc,"e2e_s":round(elapsed,6),
              "strict_verified":strict,"status":"UNSAT_EXTERNAL_VERIFIED" if strict else "UNKNOWN",
              "reason":reason,"proof_sha256":proof_sha,"proof_bytes":proof_size,
              "critical":critical,"PAR2_s":round(elapsed if strict else 2*CAP,6)
            }
            rows.append(row)
            (OUT/"trial-records.json").write_text(json.dumps(rows,indent=2,sort_keys=True)+"\n")
            print("ATLAS10_PAIRED_TRIAL "+json.dumps({
                k:row[k] for k in ("source_label","rep","arm","solver_s","checker_s","e2e_s","strict_verified","status","reason","PAR2_s")},sort_keys=True),flush=True)
            if critical:raise RuntimeError("CRITICAL_INVALID_OR_CONTRADICTORY_PROOF "+trialid+" "+reason)
assert len(rows)==len(MAN["inputs"])*PRE["repetitions"]*len(ARMS)==27
assert len({(r["source_label"],r["rep"],r["arm"]) for r in rows})==27

byarm={}
for arm in ARMS:
    armrows=[r for r in rows if r["arm"]==arm]
    byarm[arm]={
        "verified":sum(x["strict_verified"] for x in armrows),
        "attempts":len(armrows),
        "mean_e2e_s":round(sum(x["e2e_s"] for x in armrows)/len(armrows),6),
        "total_strict_PAR2_s":round(sum(x["PAR2_s"] for x in armrows),6),
        "status_counts":{s:sum(x["status"]==s for x in armrows)
                         for s in sorted({r["status"] for r in armrows})}
    }
groups={}
for source in sorted({r["source_label"] for r in rows}):
    groups[source]={arm:{
        "strict_verified":sum(x["strict_verified"] for x in rows if
           x["source_label"]==source and x["arm"]==arm),
        "PAR2_s":round(sum(x["PAR2_s"] for x in rows if
           x["source_label"]==source and x["arm"]==arm),6)}
        for arm in ARMS}
summary={
  "status":"COMPLETE" if not any(r["critical"] for r in rows) else "CRITICAL",
  "experiment":PRE["protocol"],
  "source_catalog_count":1,"correlated_permutation_variants":2,
  "total_trial_sources":3,"repetitions":PRE["repetitions"],
  "total_attempts":len(rows),"strict_e2e_cap_s":CAP,
  "reference_commit_sha256":PRE["reference_commit_sha256"],
  "one_cpu_serial":True,"source_original_sha256":MAN["source_original_sha256"],
  "arms":byarm,"per_source":groups,
  "all_external_proof_acceptance_require_exact_original_source":True,
  "no_world_rank_or_cross_family_claim":True,
  "limitation":"Only one previously evaluated historic UNSAT source plus 2 mathematically equivalent renamings; all measurements on same GitHub runner class, not necessarily same physical host across jobs.",
  "no_false_SAT_UNSAT":True,"main_untouched":True
}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS10_PAIRED_FINAL "+json.dumps(summary,sort_keys=True),flush=True)
