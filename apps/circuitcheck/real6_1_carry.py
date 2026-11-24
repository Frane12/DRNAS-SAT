#!/usr/bin/env python3
"""REAL6.1 experimental local carry-chain detector on *unchanged* Yosys gates.

A stage is accepted only when an independent 8-row gate truth table proves
sum=a XOR b XOR cin and carry=majority(a,b,cin), treating those THREE
physical gate bits as free Boolean variables. Chain edges require the carry
physical bit of one certified stage to be an input of the next stage.
This is a LOCAL gate identity, not a complete circuit SAT/UNSAT proof.
No CDCL fallback and no source-name / benchmark-specific patterns.
"""
from __future__ import annotations
import argparse, collections, hashlib, json
from pathlib import Path

GATES={"$_AND_":("A","B"),"$_OR_":("A","B"),"$_XOR_":("A","B"),
       "$_XNOR_":("A","B"),"$_NAND_":("A","B"),"$_NOR_":("A","B"),
       "$_NOT_":("A",),"$_BUF_":("A",),"$_MUX_":("A","B","S")}
VAR_MASKS=(0xAA,0xCC,0xF0)
SUM_MASK=VAR_MASKS[0]^VAR_MASKS[1]^VAR_MASKS[2]
CARRY_MASK=((VAR_MASKS[0]&VAR_MASKS[1])|
            (VAR_MASKS[0]&VAR_MASKS[2])|
            (VAR_MASKS[1]&VAR_MASKS[2]))
MAX_SUM_ROOTS=15000
MAX_FANOUT=800
MAX_DEPTH=7
MAX_EVAL_NODES=96
MAX_STAGES=300

def gate_graph(doc,top=None):
    modules=doc["modules"]
    if top is None:
        tops=[n for n,m in modules.items() if m.get("attributes",{}).get("top") in (1,"1","00000000000000000000000000000001")]
        top=tops[0] if len(tops)==1 else (next(iter(modules)) if len(modules)==1 else None)
    if not top or top not in modules:raise ValueError("TOP_MODULE_REQUIRED")
    producer={}
    consumers=collections.defaultdict(list)
    ignored=collections.Counter()
    for name,cell in modules[top].get("cells",{}).items():
        op=cell["type"]
        if op not in GATES:
            ignored[op]+=1
            continue
        con=cell.get("connections",{})
        if any(len(con.get(p,[]))!=1 for p in (*GATES[op],"Y")):
            ignored["non_single_bit_"+op]+=1;continue
        inputs=tuple(con[p][0] for p in GATES[op])
        y=con["Y"][0]
        if not isinstance(y,int):continue
        if y in producer:raise ValueError("MULTIPLE_GATE_DRIVERS")
        producer[y]=(op,inputs)
        for x in inputs:consumers[x].append(y)
    return top,producer,consumers,dict(ignored)

def eval_local(root,leaves,prod,max_nodes=MAX_EVAL_NODES):
    """Evaluate raw gate cone exactly for ALL 8 combinations of free cut bits."""
    base={x:VAR_MASKS[i] for i,x in enumerate(leaves)}
    cache={}
    active=set()
    count=0
    def walk(bit):
        nonlocal count
        if bit in base:return base[bit]
        if bit=="0":return 0
        if bit=="1":return 255
        if bit in cache:return cache[bit]
        if bit in active or bit not in prod:raise ValueError("UNBOUND_OR_CYCLIC_CONE")
        count+=1
        if count>max_nodes:raise ValueError("CONE_BUDGET")
        active.add(bit)
        op,ins=prod[bit]
        xs=[walk(x) for x in ins]
        active.remove(bit)
        if op=="$_AND_":v=xs[0]&xs[1]
        elif op=="$_OR_":v=xs[0]|xs[1]
        elif op=="$_XOR_":v=xs[0]^xs[1]
        elif op=="$_XNOR_":v=~(xs[0]^xs[1])
        elif op=="$_NAND_":v=~(xs[0]&xs[1])
        elif op=="$_NOR_":v=~(xs[0]|xs[1])
        elif op=="$_NOT_":v=~xs[0]
        elif op=="$_BUF_":v=xs[0]
        elif op=="$_MUX_":v=(xs[0]&~xs[2])|(xs[1]&xs[2])
        else:raise ValueError("UNKNOWN_GATE")
        cache[bit]=v&255
        return cache[bit]
    return walk(root)

