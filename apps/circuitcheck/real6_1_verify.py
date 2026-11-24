#!/usr/bin/env python3
"""REAL6.1 independent source-gate proof checker. Never imports the detector.

Every claimed SUM/CARRY pair is checked over all 2^3 free input assignments,
directly evaluating the unchanged gate JSON; each proposed carry link is
checked against exact physical gate bit equality.
"""
import argparse,hashlib,json
from pathlib import Path

GATE_PORTS={"$_AND_":("A","B"),"$_OR_":("A","B"),"$_XOR_":("A","B"),
            "$_XNOR_":("A","B"),"$_NAND_":("A","B"),"$_NOR_":("A","B"),
            "$_NOT_":("A",),"$_BUF_":("A",),"$_MUX_":("A","B","S")}

class BadProof(Exception):pass

def check(netlist,certificate):
    raw=Path(netlist).read_bytes()
    doc=json.loads(raw)
    proof=json.loads(Path(certificate).read_text())
    if proof.get("protocol")!="DRNAS_REAL6_1_LOCAL_CARRY_V1":
        raise BadProof("BAD_PROTOCOL")
    if proof.get("original_netlist_sha256")!=hashlib.sha256(raw).hexdigest():
        raise BadProof("NETLIST_SHA_MISMATCH")
    top=proof.get("top")
    if top not in doc["modules"]:raise BadProof("UNKNOWN_TOP")
    graph={}
    for cell in doc["modules"][top].get("cells",{}).values():
        op=cell["type"]
        if op not in GATE_PORTS:continue
        ports=cell.get("connections",{})
        if any(len(ports.get(p,[]))!=1 for p in (*GATE_PORTS[op],"Y")):continue
        out=ports["Y"][0]
        if not isinstance(out,int):continue
        if out in graph:raise BadProof("MULTIPLE_DRIVERS")
        graph[out]=(op,[ports[p][0] for p in GATE_PORTS[op]])
    def value(bit,env,stack):
        if bit in env:return env[bit]
        if bit=="0":return 0
        if bit=="1":return 1
        if bit not in graph or bit in stack or len(stack)>96:
            raise BadProof("CONE_OUTSIDE_3_BIT_CUT_OR_CYCLE")
        op,inp=graph[bit]
        vals=[value(b,env,stack | {bit}) for b in inp]
        if op=="$_AND_":return vals[0]&vals[1]
        if op=="$_OR_":return vals[0]|vals[1]
        if op=="$_XOR_":return vals[0]^vals[1]
        if op=="$_XNOR_":return 1^(vals[0]^vals[1])
        if op=="$_NAND_":return 1^(vals[0]&vals[1])
        if op=="$_NOR_":return 1^(vals[0]|vals[1])
        if op=="$_NOT_":return 1^vals[0]
        if op=="$_BUF_":return vals[0]
        if op=="$_MUX_":return vals[1] if vals[2] else vals[0]
        raise BadProof("UNKNOWN_GATE")
    stages=proof.get("stages")
    if not isinstance(stages,list) or len(stages)>300:raise BadProof("BAD_STAGE_COUNT")
    ids=set()
    for st in stages:
        inp=st.get("inputs")
        s=st.get("sum_bit");c=st.get("carry_bit")
        if not isinstance(inp,list) or len(inp)!=3 or any(not isinstance(x,int) for x in inp):
            raise BadProof("BAD_THREE_INPUT_CUT")
        if len(set(inp))!=3 or inp!=sorted(inp) or s==c or s not in graph or c not in graph:
            raise BadProof("INVALID_PHYSICAL_BITS")
        if st.get("scope")!="FREE_3_BIT_LOCAL_GATE_CUT" or st.get("truth_rows")!=8:
            raise BadProof("FALSE_PROOF_SCOPE")
        ident=(tuple(inp),s,c)
        if ident in ids:raise BadProof("DUPLICATE_STAGE")
        ids.add(ident)
        for assignment in range(8):
            bits=[(assignment>>k)&1 for k in range(3)]
            env=dict(zip(inp,bits))
            wanted_sum=bits[0]^bits[1]^bits[2]
            wanted_carry=int(sum(bits)>=2)
            if value(s,env,set())!=wanted_sum:
                raise BadProof("SUM_TRUTH_TABLE_INVALID")
            if value(c,env,set())!=wanted_carry:
                raise BadProof("CARRY_TRUTH_TABLE_INVALID")
    expected=sorted([i,j] for i,x in enumerate(stages) for j,y in enumerate(stages)
                    if i!=j and x["carry_bit"] in y["inputs"])
    if proof.get("links")!=expected:raise BadProof("FALSE_OR_MISSING_PHYSICAL_CARRY_LINK")
    chain=proof.get("longest_chain",[])
    if not isinstance(chain,list) or any(not isinstance(v,int) or v<0 or v>=len(stages) for v in chain):
        raise BadProof("INVALID_CHAIN_NODE")
    if len(set(chain))!=len(chain) or any([chain[i],chain[i+1]] not in expected for i in range(len(chain)-1)):
        raise BadProof("FALSE_CARRY_CHAIN")
    if proof.get("metrics",{}).get("certified_stage_pairs")!=len(stages):
        raise BadProof("FALSE_STAGE_COUNT")
    if proof.get("metrics",{}).get("longest_chain_bits")!=len(chain):
        raise BadProof("FALSE_CHAIN_COUNT")
    # Soundness of each stage is checked; completeness of detector results is NOT asserted.
    return {"status":"REAL6_1_INDEPENDENT_EIGHT_ROW_GATE_PROOF_PASS",
            "certified_local_stages":len(stages),"physical_carry_links":len(expected),
            "claimed_chain_length":len(chain),
            "limitation":"Local 3-independent-bit identities only; no complete circuit equivalence or SAT/UNSAT"}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--certificate",required=True)
    p.add_argument("--out")
    args=p.parse_args()
    try:
        result=check(args.netlist,args.certificate)
        if args.out:Path(args.out).write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result),flush=True)
    except (BadProof,ValueError,KeyError,TypeError,RecursionError) as e:
        print(json.dumps({"status":"NOT_VERIFIED","error":str(e)}),flush=True)
        raise SystemExit(2)
