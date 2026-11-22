#!/usr/bin/env python3
"""ATLAS14 strict original-source 5-family real benchmark; all 30 attempts.

One logical CPU in serial. Six fixed ablation/reference arms on five
precommitted *distinct original* CNF files. E2E wall includes hash check,
process startup, full proof emission/solving and *external* standard proof
verification on identical SHA-locked original CNF bytes. A status label or
an emitted proof alone never constitutes UNSAT.

Historical proofs are independently rechecked only as a separate regression,
not used for source solver trials, and never influence source selection.
"""
from __future__ import annotations
import hashlib,json,os,random,resource,subprocess,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas14_results";OUT.mkdir(exist_ok=True)
P=json.loads((HERE/"prespec.json").read_text())
M=json.loads((ROOT/"atlas14_frozen/manifest.json").read_text())
assert P["protocol"]=="DRNAS-ATLAS14-ORIGINAL-FIVE-FAMILY-ABLATION-PILOT-20261122"
assert M["status"]=="FROZEN_BEFORE_ANY_ATLAS14_TRIAL"
assert M["source_prespec_sha256"]==hashlib.sha256((HERE/"prespec.json").read_bytes()).hexdigest()
assert len(M["sources"])==P["expected_trials"]//len(P["arms"])==5
assert len(P["arms"])==6
CPU=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{CPU})
assert len(os.sched_getaffinity(0))==1
CAP=P["strict_e2e_cap_s"]
assert CAP==12
BINS={
  "Kissat4.0.4":ROOT/"kissat-src/build/kissat",
  "CaDiCaL2.1.3":ROOT/"cadical-src/build/cadical",
}
DRAT=ROOT/"drat-trim-src/drat-trim"
assert all(path.is_file() for path in BINS.values()) and DRAT.is_file()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fp:
        for chunk in iter(lambda:fp.read(65536),b""):h.update(chunk)
    return h.hexdigest()
