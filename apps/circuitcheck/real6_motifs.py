#!/usr/bin/env python3
"""DRNAS REAL6 — exact CH/MAJ/full-adder motif detection in verified GF(2) ANF.

No names, project IDs, filenames or fixed RTL signatures are consulted.
Input: unchanged Yosys netlist + REAL5-Q certificate independently rechecked.
Monomial subsets are exact for supported 2-state gate cones, conditioned on
any physical cut outputs. Variables may be primary inputs, FF Q or cut symbols.
  CH(s,a,b)  = s*a XOR s*b XOR b
  MAJ(a,b,c) = a*b XOR a*c XOR b*c
  SUM(a,b,c) = a XOR b XOR c
  FULL_ADDER = paired SUM and MAJ on the same three variable indices.

A motif containing a physical nonlinear cut is CONDITIONAL_TO_CUTS, not
a claim that whole input-to-output logic is globally quadratic. A motif
containing FF Q applies to only one unconstrained current-state snapshot,
not a temporal machine invariant. Degree and term count remain capped by
the frozen REAL5-Q engine; no CDCL fallback yields a certified success.
"""
from __future__ import annotations
import argparse, hashlib, json
from collections import defaultdict
from pathlib import Path
from real5q_verify import check

MAX_MOTIFS=300
MAX_ADDERS=64

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def probes(cert):
    """Deduplicate physical bits, prefer externally visible over internal."""
    choices=[x for x in cert["probes"] if x.get("status") in
        ("GLOBAL_EXACT_GF2_ANF","LOCAL_BOUNDED_ANF_WITH_CUTS") and
        x["kind"] in ("primary_output","ff_D","internal_probe")]
    choices.sort(key=lambda p:(p["kind"]=="internal_probe",p["kind"]=="ff_D",
                               p["name"],p["position"]))
    taken=set()
    for p in choices:
        bit=p["yosys_bit"]
        if not isinstance(bit,int) or bit in taken: continue
        taken.add(bit)
        yield p

def describe(p):
    return {"kind":p["kind"],"name":p["name"],"position":p["position"],
            "yosys_bit":p["yosys_bit"]}

def classify(p,basis_count,total_count):
    terms={int(item,16) for item in p["monomials_hex"]}
    if len(terms)!=len(p["monomials_hex"]):return []
    if any(m.bit_count()>2 or m >= (1<<total_count) for m in terms):return []
    constant=0 in terms
    without=terms-{0}
    linear={m.bit_length()-1 for m in without if m.bit_count()==1}
    pairs={frozenset(i for i in range(m.bit_length()) if (m>>i)&1)
           for m in without if m.bit_count()==2}
    if len(without)!=len(linear)+len(pairs):return []
    outputs=[]
    variables={j for edge in pairs for j in edge}|linear
    scope=("CONDITIONAL_CUT_SYMBOLS" if any(i>=basis_count for i in variables)
           else "GLOBAL_ONE_STEP")
    if len(pairs)==3 and not linear and len(variables)==3 and all(
          frozenset((a,b)) in pairs for a in variables for b in variables if a<b):
        outputs.append({"motif":"MAJ","variables":sorted(variables),
                        "inverted":constant,"scope":scope})
    if len(pairs)==2 and len(linear)==1 and len(variables)==3:
        p1,p2=list(pairs)
        shared=p1&p2
        if len(shared)==1 and (p1|p2)==variables:
            selector=next(iter(shared))
            branch=sorted(variables-{selector})
            if next(iter(linear)) in branch:
                outputs.append({"motif":"CH","variables":sorted(variables),
                    "selector":selector,"zero_branch":next(iter(linear)),
                    "one_branch":next(x for x in branch if x not in linear),
                    "inverted":constant,"scope":scope})
    if not pairs and len(linear)==3 and len(without)==3:
        outputs.append({"motif":"SUM3","variables":sorted(linear),
                        "inverted":constant,"scope":scope})
    return outputs

