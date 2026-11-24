#!/usr/bin/env python3
"""Independent proof of the complete 32-bit ORIGINAL output bus addition.

Re-read immutable original gate netlist. Verify the old REAL6.1 and REAL6.3
31-bit full-adder path with the separately implemented ITE-BDD verifier.
Then independently replay the physical XOR(a0,b0), AND(a0,b0) LSB stage and
all 31 subsequent SUM+carry equations against the source gate truth graph.

Proves 32-bit addition modulo 2^32 for 64 independent local physical cut
bits (not necessarily 64 independent original TOP PORT inputs).
No generic SAT solve or fallback; not a whole-RTL temporal proof.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from real6_3_verify import (verify as verify_prior, graph as original_graph,
                           IteBDD, Invalid)

def fail(m):raise Invalid(m)
def sha(b):return hashlib.sha256(b).hexdigest()

def verify(netlist,certfile,priorfile,proposalfile):
    raw=Path(netlist).read_bytes()
    c_raw=Path(certfile).read_bytes()
    old_raw=Path(priorfile).read_bytes()
    claim=json.loads(Path(proposalfile).read_text())
    cert=json.loads(c_raw)
    old=json.loads(old_raw)
    doc=json.loads(raw)
    if claim.get("protocol")!="DRNAS_REAL6_3_32BIT_LSB_HALF_PLUS_FULL_CHAIN_V1":
        fail("BAD_HALFADDER_PROTOCOL")
    if (claim.get("source_gate_sha256")!=sha(raw) or
        claim.get("source_real6_1_certificate_sha256")!=sha(c_raw) or
        claim.get("source_previous_independent_fulladder_report_sha256")!=sha(old_raw)):
        fail("SOURCE_OR_PRIOR_EVIDENCE_TAMPERED")
    if claim.get("top")!=cert.get("top"):fail("TOP_NOT_SAME")
    old_proof=verify_prior(netlist,certfile,priorfile)
    if old_proof["status"]!="REAL6_3_INDEPENDENT_ORIGINAL_GATE_BDD_PROOF_PASS":
        fail("PRIOR_31_BIT_PROOF_UNVERIFIED")
    module=doc["modules"][cert["top"]]
    source=original_graph(doc,cert["top"])
    proposals=claim.get("proposals")
    if not isinstance(proposals,list) or not 1<=len(proposals)<=32:
        fail("NO_OR_EXCESSIVE_SOURCE_OUTPUT_MATCHES")
    checked=[];seen=set()
    for row in proposals:
        portname=row.get("output_port_name")
        if portname not in module.get("ports",{}):fail("OUTPUT_BUS_NOT_IN_ORIGINAL")
        port=module["ports"][portname]
        bits=port.get("bits")
        if port.get("direction")!="output" or not isinstance(bits,list) or len(bits)!=32:
            fail("NO_ORIGINAL_32_BIT_OUTPUT_BUS")
        if row.get("output_port_bits")!=bits or row.get("complete_modular_sum_bits")!=32:
            fail("MISLABELED_OUTPUT_BIT_SEQUENCE")
        idx=row.get("previous_full_adder_path_index")
        if not isinstance(idx,int) or not 0<=idx<len(old["paths"]):fail("PRIOR_PATH_NOT_FOUND")
        path=old["paths"][idx]
        if len(path)!=31 or [st["sum_bit"] for st in path]!=bits[1:]:
            fail("FULL_ADDER_SUFFIX_IS_NOT_BUS_BITS_1_TO_31")
        half=row.get("lsb_half_adder")
        if not isinstance(half,dict):fail("MISSING_HALF_STAGE")
        if half.get("sum_bit")!=bits[0]:fail("HALF_SUM_NOT_LSB")
        legs=half.get("operands")
        carry_bit=half.get("carry_bit")
        if (not isinstance(legs,list) or len(legs)!=2
            or not all(isinstance(x,int) for x in legs)
            or legs!=sorted(legs) or legs[0]==legs[1]):
            fail("BAD_HALF_OPERANDS")
        root=path[0]
        if carry_bit not in root["inputs"]:fail("HALF_CARRY_NOT_IN_FIRST_FULL_ADDER")
        remain=sorted(x for x in root["inputs"] if x!=carry_bit)
        if len(remain)!=2:fail("NOT_TWO_FULL_ADDER_OPERANDS")
        if (bits[0] not in source or source[bits[0]][0]!="$_XOR_"
            or sorted(source[bits[0]][1])!=legs):
            fail("ORIGINAL_LSB_XOR_NOT_MATCHED")
        if (carry_bit not in source or source[carry_bit][0]!="$_AND_"
            or sorted(source[carry_bit][1])!=legs):
            fail("ORIGINAL_LSB_AND_NOT_MATCHED")
        if row.get("scope")!="ORIGINAL_32_OUTPUT_BITS_FREE_GATE_CUT" or row.get("full_adder_bits")!=31:
            fail("FALSE_PROOF_SCOPE")
        # Physical source gate bits used as independent cut variables;
        # the LSB AND carry is *derived*, never treated as a free bit.
        free=list(legs)+remain
        for stage in path[1:]:
            ops=stage.get("operands")
            if not isinstance(ops,list) or len(ops)!=2:fail("BAD_LATER_OPERANDS")
            free.extend(ops)
        if len(free)!=64 or len(set(free))!=64:
            fail("CUT_BITS_NOT_DISTINCT_64")
        if portname in seen:fail("DUPLICATE_PORT_CLAIM")
        seen.add(portname)
        b=IteBDD(source,free)
        a0,b0=(b.wire(x) for x in legs)
        expected_sum=b.XOR(a0,b0)
        expected_carry=b.AND(a0,b0)
        if b.wire(bits[0])!=expected_sum or b.wire(carry_bit)!=expected_carry:
            fail("LSB_HALF_ADDER_SOURCE_GATE_PROOF_FAILED")
        carry=expected_carry
        for i,stage in enumerate(path):
            if i==0:
                phys_carry=carry_bit;op=remain
            else:
                phys_carry=stage["carry_input"];op=stage["operands"]
            actual_carry=b.wire(phys_carry)
            if actual_carry!=carry:
                fail("CARRY_MISMATCH_AT_ORIGINAL_OUTPUT_BIT_"+str(i+1))
            ax,bx=(b.wire(z) for z in op)
            desired=b.XOR(b.XOR(ax,bx),carry)
            if b.wire(bits[i+1])!=desired:
                fail("SUM_MISMATCH_AT_ORIGINAL_OUTPUT_BIT_"+str(i+1))
            carry=b.MAJ(ax,bx,carry)
        checked.append({"source_output_name":portname,
                        "source_output_bits":len(bits),
                        "verified_halfadder_bits":1,
                        "verified_fulladder_bits":31,
                        "independent_local_cut_bits":len(free),
                        "BDD_nodes":len(b.nodes),
                        "result":"COMPLETE_32BIT_MODULAR_ADDITION_SOURCE_PROVED"})
    if claim.get("metrics",{}).get("32_bit_candidates")!=len(checked):
        fail("CANDIDATE_COUNT_TAMPERED")
    return {"status":"REAL6_3_SOURCE_32_BIT_INDEPENDENT_BDD_PROOF_PASS",
            "fully_verified_source_32bit_output_ports":checked,
            "total_complete_32_bit_chains":len(checked),
            "free_gate_cut_bits_per_word":64,
            "whole_RTL_temporal_correctness_claim":False,
            "whole_SAT_UNSAT_claim":False,
            "scope":"Exact combinational source gate identity for original 32-bit output bus under independent physical cut valuations"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--base-certificate",required=True)
    p.add_argument("--previous-paths",required=True)
    p.add_argument("--proposal",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:
        result=verify(a.netlist,a.base_certificate,a.previous_paths,a.proposal)
        Path(a.out).write_text(json.dumps(result,indent=2)+"\n")
        print("REAL6_3_FULL_32_INDEPENDENT",json.dumps(result),flush=True)
    except (Invalid,ValueError,KeyError,TypeError,RecursionError,OverflowError) as e:
        print("REAL6_3_FULL_32_NOT_VERIFIED",str(e),flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
