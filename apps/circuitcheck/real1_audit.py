#!/usr/bin/env python3
"""Strict 12-case public HDL corpus audit: never suppress failures or UNKNOWN."""
import argparse,hashlib,json
from pathlib import Path

ARMS=("DRNAS_DELTA1","Kissat","CaDiCaL")
CAP=30.

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--combined",type=Path,required=True)
    ap.add_argument("--shards",type=int,default=4)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    corpus=json.loads(args.manifest.read_text())
    truth={x["id"]:x for x in corpus["cases"]}
    gathered={}
    for i in range(args.shards):
        root=args.combined/f"real1-shard-{i}"
        p=root/"results/rows.json"
        if not p.is_file():p=root/"rows.json"
        if not p.is_file():
            raise RuntimeError("MISSING_SHARD "+str(i))
        data=json.loads(p.read_text())
        if data["manifest_sha256"]!=sha(args.manifest) or data["shard"]!=i:
            raise RuntimeError("SHARD_SOURCE_HASH_MISMATCH")
        for entry in data["cases"]:
            key=entry["case"]
            if key in gathered:raise RuntimeError("DUPLICATE_CASE "+key)
            gathered[key]=entry
    if set(gathered)!=set(truth):raise RuntimeError("INCOMPLETE_CORPUS")
    tally={arm:{"solved":0,"total":0,"timeout":0,"par2_seconds":0} for arm in ARMS}
    table=[
        "# DRNAS REAL1 — unmodified third-party RTL (Alex Forencich)",
        "",
        "External source pinned to exact Git commit and blob SHA. Generated harness",
        "instantiates **two native implementations** (LOOP vs REDUCTION) of the",
        "same public real LFSR/CRC IP. Fault means only a deliberate injected",
        "wrapper output flip; **upstream IP remains unchanged**.",
        "",
        "Each arm one logical CPU, 2 repeats and 30s cap. CNF export cost is",
        "reported separately and excluded from Kissat/CaDiCaL solver times.",
        "DRNAS analyzes a Yosys gate netlist, competitors analyze Yosys DIMACS;",
        "this is NOT a same-CNF SAT algorithm speedup.",
        "",
        "| Real upstream application | Inputs | Type | CNF vars | Clauses | DRNAS DELTA1 two runs | Kissat two runs | CaDiCaL two runs |",
        "|---|---:|---|---:|---:|---|---|---|"]
    for base in corpus["cases"]:
        row=gathered[base["id"]]
        if row["entry"]["sha256"]!=base["sha256"]:
            raise RuntimeError("CASE_HARNESS_TAMPERED")
        if row["upstream"]["blob_sha1"]!=next(x["blob_sha1"] for x in corpus["upstream"] if x["id"]=="alex_lfsr"):
            raise RuntimeError("UNPINNED_EXTERNAL_DUT")
        if len(row["trials"])!=6:raise RuntimeError("INCOMPLETE_ATTEMPTS "+base["id"])
        strings={}
        comparable=(row["cnf"] is not None and row["cnf_export"]["returncode"]==0)
        for arm in ARMS:
            trials=sorted([x for x in row["trials"] if x["arm"]==arm],key=lambda x:x["repeat"])
            if len(trials)!=2 or [x["repeat"] for x in trials]!=[0,1]:
                raise RuntimeError("MISSING_ARM "+base["id"]+" "+arm)
            rendered=[]
            for trial in trials:
                expect=("DIFFERENT" if base["fault"] else "EQUIVALENT") if arm=="DRNAS_DELTA1" else (
                    "SAT" if base["fault"] else "UNSAT")
                if trial["expected"]!=expect:raise RuntimeError("BAD_EXPECTATION")
                if trial["status"] in ("SAT","UNSAT","DIFFERENT","EQUIVALENT") and trial["status"]!=expect:
                    raise RuntimeError("WRONG_VERDICT")
                good=trial["status"]==expect and trial["seconds"]<=CAP
                if arm=="DRNAS_DELTA1" and good and trial["proof_replayed"] is not True:
                    raise RuntimeError("UNREPLAYED_GATE_PROOF")
                if arm!="DRNAS_DELTA1" and good and expect=="SAT" and trial.get("sat_witness_checked") is not True:
                    raise RuntimeError("UNVERIFIED_SAT_WITNESS")
                if comparable:
                    tally[arm]["total"]+=1
                    tally[arm]["solved"]+=int(good)
                    tally[arm]["timeout"]+=int(trial["status"]=="TIMEOUT")
                    tally[arm]["par2_seconds"]+=trial["seconds"] if good else CAP*2
                rendered.append(trial["status"]+" "+str(round(trial["seconds"],3))+"s")
            strings[arm]=" / ".join(rendered)
        info=row["cnf"] or {}
        table.append("| "+base["family"]+" | "+str(base["primary_input_bits"])+
            " | "+("fault" if base["fault"] else "equal")+
            " | "+str(info.get("vars","—"))+" | "+str(info.get("clauses","—"))+
            " | "+strings["DRNAS_DELTA1"]+" | "+strings["Kissat"]+
            " | "+strings["CaDiCaL"]+" |")
    table+=["","## Aggregate on successfully exported CNFs","",
            "| Arm | Confirmed/reported solved | Attempts | PAR-2 (s) | Timeouts |",
            "|---|---:|---:|---:|---:|"]
    for arm,value in tally.items():
        table.append("| "+arm+" | "+str(value["solved"])+" | "+str(value["total"])+
                     " | "+str(round(value["par2_seconds"],3))+" | "+str(value["timeout"])+" |")
    table+=["","## Real hardware classes not supported in DELTA2-C restricted source grammar",
        "",
        "| Public project | Original RTL | Observed signal | Scope |",
        "|---|---|---|---|"]
    for n in corpus["negative_controls"]:
        source=next(x for x in corpus["upstream"] if x["id"]==n["id"])
        table.append("| "+source["repo"]+" | "+source["path"]+" | "+
                    ("clocked logic" if n["clocked"] else "not classified")+
                    " | "+n["classification"]+" |")
    table+=["",
        "Limitations: exact known-good native style comparisons from one upstream",
        "module are NOT blind external reference-vs-independent-spec tests.",
        "The intentionally faulty variants are generated verification harness controls.",
        "No standard independent UNSAT certificates for baseline solvers.",
        "No FPGA LUT/place-and-route, clock timing or real-chip measurements.",
        "The real UART/SHA files are sequenced/nonlinear negative controls,",
        "not scored as solved or proof-verified by the affine checker.",""]
    result={"protocol":corpus["protocol"],"manifest_sha256":sha(args.manifest),
            "cases":gathered,"scores":tally,"third_party_upstream":corpus["upstream"],
            "negative_controls":corpus["negative_controls"]}
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    args.report.write_text("\n".join(table))
    print(args.report.read_text(),flush=True)
    print("REAL1_ALL_EXTERNAL_CASES_STRICT_AUDIT_PASS",len(gathered),flush=True)

if __name__=="__main__":
    main()
