#!/usr/bin/env python3
"""REAL5-Q external gate-cone polynomial equivalence miter generator.

Read REAL5Q independently verified certificate for ORIGINAL frozen Yosys
gate network. For up to three selected quadratic outputs (prefer external
probes with >=2 nonlinear quadratic monomials), reconstruct their ACTUAL
gate-level logic and compare to the exact GF(2) polynomial expression.
Unsupported gates are free cut terminals, exactly as certified.

Both Kissat and CaDiCaL must receive the SAME generated DIMACS, NOT a
hand-constructed SAT problem unrelated to these original gate outputs.
UNSAT miter proves an exact *local* relation, not a full original RTL
specification, temporal property, or standard proof certification.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from real5q_verify import check

VALID={"$_BUF_","$_NOT_","$_XOR_","$_XNOR_",
       "$_AND_","$_NAND_","$_OR_","$_NOR_","$_MUX_"}
MAX_GATES=20000
MAX_INPUT_BITS=1024
class Unsupported(Exception):pass

def fail(s):raise Unsupported(s)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def choices(cert,max_samples=3):
    rows=[]
    for p in cert["probes"]:
        if p.get("status") not in ("GLOBAL_EXACT_GF2_ANF","LOCAL_BOUNDED_ANF_WITH_CUTS"):
            continue
        if p.get("degree")!=2 or p.get("higher_order_monomials",0)<1:continue
        rows.append(p)
    # First demonstrate nontrivial complete quadratic outputs; fallback
    # cases are explicitly labeled rather than misreported as novel.
    rows.sort(key=lambda p:(
        p["kind"]=="internal_probe",
        p.get("status")!="GLOBAL_EXACT_GF2_ANF",
        -int(p.get("higher_order_monomials",0)>=2),
        -p.get("higher_order_monomials",0),
        p["name"],p["position"]
    ))
    chosen=[]
    bits=set()
    for p in rows:
        if p["yosys_bit"] in bits:continue
        chosen.append(p)
        bits.add(p["yosys_bit"])
        if len(chosen)>=max_samples:break
    return chosen

def create(net,cert,probe):
    mod=net["modules"][cert["top"]]
    cells=mod.get("cells",{})
    basis={x["yosys_bit"]:x["index"] for x in cert["basis"]}
    cuts={x["yosys_bit"]:x["index"] for x in cert["cuts"]}
    drivers={}
    for cname,cell in sorted(cells.items()):
        outs=[p for p,v in cell.get("port_directions",{}).items() if v=="output"]
        if not outs and "Y" in cell.get("connections",{}):outs=["Y"]
        for port in outs:
            for bit in cell["connections"][port]:
                if isinstance(bit,int):
                    if bit in drivers:fail("MULTIPLE_DRIVERS")
                    drivers[bit]=(cell,port)
    used=set()
    exprs=[]
    visiting=set()
    completed=set()
    def reference(bit):
        if bit=="0":return "1'b0"
        if bit=="1":return "1'b1"
        if not isinstance(bit,int):fail("X_OR_Z_IN_CANDIDATE")
        if bit in basis or bit in cuts:
            idx=basis[bit] if bit in basis else cuts[bit]
            used.add(idx)
            return "t_"+str(idx)
        if bit in visiting:fail("COMBINATIONAL_CYCLE")
        if bit in completed:return "g_"+str(bit)
        if len(exprs)>=MAX_GATES:fail("GATE_CONE_TOO_LARGE")
        item=drivers.get(bit)
        if item is None:fail("UNDRIVEN_GATE")
        cell,port=item
        kind=cell["type"]
        if kind not in VALID or port!="Y" or len(cell["connections"].get("Y",[]))!=1:
            fail("UNPROVEN_GATE_NOT_CUT")
        visiting.add(bit)
        try:
            pins={}
            for p in ("A","B","S"):
                x=cell["connections"].get(p)
                if x is not None:
                    if len(x)!=1:fail("NONSCALAR_GATE_PIN")
                    pins[p]=reference(x[0])
            a=pins.get("A");b=pins.get("B")
            if a is None:fail("MISSING_GATE_A")
            if kind=="$_BUF_":value=a
            elif kind=="$_NOT_":value=f"~({a})"
            elif b is None:fail("MISSING_GATE_B")
            elif kind=="$_XOR_":value=f"({a}) ^ ({b})"
            elif kind=="$_XNOR_":value=f"~(({a}) ^ ({b}))"
            elif kind=="$_AND_":value=f"({a}) & ({b})"
            elif kind=="$_NAND_":value=f"~(({a}) & ({b}))"
            elif kind=="$_OR_":value=f"({a}) | ({b})"
            elif kind=="$_NOR_":value=f"~(({a}) | ({b}))"
            elif kind=="$_MUX_":
                if "S" not in pins:fail("MISSING_MUX_S")
                value=f"({pins['S']}) ? ({b}) : ({a})"
            else:fail("UNSUPPORTED_GATE")
            exprs.append((bit,value))
            completed.add(bit)
            return "g_"+str(bit)
        finally:visiting.remove(bit)
    actual=reference(probe["yosys_bit"])
    monomials=[int(x,16) for x in probe["monomials_hex"]]
    pieces=[]
    for monomial in monomials:
        if monomial==0:pieces.append("1'b1");continue
        factors=[]
        m=monomial
        while m:
            lowest=m&-m
            index=lowest.bit_length()-1
            factors.append("t_"+str(index))
            used.add(index)
            m-=lowest
        if len(factors)>2:fail("MONOMIAL_DEGREE_OVERFLOW")
        pieces.append("("+" & ".join(factors)+")")
    model=" ^ ".join(pieces) if pieces else "1'b0"
    numbers=sorted(used)
    if not numbers:numbers=[0]
    if len(numbers)>MAX_INPUT_BITS:fail("TOO_MANY_LOCAL_CONE_INPUTS")
    lines=[f"module miter(input wire [{len(numbers)-1}:0] variables, output wire mismatch);"]
    for k,n in enumerate(numbers):
        lines.append(f" wire t_{n} = variables[{k}];")
    for bit,value in exprs:
        lines.append(f" wire g_{bit} = ({value});")
    lines+= [f" wire gate_value = ({actual});",
             f" wire polynomial_value = ({model});",
             " assign mismatch = gate_value ^ polynomial_value;",
             "endmodule"]
    return "\n".join(lines)+"\n",{
        "kind":probe["kind"],"name":probe["name"],
        "yosys_bit":probe["yosys_bit"],"position":probe["position"],
        "certified_status":probe["status"],
        "quadratic_monomial_count":probe["higher_order_monomials"],
        "monomial_count":len(monomials),
        "gate_cone_size":len(exprs),
        "terminal_variables":len(numbers),
        "cut_dependencies":probe.get("cut_indices",[]),
        "scope":"one physical Yosys gate-cone bit equality to its exact degree2 GF2 polynomial; cut outputs free"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    checked=check(args.folder)
    if checked["status"]!="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS":
        raise RuntimeError("CANDIDATE_GF2_POLYNOMIAL_NOT_PROVED")
    net=json.loads((args.folder/"netlist.json").read_text())
    cert=json.loads((args.folder/"real5q_certificate.json").read_text())
    args.out.mkdir(parents=True,exist_ok=True)
    result=[]
    for i,p in enumerate(choices(cert)):
        item={"id":"candidate_"+str(i)}
        dest=args.out/item["id"]
        dest.mkdir(parents=True,exist_ok=True)
        try:
            raw,metadata=create(net,cert,p)
            file=dest/"miter.v"
            file.write_text(raw)
            item.update({"status":"GENERATED","miter_sha256":sha(file),**metadata})
        except Unsupported as e:
            item.update({"status":"UNKNOWN","reason":str(e)})
        result.append(item)
    (args.out/"candidate_manifest.json").write_text(json.dumps(result,indent=2)+"\n")
    print("REAL5Q_ORIGINAL_GATE_CONES_SELECTED",len(result),
          [x["status"] for x in result],flush=True)
if __name__=="__main__":main()
