#!/usr/bin/env python3
"""REAL2: sound, narrow syntax-certified parity equivalence of external FPGA IP.

Proof theorem for every Boolean mask M and input vector X:
  ^(X & M) = XOR_{i where M[i]=1} X[i].
The externally published Verilog contains both forms and calls the SAME
lfsr_mask(n) function in both branches. We accept *only* a canonical
enumerated source syntax and canonical frozen harnesses; all other RTL gives
UNKNOWN. No unrolling or Yosys required. A difference in wrapper output
bit 0 is proved with an all-zero input witness independent of M.

This is a restricted-source semantic proof, NOT a general HDL verification
algorithm, formal proof of CRC specification, or full 4-state Verilog proof.
"""
from __future__ import annotations
import argparse,hashlib,json,re,time
from pathlib import Path
from real1_generate import CASES

PINNED_BLOB="e3a472e3f280f3a697dee718b0416f2667181c00"
SUPPORTED={c["id"]:c for c in CASES}

class Unknown(Exception):pass

def sha(data):return hashlib.sha256(data).hexdigest()
def blob(data):return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def squash(s):
    s=re.sub(r"/\*[\s\S]*?\*/|//[^\n]*","",s)
    return re.sub(r"\s+","",s)

# Complete active generate branches, not a fragment that might overlook
# a second assignment or an altered extra operation. Comments/whitespace
# are not semantically significant in this enumerated subset.
_CANONICAL_STYLES = r"""
genvar n;
generate
if (STYLE_INT == "REDUCTION") begin
for (n = 0; n < LFSR_WIDTH; n = n + 1) begin : lfsr_state
 wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = lfsr_mask(n);
 assign state_out[n] = ^({data_in, state_in} & mask);
end
for (n = 0; n < DATA_WIDTH; n = n + 1) begin : lfsr_data
 wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = lfsr_mask(n+LFSR_WIDTH);
 assign data_out[n] = ^({data_in, state_in} & mask);
end
end else if (STYLE_INT == "LOOP") begin
for (n = 0; n < LFSR_WIDTH; n = n + 1) begin : lfsr_state
 wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = lfsr_mask(n);
 reg state_reg;
 assign state_out[n] = state_reg;
 integer i;
 always @* begin
 state_reg = 1'b0;
 for (i = 0; i < LFSR_WIDTH; i = i + 1) begin
   if (mask[i]) begin
     state_reg = state_reg ^ state_in[i];
   end
 end
 for (i = 0; i < DATA_WIDTH; i = i + 1) begin
   if (mask[i+LFSR_WIDTH]) begin
     state_reg = state_reg ^ data_in[i];
   end
 end
 end
end
for (n = 0; n < DATA_WIDTH; n = n + 1) begin : lfsr_data
 wire [LFSR_WIDTH+DATA_WIDTH-1:0] mask = lfsr_mask(n+LFSR_WIDTH);
 reg data_reg;
 assign data_out[n] = data_reg;
 integer i;
 always @* begin
 data_reg = 1'b0;
 for (i = 0; i < LFSR_WIDTH; i = i + 1) begin
   if (mask[i]) begin
     data_reg = data_reg ^ state_in[i];
   end
 end
 for (i = 0; i < DATA_WIDTH; i = i + 1) begin
   if (mask[i+LFSR_WIDTH]) begin
     data_reg = data_reg ^ data_in[i];
   end
 end
 end
end
end else begin
 initial begin
   $error("Error: unknown style setting!");
   $finish;
 end
end
endgenerate
"""

def verify_real_source(upstream:bytes):
    if blob(upstream)!=PINNED_BLOB:
        raise Unknown("UPSTREAM_GIT_BLOB_SHA_MISMATCH")
    s=squash(upstream.decode("utf-8"))
    at=s.find("genvarn;generate")
    if at==-1:raise Unknown("NO_UNCHANGED_GENERATE_BRANCH")
    end=s.find("endgenerateendmodule",at)
    if end==-1:raise Unknown("GENERATE_BOUNDARY_NOT_FOUND")
    actual=s[at:end+len("endgenerate")]
    expected=squash(_CANONICAL_STYLES)
    if actual!=expected:raise Unknown("REDUCTION_LOOP_SYNTAX_CHANGED")
    # Explicit param selection: "AUTO" mapping is irrelevant to our explicit
    # styles, but ensure the source does not force a different STYLE_INT.
    if 'parameterSTYLE_INT=(STYLE=="AUTO")?"REDUCTION":STYLE;' not in s:
        raise Unknown("STYLE_INT_CONFIGURATION_CHANGED")
    if 'parameterSTYLE_INT=(STYLE=="AUTO")?"LOOP":STYLE;' not in s:
        raise Unknown("STYLE_INT_CONFIGURATION_CHANGED")
    if s.count("function[LFSR_WIDTH+DATA_WIDTH-1:0]lfsr_mask(")!=1:
        raise Unknown("MASK_FUNCTION_MISSING_OR_AMBIGUOUS")
    return {"gate_proof":"PARITY_OF_SAME_MASK",
            "styles":"REDUCTION_EQUALS_LOOP_FOR_ALL_MASK_AND_INPUTS",
            "output_bank_count":2,"source_git_blob_sha1":blob(upstream)}

