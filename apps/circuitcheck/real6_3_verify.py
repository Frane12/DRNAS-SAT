#!/usr/bin/env python3
"""Independent REAL6.3 proof replayer with separately written ITE BDD engine.

Source: original unchanged Yosys netlist, REAL6.1 stage certificate, REAL6.3
candidate paths. Rechecks original one-bit truth tables via independent REAL6.1
checker and *separately* proves each proposed multi-bit carry relation and SUM.
This checker does NOT import real6_3_bdd or trust its candidate math.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from real6_1_verify import check as verify_original_real61

PORTS={"$_AND_":("A","B"),"$_OR_":("A","B"),"$_XOR_":("A","B"),
       "$_XNOR_":("A","B"),"$_NAND_":("A","B"),"$_NOR_":("A","B"),
       "$_NOT_":("A",),"$_BUF_":("A",),"$_MUX_":("A","B","S")}

class Invalid(Exception):pass
def fail(m):raise Invalid(m)
def sh(b):return hashlib.sha256(b).hexdigest()

class IteBDD:
    """Pure Shannon decomposition, independent of detector AND/OR/XOR apply."""
    def __init__(self,src,free):
        self.src=src
        self.order={v:i for i,v in enumerate(free)}
        if len(self.order)!=len(free):fail("NONINDEPENDENT_FREE_CUT_IDS")
        self.nodes=[None,None]
        self.unique={};self.ites={};self.wires={}
        self.active=set()
        self.limit=45000
    def rank(self,n):
        return self.nodes[n][0] if n>1 else 1<<30
    def reduce(self,var,left,right):
        if left==right:return left
        key=(var,left,right)
        if key in self.unique:return self.unique[key]
        if len(self.nodes)>self.limit:fail("INDEPENDENT_BDD_SIZE_LIMIT")
        i=len(self.nodes);self.nodes.append(key);self.unique[key]=i
        return i
    def ite(self,test,yes,no):
        if test==1:return yes
        if test==0:return no
        if yes==no:return yes
        if yes==1 and no==0:return test
        key=(test,yes,no)
        if key in self.ites:return self.ites[key]
        top=min(self.rank(test),self.rank(yes),self.rank(no))
        def child(ptr,branch):
            if self.rank(ptr)==top:return self.nodes[ptr][1+branch]
            return ptr
        lo=self.ite(child(test,0),child(yes,0),child(no,0))
        hi=self.ite(child(test,1),child(yes,1),child(no,1))
        ans=self.reduce(top,lo,hi)
        self.ites[key]=ans;return ans
    def NOT(self,x):return self.ite(x,0,1)
    def AND(self,x,y):return self.ite(x,y,0)
    def OR(self,x,y):return self.ite(x,1,y)
    def XOR(self,x,y):return self.ite(x,self.NOT(y),y)
    def MAJ(self,a,b,c):return self.ite(a,self.ite(b,1,c),self.ite(b,c,0))
    def wire(self,bit):
        if bit=="0":return 0
        if bit=="1":return 1
        if bit in self.order:return self.reduce(self.order[bit],0,1)
        if bit in self.wires:return self.wires[bit]
        if bit not in self.src or bit in self.active:fail("UNBOUND_OR_CYCLIC_OR_UNSUPPORTED_GATE")
        if len(self.active)>1400:fail("GATE_DEPTH_LIMIT")
        typ,ins=self.src[bit]
        self.active.add(bit)
        try:values=[self.wire(z) for z in ins]
        finally:self.active.remove(bit)
        if typ=="$_AND_":value=self.AND(*values)
        elif typ=="$_OR_":value=self.OR(*values)
        elif typ=="$_XOR_":value=self.XOR(*values)
        elif typ=="$_XNOR_":value=self.NOT(self.XOR(*values))
        elif typ=="$_NAND_":value=self.NOT(self.AND(*values))
        elif typ=="$_NOR_":value=self.NOT(self.OR(*values))
        elif typ=="$_NOT_":value=self.NOT(values[0])
        elif typ=="$_BUF_":value=values[0]
        elif typ=="$_MUX_":value=self.ite(values[2],values[1],values[0])
        else:fail("UNSUPPORTED_OPERATOR")
        self.wires[bit]=value;return value

def graph(document,top):
    if top not in document.get("modules",{}):fail("BAD_MODULE")
    nodes={}
    for cell in document["modules"][top].get("cells",{}).values():
        t=cell["type"];co=cell.get("connections",{})
        if t not in PORTS:continue
        if any(len(co.get(p,[]))!=1 for p in (*PORTS[t],"Y")):continue
        y=co["Y"][0]
        if not isinstance(y,int):continue
        if y in nodes:fail("MULTIPLE_DRIVEN_GATE_BITS")
        nodes[y]=(t,tuple(co[p][0] for p in PORTS[t]))
    return nodes

def sum_topology(nodes):
    result=set()
    for out,(op,wires) in nodes.items():
        if op!="$_XOR_":continue
        for k in (0,1):
            prev=wires[k]
            if prev in nodes and nodes[prev][0]=="$_XOR_":
                args=nodes[prev][1]+(wires[1-k],)
                if len(set(args))==3 and all(isinstance(v,int) for v in args):
                    result.add((out,tuple(sorted(args))))
    return result

def replay_one_path(path,source,cert,top,allowed):
    if not isinstance(path,list) or not 2<=len(path)<=32:
        fail("BAD_PATH_LENGTH")
    physical=[p.get("sum_bit") for p in path]
    if len(set(physical))!=len(physical):fail("SAME_SUM_USED_TWICE")
    start=path[0]
    if (start.get("sum_bit"),tuple(sorted(start.get("inputs",[])))) not in allowed:
        fail("NOT_PHYSICAL_XOR_SUM_SEED")
    if not any(s["sum_bit"]==start["sum_bit"] and
               s["carry_bit"]==start.get("base_carry_bit") and
               s["inputs"]==start.get("inputs") for s in cert["stages"]):
        fail("UNCERTIFIED_FIRST_FULL_ADDER")
    independent=list(start["inputs"])
    if len(set(independent))!=3:fail("BAD_FIRST_CUT")
    prev=start["base_carry_bit"]
    for idx,stage in enumerate(path[1:]):
        out=stage.get("sum_bit")
        carry=stage.get("carry_input")
        operands=stage.get("operands")
        if not isinstance(operands,list) or len(operands)!=2 or len(set(operands))!=2:
            fail("NOT_TWO_NEW_OPERANDS")
        if any(x in independent for x in operands) or carry in operands:
            fail("INPUT_OVERLAP")
        if (out,tuple(sorted([carry]+operands))) not in allowed:
            fail("FALSE_GATE_SUM_TRIPLE")
        if idx==0 and carry!=prev:fail("MISSING_ORIGINAL_PHYSICAL_1ST_CARRY_LINK")
        independent.extend(operands)
    checker=IteBDD(source,independent)
    a,b,c=(checker.wire(v) for v in start["inputs"])
    carry=checker.MAJ(a,b,c)
    if checker.wire(start["sum_bit"])!=checker.XOR(checker.XOR(a,b),c):
        fail("FIRST_SUM_FALSE")
    for stage in path[1:]:
        actual=checker.wire(stage["carry_input"])
        if actual!=carry:fail("REAL6_3_HIDDEN_CARRY_FALSE")
        a,b=(checker.wire(v) for v in stage["operands"])
        sum_actual=checker.wire(stage["sum_bit"])
        if sum_actual!=checker.XOR(checker.XOR(a,b),actual):
            fail("REAL6_3_SUM_CONE_MISMATCH")
        carry=checker.MAJ(a,b,carry)
    return {"length":len(path),"bdd_nodes":len(checker.nodes),
            "verified_free_cut_count":len(independent)}

def verify(netlist,base,report_path):
    raw=Path(netlist).read_bytes()
    baseline=Path(base).read_bytes()
    doc=json.loads(raw);cert=json.loads(baseline)
    report=json.loads(Path(report_path).read_text())
    if report.get("protocol")!="DRNAS_REAL6_3_BDD_ARITHMETIC_CARRY_DISCOVERY_V1":
        fail("WRONG_PROTOCOL")
    if report.get("original_netlist_sha256")!=sh(raw) or report.get("source_real6_1_certificate_sha256")!=sh(baseline):
        fail("SOURCE_OR_PROOF_SHA_FORGED")
    if report.get("original_top")!=cert.get("top"):fail("TOP_CHANGED")
    original=verify_original_real61(netlist,base)
    if original.get("status")!="REAL6_1_INDEPENDENT_EIGHT_ROW_GATE_PROOF_PASS":
        fail("BASE_STAGE_PROOF_NOT_INDEPENDENT")
    gate=graph(doc,cert["top"])
    available=sum_topology(gate)
    paths=report.get("paths")
    if not isinstance(paths,list) or len(paths)>16:fail("REPORT_TOO_LARGE")
    samples=[]
    for path in paths:
        samples.append(replay_one_path(path,gate,cert,cert["top"],available))
    longest=max((s["length"] for s in samples),default=0)
    if report.get("metrics",{}).get("longest_proposed_sum_bits")!=longest:
        fail("FALSE_LONGEST_CHAIN_COUNT")
    return {"status":"REAL6_3_INDEPENDENT_ORIGINAL_GATE_BDD_PROOF_PASS",
            "verified_candidate_paths":len(paths),"longest_independently_verified_sum_bits":longest,
            "total_independently_verified_bdd_nodes":sum(s["bdd_nodes"] for s in samples),
            "max_free_cut_variables":max((s["verified_free_cut_count"] for s in samples),default=0),
            "scope":"Two-state Yosys gate-cut modular addition; no whole RTL temporal, cryptographic, SAT/UNSAT or performance claim"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--base-certificate",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:
        res=verify(a.netlist,a.base_certificate,a.report)
        Path(a.out).write_text(json.dumps(res,indent=2)+"\n")
        print("REAL6_3_INDEPENDENT",json.dumps(res),flush=True)
    except (Invalid,KeyError,ValueError,TypeError,RecursionError,OverflowError) as e:
        print("REAL6_3_NOT_VERIFIED",str(e),flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
