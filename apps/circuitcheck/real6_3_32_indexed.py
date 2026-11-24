#!/usr/bin/env python3
"""REAL6.3/32 indexed carry successor on frozen original Yosys gate netlists.

Build on REAL6.1 independently certified one-bit SUM+CARRY anchors. For each
connected arithmetic prefix, symbolically derive its carry using a canonical
reduced ordered BDD over the *existing* independent gate-cut input bits.
Index all original XOR-of-XOR SUM roots and look for a physical carry input
whose source-gate cone equals that exact prefix carry. When found, validate the
entire extended local chain with source gate BDD, without SAT/CDCL fallback.

No hardcoded ChaCha signal names, gate IDs or original netlist modifications.
Proof scope: local two-state source gate cuts, not an RTL temporal theorem.
Independent checker: unchanged real6_3_verify.py.
"""
from __future__ import annotations
import argparse
import functools
import hashlib
import json
import os
import time
from pathlib import Path
from real6_1_carry import gate_graph
from real6_3_bdd import (BDD, make_seeds, verify_path, Budget, Unsupported)

TARGET_BITS=32
MAX_BEAM=8
MAX_SOURCES=2500
MAX_VALID_SUCCESSORS=3
MAX_GLOBAL_CHECKS=100000

def digest(data):
    return hashlib.sha256(data).hexdigest()

def path_free_bits(path):
    free=list(path[0]["inputs"])
    for x in path[1:]:
        free+=x["operands"]
    return free

def desired_carry(prefix,b):
    initial=[b.wire(x) for x in prefix[0]["inputs"]]
    carry=b.majority(*initial)
    for st in prefix[1:]:
        a,c=(b.wire(x) for x in st["operands"])
        carry=b.majority(a,c,carry)
    return carry

def physical_inputs_available(prod,free):
    basis=set(free)
    active=set()
    cache={}
    def supported(bit):
        if bit in basis or bit in ("0","1"):return True
        if bit in cache:return cache[bit]
        if bit in active or bit not in prod:return False
        active.add(bit)
        ans=all(supported(child) for child in prod[bit][1])
        active.remove(bit)
        cache[bit]=ans
        return ans
    return supported

