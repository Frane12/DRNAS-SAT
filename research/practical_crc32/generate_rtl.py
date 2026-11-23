#!/usr/bin/env python3
"""Build real CRC-32 Ethernet Verilog comparison circuits for Yosys.
The direct serial LFSR and separately derived GF(2) parallel netlist
have the same observable CRC output; a third variant injects a fault.
No pre-computed XOR annotations are passed to Yosys.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

POLY=0xEDB88320
MASK=(1<<32)-1

def crc_for_bits(bits):
    c=MASK
    for bit in bits:
        f=(c&1)^bit
        c=(c>>1)^(POLY if f else 0)
    return c^MASK

def equations(nbits):
    zero=crc_for_bits([0]*nbits)
    rows=[0]*32
    for i in range(nbits):
        v=[0]*nbits
        v[i]=1
        diff=crc_for_bits(v)^zero
        for j in range(32):
            if (diff>>j)&1:
                rows[j]|=1<<i
    return rows,zero

def write_one(nbytes,fault,out):
    nbits=8*nbytes
    rows,offset=equations(nbits)
    suffix='faulty' if fault else 'equal'
    name=f'ethernet_crc32_{nbytes}byte_{suffix}'
    serial=f"""
module crc_serial(input wire [{nbits-1}:0] data, output wire [31:0] crc);
reg [31:0] c;
reg feedback;
integer i;
always @* begin
    c = 32'hFFFFFFFF;
    feedback = 1'b0;
    for (i = 0; i < {nbits}; i=i+1) begin
        feedback = c[0] ^ data[i];
        c = (c >> 1) ^ (feedback ? 32'hEDB88320 : 32'h00000000);
    end
end
assign crc = c ^ 32'hFFFFFFFF;
endmodule
"""
    parallels=[
        f"assign crc[{j}] = (^(data & {nbits}'h{rows[j]:x}))"
        +(" ^ 1'b1" if (offset>>j)&1 else "")
        +(" ^ data[0]" if fault and j==0 else "")
        +";"
        for j in range(32)
    ]
    rtl=serial+f"""
module crc_parallel(input wire [{nbits-1}:0] data, output wire [31:0] crc);
"""+'\n'.join(parallels)+f"""
endmodule
module miter(input wire [{nbits-1}:0] data, output wire mismatch);
wire [31:0] a, b;
crc_serial u_serial(.data(data), .crc(a));
crc_parallel u_parallel(.data(data), .crc(b));
assign mismatch = |(a ^ b);
endmodule
"""
    target=out/f'{name}.v'
    target.write_text(rtl)
    return {'case':name,'nbytes':nbytes,'fault':fault,'rtl':str(target),
            'rtl_sha256':hashlib.sha256(rtl.encode()).hexdigest()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--sizes',type=int,nargs='+',default=[1,2,4])
    ap.add_argument('--out',type=Path,default=Path('rtl'))
    a=ap.parse_args()
    a.out.mkdir(exist_ok=True,parents=True)
    assert crc_for_bits([(v>>j)&1 for v in b'123456789' for j in range(8)])==0xCBF43926
    manifest=[]
    for n in a.sizes:
        if not (1<=n<=64): raise ValueError('sizes 1..64 bytes')
        manifest.append(write_one(n,False,a.out))
        manifest.append(write_one(n,True,a.out))
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Generated',len(manifest),'real CRC-32 RTL miters')

if __name__=='__main__':
    main()
