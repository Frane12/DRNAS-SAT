#!/usr/bin/env python3
"""Independent DELTA1 netlist-level certificate replay (does not import engine).

The checker uses a DIFFERENT affine basis layout: bits 0..n-1 are inputs,
bit n is the constant. Independently computes coefficients for every used
gate from the referenced Yosys JSON, compares the compact certificate output
masks and checks the alleged counterexample by actual gate-level evaluation.

Trusts Yosys netlist extraction, and does not assert DRAT/LRAT/VeriPB.
Exit status 0 only for CHECKED_EQUIVALENT or CHECKED_DIFFERENT.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
import sys

VALID = {"$_BUF_","$_NOT_","$_XOR_","$_XNOR_","$_AND_","$_NAND_",
         "$_OR_","$_NOR_","$_MUX_"}

class Invalid(Exception):
    pass

def verify(folder: pathlib.Path):
    netfile = folder/"netlist.json"
    interfacefile = folder/"interface.json"
    certfile = folder/"delta1_certificate.json"
    nraw, iraw = netfile.read_bytes(), interfacefile.read_bytes()
    cert = json.loads(certfile.read_text())
    if hashlib.sha256(nraw).hexdigest()!=cert["netlist_sha256"]:
        raise Invalid("NETLIST_SHA_MISMATCH")
    if hashlib.sha256(iraw).hexdigest()!=cert["interface_sha256"]:
        raise Invalid("INTERFACE_SHA_MISMATCH")
    doc=json.loads(nraw)
    interface=json.loads(iraw)
    module=doc["modules"].get(interface["top"])
    if not module:raise Invalid("TOP_MISSING")
    ports=module["ports"]
    basis=[]
    for name in sorted(ports):
        if ports[name]["direction"]=="input":
            for offset,bit in enumerate(ports[name]["bits"]):
                if not isinstance(bit,int):raise Invalid("BASIS_NOT_BOOLEAN")
                if bit not in [b[3] for b in basis]:
                    basis.append((name,offset,len(basis),bit))
    if cert["input_basis"] != [
        {"port":n,"position":p,"index":ix,"yosys_bit":bit}
        for n,p,ix,bit in basis]:
        raise Invalid("INPUT_BASIS_DIVERGENCE")
    cbit=1<<len(basis)
    # Checker representation: constant in top bit; engine constant at bit zero.
    memory:dict[object,int]={"0":0,"1":cbit}
    for _,_,ix,bit in basis:memory[bit]=1<<ix
    driven={}
    for name,cell in module.get("cells",{}).items():
        outputs=[p for p,d in cell.get("port_directions",{}).items() if d=="output"]
        if not outputs and "Y" in cell["connections"]:outputs=["Y"]
        for out in outputs:
            for net in cell["connections"][out]:
                if isinstance(net,int):
                    if net in driven:raise Invalid("MULTIPLE_DRIVERS")
                    driven[net]=(cell,out)
    running=set()

    def make_and(a,b):
        if not a or not b:return 0
        if a==cbit:return b
        if b==cbit:return a
        if a==b:return a
        if a^b==cbit:return 0
        raise Invalid("NON_AFFINE_UNSUPPORTED_AND")

    def make_gate(op,ns):
        if op not in VALID:raise Invalid("UNSUPPORTED_CELL "+op)
        if "A" not in ns:raise Invalid("MISSING_A")
        a=ns["A"]
        if op=="$_BUF_":return a
        if op=="$_NOT_":return a^cbit
        if "B" not in ns:raise Invalid("MISSING_B")
        b=ns["B"]
        if op=="$_XOR_":return a^b
        if op=="$_XNOR_":return a^b^cbit
        if op=="$_AND_":return make_and(a,b)
        if op=="$_NAND_":return make_and(a,b)^cbit
        if op=="$_OR_":return make_and(a^cbit,b^cbit)^cbit
        if op=="$_NOR_":return make_and(a^cbit,b^cbit)
        if op=="$_MUX_":
            if "S" not in ns:raise Invalid("MISSING_S")
            s=ns["S"]
            if s==0:return a
            if s==cbit:return b
            if a==b:return a
            if a^b==cbit:return a^s
            raise Invalid("NON_AFFINE_UNSUPPORTED_MUX")
        raise Invalid("UNRECOGNIZED_CELL")

    def resolve(bit):
        if bit in memory:return memory[bit]
        if bit in ("x","z") or not isinstance(bit,int):
            raise Invalid("NON_BINARY_NET")
        if bit in running:raise Invalid("COMBINATIONAL_CYCLE")
        item=driven.get(bit)
        if item is None:raise Invalid("NO_DRIVER")
        cell,y=item
        if y!="Y" or len(cell["connections"].get("Y",[]))!=1:
            raise Invalid("UNSUPPORTED_OUTPUT_WIDTH")
        running.add(bit)
        try:
            sig={}
            for p,connected in cell["connections"].items():
                if p in ("A","B","S"):
                    if len(connected)!=1:raise Invalid("MULTIBIT_GATE_INPUT")
                    sig[p]=resolve(connected[0])
            val=make_gate(cell["type"],sig)
        finally:
            running.remove(bit)
        memory[bit]=val
        return val

    def mask_as_engine(mask:int)->int:
        return (mask&((1<<len(basis))-1))<<1 | (1 if mask&cbit else 0)

    output_total=sum(len(ports[p["reference"]]["bits"]) for p in interface["pairs"])
    if cert["output_count"]!=output_total:raise Invalid("OUTPUT_COUNT_MISMATCH")
    computed=[]
    difference=None
    unknown=[]
    for pair in interface["pairs"]:
        ref=ports[pair["reference"]]["bits"]
        candidate=ports[pair["candidate"]]["bits"]
        if len(ref)!=len(candidate):raise Invalid("MISMATCHED_WIDTH")
        for offset,(ra,rb) in enumerate(zip(ref,candidate)):
            try:
                one,two=resolve(ra),resolve(rb)
            except Invalid as ex:
                unknown.append((pair["port"],offset,str(ex)))
                continue
            entry={"port":pair["port"],"position":offset,
                   "reference_mask":hex(mask_as_engine(one)),
                   "candidate_mask":hex(mask_as_engine(two)),
                   "difference_mask":hex(mask_as_engine(one^two))}
            computed.append(entry)
            if one^two:
                difference=(pair["port"],offset,ra,rb,one^two)
                break
        if difference:break

    if computed!=cert.get("checked_outputs"):
        raise Invalid("AFFINE_OUTPUT_REPLAY_MISMATCH")
    status=cert.get("status")
    if difference:
        if status!="DIFFERENT_NETLIST":raise Invalid("DIFFERENCE_WITH_FALSE_VERDICT")
        port,offset,leftbit,rightbit,delta=difference
        witness=cert.get("witness")
        if not witness or witness["output_port"]!=port or witness["position"]!=offset:
            raise Invalid("WITNESS_WRONG_OUTPUT")
        values={}
        for record in witness.get("inputs",[]):
            k=(record["port"],record["position"])
            if k in values or record["value"] not in (0,1):
                raise Invalid("WITNESS_DUPLICATE_OR_INVALID")
            values[k]=bool(record["value"])
        if set(values)!={(n,p) for n,p,_,_ in basis}:
            raise Invalid("WITNESS_INCOMPLETE")
        cinput=0
        for n,p,ix,_ in basis:
            if values[(n,p)]:cinput|=1<<ix
        if ((delta & cbit)!=0) ^ (((delta & (cbit-1)) & cinput).bit_count()&1)==0:
            raise Invalid("WITNESS_AFFINE_EQUAL")
        bitcache={"0":False,"1":True}
        bitcache.update({bit:values[(n,p)] for n,p,_,bit in basis})
        active=set()
        def truth(bit):
            if bit in bitcache:return bitcache[bit]
            if bit in ("x","z") or bit not in driven:raise Invalid("WITNESS_UNKNOWN_NET")
            if bit in active:raise Invalid("WITNESS_CYCLE")
            cell,port=driven[bit]
            if port!="Y" or cell["type"] not in VALID:raise Invalid("WITNESS_UNSUPPORTED")
            active.add(bit)
            try:
                args={p:truth(nets[0]) for p,nets in cell["connections"].items()
                      if p in ("A","B","S") and len(nets)==1}
                k=cell["type"]
                a=args.get("A",False);b=args.get("B",False)
                if k=="$_NOT_":val=not a
                elif k=="$_BUF_":val=a
                elif k=="$_AND_":val=a and b
                elif k=="$_NAND_":val=not(a and b)
                elif k=="$_OR_":val=a or b
                elif k=="$_NOR_":val=not(a or b)
                elif k=="$_XOR_":val=a^b
                elif k=="$_XNOR_":val=not(a^b)
                elif k=="$_MUX_":val=b if args["S"] else a
                else:raise Invalid("WITNESS_UNSUPPORTED_CELL")
            finally:active.remove(bit)
            bitcache[bit]=val
            return val
        a,b=truth(leftbit),truth(rightbit)
        if a==b or int(a)!=witness["reference_bit"] or int(b)!=witness["candidate_bit"]:
            raise Invalid("BIT_LEVEL_WITNESS_FAILED")
        return {"status":"CHECKED_DIFFERENT_NETLIST","input_bits":len(basis),
                "output_bit":port+":"+str(offset),"replayed_output_bits":len(computed)}
    if status!="EQUIVALENT_NETLIST" or unknown or len(computed)!=output_total:
        raise Invalid("INCOMPLETE_EQUIVALENCE_PROOF")
    if any(int(x["difference_mask"],16) for x in computed):
        raise Invalid("NONZERO_DIFFERENCE")
    return {"status":"CHECKED_EQUIVALENT_NETLIST","input_bits":len(basis),
            "replayed_output_bits":len(computed)}

def main():
    try:
        root=pathlib.Path(sys.argv[1])
        result=verify(root)
        (root/"delta1_verification.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result))
        return 0
    except (Invalid,KeyError,ValueError,IndexError,FileNotFoundError,
            RecursionError,MemoryError,TypeError) as ex:
        print(json.dumps({"status":"NOT_VERIFIED","reason":str(ex)}))
        return 2

if __name__=="__main__":sys.exit(main())
