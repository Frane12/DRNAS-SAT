#!/usr/bin/env python3
"""Independent DELTA2-C induction checker.

Re-reads the actual original RTL with the strict source-grammar checker;
replays DELTA2-B original one-step/candidate certificates and direct N-step
symbolic recurrence; independently re-evaluates every K=1,2,4,8 block
coefficient by forward symbolic iteration; verifies raw block RTL matches
the source grammar's concrete recurrence; and runs the separately authored
DELTA1 synthesized-gate equivalence checker on each K-step block proof.

No imports from delta2c.py or delta2b_math.py. The *source grammar* and
Yosys translation are the declared trust boundary. Not general SV formal.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import sys

from delta2c_source_guard import parse_reference, RejectedSource
from delta2b_verify import replay as verify_base, VerificationError
from delta1_verify import verify as verify_gate, Invalid

class Rejected(Exception):
    pass

def reject(text):
    raise Rejected(text)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def canonical_raw(guard,k):
    # Distinctly authored canonicalization from a complete narrow grammar,
    # not accepting a free-form RTL statement merely by a substring match.
    w=guard["width"]
    state=guard["state"]; f=guard["feedback"]; i=guard["loop_index"]
    pol=guard["polynomial"]
    return (
        f"module delta2c_raw_{k}(input wire [{w-1}:0] a_state_in,"
        f"input wire [{k-1}:0] b_data,output reg [{w-1}:0] y_state);"
        f"reg [{w-1}:0] {state};reg {f};integer {i};always @* begin"
        f"{state}=a_state_in;{f}=1'b0;"
        f"for ({i}=0;{i}<{k};{i}={i}+1) begin"
        f"{f}={state}[0]^b_data[{i}];"
        f"{state}=({state}>>1)^({f}?{w}'h{pol:x}:{w}'d0);"
        f"end y_state={state};end endmodule"
    )


def direct_block(A,B,c,width,k):
    # Deliberately NOT using matrix exponentiation: complete symbolic
    # substitution for k local input variables and *arbitrary initial state*.
    rows=[1<<(j+1) for j in range(width)]
    for position in range(k):
        nxt=[]
        for j in range(width):
            value=c[j]
            mask=A[j]
            while mask:
                low=mask&-mask
                value^=rows[low.bit_length()-1]
                mask-=low
            if B[j]:
                value^=1<<(width+position+1)
            nxt.append(value)
        rows=nxt
    return rows


def replay(root:Path,source:Path,reference:str):
    if not source.is_file():reject("MISSING_ORIGINAL_SOURCE")
    guard=parse_reference(source.read_text(),reference)
    record=json.loads((root/"delta2c_certificate.json").read_text())
    if record["status"]!="CHECKED_LOCAL_BLOCKS_PENDING_INDEPENDENT_AUDIT":
        reject("UNEXPECTED_CERT_STAGE_STATUS")
    if record["source_sha256"]!=sha(source):
        reject("SOURCE_SHA_MISMATCH")
    if record["iterations"]!=guard["iterations"] or record["state_bits"]!=guard["width"]:
        reject("SOURCE_DIMENSIONS_CHANGED")
    if record["discovered_feedback"]!=hex(guard["polynomial"]):
        reject("TAP_CHANGE_DETECTED")
    if sorted(map(int,record["groups"].keys()))!=[1,2,4,8]:
        reject("INCOMPLETE_BLOCK_COVERAGE")
    base=root/"base"
    original=verify_base(base,source)
    if original["status"]!="CHECKED_COMPOSITIONAL":
        reject("BASE_NOT_REPLAYED")
    base_data=json.loads((base/"delta2b_composition.json").read_text())
    if (base_data["original_sha256"]!=sha(source)
        or base_data["schema"]["initial_state"]!=guard["initial"]
        or base_data["schema"]["iterations"]!=guard["iterations"]
        or base_data["schema"]["input_name"]!=guard["data"]
        or base_data["schema"]["output_name"]!=guard["out"]):
        reject("BASE_NOT_BOUND_TO_SOURCE")
    A=[int(x,16) for x in base_data["A_rows_hex"]]
    B=base_data["B_bits"];c=base_data["c_bits"]
    if A!=guard["A_rows"] or B!=guard["B_bits"] or c!=guard["c_bits"]:
        reject("SOURCE_SEMANTICS_DO_NOT_MATCH_GATES")
    finish=[int(x,16) for x in base_data["finish_masks_hex"]]
    if finish!=guard["finish_masks"]:
        reject("SOURCE_FINAL_OUTPUT_SEMANTICS_BAD")
    if record["candidate_verdict"]!=base_data["verdict"]:
        reject("CANDIDATE_VERDICT_MISMATCH")
    verified={}
    for k in (1,2,4,8):
        group=root/f"k{k}"
        details=json.loads((group/"block_meta.json").read_text())
        saved=record["groups"][str(k)]
        if saved!=details or details["group_size"]!=k:
            reject("CHANGED_BLOCK_METADATA")
        rtl=group/"block.v"
        proof=group/"proof"
        if sha(rtl)!=details["block_rtl_sha256"]:
            reject("BLOCK_RTL_HASH_MISMATCH")
        if sha(proof/"netlist.json")!=details["proof_netlist_sha256"]:
            reject("BLOCK_NETLIST_HASH_MISMATCH")
        if sha(proof/"delta1_certificate.json")!=details["proof_certificate_sha256"]:
            reject("BLOCK_CERTIFICATE_HASH_MISMATCH")
        text=rtl.read_text()
        match=re.search(r"\bmodule\s+delta2c_raw_"+str(k)+r"\s*\(.*?\bendmodule\b",
                        text,re.S)
        if not match:
            reject("RAW_BLOCK_MISSING")
        reduced=re.sub(r"\s+","",match[0])
        if reduced!=re.sub(r"\s+","",canonical_raw(guard,k)):
            reject("LOCAL_RAW_BLOCK_NOT_SOURCE_TRANSITION")
        # Verify the actual gate-netlist proof; the original source is tied
        # to the block only through the above strict grammar semantics.
        verdict=verify_gate(proof)
        if verdict.get("status")!="CHECKED_EQUIVALENT_NETLIST":
            reject("LOCAL_BLOCK_GATE_PROOF_FAILED")
        block=direct_block(A,B,c,guard["width"],k)
        if [int(x,16) for x in details["output_rows_hex"]]!=block:
            reject("LOCAL_BLOCK_FORMAL_COEFFICIENT_MISMATCH")
        verified[str(k)]={"status":verdict["status"],
                          "state_width":guard["width"],
                          "symbolic_inputs":k}
    return {
        "status":"CHECKED_RESTRICTED_INDUCTION",
        "source_grammar":guard["source_grammar"],
        "source_sha256":sha(source),
        "feedback_hex":hex(guard["polynomial"]),
        "induction_base":"state_0 equals literal initialization in source",
        "induction_step":"each restricted loop iteration equals verified same affine one-step relation",
        "induction_conclusion":"for 0<=k<=N, derived k-step relation is source-state relation",
        "N":guard["iterations"],"state_width":guard["width"],
        "base_derived_candidate_verdict":base_data["verdict"],
        "block_proofs":verified,
        "full_original_rtl_gate_audit":record["full_original_yosys_audit"],
        "trust_boundary":"restricted source grammar/semantic checker and Yosys 2-state gate proof"
    }


def main():
    try:
        root=Path(sys.argv[1]).resolve()
        source=Path(sys.argv[2]).resolve()
        reference=sys.argv[3] if len(sys.argv)>3 else "reference"
        result=replay(root,source,reference)
        (root/"delta2c_verification.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result),flush=True)
        return 0
    except (Rejected,RejectedSource,VerificationError,Invalid,
            FileNotFoundError,ValueError,KeyError,TypeError,IndexError,
            RecursionError,OverflowError) as ex:
        print(json.dumps({"status":"REJECTED","reason":str(ex)}),flush=True)
        return 2

if __name__=="__main__":
    sys.exit(main())
