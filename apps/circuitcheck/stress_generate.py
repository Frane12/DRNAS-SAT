#!/usr/bin/env python3
"""DRNAS CircuitCheck stress v0.3: fixed high-width source RTL cohort.

The widths are frozen *before* measuring any solver. CRC-32 is fixed-width
32-bit output with 64..2048 input bits; LFSR16 scrambler has 64..512 output bits.
Both compare a serial/feedback recurrence against independently derived
parallel GF(2) equations. Each has an injected-error SAT control.
These are generated engineering workloads, not third-party FPGA projects.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path
from generate_examples import crc, lfsr, signatures, make_crc, make_lfsr

SEED=20261123
SIZES={"crc":[64,128,256,512,1024,2048],"lfsr":[64,128,256,512]}

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def check_generator(kind:str,width:int)->None:
    fn=crc if kind=="crc" else lfsr
    masks,offset=signatures(fn,width)
    rng=random.Random(SEED+width+(1 if kind=="crc" else 2))
    for _ in range(8):
        bits=[rng.randrange(2) for __ in range(width)]
        raw=fn(bits)
        expected=([(raw>>j)&1 for j in range(32)] if isinstance(raw,int) else raw)
        parity=sum(t<<i for i,t in enumerate(bits))
        actual=[((parity & mask).bit_count() & 1)^offset[k] for k,mask in enumerate(masks)]
        if actual != expected:raise RuntimeError("bad parallel signature "+kind+" "+str(width))

def make_miter(kind:str,width:int)->str:
    output_width=32 if kind=="crc" else width
    return f"""
module miter(input wire [{width-1}:0] data, output wire mismatch);
wire [{output_width-1}:0] a, b;
reference r(.data(data),.out(a));
candidate c(.data(data),.out(b));
assign mismatch = |(a ^ b);
endmodule
"""

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for kind,widths in SIZES.items():
        for width in widths:
            check_generator(kind,width)
            for fault in (False,True):
                stem=f"{kind}_{width}_{'fault' if fault else 'equal'}"
                source=(make_crc if kind=="crc" else make_lfsr)(width,fault)
                source+=make_miter(kind,width)
                path=args.out/(stem+".v")
                path.write_text(source)
                cases.append({"id":stem,"family":kind,"input_bits":width,
                    "output_bits":32 if kind=="crc" else width,
                    "fault":fault,
                    "expected":"DIFFERENT_NETLIST" if fault else "EQUIVALENT_NETLIST",
                    "rtl":str(path),"sha256":sha(source.encode())})
    manifest={
        "protocol":"CIRCUITCHECK_STRESS_FIXED_20261123",
        "seed":SEED,"designs":len(cases)//2,"cases":cases,
        "notes":"No solver-score-dependent selection; synthesizable CRC32 and LFSR; generated not third-party RTL."
    }
    (args.out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("STRESS_FREEZE_PASS",len(cases),"cases; max input bits",max(x["input_bits"] for x in cases))

if __name__=="__main__":
    main()
