#!/usr/bin/env python3
"""REAL6.3 regression: hidden equivalent carry, 16/32-bit ripple, false proof."""
import copy,hashlib,json,tempfile
from pathlib import Path
from real6_1_selftest import design,checked,wire
from real6_3_bdd import detect
from real6_3_verify import verify,Invalid

def hidden_adder(bits,break_alias=False):
    d,_=design(bits)
    cells=d["modules"]["ripple4"]["cells"]
    # Physically RECOMPUTE bit-0 carry from first-bit inputs without
    # traversing original carry gate. Derive bit-1 carry using this
    # alternative physical wire, not the wire used by sum1. Thus the
    # original bit-1 SUM and this alternative bit-1 CARRY have different
    # three-wire boundaries and REAL6.1 cannot simply pair them.
    cells["carry0_copy_from_raw_gates"]=wire("$_XOR_",5001,A=102,B=103)
    cells["carry1_recomputed_propagate"]=wire("$_AND_",5002,A=110,B=5001)
    cells["carry1_recomputed_lookahead"]=wire("$_OR_",5000,A=112,B=5002)
    # Bit 2 consumes the equivalent carry behind a *different* physical
    # cone. A local 3-cut proof will not bridge the original bit 1->2.
    for name in ("xor_s_2","and_t_2"):
        ports=cells[name]["connections"]
        for p in ("A","B"):
            if ports[p]==[114]:ports[p]=[5000]
    if break_alias:
        cells["carry1_recomputed_lookahead"]=wire("$_XOR_",5000,A=112,B=3)
    return d

def main():
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)
        for bits in (4,8,16,32):
            net=hidden_adder(bits)
            source_cert,_=checked(folder,net)
            assert source_cert["metrics"]["longest_chain_bits"]<bits,source_cert["metrics"]
            proof=detect(folder/"netlist.json",folder/"certificate.json")
            chain=proof["metrics"]["longest_proposed_sum_bits"]
            print("REAL6_3_PROPOSED",bits,chain,proof["metrics"]["candidate_checks"],flush=True)
            assert chain>=bits,("CANNOT_RECOVER_HIDDEN_CARRY",bits,proof["metrics"])
            out=folder/"proof.json"
            out.write_text(json.dumps(proof))
            verdict=verify(folder/"netlist.json",folder/"certificate.json",out)
            assert verdict["longest_independently_verified_sum_bits"]>=bits
            print("REAL6_3_HIDDEN_CARRY_EXACT_PROOF_PASS",bits,verdict,flush=True)
        tampered=copy.deepcopy(proof)
        tampered["paths"][0][2]["carry_input"]=8888888
        out.write_text(json.dumps(tampered))
        try:verify(folder/"netlist.json",folder/"certificate.json",out)
        except (Invalid,RecursionError):
            print("REAL6_3_FORGED_HIDDEN_CARRY_REJECTED",flush=True)
        else:raise AssertionError("BAD_CARRY_CLAIM_ACCEPTED")
        tampered=copy.deepcopy(proof)
        tampered["original_netlist_sha256"]="0"*64
        out.write_text(json.dumps(tampered))
        try:verify(folder/"netlist.json",folder/"certificate.json",out)
        except Invalid:print("REAL6_3_FORGED_SOURCE_SHA_REJECTED",flush=True)
        else:raise AssertionError("BAD_SHA_CLAIM_ACCEPTED")
        print("REAL6_3_ALL_CONTROLLED_CASES_PASS",flush=True)
if __name__=="__main__":main()
