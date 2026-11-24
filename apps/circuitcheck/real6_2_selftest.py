#!/usr/bin/env python3
"""REAL6.2 proof tests: correct four-bit addition, tampered chain, bad SHA."""
import copy,hashlib,json,tempfile
from pathlib import Path
from real6_1_selftest import design,checked
from real6_2_chain import analyze
from real6_2_verify import verify,VerificationError

def main():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        good,_=design()
        base,cert=checked(root,good)
        gate=root/"netlist.json"
        derived=analyze(gate,cert)
        assert derived["metrics"]["max_candidate_chain_bits"]==4,derived["metrics"]
        report=root/"chain.json"
        report.write_text(json.dumps(derived))
        result=verify(gate,cert,report)
        assert result["max_proven_local_chain_bits"]==4,result
        assert result["checked_full_ripple_truth_rows"]>=512,result
        print("REAL6_2_GOOD_4_BIT_FULL_EXHAUSTIVE_PROOF_PASS",result,flush=True)

        forged=copy.deepcopy(derived)
        forged["chains"][0]["stage_indices"][1]=forged["chains"][0]["stage_indices"][0]
        report.write_text(json.dumps(forged))
        try:verify(gate,cert,report)
        except VerificationError:print("REAL6_2_FORGED_CHAIN_REJECTED",flush=True)
        else:raise AssertionError("FORGED_CHAIN_PASSED")

        forged=copy.deepcopy(derived)
        forged["source_netlist_sha256"]="0"*64
        report.write_text(json.dumps(forged))
        try:verify(gate,cert,report)
        except VerificationError:print("REAL6_2_FORGED_GATE_SOURCE_REJECTED",flush=True)
        else:raise AssertionError("FORGED_SOURCE_PASSED")

        broken,_=design(corrupt=2)
        base,cert=checked(root,broken)
        derived=analyze(gate,cert)
        report.write_text(json.dumps(derived))
        result=verify(gate,cert,report)
        assert result["max_proven_local_chain_bits"]<4,result
        print("REAL6_2_BAD_CARRY_BREAKS_CHAIN_PASS",result,flush=True)
        print("REAL6_2_ALL_TESTS_PASS",flush=True)

if __name__=="__main__":main()
