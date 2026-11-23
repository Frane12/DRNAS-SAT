#!/usr/bin/env python3
"""DELTA2-B deterministic affine N-step algebra regression; no Yosys required."""
from __future__ import annotations
import json
import random
from pathlib import Path
import sys
from delta2b_math import (fast_compose, matrix_mul, linear_apply,
                          compose_affine, affine_power)
from delta2_auto import compose as direct_substitution, finish_outputs

def main():
    rng=random.Random(20261123)
    count=0
    for width in (1,2,4,8,16,32):
        for n in (0,1,2,3,7,8,13,32,64,128):
            for sample in range(5):
                A=[rng.getrandbits(width) for _ in range(width)]
                B=[rng.randrange(2) for _ in range(width)]
                c=[rng.randrange(2) for _ in range(width)]
                initial=rng.getrandbits(width)
                got,meta=fast_compose(A,B,c,initial,n)
                direct=direct_substitution(A,B,c,initial,width,n)
                assert got==direct,(width,n,sample,got,direct)
                assert meta["power_matrix_multiplications"]<=2*n.bit_length()
                matrix,bias=affine_power(A,c,n)[0]
                expected_const=linear_apply(matrix,initial)^bias
                assert sum((x&1)<<j for j,x in enumerate(got))==expected_const
                for _ in range(3):
                    val=rng.getrandbits(n)
                    state=initial
                    for k in range(n):
                        after=0
                        for j in range(width):
                            bit=((A[j]&state).bit_count()&1)^c[j]^(B[j]*((val>>k)&1))
                            after|=bit<<j
                        state=after
                    reconstructed=sum((((mask>>1)&val).bit_count()&1) <<j
                                     for j,mask in enumerate(got))
                    reconstructed ^= sum((mask&1)<<j for j,mask in enumerate(got))
                    assert state==reconstructed,(width,n,sample)
                count+=1
    print("DELTA2B_INDEPENDENT_DIRECT_ALGEBRA_PASS",count)

if __name__=="__main__":main()
