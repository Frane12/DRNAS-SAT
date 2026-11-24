#!/usr/bin/env python3
"""Independent REAL6.2 original-gate multi-bit ripple identity checker.

Replays REAL6.1 independent 8-input truth proof before any chain claim.
Then enumerates 2^(2*n+1) free assignments and evaluates original Yosys
gate equations for every chain (n<=6), proving SUM + carry arithmetically.
No HDL semantic, temporal or full-device claim. No solver fallback.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from real6_1_verify import check as verify_stage_source

PORTS={"$_AND_":("A","B"),"$_OR_":("A","B"),"$_XOR_":("A","B"),
       "$_XNOR_":("A","B"),"$_NAND_":("A","B"),"$_NOR_":("A","B"),
       "$_NOT_":("A",),"$_BUF_":("A",),"$_MUX_":("A","B","S")}

class VerificationError(Exception):pass
def fail(message):raise VerificationError(message)
def sha(b):return hashlib.sha256(b).hexdigest()

def graph_from_source(doc,top):
    if top not in doc["modules"]:fail("MISSING_SOURCE_TOP")
    producer={}
    for c in doc["modules"][top].get("cells",{}).values():
        op=c["type"]
        if op not in PORTS:continue
        co=c.get("connections",{})
        if any(len(co.get(p,[]))!=1 for p in (*PORTS[op],"Y")):continue
        y=co["Y"][0]
        if not isinstance(y,int):continue
        if y in producer:fail("MULTIDRIVER")
        producer[y]=(op,tuple(co[p][0] for p in PORTS[op]))
    return producer

def evaluate(bit,known,producer,cache,active):
    if bit in known:return known[bit]
    if bit=="0":return 0
    if bit=="1":return 1
    if bit in cache:return cache[bit]
    if bit not in producer or bit in active or len(active)>2500:
        fail("UNPROVEN_UPSTREAM_SIGNAL_OR_CYCLE")
    op,src=producer[bit]
    active.add(bit)
    v=[evaluate(x,known,producer,cache,active) for x in src]
    active.remove(bit)
    if op=="$_AND_":out=v[0]&v[1]
    elif op=="$_OR_":out=v[0]|v[1]
    elif op=="$_XOR_":out=v[0]^v[1]
    elif op=="$_XNOR_":out=1^(v[0]^v[1])
    elif op=="$_NAND_":out=1^(v[0]&v[1])
    elif op=="$_NOR_":out=1^(v[0]|v[1])
    elif op=="$_NOT_":out=1^v[0]
    elif op=="$_BUF_":out=v[0]
    elif op=="$_MUX_":out=v[1] if v[2] else v[0]
    else:fail("UNSUPPORTED_GATE")
    cache[bit]=out
    return out

def verify(netlist,certificate,chain_report):
    raw=Path(netlist).read_bytes()
    base_raw=Path(certificate).read_bytes()
    report=json.loads(Path(chain_report).read_text())
    cert=json.loads(base_raw)
    if report.get("protocol")!="DRNAS_REAL6_2_PHYSICAL_CHAIN_AUDIT_V1":
        fail("WRONG_REAL6_2_PROTOCOL")
    if report.get("source_netlist_sha256")!=sha(raw):
        fail("FORGED_SOURCE_GATE_SHA")
    if report.get("source_real6_1_certificate_sha256")!=sha(base_raw):
        fail("FORGED_PREVIOUS_PROOF_SHA")
    independently=verify_stage_source(netlist,certificate)
    if independently.get("status")!="REAL6_1_INDEPENDENT_EIGHT_ROW_GATE_PROOF_PASS":
        fail("BASE_EIGHT_ROW_PROOF_FAILED")
    if report.get("stages")!=cert.get("stages"):fail("STAGE_DATA_CHANGED")
    stages=cert["stages"]
    graph=graph_from_source(json.loads(raw),cert["top"])
    chains=report.get("chains")
    if not isinstance(chains,list) or len(chains)>200:fail("BAD_CHAINS")
    if report.get("metrics",{}).get("base_stage_pairs")!=len(stages):
        fail("BAD_STAGE_COUNT")
    if report["metrics"].get("candidate_connected_chains")!=len(chains):
        fail("BAD_CHAIN_COUNT")
    checked=0;rows=0;maximum=0
    for chain in chains:
        ids=chain.get("stage_indices")
        if (not isinstance(ids,list) or not 2<=len(ids)<=6
            or any(not isinstance(k,int) or k<0 or k>=len(stages) for k in ids)
            or len(set(ids))!=len(ids)):fail("CHAIN_INDICES_INVALID")
        if chain.get("length_bits")!=len(ids) or chain.get("scope")!="LOCAL_CONNECTED_GATE_CUT":
            fail("CHAIN_SCOPE_OR_LENGTH_WRONG")
        first=stages[ids[0]]
        cin=min(first["inputs"])
        if chain.get("first_carry_bit")!=cin:fail("FIRST_CARRY_NOT_CANONICAL")
        operands=[sorted(x for x in first["inputs"] if x!=cin)]
        cut_inputs=[cin]+operands[0]
        seen=set(cut_inputs)
        prior_carry=first["carry_bit"]
        prior_outputs={first["sum_bit"],first["carry_bit"]}
        for stage_id in ids[1:]:
            s=stages[stage_id]
            if prior_carry not in s["inputs"]:fail("NOT_PHYSICALLY_LINKED_CARRY")
            other=sorted(x for x in s["inputs"] if x!=prior_carry)
            if (len(other)!=2 or any(v in seen or v in prior_outputs for v in other)
                or s["sum_bit"] in seen or s["carry_bit"] in seen
                or s["sum_bit"] in prior_outputs or s["carry_bit"] in prior_outputs):
                fail("OVERLAPPING_FREE_OPERANDS_OR_OUTPUTS")
            operands.append(other)
            cut_inputs.extend(other)
            seen.update(other)
            prior_outputs.update((s["sum_bit"],s["carry_bit"]))
            prior_carry=s["carry_bit"]
        n=len(ids)
        maximum=max(maximum,n)
        for assignment in range(1<<(2*n+1)):
            env={bit:(assignment>>j)&1 for j,bit in enumerate(cut_inputs)}
            a=sum(env[p[0]]<<k for k,p in enumerate(operands))
            b=sum(env[p[1]]<<k for k,p in enumerate(operands))
            observed=0;cache={}
            for k,stage_id in enumerate(ids):
                stage=stages[stage_id]
                observed+=evaluate(stage["sum_bit"],env,graph,cache,set())<<k
            last=stages[ids[-1]]["carry_bit"]
            observed+=evaluate(last,env,graph,cache,set())<<n
            expected=a+b+env[cin]
            if observed!=expected:
                fail("RIPPLE_ADDITION_TRUTH_TABLE_FAILED_chain_%s_row_%d"%(ids,assignment))
            rows+=1
        checked+=1
    if report["metrics"].get("max_candidate_chain_bits")!=maximum:
        fail("FALSE_LONGEST_CHAIN")
    return {"status":"REAL6_2_INDEPENDENT_SOURCE_GATE_CHAIN_PROOF_PASS",
            "verified_chains":checked,"checked_full_ripple_truth_rows":rows,
            "max_proven_local_chain_bits":maximum,
            "source_only":True,
            "limitation":"2-state Yosys combinational local gate-cut chains; not whole RTL circuit, SAT/UNSAT or clock invariant"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--certificate",required=True)
    p.add_argument("--chain-report",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:
        result=verify(a.netlist,a.certificate,a.chain_report)
        Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
        print("REAL6_2_VERIFIED",json.dumps(result),flush=True)
    except (VerificationError,ValueError,TypeError,KeyError,IndexError,RecursionError,OverflowError) as e:
        print("REAL6_2_NOT_VERIFIED",str(e),flush=True)
        raise SystemExit(2)

if __name__=="__main__":main()
