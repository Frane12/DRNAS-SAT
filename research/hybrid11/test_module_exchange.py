#!/usr/bin/env python3
"""Prospective deterministic bridge fact-transfer audit; same source per ON/direct/OFF.
No solver-speed superiority claim. Independent VeriPB is the authority for UNSAT.
"""
import csv,hashlib,json,os,subprocess,sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
GEN=ROOT/"research/hybrid11/generate_indirect.py"
PROD=ROOT/"research/hybrid11/signed_2sat_exchange.py"
EMIT=ROOT/"research/hybrid11/emit_veripb_indirect.py"
WORK=ROOT/"hybrid11_bridge_test_output"
WORK.mkdir(exist_ok=True,parents=True)
CPU=min(os.sched_getaffinity(0))

def call(name,args,timeout=100,ok=(0,)):
    start=time.perf_counter()
    p=subprocess.run(["taskset","-c",str(CPU)]+[str(x) for x in args],
                     text=True,capture_output=True,timeout=timeout)
    sec=time.perf_counter()-start
    (WORK/(name+".log")).write_text(f"returncode={p.returncode}\nwall_s={sec}\nSTDOUT\n{p.stdout}\nSTDERR\n{p.stderr}")
    if p.returncode not in ok:raise RuntimeError(f"{name}: rc={p.returncode} {p.stdout[-500:]} {p.stderr[-500:]}")
    return p,sec

cases=[("split8",8,303,"split",False),("mixed12",12,505,"mixed",False),
       ("permuted16",16,99,"mixed",True)]
records=[]
for name,n,seed,structure,perm in cases:
    cnf=WORK/f"{name}.cnf"
    gen=[sys.executable,GEN,"--n",n,"--seed",seed,"--structure",structure,
         "--noise","--output",cnf]
    if perm:gen.append("--permute")
    call(name+"-generate",gen)
    source_sha=hashlib.sha256(cnf.read_bytes()).hexdigest()
    for rep in (1,2,3):
        tag=f"{name}-rep{rep}"
        exchange=WORK/(tag+".exchange.json")
        pb=WORK/(tag+".bridge.pbp")
        meta=WORK/(tag+".bridge.meta.json")
        _,producer_s=call(tag+"-producer",[sys.executable,PROD,"--cnf",cnf,"--output",exchange])
        claims=json.loads(exchange.read_text())
        assert claims["verdict"]=="FACTS_ONLY_UNCHECKED",claims
        assert claims["source_sha256"]==source_sha
        assert len(claims["links"])==n
        _,bridge_emitter_s=call(tag+"-bridge-emit",[sys.executable,EMIT,
                            "--cnf",cnf,"--output",pb,"--meta",meta,
                            "--exchange",exchange,"--require-exchange"])
        m=json.loads(meta.read_text())
        assert m["source_verified_exchange_used"] and m["received_links"]==n
        assert m["source_sha256"]==source_sha
        _,bridge_check_s=call(tag+"-bridge-veripb",["veripb","--cnf",cnf,pb],timeout=130)
        verdict=(WORK/(tag+"-bridge-veripb.log")).read_text()
        assert "s VERIFIED UNSATISFIABLE" in verdict
        direct=WORK/(tag+".direct.pbp")
        dmeta=WORK/(tag+".direct.meta.json")
        _,direct_emit_s=call(tag+"-direct-emit",[sys.executable,EMIT,
                              "--cnf",cnf,"--output",direct,"--meta",dmeta])
        _,direct_check_s=call(tag+"-direct-veripb",["veripb","--cnf",cnf,direct],timeout=130)
        assert "s VERIFIED UNSATISFIABLE" in (WORK/(tag+"-direct-veripb.log")).read_text()
        assert not json.loads(dmeta.read_text())["source_verified_exchange_used"]
        off=WORK/(tag+".off.pbp")
        p,_=call(tag+"-off",[sys.executable,EMIT,"--cnf",cnf,
                         "--output",off,"--require-exchange"],ok=(2,))
        assert "bridge OFF" in p.stdout and not off.exists()
        records.append({"case":name,"n":n,"seed":seed,"repetition":rep,
            "source_sha256":source_sha,"links":len(claims["links"]),
            "signed_neg_links":sum(x["xor_bit"] for x in claims["links"]),
            "bridge_producer_s":round(producer_s,6),
            "bridge_emitter_s":round(bridge_emitter_s,6),
            "bridge_veripb_s":round(bridge_check_s,6),
            "bridge_total_e2e_s":round(producer_s+bridge_emitter_s+bridge_check_s,6),
            "direct_emitter_s":round(direct_emit_s,6),
            "direct_veripb_s":round(direct_check_s,6),
            "direct_total_e2e_s":round(direct_emit_s+direct_check_s,6),
            "bridge_proof_bytes":pb.stat().st_size,
            "direct_proof_bytes":direct.stat().st_size,
            "proof_identical":hashlib.sha256(pb.read_bytes()).hexdigest()==hashlib.sha256(direct.read_bytes()).hexdigest(),
            "off":"UNKNOWN_NO_EXCHANGE",
            "bridge":"VERIPB_VERIFIED_UNSAT",
            "direct":"VERIPB_VERIFIED_UNSAT"})
        print("TRIAL "+json.dumps(records[-1],sort_keys=True),flush=True)

