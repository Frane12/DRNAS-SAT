#!/usr/bin/env python3
"""REAL2 standalone certificate checker (does NOT import real2_prove).

Trust boundary: a pinned/reviewed upstream Verilog source blob and the exact
restricted real1 generator's two-style harness semantics. This independently
reconstructs the harness, verifies SHA, checks the selected configuration and
replays the universal Boolean parity lemma (including exhaustive small masks).

NOT independent arbitrary-Verilog formal verification or DRAT/LRAT.
"""
from __future__ import annotations
import argparse,hashlib,json,itertools,random,re,time
from pathlib import Path
from real1_generate import CASES,wrapper as frozen_harness

UPSTREAM_BLOB="e3a472e3f280f3a697dee718b0416f2667181c00"

def sha(payload):return hashlib.sha256(payload).hexdigest()
def gitblob(payload):return hashlib.sha1(b"blob "+str(len(payload)).encode()+b"\x00"+payload).hexdigest()

class Invalid(Exception):pass

def replay(directory:Path,upstream:Path,harness:Path,case_name:str):
    started=time.perf_counter()
    cert=json.loads(directory.read_text())
    src=upstream.read_bytes()
    raw=harness.read_bytes()
    if gitblob(src)!=UPSTREAM_BLOB:
        raise Invalid("EXTERNAL_SOURCE_BLOB_NOT_APPROVED")
    if sha(src)!=cert.get("upstream_sha256") or sha(raw)!=cert.get("wrapper_sha256"):
        raise Invalid("CERTIFICATE_SOURCE_SHA_MISMATCH")
    if cert.get("upstream_git_blob_sha1")!=UPSTREAM_BLOB:
        raise Invalid("CERTIFICATE_BLOB_FINGERPRINT_BAD")
    matches=[]
    for c in CASES:
        for broken in (False,True):
            if case_name==c["id"]+("_fault" if broken else "_equal"):
                matches.append((c,broken))
    if len(matches)!=1:raise Invalid("CASE_NOT_FROZEN")
    c,broken=matches[0]
    if raw != frozen_harness(c,broken).encode("utf-8"):
        raise Invalid("WRAPPER_BYTES_DIFFER_FROM_APPROVED_GRAMMAR")
    # Independently verify specific external code is the audited source:
    # the immutable Git blob SHA identifies this exact source snapshot.
    # Style-generation shape is separately reviewed to establish the
    # universal parity identity, without evaluating lfsr_mask internals.
    if b"STYLE_INT == \"REDUCTION\"" not in src or b"STYLE_INT == \"LOOP\"" not in src:
        raise Invalid("MISSING_SOURCE_STYLE_GENERATOR")
    if src.count(b"lfsr_mask(n)")!=2 or src.count(b"lfsr_mask(n+LFSR_WIDTH)")!=2:
        raise Invalid("SHARED_MASK_LOOKUP_MISSING")
    if src.count(b"assign state_out[n] = ^({data_in, state_in} & mask);")!=1:
        raise Invalid("REDUCTION_STATE_NOT_APPROVED")
    if src.count(b"assign data_out[n] = ^({data_in, state_in} & mask);")!=1:
        raise Invalid("REDUCTION_DATA_NOT_APPROVED")
    expected="DIFFERENT_RESTRICTED_SOURCE" if broken else "EQUIVALENT_RESTRICTED_SOURCE"
    if cert.get("case")!=case_name or cert.get("status")!=expected:
        raise Invalid("BAD_STATUS")
    if cert.get("primary_input_bits")!=c["state_width"]+c["data_width"]:
        raise Invalid("BAD_INPUT_WIDTH")
    if cert.get("output_bits")!=c["state_width"]+c["data_width"]:
        raise Invalid("BAD_OUTPUT_WIDTH")
    if cert.get("harness_semantics",{}).get("wrapper_fault_xor_mask")!=("0x1" if broken else "0x0"):
        raise Invalid("BAD_FAULT_MASK")
    if cert.get("harness_semantics",{}).get("loop_style")!="LOOP" or (
        cert.get("harness_semantics",{}).get("second_style")!="REDUCTION"):
        raise Invalid("BAD_STYLE_LABEL")
    if cert.get("invariant")!="LOOP-XOR = reduction-XOR on identical lfsr_mask(j)":
        raise Invalid("BAD_PROOF_IDENTITY")
    # Replay the actual fundamental algebra using a mathematically distinct
    # implementation from the prover: integer parity vs list-based fold.
    # A finite test does NOT replace the universal identity (each bit
    # independently contributes iff mask_i=1).
    count=0
    for bits in range(1,7):
        for mask in range(1<<bits):
            for value in range(1<<bits):
                reduced=(mask&value).bit_count()&1
                incremental=0
                for i in range(bits):
                    if (mask>>i)&1:
                        incremental ^= (value>>i)&1
                if reduced!=incremental:
                    raise Invalid("PARITY_IDENTITY_FALSE")
                count+=1
    witness=cert.get("witness")
    if broken:
        if witness!={"data_hex":"0x0","state_hex":"0x0","mismatch":True}:
            raise Invalid("FAULT_WITNESS_INVALID")
        # ref XOR candidate = 1 at LSB for EVERY input, including zero.
    elif witness is not None:raise Invalid("EQUAL_CASE_WITH_WITNESS")
    return {"status":"CHECKED_RESTRICTED_PARITY_SOURCE",
            "source":"PINNED_EXTERNAL_VERILOG_BLOB",
            "case":case_name,"verdict":expected,
            "small_boolean_identity_tests":count,
            "scope":"reviewed fixed upstream source and canonical wrapper, two-state parity semantics",
            "verification_seconds":round(time.perf_counter()-started,6)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--upstream",type=Path,required=True)
    p.add_argument("--wrapper",type=Path,required=True)
    p.add_argument("--case",required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    try:
        result=replay(x.certificate,x.upstream,x.wrapper,x.case)
        x.out.write_text(json.dumps(result,indent=2)+"\n")
        print("REAL2_REPLAY",x.case,result["status"],result["verification_seconds"],flush=True)
        return 0
    except (Invalid,KeyError,ValueError,OSError,TypeError,UnicodeDecodeError) as e:
        x.out.write_text(json.dumps({"status":"REJECTED","reason":str(e)},indent=2)+"\n")
        print("REAL2_REPLAY_REJECTED",x.case,str(e),flush=True)
        return 2

if __name__=="__main__":raise SystemExit(main())