def parse_case(name):
    for c in CASES:
        if name==c["id"]+"_equal":return c,False
        if name==c["id"]+"_fault":return c,True
    raise Unknown("NON_FROZEN_CASE_NAME")

def independent_harness_semantics(raw:str,c:dict,fault:bool):
    # Fail-closed exact syntax with data-driven widths and params. The
    # original upstream DUT remains identical for both instances; the
    # wrapper injects ONLY an optional single output bit flip.
    # This is intentionally independent of the real1_generate.wrapper
    # implementation: construct the accepted semantic grammar here.
    w,n=c["state_width"],c["data_width"]
    k=n+w
    fmt=f"lfsr#(.LFSR_WIDTH({w}),.LFSR_POLY({c['poly']}),.LFSR_CONFIG(\"{c['config']}\"),.DATA_WIDTH({n}),.REVERSE({c['reverse']}),.STYLE"
    reference=(
        f"modulereference(inputwire[{n-1}:0]data,inputwire[{w-1}:0]state,"
        f"outputwire[{k-1}:0]out);"
        f"wire[{w-1}:0]ref_state;wire[{n-1}:0]ref_data;"
        +fmt+"(\"LOOP\"))block_ref(.data_in(data),.state_in(state),"
        ".data_out(ref_data),.state_out(ref_state));"
        "assignout={ref_data,ref_state};endmodule"
    )
    candidate=(
        f"modulecandidate(inputwire[{n-1}:0]data,inputwire[{w-1}:0]state,"
        f"outputwire[{k-1}:0]out);"
        f"wire[{w-1}:0]impl_state;wire[{n-1}:0]impl_data;"
        +fmt+"(\"REDUCTION\"))block_impl(.data_in(data),.state_in(state),"
        ".data_out(impl_data),.state_out(impl_state));"
        f"assignout={{impl_data,impl_state}}"
        +(f"^{k}'h1" if fault else "")+
        ";endmodule"
    )
    miter=(
        f"modulemiter(inputwire[{n-1}:0]data,inputwire[{w-1}:0]state,"
        "outputwiremismatch);"
        f"wire[{k-1}:0]a,b;"
        "referencer(.data(data),.state(state),.out(a));"
        "candidatec(.data(data),.state(state),.out(b));"
        "assignmismatch=|(a^b);endmodule"
    )
    actual=squash(raw)
    expected=reference+candidate+miter
    if actual!=expected:
        raise Unknown("TEST_WRAPPER_NOT_IN_RESTRICTED_GRAMMAR")
    return {"loop_style":"LOOP","second_style":"REDUCTION",
            "data_bits":n,"state_bits":w,"total_outputs":k,
            "wrapper_fault_xor_mask":"0x1" if fault else "0x0",
            "formula":"ref_out XOR impl_out = 1 (LSB) if fault else 0"}

def prove(upstream:bytes,wrapper:bytes,case_name:str):
    t0=time.perf_counter()
    c,fault=parse_case(case_name)
    source=verify_real_source(upstream)
    harness=independent_harness_semantics(wrapper.decode("utf-8"),c,fault)
    verdict="DIFFERENT_RESTRICTED_SOURCE" if fault else "EQUIVALENT_RESTRICTED_SOURCE"
    # Exact witness for wrapper XOR 1: choose zero input/state. Since
    # ref and impl have the same output for all possible masks, their LSB
    # values differ regardless of computed internal CRC/PRBS state.
    witness={"data_hex":"0x0","state_hex":"0x0","mismatch":True} if fault else None
    result={"method":"DRNAS-REAL2-PARITY-RESTRICTED-SOURCE-v1",
        "status":verdict,"case":case_name,"output_bits":harness["total_outputs"],
        "primary_input_bits":harness["data_bits"]+harness["state_bits"],
        "upstream_git_blob_sha1":source["source_git_blob_sha1"],
        "upstream_sha256":sha(upstream),"wrapper_sha256":sha(wrapper),
        "invariant":"LOOP-XOR = reduction-XOR on identical lfsr_mask(j)",
        "source_semantics":source,"harness_semantics":harness,
        "witness":witness,
        "limitations":"specific pinned external source + fully checked narrow harness syntax; no general HDL verification",
        "elapsed_seconds":round(time.perf_counter()-t0,6)}
    return result

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--upstream",type=Path,required=True)
    a.add_argument("--wrapper",type=Path,required=True)
    a.add_argument("--case",required=True)
    a.add_argument("--out",type=Path,required=True)
    x=a.parse_args()
    x.out.parent.mkdir(parents=True,exist_ok=True)
    try:
        result=prove(x.upstream.read_bytes(),x.wrapper.read_bytes(),x.case)
        x.out.write_text(json.dumps(result,indent=2)+"\n")
        print("REAL2_PROOF",x.case,result["status"],result["elapsed_seconds"],flush=True)
        return 0
    except (Unknown,ValueError,IndexError,UnicodeDecodeError) as ex:
        x.out.write_text(json.dumps({"status":"UNKNOWN","reason":str(ex),"case":x.case},indent=2)+"\n")
        print("REAL2_UNKNOWN",x.case,str(ex),flush=True)
        return 2

if __name__=="__main__":raise SystemExit(main())
