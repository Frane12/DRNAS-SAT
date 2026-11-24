#!/usr/bin/env python3
"""Independent REAL6 motif and FULL-ADDER checker.

Does not import real6_motifs. Reads original immutable Yosys gate JSON and
replays EVERY REAL5-Q ANF via separately implemented monomial-set checker.
Then independently enumerates all 8 assignments of each 3-variable ANF,
classifies MAJ, selector-CHOICE, and SUM by truth tables, and checks linked
sum/carry bits really are a full-adder pair on identical variables.

It does not prove original HDL semantics, reachability, clocks or a
whole-circuit SAT/UNSAT claim. Cuts are unconstrained Boolean symbols;
patterns involving them are explicitly conditional symbolic identities.
"""
from __future__ import annotations
import itertools,hashlib,json,sys
from pathlib import Path
from real5q_verify import check as replay_original_anf

class Invalid(Exception):pass
def fail(m):raise Invalid(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(p):return (p["kind"],p["name"],p["position"],p["yosys_bit"])
def label(p):return {k:p[k] for k in ("kind","name","position","yosys_bit")}

def truth(terms,variables,values):
    assignment=sum((values[k]<<variables[k]) for k in range(3))
    result=0
    for m in terms:
        if m&assignment==m:result^=1
    return result

def independently_classify(p,basis_count,total):
    if p.get("status") not in ("GLOBAL_EXACT_GF2_ANF","LOCAL_BOUNDED_ANF_WITH_CUTS"):
        return []
    monomials=[int(v,16) for v in p["monomials_hex"]]
    if any(x<0 or x.bit_count()>2 or x>=(1<<total) for x in monomials):
        fail("UNSUPPORTED_MONOMIAL")
    variables=sorted({i for m in monomials for i in range(m.bit_length()) if m>>i&1})
    if len(variables)!=3:return []
    variable_to_pos={v:i for i,v in enumerate(variables)}
    table={}
    for vals in itertools.product((0,1),repeat=3):
        table[vals]=truth(monomials,variables,vals)
    conditional=any(v>=basis_count for v in variables)
    scope="CONDITIONAL_CUT_SYMBOLS" if conditional else "GLOBAL_ONE_STEP"
    base={"probe":label(p),"variables":variables,"scope":scope}
    answers=[]
    for inverted in (False,True):
        if all(table[vals]==(int(sum(vals)>=2)^int(inverted)) for vals in table):
            answers.append({**base,"motif":"MAJ","inverted":inverted})
        if all(table[vals]==((vals[0]^vals[1]^vals[2])^int(inverted)) for vals in table):
            answers.append({**base,"motif":"SUM3","inverted":inverted})
        for selector in variables:
            for zero in variables:
                if zero==selector:continue
                one=next(j for j in variables if j not in (selector,zero))
                if all(table[vals]==(
                    (vals[variable_to_pos[one]] if vals[variable_to_pos[selector]]
                    else vals[variable_to_pos[zero]]) ^ int(inverted))
                    for vals in table):
                    answers.append({**base,"motif":"CH","selector":selector,
                                    "zero_branch":zero,"one_branch":one,
                                    "inverted":inverted})
    return answers

def verify(folder,report_path):
    base=replay_original_anf(folder)
    if base.get("status")!="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS":
        fail("BASE_POLYNOMIAL_CERTIFICATE_UNVERIFIED")
    doc=json.loads((folder/"real5q_certificate.json").read_text())
    report=json.loads(report_path.read_text())
    if report.get("gate_netlist_sha256")!=sha(folder/"netlist.json"):
        fail("ORIGINAL_GATE_SHA_CHANGED")
    if report.get("base_polynomial_certificate_sha256")!=sha(folder/"real5q_certificate.json"):
        fail("ORIGINAL_POLYNOMIAL_CERT_SHA_CHANGED")
    basis_count=len(doc["basis"])
    total=basis_count+len(doc["cuts"])
    external=[]
    internal=[]
    available={}
    for p in doc["probes"]:
        if p.get("kind") not in ("primary_output","ff_D","internal_probe"):
            continue
        if p.get("status") not in ("GLOBAL_EXACT_GF2_ANF","LOCAL_BOUNDED_ANF_WITH_CUTS"):
            continue
        k=key(p)
        # A physical net bit might have multiple output names. Prefer a
        # real output/next-state pin over an internal probe.
        if p["kind"]!="internal_probe":external.append(p)
        else:internal.append(p)
        available[k]=p
    ordered=sorted(external,key=lambda p:(p["kind"]=="ff_D",
                 p["name"],p["position"]))
    ordered+=sorted(internal,key=lambda p:(p["name"],p["position"]))
    seen_bits=set()
    all_expected=[]
    for p in ordered:
        if p["yosys_bit"] in seen_bits:continue
        seen_bits.add(p["yosys_bit"])
        all_expected.extend(independently_classify(p,basis_count,total))
    current=report.get("motifs")
    if not isinstance(current,list) or len(current)>300:
        fail("MOTIF_LIMIT_OR_FORMAT_BAD")
    # Match independently classified exact truth tables. Reject invented,
    # duplicate or changed motif details but do not rely on discovery code.
    expected_keys={json.dumps(m,sort_keys=True) for m in all_expected}
    claimed_keys=[json.dumps(m,sort_keys=True) for m in current]
    if len(set(claimed_keys))!=len(claimed_keys):
        fail("DUPLICATE_MOTIF")
    if any(k not in expected_keys for k in claimed_keys):
        fail("UNSUPPORTED_MOTIF_TRUTH_TABLE")
    if len(current)!=min(len(all_expected),300):
        fail("INCOMPLETE_REPORTED_MOTIFS")
    actual_count=report.get("counts",{})
    control={
        "matched_motifs_before_display_limit":len(all_expected),
        "reported_motifs":min(len(all_expected),300),
        "majs":sum(x["motif"]=="MAJ" for x in all_expected),
        "chs":sum(x["motif"]=="CH" for x in all_expected),
        "three_input_xor_sums":sum(x["motif"]=="SUM3" for x in all_expected),
        "globally_proven_motifs":sum(x["scope"]=="GLOBAL_ONE_STEP" for x in all_expected),
        "conditional_cut_motifs":sum(x["scope"]=="CONDITIONAL_CUT_SYMBOLS" for x in all_expected)
    }
    for name,value in control.items():
        if actual_count.get(name)!=value:fail("FALSE_MOTIF_STATS "+name)
    # Recreate full-adder candidate set from independent MAJ/SUM truth tables.
    all_adders=[]
    carry=[p for p in all_expected if p["motif"]=="MAJ" and not p["inverted"]]
    sums=[p for p in all_expected if p["motif"]=="SUM3" and not p["inverted"]]
    for summation in sums:
        for majority in carry:
            if summation["variables"]!=majority["variables"]:continue
            if summation["probe"]["yosys_bit"]==majority["probe"]["yosys_bit"]:continue
            both=all(p["kind"]!="internal_probe" for p in (
                summation["probe"],majority["probe"]))
            all_adders.append({"kind":"FULL_ADDER_1_BIT",
                "variables":summation["variables"],
                "sum_probe":summation["probe"],
                "carry_probe":majority["probe"],
                "scope":summation["scope"],
                "both_outputs_external":both})
    claims=report.get("full_adder_pairs")
    if not isinstance(claims,list) or len(claims)>64:fail("PAIR_LIMIT_BAD")
    allowed={json.dumps(x,sort_keys=True) for x in all_adders}
    incoming=[json.dumps(x,sort_keys=True) for x in claims]
    if len(set(incoming))!=len(incoming) or any(x not in allowed for x in incoming):
        fail("FALSE_FULL_ADDER_INPUTS_OR_CARRY")
    if len(claims)!=min(len(all_adders),64):fail("MISSING_FULL_ADDER_PAIR")
    if actual_count.get("paired_full_adders_before_limit")!=len(all_adders):
        fail("FALSE_FULL_ADDER_STATS")
    if actual_count.get("paired_full_adders_reported")!=len(claims):
        fail("FALSE_REPORTED_PAIR_COUNT")
    if report.get("status")!=("MOTIFS_VERIFIED_BASE_ANF" if all_expected else
                             "NO_MATCHING_VERIFIED_MOTIFS"):
        fail("UNSOUND_MOTIF_VERDICT")
    return {"status":"CHECKED_REAL6_MOTIF_TRUTH_TABLES",
            "gate_netlist_sha256":report["gate_netlist_sha256"],
            "motifs_replayed":len(current),"all_motifs":len(all_expected),
            "adder_pairs_replayed":len(claims),
            "scope":"2-state gate ANF verified for current FF-Q and any independent cut signals"}

def main():
    folder=Path(sys.argv[1]).resolve()
    report=Path(sys.argv[2]).resolve()
    dest=Path(sys.argv[3]).resolve()
    try:
        result=verify(folder,report)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,indent=2)+"\n")
        print("REAL6_INDEPENDENT_PASS",result["motifs_replayed"],
              "adder_pairs",result["adder_pairs_replayed"],flush=True)
        return 0
    except (Invalid,ValueError,KeyError,TypeError,IndexError,
            RecursionError,FileNotFoundError,MemoryError) as e:
        print(json.dumps({"status":"NOT_VERIFIED","reason":str(e)}),flush=True)
        return 2

if __name__=="__main__":raise SystemExit(main())
