#!/usr/bin/env python3
"""Adversarial small-source induction and independent block coefficient tests."""
from __future__ import annotations
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from generate_examples import make_crc
from delta2c_source_guard import parse_reference,RejectedSource
from delta2c import block_rows
from delta2c_verify import direct_block

def rejected(source):
    try:
        parse_reference(source,"reference")
    except RejectedSource:
        return
    raise AssertionError("dangerous source mutation incorrectly accepted")

def main():
    for n in (8,64,256,2048):
        src=make_crc(n,False)
        d=parse_reference(src,"reference")
        assert d["iterations"]==n and d["width"]==32
        assert d["polynomial"]==int("EDB88320",16)
        assert d["initial"]==(1<<32)-1 and d["final_xor"]==(1<<32)-1
        assert d["B_bits"]==[(int("EDB88320",16)>>j)&1 for j in range(32)]
        mutated=src.replace("32'hEDB88320","32'h82F63B78")
        assert parse_reference(mutated,"reference")["polynomial"]==int("82F63B78",16)
        modifications=[
            ("f = state[0] ^ data[i];","f = state[0] ^ data[i] ^ (i==7);"),
            ("state >> 1","state >> 2"),
            ("state[0] ^ data[i]","state[1] ^ data[i]"),
            ("state = (state>>1)","state = (state>>2)"),
            ("out = state ^ 32'hFFFFFFFF;","out = state ^ 32'hFFFFFFFF; out = ~out;"),
            ("i=i+1","i=i+2"),
            ("i<"+str(n),"i<"+str(n-1)),
            ("state = 32'hFFFFFFFF;","state = 32'hFFFFFFFF; state = 0;"),
            ("f ? 32'hEDB88320 : 32'd0","f ? 32'hEDB88320 : 32'd1"),
        ]
        for before,after in modifications:
            if before in src:
                rejected(src.replace(before,after,1))
        print("DELTA2C_SOURCE_RESTRICTED_PASS",n,flush=True)

    rng=random.Random(20261124)
    cases=0
    for w in (2,4,8,16,32):
        for k in (1,2,4,8):
            for i in range(25):
                A=[rng.getrandbits(w) for _ in range(w)]
                B=[rng.randrange(2) for _ in range(w)]
                c=[rng.randrange(2) for _ in range(w)]
                fast,_=block_rows(A,B,c,k)
                independent=direct_block(A,B,c,w,k)
                assert fast==independent,(w,k,i)
                for _ in range(4):
                    state=rng.getrandbits(w)
                    bits=rng.getrandbits(k)
                    s=state
                    for pos in range(k):
                        t=0
                        for j in range(w):
                            v=((A[j]&s).bit_count()&1)^c[j]^(B[j]*((bits>>pos)&1))
                            t|=v<<j
                        s=t
                    got=0
                    for j,mask in enumerate(fast):
                        v=(mask&1)^(((mask>>1)&state).bit_count()&1)
                        v^=(((mask>>(w+1))&bits).bit_count()&1)
                        got|=v<<j
                    assert s==got
                cases+=1
    print("DELTA2C_BLOCK_DIRECT_INDEPENDENT_PASS",cases,flush=True)

if __name__=="__main__":main()