def search(original_netlist,base_certificate,target_bits=TARGET_BITS,beam=MAX_BEAM):
    net=Path(original_netlist).read_bytes()
    base=Path(base_certificate).read_bytes()
    cert=json.loads(base)
    top,prod,consumers,unknown=gate_graph(json.loads(net),cert["top"])
    seeds,raw=make_seeds(prod)
    roots={x["sum_bit"] for x in seeds}
    # Source certified literal wire edges seed search. No filename-based hints.
    anchors=[]
    for s in cert["stages"]:
        if s["sum_bit"] not in roots:continue
        for t in cert["stages"]:
            if t["sum_bit"] not in roots or t is s or s["carry_bit"] not in t["inputs"]:
                continue
            two=sorted(x for x in t["inputs"] if x!=s["carry_bit"])
            if len(two)!=2 or len(set(two))!=2 or any(x in s["inputs"] for x in two):
                continue
            root={"sum_bit":s["sum_bit"],"inputs":s["inputs"],"base_carry_bit":s["carry_bit"]}
            second={"sum_bit":t["sum_bit"],"carry_input":s["carry_bit"],"operands":two}
            path=[root,second]
            ok,_=verify_path(path,prod)
            if ok:anchors.append(path)
    beams=anchors[:beam]
    found=list(beams)
    metrics={"source_one_bit_pairs":len(cert["stages"]),
             "source_xor_triple_seeds":len(seeds),
             "certified_two_bit_physical_anchors":len(anchors),
             "symbolic_carry_wires_evaluated":0,
             "candidate_successors_structurally_relevant":0,
             "full_extended_path_tests":0,
             "skipped_unbound_or_budgeted":0,
             "search_budget_reached":False,
             "progress":[]}
    start=time.perf_counter()
    while beams and max(len(p) for p in beams)<target_bits:
        extended=[]
        for path in beams:
            used=set(path_free_bits(path))
            sums={st["sum_bit"] for st in path}
            last_sum=path[-1]["sum_bit"]
            free=path_free_bits(path)
            try:
                b=BDD(prod,free)
                expected=desired_carry(path,b)
            except (Budget,Unsupported,RecursionError):
                metrics["skipped_unbound_or_budgeted"]+=1
                continue
            supported=physical_inputs_available(prod,free)
            # Rank by next physical SUM bit proximity, but all accepted
            # assertions are fully checked against original gate equations.
            ordering=sorted(seeds,key=lambda s:(abs(s["sum_bit"]-last_sum),s["sum_bit"]))
            accepted=[]
            carry_cache={}
            visits=0
            for candidate in ordering:
                if candidate["sum_bit"] in sums:continue
                for v in candidate["inputs"]:
                    operands=sorted(x for x in candidate["inputs"] if x!=v)
                    if len(operands)!=2 or len(set(operands))!=2:continue
                    if any(x in used for x in operands) or v in operands:continue
                    if v not in carry_cache:
                        visits+=1
                        if visits>MAX_SOURCES:break
                        if not supported(v):
                            carry_cache[v]=False
                        else:
                            try:
                                carry_cache[v]=(b.wire(v)==expected)
                                metrics["symbolic_carry_wires_evaluated"]+=1
                            except (Budget,Unsupported,RecursionError):
                                carry_cache[v]=False
                                metrics["skipped_unbound_or_budgeted"]+=1
                    if not carry_cache[v]:continue
                    metrics["candidate_successors_structurally_relevant"]+=1
                    next_path=path+[{"sum_bit":candidate["sum_bit"],
                                     "carry_input":v,"operands":operands}]
                    metrics["full_extended_path_tests"]+=1
                    try:
                        valid,_=verify_path(next_path,prod)
                    except (Budget,Unsupported,RecursionError):
                        valid=False
                        metrics["skipped_unbound_or_budgeted"]+=1
                    if valid:
                        accepted.append(next_path)
                        if len(accepted)>=MAX_VALID_SUCCESSORS:break
                if visits>MAX_SOURCES or len(accepted)>=MAX_VALID_SUCCESSORS:break
            extended.extend(accepted)
        if not extended:break
        extended.sort(key=lambda p:(-len(p),[x["sum_bit"] for x in p]))
        # Diversify by physical SUM sequence. This is intentionally a
        # noncomplete heuristic search; the certificate is independently proofed.
        seen=set();next_beam=[]
        for path in extended:
            key=tuple(x["sum_bit"] for x in path)
            if key in seen:continue
            seen.add(key);next_beam.append(path)
            if len(next_beam)>=beam:break
        beams=next_beam
        found.extend(beams)
        curr=max(len(p) for p in beams)
        metrics["progress"].append({"bits":curr,"beam":len(beams),
                                    "evaluated_wires":metrics["symbolic_carry_wires_evaluated"],
                                    "path_tests":metrics["full_extended_path_tests"]})
        print("REAL6_3_32_PROGRESS",metrics["progress"][-1],flush=True)
        if metrics["full_extended_path_tests"]>=MAX_GLOBAL_CHECKS:
            metrics["search_budget_reached"]=True
            break
    found.sort(key=lambda p:(-len(p),[s["sum_bit"] for s in p]))
    results=[];used=set()
    for path in found:
        seq=tuple(s["sum_bit"] for s in path)
        if seq in used:continue
        used.add(seq)
        results.append(path)
        if len(results)>=16:break
    longest=max((len(p) for p in results),default=0)
    metrics.update({"longest_proposed_sum_bits":longest,
                    "target_32_found":longest>=target_bits,
                    "elapsed_detection_seconds":round(time.perf_counter()-start,4),
                    "not_a_new_blind_holdout":True,
                    "external_gate_inputs_trusted_only_as_free_cuts":True})
    return {
        "protocol":"DRNAS_REAL6_3_BDD_ARITHMETIC_CARRY_DISCOVERY_V1",
        "scope":"retrospective source-only 2-state exact local gate-cut modular addition; no whole RTL time behavior, circuit SAT/UNSAT or complexity claim",
        "original_netlist_sha256":digest(net),
        "source_real6_1_certificate_sha256":digest(base),
        "original_top":top,
        "paths":results,
        "metrics":metrics
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--base-certificate",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--target-bits",type=int,default=TARGET_BITS)
    a=p.parse_args()
    report=search(a.netlist,a.base_certificate,target_bits=a.target_bits)
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print("REAL6_3_32_DETECTION",json.dumps(report["metrics"]),flush=True)

if __name__=="__main__":
    main()
