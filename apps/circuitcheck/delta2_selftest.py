#!/usr/bin/env python3
"""DELTA2-A source-cut and matrix-composition adversarial tests, no Yosys."""
from __future__ import annotations
import random
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from generate_examples import make_crc
from stress_generate import make_miter
from delta2_auto import discover, compose, finish_outputs, render_model, DiscoveryFailure


def check():
    for n in (8,64,256,2048):
        src=make_crc(n,False)+make_miter("crc",n)
        plan=discover(src,"reference")
        assert plan["iterations"]==n and plan["state_bits"]==32
        assert plan["input_bits"]==n and plan["output_bits"]==32
        assert plan["source_cut_count"]==n+1 if "source_cut_count" in plan else True
        assert "b_input_bit" in plan["transition_rtl"]
        assert "a_state_in" in plan["transition_rtl"]
        assert "state = 32'hFFFFFFFF" not in plan["transition_rtl"]
        assert "drnas_output" in plan["finish_rtl"]
        # The transition polynomial comes from the RTL, not the detector.
        altered=src.replace("32'hEDB88320","32'h82F63B78")
        new=discover(altered,"reference")
        assert "82F63B78" in new["transition_rtl"]
        # Cross-iteration loop-index references must not be hidden as a
        # constant-stage model; reject rather than give a false proof.
        modified=src.replace("f = state[0] ^ data[i];",
                             "f = state[0] ^ data[i] ^ (i == 3);")
        try:
            discover(modified,"reference")
        except DiscoveryFailure:pass
        else:raise RuntimeError("loop-index-dependent transition accepted")
        print("DELTA2_AUTO_CUT_PASS",n,flush=True)

    rng=random.Random(20261123)
    for width in (4,8,32):
        for steps in (1,8,32):
            for _ in range(10):
                A=[rng.getrandbits(width) for j in range(width)]
                B=[rng.randrange(2) for j in range(width)]
                c=[rng.randrange(2) for j in range(width)]
                initial=rng.getrandbits(width)
                out=compose(A,B,c,initial,width,steps)
                for _ in range(10):
                    input_value=rng.getrandbits(steps)
                    state=initial
                    for k in range(steps):
                        new_state=0
                        for j in range(width):
                            bit=((A[j]&state).bit_count()&1)^c[j]^(
                                B[j]*((input_value>>k)&1))
                            new_state|=bit<<j
                        state=new_state
                    inferred=sum(((((m>>1)&input_value).bit_count()&1)^(m&1))<<j
                                 for j,m in enumerate(out))
                    assert inferred==state
                finale=[1<<(k+1) for k in range(width)]
                assert finish_outputs(out,finale,width)==out
    schema={"input_bits":8,"output_bits":2,"input_name":"d","output_name":"o"}
    assert "drnas_delta2_model" in render_model(schema,[1,5])
    print("DELTA2_AFFINE_COMPOSITION_PASS")


if __name__=="__main__":check()
