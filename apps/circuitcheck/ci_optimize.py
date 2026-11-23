#!/usr/bin/env python3
"""CI for v0.2: proof gating, gate metrics, nonlinear rejection and tamper controls."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys

APP=Path(__file__).resolve().parent
OUT=Path("circuitcheck-opt-v02-results")

def run(cmd,timeout=180):
    return subprocess.run([str(x) for x in cmd],capture_output=True,text=True,
                          timeout=timeout,check=False)

def main():
    OUT.mkdir(exist_ok=True)
    p=run([sys.executable,APP/"generate_examples.py","--out",OUT/"examples"])
    if p.returncode:raise RuntimeError("generate examples failed:\n"+p.stderr)
    manifest=json.loads((OUT/"examples/manifest.json").read_text())
    selected=[x for x in manifest if x["kind"] in ("crc","lfsr","gray","nonlinear")
              and x["expected"]=="EQUIVALENT_NETLIST"]
    assert len(selected)==5
    summary=[]
    for item in selected:
        input_file=OUT/"examples"/item["file"]
        original_hash=hashlib.sha256(input_file.read_bytes()).hexdigest()
        if original_hash!=item["sha256"]:raise RuntimeError("frozen RTL mismatch")
        out=OUT/"cases"/Path(item["file"]).stem
        r=run([sys.executable,APP/"optimize.py","--rtl",input_file,
               "--reference","reference","--out",out],300)
        report=json.loads((out/"optimization.json").read_text())
        outcome=report["status"]
        if item["kind"]=="nonlinear":
            if outcome!="UNKNOWN" or "NONLINEAR_ANF" not in report.get("reason",""):
                raise RuntimeError("nonlinear safe rejection did not occur "+str(report))
        else:
            if r.returncode!=0 or not outcome.startswith("PROVED_"):
                raise RuntimeError("proof missing on "+item["file"]+"\n"+
                                   json.dumps(report,indent=2)+"\n"+r.stdout[-3000:])
            if report["proof"]!="CHECKED_EQUIVALENT_NETLIST":
                raise RuntimeError("not independently replayable")
            again=run([sys.executable,APP/"verify_certificate.py",out/"proof"])
            if again.returncode:raise RuntimeError("proof verifier rejected emitted candidate")
            # Alter a previously verified certificate: independent checker must reject it.
            certfile=out/"proof/certificate.json"
            original=certfile.read_bytes()
            cert=json.loads(original)
            cert["output_polynomials"][0]["candidate_terms"]=["0xdeadbeef"]
            certfile.write_text(json.dumps(cert))
            corrupt=run([sys.executable,APP/"verify_certificate.py",out/"proof"])
            certfile.write_bytes(original)
            if corrupt.returncode==0:raise RuntimeError("tampered certificate accepted")
        if hashlib.sha256(input_file.read_bytes()).hexdigest()!=original_hash:
            raise RuntimeError("source input changed")
        summary.append({"case":item["file"],"status":outcome,
                        "reference_gate_count":report.get("original",{}).get("gate_count"),
                        "candidate_gate_count":report.get("candidate",{}).get("gate_count"),
                        "original_gate_depth":report.get("original",{}).get("max_gate_depth"),
                        "candidate_gate_depth":report.get("candidate",{}).get("max_gate_depth"),
                        "shared_subexpressions":report.get("math",{}).get("shared_nodes"),
                        "wall_s":report["end_to_end_seconds"],"reason":report.get("reason")})
        (OUT/"audit.json").write_text(json.dumps(summary,indent=2)+"\n")
        print("OPT_CASE",item["file"],outcome,
              "ref",report.get("original",{}).get("gate_count"),
              "new",report.get("candidate",{}).get("gate_count"),flush=True)
    assert len(summary)==5
    lines=["# DRNAS CircuitCheck Optimize v0.2 — CI",
           "",
           "Gate numbers are generic technology-independent Yosys mapped logic cells, NOT FPGA LUTs.",
           "Optimized modules are approved only after exact ANF and independent replay;",
           "nonlinear inputs safely return UNKNOWN. Timing/power is not claimed.",
           "",
           "| Case | Outcome | Reference gates | Candidate gates | Ref depth | Candidate depth |",
           "|---|---|---:|---:|---:|---:|"]
    for row in summary:
        lines.append(f"| {row['case']} | {row['status']} | {row['reference_gate_count'] or '—'} | {row['candidate_gate_count'] or '—'} | {row['original_gate_depth'] or '—'} | {row['candidate_gate_depth'] or '—'} |")
    (OUT/"AUDIT.md").write_text("\n".join(lines)+"\n")
    print("DRNAS_CIRCUITCHECK_V02_TESTS_PASS",flush=True)

if __name__=="__main__":
    main()