def sum_seeds(prod):
    """Structural XOR-of-XOR seeds, but identities are always truth checked."""
    for out,(op,ins) in sorted(prod.items()):
        if op!="$_XOR_":continue
        for ix in (0,1):
            sub=ins[ix]
            if sub not in prod or prod[sub][0]!="$_XOR_":continue
            others=prod[sub][1]+(ins[1-ix],)
            if len(set(others))==3 and all(isinstance(v,int) for v in others):
                yield out,tuple(others)

def reachable_outputs(leaves,consumers,max_depth=MAX_DEPTH,cap=MAX_FANOUT):
    queue=collections.deque((x,0) for x in leaves)
    seen=set(leaves)
    while queue:
        bit,depth=queue.popleft()
        if depth>=max_depth:continue
        for out in consumers.get(bit,()):
            if out in seen:continue
            seen.add(out)
            if len(seen)>cap:return None
            queue.append((out,depth+1))
    return seen

def detect(doc,top=None):
    top,prod,consumers,ignored=gate_graph(doc,top)
    roots=0;budgeted=0;invalid=0
    stages={}
    for sum_bit,raw in sum_seeds(prod):
        roots+=1
        if roots>MAX_SUM_ROOTS:
            budgeted+=1;break
        leaves=tuple(sorted(raw))
        try:
            if eval_local(sum_bit,leaves,prod)!=SUM_MASK:continue
        except ValueError:
            invalid+=1;continue
        near=reachable_outputs(leaves,consumers)
        if near is None:
            budgeted+=1;continue
        for carry_bit in sorted(near):
            if carry_bit==sum_bit or carry_bit not in prod:continue
            if prod[carry_bit][0] not in ("$_OR_","$_XOR_","$_MUX_","$_NOR_","$_XNOR_"):continue
            try:
                if eval_local(carry_bit,leaves,prod)!=CARRY_MASK:continue
            except ValueError:continue
            key=(leaves,sum_bit,carry_bit)
            stages[key]={"inputs":list(leaves),"sum_bit":sum_bit,
                         "carry_bit":carry_bit,"scope":"FREE_3_BIT_LOCAL_GATE_CUT",
                         "truth_rows":8}
            if len(stages)>=MAX_STAGES:
                budgeted+=1;break
        if len(stages)>=MAX_STAGES:break
    ranked=sorted(stages.values(),key=lambda s:(s["inputs"],s["sum_bit"],s["carry_bit"]))
    links=[]
    for i,s in enumerate(ranked):
        for j,t in enumerate(ranked):
            if i!=j and s["carry_bit"] in t["inputs"]:
                links.append([i,j])
    links.sort()
    edges=collections.defaultdict(list)
    for i,j in links:edges[i].append(j)
    def longest(start,path):
        if len(path)>=32:return path
        options=[j for j in edges[start] if j not in path]
        paths=[longest(j,path+[j]) for j in options]
        return max(paths,key=lambda x:(len(x),[-v for v in x]),default=path)
    chain=max((longest(i,[i]) for i in range(len(ranked))),key=len,default=[])
    status="PARTIAL_BUDGET" if budgeted else "CHECKED_DETECTOR_FINISHED"
    return {"protocol":"DRNAS_REAL6_1_LOCAL_CARRY_V1","status":status,
            "top":top,"proof_scope":"LOCAL 8-row truth tables with 3 independent gate-cut bits; no whole-core UNSAT proof",
            "stages":ranked,"links":links,"longest_chain":chain,
            "metrics":{"xor_of_xor_roots_seen":roots,"certified_stage_pairs":len(ranked),
                       "carry_links":len(links),"longest_chain_bits":len(chain),
                       "budget_exceeded":budgeted,"invalid_or_unsupported_seed":invalid,
                       "unsupported_gate_types":ignored}}

def write_report(netlist,top,out):
    b=Path(netlist).read_bytes()
    doc=json.loads(b)
    proof=detect(doc,top)
    proof["original_netlist_sha256"]=hashlib.sha256(b).hexdigest()
    Path(out).write_text(json.dumps(proof,indent=2)+"\n")
    print("REAL6_1",proof["top"],proof["status"],proof["metrics"],flush=True)

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--netlist",required=True)
    a.add_argument("--top")
    a.add_argument("--out",required=True)
    v=a.parse_args()
    write_report(v.netlist,v.top,v.out)
