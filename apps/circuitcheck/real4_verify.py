#!/usr/bin/env python3
"""Independent REAL4 affine-island certificate replay.

This checker does NOT import real4_islands.py nor use its mask evaluator.
It works with GF(2) monomial *sets* (not Python integer bitmasks) and
rediscovers every FF-Q source, nonlinear/unsupported cutpoint and probe
from the immutable Yosys JSON. A successful check establishes only
one-cycle/local exact identities relative to real gate-output cut signals,
NOT arbitrary source RTL equivalence, temporal properties, SAT or UNSAT.
"""
from __future__ import annotations
import collections,hashlib,json,sys
from pathlib import Path

BASIC={"$_BUF_","$_NOT_","$_XOR_","$_XNOR_",
       "$_AND_","$_NAND_","$_OR_","$_NOR_","$_MUX_"}
ONE=frozenset([-1])
ZERO=frozenset()
class Rejected(Exception):pass
def stop(s):raise Rejected(s)
def sequential(kind):
    t=kind.lower()
    return ("dff" in t or "dffe" in t or t in ("$ff","$_ff_")) and "latch" not in t
def masks(fs):
    value=0
    for pos in fs:
        if pos == -1:value^=1
        elif pos>=0:value^=1<<(pos+1)
        else:stop("BAD_GALOIS_VARIABLE")
    return hex(value)

