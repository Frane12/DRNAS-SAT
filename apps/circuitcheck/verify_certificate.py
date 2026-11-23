#!/usr/bin/env python3
"""Independent replay of DRNAS CircuitCheck's *netlist-level* ANF certificate.

This file intentionally does not import proof_engine.py or circuitcheck.py.
It independently recomputes Boolean-ring polynomials from the immutable
Yosys gate JSON using a different coefficient representation (dict/set).
It validates every output polynomial and, for a negative equivalence result,
checks the counterexample both algebraically and by gate-level simulation.

Trust boundary: the upstream Yosys Verilog-to-netlist conversion is trusted.
No DRAT, LRAT, VeriPB or source-Verilog independent theorem is claimed.
"""
from __future__ import annotations
import hashlib,json,pathlib,sys

SUPPORTED={"$_NOT_","$_BUF_","$_XOR_","$_XNOR_","$_AND_","$_NAND_",
           "$_OR_","$_NOR_","$_MUX_"}
LIMIT=24000
PRODUCT_LIMIT=150000

class Invalid(Exception):pass

def add(x,y):
    r=set(x)
    for t in y:
        if t in r:r.remove(t)
        else:r.add(t)
    if len(r)>LIMIT:raise Invalid("proof replay term limit")
    return r

def prod(x,y):
    if len(x)*len(y)>PRODUCT_LIMIT:raise Invalid("replay polynomial growth")
    r=set()
    for a in x:
        for b in y:
            term=a|b
            if term in r:r.remove(term)
            else:r.add(term)
    if len(r)>LIMIT:raise Invalid("proof replay term limit")
    return r

def calc(kind,inputs):
    a=inputs.get("A",set());b=inputs.get("B",set())
    if kind=="$_BUF_":return a
    if kind=="$_NOT_":return add(a,{0})
    if kind=="$_XOR_":return add(a,b)
    if kind=="$_XNOR_":return add(add(a,b),{0})
    if kind=="$_AND_":return prod(a,b)
    if kind=="$_NAND_":return add(prod(a,b),{0})
    if kind=="$_OR_":return add(add(a,b),prod(a,b))
    if kind=="$_NOR_":return add(add(add(a,b),prod(a,b)),{0})
    if kind=="$_MUX_":return add(a,prod(inputs["S"],add(a,b)))
    raise Invalid("unsupported cell in proof: "+kind)

def bitgate(kind,p):
    a=p.get("A",False);b=p.get("B",False)
    if kind=="$_BUF_":return a
    if kind=="$_NOT_":return not a
    if kind=="$_XOR_":return a^b
    if kind=="$_XNOR_":return not(a^b)
    if kind=="$_AND_":return a and b
    if kind=="$_NAND_":return not(a and b)
    if kind=="$_OR_":return a or b
    if kind=="$_NOR_":return not(a or b)
    if kind=="$_MUX_":return b if p["S"] else a
    raise Invalid("unsupported bit-level gate")

