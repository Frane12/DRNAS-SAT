#!/usr/bin/env python3
"""Run CircuitCheck end-to-end proof, fault, tamper and UNKNOWN controls in CI."""
from __future__ import annotations
import hashlib,json,pathlib,shutil,subprocess,sys,time

ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path("circuitcheck-ci-results")
EXAMPLES=OUT/"examples"

def run(*cmd,timeout=150):
    return subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=timeout)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    p=run(sys.executable,ROOT/"generate_examples.py","--out",EXAMPLES)
    if p.returncode:raise RuntimeError("generator: "+p.stderr)
    cases=json.loads((EXAMPLES/"manifest.json").read_text())
    summary=[]
    for x in cases:
        path=EXAMPLES/x["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=x["sha256"]:
            raise RuntimeError("example SHA mismatch")
        out=OUT/"cases"/path.stem
        p=run(sys.executable,ROOT/"circuitcheck.py",
            "--rtl",path,"--reference","reference","--candidate","candidate",
            "--out",out,timeout=210)
        report=json.loads((out/"report.json").read_text())
        got=report["status"]
        row={"case":x["file"],"expected":x["expected"],"actual":got,
             "return_code":p.returncode,"wall_s":report["elapsed_seconds"]}
        print("CIRCUITCHECK",x["file"],got,report["elapsed_seconds"],"s",flush=True)
        if got!=x["expected"]:
            raise RuntimeError("unexpected verdict "+str(row)+"\n"+
                               p.stdout[-2000:]+"\n"+p.stderr[-2000:])
        if got=="UNKNOWN_UNSUPPORTED":
            if p.returncode!=2:raise RuntimeError("UNKNOWN exit contract failed")
            row["checker"]="NOT_APPLICABLE"
        else:
            if p.returncode!=(0 if got=="EQUIVALENT_NETLIST" else 10):
                raise RuntimeError("exit status mismatch "+str(row))
            v=run(sys.executable,ROOT/"verify_certificate.py",out)
            if v.returncode:raise RuntimeError("independent cert checker FAILED "+str(row)+"\n"+v.stdout)
            ver=json.loads((out/"verification.json").read_text())
            row["checker"]=ver["status"]
            # Tampering with a signed output polynomial must be rejected.
            cert_file=out/"certificate.json"
            original=cert_file.read_bytes()
            cert=json.loads(original)
            cert["output_polynomials"][0]["ref_terms"]=["0xdeadbeef"]
            cert_file.write_text(json.dumps(cert))
            bad=run(sys.executable,ROOT/"verify_certificate.py",out)
            cert_file.write_bytes(original)
            if bad.returncode==0:
                raise RuntimeError("tampered certificate was accepted")
            row["tamper_rejected"]=True
        summary.append(row)
        (OUT/"audit.json").write_text(json.dumps(summary,indent=2)+"\n")
    assert len(summary)==11
    assert sum(c["actual"]=="EQUIVALENT_NETLIST" for c in summary)==5
    assert sum(c["actual"]=="DIFFERENT_NETLIST" for c in summary)==5
    assert sum(c["actual"]=="UNKNOWN_UNSUPPORTED" for c in summary)==1
    (OUT/"AUDIT.md").write_text("# DRNAS CircuitCheck v0.1 CI audit\n\n"+
      "| Circuit | Expected | Result | Duration | Cert replay |\n"+
      "|---|---|---|---:|---|\n"+
      "\n".join(f"| {c['case']} | {c['expected']} | {c['actual']} | {c['wall_s']:.3f}s | {c['checker']} |"
                for c in summary)+"\n\n"+
      "Mathematical proof scope: synthesized two-state Yosys gate netlist, not source-Verilog standard certificate.\n")
    print("CIRCUITCHECK_ALL_11_TESTS_PASS",flush=True)

if __name__=="__main__":
    main()