# Reject a forged source hash and a fabricated implication path.
cnf=WORK/"split8.cnf"
good=json.loads((WORK/"split8-rep1.exchange.json").read_text())
for badtype in ("hash","path"):
    bad=json.loads(json.dumps(good))
    if badtype=="hash":
        bad["source_sha256"]="f"*64
    else:
        a=bad["links"][0]
        a["path_xy"]=[a["x"],-(a["y"] if a["xor_bit"]==0 else -a["y"])]
    f=WORK/f"forged-{badtype}.json";f.write_text(json.dumps(bad))
    pb=WORK/f"forged-{badtype}.pbp"
    p,_=call("forged-"+badtype,[sys.executable,EMIT,"--cnf",cnf,"--exchange",f,
                              "--require-exchange","--output",pb],ok=(2,))
    assert "HYBRID11_UNKNOWN" in p.stdout and not pb.exists()

# Controls: SAT with independently constructed witness, and destroyed source link.
for mode in ("sat","broken_link","missing_amo","missing_gate"):
    cnf=WORK/f"control-{mode}.cnf"
    p,_=call("control-gen-"+mode,[sys.executable,GEN,"--n",12,"--seed",101,
                         "--structure","split","--mode",mode,"--output",cnf])
    if mode=="sat":
        assert '"sat_model_verified": true' in p.stdout
    ex=WORK/f"control-{mode}.exchange.json"
    call("control-2sat-"+mode,[sys.executable,PROD,"--cnf",cnf,"--output",ex])
    out=WORK/f"control-{mode}.pbp"
    p,_=call("control-bridge-"+mode,[sys.executable,EMIT,"--cnf",cnf,
                      "--exchange",ex,"--require-exchange","--output",out],ok=(2,))
    assert "HYBRID11_UNKNOWN" in p.stdout and not out.exists()

with (WORK/"paired_trials.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
summary={"status":"PASS","tested_cases":len(cases),"repetitions_each":3,"trials":len(records),
         "bridge_veripb_verified":sum(x["bridge"]=="VERIPB_VERIFIED_UNSAT" for x in records),
         "direct_veripb_verified":sum(x["direct"]=="VERIPB_VERIFIED_UNSAT" for x in records),
         "off_unknown":sum(x["off"]=="UNKNOWN_NO_EXCHANGE" for x in records),
         "proof_identical_count":sum(x["proof_identical"] for x in records),
         "controls_safe_unknown":4,"forged_messages_rejected":2,
         "bridge_median_e2e_s":statistics.median(x["bridge_total_e2e_s"] for x in records),
         "direct_median_e2e_s":statistics.median(x["direct_total_e2e_s"] for x in records),
         "scope":"CONSTRUCTED signed 2-SAT/XOR3-XOR4/ALO instances, not real unseen CNFs",
         "off_interpretation":"Modular transport switched OFF; direct monolithic reference still proves UNSAT",
         "proof_checker":"independent VeriPB 3.0.2"}
(WORK/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("SUMMARY "+json.dumps(summary,sort_keys=True),flush=True)