def detect(cert):
    basis_count=len(cert["basis"])
    total_count=basis_count+len(cert["cuts"])
    motifs=[]
    by_kind=defaultdict(list)
    for p in probes(cert):
        for found in classify(p,basis_count,total_count):
            row={"probe":describe(p),**found}
            motifs.append(row)
            by_kind[(found["motif"],tuple(found["variables"]),found["inverted"])].append(row)
    motifs.sort(key=lambda m:(m["motif"],m["scope"]!="GLOBAL_ONE_STEP",
             m["variables"],m["probe"]["kind"]=="internal_probe",
             m["probe"]["name"],m["probe"]["position"]))
    adders=[]
    seen=set()
    for (kind,variables,inverted), sums in sorted(by_kind.items()):
        if kind!="SUM3" or inverted:continue
        carry=by_kind.get(("MAJ",variables,False),[])
        for summation in sums:
            for majority in carry:
                if summation["probe"]["yosys_bit"]==majority["probe"]["yosys_bit"]:
                    continue
                marker=(summation["probe"]["yosys_bit"],majority["probe"]["yosys_bit"])
                if marker in seen:continue
                seen.add(marker)
                scope=("CONDITIONAL_CUT_SYMBOLS" if any(v>=basis_count for v in variables)
                       else "GLOBAL_ONE_STEP")
                adders.append({"kind":"FULL_ADDER_1_BIT",
                    "variables":list(variables),
                    "sum_probe":summation["probe"],
                    "carry_probe":majority["probe"],
                    "scope":scope,
                    "both_outputs_external":all(p["kind"]!="internal_probe"
                        for p in (summation["probe"],majority["probe"]))})
    adders.sort(key=lambda r:(not r["both_outputs_external"],
          r["scope"]!="GLOBAL_ONE_STEP",r["variables"],
          r["sum_probe"]["name"],r["carry_probe"]["name"]))
    return motifs[:MAX_MOTIFS],adders[:MAX_ADDERS],{
        "matched_motifs_before_display_limit":len(motifs),
        "reported_motifs":min(MAX_MOTIFS,len(motifs)),
        "majs":sum(m["motif"]=="MAJ" for m in motifs),
        "chs":sum(m["motif"]=="CH" for m in motifs),
        "three_input_xor_sums":sum(m["motif"]=="SUM3" for m in motifs),
        "paired_full_adders_before_limit":len(adders),
        "paired_full_adders_reported":min(len(adders),MAX_ADDERS),
        "globally_proven_motifs":sum(m["scope"]=="GLOBAL_ONE_STEP" for m in motifs),
        "conditional_cut_motifs":sum(m["scope"]=="CONDITIONAL_CUT_SYMBOLS" for m in motifs)
    }

def generate(folder):
    result=check(folder)
    if result.get("status")!="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS":
        raise ValueError("BASE_GF2_CERTIFICATE_UNVERIFIED")
    source=folder/"real5q_certificate.json"
    cert=json.loads(source.read_text())
    motifs,adders,summary=detect(cert)
    return {
       "status":"MOTIFS_VERIFIED_BASE_ANF" if motifs else "NO_MATCHING_VERIFIED_MOTIFS",
       "engine":"DRNAS_REAL6_EXACT_ANF_MOTIF_LINK_V1",
       "gate_netlist_sha256":sha(folder/"netlist.json"),
       "base_polynomial_certificate_sha256":sha(source),
       "proof_scope":"one-step 2-state Yosys gate ANF, current FF-Q unconstrained and nonlinear cuts free",
       "motifs":motifs,"full_adder_pairs":adders,
       "counts":summary
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--folder",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:result=generate(a.folder)
    except (ValueError,KeyError,IndexError,TypeError,
            FileNotFoundError,OverflowError,MemoryError) as e:
        result={"status":"UNKNOWN","reason":str(e)}
    a.out.parent.mkdir(exist_ok=True,parents=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("REAL6_MOTIFS",result["status"],result.get("counts",{}),flush=True)
    return 0 if result["status"]!="UNKNOWN" else 2

if __name__=="__main__":
    raise SystemExit(main())
