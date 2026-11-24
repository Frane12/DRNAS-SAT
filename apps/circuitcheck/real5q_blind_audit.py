#!/usr/bin/env python3
"""REAL5Q five-project prospective source holdout audit.

Require all five original exact SHA source files and all three shard records
with the prelocked algorithm unchanged. Independent proof checker REPLAYS
all successful Yosys gate-level quadratic certificates. For each local
polynomial gate-cone control, check exact miter/CNF SHA and two Kissat/two
CaDiCaL statuses, preserving any timeout, UNKNOWN or failed synthesis.
This does NOT claim full-module SAT/UNSAT or certified DRAT/LRAT.
"""
import argparse,hashlib,json
from pathlib import Path
from real5q_verify import check

CORE="fc0ed0b1a57bd5b0df75ba3f307faccef7a763edb39408e20e278cd09d40d35a"
CHECKER="a7203de8c48148dc24a9bb37f593e1b924b5e3d24c8cdf767e6bbd91c117738b"

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def fail(m):raise RuntimeError(m)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen",type=Path,required=True)
    p.add_argument("--combined",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    corpus=json.loads((a.frozen/"manifest.json").read_text())
    ids=[x["id"] for x in corpus["cases"]]
    if len(ids)!=5 or len(set(ids))!=5:fail("COHORT_NOT_FIVE")
    all_rows={}
    folders={}
    for shard in (0,1,2):
        folder=a.combined/f"real5q-shard-{shard}"/"results"
        if not (folder/"rows.json").is_file():fail("NO_SHARD "+str(shard))
        manifest=json.loads((folder/"rows.json").read_text())
        if (manifest["source_manifest_sha256"]!=sha(a.frozen/"manifest.json")
            or manifest["prelocked_anf_sha256"]!=CORE or
            manifest["prelocked_verifier_sha256"]!=CHECKER or
            manifest["shard"]!=shard):
            fail("TAMPERED_MATH_PRELOCK_OR_COHORT")
        for case in manifest["cases"]:
            if case["id"] in all_rows:fail("DUPLICATE_SOURCE "+case["id"])
            all_rows[case["id"]]=case
            folders[case["id"]]=folder
    if set(all_rows)!=set(ids):fail("MISSING_UNSEEN_SOURCE")
    stats={"selected_new_modules":5,"synthesized":0,"source_frontend_unsupported":0,
           "synthesis_timeouts":0,"polynomial_gate_certificates_verified":0,
           "global_degree2_external_probes":0,
           "sampled_internal_global_degree2":0,
           "local_bounded_polynomial_external_probes":0,
           "remaining_UNKNOWN_external_probes":0,
           "sampled_local_cones":0,
           "independent_yosys_local_cones_verified":0,
           "Kissat_UNSAT_reported":0,
           "CaDiCaL_UNSAT_reported":0,
           "solver_trial_unknown_or_timeout":0}
    output={
        "protocol":corpus["protocol"],
        "frozen_manifest_sha256":sha(a.frozen/"manifest.json"),
        "lock_run":45344568141,
        "math_engine_sha256":CORE,"independent_checker_sha256":CHECKER,
        "cases":all_rows,"stats":stats}
    lines=["# DRNAS REAL5-Q — prospective original third-party RTL holdout",
           "",
           "The exact degree2 polynomial algorithm and independent checker were",
           "SHA-locked (green test 45344568141) **before** these five source",
           "modules were selected. No RTL source files were edited or skipped.",
           "Unrecognized synthesis, unsupported HDL or missing blocks are",
           "reported explicitly, never counted as SAT/UNSAT defeats.",
           "",
           "| Original source | Yosys full-source gate netlist | Global quadratic external probes | Sampled quadratic internal | Local polynomial external | Unknown external | Actual gate-cone SAT controls |",
           "|---|---|---:|---:|---:|---:|---|"]
    for entry in corpus["cases"]:
        name=entry["id"]
        where=folders[name]
        case=all_rows[name]
        raw=a.frozen/entry["source_filename"]
        if not raw.is_file() or sha(raw)!=entry["sha256"] or case["original_sha256"]!=entry["sha256"]:
            fail("ORIGINAL_UNMODIFIED_RTL_SHA_MISMATCH "+name)
        stage=case["synthesis"]["status"]
        stats["synthesized"]+=int(stage=="OK")
        stats["source_frontend_unsupported"]+=int(stage=="FRONTEND_UNSUPPORTED")
        stats["synthesis_timeouts"]+=int(stage=="TIMEOUT")
        m=case["polynomial"].get("metrics",{})
        success=case["verification"]["status"]=="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS"
        if success:
            folder=where/"cases"/name
            if not (folder/"netlist.json").is_file():fail("ORIGINAL_NETLIST_MISSING")
            if sha(folder/"netlist.json")!=case["netlist_sha256"]:
                fail("NETLIST_IN_SHA_MANIFEST_CHANGED")
            replay=check(folder)
            if replay["status"]!="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS":
                fail("POLYNOMIAL_CERT_INDEPENDENT_REPLAY_FAILED")
            stats["polynomial_gate_certificates_verified"]+=1
            stats["global_degree2_external_probes"]+=m.get("global_degree2_probes",0)
            stats["sampled_internal_global_degree2"]+=m.get("sampled_internal_global_degree2",0)
            stats["local_bounded_polynomial_external_probes"]+=m.get("local_polynomial_probes",0)
            stats["remaining_UNKNOWN_external_probes"]+=m.get("unknown_probes",0)
        satfile=where/"quadratic_sat"/"results.json"
        check_summary="NO_VERIFIED_CONES_OR_SOURCE"
        if success and not satfile.is_file():
            fail("MISSING_MANDATORY_SAT_CONTROL_RECORD "+name)
        if success and satfile.is_file():
            sat=json.loads(satfile.read_text())
            if name not in sat["cases"]:fail("CASE_NOT_IN_SAT_ARTIFACT")
            satcase=sat["cases"][name]
            selected=satcase["selected_cones"]
            stats["sampled_local_cones"]+=len(selected)
            for candidate in selected:
                if candidate["status"]!="GENERATED":continue
                actual=where/"quadratic_sat"/name/"candidate_cones"/candidate["id"]
                if sha(actual/"miter.v")!=candidate["miter_sha256"]:
                    fail("REAL_QUADRATIC_CONE_MITER_SHA_CHANGED")
                if candidate.get("cnf_status")=="EXPORTED":
                    if sha(actual/"identity.cnf")!=candidate["cnf"]["sha256"]:
                        fail("EXACT_SAME_SAT_CNF_SHA_CHANGED")
                    if candidate.get("yosys_formal",{}).get("status")=="VERIFIED_LOCAL_EQUAL":
                        stats["independent_yosys_local_cones_verified"]+=1
            trials=satcase["trials"]
            for candidate in selected:
                if candidate.get("cnf_status")!="EXPORTED":continue
                for arm in ("Kissat","CaDiCaL"):
                    ts=[t for t in trials if t["cone"]==candidate["id"] and t["arm"]==arm]
                    if len(ts)!=2 or sorted(t["repeat"] for t in ts)!=[0,1]:
                        fail("MISSING_PINNED_SAT_SOLVER_RUNS")
                    for t in ts:
                        if t["status"]=="SAT":fail("FALSE_LOCAL_GF2_POLYNOMIAL")
                        if t["status"]=="UNSAT":stats[arm+"_UNSAT_reported"]+=1
                        else:stats["solver_trial_unknown_or_timeout"]+=1
            check_summary="local_cones_"+str(len(selected))
        lines.append("| "+name+" | "+stage+
            " | "+str(m.get("global_degree2_probes","—"))+
            " | "+str(m.get("sampled_internal_global_degree2","—"))+
            " | "+str(m.get("local_polynomial_probes","—"))+
            " | "+str(m.get("unknown_probes","—"))+
            " | "+check_summary+" |")
        print("REAL5Q_PROSPECTIVE_AUDIT_CASE",name,"synthesis",stage,
              "quadratic",m.get("global_degree2_probes",0),flush=True)
    lines+=["","## Reproducible totals","",
            "| Metric | Count |","|---|---:|"]
    for k,v in stats.items():lines.append("| "+k+" | "+str(v)+" |")
    lines+=["",
            "Original source HDL was translated with the Yosys version used",
            "by this CI runner. All global quadratic claims are exact only",
            "for a single 2-state gate-level function of primary input and",
            "current FF-Q bits. Local polynomials treat nonlinear cutpoints as",
            "unconstrained separate Boolean signals. No temporal claims.",
            "Kissat and CaDiCaL inspect only the selected local gate-cone",
            "miter CNF; those are NOT full-core SAT benchmark formulas.",
            "Reported solver UNSAT verdicts are not independently DRAT/LRAT certified."]
    a.out.write_text(json.dumps(output,indent=2)+"\n")
    a.report.write_text("\n".join(lines)+"\n")
    print("REAL5Q_PROSPECTIVE_FIVE_NEW_SOURCE_AUDIT_COMPLETED",flush=True)

if __name__=="__main__":main()
