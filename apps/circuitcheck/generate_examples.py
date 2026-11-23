#!/usr/bin/env python3
"""Generate reproducible real RTL examples for DRNAS CircuitCheck CI and demo.

CRC-32 and LFSR are real linear-feedback algorithms, not tautological CNF
fixtures. The two implementations use serial shift/update vs independently
computed parallel basis/parity expressions. The faulty copy flips an output.
"""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path

POLY = 0xEDB88320
MASK = (1<<32)-1
SEED = 0xA5C3

def crc(bits: list[int]) -> int:
    state=MASK
    for bit in bits:
        f=(state&1)^bit
        state=(state>>1)^(POLY if f else 0)
    return state^MASK

def lfsr(bits: list[int]) -> list[int]:
    state=SEED
    result=[]
    for bit in bits:
        feedback=((state>>15)^(state>>13)^bit)&1
        state=((state<<1)&0xffff)|feedback
        result.append(feedback^((state>>3)&1))
    return result

def signatures(func, width:int):
    zero=func([0]*width)
    if isinstance(zero,int):zero=[(zero>>j)&1 for j in range(32)]
    outputs=len(zero)
    masks=[0]*outputs
    for k in range(width):
        x=[0]*width;x[k]=1
        v=func(x)
        if isinstance(v,int):v=[(v>>j)&1 for j in range(32)]
        for j in range(outputs):
            if v[j]^zero[j]:masks[j]|=1<<k
    return masks,zero

def make_crc(width:int,fault:bool) -> str:
    rows,off=signatures(crc,width)
    terms=[]
    for j,(mask,c) in enumerate(zip(rows,off)):
        terms.append(f"assign out[{j}] = (^(data & {width}'h{mask:x})) "+
                     ("^ 1'b1 " if c else "")+
                     ("^ 1'b1 " if fault and j==0 else "")+";")
    return f"""
module reference(input wire [{width-1}:0] data, output reg [31:0] out);
reg [31:0] state;
reg f;
integer i;
always @* begin
  state = 32'hFFFFFFFF;
  f = 1'b0;
  for (i=0; i<{width}; i=i+1) begin
    f = state[0] ^ data[i];
    state = (state>>1) ^ (f ? 32'hEDB88320 : 32'd0);
  end
  out = state ^ 32'hFFFFFFFF;
end
endmodule
module candidate(input wire [{width-1}:0] data, output wire [31:0] out);
{chr(10).join(terms)}
endmodule
"""

def make_lfsr(width:int,fault:bool) -> str:
    rows,off=signatures(lfsr,width)
    terms=[]
    for j,(mask,c) in enumerate(zip(rows,off)):
        terms.append(f"assign out[{j}] = (^(data & {width}'h{mask:x})) "+
                     ("^ 1'b1 " if c else "")+
                     ("^ 1'b1 " if fault and j==0 else "")+";")
    return f"""
module reference(input wire [{width-1}:0] data, output reg [{width-1}:0] out);
reg [15:0] state;
reg feedback;
integer i;
always @* begin
  state = 16'hA5C3;
  feedback = 1'b0;
  out = {width}'d0;
  for (i=0; i<{width}; i=i+1) begin
    feedback = state[15] ^ state[13] ^ data[i];
    state = {{state[14:0],feedback}};
    out[i] = feedback ^ state[3];
  end
end
endmodule
module candidate(input wire [{width-1}:0] data, output wire [{width-1}:0] out);
{chr(10).join(terms)}
endmodule
"""

def make_gray(width:int,fault:bool) -> str:
    return f"""
module reference(input wire [{width-1}:0] data, output wire [{width-1}:0] out);
assign out = data;
endmodule
module candidate(input wire [{width-1}:0] data, output wire [{width-1}:0] out);
wire [{width-1}:0] gray;
wire [{width-1}:0] decoded;
assign gray = data ^ (data >> 1);
assign decoded[{width-1}] = gray[{width-1}];
genvar i;
generate for(i=0;i<{width-1};i=i+1) begin: d
   assign decoded[i] = decoded[i+1] ^ gray[i];
end endgenerate
assign out = decoded {"^ "+str(width)+"'h1" if fault else ""};
endmodule
"""

def make_nonlinear(width:int,fault:bool) -> str:
    return f"""
module reference(input wire [{2*width-1}:0] data, output wire [{width-1}:0] out);
assign out = data[{width-1}:0] & data[{2*width-1}:{width}];
endmodule
module candidate(input wire [{2*width-1}:0] data, output wire [{width-1}:0] out);
assign out = (data[{width-1}:0] & data[{2*width-1}:{width}]) {"^ "+str(width)+"'h1" if fault else ""};
endmodule
"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,default=Path("examples"))
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for kind,width in (("gray",32),("lfsr",64),("crc",8),("crc",32),("nonlinear",16)):
        for fault in (False,True):
            src={"gray":make_gray,"lfsr":make_lfsr,"crc":make_crc,
                 "nonlinear":make_nonlinear}[kind](width,fault)
            filename=f"{kind}_{width}_{'fault' if fault else 'equal'}.v"
            (a.out/filename).write_text(src)
            manifest.append({"file":filename,"kind":kind,"width":width,
                             "expected":"DIFFERENT_NETLIST" if fault else "EQUIVALENT_NETLIST",
                             "sha256":hashlib.sha256(src.encode()).hexdigest()})
    sequential="""
module reference(input wire clk, input wire data, output reg out);
always @(posedge clk) out <= data;
endmodule
module candidate(input wire clk, input wire data, output wire out);
assign out=data;
endmodule
"""
    (a.out/"sequential_unknown.v").write_text(sequential)
    manifest.append({"file":"sequential_unknown.v","kind":"sequential","width":1,
                    "expected":"UNKNOWN_UNSUPPORTED",
                    "sha256":hashlib.sha256(sequential.encode()).hexdigest()})
    (a.out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("CircuitCheck examples frozen:",len(manifest))

if __name__=="__main__":
    main()
