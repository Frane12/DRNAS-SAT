#!/usr/bin/env python3
"""ATLAS17 original-CNF cross-module cooperation audit, proof-first.

Always run single-arm detectors and joint fact exchange independently.
Only standard externally verified original-CNF UNSAT counts. The provenance
of selected inputs was frozen before executing this script.
"""
import hashlib, json, os, pathlib, resource, subprocess, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[2]
HOME=ROOT/"research/atlas17_probe"
SRC=ROOT/"atlas17_original_inputs"
OUT=ROOT/"atlas17_probe_results";OUT.mkdir(exist_ok=True)
P=json.loads((HOME/"prespec.json").read_text())
M=json.loads((SRC/"manifest.json").read_text())
assert M["status"]=="FROZEN_BEFORE_ANY_SOLVER"
assert M["prespec_sha256"]==hashlib.sha256((HOME/"prespec.json").read_bytes()).hexdigest()
assert M["no_source_substitution"]
ARM_LIMIT=float(P["cap_per_proof_arm_s"])
REF_LIMIT=float(P["per_reference_cap_s"])
CPU=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{CPU})
ARMS=("GRAPH_ONLY","HALL_ONLY","XOR_ONLY","PCMAX_WEIGHTED",
      "GRAPH_HALL","XOR_HALL","TRIPLE_HALL")
PUBLIC_ARM={"GRAPH_ONLY","HALL_ONLY","XOR_ONLY","PCMAX_WEIGHTED",
            "GRAPH_HALL","XOR_HALL","TRIPLE_HALL"}
