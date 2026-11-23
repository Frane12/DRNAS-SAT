#!/usr/bin/env python3
"""DRNAS DELTA1: Verilog -> optimized gate netlist -> compact affine witness/proof.

Exit 0 exact equivalent netlist, 10 concrete difference, 2 UNKNOWN/error.
Certificate must be independently replayed with delta1_verify.py; this
launcher deliberately does not claim raw Verilog semantic proof.
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
from circuitcheck import yosys, identify_ports, build_wrapper
from delta1_engine import Unknown, write_certificate

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--rtl",nargs="+",required=True,type=pathlib.Path)
    p.add_argument("--reference",required=True)
    p.add_argument("--candidate",required=True)
    p.add_argument("--out",required=True,type=pathlib.Path)
    p.add_argument("--yosys-timeout",type=int,default=100)
    args=p.parse_args()
    work=args.out.resolve()
    work.mkdir(parents=True, exist_ok=True)
    start=time.perf_counter()
    info={"engine":"DRNAS-DELTA1-AFFINE","status":"UNKNOWN_UNSUPPORTED",
          "proof_scope":"Yosys-synthesized combinational gate netlist, 2-state"}
    try:
        sources=[]
        hashes=[]
        for i,src in enumerate(args.rtl):
            src=src.resolve()
            if not src.is_file():
                raise Unknown("RTL_FILE_NOT_FOUND "+str(src))
            local=work/("source_"+str(i)+".v")
            shutil.copyfile(src,local)
            sources.append(local.name)
            hashes.append({"name":src.name,"sha256":hashlib.sha256(src.read_bytes()).hexdigest()})
        files=" ".join(sources)
        # Shared Yosys frontend/proc/synthesis path with v0.1 CircuitCheck.
        yosys("read_verilog -sv "+files+"; proc; opt; write_json pre.json",
              work,args.yosys_timeout)
        pre=json.loads((work/"pre.json").read_text())
        ports=identify_ports(pre,args.reference,args.candidate)
        wrapper,iface=build_wrapper(ports,args.reference,args.candidate)
        (work/"wrapper.v").write_text(wrapper)
        (work/"interface.json").write_text(json.dumps(iface,indent=2)+"\n")
        yosys("read_verilog -sv "+files+" wrapper.v; "
              "hierarchy -check -top drnas_compare; proc; flatten; opt; "
              "techmap; opt; write_json netlist.json",
              work,args.yosys_timeout)
        result=write_certificate(work/"netlist.json",work/"interface.json",
                                 work/"delta1_certificate.json")
        info.update({"status":result["status"],"metrics":result["metrics"],
                     "netlist_sha256":result["netlist_sha256"],
                     "certificate_sha256":hashlib.sha256((work/"delta1_certificate.json").read_bytes()).hexdigest(),
                     "sources":hashes,"reference":args.reference,
                     "candidate":args.candidate})
    except (Unknown,ValueError,KeyError,RuntimeError,RecursionError,subprocess.TimeoutExpired,
            MemoryError,OverflowError) as ex:
        info["status"]="UNKNOWN_UNSUPPORTED"
        info["reason"]=str(ex)
    info["wall_seconds"]=round(time.perf_counter()-start,6)
    (work/"delta1_report.json").write_text(json.dumps(info,indent=2)+"\n")
    print(json.dumps(info,indent=2),flush=True)
    return {"EQUIVALENT_NETLIST":0,"DIFFERENT_NETLIST":10,
            "UNKNOWN_UNSUPPORTED":2}[info["status"]]

if __name__=="__main__":
    sys.exit(main())
