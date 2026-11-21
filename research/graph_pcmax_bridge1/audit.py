#!/usr/bin/env python3
"""Paired GRAPH + PCMAX/Hall source-proof bridge, repeated verifiable audit.

On synthetic fixed graph-color + independent color quota:
GRAPH alone: source graph has k vertices with k colors -> no graph-only UNSAT.
PCMAX alone: quota is satisfiable without graph resource mutual-exclusions.
Graph source exports k per-color mutex capacity facts, PCMAX reads and
independently validates source clauses, then uses quota to emit VeriPB proof.
"""
import hashlib,json,os,statistics,subprocess,sys,time,csv
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MOD=HERE/"module_bridge.py"
GRAPH_OLD=ROOT/"research/graphclique/emit_veripb.py"
HALL_OLD=ROOT/"research/match3_flow_hall.py"
OUT=Path("graph_pcmax_bridge1_results")
OUT.mkdir(exist_ok=True)
CPU=min(os.sched_getaffinity(0))
cases=[("small",4,1121),("medium",6,2451),("larger",10,3891)]
records=[]
def run(label,args,allowed=(0,),timeout=75):
    start=time.perf_counter()
    result=subprocess.run(["taskset","-c",str(CPU)]+[str(x) for x in args],
                          capture_output=True,text=True,timeout=timeout)
    sec=time.perf_counter()-start
    (OUT/(label+".log")).write_text(f"returncode={result.returncode}\nwall_s={sec:.9f}\n"+result.stdout+"\n"+result.stderr)
    if result.returncode not in allowed:
        raise RuntimeError(f"{label} rc {result.returncode} tail {result.stdout[-400:]} {result.stderr[-400:]}")
    return result,sec
for name,k,seed in cases:
    cnf=OUT/(name+".cnf")
    info=OUT/(name+".source.json")
    run(name+"-generate",[sys.executable,MOD,"generate","--k",k,"--seed",seed,
                             "--cnf",cnf,"--meta",info])
    m=json.loads(info.read_text())
    assert m["mode"]=="unsat" and m["sha256"]==hashlib.sha256(cnf.read_bytes()).hexdigest()
    base_sha=m["sha256"]
    for rep in (1,2,3):
        tag=f"{name}-rep{rep}"
        facts=OUT/(tag+".graph.json")
        prf=OUT/(tag+".pbp")
        meta=OUT/(tag+".proofmeta.json")
        graph,gt=run(tag+"-graph",[sys.executable,MOD,"graph","--cnf",cnf,"--facts",facts])
        f=json.loads(facts.read_text())
        assert f["status"]=="SOURCE_FACTS_ONLY_NO_SAT_VERDICT" and f["color_count"]==k
        # Independent original-source check, NOT trusting the graph producer's label.
        source,st=run(tag+"-premises",[sys.executable,HERE/"source_check.py",cnf,facts])
        d=json.loads(source.stdout)
        assert d["status"]=="SOURCE_GRAPH_AND_QUOTA_VERIFIED" and d["source_sha256"]==base_sha
        assert d["demand_min"]==2 and d["capacity_max"]==1
        combined,ct=run(tag+"-capacity",[sys.executable,MOD,"capacity","--cnf",cnf,
                                    "--facts",facts,"--proof",prf,"--meta",meta])
        p=json.loads(meta.read_text())
        assert p["status"]=="EMITTED_UNCHECKED_REQUIRES_VERIPB"
        checked,vt=run(tag+"-veripb",["veripb","--cnf",cnf,prf])
        assert "s VERIFIED UNSATISFIABLE" in checked.stdout
        # Same exact source; graph-only existing method and original MATCH3
        # intentionally do NOT know how to combine quota + graph semantics.
        oldp=OUT/(tag+".old-graph.pbp");oldmeta=OUT/(tag+".old-graph.json")
        oldg,_=run(tag+"-old-graph",[sys.executable,GRAPH_OLD,"--cnf",cnf,"--pbp",oldp,
                          "--meta",oldmeta],allowed=(2,))
        assert "GRAPH_CLIQUE_UNKNOWN" in oldg.stdout and not oldp.exists()
        oldhall=OUT/(tag+".old-match3.json")
        run(tag+"-old-hall",[sys.executable,HALL_OLD,cnf,"--certificate",oldhall])
        h=json.loads(oldhall.read_text())
        assert h["status"]=="UNKNOWN",h
        # OFF: no exchange -> must never claim a solution.
        offproof=OUT/(tag+".off.pbp");offmeta=OUT/(tag+".offmeta.json")
        off,_=run(tag+"-off",[sys.executable,MOD,"capacity","--cnf",cnf,
                    "--proof",offproof,"--meta",offmeta],allowed=(2,))
        assert "NO_GRAPH_FACTS_TRANSPORT_OFF" in off.stdout and not offproof.exists()
        records.append({"case":name,"k":k,"seed":seed,"rep":rep,"source_sha256":base_sha,
          "variables":m["variables"],"clauses":m["clauses"],
          "graph_source_extract_s":round(gt,6),
          "independent_source_check_s":round(st,6),
          "pcmax_proof_emit_s":round(ct,6),
          "veripb_check_s":round(vt,6),
          "total_exchange_verify_s":round(gt+st+ct+vt,6),
          "proof_bytes":prf.stat().st_size,
          "source_pairs_verified":d["edge_checks"],
          "source_quota_clauses":d["quota_clause_checks"],
          "graph_only":"UNKNOWN","pcmax_only":"UNKNOWN",
          "together":"VERIPB_VERIFIED_UNSAT"})
        print("TRIAL "+json.dumps(records[-1],sort_keys=True),flush=True)
