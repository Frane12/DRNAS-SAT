#!/usr/bin/env python3
"""DRNAS REAL5-Q: bounded exact Boolean ANF for previously unknown RTL gates.

Extension after negative REAL5 cancellation pilot. Every selected Yosys gate
bit is represented as a GF(2) polynomial of square-free monomials:
  NOT(a)=a+1; XOR=a+b; AND=ab; OR=a+b+ab;
  MUX(s,a,b)=a+s(a+b), all coefficients mod 2.
Since Boolean x^2=x, product monomials combine by bitwise OR.

Allow degree <=2 and <=96 monomials per signal, <=4096 multiply-pairs.
When expansion exceeds those caps introduce a fresh variable *at the actual
gate output*. Resulting expressions remain exact CONDITIONAL on such physical
cut signals; they are not globally quadratic if they depend on a cut.
All source-to-gate translation trusts Yosys 2-state semantics.
No assumption of generic SAT speedup or temporal correctness.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,sys
from pathlib import Path

SUPPORTED={"$_BUF_","$_NOT_","$_XOR_","$_XNOR_","$_AND_","$_NAND_",
           "$_OR_","$_NOR_","$_MUX_"}
MAX_DEGREE=2
MAX_MONOMIALS=96
MAX_PRODUCT_PAIRS=4096
MAX_BASIS=8192
MAX_CELLS=200000
MAX_PROBES=1536
MAX_INTERNAL=64

class CannotProve(Exception):pass
class ExpansionLimit(Exception):pass
def fail(s):raise CannotProve(s)
def is_ff(kind):
    t=kind.lower()
    return ("dff" in t or "dffe" in t or t in ("$ff","$_ff_")) and "latch" not in t

def plus(a,b):
    return a.symmetric_difference(b)

def product(a,b):
    if len(a)*len(b)>MAX_PRODUCT_PAIRS:
        raise ExpansionLimit("MULTIPLICATION_PRODUCT_PAIR_BUDGET")
    terms=set()
    for x in a:
        for y in b:
            combined=x|y
            if combined.bit_count()>MAX_DEGREE:
                raise ExpansionLimit("MAX_GF2_ANF_DEGREE_EXCEEDED")
            if combined in terms:terms.remove(combined)
            else:terms.add(combined)
            if len(terms)>MAX_MONOMIALS:
                raise ExpansionLimit("MONOMIAL_COUNT_EXCEEDED")
    return frozenset(terms)

def validate_poly(terms):
    if len(terms)>MAX_MONOMIALS:
        raise ExpansionLimit("MONOMIAL_COUNT_EXCEEDED")
    if any(t.bit_count()>MAX_DEGREE for t in terms):
        raise ExpansionLimit("GF2_DEGREE_EXCEEDED")
    return frozenset(terms)

def encode(terms):
    return [hex(x) for x in sorted(terms,key=lambda m:(m.bit_count(),m))]

def analyze(net,top):
    module=net.get("modules",{}).get(top)
    if not isinstance(module,dict):fail("MISSING_TOP")
    cells=module.get("cells",{})
    ports=module.get("ports",{})
    if len(cells)>MAX_CELLS:fail("GATE_CELL_LIMIT")
    drivers={}
    state=[]
    next_state=[]
    for cname,c in sorted(cells.items()):
        outputs=[p for p,d in c.get("port_directions",{}).items() if d=="output"]
        if not outputs and "Y" in c.get("connections",{}):outputs=["Y"]
        for port in outputs:
            for pos,bit in enumerate(c["connections"][port]):
                if isinstance(bit,int):
                    if bit in drivers:fail("MULTIPLE_DRIVERS")
                    drivers[bit]=(cname,c,port,pos)
        if is_ff(c.get("type","")):
            ds=c.get("connections",{}).get("D")
            qs=c.get("connections",{}).get("Q")
            if ds is None or qs is None or len(ds)!=len(qs):
                fail("NON_STANDARD_FF")
            for pos,(d,q) in enumerate(zip(ds,qs)):
                if not isinstance(q,int):fail("NON_BINARY_Q")
                state.append({"kind":"ff_Q","name":cname,"position":pos,
                              "yosys_bit":q})
                next_state.append({"kind":"ff_D","name":cname,"position":pos,
                                   "yosys_bit":d})
    inputs=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="input":
            for pos,bit in enumerate(p["bits"]):
                if not isinstance(bit,int):fail("NON_BINARY_PRIMARY_INPUT")
                inputs.append({"kind":"input","name":name,"position":pos,
                               "yosys_bit":bit})
    constants={"0":frozenset(),"1":frozenset([0])}
    memory=dict(constants)
    basis=[]
    for rec in inputs+state:
        bit=rec["yosys_bit"]
        if bit in memory:continue
        if bit in drivers and rec["kind"]=="input":fail("INPUT_IS_DRIVEN")
        if len(basis)>=MAX_BASIS:fail("TOO_MANY_INPUT_AND_FF_BITS")
        index=len(basis)
        memory[bit]=frozenset([1<<index])
        basis.append({**rec,"index":index})
    for rec in state:
        drv=drivers.get(rec["yosys_bit"])
        if drv is None or not is_ff(drv[1].get("type","")):
            fail("STATE_Q_DRIVER_UNKNOWN")
    cuts=[]
    cut_by_bit={}
    active=set()
    stats=collections.Counter()
    sys.setrecursionlimit(max(sys.getrecursionlimit(),100000))
    def cut(bit,reason):
        if bit not in cut_by_bit:
            if len(basis)+len(cuts)>=MAX_BASIS:fail("CUT_VARIABLE_LIMIT")
            cname,cell,port,pos=drivers[bit]
            info={"yosys_bit":bit,"cell":cname,"cell_type":cell.get("type",""),
                  "output_port":port,"position":pos,
                  "reason":reason,"index":len(basis)+len(cuts)}
            cut_by_bit[bit]=info
            cuts.append(info)
        return frozenset([1<<cut_by_bit[bit]["index"]])
    def resolve(bit):
        if bit in memory:return memory[bit]
        if not isinstance(bit,int):raise CannotProve("UNDEFINED_NON_BINARY_BIT")
        if bit in active:raise CannotProve("COMBINATIONAL_CYCLE")
        drv=drivers.get(bit)
        if drv is None:raise CannotProve("UNDRIVEN_BIT")
        cname,cell,port,pos=drv
        k=cell.get("type","")
        if is_ff(k):raise CannotProve("UNBOUND_SEQUENTIAL_CELL")
        if k not in SUPPORTED or port!="Y" or len(cell["connections"].get("Y",[]))!=1:
            v=cut(bit,"UNSUPPORTED_CELL")
            memory[bit]=v;stats["unsupported_gate_cuts"]+=1
            return v
        active.add(bit)
        try:
            inputs={}
            for pin in ("A","B","S"):
                if pin in cell.get("connections",{}):
                    conn=cell["connections"][pin]
                    if len(conn)!=1:raise CannotProve("GATE_NON_SCALAR_INPUT")
                    inputs[pin]=resolve(conn[0])
            if "A" not in inputs:raise CannotProve("GATE_MISSING_A")
            a=inputs["A"]
            if k=="$_BUF_":out=a
            elif k=="$_NOT_":out=plus(a,frozenset([0]))
            else:
                if "B" not in inputs:raise CannotProve("GATE_MISSING_B")
                b=inputs["B"]
                try:
                    if k=="$_XOR_":out=plus(a,b)
                    elif k=="$_XNOR_":out=plus(plus(a,b),frozenset([0]))
                    elif k in ("$_AND_","$_NAND_"):
                        out=product(a,b)
                        if k=="$_NAND_":out=plus(out,frozenset([0]))
                    elif k in ("$_OR_","$_NOR_"):
                        out=plus(plus(a,b),product(a,b))
                        if k=="$_NOR_":out=plus(out,frozenset([0]))
                    elif k=="$_MUX_":
                        if "S" not in inputs:raise CannotProve("MISSING_SELECTOR")
                        out=plus(a,product(inputs["S"],plus(a,b)))
                    else:raise CannotProve("UNSUPPORTED_OPERATION")
                    out=validate_poly(out)
                except ExpansionLimit as ex:
                    out=cut(bit,str(ex));stats["bounded_expansion_cuts"]+=1
            memory[bit]=out
            stats["evaluated_supported_gates"]+=1
            return out
        finally:active.remove(bit)
    probes=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="output":
            for pos,bit in enumerate(p["bits"]):
                probes.append({"kind":"primary_output","name":name,"position":pos,"yosys_bit":bit})
    for rec in next_state:
        probes.append({"kind":"ff_D","name":rec["name"],
                       "position":rec["position"],"yosys_bit":rec["yosys_bit"]})
    count_internal=0
    for cname,c in sorted(cells.items()):
        if (c.get("type") in ("$_XOR_","$_XNOR_","$_AND_","$_OR_")
                and count_internal<MAX_INTERNAL):
            for bit in c["connections"].get("Y",[]):
                if count_internal>=MAX_INTERNAL:break
                probes.append({"kind":"internal_probe","name":cname,"position":0,"yosys_bit":bit})
                count_internal+=1
    if len(probes)>MAX_PROBES:fail("PROBE_BUDGET")
    results=[]
    for p in probes:
        row=dict(p)
        try:
            terms=resolve(p["yosys_bit"])
            deg=max((m.bit_count() for m in terms),default=0)
            cut_indices={x["index"] for x in cuts}
            used_cut=sorted({i for m in terms for i in cut_indices if m>>i&1})
            if used_cut:
                status="LOCAL_BOUNDED_ANF_WITH_CUTS"
            else:
                status="GLOBAL_EXACT_GF2_ANF"
            row.update({"status":status,"monomials_hex":encode(terms),
                        "degree":deg,"monomial_count":len(terms),
                        "cut_indices":used_cut,
                        "higher_order_monomials":sum(m.bit_count()>=2 for m in terms),
                        "global_quadratic":not used_cut and any(m.bit_count()==2 for m in terms)})
        except CannotProve as ex:
            row.update({"status":"UNKNOWN","reason":str(ex)})
        results.append(row)
    external=[x for x in results if x["kind"]!="internal_probe"]
    return {
        "engine":"DRNAS_REAL5Q_BOUNDED_ANF_DEGREE2",
        "top":top,
        "source_boundary":"Yosys two-state techmapped logic; FF-Q unconstrained, nonlinear cuts independent",
        "limits":{"degree":MAX_DEGREE,"monomials":MAX_MONOMIALS,
                  "multiplication_pairs":MAX_PRODUCT_PAIRS,"sampled_internal":MAX_INTERNAL},
        "basis":basis,"cuts":cuts,"probes":results,
        "metrics":{
            "cells":len(cells),
            "input_basis_bits":len(basis),
            "FF_Q_bits":len(state),
            "cut_outputs":len(cuts),
            "externally_visible_or_ff_D_probes":len(external),
            "global_polynomial_probes":sum(p["status"]=="GLOBAL_EXACT_GF2_ANF" for p in external),
            "global_degree2_probes":sum(p.get("global_quadratic",False) for p in external),
            "local_polynomial_probes":sum(p["status"]=="LOCAL_BOUNDED_ANF_WITH_CUTS" for p in external),
            "unknown_probes":sum(p["status"]=="UNKNOWN" for p in external),
            "sampled_internal_global_degree2":sum(p.get("global_quadratic",False) for p in results if p["kind"]=="internal_probe"),
            "cut_gate_expansion_limit":stats["bounded_expansion_cuts"],
            "unsupported_gate_cuts":stats["unsupported_gate_cuts"]
        },
        "status":"EXACT_BOUNDED_POLYNOMIAL_CERTIFICATE_NOT_SAT_UNSAT"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True,type=Path)
    p.add_argument("--top",required=True)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    try:
        raw=a.netlist.read_bytes()
        r=analyze(json.loads(raw),a.top)
        r["netlist_sha256"]=hashlib.sha256(raw).hexdigest()
    except (CannotProve,KeyError,ValueError,TypeError,IndexError,
            RecursionError,OverflowError,MemoryError) as ex:
        r={"status":"UNKNOWN","reason":str(ex)}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("REAL5Q",a.top,r["status"],r.get("metrics"),flush=True)
    return 0 if r["status"]!="UNKNOWN" else 2
if __name__=="__main__":sys.exit(main())
