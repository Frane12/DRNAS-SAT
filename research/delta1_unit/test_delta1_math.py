#!/usr/bin/env python3
"""Independent adversarial DELTA1 proof/witness tests (no Yosys necessary)."""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"apps/circuitcheck"))
from delta1_engine import write_certificate
from delta1_verify import verify, Invalid

def make_case(folder,kind,width=4):
    folder.mkdir(parents=True,exist_ok=True)
    ins=list(range(2,width+2))
    nextbit=width+2
    cells={}
    def gate(op,a,b=None,s=None):
        nonlocal nextbit
        out=nextbit;nextbit+=1
        args={"A":[a],"Y":[out]}
        directions={"A":"input","Y":"output"}
        if b is not None: args["B"]=[b];directions["B"]="input"
        if s is not None: args["S"]=[s];directions["S"]="input"
        cells["g"+str(out)]={"type":op,"connections":args,"port_directions":directions}
        return out
    xor=gate("$_XOR_",ins[0],ins[-1])
    if kind=="equal":
        ref=xor;target=gate("$_XOR_",ins[-1],ins[0])
    elif kind=="fault":
        ref=xor;target=gate("$_NOT_",xor)
    elif kind=="nonlinear":
        ref=gate("$_AND_",ins[0],ins[-1]);target=ref
    elif kind=="complement_mux":
        ref=gate("$_NOT_",xor)
        target=gate("$_MUX_",xor,ref,"1")
        # select constant one; target = NOT xor
    else:raise ValueError(kind)
    mod={"ports":{"data":{"direction":"input","bits":ins},
                  "drnas_ref_out":{"direction":"output","bits":[ref]},
                  "drnas_impl_out":{"direction":"output","bits":[target]}},
          "cells":cells}
    net={"modules":{"drnas_compare":mod}}
    iface={"top":"drnas_compare","pairs":[{"port":"out","reference":"drnas_ref_out",
                                             "candidate":"drnas_impl_out"}]}
    (folder/"netlist.json").write_text(json.dumps(net)+"\n")
    (folder/"interface.json").write_text(json.dumps(iface)+"\n")
    return write_certificate(folder/"netlist.json",folder/"interface.json",
                             folder/"delta1_certificate.json")

def main():
    expected={"equal":"EQUIVALENT_NETLIST","fault":"DIFFERENT_NETLIST",
              "nonlinear":"UNKNOWN_UNSUPPORTED","complement_mux":"EQUIVALENT_NETLIST"}
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for name,width in [("equal",4),("fault",4),("nonlinear",4),
                           ("complement_mux",4),("fault",2048),("equal",2048)]:
            where=root/(name+"_"+str(width))
            cert=make_case(where,name,width)
            if cert["status"]!=expected[name]:
                raise RuntimeError("unsound verdict "+str((name,width,cert["status"])))
            if cert["status"]=="UNKNOWN_UNSUPPORTED":
                try:verify(where)
                except Invalid:pass
                else:raise RuntimeError("UNKNOWN somehow certified")
            else:
                outcome=verify(where)
                predicted="CHECKED_EQUIVALENT_NETLIST" if name in ("equal","complement_mux") else "CHECKED_DIFFERENT_NETLIST"
                if outcome["status"]!=predicted:raise RuntimeError("bad replay")
                data=json.loads((where/"delta1_certificate.json").read_text())
                data["checked_outputs"][0]["difference_mask"]="0xDEADBEEF"
                (where/"delta1_certificate.json").write_text(json.dumps(data)+"\n")
                try:verify(where)
                except Invalid:pass
                else:raise RuntimeError("tampered certificate accepted")
            print("DELTA1_UNIT",name,width,cert["status"],flush=True)
    print("DELTA1_ADVERSARIAL_UNIT_PASS",flush=True)
if __name__=="__main__":main()