# Tampering with source-bound math messages must be rejected even though
# source CNF itself remains unchanged.
base=OUT/"small-rep1.graph.json"
for mode in ("sha","edge"):
    x=json.loads(base.read_text())
    if mode=="sha":x["source_sha256"]="0"*64
    else:x["aligned_vertices"][0][0]=x["aligned_vertices"][0][1]
    malformed=OUT/("malformed-"+mode+".json")
    malformed.write_text(json.dumps(x))
    target=OUT/("malformed-"+mode+".pbp");meta=OUT/("malformed-"+mode+".meta.json")
    p,_=run("malformed-"+mode,[sys.executable,MOD,"capacity",
                      "--cnf",OUT/"small.cnf","--facts",malformed,
                      "--proof",target,"--meta",meta],allowed=(2,))
    assert "CAPACITY_UNKNOWN" in p.stdout and not target.exists()
# SAT controls backed by actual satisfying assignment from independent
# constructor; changing source invalidates the exact graph or quota premise.
for mode in ("no_quota","drop_quota","drop_edge"):
    cnf=OUT/("control-"+mode+".cnf")
    meta=OUT/("control-"+mode+".json")
    run("create-control-"+mode,[sys.executable,MOD,"generate","--k",6,"--seed",2026,
                       "--mode",mode,"--cnf",cnf,"--meta",meta])
    assert json.loads(meta.read_text())["sat_model_verified_by_constructor"]
    facts=OUT/("control-"+mode+".graph.json")
    run("graph-control-"+mode,[sys.executable,MOD,"graph","--cnf",cnf,"--facts",facts])
    prf=OUT/("control-"+mode+".pbp");pmeta=OUT/("control-"+mode+".proofmeta.json")
    p,_=run("capacity-control-"+mode,[sys.executable,MOD,"capacity","--cnf",cnf,
                          "--facts",facts,"--proof",prf,"--meta",pmeta],allowed=(2,))
    assert "CAPACITY_UNKNOWN" in p.stdout and not prf.exists()
# Existing original CNFs: do not claim this specialized bridge also
# recognizes the unrelated PCMAX BDD or clique>colors standalone cases.
for name,file in [("original-pcmax-bdd",ROOT/"evidence/pcmax-weighted2/05/original.cnf"),
                  ("original-graph-k11",ROOT/"evidence/graph-k11/original.cnf")]:
    f=OUT/(name+".facts.json")
    run("facts-"+name,[sys.executable,MOD,"graph","--cnf",file,"--facts",f])
    proof=OUT/(name+".pbp");meta=OUT/(name+".proofmeta.json")
    p,_=run("capacity-"+name,[sys.executable,MOD,"capacity","--cnf",file,
                               "--facts",f,"--proof",proof,"--meta",meta],allowed=(2,))
    assert "CAPACITY_UNKNOWN" in p.stdout and not proof.exists()
with (OUT/"trials.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]))
    w.writeheader();w.writerows(records)
secs=[r["total_exchange_verify_s"] for r in records]
summary={"status":"PASS","source_cases":len(cases),"reps_per_source":3,
         "total_trials":len(records),"verified_unsat":len(records),
         "graph_alone_unknown":len(records),"pcmax_alone_unknown":len(records),
         "malformed_exchange_rejections":2,"sat_controls_no_false_unsat":3,
         "unsupported_original_cnfs_unknown":2,
         "median_e2e_s":statistics.median(secs),"max_e2e_s":max(secs),
         "scope":"CONSTRUCTED graph-coloring quota family; no standard solver comparison",
         "verifier":"external VeriPB 3.0.2",
         "modules":"source GRAPH color-clique AMO facts -> PCMAX two-of-k quota",
         "novelty_note":"Existing CP/Hall mathematics, newly tested bounded modular transfer"}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("SUMMARY "+json.dumps(summary,sort_keys=True),flush=True)