def proof_replay(folder:Path):
    raw=(folder/"netlist.json").read_bytes()
    cert=json.loads((folder/"real4_certificate.json").read_text())
    if cert.get("netlist_sha256")!=hashlib.sha256(raw).hexdigest():
        stop("NETLIST_SHA256_MISMATCH")
    top=cert.get("top")
    net=json.loads(raw)
    module=net.get("modules",{}).get(top)
    if not isinstance(module,dict):stop("TOP_CHANGED")
    cells=module.get("cells",{})
    ports=module.get("ports",{})
    if len(cells)>200000:stop("CELL_BUDGET")
    source={}
    ff_basis=[]
    dprobes=[]
    for cname,cell in sorted(cells.items()):
        kind=cell.get("type","")
        dirs=cell.get("port_directions",{})
        outputs=[k for k,v in dirs.items() if v=="output"]
        if not outputs and "Y" in cell.get("connections",{}):outputs=["Y"]
        for port in outputs:
            for offset,bit in enumerate(cell["connections"].get(port,[])):
                if isinstance(bit,int):
                    if bit in source:stop("MULTIPLE_NET_DRIVERS")
                    source[bit]=(cname,cell,port,offset)
        if sequential(kind):
            connections=cell.get("connections",{})
            qs=connections.get("Q")
            ds=connections.get("D")
            if qs is None or ds is None or len(qs)!=len(ds):
                stop("UNRECOGNIZED_FF")
            for position,(q,d) in enumerate(zip(qs,ds)):
                if not isinstance(q,int):stop("NON_BINARY_FF_Q")
                ff_basis.append({"source":"state_Q","cell":cname,"position":position,
                                 "yosys_bit":q})
                dprobes.append({"kind":"ff_next_state","name":cname,"position":position,
                                "yosys_bit":d})
    raw_inputs=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="input":
            for position,bit in enumerate(p["bits"]):
                if not isinstance(bit,int):stop("NON_BINARY_INPUT")
                raw_inputs.append({"source":"input","name":name,"position":position,
                                   "yosys_bit":bit})
    basis=[]
    memory={"0":ZERO,"1":ONE}
    for item in raw_inputs+ff_basis:
        bit=item["yosys_bit"]
        if bit in memory:continue
        if item["source"]=="input" and bit in source:
            stop("INPUT_IS_DRIVEN")
        entry={**item,"index":len(basis)}
        memory[bit]=frozenset([len(basis)])
        basis.append(entry)
    if cert.get("basis")!=basis:stop("PRIMARY_AND_STATE_BASIS_CHANGED")
    if len(basis)>8192:stop("INPUT_BASIS_BUDGET")
    for x in ff_basis:
        drv=source.get(x["yosys_bit"])
        if drv is None or not sequential(drv[1].get("type","")):
            stop("FAKE_STATE_BIT")
    cuts=[]
    cut_map={}
    active=set()
    sys.setrecursionlimit(max(sys.getrecursionlimit(),100000))
    def cut(bit,why):
        if bit not in cut_map:
            if len(basis)+len(cuts)>=8192:stop("CUT_BUDGET")
            cname,cell,port,pos=source[bit]
            ident=len(basis)+len(cuts)
            entry={"yosys_bit":bit,"cell":cname,"kind":cell.get("type",""),
                   "output_port":port,"output_position":pos,
                   "reason":why,"index":ident}
            cuts.append(entry)
            cut_map[bit]=entry
        return frozenset([cut_map[bit]["index"]])
    def is_and_affine(a,b):
        if not a or not b:return ZERO
        if a==ONE:return b
        if b==ONE:return a
        if a==b:return a
        if a.symmetric_difference(b)==ONE:return ZERO
        raise Rejected("NONLINEAR")
    def resolve(bit):
        if bit in memory:return memory[bit]
        if not isinstance(bit,int):stop("NON_BINARY_WIRE")
        if bit in active:stop("COMBINATIONAL_CYCLE")
        item=source.get(bit)
        if item is None:stop("NO_SIGNAL_DRIVER")
        cname,cell,output,pos=item
        kind=cell.get("type","")
        if sequential(kind):stop("UNMODELED_FF_PIN")
        if kind not in BASIC or output!="Y" or len(cell["connections"].get("Y",[]))!=1:
            result=cut(bit,"UNSUPPORTED_CELL_OR_PORT")
            memory[bit]=result
            return result
        active.add(bit)
        try:
            operands={}
            for k in ("A","B","S"):
                wires=cell["connections"].get(k)
                if wires is not None:
                    if len(wires)!=1:stop("NON_SCALAR_GATE_INPUT")
                    operands[k]=resolve(wires[0])
            if "A" not in operands:stop("NO_GATE_A")
            a=operands["A"]
            if kind=="$_BUF_":result=a
            elif kind=="$_NOT_":result=a.symmetric_difference(ONE)
            else:
                if "B" not in operands:stop("NO_GATE_B")
                b=operands["B"]
                if kind in ("$_XOR_","$_XNOR_"):
                    result=a.symmetric_difference(b)
                    if kind=="$_XNOR_":result=result.symmetric_difference(ONE)
                elif kind in ("$_AND_","$_NAND_"):
                    try:
                        result=is_and_affine(a,b)
                        if kind=="$_NAND_":result=result.symmetric_difference(ONE)
                    except Rejected:result=cut(bit,"NONLINEAR_AND")
                elif kind in ("$_OR_","$_NOR_"):
                    try:
                        result=is_and_affine(a.symmetric_difference(ONE),
                                             b.symmetric_difference(ONE)).symmetric_difference(ONE)
                        if kind=="$_NOR_":result=result.symmetric_difference(ONE)
                    except Rejected:result=cut(bit,"NONLINEAR_OR")
                elif kind=="$_MUX_":
                    if "S" not in operands:stop("MISSING_MUX_S")
                    s=operands["S"]
                    if s==ZERO:result=a
                    elif s==ONE:result=b
                    elif a==b:result=a
                    elif a.symmetric_difference(b)==ONE:result=a.symmetric_difference(s)
                    else:result=cut(bit,"NONLINEAR_MUX")
                else:stop("UNKNOWN_GATE")
            memory[bit]=result
            return result
        finally:
            active.remove(bit)
    probes=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="output":
            for j,bit in enumerate(p["bits"]):
                probes.append({"kind":"primary_output","name":name,
                               "position":j,"yosys_bit":bit})
    probes.extend(dprobes)
    total_xor=0
    for name,cell in sorted(cells.items()):
        if cell.get("type") in ("$_XOR_","$_XNOR_"):
            total_xor+=1
            if total_xor<=32:
                for bit in cell.get("connections",{}).get("Y",[]):
                    probes.append({"kind":"internal_xor","name":name,
                                   "position":0,"yosys_bit":bit})
    if len(probes)>1536:stop("PROBES_BUDGET")
    rows=[]
    for p in probes:
        record=dict(p)
        try:
            value=resolve(p["yosys_bit"])
            cut_indices=[v["index"] for v in cuts if v["index"] in value]
            record.update({"mask_hex":masks(value),
                "status":"LOCAL_AFFINE_WITH_CUTS" if cut_indices else "GLOBAL_AFFINE_ONE_STEP",
                "cut_indices":cut_indices})
        except Rejected as e:
            record.update({"status":"UNKNOWN","reason":str(e)})
        rows.append(record)
    if cert.get("cutpoints")!=cuts:stop("NONLINEAR_CUT_CERTIFICATE_CHANGED")
    # UNKNOWN explanations may be phrased differently by the independently
    # implemented engines. The independently recomputed UNKNOWN *status*
    # must agree; exact affine masks/cut identities must match in full.
    submitted=cert.get("probes")
    if not isinstance(submitted,list) or len(submitted)!=len(rows):
        stop("PROBE_COVERAGE_CHANGED")
    for got,correct in zip(submitted,rows):
        if got.get("status")=="UNKNOWN" and correct.get("status")=="UNKNOWN":
            ga={k:v for k,v in got.items() if k!="reason"}
            ca={k:v for k,v in correct.items() if k!="reason"}
            if ga!=ca:stop("UNKNOWN_PROBE_METADATA_MISMATCH")
        elif got!=correct:
            stop("PROBE_EXPR_NOT_REPRODUCIBLE")
    metrics=cert.get("metrics",{})
    checks={
        "cells":len(cells),
        "input_bits":len(raw_inputs),
        "state_Q_bits":len(ff_basis),
        "xor_gate_count":total_xor,
        "primary_output_bits":sum(x["kind"]=="primary_output" for x in rows),
        "next_state_bits":len(dprobes),
        "global_affine_external_and_state_probes":sum(x["status"]=="GLOBAL_AFFINE_ONE_STEP" and x["kind"]!="internal_xor" for x in rows),
        "local_affine_external_and_state_probes":sum(x["status"]=="LOCAL_AFFINE_WITH_CUTS" and x["kind"]!="internal_xor" for x in rows),
        "unknown_external_and_state_probes":sum(x["status"]=="UNKNOWN" and x["kind"]!="internal_xor" for x in rows),
        "cutpoints":len(cuts)
    }
    if any(metrics.get(k)!=v for k,v in checks.items()):
        stop("REPORTED_COUNTS_DIVERGE")
    if cert.get("status")!="STRUCTURE_EXTRACTED_NOT_A_FULL_CIRCUIT_SAT_VERDICT":
        stop("VERDICT_SCOPE_FALSE")
    return {"status":"CHECKED_LOCAL_AFFINE_GATE_IDENTITIES",
            "netlist_sha256":cert["netlist_sha256"],"top":top,
            "replayed_probes":len(rows),"verified_cutpoints":len(cuts),
            "global_affine_probes":checks["global_affine_external_and_state_probes"],
            "local_affine_probes":checks["local_affine_external_and_state_probes"],
            "unknown_probes":checks["unknown_external_and_state_probes"],
            "scope":"not a SAT/UNSAT or sequential temporal proof"}

def main():
    folder=Path(sys.argv[1])
    try:
        result=proof_replay(folder)
        (folder/"real4_verification.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result))
        return 0
    except (Rejected,KeyError,ValueError,TypeError,IndexError,RecursionError,
            OverflowError,FileNotFoundError,MemoryError) as e:
        print(json.dumps({"status":"NOT_VERIFIED","reason":str(e)}))
        return 2
if __name__=="__main__":raise SystemExit(main())
