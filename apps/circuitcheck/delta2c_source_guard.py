#!/usr/bin/env python3
"""Independent *restricted-source-grammar* semantic guard for DELTA2-C.

This is deliberately NOT a general Verilog frontend. It accepts only an
entire single combinational reference module of the shape:

    state = literal; f = 0;
    for (i=0; i<N; i=i+1) begin
      f = state[0] ^ data[i];
      state = (state >> 1) ^ (f ? polynomial : zero);
    end
    out = state ^ final_xor;

Identifiers, widths, constants and feedback polynomial are all recovered
from the supplied source. All unmatched behavior fails CLOSED. This small
language has an explicit 2-state mathematical semantics, so the induction
argument does not require Yosys to expand all N original loop iterations.
No claim is made about general SV parsing, 4-state semantics, or industry
formal-signoff correctness of this lightweight source checker.
"""
from __future__ import annotations
import re

ID=r"[A-Za-z_][A-Za-z_0-9]*"
LIT=r"\d+'[hHdDbB][0-9a-fA-F_]+"

class RejectedSource(Exception):
    pass

def reject(msg):
    raise RejectedSource(msg)

def literal(s,width):
    m=re.fullmatch(r"(\d+)'([hHdDbB])([0-9a-fA-F_]+)",s)
    if not m or int(m[1])!=width: reject("literal width or syntax unsupported")
    base={"h":16,"d":10,"b":2}[m[2].lower()]
    val=int(m[3].replace("_",""),base)
    if val>=1<<width:reject("literal overflow")
    return val


def parse_reference(source:str, reference:str="reference")->dict:
    # Match a distinct module, then parse its ENTIRE header and body.
    # Comments, extra constructs, multi-always blocks and hidden assignments
    # cannot be accepted by the anchored grammar.
    if not re.fullmatch(ID,reference):reject("bad module identifier")
    modules=list(re.finditer(r"\bmodule\s+("+ID+r")\s*\((.*?)\)\s*;(.*?)\bendmodule\b",
                             source,re.S))
    matches=[m for m in modules if m[1]==reference]
    if len(matches)!=1:reject("missing/ambiguous reference module")
    header,body=matches[0][2],matches[0][3]
    if "//" in header+body or "/*" in header+body:reject("comments not supported")
    h=re.fullmatch(
        r"\s*input\s+wire\s+\[\s*(\d+)\s*:\s*0\s*\]\s*("+ID+r")\s*,\s*"
        r"output\s+reg\s+\[\s*(\d+)\s*:\s*0\s*\]\s*("+ID+r")\s*",header,re.S)
    if not h:reject("header outside restricted source grammar")
    n=int(h[1])+1
    width=int(h[3])+1
    data,out=h[2],h[4]
    if n<2 or n>65536 or width<2 or width>256 or data==out:
        reject("unsupported port dimensions")
    b=re.fullmatch(
        r"\s*reg\s+\[\s*(\d+)\s*:\s*0\s*\]\s*("+ID+r")\s*;\s*"
        r"reg\s+("+ID+r")\s*;\s*integer\s+("+ID+r")\s*;\s*"
        r"always\s+@\s*\*\s*begin\s*(.*?)\s*end\s*",body,re.S)
    if not b:reject("body outside restricted source grammar")
    if int(b[1])+1!=width:reject("state/output dimension mismatch")
    state,f,idx=b[2],b[3],b[4]
    if len(set([data,out,state,f,idx]))!=5:reject("aliasing identifier")
    rstate=re.escape(state);rdata=re.escape(data);rf=re.escape(f)
    ridx=re.escape(idx);rout=re.escape(out)
    body_pattern=(
        r"\s*"+rstate+r"\s*=\s*(?P<initial>"+LIT+r")\s*;\s*"
        +rf+r"\s*=\s*1'[bB]0\s*;\s*"
        r"for\s*\(\s*"+ridx+r"\s*=\s*0\s*;\s*"
        +ridx+r"\s*<\s*(?P<loop>\d+)\s*;\s*"
        +ridx+r"\s*=\s*"+ridx+r"\s*\+\s*1\s*\)\s*begin\s*"
        +rf+r"\s*=\s*"+rstate+r"\s*\[\s*0\s*\]\s*\^\s*"
        +rdata+r"\s*\[\s*"+ridx+r"\s*\]\s*;\s*"
        +rstate+r"\s*=\s*\(\s*"+rstate+r"\s*>>\s*1\s*\)\s*\^\s*"
        r"\(\s*"+rf+r"\s*\?\s*(?P<poly>"+LIT+r")\s*:\s*"
        r"(?P<zero>"+LIT+r")\s*\)\s*;\s*end\s*"
        +rout+r"\s*=\s*"+rstate+r"\s*\^\s*(?P<final>"+LIT+r")\s*;\s*"
    )
    statements=re.fullmatch(body_pattern,b[5],re.S)
    if not statements:reject("loop, body or final output outside verified grammar")
    if int(statements["loop"])!=n:reject("loop bound differs from input width")
    init=literal(statements["initial"],width)
    poly=literal(statements["poly"],width)
    zero=literal(statements["zero"],width)
    final=literal(statements["final"],width)
    if zero!=0:reject("conditional false branch must be zero")
    # Derive transition matrix directly from *source expression semantics*,
    # not from Yosys or any of the DELTA2-A/B engine functions.
    A=[];B=[]
    for j in range(width):
        tap=(poly>>j)&1
        row=(1<<(j+1)) if j+1<width else 0
        A.append(row^tap)  # state[0] enters via feedback polynomial
        B.append(tap)
    finish_masks=[(1<<(j+1))|((final>>j)&1) for j in range(width)]
    return {
        "source_grammar":"RESTRICTED_REFLECTED_FEEDBACK_V1",
        "reference":reference,"data":data,"out":out,"state":state,
        "feedback":f,"loop_index":idx,"iterations":n,"width":width,
        "initial":init,"polynomial":poly,"final_xor":final,
        "A_rows":A,"B_bits":B,"c_bits":[0]*width,
        "finish_masks":finish_masks
    }
