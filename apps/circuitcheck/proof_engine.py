#!/usr/bin/env python3
"""DRNAS CircuitCheck: exact algebraic normal form (ANF) over Yosys gate JSON.

Every Boolean function is represented as a polynomial over GF(2) with
idempotent variables x*x=x. A monomial is a bitset of input variable IDs;
a polynomial is a set of monomials with odd coefficients. This is exact
for supported combinational cells, not statistical testing or SAT search.
If representation explodes or a gate is unsupported, return UNKNOWN.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

MAX_PRODUCTS = 150000
MAX_TERMS = 24000
SUPPORTED = {"$_NOT_", "$_BUF_", "$_XOR_", "$_XNOR_", "$_AND_",
             "$_NAND_", "$_OR_", "$_NOR_", "$_MUX_"}

class Unsupported(Exception):
    pass

def xor(a: frozenset[int], b: frozenset[int]) -> frozenset[int]:
    r = a.symmetric_difference(b)
    if len(r) > MAX_TERMS:
        raise Unsupported("ANF term budget exceeded")
    return frozenset(r)

def mult(a: frozenset[int], b: frozenset[int]) -> frozenset[int]:
    if not a or not b: return frozenset()
    if a == frozenset({0}): return b
    if b == frozenset({0}): return a
    if len(a)*len(b) > MAX_PRODUCTS:
        raise Unsupported("ANF multiplication budget exceeded")
    s: set[int] = set()
    for x in a:
        for y in b:
            p = x | y
            if p in s: s.remove(p)
            else: s.add(p)
    if len(s) > MAX_TERMS:
        raise Unsupported("ANF term budget exceeded")
    return frozenset(s)

ONE = frozenset({0})
ZERO: frozenset[int] = frozenset()

def gate(kind: str, ins: dict[str, frozenset[int]]) -> frozenset[int]:
    a = ins.get("A", ZERO)
    b = ins.get("B", ZERO)
    if kind == "$_BUF_": return a
    if kind == "$_NOT_": return xor(a, ONE)
    if kind == "$_XOR_": return xor(a, b)
    if kind == "$_XNOR_": return xor(xor(a,b),ONE)
    if kind == "$_AND_": return mult(a, b)
    if kind == "$_NAND_": return xor(mult(a,b), ONE)
    if kind == "$_OR_": return xor(xor(a,b),mult(a,b))
    if kind == "$_NOR_": return xor(xor(xor(a,b),mult(a,b)),ONE)
    if kind == "$_MUX_": return xor(a,mult(ins["S"],xor(a,b)))
    raise Unsupported("unsupported gate "+kind)

def truth_gate(kind: str, ins: dict[str, bool]) -> bool:
    a=ins.get("A",False);b=ins.get("B",False)
    if kind=="$_BUF_":return a
    if kind=="$_NOT_":return not a
    if kind=="$_XOR_":return a^b
    if kind=="$_XNOR_":return not(a^b)
    if kind=="$_AND_":return a and b
    if kind=="$_NAND_":return not(a and b)
    if kind=="$_OR_":return a or b
    if kind=="$_NOR_":return not(a or b)
    if kind=="$_MUX_":return b if ins["S"] else a
    raise Unsupported("unsupported gate "+kind)

def analyze(doc: dict, interface: dict) -> dict:
    module = doc["modules"].get(interface["top"])
    if not isinstance(module,dict):
        raise Unsupported("selected synthesized module missing")
    ports = module["ports"]
    memo: dict[object, frozenset[int]]={"0":ZERO,"1":ONE}
    input_bits: list[dict] = []
    for name in sorted(ports):
        p=ports[name]
        if p["direction"]!="input":continue
        for offset,bit in enumerate(p["bits"]):
            if not isinstance(bit,int):
                raise Unsupported("input tied to literal or unknown")
            if bit not in memo:
                i=len(input_bits)
                memo[bit]=frozenset({1<<i})
                input_bits.append({"port":name,"position":offset,"bit_index":i,
                                   "yosys_bit":bit})
    drivers: dict[int,dict]={}
    for cell_name,cell in module["cells"].items():
        con=cell["connections"]
        outputs=[port for port,direction in cell.get("port_directions",{}).items()
                 if direction=="output"]
        if not outputs and "Y" in con: outputs=["Y"]
        for port in outputs:
            for bit in con[port]:
                if not isinstance(bit,int):continue
                if bit in drivers:
                    raise Unsupported("multiple drivers on "+str(bit))
                drivers[bit]={"name":cell_name,"cell":cell,"port":port}
    in_progress:set[int]=set()
    def resolve(bit):
        if bit in memo:return memo[bit]
        if bit in ("x","z"):raise Unsupported("undefined/high-impedance net encountered")
        if not isinstance(bit,int):raise Unsupported("unexpected bit identifier")
        if bit in in_progress:raise Unsupported("combinational cycle")
        item=drivers.get(bit)
        if item is None:raise Unsupported("undriven output net "+str(bit))
        cell=item["cell"];kind=cell["type"]
        if kind not in SUPPORTED:raise Unsupported("unsupported gate "+kind)
        if item["port"]!="Y" or len(cell["connections"].get("Y",[]))!=1:
            raise Unsupported("unsupported multi-output gate "+kind)
        in_progress.add(bit)
        try:
            arguments={port:resolve(bits[0]) for port,bits in cell["connections"].items()
                       if port in ("A","B","S") and len(bits)==1}
            if "A" not in arguments or (kind in ("$_XOR_","$_XNOR_","$_AND_",
                "$_NAND_","$_OR_","$_NOR_","$_MUX_") and "B" not in arguments):
                raise Unsupported("incomplete gate input "+kind)
            if kind=="$_MUX_" and "S" not in arguments:
                raise Unsupported("incomplete MUX selector")
            value=gate(kind,arguments)
        finally:
            in_progress.remove(bit)
        memo[bit]=value
        return value

    output_polys=[]
    unknown=[]
    difference=[]
    pairs=interface["pairs"]
    for pair in pairs:
        left=ports[pair["reference"]]["bits"]
        right=ports[pair["candidate"]]["bits"]
        if len(left)!=len(right):raise Unsupported("output width mismatch")
        for k,(a,b) in enumerate(zip(left,right)):
            try:
                l=resolve(a);r=resolve(b)
                output_polys.append({"port":pair["port"],"position":k,
                    "ref_terms":[hex(t) for t in sorted(l)],
                    "candidate_terms":[hex(t) for t in sorted(r)]})
                delta=xor(l,r)
                if delta:difference.append((pair["port"],k,delta,a,b))
            except Unsupported as ex:
                unknown.append({"port":pair["port"],"bit":k,"reason":str(ex)})
    evidence={"engine":"DRNAS-CircuitCheck-ANF-v0.1",
              "assumptions":"Yosys synthesized combinational two-state gate netlist; exact algebraic normal forms",
              "variables":input_bits,"output_polynomials":output_polys,
              "unknown":unknown,"supported_cells":sorted(SUPPORTED),
              "max_monomials":MAX_TERMS}
    if difference:
        name,k,delta,a,b=difference[0]
        minimum=min(delta,key=lambda m:(m.bit_count(),m))
        assignment={v["yosys_bit"]:bool(minimum & (1<<v["bit_index"]))
                    for v in input_bits}
        bit_cache:dict[object,bool]={"0":False,"1":True}
        bit_cache.update(assignment)
        visiting:set[int]=set()
        def eval_bit(t):
            if t in bit_cache:return bit_cache[t]
            if t in ("x","z"):raise Unsupported("undefined bit in witness")
            if t in visiting:raise Unsupported("combinational cycle in witness")
            d=drivers.get(t)
            if d is None:raise Unsupported("no gate driving witness output")
            cell=d["cell"];kind=cell["type"]
            if kind not in SUPPORTED or len(cell["connections"].get("Y",[]))!=1:
                raise Unsupported("unsupported witness driver")
            visiting.add(t)
            try:
                args={p:eval_bit(bits[0]) for p,bits in cell["connections"].items()
                      if p in ("A","B","S") and len(bits)==1}
                val=truth_gate(kind,args)
            finally:visiting.remove(t)
            bit_cache[t]=val
            return val
        if eval_bit(a)==eval_bit(b):
            raise Unsupported("symbolic witness failed independent binary evaluation")
        evidence["counterexample"]={"port":name,"output_position":k,
           "inputs":[{"port":p["port"],"position":p["position"],
                      "value":int(bool(minimum & (1<<p["bit_index"])))} for p in input_bits],
           "reference_bit":int(eval_bit(a)),"candidate_bit":int(eval_bit(b))}
        evidence["status"]="DIFFERENT_NETLIST"
    elif unknown:
        evidence["status"]="UNKNOWN_UNSUPPORTED"
    else:
        evidence["status"]="EQUIVALENT_NETLIST"
    return evidence

def check_file(netlist:Path, interface:Path, output:Path) -> dict:
    raw=netlist.read_bytes()
    evidence=analyze(json.loads(raw),json.loads(interface.read_text()))
    evidence["netlist_sha256"]=hashlib.sha256(raw).hexdigest()
    evidence["interface_sha256"]=hashlib.sha256(interface.read_bytes()).hexdigest()
    output.write_text(json.dumps(evidence,indent=2)+"\n")
    return evidence