def sha_file(p):
    digest=hashlib.sha256()
    with pathlib.Path(p).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):digest.update(chunk)
    return digest.hexdigest()
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n")
def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE,(96*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_AS,(4*1024*1024*1024,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(26,28))
def call(argv,deadline,log,stage):
    available=deadline-time.perf_counter()
    if available<=0.03:return {"status":"TIMEOUT","elapsed":0,"reason":"TOTAL_BUDGET_EXHAUSTED"}
    start=time.perf_counter()
    try:
        r=subprocess.run([str(x) for x in argv],
                         capture_output=True,text=True,errors="replace",
                         timeout=available,preexec_fn=limits)
        out=r.stdout+"\n"+r.stderr
        log.write_text(log.read_text()+f"\n[{stage}] rc={r.returncode}\n"+out[-4500:])
        return {"status":"RETURNED","rc":r.returncode,
                "elapsed":round(time.perf_counter()-start,6),
                "tail":out[-480:]}
    except subprocess.TimeoutExpired:
        log.write_text(log.read_text()+f"\n[{stage}] TIMEOUT\n")
        return {"status":"TIMEOUT","elapsed":round(time.perf_counter()-start,6),
                "reason":f"{stage}_TIMEOUT"}
def parse_model(source,output):
    # Validate every original clause if a full model is present. None => safe UNKNOWN.
    values={}
    for line in output.splitlines():
        if not line.startswith("v ") and line.strip()!="v":continue
        try: ints=[int(z) for z in line[1:].strip().split()]
        except ValueError:return None
        for lit in ints:
            if lit:values[abs(lit)]=(lit>0)
    if not values:return None
    n=None;m=None;seen=0;pending=[]
    with source.open("rb") as fd:
        for line in fd:
            cols=line.split()
            if not cols or cols[0]==b"c":continue
            if cols[0]==b"p":
                if n is not None or len(cols)!=4 or cols[1]!=b"cnf":raise AssertionError("SAT_BAD_SOURCE")
                n,m=int(cols[2]),int(cols[3]);continue
            for t in cols:
                lit=int(t)
                if lit==0:
                    seen+=1
                    if not any(values.get(abs(x))==(x>0) for x in pending):return False
                    pending=[]
                else:pending.append(lit)
    if n is None or seen!=m or pending:raise AssertionError("SAT_BAD_DIMACS")
    if set(values)<set(range(1,n+1)):return None
    return True
def checker(src,proof,deadline,log,kind):
    cmd=([ROOT/"drat-trim-src/drat-trim",src,proof,"-f"] if kind=="DRAT" else
         ["veripb","--cnf",src,proof])
    result=call(cmd,deadline,log,"EXTERNAL_"+kind)
    if result["status"]=="TIMEOUT":return "CHECK_TIMEOUT"
    good=(result["rc"]==0 and
         ("s VERIFIED UNSATISFIABLE" in result["tail"] if kind=="PBP" else
          "s VERIFIED" in result["tail"] and "s NOT VERIFIED" not in result["tail"]))
    if not good:raise AssertionError("EXTERNAL_ORIGINAL_PROOF_REJECTED "+kind+" "+str(result))
    return "VERIFIED"
def proof_arm(source,sha,arm):
    base=OUT/"arms"/sha[:16]/arm;base.mkdir(parents=True,exist_ok=True)
    proof=base/"new.pbp";meta=base/"details.json";claims=base/"facts.json"
    cert=base/"capacity.json";log=base/"evidence.log"
    log.write_text("")
    proof.unlink(missing_ok=True)
    start=time.perf_counter();deadline=start+ARM_LIMIT
    py=sys.executable
    action=None
    if arm in ("GRAPH_ONLY","HALL_ONLY"):
        mode=arm
        action=[py,ROOT/"research/atlas14_five/modes.py",
                "--mode",mode,"--cnf",source,"--proof",proof,"--meta",meta]
    elif arm in ("GRAPH_HALL","XOR_HALL","TRIPLE_HALL"):
        action=[py,ROOT/"research/atlas15_exchange/bridge.py",
                "--cnf",source,"--mode",arm,"--claims",claims,
                "--proof",proof,"--meta",meta]
    elif arm=="XOR_ONLY":
        action=[py,ROOT/"research/xorlin1/extract.py",
                "--cnf",source,"--certificate",cert,"--meta",meta]
    elif arm=="PCMAX_WEIGHTED":
        action=[ROOT/"build/drnas-pcmax",source,"--mode","core","--time","7",
                "--pcmax-only","--pcmax-capacity","--pcmax-budget-ms","5000",
                "--pcmax-certificate",cert]
    else:raise AssertionError("UNRECOGNIZED_MODE")
    emitted=call(action,deadline,log,"DISCOVER")
    why="UNKNOWN";proof_verified=False
    if emitted["status"]=="TIMEOUT":why="DETECTOR_TIMEOUT"
    elif emitted["rc"] in (0,20):
        if arm=="XOR_ONLY" and emitted["rc"]==0 and cert.exists():
            emitted=call([py,ROOT/"research/xorlin1/emit_veripb.py",
                 "--cnf",source,"--certificate",cert,"--output",proof,
                 "--meta",base/"xor_emitter.json"],deadline,log,"EMIT_XOR")
        elif arm=="PCMAX_WEIGHTED" and emitted["rc"]==20:
            if not cert.exists():raise AssertionError("UNVERIFIED_NATIVE_UNSAT_NO_CERT")
            check=call([py,ROOT/"research/pcmax_capacity/check_capacity.py",
                        source,cert],deadline,log,"CHECK_NATIVE_CAPACITY")
            if check["status"]=="RETURNED" and check["rc"]==0:
                emitted=call([py,ROOT/"research/pcmax_capacity/emit_veripb_capacity_weighted2.py",
                    "--cnf",source,"--certificate",cert,"--output",proof],
                    deadline,log,"EMIT_WEIGHTED")
            elif check["status"]=="TIMEOUT":emitted=check
            else:raise AssertionError("NATIVE_CAPACITY_CERTIFICATE_REJECTED "+str(check))
        elif arm=="PCMAX_WEIGHTED" and emitted["rc"]==0:
            emitted={"status":"UNKNOWN","reason":"NATIVE_RETURNED_UNKNOWN"}
        if emitted["status"]=="RETURNED" and emitted["rc"]==0 and proof.is_file() and proof.stat().st_size>0:
            proof_verified=checker(source,proof,deadline,log,"PBP")=="VERIFIED"
            why="UNSAT_VERIFIED" if proof_verified else "CHECK_TIMEOUT"
        elif emitted["status"]=="TIMEOUT":why="EMITTER_OR_CHECK_TIMEOUT"
        elif emitted["status"]=="UNKNOWN":why=emitted["reason"]
        elif emitted["status"]=="RETURNED" and emitted["rc"]==2:why="EMITTER_UNKNOWN"
        else:why="NO_STANDARD_PROOF"
    elif emitted["rc"]==2:why="STRUCTURE_UNSUPPORTED"
    else:why="RESOURCE_OR_PROBE_ERROR"
    elapsed=round(time.perf_counter()-start,6)
    if sha_file(source)!=sha:raise AssertionError("ORIGINAL_SHA_CHANGED_DURING_PROOF")
    if proof_verified and elapsed>ARM_LIMIT:proof_verified=False;why="E2E_OVER_CAP"
    out={"arm":arm,"status":"UNSAT_VERIFIED" if proof_verified else "UNKNOWN",
         "reason":why,"e2e_s":elapsed,"source_sha256":sha,
         "proof_bytes":proof.stat().st_size if proof.is_file() else 0,
         "proof_sha256":sha_file(proof) if proof.is_file() else None,
         "source_original_proof_checked":proof_verified,
         "producer_rc":emitted.get("rc")}
    save(base/"trial.json",out)
    return out
def reference(source,sha,arm):
    folder=OUT/"reference"/sha[:16]/arm;folder.mkdir(parents=True,exist_ok=True)
    proof=folder/"candidate.drat";log=folder/"evidence.log";log.write_text("")
    start=time.perf_counter();deadline=start+REF_LIMIT
    binary=(ROOT/"kissat-src/build/kissat" if arm=="Kissat4.0.4" else
            ROOT/"cadical-src/build/cadical")
    cmd=[binary,"--no-binary",source,proof] if arm=="Kissat4.0.4" else [binary,"--no-binary",source,proof]
    r=call(cmd,deadline,log,"REFERENCE")
    ok=None;reason="UNKNOWN";status="UNKNOWN"
    if r["status"]=="TIMEOUT":reason="SOLVER_TIMEOUT"
    elif r["rc"]==20:
        if proof.is_file() and proof.stat().st_size:
            ok=checker(source,proof,deadline,log,"DRAT")
            if ok=="VERIFIED":status="UNSAT_VERIFIED";reason="DRAT_VERIFIED"
            else:reason=ok
        else:reason="NO_STANDARD_PROOF"
    elif r["rc"]==10:
        # Only a complete independently checked assignment is a confirmed SAT.
        text=log.read_text()
        verified=parse_model(source,text)
        if verified is True:status="SAT_MODEL_VERIFIED";reason="ORIGINAL_MODEL_CHECKED"
        elif verified is False:raise AssertionError("REFERENCE_RETURNED_INVALID_SAT_MODEL")
        else:reason="SAT_NOT_INDEPENDENTLY_MODEL_VERIFIED"
    else:reason="RESOURCE_OR_UNKNOWN"
    elapsed=round(time.perf_counter()-start,6)
    if elapsed>REF_LIMIT:status="UNKNOWN";reason="E2E_OVER_CAP"
    if sha_file(source)!=sha:raise AssertionError("REFERENCE_SOURCE_HASH_CHANGED")
    row={"arm":arm,"status":status,"reason":reason,"e2e_s":elapsed,
         "proof_bytes":proof.stat().st_size if proof.is_file() else 0,
         "source_sha256":sha}
    save(folder/"trial.json",row)
    return row
rows=[]
for item in M["sources"]:
    path=ROOT/item["path"];digest=item["sha256"]
    if sha_file(path)!=digest:raise AssertionError("MISSING_OR_CHANGED_ORIGINAL_SOURCE")
    row={"name":item["name"],"cohort":item["cohort"],"sha256":digest,
         "variables":item["variables"],"clauses":item["clauses"],"arms":{}}
    for mode in ARMS:
        row["arms"][mode]=proof_arm(path,digest,mode)
        print("ATLAS17_ARM "+json.dumps({"name":item["name"],"cohort":item["cohort"],
              **{k:row["arms"][mode][k] for k in ("arm","status","reason","e2e_s")}},sort_keys=True),flush=True)
    strict=lambda m:row["arms"][m]["status"]=="UNSAT_VERIFIED"
    singles=any(strict(a) for a in ("GRAPH_ONLY","HALL_ONLY","XOR_ONLY","PCMAX_WEIGHTED"))
    pair_graph=strict("GRAPH_HALL") and not strict("GRAPH_ONLY") and not strict("HALL_ONLY")
    pair_xor=strict("XOR_HALL") and not strict("XOR_ONLY") and not strict("HALL_ONLY")
    triple=(strict("TRIPLE_HALL") and not singles and
            not strict("GRAPH_HALL") and not strict("XOR_HALL"))
    row["synergy"]={"graph_plus_hall_only":pair_graph,"xor_plus_hall_only":pair_xor,
                    "genuine_three_way_only":triple,
                    "any_proof":any(strict(a) for a in ARMS),
                    "no_individual_verified":not singles}
    if item["cohort"]=="public_preselected":
        for arm in ("Kissat4.0.4","CaDiCaL2.1.3"):
            row.setdefault("references",{})[arm]=reference(path,digest,arm)
    rows.append(row)
    save(OUT/"summary.json",{"status":"IN_PROGRESS","rows":rows})
    print("ATLAS17_SOURCE "+json.dumps({"name":row["name"],"cohort":row["cohort"],
        "proof_by_module":{k:v["status"] for k,v in row["arms"].items()},
        "synergy":row["synergy"],"references":row.get("references")},sort_keys=True),flush=True)
public=[r for r in rows if r["cohort"]=="public_preselected"]
ret=[r for r in rows if r["cohort"]=="retrospective_known"]
def count(label,pool):return sum(bool(r["synergy"][label]) for r in pool)
summary={"status":"COMPLETE","source_cohort":len(rows),
         "public_preselected":len(public),"public_unavailable":len(M["failures"]),
         "retrospective_known":len(ret),"public_verified_by_any":count("any_proof",public),
         "retrospective_verified_by_any":count("any_proof",ret),
         "public_genuine_three_way_only":count("genuine_three_way_only",public),
         "public_pairwise_graph_hall_only":count("graph_plus_hall_only",public),
         "public_pairwise_xor_hall_only":count("xor_plus_hall_only",public),
         "retrospective_genuine_three_way_only":count("genuine_three_way_only",ret),
         "proofs_only_externally_VERIPB":True,"main_untouched":True,
         "zero_cdcl_fallback":True,"no_world_rank_claim":True,
         "single_cpu":CPU,"cap_s":ARM_LIMIT,
         "unavailable_public":M["failures"],
         "rows":rows}
save(OUT/"summary.json",summary)
print("ATLAS17_FINAL "+json.dumps({k:v for k,v in summary.items()
      if k not in ("rows","unavailable_public")},sort_keys=True),flush=True)
