#!/usr/bin/env python3
"""DRNAS REAL4: certifiable affine islands in arbitrary flattened 2-state gates.

Unlike REAL2/REAL3 this engine has NO source/template/filename/SHA lookup.
Given Yosys techmapped JSON it symbolically evaluates each output, every FF D
next-state bit, and up to 32 internal XOR signals. An XOR/NOT/BUF chain
is an exact GF(2) affine function of primary input and FF Q state symbols.
For nonlinear or unsupported cells it introduces a fresh CUT symbol equal
to that physical cell's output. Therefore a local identity is exact
RELATIVE TO THE CUT VALUES, not a proof of full-RTL/global linearity.
A globally-affine proof has NO cut symbols. A sequential state Q is
an unconstrained input; no temporal/cross-cycle safety claim is made.

Every result MUST be independently re-evaluated by real4_verify.py.
The whole HDL -> Yosys two-state lowering is a trusted boundary.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,sys
from pathlib import Path

ALLOWED={"$_BUF_","$_NOT_","$_XOR_","$_XNOR_",
         "$_AND_","$_NAND_","$_OR_","$_NOR_","$_MUX_"}
MAX_CELLS=200000
MAX_PROBES=1536
MAX_BASIS=8192
MAX_XOR_PROBES=32

class Unsupported(Exception):pass
def fail(reason):raise Unsupported(reason)

def is_ff(kind):
    k=kind.lower()
    return ("dff" in k or "dffe" in k or k in ("$ff","$_ff_")) and "latch" not in k

def is_input(x):
    return isinstance(x,int)

def analyze(net,top):
    module=net.get("modules",{}).get(top)
    if not isinstance(module,dict):fail("TOP_MODULE_MISSING")
    ports=module.get("ports",{})
    cells=module.get("cells",{})
    if len(cells)>MAX_CELLS:fail("CELL_BUDGET")
    # Every net has at most one driver. Never silently accept a false
    # proof in a multiply driven, undriven or X/Z-dependent cone.
    drivers={}
    state=[]
    sequential=[]
    for cname,cell in sorted(cells.items()):
        kind=cell.get("type","")
        dirs=cell.get("port_directions",{})
        outs=[p for p,v in dirs.items() if v=="output"]
        if not outs and "Y" in cell.get("connections",{}):outs=["Y"]
        for port in outs:
            for position,bit in enumerate(cell["connections"].get(port,[])):
                if isinstance(bit,int):
                    if bit in drivers:fail("MULTIPLE_DRIVERS")
                    drivers[bit]=(cname,cell,port,position)
        if is_ff(kind):
            if ("Q" not in cell.get("connections",{}) or
                    "D" not in cell.get("connections",{})):
                fail("FF_WITHOUT_Q_OR_D "+kind)
            qbits=cell["connections"]["Q"]
            dbits=cell["connections"]["D"]
            if len(qbits)!=len(dbits):fail("FF_WIDTH_MISMATCH")
            for j,(qbit,dbit) in enumerate(zip(qbits,dbits)):
                if not isinstance(qbit,int):fail("FF_Q_NOT_BINARY_BIT")
                state.append({"source":"state_Q","cell":cname,"position":j,
                              "yosys_bit":qbit})
                sequential.append({"cell":cname,"position":j,"bit":dbit,
                                   "kind":"ff_next_state"})
    input_basis=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="input":
            for position,bit in enumerate(p["bits"]):
                if not isinstance(bit,int):fail("PRIMARY_INPUT_NOT_BINARY_BIT")
                input_basis.append({"source":"input","name":name,
                                    "position":position,"yosys_bit":bit})
    # Bit-level aliases are allowed only if they refer to the same declared
    # Boolean variable. Different named inputs aliased by Yosys are
    # represented once and all uses of that net bind to the same variable.
    basis=[]
    known={"0":0,"1":1}
    for declaration in input_basis+state:
        bit=declaration["yosys_bit"]
        if bit in known: continue
        if bit in drivers and declaration["source"]=="input":
            fail("PRIMARY_INPUT_HAS_DRIVER")
        d=dict(declaration)
        d["index"]=len(basis)
        known[bit]=1<<(len(basis)+1)
        basis.append(d)
    if len(basis)>MAX_BASIS:fail("BASIS_BUDGET")
    for rec in state:
        bit=rec["yosys_bit"]
        driver=drivers.get(bit)
        if driver is None or not is_ff(driver[1].get("type","")):
            fail("STATE_Q_DRIVER_IS_NOT_FF")
    cutpoints=[]
    cut_by_bit={}
    active=set()
    unknown={}
    stats=collections.Counter()
    sys.setrecursionlimit(max(sys.getrecursionlimit(),200000))

    def cut(bit,reason):
        if bit not in cut_by_bit:
            if len(basis)+len(cutpoints)>=MAX_BASIS:fail("CUT_BASIS_BUDGET")
            who=drivers[bit]
            item={"yosys_bit":bit,"cell":who[0],
                  "kind":who[1].get("type",""),
                  "output_port":who[2],"output_position":who[3],
                  "reason":reason,"index":len(basis)+len(cutpoints)}
            cut_by_bit[bit]=item
            cutpoints.append(item)
        return 1<<(cut_by_bit[bit]["index"]+1)

    def affine_and(a,b):
        if a==0 or b==0:return 0
        if a==1:return b
        if b==1:return a
        if a==b:return a
        if (a^b)==1:return 0
        raise Unsupported("NONLINEAR_AND")

    def resolve(bit):
        if bit in known:return known[bit]
        if not isinstance(bit,int) or bit in ("x","z"):
            raise Unsupported("NON_BINARY_CONSTANT")
        if bit in active:raise Unsupported("COMBINATIONAL_CYCLE")
        driver=drivers.get(bit)
        if driver is None:raise Unsupported("UNDRIVEN_NET")
        cname,cell,port,pos=driver
        kind=cell.get("type","")
        if is_ff(kind):raise Unsupported("UNMODELED_SEQUENTIAL_OUTPUT")
        if kind not in ALLOWED or port!="Y" or len(cell.get("connections",{}).get("Y",[]))!=1:
            stats["unsupported_cell_cut"]+=1
            answer=cut(bit,"UNSUPPORTED_CELL_OR_PORT")
            known[bit]=answer
            return answer
        active.add(bit)
        try:
            args={}
            for p in ("A","B","S"):
                bits=cell["connections"].get(p)
                if bits is not None:
                    if len(bits)!=1:raise Unsupported("NON_SCALAR_GATE_CONNECTION")
                    args[p]=resolve(bits[0])
            if "A" not in args:raise Unsupported("MISSING_A")
            a=args["A"]
            if kind=="$_BUF_":result=a
            elif kind=="$_NOT_":result=a^1
            else:
                if "B" not in args:raise Unsupported("MISSING_B")
                b=args["B"]
                if kind=="$_XOR_":result=a^b
                elif kind=="$_XNOR_":result=a^b^1
                elif kind in ("$_AND_","$_NAND_"):
                    try:result=affine_and(a,b)
                    except Unsupported:
                        result=cut(bit,"NONLINEAR_AND");stats["nonlinear_cut"]+=1
                    if kind=="$_NAND_" and bit not in cut_by_bit:result^=1
                elif kind in ("$_OR_","$_NOR_"):
                    try: result=affine_and(a^1,b^1)^1
                    except Unsupported:
                        result=cut(bit,"NONLINEAR_OR");stats["nonlinear_cut"]+=1
                    if kind=="$_NOR_" and bit not in cut_by_bit:result^=1
                elif kind=="$_MUX_":
                    if "S" not in args:raise Unsupported("MISSING_SELECTOR")
                    s=args["S"]
                    if s==0:result=a
                    elif s==1:result=b
                    elif a==b:result=a
                    elif a^b==1:result=a^s
                    else:
                        result=cut(bit,"NONLINEAR_MUX")
                        stats["nonlinear_cut"]+=1
                else:raise Unsupported("INTERNAL_GATE_BRANCH")
            stats["supported_gate_evaluations"]+=1
            known[bit]=result
            return result
        finally:
            active.remove(bit)

    probes=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="output":
            for i,b in enumerate(p["bits"]):
                probes.append({"kind":"primary_output","name":name,
                               "position":i,"yosys_bit":b})
    for rec in sequential:
        probes.append({"kind":"ff_next_state","name":rec["cell"],
                       "position":rec["position"],"yosys_bit":rec["bit"]})
    xor_total=0
    for cname,cell in sorted(cells.items()):
        if cell.get("type") in ("$_XOR_","$_XNOR_"):
            xor_total+=1
            if xor_total<=MAX_XOR_PROBES:
                for bit in cell.get("connections",{}).get("Y",[]):
                    probes.append({"kind":"internal_xor","name":cname,
                                   "position":0,"yosys_bit":bit})
    if len(probes)>MAX_PROBES:fail("OUTPUT_PROBE_BUDGET")
    rows=[]
    for p in probes:
        item=dict(p)
        try:
            mask=resolve(p["yosys_bit"])
            cutbits={c["index"] for c in cutpoints}
            used_cut=any(mask&(1<<(j+1)) for j in cutbits)
            item["mask_hex"]=hex(mask)
            item["status"]="LOCAL_AFFINE_WITH_CUTS" if used_cut else "GLOBAL_AFFINE_ONE_STEP"
            item["cut_indices"]=[j for j in sorted(cutbits) if mask&(1<<(j+1))]
        except Unsupported as e:
            item["status"]="UNKNOWN"
            item["reason"]=str(e)
            stats["unknown_probes"]+=1
        rows.append(item)
    global_count=sum(x["status"]=="GLOBAL_AFFINE_ONE_STEP" for x in rows if x["kind"]!="internal_xor")
    local_count=sum(x["status"]=="LOCAL_AFFINE_WITH_CUTS" for x in rows if x["kind"]!="internal_xor")
    unknown_count=sum(x["status"]=="UNKNOWN" for x in rows if x["kind"]!="internal_xor")
    return {"engine":"REAL4_AFFINE_ISLANDS_V1","top":top,
            "scope":"Yosys techmapped two-state netlist, FF Q unconstrained state; local expressions exact only when nonlinear cut outputs are treated as independent symbols",
            "basis":basis,"cutpoints":cutpoints,
            "probes":rows,"metrics":{"cells":len(cells),"input_bits":len(input_basis),
                       "state_Q_bits":len(state),"xor_gate_count":xor_total,
                       "primary_output_bits":len([x for x in rows if x["kind"]=="primary_output"]),
                       "next_state_bits":len(sequential),
                       "global_affine_external_and_state_probes":global_count,
                       "local_affine_external_and_state_probes":local_count,
                       "unknown_external_and_state_probes":unknown_count,
                       "cutpoints":len(cutpoints),**stats},
            "status":"STRUCTURE_EXTRACTED_NOT_A_FULL_CIRCUIT_SAT_VERDICT"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True,type=Path)
    p.add_argument("--top",required=True)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    try:
        raw=a.netlist.read_bytes()
        result=analyze(json.loads(raw),a.top)
        result["netlist_sha256"]=hashlib.sha256(raw).hexdigest()
    except (Unsupported,KeyError,ValueError,IndexError,RecursionError,OverflowError,MemoryError,TypeError) as e:
        result={"status":"UNKNOWN","reason":str(e),"top":a.top}
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("REAL4_STRUCTURE",a.top,result["status"],
          result.get("metrics"),flush=True)
    return 0 if result["status"]!="UNKNOWN" else 2
if __name__=="__main__":raise SystemExit(main())
