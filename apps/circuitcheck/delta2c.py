#!/usr/bin/env python3
"""DELTA2-C: prove a single extracted step and K=2,4,8 transition blocks.

A narrow independent RTL-grammar guard checks *all* original reference
statements (not just detected cutpoint names), and derives the exact
2-state recurrence from them. Against independently verified DELTA2-B
one-step/final/candidate Yosys gate proofs, it checks the source semantics.
For each K generate a raw K-iteration RTL block and a matrix-composed
RTL block, formally compare them with DELTA1 and replay the netlist proof.
Then independent delta2c_verify.py rechecks all group equations and files.

Induction claim for this RESTRICTED RTL GRAMMAR:
  base: original source initializes s0;
  step: every loop iteration follows the guarded same recurrence;
  invariant: mathematical state after k iterations equals RTL state;
  hence result after N iterations equals the N-fold composition.
This is *not* a general SystemVerilog/4-state proof or a standard DRAT/LRAT.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from delta2c_source_guard import parse_reference, RejectedSource
from delta2b_math import affine_power, linear_apply
from delta2_auto import DiscoveryFailure

HERE=Path(__file__).resolve().parent
GROUPS=(1,2,4,8)

class InductionRejected(Exception):
    pass

def reject(message):
    raise InductionRejected(message)

def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(command,work,timeout=200):
    return subprocess.run([str(x) for x in command],cwd=work,
                          capture_output=True,text=True,timeout=timeout)

def validate_source_against_verified_step(guard,base):
    n=guard["width"]
    if base["schema"]["input_bits"] != guard["iterations"] or (
        base["schema"]["state_bits"]!=n or
        base["schema"]["initial_state"]!=guard["initial"] or
        base["schema"]["input_name"]!=guard["data"] or
        base["schema"]["output_name"]!=guard["out"]):
        reject("source schema not matched to verified step")
    A=[int(v,16) for v in base["A_rows_hex"]]
    B=base["B_bits"];c=base["c_bits"]
    if A!=guard["A_rows"] or B!=guard["B_bits"] or c!=guard["c_bits"]:
        reject("source semantics disagree with independently verified Yosys stage")
    if [int(v,16) for v in base["finish_masks_hex"]]!=guard["finish_masks"]:
        reject("source finish XOR differs from Yosys gate proof")
    return A,B,c


def block_rows(A:list[int],B:list[int],c:list[int],size:int):
    width=len(A)
    (linear,bias),mults=affine_power(A,c,size)
    masks=[((bias>>j)&1) | (linear[j]<<1) for j in range(width)]
    coefficient=sum((bit<<j) for j,bit in enumerate(B))
    for pos in range(size-1,-1,-1):
        b=coefficient
        while b:
            one=b&-b
            masks[one.bit_length()-1]^=1<<(width+pos+1)
            b-=one
        coefficient=linear_apply(A,coefficient)
    return masks,mults


def block_raw_rtl(guard,k):
    width=guard["width"]
    s=guard["state"];f=guard["feedback"];idx=guard["loop_index"]
    poly=guard["polynomial"]
    return (
        f"module delta2c_raw_{k}(input wire [{width-1}:0] a_state_in, "
        f"input wire [{k-1}:0] b_data, output reg [{width-1}:0] y_state);\n"
        f"  reg [{width-1}:0] {s};\n  reg {f};\n  integer {idx};\n"
        "  always @* begin\n"
        f"    {s} = a_state_in;\n    {f} = 1'b0;\n"
        f"    for ({idx}=0; {idx}<{k}; {idx}={idx}+1) begin\n"
        f"      {f} = {s}[0] ^ b_data[{idx}];\n"
        f"      {s} = ({s} >> 1) ^ ({f} ? {width}'h{poly:x} : {width}'d0);\n"
        "    end\n"
        f"    y_state = {s};\n  end\nendmodule\n"
    )


def block_math_rtl(width,k,rows):
    lines=[
        f"module delta2c_math_{k}(input wire [{width-1}:0] a_state_in, "
        f"input wire [{k-1}:0] b_data, output wire [{width-1}:0] y_state);"
    ]
    for j,m in enumerate(rows):
        s=(m>>1)&((1<<width)-1)
        inp=m>>(width+1)
        if inp>=(1<<k):reject("outside block input basis")
        expr=f"^(a_state_in & {width}'h{s:x}) ^ "
        expr+=f"^(b_data & {k}'h{inp:x})"
        if m&1:expr+=" ^ 1'b1"
        lines.append(f"  assign y_state[{j}] = {expr};")
    lines.append("endmodule")
    return "\n".join(lines)+"\n"


def perform(args):
    start=time.perf_counter()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=args.rtl.resolve()
    info={"engine":"DELTA2-C-RESTRICTED-INDUCTION",
          "status":"UNKNOWN","source_sha256":sha(source),
          "groups":{},"source_proof_scope":"only strict two-state RTL grammar",
          "full_original_yosys_audit":"NOT_RUN"}
    try:
        # Step 1: existing DELTA2-B already checks Yosys step / finish / candidate
        # and an independently implemented direct symbolic proof of N steps.
        t=time.perf_counter()
        basefolder=out/"base"
        command=[sys.executable,HERE/"delta2b.py","--rtl",source,
                 "--reference",args.reference,"--candidate",args.candidate,
                 "--out",basefolder]
        if args.full_rtl_audit:command+=["--full-rtl-audit"]
        result=run(command,out,300)
        (out/"base.log").write_text(result.stdout+"\n"+result.stderr)
        if result.returncode:
            reject("DELTA2B_BASE_PROOF_FAILED; inspect base.log")
        base=json.loads((basefolder/"delta2b_composition.json").read_text())
        breport=json.loads((basefolder/"delta2b_report.json").read_text())
        if not breport.get("independently_verified"):
            reject("BASE_INDEPENDENT_REPLAY_MISSING")
        if breport["source_sha256"]!=info["source_sha256"]:
            reject("BASE_SOURCE_SHA_MISMATCH")
        info["base_time_s"]=round(time.perf_counter()-t,6)
        info["full_original_yosys_audit"]=breport.get("source_audit","NOT_RUN")

        # Step 2: independent restricted-grammar source semantic derivation.
        t=time.perf_counter()
        guard=parse_reference(source.read_text(),args.reference)
        if guard["source_grammar"]!="RESTRICTED_REFLECTED_FEEDBACK_V1":
            reject("SOURCE_GRAMMAR_NOT_ACCEPTED")
        A,B,c=validate_source_against_verified_step(guard,base)
        info["source_guard_time_s"]=round(time.perf_counter()-t,6)
        info["iterations"]=guard["iterations"]
        info["state_bits"]=guard["width"]
        info["discovered_feedback"]=hex(guard["polynomial"])
        info["invariant"]="for all k<=N, state_after_k is the k-fold source-derived affine transition"
        info["candidate_verdict"]=base["verdict"]

        # Step 3: one-step, two-step, four-step, eight-step local gate proofs
        # for arbitrary initial state and arbitrary local input bits.
        for k in GROUPS:
            t=time.perf_counter()
            group=out/f"k{k}";group.mkdir(exist_ok=True)
            rows,mult=block_rows(A,B,c,k)
            local=group/"block.v"
            local.write_text(block_raw_rtl(guard,k)+"\n"+block_math_rtl(guard["width"],k,rows))
            proof=group/"proof"
            res=run([sys.executable,HERE/"delta1.py","--rtl",local,
                     "--reference",f"delta2c_raw_{k}",
                     "--candidate",f"delta2c_math_{k}",
                     "--out",proof],group,180)
            (group/"proof.log").write_text(res.stdout+"\n"+res.stderr)
            if res.returncode:
                reject(f"GROUP_{k}_NOT_PROVED; inspect k{k}/proof.log")
            replay=run([sys.executable,HERE/"delta1_verify.py",proof],group,180)
            (group/"replay.log").write_text(replay.stdout+"\n"+replay.stderr)
            if replay.returncode:
                reject(f"GROUP_{k}_REPLAY_FAILED")
            check=json.loads((proof/"delta1_verification.json").read_text())
            if check.get("status")!="CHECKED_EQUIVALENT_NETLIST":
                reject(f"GROUP_{k}_REPLAY_BAD_VERDICT")
            meta={"group_size":k,
                  "matrix_power_multiplications":mult,
                  "block_rtl_sha256":sha(local),
                  "proof_netlist_sha256":sha(proof/"netlist.json"),
                  "proof_certificate_sha256":sha(proof/"delta1_certificate.json"),
                  "proof_status":check["status"],"output_rows_hex":[hex(x) for x in rows],
                  "proof_elapsed_s":round(time.perf_counter()-t,6)}
            (group/"block_meta.json").write_text(json.dumps(meta,indent=2)+"\n")
            info["groups"][str(k)]=meta
            print(f"DELTA2C_GROUP {k} EXACT_GATE_PROOF_PASS {meta['proof_elapsed_s']}s",flush=True)

        info["source_guard"]="SOURCE_STEP_SEMANTICS_CHECKED"
        info["status"]="CHECKED_LOCAL_BLOCKS_PENDING_INDEPENDENT_AUDIT"
        (out/"delta2c_certificate.json").write_text(json.dumps(info,indent=2)+"\n")

        # Step 4: independent total check including original restrictive source
        # and direct substitution, without importing the DELTA2-C math engine.
        t=time.perf_counter()
        independent=run([sys.executable,HERE/"delta2c_verify.py",
                         out,source,args.reference],out,180)
        (out/"independent.log").write_text(independent.stdout+"\n"+independent.stderr)
        if independent.returncode:
            reject("INDEPENDENT_INDUCTION_CHECK_REJECTED")
        proof_status=json.loads((out/"delta2c_verification.json").read_text())
        if proof_status["status"]!="CHECKED_RESTRICTED_INDUCTION":
            reject("INDEPENDENT_INDUCTION_CHECK_BAD_STATUS")
        info["independent_audit_s"]=round(time.perf_counter()-t,6)
        info["status"]="CHECKED_RESTRICTED_INDUCTION"
    except (InductionRejected,RejectedSource,DiscoveryFailure,ValueError,KeyError,
            TypeError,IndexError,FileNotFoundError,subprocess.TimeoutExpired,
            MemoryError,RecursionError,OverflowError) as ex:
        info["status"]="UNKNOWN"
        info["reason"]=str(ex)
    info["total_elapsed_s"]=round(time.perf_counter()-start,6)
    (out/"delta2c_report.json").write_text(json.dumps(info,indent=2)+"\n")
    print("DELTA2C_SUMMARY",json.dumps({k:v for k,v in info.items() if k!="groups"}),flush=True)
    return 0 if info["status"]=="CHECKED_RESTRICTED_INDUCTION" else 2


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--rtl",required=True,type=Path)
    parser.add_argument("--reference",default="reference")
    parser.add_argument("--candidate",default="candidate")
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument("--full-rtl-audit",action="store_true")
    args=parser.parse_args()
    return perform(args)


if __name__=="__main__":
    sys.exit(main())
