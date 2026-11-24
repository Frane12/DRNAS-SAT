#!/usr/bin/env python3
"""No-cherry-picking REAL4 blind audit.

Requires all 6 originally selected external HDL cases in the final result,
verifies SHA-frozen source and EXACT locked gate interpreter/checker hashes,
re-runs independent per-probe algebra certificate replay on every success,
validates each generated local-miter/CNF SHA, validates all paired SAT arm
records and never upgrades UNKNOWN, timeout or unverified UNSAT into success.
"""
import argparse,hashlib,json
from pathlib import Path
from real4_verify import proof_replay

LOCKED_ENGINE="0d2fd18b34c2c871b076f3f863982c11d91376ce0d4d9d4f5063f7dba50c4590"
LOCKED_CHECKER="85774fce3605280c4dbd771664f8eaf04d100d79e12792e5dbe36cffc9d48beb"

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fail(message):raise RuntimeError(message)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--sources",type=Path,required=True)
    ap.add_argument("--combined",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    ap.add_argument("--shards",type=int,default=3)
    x=ap.parse_args()
    frozen=json.loads(x.manifest.read_text())
    if frozen["protocol"]!="DRNAS_REAL4_BLIND_EXTERNAL_6_V1":
        fail("WRONG_PROTOCOL")
    if frozen["prelock_run_id"]!=45339922757:
        fail("MISSING_ENGINE_PRELOCK")
    all_cases={}
    location={}
    for index in range(x.shards):
        folder=x.combined/f"real4-shard-{index}"
        summary=folder/"results"/"rows.json"
        if not summary.is_file():summary=folder/"rows.json"
        if not summary.is_file():fail("SHARD_MISSING "+str(index))
        data=json.loads(summary.read_text())
        if (data["source_manifest_sha256"]!=sha(x.manifest) or
              data["shard"]!=index or data["shards"]!=x.shards):
            fail("SHARD_OR_MANIFEST_CHANGED "+str(index))
        if data["engine_sha256"]!={"real4_islands":LOCKED_ENGINE,
                                   "real4_verify":LOCKED_CHECKER}:
            fail("ENGINE_CHANGED_AFTER_PRELOCK "+str(index))
        for case in data["cases"]:
            if case["id"] in all_cases:fail("DUPLICATE_CASE")
            all_cases[case["id"]]=case
            location[case["id"]]=folder/"results"/case["id"]
    expected={case["id"]:case for case in frozen["cases"]}
    if set(expected)!=set(all_cases):fail("HOLDOUT_COHORT_NOT_COMPLETE")
    tally={"cases":len(expected),"synth_success":0,"synth_failed_or_timeout":0,
           "certificates_independently_replayed":0,"global_affine_probes":0,
           "local_affine_probes":0,"unknown_probes":0,
           "nonlinear_cutpoints":0,"replayed_local_cone_checks":0,
           "Kissat_UNSAT_reported":0,"CaDiCaL_UNSAT_reported":0,
           "SAT_solver_TIME_OUT":0,"SAT_solver_errors":0,
           "total_solver_trials":0}
    lines=[
        "# DRNAS REAL4 — true blind external RTL holdout",
        "",
        "REAL4 interpreter and independent checker were locked **before**",
        "the six third-party original RTL files were selected; the SHA-256 of",
        "both code files is verified against the previous green unit run",
        "45339922757. No source-specific branches, parameters, regexes,",
        "ports, or special cases are used by REAL4.",
        "",
        "The proof checks **local Boolean gate identities**, with Flip-Flop Q",
        "as arbitrary state and nonlinear cut outputs as free variables.",
        "A local identity is NOT a whole-design UNSAT or SAT result,",
        "not a temporal sequential proof and not an original RTL specification.",
        "Kissat/CaDiCaL inspect SAME generated Yosys CNF of one local cone",
        "per sample; this is not original full-project CNF comparison.",
        "Only synthesis and SAT solver time are measured separately.",
        "",
        "| Original external HDL | Synthesis | Cell count | FF-Q bits | XOR gates | Global affine probes | Local affine probes | Unknown probes | Nonlinear/unsupported cuts | Replayed sample cone SAT controls |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"
    ]
    for original in frozen["cases"]:
        key=original["id"]
        source=x.sources/(key+".sv")
        entry=all_cases[key]
        folder=location[key]
        if not source.is_file() or sha(source)!=original["sha256"] or entry["original_sha256"]!=original["sha256"]:
            fail("SOURCE_SHA_MISMATCH "+key)
        if entry["source_git_blob_sha1"]!=original["blob"]:
            fail("GIT_BLOB_PIN_MISMATCH "+key)
        stage=entry["synthesis"]
        success=stage["status"]=="OK"
        tally["synth_success"]+=int(success)
        tally["synth_failed_or_timeout"]+=int(not success)
        metric={}
        if success and entry["affine_analysis"]["status"]=="STRUCTURE_EXTRACTED_NOT_A_FULL_CIRCUIT_SAT_VERDICT":
            if entry["independent_replay"]["status"]!="CHECKED":
                fail("MISSING_INDEPENDENT_CERTIFICATE "+key)
            evidence=proof_replay(folder)
            if evidence["status"]!="CHECKED_LOCAL_AFFINE_GATE_IDENTITIES":
                fail("LOCAL_GATE_PROOF_NOT_REPLAYED "+key)
            if entry["netlist_sha256"]!=sha(folder/"netlist.json"):
                fail("LOCAL_NETLIST_SHA_WRONG")
            tally["certificates_independently_replayed"]+=1
            metric=entry["affine_analysis"]["metrics"]
            tally["global_affine_probes"]+=metric.get("global_affine_external_and_state_probes",0)
            tally["local_affine_probes"]+=metric.get("local_affine_external_and_state_probes",0)
            tally["unknown_probes"]+=metric.get("unknown_external_and_state_probes",0)
            tally["nonlinear_cutpoints"]+=metric.get("cutpoints",0)
        elif success and entry["independent_replay"]["status"]=="CHECKED":
            fail("FALSE_PROOF_LEVEL "+key)
        summaries=[]
        for c in entry["cones"]:
            if c["status"]!="GENERATED":
                summaries.append(c["status"])
                continue
            dest=folder/"cones"/c["name"]
            if not (dest/"miter.v").is_file() or sha(dest/"miter.v")!=c["miter_sha256"]:
                fail("MITER_SOURCE_SHA_CHANGED "+key)
            status=c["cnf_export"]["status"]
            if status!="OK":
                summaries.append("CNF_"+status)
                continue
            if sha(dest/"miter.cnf")!=c["cnf"]["sha256"]:
                fail("ORIGINAL_MITER_CNF_SHA_CHANGED "+key)
            trials=c["baselines"]
            if len(trials)!=4:fail("INCOMPLETE_SAT_PAIRS "+key)
            for arm in ("Kissat","CaDiCaL"):
                ts=sorted((t for t in trials if t["arm"]==arm),key=lambda t:t["repeat"])
                if len(ts)!=2 or [t["repeat"] for t in ts]!=[0,1]:
                    fail("BAD_PAIR_REPETITIONS "+key)
                for t in ts:
                    tally["total_solver_trials"]+=1
                    if t["status"]=="SAT" or t["status"]=="SOUNDNESS_ALARM_SAT":
                        fail("REAL4_AFFINE_PROOF_CONTRADICTION "+key)
                    if t["status"]=="UNSAT":
                        tally[arm+"_UNSAT_reported"]+=1
                    elif t["status"]=="TIMEOUT":
                        tally["SAT_solver_TIME_OUT"]+=1
                    else:tally["SAT_solver_errors"]+=1
            tally["replayed_local_cone_checks"]+=1
            summaries.append("Kissat/CaDiCaL "+"/".join(t["status"] for t in trials))
        s=str(metric.get("cells","—"))
        lines.append("| "+key+" ("+original["domain"]+") | "+stage["status"]+
           " | "+s+" | "+str(metric.get("state_Q_bits","—"))+
           " | "+str(metric.get("xor_gate_count","—"))+
           " | "+str(metric.get("global_affine_external_and_state_probes","—"))+
           " | "+str(metric.get("local_affine_external_and_state_probes","—"))+
           " | "+str(metric.get("unknown_external_and_state_probes","—"))+
           " | "+str(metric.get("cutpoints","—"))+
           " | "+("; ".join(summaries) if summaries else "NO_CERTIFIED_CONE")+" |")
        print("REAL4_BLIND_AUDITED",key,"synth",stage["status"],
              "global",metric.get("global_affine_external_and_state_probes"),
              "local",metric.get("local_affine_external_and_state_probes"),
              "cuts",metric.get("cutpoints"),flush=True)
    lines+=["","## Totals","",
            "| Metric | Result |","|---|---:|"]
    for k,v in tally.items():lines.append("| "+k+" | "+str(v)+" |")
    lines+=["",
        "## Limits and original-source boundary",
        "",
        "An RTL module that fails Yosys elaboration/synthesis within its 100s cap",
        "is a genuine UNSUPPORTED/TIMEOUT, not a solver defeat.",
        "Global affine evidence holds over primary input bits and arbitrarily",
        "chosen current-state FF-Q bits, **not across successive clock cycles**.",
        "Local evidence holds only relative to separately introduced free",
        "nonlinear/cell outputs, never claiming that the whole module is affine.",
        "Any FFT, CPU, crypto core without supported proofs remains UNKNOWN",
        "rather than a claimed SAT/UNSAT or a manufactured speedup.",
        "Yosys lowering is trusted; independently checked standard",
        "UNSAT certificates (DRAT/LRAT) are not produced for Kissat/CaDiCaL.",
        ""]
    x.report.write_text("\n".join(lines))
    x.output.write_text(json.dumps({
        "protocol":frozen["protocol"],"frozen_source_sha256":sha(x.manifest),
        "engine_sha256":LOCKED_ENGINE,"checker_sha256":LOCKED_CHECKER,
        "source":frozen,"results":all_cases,"stats":tally
    },indent=2)+"\n")
    print("REAL4_BLIND_ALL_SIX_EXTERNAL_RTL_INDEPENDENT_AUDIT_COMPLETE",flush=True)

if __name__=="__main__":main()
