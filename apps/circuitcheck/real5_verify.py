#!/usr/bin/env python3
"""Independent REAL5 check: prove each cross-cone relation from REAL4 netlist.

Does NOT import REAL5 discovery or Gaussian elimination. Inputs are a
REAL4 independently replayed gate certificate and a claimed relation
list. Independently recomputes the XOR of each contributing probe's
GF(2) variables using SET SYMMETRIC DIFFERENCE. The nonlinear cut
variables must cancel exactly; full relationship must match claim.
No whole-circuit global SAT/UNSAT, temporal or source-language claim.
"""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
from real4_verify import proof_replay

class Invalid(Exception):pass
def fail(reason):raise Invalid(reason)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def as_set(mask):
    value=int(mask,16)
    if value<0:fail("NEGATIVE_AFFINE_MASK")
    variables=set()
    if value&1:variables.add(-1)
    v=value>>1
    while v:
        bit=v&-v
        variables.add(bit.bit_length()-1)
        v-=bit
    return variables

def verify(folder:Path, relations_file:Path):
    checked=proof_replay(folder)
    if checked["status"]!="CHECKED_LOCAL_AFFINE_GATE_IDENTITIES":
        fail("REAL4_CERT_NOT_REPLAYABLE")
    cert=json.loads((folder/"real4_certificate.json").read_text())
    report=json.loads(relations_file.read_text())
    if report.get("netlist_sha256")!=sha(folder/"netlist.json"):
        fail("ORIGINAL_NETLIST_SHA_MISMATCH")
    if report.get("real4_certificate_sha256")!=sha(folder/"real4_certificate.json"):
        fail("ORIGINAL_GATE_CERT_SHA_MISMATCH")
    if report.get("original_real4_replay")!="CHECKED_LOCAL_AFFINE_GATE_IDENTITIES":
        fail("UNVERIFIED_PROVENANCE")
    input_count=len(cert["basis"])
    probes={}
    for p in cert["probes"]:
        if p["status"] in ("GLOBAL_AFFINE_ONE_STEP","LOCAL_AFFINE_WITH_CUTS"):
            key=(p["kind"],p["name"],p["position"],p["yosys_bit"])
            if key in probes:fail("DUPLICATE_PROBE")
            probes[key]=p
    relations=report.get("relations")
    if not isinstance(relations,list) or len(relations)>64:fail("RELATION_BUDGET")
    seen=set()
    proven=[]
    for index,r in enumerate(relations):
        terms=r.get("probes")
        if not isinstance(terms,list) or not 2<=len(terms)<=8:
            fail("INVALID_RELATION_ARITY")
        xor=set()
        combined_cuts=set()
        wires=set()
        internal=False
        for p in terms:
            key=(p.get("kind"),p.get("name"),p.get("position"),p.get("yosys_bit"))
            if key not in probes:fail("NONEXISTENT_OR_UNKNOWN_PROBE")
            if key[3] in wires:fail("REPEATED_PHYSICAL_OUTPUT_BIT")
            wires.add(key[3])
            if key[0]=="internal_xor":internal=True
            ps=as_set(probes[key]["mask_hex"])
            xor.symmetric_difference_update(ps)
            combined_cuts.update(x for x in ps if x>=input_count)
        keyset=frozenset(wires)
        if keyset in seen:fail("DUPLICATE_RELATIONAL_IDENTITY")
        seen.add(keyset)
        leftover_cut={x for x in xor if x>=input_count}
        if leftover_cut:fail("NONLINEAR_CUT_DEPENDENCE_REMAINS")
        if not combined_cuts:fail("NO_ACTUAL_NONLINEAR_CANCEL")
        data_terms={v for v in xor if 0<=v<input_count}
        if len(data_terms)<2:fail("TRIVIAL_INPUT_SIDE")
        ordinary={v for v in xor if v<input_count}
        target=as_set(r.get("output_xor_mask_hex","0x0"))
        if ordinary!=target:fail("FALSE_RELATIONAL_RHS")
        if r.get("ordinary_input_coefficient_weight")!=len(data_terms):
            fail("FALSE_INPUT_WEIGHT")
        if r.get("nonlinear_cutpoints_canceled")!=len(combined_cuts):
            fail("FALSE_CUT_CANCEL_COUNT")
        if r.get("canceled_cut_indices")!=sorted(combined_cuts):
            fail("FALSE_CUT_IDENTIFIER_SET")
        if r.get("term_count")!=len(terms):
            fail("FALSE_ARITY_METADATA")
        expected_type=("INCLUDES_SAMPLED_INTERNAL_XOR" if internal
                       else "EXTERNAL_OUTPUT_AND_FF_D")
        if r.get("relation_type")!=expected_type:fail("MISLABELED_RELATION_SCOPE")
        proven.append({
            "number":index,"type":expected_type,
            "original_output_bits":len(terms),
            "canceled_nonlinear_gates":len(combined_cuts),
            "remaining_input_coefficients":len(data_terms),
            "original_real4_gate_netlist_sha256":report["netlist_sha256"]
        })
    if report.get("status")!=("RELATIONAL_IDENTITIES_FOUND" if proven
                              else "NO_NONTRIVIAL_CANCELLATION_FOUND"):
        fail("FALSE_VERDICT")
    return {"status":"CHECKED_GF2_CROSSCONE_RELATIONS",
            "relations_replayed":len(proven),"certificates":proven,
            "scope":"exact one-step Boolean identities under Yosys gate semantics; no original-source or temporal proof"}

def main():
    folder=Path(sys.argv[1]);input_report=Path(sys.argv[2])
    out=Path(sys.argv[3])
    try:
        result=verify(folder,input_report)
        out.write_text(json.dumps(result,indent=2)+"\n")
        print("REAL5_INDEPENDENT_RELATIONS_PASS",result["relations_replayed"],flush=True)
        return 0
    except (Invalid,ValueError,TypeError,KeyError,IndexError,
            FileNotFoundError,MemoryError,RecursionError) as e:
        print(json.dumps({"status":"NOT_VERIFIED","reason":str(e)},flush=True))
        return 2
if __name__=="__main__":sys.exit(main())
