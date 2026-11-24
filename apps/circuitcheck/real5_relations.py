#!/usr/bin/env python3
"""DRNAS REAL5: find exact nonlinear-cut cancellation between different outputs.

Reads independently verified REAL4 gate-netlist affine-island certificates.
Each proven output y_i has an EXACT symbolic form, over GF(2):
    y_i = L_i(primary_inputs, unconstrained_FF_Q) XOR C_i(cut_outputs)
where cut_outputs are *actual* Yosys cell output wires.

By GF(2) linear algebra, whenever XOR(C_i for i in selected_outputs)==0:
    XOR(y_i for i in selected_outputs) = XOR(L_i)   (for ALL inputs/cuts)
even if every y_i individually depended on nonlinear cutpoints.

This is a certificate of a *relational one-step identity*, not a proof that
each output is affine, that a whole circuit is SAT/UNSAT, or that any temporal
property holds. Only relations with >=2 distinct physical outputs, >=2
primary/state input coefficients, and canceled nonlinear cuts are reported.

The previous REAL4 engine and its independent verifier are unchanged.
No custom source/project names, CRC patterns, or polynomial tuning.
"""
from __future__ import annotations
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path

from real4_verify import proof_replay

MAX_TERMS=8
MAX_RELATIONS=64
MAX_ROWS=2048

class NoProof(Exception):pass

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def eligible(cert):
    basis_size=len(cert["basis"])
    # The certificate may include internal probes; always distinguish external
    # output+FF-D relations from relations mixing sampled internal gates.
    rows=[]
    seen=set()
    for p in cert["probes"]:
        if p["status"] not in ("GLOBAL_AFFINE_ONE_STEP","LOCAL_AFFINE_WITH_CUTS"):
            continue
        if p["kind"] not in ("primary_output","ff_next_state","internal_xor"):
            continue
        bit=p["yosys_bit"]
        if not isinstance(bit,int) or bit in seen:
            continue
        seen.add(bit)
        mask=int(p["mask_hex"],16)
        cut_vector=mask>>(basis_size+1)
        if not cut_vector:continue
        rows.append({
            "probe":{"kind":p["kind"],"name":p["name"],
                     "position":p["position"],"yosys_bit":bit},
            "mask":mask,"cut_vector":cut_vector,
            "ordinary_mask":mask&((1<<(basis_size+1))-1),
        })
    if len(rows)>MAX_ROWS:raise NoProof("CANDIDATE_ROWS_BUDGET")
    return rows

