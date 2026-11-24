#!/usr/bin/env python3
"""REAL6.2 physically connected, non-overlapping ripple carry chain candidates.

Input: immutable REAL6 original Yosys technology-gate netlist and REAL6.1
eight-row source-verified stages. No new RTL, no benchmark-specific names,
no CDCL fallback. Actual proof is performed by real6_2_verify.py, separately.
A local chain is not a full-chip arithmetical/temporal theorem.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

MAX_CHAIN_BITS=6
MAX_CHAINS=200
MAX_PATH_SEARCH=30000

def sha(raw):return hashlib.sha256(raw).hexdigest()

def candidates(cert):
    stages=cert["stages"]
    edges={i:[] for i in range(len(stages))}
    for i,x in enumerate(stages):
        for j,y in enumerate(stages):
            if i!=j and x["carry_bit"] in y["inputs"]:
                edges[i].append(j)
    uniq={};steps=0
    for root in range(len(stages)):
        first=stages[root]
        def explore(path,seen_external):
            nonlocal steps
            steps+=1
            if steps>MAX_PATH_SEARCH:return
            if len(path)>=2:
                ids=tuple(path)
                uniq[ids]={"stage_indices":list(ids),
                    "length_bits":len(ids),"scope":"LOCAL_CONNECTED_GATE_CUT",
                    "first_carry_bit":min(first["inputs"])}
            if len(path)>=MAX_CHAIN_BITS:return
            previous=stages[path[-1]]
            for nxt in edges[path[-1]]:
                if nxt in path:continue
                stage=stages[nxt]
                carry=previous["carry_bit"]
                fresh=[v for v in stage["inputs"] if v!=carry]
                if len(fresh)!=2:continue
                if carry in seen_external or any(v in seen_external for v in fresh):
                    continue
                # Keep operand cut symbols distinct, but do not claim their
                # physical upstream independence in the original full core.
                explore(path+[nxt],seen_external|set(fresh))
        explore([root],set(first["inputs"]))
        if steps>MAX_PATH_SEARCH:break
    ordered=sorted(uniq.values(),key=lambda x:(-x["length_bits"],x["stage_indices"]))
    return ordered[:MAX_CHAINS],steps,steps>MAX_PATH_SEARCH

def analyze(netlist,certificate):
    src=Path(netlist).read_bytes();cert_raw=Path(certificate).read_bytes()
    proof=json.loads(cert_raw)
    if proof.get("original_netlist_sha256")!=sha(src):
        raise ValueError("SOURCE_GATE_SHA_MISMATCH")
    if proof.get("protocol")!="DRNAS_REAL6_1_LOCAL_CARRY_V1":
        raise ValueError("WRONG_BASE_CERTIFICATE")
    stages=proof["stages"]
    for s in stages:
        if len(s["inputs"])!=3 or len(set(s["inputs"]))!=3:
            raise ValueError("INVALID_BASE_STAGE")
    chains,visited,cut=candidates(proof)
    triples={tuple(s["inputs"]) for s in stages}
    sums={s["sum_bit"] for s in stages}
    carries={s["carry_bit"] for s in stages}
    pairs={(s["sum_bit"],s["carry_bit"]) for s in stages}
    result={
        "protocol":"DRNAS_REAL6_2_PHYSICAL_CHAIN_AUDIT_V1",
        "source_netlist_sha256":sha(src),
        "source_real6_1_certificate_sha256":sha(cert_raw),
        "source_real6_1_status":proof["status"],
        "scope":"RETROSPECTIVE original Yosys gate netlists. Local cut-gate ripple structure only; not a whole RTL SAT/UNSAT or equivalence theorem.",
        "stages":stages,
        "chains":chains,
        "metrics":{
            "base_stage_pairs":len(stages),
            "distinct_three_input_cuts":len(triples),
            "distinct_sum_output_bits":len(sums),
            "distinct_carry_output_bits":len(carries),
            "distinct_physical_sum_carry_bit_pairs":len(pairs),
            "candidate_connected_chains":len(chains),
            "max_candidate_chain_bits":max((x["length_bits"] for x in chains),default=0),
            "path_search_steps":visited,
            "path_search_budget_hit":cut
        }}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--certificate",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=analyze(a.netlist,a.certificate)
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print("REAL6_2_CHAIN_DETECTION",report["metrics"],flush=True)

if __name__=="__main__":main()
