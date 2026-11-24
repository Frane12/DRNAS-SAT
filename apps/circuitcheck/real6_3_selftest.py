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
    # Original physical carry from bit 1 is OR(generate,propagate).
    # For bit 2, a DIFFERENT gate bit supplies exactly the same carry:
    # XOR(generate,propagate) == OR(generate,propagate), because terms
    # never overlap. No source-name or stage-specific detection in solver.
    g,t=112,113
    alt=5000
    cells["carry_alias_different_gate"]=wire("$_XOR_",alt,A=g,B=t)
    prior=114
    for name in ("xor_s_2","and_t_2"):
        ports=cells[name]["connections"]
        for p in ("A","B"):
            if ports[p]==[prior]:ports[p]=[alt]
    if break_alias:
        cells["carry_alias_different_gate"]=wire("$_OR_",alt,A=g,B=3)
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
