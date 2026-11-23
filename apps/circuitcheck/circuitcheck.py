#!/usr/bin/env python3
"""DRNAS CircuitCheck v0.1 — real Verilog/RTL equality by certified ANF.

Examples:
 python3 apps/circuitcheck/circuitcheck.py --rtl examples/gray_equal.v \
   --reference reference --candidate candidate --out build/gray
 python3 apps/circuitcheck/verify_certificate.py build/gray
 exit codes: 0 algebraically equal; 10 concrete difference; 2 UNKNOWN; 1 error

This tool is a *proof checker for the synthesized combinational Yosys gate
netlist*, not yet an independent proof against raw Verilog semantics and
not a general SAT solver. Unsupported gates return UNKNOWN, not UNSAT.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time
from proof_engine import Unsupported, check_file

def yosys(script: str, work: pathlib.Path, timeout_s:float):
    p=work/"run.ys"
    p.write_text(script+"\n")
    run=subprocess.run(["yosys","-s",p.name],cwd=work,
                       capture_output=True,text=True,timeout=timeout_s)
    (work/"yosys.log").write_text(run.stdout+"\n"+run.stderr)
    if run.returncode:
        raise RuntimeError("Yosys failed, see "+str(work/"yosys.log"))
    return run.stdout

def identify_ports(pre:dict, reference:str, candidate:str):
    modules=pre.get("modules",{})
    if reference==candidate or reference not in modules or candidate not in modules:
        raise ValueError("two distinct existing module names are required")
    a=modules[reference].get("ports",{})
    b=modules[candidate].get("ports",{})
    if set(a)!=set(b):
        raise ValueError("module port names are different")
    import re
    for name in a:
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*",name):
            raise ValueError("escaped/special port names not yet supported")
        if a[name].get("direction")!=b[name].get("direction"):
            raise ValueError("port directions differ: "+name)
        if a[name]["direction"] not in ("input","output"):
            raise ValueError("only unclocked input/output interfaces supported")
        if len(a[name]["bits"])!=len(b[name]["bits"]):
            raise ValueError("port widths differ: "+name)
    if not any(p["direction"]=="input" for p in a.values()):
        raise ValueError("at least one input needed")
    if not any(p["direction"]=="output" for p in a.values()):
        raise ValueError("at least one output needed")
    return a

def build_wrapper(ports, reference, candidate):
    def wire(width,name):
        return f"wire [{width-1}:0] {name}"
    names=sorted(ports)
    params=[]
    left=[];right=[];connections_a=[];connections_b=[]
    interface={"top":"drnas_compare","pairs":[]}
    for name in names:
        width=len(ports[name]["bits"])
        if ports[name]["direction"]=="input":
            params.append(f"input wire [{width-1}:0] {name}")
            connections_a.append(f".{name}({name})")
            connections_b.append(f".{name}({name})")
        else:
            ref_name="drnas_ref_"+name
            impl_name="drnas_impl_"+name
            params.extend((f"output wire [{width-1}:0] {ref_name}",
                           f"output wire [{width-1}:0] {impl_name}"))
            connections_a.append(f".{name}({ref_name})")
            connections_b.append(f".{name}({impl_name})")
            interface["pairs"].append({"port":name,"reference":ref_name,
                                       "candidate":impl_name})
    wrapper=f"module drnas_compare(\n  "+",\n  ".join(params)+");\n"
    wrapper+=f"  {reference} drnas_reference(\n    "+",\n    ".join(connections_a)+");\n"
    wrapper+=f"  {candidate} drnas_candidate(\n    "+",\n    ".join(connections_b)+");\n"
    wrapper+="endmodule\n"
    return wrapper,interface

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--rtl",type=pathlib.Path,nargs="+",required=True)
    ap.add_argument("--reference",required=True,help="reference Verilog module")
    ap.add_argument("--candidate",required=True,help="candidate Verilog module")
    ap.add_argument("--out",type=pathlib.Path,required=True)
    ap.add_argument("--yosys-timeout",type=int,default=90)
    a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    try:
        rtl_files=[]
        origins=[]
        for n,source in enumerate(a.rtl):
            source=source.resolve()
            if not source.is_file():raise ValueError("missing RTL: "+str(source))
            target=out/f"input_{n}.v";shutil.copyfile(source,target)
            rtl_files.append(target.name)
            origins.append({"name":source.name,"sha256":hashlib.sha256(source.read_bytes()).hexdigest()})
        files=" ".join(rtl_files)
        yosys("read_verilog -sv "+files+"; proc; opt; write_json pre.json",
              out,a.yosys_timeout)
        pre=json.loads((out/"pre.json").read_text())
        ports=identify_ports(pre,a.reference,a.candidate)
        wrapper,interface=build_wrapper(ports,a.reference,a.candidate)
        (out/"wrapper.v").write_text(wrapper)
        (out/"interface.json").write_text(json.dumps(interface,indent=2)+"\n")
        yosys("read_verilog -sv "+files+
              " wrapper.v; hierarchy -check -top drnas_compare; "
              "proc; flatten; opt; techmap; opt; write_json netlist.json",
              out,a.yosys_timeout)
        evidence=check_file(out/"netlist.json",out/"interface.json",out/"certificate.json")
        report={"tool":"DRNAS CircuitCheck v0.1","status":evidence["status"],
                "level":"exact ANF proof over synthesized Yosys combinational gate netlist",
                "reference_module":a.reference,"candidate_module":a.candidate,
                "source_files":origins,
                "verification":"run verify_certificate.py OUTPUT_DIRECTORY",
                "elapsed_seconds":round(time.perf_counter()-start,6),
                "certificate_sha256":hashlib.sha256((out/"certificate.json").read_bytes()).hexdigest()}
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(report,indent=2),flush=True)
        return {"EQUIVALENT_NETLIST":0,"DIFFERENT_NETLIST":10,
                "UNKNOWN_UNSUPPORTED":2}[evidence["status"]]
    except (Unsupported,ValueError,RuntimeError,subprocess.TimeoutExpired) as ex:
        report={"tool":"DRNAS CircuitCheck v0.1","status":"UNKNOWN_UNSUPPORTED",
                "reason":str(ex),"elapsed_seconds":round(time.perf_counter()-start,6)}
        (out/"report.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(report,indent=2),flush=True)
        return 2

if __name__=="__main__":
    sys.exit(main())
