#!/usr/bin/env python3
"""Separate DELTA2-B compositional verifier, no DELTA2-B math imports.

Replays the one-step/finish/candidate synthesized Yosys certificates using
the separately authored DELTA1 checker, then recomputes N-step output ANFs
with direct sequential symbolic substitution, independently of matrix powers.
Validates source, netlists, candidate, output coverage and every coefficient.
A PASS establishes compositional validity *conditional* on RTL loop extraction,
not raw-Verilog source equivalence or DRAT/LRAT.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from delta1_verify import verify as verify_netlist, Invalid

class VerificationError(Exception):
    pass

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fail(msg):
    raise VerificationError(msg)

def replay(folder:Path,source:Path):
    info=json.loads((folder/"delta2b_composition.json").read_text())
    sch=info["schema"]
    count,width,outputs=(sch["iterations"],sch["state_bits"],sch["output_bits"])
    if count!=sch["input_bits"] or count<1 or width<1 or outputs<1:
        fail("invalid declared dimensions")
    if info["original_sha256"]!=sha(source):
        fail("ORIGINAL_SOURCE_SHA_MISMATCH")
    if info["derived_model_sha256"]!=sha(folder/"drnas_delta2_model.v"):
        fail("DERIVED_MODEL_SHA_MISMATCH")
    files=[("drnas_delta2_step","step_meta","step_masks_hex",width),
           ("drnas_delta2_finish","finish_meta","finish_masks_hex",outputs),
           (sch.get("candidate_module","candidate"),"candidate_meta","candidate_masks_hex",outputs)]
    # Candidate's original module name is not hardcoded: the folder contains
    # one candidate proof certificate from the metadata, bound to a netlist.
    candidate_name = info.get("candidate_name")
    if not candidate_name:
        fail("candidate name must be authenticated")
    files[2]=(candidate_name,"candidate_meta","candidate_masks_hex",outputs)
    verified={}
    for name,metakey,coeffkey,count_out in files:
        location=folder/("cert_"+name)
        meta=info[metakey]
        if not location.is_dir():
            fail("MISSING_CERT_DIR "+name)
        if sha(location/"netlist.json")!=meta["netlist_sha256"]:
            fail("NETLIST_HASH_MISMATCH "+name)
        if sha(location/"delta1_certificate.json")!=meta["certificate_sha256"]:
            fail("CERT_HASH_MISMATCH "+name)
        cert=json.loads((location/"delta1_certificate.json").read_text())
        result=verify_netlist(location)
        if result.get("status")!="CHECKED_EQUIVALENT_NETLIST":
            fail("AFFINE_CELL_REPLAY_FAILED "+name)
        coefficients=[int(row["reference_mask"],16) for row in cert["checked_outputs"]]
        asserted=[int(x,16) for x in info[coeffkey]]
        if len(asserted)!=count_out or coefficients!=asserted:
            fail("AFFINE_COEFFICIENT_TAMPERING "+name)
        verified[name]={"cells_checked":result["replayed_output_bits"],
                        "netlist_sha256":meta["netlist_sha256"]}
    n=width
    stage=[int(s,16) for s in info["step_masks_hex"]]
    A=[int(x,16) for x in info["A_rows_hex"]]
    B=info["B_bits"]
    c=info["c_bits"]
    if len(A)!=n or len(B)!=n or len(c)!=n or len(stage)!=n:
        fail("stage matrix wrong dimensions")
    for j,m in enumerate(stage):
        if (m&1)!=c[j] or ((m>>1)&((1<<n)-1))!=A[j] or (
            m>>(n+1))!=B[j]:
            fail("stage A/B/c not derived from exact gate proof")
        if A[j]>=1<<n or B[j] not in (0,1) or c[j] not in (0,1):
            fail("non-affine row unexpected")
    initial=sch["initial_state"]
    if not isinstance(initial,int) or not 0<=initial<(1<<n):
        fail("invalid initial state")
    # Independently iterate all input variables as formal symbols.
    # This is the straightforward old DELTA2-A recurrence; no matrix powers.
    state=[(initial>>j)&1 for j in range(n)]
    for k in range(count):
        nextstate=[]
        for j in range(n):
            out=c[j]
            row=A[j]
            while row:
                bit=row&-row
                out^=state[bit.bit_length()-1]
                row-=bit
            if B[j]:
                out^=1<<(k+1)
            nextstate.append(out)
        state=nextstate
    finish=[int(x,16) for x in info["finish_masks_hex"]]
    result=[]
    for mask in finish:
        m=mask>>1
        if m>>(n):
            fail("finish polynomial exceeds state variables")
        out=mask&1
        while m:
            one=m&-m
            out^=state[one.bit_length()-1]
            m-=one
        result.append(out)
    asserted=[int(x,16) for x in info["final_model_masks_hex"]]
    if len(asserted)!=outputs or result!=asserted:
        fail("N_STEP_COMPOSITION_COEFFICIENT_MISMATCH")
    can=[int(x,16) for x in info["candidate_masks_hex"]]
    delta=[a^b for a,b in zip(result,can)]
    if [int(x,16) for x in info["difference_masks_hex"]]!=delta:
        fail("OUTPUT_DELTA_MISMATCH")
    first=next((i for i,d in enumerate(delta) if d),None)
    if first!=info["first_difference_bit"]:
        fail("FIRST_DIFFERENCE_MISMATCH")
    expected="DIFFERENT_EXTRACTED_MODEL" if first is not None else "EQUIVALENT_EXTRACTED_MODEL"
    if expected!=info["verdict"]:
        fail("VERDICT_MISMATCH")
    return {"status":"CHECKED_COMPOSITIONAL","verdict":expected,
            "steps_replayed":count,"state_bits":width,
            "output_bits_replayed":outputs,
            "source_scope":"conditional on strict RTL loop cut extraction",
            "verified_gate_proofs":verified,
            "full_original_source_audit_included":False}

def main():
    try:
        folder=Path(sys.argv[1]).resolve()
        src=Path(sys.argv[2]).resolve()
        result=replay(folder,src)
        (folder/"delta2b_verification.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result),flush=True)
        return 0
    except (VerificationError,Invalid,ValueError,KeyError,TypeError,
            IndexError,FileNotFoundError,RecursionError,OverflowError) as ex:
        print(json.dumps({"status":"REJECTED","reason":str(ex)}),flush=True)
        return 2

if __name__=="__main__":
    sys.exit(main())
