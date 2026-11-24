#!/usr/bin/env python3
"""REAL4 local-cone SAT crosschecks for selected proof-replayed output bits.

Construct a tiny *exact gate-level cone* from unchanged Yosys original
netlist and compare it to REAL4's reported GF2 affine mask by a miter.
An unsupported/nonlinear output is a free cut input, NOT guessed away.
Both Kissat and CaDiCaL see the exact SAME resulting CNF. This proves
a local gate identity relative to cuts, not complete original RTL SAT/UNSAT.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re
from pathlib import Path

GATE={"$_BUF_","$_NOT_","$_XOR_","$_XNOR_","$_AND_",
      "$_NAND_","$_OR_","$_NOR_","$_MUX_"}
class CannotGenerate(Exception):pass

def fail(why):raise CannotGenerate(why)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def selected(cert,limit=3):
    probes=cert["probes"]
    unique=[]
    for klass in ("GLOBAL_AFFINE_ONE_STEP","LOCAL_AFFINE_WITH_CUTS"):
        for provenance in ("primary_output","ff_next_state","internal_xor"):
            for p in probes:
                if (p["status"]==klass and p["kind"]==provenance and
                        p["yosys_bit"] not in [v["yosys_bit"] for v in unique]):
                    unique.append(p)
                    break
            if len(unique)>=limit:return unique
    return unique

def miter(net,cert,probe):
    module=net["modules"][cert["top"]]
    sources={}
    for cname,cell in sorted(module["cells"].items()):
        outs=[p for p,d in cell.get("port_directions",{}).items() if d=="output"]
        if not outs and "Y" in cell.get("connections",{}):outs=["Y"]
        for port in outs:
            for j,bit in enumerate(cell["connections"][port]):
                if isinstance(bit,int):
                    if bit in sources:fail("DUPLICATE_DRIVER")
                    sources[bit]=(cell,port)
    basis={v["yosys_bit"]:v["index"] for v in cert["basis"]}
    cut={v["yosys_bit"]:v["index"] for v in cert["cutpoints"]}
    term_by_index={v["index"]:v["yosys_bit"] for v in cert["basis"]+cert["cutpoints"]}
    # Keep terminal positions stable and compact by original REAL4 bit index.
    references={}
    operations=[]
    active=set()
    built=set()
    def ref(bit):
        if bit=="0":return "1'b0"
        if bit=="1":return "1'b1"
        if not isinstance(bit,int):fail("X_Z_IN_SAT_MITER")
        if bit in basis or bit in cut:
            i=(basis[bit] if bit in basis else cut[bit])
            references[i]=True
            return "T_"+str(i)
        if bit in active:fail("COMBINATIONAL_CYCLE")
        if bit in built:return "g_"+str(bit)
        source=sources.get(bit)
        if source is None:fail("UNDRIVEN")
        cell,port=source
        kind=cell["type"]
        if kind not in GATE or port!="Y" or len(cell["connections"]["Y"])!=1:
            fail("UNSUPPORTED_NOT_MARKED_CUT")
        active.add(bit)
        try:
            args={}
            for p in ("A","B","S"):
                if p in cell["connections"]:
                    pins=cell["connections"][p]
                    if len(pins)!=1:fail("NON_SCALAR")
                    args[p]=ref(pins[0])
            a,b=args.get("A"),args.get("B")
            if a is None:fail("MISSING_A")
            if kind=="$_BUF_":expr=a
            elif kind=="$_NOT_":expr=f"~({a})"
            else:
                if b is None:fail("MISSING_B")
                if kind=="$_XOR_":expr=f"({a}) ^ ({b})"
                elif kind=="$_XNOR_":expr=f"~(({a}) ^ ({b}))"
                elif kind=="$_AND_":expr=f"({a}) & ({b})"
                elif kind=="$_NAND_":expr=f"~(({a}) & ({b}))"
                elif kind=="$_OR_":expr=f"({a}) | ({b})"
                elif kind=="$_NOR_":expr=f"~(({a}) | ({b}))"
                elif kind=="$_MUX_":
                    if "S" not in args:fail("MISSING_S")
                    expr=f"({args['S']}) ? ({b}) : ({a})"
                else:fail("UNKNOWN_GATE")
            operations.append((bit,expr))
            built.add(bit)
            return "g_"+str(bit)
        finally:active.remove(bit)
    terminal=ref(probe["yosys_bit"])
    mask=int(probe["mask_hex"],16)
    for i in range(len(cert["basis"])+len(cert["cutpoints"])):
        if mask&(1<<(i+1)):references[i]=True
    if not references:
        # constant output: input bus of one unused bit is harmless
        references[0]=True
    ids=sorted(references)
    pin_mapping={j:i for i,j in enumerate(ids)}
    lines=[f"module miter(input wire [{len(ids)-1}:0] bitvars, output wire mismatch);"]
    for bit in ids:
        lines.append(f" wire T_{bit} = bitvars[{pin_mapping[bit]}];")
    for bit,expr in operations:
        lines.append(f" wire g_{bit} = {expr};")
    terms=[f"T_{i}" for i in ids if mask&(1<<(i+1))]
    if mask&1:terms+=["1'b1"]
    spec=" ^ ".join(terms) if terms else "1'b0"
    lines+=[f" wire actual = {terminal};",
            f" wire model = {spec};",
            " assign mismatch = actual ^ model;",
            "endmodule"]
    return "\n".join(lines)+"\n",{"provenance":probe["kind"],"name":probe["name"],
          "position":probe["position"],"net_bit":probe["yosys_bit"],
          "mask_hex":probe["mask_hex"],"local_cut_indices":probe.get("cut_indices",[]),
          "input_symbols":len(ids),"gate_count":len(operations),
          "scope":"real synthesized Boolean cone with free cut/state inputs"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    cert=json.loads((a.folder/"real4_certificate.json").read_text())
    net=json.loads((a.folder/"netlist.json").read_text())
    if hashlib.sha256((a.folder/"netlist.json").read_bytes()).hexdigest()!=cert["netlist_sha256"]:
        fail("NETLIST_HASH")
    a.out.mkdir(exist_ok=True,parents=True)
    result=[]
    for i,probe in enumerate(selected(cert)):
        label="cone_"+str(i)
        try:
            raw,record=miter(net,cert,probe)
            where=a.out/label
            where.mkdir(exist_ok=True)
            dest=where/"miter.v"
            dest.write_text(raw)
            result.append({"name":label,"status":"GENERATED",
                           "miter_sha256":sha(dest),**record})
        except CannotGenerate as e:
            result.append({"name":label,"status":"NOT_SUPPORTED","reason":str(e)})
    (a.out/"cones.json").write_text(json.dumps(result,indent=2)+"\n")
    print("REAL4_GENUINE_GATE_CONES",len(result),[x["status"] for x in result])
if __name__=="__main__":main()
