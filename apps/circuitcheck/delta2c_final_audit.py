#!/usr/bin/env python3
"""Final DELTA2-C audit-only: reconcile original and apt-failure retry artifacts.

No solvers rerun; independently recompute every source-restricted induction,
every original-reference synthesis proof (on full arms), and cross-check
Kissat and CaDiCaL statuses, SHA-256, cap, SAT witness validation, local K
block counts and the precise original 20-case frozen manifest.

This does NOT turn solver UNSAT into an external DRAT/LRAT proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from delta2c_verify import replay as check_induction
from delta1_verify import verify as check_netlist

CASES=(("crc_64_equal","crc64equal",64,False),
       ("crc_64_fault","crc64fault",64,True),
       ("crc_2048_equal","crc2048equal",2048,False),
       ("crc_2048_fault","crc2048fault",2048,True))
GROUPS=(1,2,4,8)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True,type=Path)
    p.add_argument("--frozen",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    frozen=json.loads((args.frozen/"manifest.json").read_text())
    assert frozen["protocol"]=="CIRCUITCHECK_STRESS_FIXED_20261123"
    refs={case["id"]:case for case in frozen["cases"]}
    report={"protocol":"DRNAS_DELTA2C_FROZEN_FOUR_CASE_AUDIT",
            "original_stress_frozen_manifest_sha256":sha(args.frozen/"manifest.json"),
            "original_test_run":45286501965,
            "original_failed_job_reason":"GitHub runner Ubuntu dpkg installation interrupted before CRC2048-fault test",
            "recovery_run":45286969991,
            "tamper_test_run":45287427633,
            "source_level_scope":"narrow source grammar, two-state reflected-feedback RTL; Yosys gate netlist trusted for independent gate proofs",
            "standard_unsat_certificates":0,
            "cases":{}}
    lines=["# DRNAS DELTA2-C — 4/4 original CRC cases, independent replay",
           "",
           "Frozen original RTL: GitHub run 45245092918, all SHA-256 confirmed.",
           "Three original cases measured in run 45286501965; the fourth",
           "(CRC-2048 fault) was run unchanged in successful recovery run 45286969991",
           "after an Ubuntu package-install interruption, not a proof-engine failure.",
           "",
           "**All four cases have independent restricted-induction replay,",
           "four K-block gate-netlist checks and an additional full Yosys",
           "original-reference-vs-generated-model replay.**",
           "Only the limited source grammar is recognized; NOT arbitrary Verilog signoff.",
           "Kissat and CaDiCaL receive Yosys CNF, not DELTA2-C source/matrix representation;",
           "Kissat/CaDiCaL UNSAT is reported but not independently DRAT/LRAT-certified.",
           "",
           "| Original RTL | DIMACS vars | DELTA2-C restricted (s) | DELTA2-C full netlist (s) | Kissat original CNF r0/r1 | CaDiCaL original CNF r0/r1 |",
           "|---|---:|---:|---:|---|---|"]
    for case_id,folder,width,fault in CASES:
        original=args.frozen/(case_id+".v")
        entry=refs[case_id]
        if sha(original)!=entry["sha256"]:
            raise RuntimeError("SOURCE_SHA_NOT_FROZEN "+case_id)
        base=args.root/folder/"result"
        if not base.is_dir():
            raise RuntimeError("CASE_ARTIFACT_MISSING "+str(base))
        results={}
        for mode in ("fast","full"):
            path=base/mode
            r=json.loads((path/"delta2c_report.json").read_text())
            if r["status"]!="CHECKED_RESTRICTED_INDUCTION" or r["source_sha256"]!=entry["sha256"]:
                raise RuntimeError("FALSE_OR_STALE_INDUCTION "+case_id+" "+mode)
            if r["iterations"]!=width or r["state_bits"]!=32 or sorted(r["groups"])!=["1","2","4","8"]:
                raise RuntimeError("WRONG_INDUCTION_GROUPS "+case_id)
            expected="DIFFERENT_EXTRACTED_MODEL" if fault else "EQUIVALENT_EXTRACTED_MODEL"
            if r["candidate_verdict"]!=expected:
                raise RuntimeError("WRONG_CANDIDATE_RESULT "+case_id)
            desired="NOT_RUN" if mode=="fast" else "CHECKED_ORIGINAL_NETLIST"
            if r["full_original_yosys_audit"]!=desired:
                raise RuntimeError("WRONG_SOURCE_AUDIT_LEVEL "+case_id)
            replayed=check_induction(path,original,"reference")
            if replayed["status"]!="CHECKED_RESTRICTED_INDUCTION" or replayed["N"]!=width:
                raise RuntimeError("REPLAY_MISMATCH "+case_id)
            if mode=="full":
                checked=check_netlist(path/"base/full_original_audit")
                if checked["status"]!="CHECKED_EQUIVALENT_NETLIST":
                    raise RuntimeError("FULL_YOSYS_ORIGINAL_REPLAY_FAILED "+case_id)
            results[mode]={"seconds":r["total_elapsed_s"],
                           "status":r["status"],
                           "source_audit":desired,
                           "proof_replayed_again":True}
        baseline=json.loads((base/"baselines/baseline.json").read_text())
        if baseline["source_sha256"]!=entry["sha256"]:
            raise RuntimeError("CNF_SOURCE_SHA_MISMATCH "+case_id)
        if baseline["full"]["cnf"] is None or baseline["full"]["cnf_export"]["return_code"]!=0:
            raise RuntimeError("CNF_EXPORT_NOT_COMPLETE "+case_id)
        attempts=baseline["full"]["trials"]
        if len(attempts)!=4:
            raise RuntimeError("INCOMPLETE_SAT_ATTEMPTS "+case_id)
        byarm={}
        for arm in ("Kissat","CaDiCaL"):
            ts=sorted([t for t in attempts if t["arm"]==arm],key=lambda t:t["repeat"])
            if len(ts)!=2 or [t["repeat"] for t in ts]!=[0,1]:
                raise RuntimeError("MISSING_SAT_REPEAT "+case_id+" "+arm)
            for t in ts:
                if t["seconds"]>30.5:
                    raise RuntimeError("BAD_ORIGINAL_SOLVER_CAP "+case_id)
                if t["status"] not in ("SAT","UNSAT","TIMEOUT"):
                    raise RuntimeError("BAD_SAT_STATUS "+case_id)
                if fault:
                    if t["status"]!="SAT" or t["sat_witness_checked"] is not True:
                        raise RuntimeError("UNVERIFIED_FAULT_MODEL "+case_id)
                elif t["status"]=="SAT":
                    raise RuntimeError("FALSE_SAT_ON_EQUAL_SOURCE "+case_id)
            byarm[arm]=ts
        if set(baseline["blocks"])!=set(map(str,GROUPS)):
            raise RuntimeError("MISSING_BLOCK_BENCHMARK "+case_id)
        blocks={}
        for k in GROUPS:
            group=baseline["blocks"][str(k)]
            if group["cnf"] is None or group["size"]!=k or len(group["trials"])!=2:
                raise RuntimeError("INCOMPLETE_LOCAL_K_BLOCK "+case_id+" "+str(k))
            statuses={x["arm"]:x["status"] for x in group["trials"]}
            if statuses!={"Kissat":"UNSAT","CaDiCaL":"UNSAT"}:
                raise RuntimeError("LOCAL_SAT_BASELINE_WRONG "+case_id+" "+str(k))
            blocks[str(k)]={t["arm"]:{"status":t["status"],"seconds":t["seconds"]}
                            for t in group["trials"]}
        report["cases"][case_id]={
            "source_sha256":entry["sha256"],
            "original_cnf":baseline["full"]["cnf"],
            "DELTA2C":results,
            "Kissat":byarm["Kissat"],
            "CaDiCaL":byarm["CaDiCaL"],
            "local_step_baselines":blocks,
            "induction_and_full_replay_checked":True,
            "single_cpu":baseline["single_cpu"]
        }
        render=lambda v: " / ".join(t["status"]+" "+str(round(t["seconds"],3))+"s" for t in v)
        lines.append("| "+case_id+" | "+str(baseline["full"]["cnf"]["vars"])+
                     " | "+str(round(results["fast"]["seconds"],3))+
                     " | "+str(round(results["full"]["seconds"],3))+
                     " | "+render(byarm["Kissat"])+
                     " | "+render(byarm["CaDiCaL"])+" |")
        print("DELTA2C_FINAL_CASE_REPLAY_PASS",case_id,
              "fast_s",results["fast"]["seconds"],
              "full_s",results["full"]["seconds"],flush=True)
    if len(report["cases"])!=4:
        raise RuntimeError("FINAL_CASE_MISSING")
    lines+=["",
            "## Local 1-, 2-, 4-, 8-step comparisons",
            "",
            "Each K has a separate DELTA1/Yosys equivalence certificate with",
            "independent replay for arbitrary initial register and K input bits.",
            "Both Kissat and CaDiCaL reported UNSAT on the corresponding",
            "local miter CNF within 10s; these SAT solver UNSAT statuses",
            "have no separate DRAT/LRAT verification in this study.",
            "",
            "## Interpretation",
            "",
            "The restricted one-step source-grammar induction can avoid the full",
            "N-step RTL expansion cost. The additional full original-Yosys gate",
            "audit remains significantly more expensive. On deliberately faulty",
            "SAT controls, Kissat and CaDiCaL can find witnesses much faster.",
            "No same-CNF speedup or polynomial-time arbitrary SAT claim.",
            ""]
    args.report.write_text("\n".join(lines))
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print("DELTA2C_FINAL_ALL_FOUR_CASES_AND_SAT_BOTH_ARMS_AUDITED",flush=True)

if __name__=="__main__":
    main()
