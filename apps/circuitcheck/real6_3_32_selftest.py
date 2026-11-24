#!/usr/bin/env python3
"""Controlled REAL6.3/32 regression on 4,8,16,32-bit hidden carry adder.

The physical carry alias is recomputed by different gates. REAL6.1 is
required to fall short, but new indexed BDD plus independent ITE verifier
must recover and prove the whole chain. Forged paths must be rejected.
"""
from __future__ import annotations
import copy,json,tempfile
from pathlib import Path
from real6_3_selftest import hidden_adder
from real6_1_selftest import checked
from real6_3_32_indexed import search
from real6_3_verify import verify,Invalid

def main():
    with tempfile.TemporaryDirectory() as td:
        folder=Path(td)
        for bits in (4,8,16,32):
            net=hidden_adder(bits)
            base,_=checked(folder,net)
            old=base["metrics"]["longest_chain_bits"]
            assert old<bits,("NO_BLIND_SPOT",bits,base["metrics"])
            source=folder/"netlist.json"
            proof=folder/"certificate.json"
            new=search(source,proof,target_bits=bits)
            found=new["metrics"]["longest_proposed_sum_bits"]
            if found<bits:
                print("REAL6_3_32_UNKNOWN_CONTROL",bits,new["metrics"],flush=True)
                raise AssertionError("TARGET_NOT_RECOGNIZED")
            report=folder/"new.json"
            report.write_text(json.dumps(new))
            verdict=verify(source,proof,report)
            assert verdict["longest_independently_verified_sum_bits"]==bits,verdict
            print("REAL6_3_32_CONTROL_PASS",bits,"old",old,"new",found,
                  "independent",verdict["longest_independently_verified_sum_bits"],flush=True)
        attack=copy.deepcopy(new)
        attack["paths"][0][-1]["carry_input"]=9999999
        report.write_text(json.dumps(attack))
        try:verify(source,proof,report)
        except (Invalid,RecursionError):
            print("REAL6_3_32_TAMPER_WRONG_CARRY_REJECTED",flush=True)
        else:raise AssertionError("FORGED_CARRY_ACCEPTED")
        attack=copy.deepcopy(new)
        attack["original_netlist_sha256"]="0"*64
        report.write_text(json.dumps(attack))
        try:verify(source,proof,report)
        except Invalid:print("REAL6_3_32_TAMPER_SOURCE_REJECTED",flush=True)
        else:raise AssertionError("FORGED_SOURCE_ACCEPTED")
        print("REAL6_3_32_ALL_CONTROLLED_PASS",flush=True)
if __name__=="__main__":main()