def verify(root:pathlib.Path):
    net_bytes=(root/"netlist.json").read_bytes()
    int_bytes=(root/"interface.json").read_bytes()
    cert=json.loads((root/"certificate.json").read_text())
    if hashlib.sha256(net_bytes).hexdigest()!=cert.get("netlist_sha256"):
        raise Invalid("netlist SHA-256 mismatch")
    if hashlib.sha256(int_bytes).hexdigest()!=cert.get("interface_sha256"):
        raise Invalid("interface SHA-256 mismatch")
    net=json.loads(net_bytes);interface=json.loads(int_bytes)
    module=net["modules"][interface["top"]]
    ports=module["ports"];cells=module["cells"]
    memo:dict[object,set[int]]={"0":set(),"1":{0}}
    variables=[]
    for name in sorted(ports):
        if ports[name]["direction"]!="input":continue
        for pos,bit in enumerate(ports[name]["bits"]):
            if not isinstance(bit,int):raise Invalid("nonbinary primary input")
            if bit not in memo:
                index=len(variables)
                memo[bit]={1<<index}
                variables.append((name,pos,index,bit))
    expected_variables=[{"port":name,"position":pos,"bit_index":index,
                         "yosys_bit":bit} for name,pos,index,bit in variables]
    if cert.get("variables")!=expected_variables:
        raise Invalid("input basis or variable mapping modified")
    drivers={}
    for name,cell in cells.items():
        directions=cell.get("port_directions",{})
        output_ports=[p for p,d in directions.items() if d=="output"]
        if not output_ports and "Y" in cell["connections"]:output_ports=["Y"]
        for p in output_ports:
            for bit in cell["connections"][p]:
                if not isinstance(bit,int):continue
                if bit in drivers:raise Invalid("multiple Yosys drivers")
                drivers[bit]=(name,cell,p)
    visiting=set()
    def resolve(bit):
        if bit in memo:return memo[bit]
        if bit in ("x","z"):raise Invalid("undefined net")
        if bit in visiting:raise Invalid("combinational loop")
        if bit not in drivers:raise Invalid("undriven net")
        name,c,output=drivers[bit]
        kind=c["type"]
        if kind not in SUPPORTED or output!="Y" or len(c["connections"].get("Y",[]))!=1:
            raise Invalid("unsupported gate in signed proof: "+kind)
        visiting.add(bit)
        try:
            ins={p:resolve(v[0]) for p,v in c["connections"].items()
                 if p in ("A","B","S") and len(v)==1}
            if "A" not in ins or (kind not in ("$_BUF_","$_NOT_") and "B" not in ins):
                raise Invalid("incomplete gate inputs")
            if kind=="$_MUX_" and "S" not in ins:raise Invalid("incomplete MUX selector")
            ans=calc(kind,ins)
        finally: visiting.remove(bit)
        memo[bit]=ans
        return ans
    observed=[]
    differences=[]
    for pair in interface["pairs"]:
        left=ports[pair["reference"]]["bits"]
        right=ports[pair["candidate"]]["bits"]
        if len(left)!=len(right):raise Invalid("unmatched outputs")
        for pos,(a,b) in enumerate(zip(left,right)):
            l=resolve(a);r=resolve(b)
            observed.append({"port":pair["port"],"position":pos,
                "ref_terms":[hex(i) for i in sorted(l)],
                "candidate_terms":[hex(i) for i in sorted(r)]})
            if l!=r:differences.append((pair["port"],pos,a,b))
    if cert.get("output_polynomials")!=observed:
        raise Invalid("independent ANF replay differs from certificate")
    if cert["status"]=="EQUIVALENT_NETLIST":
        if differences or cert.get("unknown"):raise Invalid("equivalence claim unsupported")
        return {"status":"CHECKED_EQUIVALENT_NETLIST","ports_checked":len(observed),
                "netlist_sha256":cert["netlist_sha256"]}
    if cert["status"]=="DIFFERENT_NETLIST":
        witness=cert.get("counterexample")
        if not witness:raise Invalid("no counterexample")
        choice={}
        for i in witness["inputs"]:
            key=(i["port"],i["position"])
            if key in choice or i["value"] not in (0,1):raise Invalid("invalid input assignment")
            choice[key]=bool(i["value"])
        if set(choice)!={(n,p) for n,p,_,_ in variables}:
            raise Invalid("missing witness input bit")
        values={bit:choice[(n,p)] for n,p,_,bit in variables}
        values.update({"0":False,"1":True})
        busy=set()
        def eval_bit(bit):
            if bit in values:return values[bit]
            if bit in busy:raise Invalid("witness combinational loop")
            if bit not in drivers:raise Invalid("witness undriven net")
            _,c,p=drivers[bit]
            if c["type"] not in SUPPORTED or p!="Y":raise Invalid("unsupported gate in witness")
            busy.add(bit)
            try:
                inp={name:eval_bit(bits[0]) for name,bits in c["connections"].items()
                     if name in ("A","B","S") and len(bits)==1}
                result=bitgate(c["type"],inp)
            finally: busy.remove(bit)
            values[bit]=result
            return result
        pairlist=[x for x in differences if (x[0],x[1])==
                    (witness["port"],witness["output_position"])]
        if len(pairlist)!=1:raise Invalid("counterexample not for differing output")
        _,_,a,b=pairlist[0]
        av,bv=eval_bit(a),eval_bit(b)
        if av==bv or int(av)!=witness["reference_bit"] or int(bv)!=witness["candidate_bit"]:
            raise Invalid("counterexample fails concrete gate evaluation")
        return {"status":"CHECKED_DIFFERENT_NETLIST","ports_checked":len(observed),
                "counterexample":witness,"netlist_sha256":cert["netlist_sha256"]}
    raise Invalid("no proof for UNKNOWN status")

def main():
    try:
        root=pathlib.Path(sys.argv[1])
        result=verify(root)
        (root/"verification.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result,indent=2))
        return 0
    except (Invalid,KeyError,IndexError,ValueError,FileNotFoundError) as ex:
        print(json.dumps({"status":"NOT_VERIFIED","reason":str(ex)}))
        return 2

if __name__=="__main__":sys.exit(main())
