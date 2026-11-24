#!/usr/bin/env python3
"""Self-contained 4-bit ripple carry, wrong-carry, and forged-proof tests."""
import copy,hashlib,json,tempfile
from pathlib import Path
from real6_1_carry import detect
from real6_1_verify import check,BadProof

def wire(typ,y,**port_bits):
    return {"type":typ,"connections":{**{p:[v] for p,v in port_bits.items()},"Y":[y]}}

def design(n=4,corrupt=None):
    cells={};cin=2;port={};stage=[]
    for i in range(n):
        a,b=3+2*i,4+2*i
        p=100+10*i;s=101+10*i;g=102+10*i;t=103+10*i;c=104+10*i
        cells[f"xor_p_{i}"]=wire("$_XOR_",p,A=a,B=b)
        cells[f"xor_s_{i}"]=wire("$_XOR_",s,A=p,B=cin)
        cells[f"and_g_{i}"]=wire("$_AND_",g,A=a,B=b)
        cells[f"and_t_{i}"]=wire("$_AND_",t,A=p,B=cin)
        if corrupt==i:
            cells[f"bad_c_{i}"]=wire("$_XOR_",c,A=a,B=cin)
        else:
            cells[f"or_c_{i}"]=wire("$_OR_",c,A=g,B=t)
        stage.append((a,b,cin,s,c))
        port[f"s{i}"]={"direction":"output","bits":[s]}
        cin=c
    port["initial_carry"]={"direction":"input","bits":[2]}
    for i in range(n):
        for k,bit in ((f"a{i}",3+2*i),(f"b{i}",4+2*i)):
            port[k]={"direction":"input","bits":[bit]}
    return {"modules":{"ripple4":{"ports":port,"cells":cells}}},stage

def checked(folder,doc):
    raw=folder/"netlist.json"
    raw.write_text(json.dumps(doc))
    proof=detect(doc,"ripple4")
    proof["original_netlist_sha256"]=hashlib.sha256(raw.read_bytes()).hexdigest()
    cert=folder/"certificate.json"
    cert.write_text(json.dumps(proof))
    independent=check(raw,cert)
    assert independent["status"]=="REAL6_1_INDEPENDENT_EIGHT_ROW_GATE_PROOF_PASS"
    return proof,cert

def main():
    with tempfile.TemporaryDirectory() as td:
        folder=Path(td)
        good,raw_stages=design()
        p,path=checked(folder,good)
        assert p["metrics"]["longest_chain_bits"]>=4,p["metrics"]
        assert p["metrics"]["certified_stage_pairs"]>=4,p["metrics"]
        print("REAL6_1_GOOD_FOUR_BIT_RIPPLE_AND_INDEPENDENT_PROOF_PASS",p["metrics"],flush=True)
        original=path.read_text()
        forged=copy.deepcopy(p)
        forged["stages"][0]["carry_bit"]=forged["stages"][0]["sum_bit"]
        path.write_text(json.dumps(forged))
        try:check(folder/"netlist.json",path)
        except BadProof:print("REAL6_1_FALSE_CARRY_REJECTED",flush=True)
        else:raise AssertionError("FALSE_CARRY_WAS_ACCEPTED")
        forged=copy.deepcopy(p)
        forged["original_netlist_sha256"]="0"*64
        path.write_text(json.dumps(forged))
        try:check(folder/"netlist.json",path)
        except BadProof:print("REAL6_1_FORGED_SOURCE_SHA_REJECTED",flush=True)
        else:raise AssertionError("FALSE_SOURCE_WAS_ACCEPTED")
        path.write_text(original)
        bad,_=design(corrupt=2)
        wrong,_=checked(folder,bad)
        assert wrong["metrics"]["longest_chain_bits"]<4,wrong["metrics"]
        print("REAL6_1_WRONG_MIDDLE_CARRY_BREAKS_CERTIFIED_CHAIN_PASS",
              wrong["metrics"],flush=True)
        print("REAL6_1_ALL_TESTS_PASS",flush=True)

if __name__=="__main__":main()
