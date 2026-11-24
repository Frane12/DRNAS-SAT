#!/usr/bin/env python3
"""Independent REAL5-Q certificate checker using sets of set-valued monomials.

No import from real5q_anf. Replays the original Yosys techmapped network
from scratch using a mathematically different representation:
monomial = frozenset(variable indices), polynomial = frozenset(monomials).
GF2 multiplication = symmetric-difference convolution with set union
(idempotence x^2=x). Every emitted coefficient and nonlinear cut is checked
against the claimed gate-netlist SHA. No source-level, temporal, or original
CNF DRAT/LRAT proof.
"""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path

ACCEPTED={"$_BUF_","$_NOT_","$_XOR_","$_XNOR_",
          "$_AND_","$_NAND_","$_OR_","$_NOR_","$_MUX_"}
CONST0=frozenset()
CONST1=frozenset([frozenset()])
MAX_BASIS=8192
MAX_DEGREE=2
MAX_TERMS=96
MAX_PAIRS=4096
class Invalid(Exception):pass
class TooLarge(Exception):pass
def fail(s):raise Invalid(s)
def ff(kind):
    t=kind.lower()
    return ("dff" in t or "dffe" in t or t in ("$ff","$_ff_")) and "latch" not in t

def add(a,b):return a.symmetric_difference(b)
def multiply(a,b):
    if len(a)*len(b)>MAX_PAIRS:raise TooLarge("MULTIPLICATION_PRODUCT_PAIR_BUDGET")
    result=set()
    for x in a:
        for y in b:
            z=x.union(y)
            if len(z)>MAX_DEGREE:raise TooLarge("MAX_GF2_ANF_DEGREE_EXCEEDED")
            if z in result:result.remove(z)
            else:result.add(z)
            if len(result)>MAX_TERMS:raise TooLarge("MONOMIAL_COUNT_EXCEEDED")
    return frozenset(result)
def bound(x):
    if len(x)>MAX_TERMS:raise TooLarge("MONOMIAL_COUNT_EXCEEDED")
    if any(len(m)>MAX_DEGREE for m in x):raise TooLarge("GF2_DEGREE_EXCEEDED")
    return x
def encode(poly):
    integers=[sum(1<<bit for bit in m) for m in poly]
    return [hex(x) for x in sorted(integers,key=lambda x:(x.bit_count(),x))]

