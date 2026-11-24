#!/usr/bin/env python3
"""ATLAS16 preliminary proof-first pilot. No main edits, no CDCL inside DRNAS router.

Two populations are reported separately:
  (A) archived published original CNFs, tested from raw source bytes;
  (B) newly generated controlled GRAPH/XOR/HALL sources and a SAT mutation.
The generator seeds are predeclared, but constructed examples are NOT blind.
Old evidence certificates/proofs are NEVER inputs to the router.
"""
import argparse
import ast
import hashlib
import importlib.util
import itertools
import json
import os
import random
import subprocess
import sys
import time
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas16_pilot_results"
sys.path.insert(0,str(ROOT))
for p in ("research/atlas15_exchange","research/atlas13_exchange",
          "research/pcmax_capacity","research/structure_atlas1","research/graphclique"):
    sys.path.insert(0,str(ROOT/p))
sys.path.insert(0,str(ROOT/"research/atlas15_exchange"))
from atlas import parse, encoded, transform
from bridge import compile_original as exchange_compile, HallUnknown
from facts import Unknown as ExchangeUnknown
from witness import verify_full_original_sat_model
from check_capacity import check as capacity_check
from emit_veripb_capacity_weighted2 import generate as weighted_proof
from research.atlas_eo import decode as eo_decode, check as eo_check
from research.atlas_eo.route import candidate as eo_candidate
gpath=ROOT/"research/graphclique/emit_veripb.py"
spec=importlib.util.spec_from_file_location("atlas16_graph_module",gpath)
graph=importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph)
CPU=min(os.sched_getaffinity(0))
os.sched_setaffinity(0,{CPU})
CAP=15.0
def sha(data): return hashlib.sha256(data).hexdigest()
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n")
def verify_standard(cnf,proof,kind,limit=20):
    cmd=(["veripb","--cnf",str(cnf),str(proof)] if kind=="pb"
         else [str(ROOT/"drat-trim-src/drat-trim"),str(cnf),str(proof),"-f"])
    try: r=subprocess.run(cmd,capture_output=True,text=True,timeout=limit)
    except subprocess.TimeoutExpired: return "CHECK_TIMEOUT"
    except FileNotFoundError: return "CHECKER_UNAVAILABLE"
    msg=r.stdout+"\n"+r.stderr
    if r.returncode==0 and ("s VERIFIED UNSATISFIABLE" in msg if kind=="pb"
                            else "s VERIFIED" in msg and "s NOT VERIFIED" not in msg):
        return "ACCEPTED"
    raise AssertionError("EXTERNAL_CHECK_REJECTED: "+str(cmd)+" "+msg[-900:])