def detect(cert):
    n=len(cert["basis"])
    rows=eligible(cert)
    # First prioritize exact 2-term cancellations; then bounded-length
    # Gaussian elimination can discover 3+ output relations.
    bucket=defaultdict(list)
    proposals=[]
    for i,r in enumerate(rows):
        bucket[r["cut_vector"]].append(i)
    for cut,indices in bucket.items():
        for position,i in enumerate(indices[:32]):
            for j in indices[position+1:32]:
                proposals.append((i,j))
    # Binary Gaussian elimination on the nonlinear-cut coefficient vectors,
    # with an output-combination bitset carrying every row operation.
    pivots={}
    for i,row in enumerate(rows):
        remainder=row["cut_vector"]
        combination=1<<i
        while remainder:
            pivot=remainder.bit_length()-1
            if pivot in pivots:
                oldvec,oldmask=pivots[pivot]
                remainder ^= oldvec
                combination ^= oldmask
            else:
                pivots[pivot]=(remainder,combination)
                break
        if remainder==0 and 2<=combination.bit_count()<=MAX_TERMS:
            indices=tuple(k for k in range(len(rows)) if combination>>k&1)
            proposals.append(indices)
    results=[]
    seen=set()
    for raw_indices in proposals:
        ids=tuple(sorted(set(raw_indices)))
        if len(ids)!=len(raw_indices) or len(ids)<2 or len(ids)>MAX_TERMS or ids in seen:
            continue
        seen.add(ids)
        selected=[rows[k] for k in ids]
        # Eliminate alias-self relations and duplicated physical net bits.
        if len({r["probe"]["yosys_bit"] for r in selected})!=len(selected):
            continue
        nonlinear=0
        ordinary=0
        for r in selected:
            nonlinear ^= r["cut_vector"]
            ordinary ^= r["ordinary_mask"]
        if nonlinear!=0:continue
        input_weight=(ordinary>>1).bit_count()
        if input_weight<2:continue
        canceled_cuts=set()
        for r in selected:
            v=r["cut_vector"]
            while v:
                bit=v&-v
                canceled_cuts.add(bit.bit_length()-1)
                v-=bit
        if not canceled_cuts:continue
        external=all(r["probe"]["kind"]!="internal_xor" for r in selected)
        item={
            "relation_type":"EXTERNAL_OUTPUT_AND_FF_D" if external else "INCLUDES_SAMPLED_INTERNAL_XOR",
            "probes":[r["probe"] for r in selected],
            "output_xor_mask_hex":hex(ordinary),
            "term_count":len(ids),
            "ordinary_input_coefficient_weight":input_weight,
            "nonlinear_cutpoints_canceled":len(canceled_cuts),
            "canceled_cut_indices":[n+i for i in sorted(canceled_cuts)],
            "scope":"one-step exact relation across output/FF-D signals; FF Q and nonlinear cut outputs are unconstrained"
        }
        results.append(item)
    # Fixed scoring rule, independent of the source family. An external
    # relation is more useful than a relation involving internal probe pins.
    results.sort(key=lambda x: (
        x["relation_type"]!="EXTERNAL_OUTPUT_AND_FF_D",
        -x["nonlinear_cutpoints_canceled"],
        x["term_count"],
        -x["ordinary_input_coefficient_weight"],
        [(p["kind"],p["name"],p["position"]) for p in x["probes"]]
    ))
    return results[:MAX_RELATIONS],{
        "eligible_cut_dependent_probes":len(rows),
        "candidate_pair_or_nullspace_relations":len(proposals),
        "verified_nontrivial_relations":len(results),
        "reported_max":MAX_RELATIONS,
        "external_relations_reported":sum(x["relation_type"]=="EXTERNAL_OUTPUT_AND_FF_D" for x in results[:MAX_RELATIONS]),
        "internally_sampled_relations_reported":sum(x["relation_type"]!="EXTERNAL_OUTPUT_AND_FF_D" for x in results[:MAX_RELATIONS]),
    }

def generate(folder):
    verified=proof_replay(folder)
    if verified["status"]!="CHECKED_LOCAL_AFFINE_GATE_IDENTITIES":
        raise NoProof("ORIGINAL_GATE_PROOF_NOT_REPLAYED")
    cert=json.loads((folder/"real4_certificate.json").read_text())
    relations,stats=detect(cert)
    result={
        "engine":"DRNAS_REAL5_CROSSCONE_CUT_CANCELLATION_V1",
        "netlist_sha256":sha(folder/"netlist.json"),
        "real4_certificate_sha256":sha(folder/"real4_certificate.json"),
        "original_real4_replay":"CHECKED_LOCAL_AFFINE_GATE_IDENTITIES",
        "source_scope":"Yosys two-state gate netlist, no temporal/global SAT claim",
        "relations":relations,"stats":stats,
        "status":"RELATIONAL_IDENTITIES_FOUND" if relations else "NO_NONTRIVIAL_CANCELLATION_FOUND"
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    x=p.parse_args()
    try:
        result=generate(x.folder)
    except (NoProof,KeyError,ValueError,TypeError,FileNotFoundError,OverflowError,MemoryError) as e:
        result={"status":"UNKNOWN","reason":str(e)}
    x.out.parent.mkdir(exist_ok=True,parents=True)
    x.out.write_text(json.dumps(result,indent=2)+"\n")
    print("REAL5_RELATIONS",result["status"],result.get("stats",{}),flush=True)
    return 0 if result["status"]!="UNKNOWN" else 2

if __name__=="__main__":raise SystemExit(main())
