#!/usr/bin/env python3
"""Strict prospective five-source REAL6 gate math and SAT control audit.

All five original pinned sources must appear, including all unsupported
frontend or no-motif results. Reopen the original gate netlist and re-run
both independent REAL5Q and REAL6 truth table checkers. Check immutable
engine SHA, exact same micro-cone CNF SHA, paired Kissat+CaDiCaL calls
and keep absence of DRAT/LRAT proof explicit.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from real6_verify import verify as verify_motifs
from real5q_verify import check as verify_base

ENGINE_SHA={
  "real5q_anf.py":"fc0ed0b1a57bd5b0df75ba3f307faccef7a763edb39408e20e278cd09d40d35a",
  "real5q_verify.py":"a7203de8c48148dc24a9bb37f593e1b924b5e3d24c8cdf767e6bbd91c117738b",
  "real6_motifs.py":"f27a4a3f2efc73d0c8aa35fcca8092acf5d973a8b46004de2c1d90706ebb4365",
  "real6_verify.py":"28d660b8486f8590ea3fa2091a18e6df9cec7cd95c76b59d8315ecf5956ab803"
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fail(message):raise RuntimeError(message)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen",type=Path,required=True)
    p.add_argument("--combined",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    frozen=json.loads((args.frozen/"manifest.json").read_text())
    if frozen.get("protocol")!="DRNAS_REAL6_PROSPECTIVE_FIVE_UNKNOWN_ORIGINAL_RTL" or (
       frozen.get("engine_prelock_run")!=45347547028):
        fail("WRONG_FROZEN_HOLDOUT")
    expected={c["id"]:c for c in frozen["cases"]}
    if len(expected)!=5:fail("NOT_FIVE_SOURCE_CORPUS")
    found={}
    folders={}
    for i in (0,1,2):
        folder=args.combined/f"real6-shard-{i}"/"results"
        filename=folder/"rows.json"
        if not filename.is_file():fail("MISSING_SHARD "+str(i))
        record=json.loads(filename.read_text())
        if (record["shard"]!=i or record["shards"]!=3 or
             record["manifest_sha256"]!=sha(args.frozen/"manifest.json") or
             record["mathematical_engine_sha256"]!=ENGINE_SHA):
            fail("MATHEMATICAL_PRELOCK_OR_MANIFEST_CHANGED")
        for c in record["cases"]:
            if c["id"] in found:fail("DUPLICATE_SOURCE")
            found[c["id"]]=c
            folders[c["id"]]=folder/c["id"]
    if set(found)!=set(expected):fail("EXCLUDED_UNKNOWN_SOURCE")
    counts={"sources":5,"synthesized":0,"unsupported_frontend_or_dependencies":0,
       "synthesis_timeouts":0,"verified_ANF_gate_certificates":0,
       "independently_replayed_REAL6_certificates":0,
       "global_CHOICES":0,"cut_conditional_CHOICES":0,
       "global_MAJORITY":0,"cut_conditional_MAJORITY":0,
       "global_SUM3":0,"cut_conditional_SUM3":0,
       "one_bit_FULL_ADDER_pairs":0,
       "same_gate_CNF_cones":0,"yosys_formal_gate_cones_proved":0,
       "Kissat_UNSAT_reported":0,"CaDiCaL_UNSAT_reported":0,
       "SAT_attempts_unfinished_or_unknown":0}
    lines=["# DRNAS REAL6 — new five-source prospective original HDL holdout",
           "",
           "Mathematical detector and independent REAL6 checker were SHA locked",
           "in successful run 45347547028 **before these five original RTL",
           "files were selected**. Exact Git blob / SHA256 sources remain",
           "unaltered. No failed frontend or missing-module result is dropped.",
           "",
           "REAL6 labels CH, MAJ, three-variable XOR sums and 1-bit",
           "SUM+MAJ full adders by exhaustive 3-variable truth tables",
           "over already independently proved GF2 degree<=2 gate ANFs.",
           "A pattern involving nonlinear free cut variables is LOCAL and",
           "not a claim about whole-circuit global quadratic complexity.",
           "",
           "| New original RTL | Yosys synthesis | Verified CH | MAJ | SUM3 | Full-adder pairs | Global motifs | Conditional-cut motifs | Local SAT cones |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for target in frozen["cases"]:
        name=target["id"]
        c=found[name]
        path=folders[name]
        original=args.frozen/target["filename"]
        if not original.is_file() or sha(original)!=target["sha256"] or (
             c.get("source_sha256")!=target["sha256"] or c.get("original_blob")!=target["blob"]):
            fail("FROZEN_ORIGINAL_SOURCE_CHANGED "+name)
        status=c["synthesis"]["status"]
        counts["synthesized"]+=int(status=="OK")
        counts["unsupported_frontend_or_dependencies"]+=int(status=="FRONTEND_OR_DEPENDENCY_UNSUPPORTED")
        counts["synthesis_timeouts"]+=int(status=="TIMEOUT")
        numerical={}
        if status=="OK":
            gate=path/"netlist.json"
            if not gate.is_file() or sha(gate)!=c["netlist_sha256"]:
                fail("ORIGINAL_YOSYS_GATE_CHANGED "+name)
            qstatus=c["gf2_anf"]["status"]
            if qstatus=="CHECKED":
                if verify_base(path)["status"]!="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS":
                    fail("ORIGINAL_ANF_PROOF_REPLAY_FAILED "+name)
                counts["verified_ANF_gate_certificates"]+=1
                report_file=path/"real6_certificate.json"
                if not report_file.is_file():fail("MISSING_REAL6_CERT")
                confirmed=verify_motifs(path,report_file)
                if confirmed["status"]!="CHECKED_REAL6_MOTIF_TRUTH_TABLES" or (
                     c["real6_independent_replay"]["status"]!=confirmed["status"]):
                    fail("REAL6_MOTIF_NOT_INDEPENDENTLY_REPLAYED "+name)
                counts["independently_replayed_REAL6_certificates"]+=1
                report=json.loads(report_file.read_text())
                if c["real6_motifs"]["certificate_sha256"]!=sha(report_file):
                    fail("REAL6_MOTIF_SHA_CHANGED")
                numerical=report["counts"]
                for kind,prefix in (("chs","CHOICES"),("majs","MAJORITY"),("three_input_xor_sums","SUM3")):
                    for motif in report["motifs"]:
                        if motif["motif"]=={"chs":"CH","majs":"MAJ","three_input_xor_sums":"SUM3"}[kind]:
                            key=("cut_conditional_" if motif["scope"]!="GLOBAL_ONE_STEP" else "global_")+prefix
                            counts[key]+=1
                counts["one_bit_FULL_ADDER_pairs"]+=report["counts"]["paired_full_adders_before_limit"]
            elif qstatus not in ("UNKNOWN","TIMEOUT"):
                fail("BASE_ANF_MALFORMED_STATUS "+name)
        for cone in c["sampled_cone_sat"]:
            if cone.get("status") not in ("CNF_AVAILABLE","CNF_EXPORT_FAILED","UNSUPPORTED_LOCAL_GATE_CONE"):
                fail("CONE_STATUS_NOT_RECORDED "+name)
            if cone["status"]!="CNF_AVAILABLE":continue
            folder=path/"local_checks"/cone["label"]
            if sha(folder/"miter.v")!=cone["miter_sha256"]:
                fail("REAL_ORIGINAL_GATE_CONE_SHA_MISMATCH "+name)
            if sha(folder/"same_cone.cnf")!=cone["cnf"]["sha256"]:
                fail("KISSAT_CADICAL_NOT_SAME_CNF "+name)
            counts["same_gate_CNF_cones"]+=1
            if cone["yosys_gate_identity"]["status"]=="VERIFIED_LOCAL_GATE_IDENTITY":
                counts["yosys_formal_gate_cones_proved"]+=1
            attempts=cone["solver_runs"]
            if len(attempts)!=4:fail("MISSING_PAIRED_SAT_ATTEMPTS "+name)
            for solver in ("Kissat","CaDiCaL"):
                trials=[t for t in attempts if t["arm"]==solver]
                if len(trials)!=2 or sorted(t["rep"] for t in trials)!=[0,1]:
                    fail("MISSING_SAT_REPETITION "+name)
                for t in trials:
                    if t["status"]=="SAT":fail("SOUNDNESS_ALARM_POLYNOMIAL_IS_FALSE")
                    if t["status"]=="UNSAT":counts[solver+"_UNSAT_reported"]+=1
                    else:counts["SAT_attempts_unfinished_or_unknown"]+=1
        lines.append("| "+name+" | "+status+
          " | "+str(numerical.get("chs","—"))+
          " | "+str(numerical.get("majs","—"))+
          " | "+str(numerical.get("three_input_xor_sums","—"))+
          " | "+str(numerical.get("paired_full_adders_before_limit","—"))+
          " | "+str(numerical.get("globally_proven_motifs","—"))+
          " | "+str(numerical.get("conditional_cut_motifs","—"))+
          " | "+str(len(c["sampled_cone_sat"]))+" |")
        print("REAL6_PROSPECTIVE_SOURCE_AUDITED",name,status,numerical,flush=True)
    lines+=["","## Full non-cherry-picked summary","",
            "| Metric | Count |","|---|---:|"]
    for name,value in counts.items():lines.append("| "+name+" | "+str(value)+" |")
    lines+=["","## Scientific limitations",
        "This is automatic recognition of local 3-variable polynomials",
        "in the output/FF-D or sampled internal bits of Yosys technology-mapped",
        "two-state gates. It does not prove original RTL protocol correctness,",
        "temporal invariants, cryptographic security or whole-core SAT/UNSAT.",
        "The verifier recomputes each 3-input truth table against independent",
        "gate certificate replay, but still trusts Yosys source lowering.",
        "CNF SAT baselines are **local originally generated gate-cone miters**",
        "and are NOT the full FPGA project's CNF. UNSAT is solver-reported",
        "without a separately replayed standard DRAT/LRAT certificate.",
        "An unsupported module is a frontend/dependency limitation, not a",
        "logical impossibility nor a Kissat/CaDiCaL failure."]
    results={"protocol":frozen["protocol"],"prelock_run":45347547028,
             "source_manifest_sha256":sha(args.frozen/"manifest.json"),
             "math_sha256":ENGINE_SHA,"cases":found,"stats":counts}
    args.out.write_text(json.dumps(results,indent=2)+"\n")
    args.report.write_text("\n".join(lines)+"\n")
    print("REAL6_PROSPECTIVE_ALL_FIVE_ORIGINAL_HARDWARE_AUDIT_COMPLETE",flush=True)

if __name__=="__main__":main()
