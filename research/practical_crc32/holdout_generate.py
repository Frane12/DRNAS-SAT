#!/usr/bin/env python3
"""Prospective, not-yet-used MIX3 holdout families (2026-11-23).

Different algorithm families from the CRC-32 development set:
  GRAY: Gray encode/decode round trip vs independent wire identity
  LFSR: streaming fixed-register scrambler vs basis-derived parallel GF(2)
  ADDER: bitwise ripple-carry vs arithmetic '+' RTL

Each has an equal (UNSAT miter) and a deliberately faulty (SAT miter) case.
Frozen deterministic generation, independent Python function checks, exact
source/RTL hashes. No solver/solver-output information enters generation.
These are *synthetic digital-circuit holdouts*, not third-party chip designs.
"""
from __future__ import annotations
import argparse, hashlib, json, random
from pathlib import Path

SEED = 20261123
LFSR_SEED = 0xA5C3
MASK16 = 0xFFFF

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def lfsr(words: list[int]) -> list[int]:
    state=LFSR_SEED
    out=[]
    for bit in words:
        feedback=((state>>15)^(state>>13)^bit)&1
        state=((state<<1)&MASK16)|feedback
        out.append(feedback^((state>>3)&1))
    return out

def lfsr_rows(width: int) -> tuple[list[int],list[int]]:
    empty=lfsr([0]*width)
    masks=[0]*width
    for src in range(width):
        data=[0]*width;data[src]=1
        diff=lfsr(data)
        for out in range(width):
            if diff[out]^empty[out]:
                masks[out]|=1<<src
    for testseed in range(8):
        rng=random.Random(SEED+width+testseed)
        data=[rng.randrange(2) for _ in range(width)]
        observed=lfsr(data)
        parallel=[((m & sum(bit<<i for i,bit in enumerate(data))).bit_count()&1)^empty[j]
                  for j,m in enumerate(masks)]
        assert observed==parallel
    return masks,empty

def gray_rtl(w: int, faulty: bool) -> str:
    # Two structurally distinct computations: Gray decode vs identity wire.
    # The latter is intentionally not another Gray-decoder implementation.
    suffix=f" ^ {w}'h1" if faulty else ""
    return f"""
module left(input wire [{w-1}:0] data, output wire [{w-1}:0] out);
wire [{w-1}:0] gray;
assign gray = data ^ (data >> 1);
assign out[{w-1}] = gray[{w-1}];
genvar i;
generate for (i=0; i<{w-1}; i=i+1) begin: decode_gray
  assign out[i] = out[i+1] ^ gray[i];
end endgenerate
endmodule
module right(input wire [{w-1}:0] data, output wire [{w-1}:0] out);
assign out = data{suffix};
endmodule
module miter(input wire [{w-1}:0] data, output wire mismatch);
wire [{w-1}:0] a,b;
left left_inst(.data(data), .out(a));
right right_inst(.data(data), .out(b));
assign mismatch = |(a ^ b);
endmodule
"""

def lfsr_rtl(w: int, faulty: bool) -> str:
    rows,offset=lfsr_rows(w)
    right=[]
    for j,mask in enumerate(rows):
        suffix=" ^ 1'b1" if offset[j] else ""
        fault=" ^ 1'b1" if faulty and j==0 else ""
        right.append(f"assign out[{j}] = (^(data & {w}'h{mask:x})){suffix}{fault};")
    return f"""
module left(input wire [{w-1}:0] data, output reg [{w-1}:0] out);
reg [15:0] state;
reg feedback;
integer i;
always @* begin
  state = 16'hA5C3;
  out = {w}'d0;
  feedback = 1'b0;
  for (i=0; i<{w}; i=i+1) begin
    feedback = state[15] ^ state[13] ^ data[i];
    state = {{state[14:0], feedback}};
    out[i] = feedback ^ state[3];
  end
end
endmodule
module right(input wire [{w-1}:0] data, output wire [{w-1}:0] out);
{chr(10).join(right)}
endmodule
module miter(input wire [{w-1}:0] data, output wire mismatch);
wire [{w-1}:0] a,b;
left left_inst(.data(data), .out(a));
right right_inst(.data(data), .out(b));
assign mismatch = |(a ^ b);
endmodule
"""

def add_rtl(w: int, faulty: bool) -> str:
    # Mixed AND, OR, XOR. Different encoding than CRC and LFSR.
    suffix=f" ^ {w}'h1" if faulty else ""
    return f"""
module left(input wire [{2*w-1}:0] data, output wire [{w-1}:0] out);
wire [{w}:0] carry;
assign carry[0] = 1'b0;
genvar k;
generate for (k=0; k<{w}; k=k+1) begin: ripple
  wire a,b;
  assign a = data[k];
  assign b = data[k+{w}];
  assign out[k] = a ^ b ^ carry[k];
  assign carry[k+1] = (a & b) | (a & carry[k]) | (b & carry[k]);
end endgenerate
endmodule
module right(input wire [{2*w-1}:0] data, output wire [{w-1}:0] out);
assign out = (data[{w-1}:0] + data[{2*w-1}:{w}]){suffix};
endmodule
module miter(input wire [{2*w-1}:0] data, output wire mismatch);
wire [{w-1}:0] a,b;
left left_inst(.data(data), .out(a));
right right_inst(.data(data), .out(b));
assign mismatch = |(a ^ b);
endmodule
"""

def selftest() -> None:
    rng=random.Random(SEED)
    for w in (8,16,32):
        for _ in range(20):
            val=rng.getrandbits(w)
            gr=val^(val>>1)
            result=0
            for k in range(w-1,-1,-1):
                result|=(((gr>>k)&1)^((result>>(k+1))&1))<<k
            assert result==val
    for w in (8,16):
        m=(1<<w)-1
        for _ in range(30):
            a=rng.getrandbits(w);b=rng.getrandbits(w)
            carry=0;s=0
            for i in range(w):
                ai=(a>>i)&1;bi=(b>>i)&1
                s|=(ai^bi^carry)<<i
                carry=(ai&bi)|(ai&carry)|(bi&carry)
            assert (a+b)&m==s
    for w in (16,32,64): lfsr_rows(w)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=Path("holdout_rtl"))
    a=ap.parse_args()
    selftest()
    a.out.mkdir(parents=True,exist_ok=True)
    cohort=[("gray",w) for w in (8,16,32)] + \
           [("lfsr",w) for w in (16,32,64)] + \
           [("adder",w) for w in (8,16)]
    manifest=[]
    for fam,w in cohort:
        for faulty in (False,True):
            name=f"{fam}_{w}_{'fault' if faulty else 'equal'}"
            rtl={"gray":gray_rtl,"lfsr":lfsr_rtl,"adder":add_rtl}[fam](w,faulty)
            path=a.out/f"{name}.v"
            path.write_text(rtl)
            manifest.append({
                "case":name,"family":fam,"width":w,"fault":faulty,
                "expected":"SAT" if faulty else "UNSAT",
                "rtl":str(path),"rtl_sha256":sha(rtl.encode()),
                # The holdout checker is for post-run audit only, never solver routing.
            })
    (a.out/"manifest.json").write_text(json.dumps({
        "protocol":"MIX3_HOLDOUT_FROZEN_20261123",
        "design_seed":SEED,
        "family_count":len(cohort),"formula_count":len(manifest),
        "note":"Prospective unseen synthetic families; not a blind third-party hardware test.",
        "cases":manifest},indent=2)+"\n")
    print("HOLDOUT_GENERATED",len(manifest),"RTL circuits, selftests passed")

if __name__=="__main__":
    main()