def check(folder:Path):
    netfile=folder/"netlist.json"
    certfile=folder/"real5q_certificate.json"
    doc=json.loads(netfile.read_text())
    claim=json.loads(certfile.read_text())
    if hashlib.sha256(netfile.read_bytes()).hexdigest()!=claim.get("netlist_sha256"):
        fail("ORIGINAL_NETLIST_SHA_MISMATCH")
    module=doc.get("modules",{}).get(claim["top"])
    if not isinstance(module,dict):fail("TOP_MISSING")
    cells=module.get("cells",{})
    ports=module.get("ports",{})
    if len(cells)>200000:fail("TOO_MANY_CELLS")
    drivers={}
    state=[]
    dbits=[]
    for name,cell in sorted(cells.items()):
        outs=[p for p,d in cell.get("port_directions",{}).items() if d=="output"]
        if not outs and "Y" in cell.get("connections",{}):outs=["Y"]
        for p in outs:
            for i,bit in enumerate(cell["connections"][p]):
                if isinstance(bit,int):
                    if bit in drivers:fail("MULTIPLE_DRIVERS")
                    drivers[bit]=(name,cell,p,i)
        if ff(cell.get("type","")):
            d=cell.get("connections",{}).get("D")
            q=cell.get("connections",{}).get("Q")
            if d is None or q is None or len(d)!=len(q):
                fail("BAD_FF_PINOUT")
            for i,(dd,qq) in enumerate(zip(d,q)):
                if not isinstance(qq,int):fail("BAD_FF_Q")
                state.append({"kind":"ff_Q","name":name,"position":i,"yosys_bit":qq})
                dbits.append({"kind":"ff_D","name":name,"position":i,"yosys_bit":dd})
    input_bits=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="input":
            for i,b in enumerate(p["bits"]):
                if not isinstance(b,int):fail("NON_BINARY_INPUT")
                input_bits.append({"kind":"input","name":name,"position":i,"yosys_bit":b})
    basis=[]
    mem={"0":CONST0,"1":CONST1}
    for p in input_bits+state:
        bit=p["yosys_bit"]
        if bit in mem:continue
        if p["kind"]=="input" and bit in drivers:fail("INPUT_ALREADY_HAS_DRIVER")
        index=len(basis)
        if index>=MAX_BASIS:fail("BASIS_OVERFLOW")
        mem[bit]=frozenset([frozenset([index])])
        basis.append({**p,"index":index})
    if claim.get("basis")!=basis:fail("SYMBOLIC_INPUT_BASIS_MISMATCH")
    for record in state:
        node=drivers.get(record["yosys_bit"])
        if node is None or not ff(node[1].get("type","")):
            fail("FALSE_SEQUENTIAL_Q")
    cuts=[]
    cut_map={}
    visiting=set()
    sys.setrecursionlimit(max(sys.getrecursionlimit(),100000))
    def new_cut(bit,why):
        if bit not in cut_map:
            if len(basis)+len(cuts)>=MAX_BASIS:fail("TOO_MANY_CUT_SYMBOLS")
            name,cell,p,i=drivers[bit]
            record={"yosys_bit":bit,"cell":name,
                    "cell_type":cell.get("type",""),
                    "output_port":p,"position":i,"reason":why,
                    "index":len(basis)+len(cuts)}
            cuts.append(record);cut_map[bit]=record
        return frozenset([frozenset([cut_map[bit]["index"]])])
    def evaluate(bit):
        if bit in mem:return mem[bit]
        if not isinstance(bit,int):fail("UNKNOWN_CONSTANT_XZ")
        if bit in visiting:fail("COMBINATIONAL_CYCLE")
        row=drivers.get(bit)
        if row is None:fail("UNDRIVEN_WIRE")
        name,c,port,j=row
        typ=c.get("type","")
        if ff(typ):fail("UNBOUND_FF_OUTPUT")
        if typ not in ACCEPTED or port!="Y" or len(c["connections"].get("Y",[]))!=1:
            val=new_cut(bit,"UNSUPPORTED_CELL")
            mem[bit]=val
            return val
        visiting.add(bit)
        try:
            args={}
            for p in ("A","B","S"):
                if p in c.get("connections",{}):
                    arr=c["connections"][p]
                    if len(arr)!=1:fail("NOT_SINGLE_BIT_GATE")
                    args[p]=evaluate(arr[0])
            if "A" not in args:fail("GATE_A_MISSING")
            a=args["A"]
            if typ=="$_BUF_":out=a
            elif typ=="$_NOT_":out=add(a,CONST1)
            else:
                if "B" not in args:fail("GATE_B_MISSING")
                b=args["B"]
                try:
                    if typ=="$_XOR_":out=add(a,b)
                    elif typ=="$_XNOR_":out=add(add(a,b),CONST1)
                    elif typ in ("$_AND_","$_NAND_"):
                        out=multiply(a,b)
                        if typ=="$_NAND_":out=add(out,CONST1)
                    elif typ in ("$_OR_","$_NOR_"):
                        out=add(add(a,b),multiply(a,b))
                        if typ=="$_NOR_":out=add(out,CONST1)
                    elif typ=="$_MUX_":
                        if "S" not in args:fail("MUX_SELECTOR_MISSING")
                        out=add(a,multiply(args["S"],add(a,b)))
                    else:fail("UNKNOWN_GATE_KIND")
                    out=bound(out)
                except TooLarge as ex:out=new_cut(bit,str(ex))
            mem[bit]=out
            return out
        finally:visiting.remove(bit)
    probes=[]
    for name,p in sorted(ports.items()):
        if p["direction"]=="output":
            for j,b in enumerate(p["bits"]):
                probes.append({"kind":"primary_output","name":name,"position":j,"yosys_bit":b})
    probes.extend(dbits)
    internals=0
    for name,cell in sorted(cells.items()):
        if cell.get("type") in ("$_XOR_","$_XNOR_","$_AND_","$_OR_"):
            if internals>=64:break
            for bit in cell["connections"].get("Y",[]):
                if internals>=64:break
                probes.append({"kind":"internal_probe","name":name,"position":0,"yosys_bit":bit})
                internals+=1
    if len(probes)>1536:fail("TOO_MANY_PROBES")
    candidate=claim.get("probes")
    if not isinstance(candidate,list) or len(candidate)!=len(probes):
        fail("PROBES_INCOMPLETE")
    outcome={}
    for i,p in enumerate(probes):
        want=candidate[i]
        if any(want.get(k)!=v for k,v in p.items()):
            fail("PROBE_POSITION_CHANGED")
        try:
            polynomial=evaluate(p["yosys_bit"])
        except Invalid as e:
            if want.get("status")!="UNKNOWN":
                fail("UNKNOWN_HIDDEN_BY_FORMAL_CLAIM")
            continue
        degree=max((len(m) for m in polynomial),default=0)
        cuts_used=sorted({j for m in polynomial for j in m if j>=len(basis)})
        status="LOCAL_BOUNDED_ANF_WITH_CUTS" if cuts_used else "GLOBAL_EXACT_GF2_ANF"
        expected={
            "status":status,"monomials_hex":encode(polynomial),
            "degree":degree,"monomial_count":len(polynomial),
            "cut_indices":cuts_used,
            "higher_order_monomials":sum(len(m)>=2 for m in polynomial),
            "global_quadratic":not cuts_used and any(len(m)==2 for m in polynomial)
        }
        if any(want.get(k)!=v for k,v in expected.items()):
            fail("MONOMIAL_PROOF_NOT_REPLAYED "+str(i))
        outcome[status]=outcome.get(status,0)+1
    if claim.get("cuts")!=cuts:fail("NONLINEAR_CUT_BOUNDARY_CHANGED")
    if claim.get("status")!="EXACT_BOUNDED_POLYNOMIAL_CERTIFICATE_NOT_SAT_UNSAT":
        fail("INCORRECT_PROOF_SCOPE")
    if claim.get("limits")!={"degree":2,"monomials":96,
                             "multiplication_pairs":4096,"sampled_internal":64}:
        fail("ALGORITHM_BOUNDARIES_MISREPORTED")
    return {"status":"CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS",
            "replayed_probes":len(probes),"cuts_replayed":len(cuts),
            "global_probes_replayed":outcome.get("GLOBAL_EXACT_GF2_ANF",0),
            "local_probes_replayed":outcome.get("LOCAL_BOUNDED_ANF_WITH_CUTS",0),
            "scope":"2-state gate ANF relations, no whole circuit temporal/SAT proof"}

def main():
    folder=Path(sys.argv[1])
    try:
        v=check(folder)
        (folder/"real5q_verification.json").write_text(json.dumps(v,indent=2)+"\n")
        print("REAL5Q_INDEPENDENT_VERIFIER_PASS",v["replayed_probes"],flush=True)
        return 0
    except (Invalid,ValueError,TypeError,KeyError,IndexError,
            FileNotFoundError,MemoryError,OverflowError,RecursionError) as e:
        print(json.dumps({"status":"NOT_VERIFIED","reason":str(e)}))
        return 2
if __name__=="__main__":sys.exit(main())