def call(args,limit,label):
    started=time.perf_counter()
    def bounds():
        resource.setrlimit(resource.RLIMIT_AS,(P["memory_cap_bytes"],)*2)
        resource.setrlimit(resource.RLIMIT_FSIZE,(P["proof_file_max_bytes"],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(20,22))
        os.sched_setaffinity(0,{CPU})
    try:
        p=subprocess.run([str(a) for a in args],capture_output=True,text=True,
            timeout=max(.1,limit),preexec_fn=bounds)
        (OUT/(label+".log")).write_text((p.stdout+"\n"+p.stderr)[-15000:])
        return p.returncode,p.stdout,p.stderr,False,round(time.perf_counter()-started,6)
    except subprocess.TimeoutExpired:
        (OUT/(label+".log")).write_text("TIMEOUT "+str(limit)+"\n")
        return None,"","",True,round(time.perf_counter()-started,6)
def clauses(raw):
    n=m=None;rows=[];pending=[]
    for line in raw.decode("ascii").splitlines():
        z=line.split()
        if not z or z[0]=="c":continue
        if z[0]=="p":
            assert n is None
            n,m=map(int,z[2:]);continue
        for x in z:
            v=int(x)
            if v:pending.append(v)
            else:rows.append(tuple(pending));pending=[]
    assert n is not None and not pending and len(rows)==m
    return n,rows
def checked_sat_model(raw,stdout):
    n,rows=clauses(raw)
    assign={}
    for ln in stdout.splitlines():
        if ln.startswith("v "):
            for word in ln[2:].split():
                lit=int(word)
                if lit==0:continue
                if not 1<=abs(lit)<=n or (abs(lit) in assign and assign[abs(lit)]!=(lit>0)):
                    return False
                assign[abs(lit)]=lit>0
    return len(assign)==n and all(any(assign[abs(v)]==(v>0) for v in row) for row in rows)
all_rows=[]
for item in M["sources"]:
    source=ROOT/item["path"]
    assert sha(source)==item["source_sha256"],"SOURCE_CHANGED"
    print("ATLAS14_INPUT_SHA_PASS "+json.dumps({"id":item["id"],"sha":item["source_sha256"]},sort_keys=True),flush=True)
    order=list(P["arms"])
    random.Random("ATLAS14_SOURCE_ORDER_"+item["source_sha256"]).shuffle(order)
    for arm in order:
        idx=len(all_rows)
        tag=f"{item['id']}-{arm}"
        started=time.perf_counter()
        if sha(source)!=item["source_sha256"]:raise RuntimeError("SOURCE_CHANGED_DURING_TRIAL")
        proof=OUT/(tag+".proof")
        meta=OUT/(tag+".meta.json")
        structural=arm in ("GRAPH_ONLY","HALL_ONLY","EXCHANGE_ONLY","BRIDGE_FULL")
        if structural:
            command=[sys.executable,HERE/"modes.py","--mode",arm,
                "--cnf",source,"--proof",proof,"--meta",meta]
        elif arm=="Kissat4.0.4":
            command=[BINS[arm],"--no-binary",source,proof]
        else:
            command=[BINS[arm],"-q","--no-binary",source,proof]
        rem=CAP-(time.perf_counter()-started)
        rc,stdout,stderr,timedout,producing_s=call(command,rem,tag+"-produce")
        strict=False;verified_model=False;checker_s=0;reason="UNKNOWN"
        checker_rc=None;checker_output=""
        size=proof.stat().st_size if proof.exists() else 0
        psha=sha(proof) if size>0 else None
        if timedout:
            reason="PRODUCER_TIMEOUT"
        elif rc==10 and not structural and "s SATISFIABLE" in stdout:
            if checked_sat_model(source.read_bytes(),stdout):
                verified_model=True;reason="SAT_MODEL_ORIGINAL_VERIFIED"
            else:
                raise RuntimeError("INVALID_REFERENCE_SAT_MODEL_"+tag)
        elif (structural and rc==0) or (not structural and rc==20 and "s UNSATISFIABLE" in stdout):
            if size==0:raise RuntimeError("UNSAT_REPORTED_WITH_NO_PROOF_"+tag)
            rem=CAP-(time.perf_counter()-started)
            if rem<=0.1:
                reason="NO_PROOF_CHECK_BUDGET"
            else:
                check_cmd=(["veripb","--cnf",source,proof] if structural else [DRAT,source,proof,"-f"])
                checker_rc,co,ce,ct,checker_s=call(check_cmd,rem,tag+"-check")
                checker_output=co+ce
                if ct:reason="PROOF_CHECK_TIMEOUT"
                else:
                    strict=bool(checker_rc==0 and
                        ("s VERIFIED UNSATISFIABLE" in checker_output if structural else
                         "s VERIFIED" in checker_output and "s NOT VERIFIED" not in checker_output))
                    reason="STANDARD_ORIGINAL_PROOF_VERIFIED" if strict else "EXTERNAL_PROOF_REJECTED"
                    if not strict:raise RuntimeError("INVALID_EXTERNAL_PROOF_"+tag+":"+checker_output[-350:])
        elif rc in (0,2):
            reason="SAFE_UNKNOWN"
        elif rc in (None,-9,-24,-25):
            reason="RESOURCE_OR_LIMIT_UNKNOWN"
        elif rc==20:
            raise RuntimeError("INVALID_UNVERIFIED_UNSAT_STATUS_"+tag)
        elif rc is not None:
            # Python solver mode failure is unknown; do not conceal.
            reason="PRODUCER_ERROR_RC_"+str(rc)
        elapsed=round(time.perf_counter()-started,6)
        strict=bool(strict and elapsed<=CAP)
        row={
          "source_id":item["id"],"family_for_reporting_only":item["family_for_reporting_only"],
          "source_sha256":item["source_sha256"],"arm":arm,"rep":0,
          "status":"UNSAT_VERIPB_OR_DRAT_VERIFIED" if strict else
                     ("SAT_MODEL_VERIFIED" if verified_model else "UNKNOWN"),
          "reason":reason,"strict_verification":strict,
          "sat_model_verification":verified_model,
          "e2e_s":elapsed,"producer_s":producing_s,
          "checker_s":checker_s,"proof_bytes":size,
          "proof_sha256":psha,"producer_rc":rc,"checker_rc":checker_rc,
          "PAR2_s":round(elapsed if (strict or verified_model) else P["par2_penalty_s"],6)}
        all_rows.append(row)
        (OUT/"all-trials.json").write_text(json.dumps(all_rows,sort_keys=True,indent=2)+"\n")
        print("ATLAS14_TRIAL "+json.dumps({k:row[k] for k in ("source_id","arm","status","reason","producer_s","checker_s","e2e_s","proof_bytes")},sort_keys=True),flush=True)

assert len(all_rows)==P["expected_trials"]
assert len({(r["source_id"],r["arm"],r["rep"]) for r in all_rows})==len(all_rows)
# Grounded older *stored* standard proof of each old source is checked
# separately, NOT included as solver arm or proof-discovery performance.
history=[]
for item in M["sources"]:
    source=ROOT/item["path"]
    proof=ROOT/item["historical_standard_proof"]
    assert sha(source)==item["source_sha256"]
    assert sha(proof)==item["historical_proof_sha256"]
    rc,stdout,stderr,timeout,sec=call(["veripb","--cnf",source,proof],min(CAP,12),
                                        item["id"]+"-HISTORICAL-PROOF-CHECK")
    ok=rc==0 and "s VERIFIED UNSATISFIABLE" in stdout+stderr
    history.append({"source_id":item["id"],"historical_proof_standard_veripb_accepted":ok,
                    "checker_s":sec,"proof_bytes":item["historical_proof_bytes"],
                    "not_a_new_solver_result":True})
    print("ATLAS14_EXISTING_STORED_PROOF_REGRESSION "+json.dumps(history[-1],sort_keys=True),flush=True)
summary={
    "status":"COMPLETE","source_originals":len(M["sources"]),
    "family_labels":M["distinct_family_labels"],"repetitions":P["repetitions"],
    "total_trials":len(all_rows),"strict_e2e_cap_s":CAP,
    "arms":{arm:{"attempts":len([r for r in all_rows if r["arm"]==arm]),
         "accepted_standard_UNSAT":sum(r["strict_verification"] for r in all_rows if r["arm"]==arm),
         "SAT_models":sum(r["sat_model_verification"] for r in all_rows if r["arm"]==arm),
         "PAR2_total_s":round(sum(r["PAR2_s"] for r in all_rows if r["arm"]==arm),6)}
       for arm in P["arms"]},
    "by_source":{item["id"]:{r["arm"]:{"status":r["status"],"e2e_s":r["e2e_s"],"reason":r["reason"]}
        for r in all_rows if r["source_id"]==item["id"]} for item in M["sources"]},
    "historical_proof_checks":history,
    "source_originals_all_SHA_checked":True,
    "source_labels_never_passed_to_discovery":True,
    "external_standard_proofs_only":True,
    "experimental_source_selection":"Previously published original CNFs from repo; retrospective five-source pilot, not blind.",
    "note":"One repetition pilot, known source sample; no statistically defensible solver superiority conclusion",
    "no_main_modifications":True}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS14_FINAL "+json.dumps(summary,sort_keys=True),flush=True)