def get_generator():
    """Reuse exactly the ATLAS15 construction functions, not its benchmark side effects."""
    src=(ROOT/"research/atlas15_exchange/audit.py").read_text()
    parsed=ast.parse(src)
    names={"allow","masks","build"}
    definitions=[n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert len(definitions)==3
    module=ast.fix_missing_locations(ast.Module(body=definitions,type_ignores=[]))
    env={"random":random,"itertools":itertools,"encoded":encoded,"parse":parse,"hashof":sha}
    exec(compile(module,"frozen_ATLAS15_fixture_generators","exec"),env)
    return env["build"]
def sources():
    pin=[
        ("graph-k11","evidence/graph-k11/original.cnf",
         "69d4e0ad868e920920d214acaf0c37f52870655ecc8a6807fd1ee3e4dcaa91e0"),
        ("pcmax-m00","evidence/pcmax-weighted2/00/original.cnf",
         "c55ab8fe2c9e10f0579f806802bc32d04913f12cd6ce28e6662b8d59d114c174"),
        ("pcmax-m05","evidence/pcmax-weighted2/05/original.cnf",
         "a540b7d1aa098217bde5145b56f1f8e4898e9fedd73ea1ad99259ed43fa1e275")]
    cases=[]
    for name,path,expected in pin:
        source=ROOT/path
        assert sha(source.read_bytes())==expected,(name,"ORIGINAL_SHA_CHANGED")
        cases.append({"name":name,"type":"archived_original","source":source,
                      "sha256":expected})
    build=get_generator()
    raw5,m5=build(5,seed=66005)
    raw6,m6=build(6,seed=66006)
    n6,c6=parse(raw6)
    renamed,equiv,_=transform(n6,c6,seed=90666,rename=True,flip=False,shuffle=True)
    assert equiv
    constructed=[("joint-k5-seed66005",raw5),("joint-k6-seed66006",raw6),
                 ("joint-k6-renamed",renamed)]
    for name,raw in constructed:
        path=OUT/"input"/(name+".cnf")
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
        cases.append({"name":name,"type":"constructed_joint","source":path,
                      "sha256":sha(raw)})
    # Deliberate SAT negative: drop precisely one essential XOR truth-table clause.
    blocker=tuple(sorted((m6["selectors"][(0,0)],m6["selectors"][(1,0)])))
    assert m6["auxiliary_roles"][blocker]["kind"]=="XOR"
    mutated,desc=build(6,seed=66006,remove_xor_blocker=blocker)
    assert desc["selectors"]==m6["selectors"]
    chosen=[0,0,1,2,3,4,5]
    model={v:(chosen[g]==color) for (g,color),v in desc["selectors"].items()}
    for pair,info in desc["auxiliary_roles"].items():
        a,b=pair
        model[info["aux"]]=(True if info["kind"]=="XOR" else model[a])
    nv,_=parse(mutated)
    witness={"source_sha256":sha(mutated),
             "assignment":[None]+[model[v] for v in range(1,nv+1)]}
    checked=verify_full_original_sat_model(mutated,witness)
    assert checked["status"]=="INDEPENDENT_ORIGINAL_SOURCE_SAT_MODEL_VERIFIED"
    satpath=OUT/"input"/"joint-k6-sat-mutation.cnf"
    satpath.write_bytes(mutated)
    save(OUT/"sat_control_witness.json",witness)
    cases.append({"name":"joint-k6-sat-mutation","type":"constructed_SAT_control",
                  "source":satpath,"sha256":sha(mutated)})
    frozen=[{"name":c["name"],"type":c["type"],"sha256":c["sha256"],
             "variables":parse(c["source"].read_bytes())[0],
             "clauses":len(parse(c["source"].read_bytes())[1])} for c in cases]
    save(OUT/"frozen_inputs.json",frozen)
    print("ATLAS16_SOURCE_FREEZE "+json.dumps(frozen,sort_keys=True),flush=True)
    return cases
def native_capacity(cnf,folder,binfile):
    certificate=folder/"newly_detected_capacity.json"
    cmd=[str(binfile),str(cnf),"--mode","core","--time","7",
         "--pcmax-only","--pcmax-capacity","--pcmax-budget-ms","5000",
         "--pcmax-certificate",str(certificate)]
    try: r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
    except subprocess.TimeoutExpired: return None,"NATIVE_TIMEOUT"
    (folder/"native.log").write_text(r.stdout+"\n"+r.stderr)
    if r.returncode!=20 or "s UNSATISFIABLE" not in r.stdout or not certificate.is_file():
        if r.returncode==20: raise AssertionError("NATIVE_UNSAT_WITHOUT_CERTIFICATE")
        return None,"NATIVE_NO_CERTIFICATE"
    evidence=capacity_check(cnf.read_bytes(),json.loads(certificate.read_text()))
    if evidence["status"]!="UNSAT_STRUCTURAL_CERTIFICATE_VERIFIED":
        raise AssertionError("NATIVE_CAPACITY_CERTIFICATE_REJECTED")
    proof=folder/"native-weighted.pbp"
    details=weighted_proof(cnf,certificate,proof)
    assert details["status"]=="EMITTED_UNCHECKED"
    return proof,"PCMAX_SOURCE_CAPACITY"
def auto(case,binfile,*,folder=None,eo_only=False,enable_eo=True):
    cnf=case["source"]
    raw=cnf.read_bytes()
    folder=folder if folder is not None else OUT/"auto"/case["name"]
    folder.mkdir(parents=True,exist_ok=True)
    attempts=[]
    start=time.perf_counter()
    # Source-only recognition. No expected status or filename is given to a module.
    modes = ("GRAPH_SOURCE","TRIPLE_FACT_EXCHANGE","PCMAX_NATIVE_WEIGHTED","EO")
    if not enable_eo:
        modes=modes[:-1]
    for mode in (("EO",) if eo_only else modes):
        if time.perf_counter()-start >= CAP:
            attempts.append({"mode":mode,"status":"UNKNOWN","reason":"end-to-end time limit"})
            break
        details={}
        try:
            if mode=="GRAPH_SOURCE":
                candidate,_=graph.compile_source(raw,max_trials=50000)
                proof=folder/"graph.pbp"
                proof.write_text(candidate)
            elif mode=="TRIPLE_FACT_EXCHANGE":
                proof=folder/"triple.pbp"
                exchange_compile(cnf,"TRIPLE_HALL",folder/"facts.json",proof,
                                 folder/"exchange_meta.json")
            elif mode=="EO":
                details=eo_candidate(raw,folder)
                mode=details.pop("mode")
                if "model" in details:
                    model=details.pop("model")
                    verify_full_original_sat_model(raw,model)
                    save(folder/"model.json",model)
                    elapsed=round(time.perf_counter()-start,6)
                    status="SAT_VERIFIED" if elapsed<=CAP else "VERIFIED_BUT_OVER_15S"
                    result={"status":status,"mode":mode,"e2e_s":elapsed,"attempts":attempts,
                            "source_sha256":sha(raw),**details}
                    save(folder/"result.json",result)
                    return result
                proof=details.pop("proof",None)
                if proof is None:
                    attempts.append({"mode":mode,"status":"UNKNOWN",**details})
                    continue
            else:
                if not binfile.is_file():
                    attempts.append({"mode":mode,"status":"UNKNOWN","reason":"native binary unavailable"})
                    continue
                proof,reason=native_capacity(cnf,folder,binfile)
                if proof is None:
                    attempts.append({"mode":mode,"status":"UNKNOWN","reason":reason})
                    continue
            remaining=CAP-(time.perf_counter()-start)
            checked=verify_standard(cnf,proof,"pb",limit=remaining) if remaining>0 else "CHECK_TIMEOUT"
            if checked!="ACCEPTED":
                attempts.append({"mode":mode,"status":"UNKNOWN","reason":checked})
                break
            elapsed=round(time.perf_counter()-start,6)
            status=("UNSAT_VERIFIED" if elapsed<=CAP else "VERIFIED_BUT_OVER_15S")
            result={"status":status,"mode":mode,"e2e_s":elapsed,
                    "proof_bytes":proof.stat().st_size,
                    "proof_sha256":sha(proof.read_bytes()),"attempts":attempts,
                    "source_sha256":sha(raw),**details}
            save(folder/"result.json",result)
            return result
        except (graph.Unsupported,ExchangeUnknown,HallUnknown,ValueError) as e:
            attempts.append({"mode":mode,"status":"UNKNOWN","reason":str(e)[:220]})
            continue
    result={"status":"UNKNOWN","mode":None,"source_sha256":sha(raw),
            "e2e_s":round(time.perf_counter()-start,6),"attempts":attempts}
    save(folder/"result.json",result)
    return result
def previous_bridge(case):
    cnf=case["source"]
    folder=OUT/"old_atlas14"/case["name"]
    folder.mkdir(parents=True,exist_ok=True)
    proof=folder/"old.pbp"
    start=time.perf_counter()
    cmd=[sys.executable,str(ROOT/"research/atlas14_five/modes.py"),
         "--mode","BRIDGE_FULL","--cnf",str(cnf),"--proof",str(proof),
         "--meta",str(folder/"old.json")]
    try:r=subprocess.run(cmd,capture_output=True,text=True,timeout=12)
    except subprocess.TimeoutExpired:
        return {"status":"UNKNOWN","reason":"PRODUCER_TIMEOUT","e2e_s":12}
    (folder/"producer.log").write_text(r.stdout+"\n"+r.stderr)
    if r.returncode!=0 or not proof.is_file():
        return {"status":"UNKNOWN","reason":"SAFE_UNKNOWN","e2e_s":
                round(time.perf_counter()-start,6)}
    checked=verify_standard(cnf,proof,"pb",limit=max(1,CAP-(time.perf_counter()-start)))
    elapsed=round(time.perf_counter()-start,6)
    return {"status":"UNSAT_VERIFIED" if checked=="ACCEPTED" and elapsed<=CAP
            else "UNKNOWN","e2e_s":elapsed,"proof_bytes":proof.stat().st_size}
def reference(name,cnf,*,folder=None,solver_limit=12):
    folder=folder if folder is not None else OUT/"reference"/cnf.stem/name
    folder.mkdir(parents=True,exist_ok=True)
    proof=folder/"candidate.drat"
    binpath=(ROOT/"kissat-src/build/kissat" if name=="Kissat4.0.4"
             else ROOT/"cadical-src/build/cadical")
    cmd=([str(binpath),"--no-binary",str(cnf),str(proof)]
         if name=="Kissat4.0.4" else
         [str(binpath),"-q","--no-binary",str(cnf),str(proof)])
    start=time.perf_counter()
    try:r=subprocess.run(cmd,capture_output=True,text=True,timeout=min(CAP,solver_limit))
    except subprocess.TimeoutExpired:
        return {"status":"UNKNOWN","reason":"TIMEOUT","e2e_s":round(time.perf_counter()-start,6)}
    (folder/"solver.log").write_text(r.stdout+"\n"+r.stderr)
    if r.returncode==10:
        raw=cnf.read_bytes()
        n,_=parse(raw)
        values={}
        for line in r.stdout.splitlines():
            if line.split()[:1]!=["v"]:
                continue
            for x in map(int,line.split()[1:]):
                if not x:
                    continue
                if abs(x)>n or (abs(x) in values and values[abs(x)]!=(x>0)):
                    raise AssertionError("invalid reference SAT assignment")
                values[abs(x)]=x>0
        bits=[None]+[values.get(v,False) for v in range(1,n+1)]
        model={"source_sha256":sha(raw),"assignment":bits}
        try:
            verify_full_original_sat_model(raw,model)
        except ValueError:
            return {"status":"UNKNOWN","reason":"reference SAT model did not verify",
                    "e2e_s":round(time.perf_counter()-start,6)}
        save(folder/"model.json",model)
        elapsed=round(time.perf_counter()-start,6)
        return {"status":"SAT_VERIFIED" if elapsed<=CAP else "UNKNOWN",
                "e2e_s":elapsed,"reason":"whole-source model"}
    if r.returncode==20 and proof.is_file() and proof.stat().st_size>0:
        checked=verify_standard(cnf,proof,"drat",
            limit=max(0.001,CAP-(time.perf_counter()-start)))
        elapsed=round(time.perf_counter()-start,6)
        return {"status":"UNSAT_VERIFIED" if checked=="ACCEPTED" and elapsed<=CAP
                else "UNKNOWN","reason":checked,"e2e_s":elapsed,
                "proof_bytes":proof.stat().st_size}
    return {"status":"UNKNOWN","reason":"NO_CHECKED_UNSAT_OR_MODEL",
            "rc":r.returncode,"e2e_s":round(time.perf_counter()-start,6)}
def main():
    ap=argparse.ArgumentParser(description="ATLAS source-only proof router")
    ap.add_argument("--cnf",type=Path,help="run on an arbitrary source DIMACS")
    ap.add_argument("--out",type=Path,default=OUT,help="parent folder for evidence")
    group=ap.add_mutually_exclusive_group()
    group.add_argument("--eo-only",action="store_true",help="run just the verified EO consumers")
    group.add_argument("--without-eo",action="store_true",help="run the original ATLAS16 routes only")
    group.add_argument("--facts-only",action="store_true",help="export independently replayable EO facts")
    args=ap.parse_args()
    binfile=(ROOT/"build/drnas-pcmax").resolve()
    if args.cnf is not None:
        args.out.mkdir(parents=True,exist_ok=True)
        folder=Path(tempfile.mkdtemp(prefix="source-",dir=args.out))
        # Freeze one immutable input for discovery and all external checks.
        source=folder/"original.cnf"
        raw=args.cnf.read_bytes()
        source.write_bytes(raw)
        if args.facts_only:
            _,_,facts=eo_decode.decode(raw)
            checked=eo_check.verify(raw,facts)
            save(folder/"eo-facts.json",facts)
            result={"status":"FACTS_VERIFIED","source_sha256":sha(raw),
                    "scan":facts["scan"],**checked}
        else:
            result=auto({"source":source,"name":args.cnf.stem},binfile,
                        folder=folder,eo_only=args.eo_only,enable_eo=not args.without_eo)
        print(json.dumps({**result,"evidence_dir":str(folder.resolve())},sort_keys=True))
        return
    if args.eo_only or args.facts_only or args.without_eo:
        ap.error("source mode requires --cnf")
    assert binfile.is_file(),"NATIVE_PC_MAX_NOT_COMPILED"
    cases=sources()
    records=[]
    for case in cases:
        assert sha(case["source"].read_bytes())==case["sha256"]
        row={"name":case["name"],"type":case["type"],"sha256":case["sha256"]}
        row["old_atlas14"]=previous_bridge(case)
        row["atlas16_auto"]=auto(case,binfile)
        # Paired references on the largest structural, PCMAX and joint demos.
        if case["name"] in ("graph-k11","pcmax-m00","joint-k6-seed66006"):
            row["Kissat4.0.4"]=reference("Kissat4.0.4",case["source"])
            row["CaDiCaL2.1.3"]=reference("CaDiCaL2.1.3",case["source"])
        if case["type"]=="constructed_SAT_control":
            assert row["atlas16_auto"]["status"] in ("UNKNOWN","SAT_VERIFIED"),"FALSE_UNSAT_ON_SAT_CONTROL"
            assert row["old_atlas14"]["status"]=="UNKNOWN","OLD_FALSE_UNSAT"
        print("ATLAS16_PILOT_TRIAL "+json.dumps(row,sort_keys=True),flush=True)
        records.append(row)
        save(OUT/"summary.json",{"status":"IN_PROGRESS","rows":records})
    summary={"status":"COMPLETE","cases":len(cases),
         "archived_originals":sum(x["type"]=="archived_original" for x in records),
         "constructed_joint":sum(x["type"]=="constructed_joint" for x in records),
         "sat_negative_checked":True,"router_verified":sum(x["atlas16_auto"]["status"]=="UNSAT_VERIFIED" for x in records),
         "old_bridge_verified":sum(x["old_atlas14"]["status"]=="UNSAT_VERIFIED" for x in records),
         "no_cdcl_in_atlas_router":True,"single_cpu_serial":CPU,"e2e_cap_s":CAP,
         "not_blind_not_world_record":True,"main_untouched":True,"rows":records}
    save(OUT/"summary.json",summary)
    print("ATLAS16_PILOT_FINAL "+json.dumps({k:v for k,v in summary.items() if k!="rows"},sort_keys=True),flush=True)
if __name__=="__main__":main()
