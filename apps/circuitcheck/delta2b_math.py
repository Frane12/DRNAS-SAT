#!/usr/bin/env python3
"""DELTA2-B compositional affine recurrence engine.

Given a verified one-step law s'=A*s XOR B*x XOR c, do NOT build or
synthesize N unfolded hardware stages. Compute:
  A^N, bias_N = (A,c)^N by binary exponentiation of affine maps;
  coeff(input[k]) = A^(N-1-k) * B via reverse vector propagation.
The result is a *full* affine function of all N input bits.

Exact for GF(2) matrices. This alone DOES NOT independently prove
the source RTL was faithfully extracted; the SHA-frozen strict parser,
one-step Yosys gate proof and optional full-source RTL audit are separate
trust layers. No hand-coded CRC polynomial, no heuristic CRC detection.
"""
from __future__ import annotations

def check(A, B, c, initial, count):
    w=len(A)
    if w<1 or count<0 or len(B)!=w or len(c)!=w:
        raise ValueError("matrix dimensions invalid")
    if not all(isinstance(x,int) and 0<=x<(1<<w) for x in A):
        raise ValueError("matrix row out of range")
    if not all(x in (0,1) for x in B+c):
        raise ValueError("affine c/B must be scalar bits")
    if not isinstance(initial,int) or not (0<=initial<1<<w):
        raise ValueError("initial state invalid")


def linear_apply(rows:list[int], vector:int)->int:
    result=0
    for j,mask in enumerate(rows):
        result|=((mask&vector).bit_count()&1)<<j
    return result


def matrix_mul(left:list[int],right:list[int])->list[int]:
    # left * right, all linear over GF(2)
    result=[]
    for row in left:
        value=0
        while row:
            bit=row&-row
            value^=right[bit.bit_length()-1]
            row-=bit
        result.append(value)
    return result


def compose_affine(outer, inner):
    # outer(inner(s)): A_outer*A_inner*s + A_outer*b_inner + b_outer
    A,b=outer
    C,d=inner
    return (matrix_mul(A,C),linear_apply(A,d)^b)


def affine_power(A:list[int],c:list[int],count:int):
    width=len(A)
    identity=[1<<j for j in range(width)]
    result=(identity,0)
    cbits=sum((b<<j) for j,b in enumerate(c))
    base=(A[:],cbits)
    steps=count
    multiplications=0
    while steps:
        if steps&1:
            result=compose_affine(base,result)
            multiplications+=1
        steps>>=1
        if steps:
            base=compose_affine(base,base)
            multiplications+=1
    return result,multiplications


def fast_compose(A:list[int], B:list[int], c:list[int],
                 initial:int, count:int):
    check(A,B,c,initial,count)
    width=len(A)
    (power,bias),mults=affine_power(A,c,count)
    const_state=linear_apply(power,initial)^bias
    rows=[(const_state>>j)&1 for j in range(width)]
    feedback=sum((b<<j) for j,b in enumerate(B))
    # Iterate the *state-width vector*, not a 2048-variable expression.
    # For x_k the state contribution is A^(count-1-k) B.
    for k in range(count-1,-1,-1):
        v=feedback
        while v:
            one=v&-v
            rows[one.bit_length()-1]^=1<<(k+1)
            v-=one
        feedback=linear_apply(A,feedback)
    return rows,{"method":"binary_affine_power_and_reverse_input_basis",
                 "power_matrix_multiplications":mults,
                 "input_iterations":count,"state_width":width}
