#!/usr/bin/env python3
"""REAL3: source-name-agnostic and fail-closed affine parity recognizer.

Handles two entire-module 2-state grammars: scalar reduction (including
compile-time odd selection) and multi-chunk parity/error checker. Produces
GF2 affine masks: low bit constant, upper bits coefficient vector.
Unrecognized sequential/control logic => UNKNOWN; NOT generic SV parsing.
"""
import argparse,hashlib,json,re
from pathlib import Path

IDENT=r"[A-Za-z_][A-Za-z0-9_]*"
MOD=re.compile(r"\Amodule\s+(?P<name>"+IDENT+r")\s*(?:#\s*\((?P<params>.*?)\))?\s*\((?P<ports>.*?)\)\s*;\s*(?P<body>.*?)\s*endmodule(?:\s*:\s*"+IDENT+r")?\s*\Z",re.S)
class Unknown(Exception):pass
def fail(s):raise Unknown(s)
def q(s):return re.escape(s)
def squash(s):return re.sub(r"\s+","",s)

def parse_module(raw):
    try:s=raw.decode("utf-8")
    except UnicodeDecodeError:fail("UTF8_REQUIRED")
    s=re.sub(r"/\*[\s\S]*?\*/|//[^\n]*"," ",s)
    for directive in ("timescale","default_nettype"):
        s=re.sub(r"(?m)^\s*\x60"+directive+r"[^\n]*(?:\n|$)","",s)
    if chr(96) in s:fail("OTHER_PREPROCESSOR_UNSUPPORTED")
    m=MOD.fullmatch(s.strip())
    if m is None:fail("NOT_COMPLETE_SUPPORTED_MODULE")
    return m["name"],squash(m["params"] or ""),squash(m["ports"]),squash(m["body"])

def parameters(raw):
    found={}
    if raw:
        for part in raw.split(","):
            m=re.fullmatch(r"parameter(?:bit|intunsigned|int|integer)?("+IDENT+r")=(\d+)",part)
            if not m:fail("NON_LITERAL_PARAMETER")
            if m[1] in found:fail("DUPLICATE_PARAMETER")
            found[m[1]]=int(m[2])
    return found

def width_of(token,params):
    if token.isdecimal():width=int(token)+1
    elif token.endswith("-1") and token[:-2] in params:width=params[token[:-2]]
    else:fail("UNRESOLVED_WIDTH")
    if not 1<=width<=1024:fail("OUT_OF_RANGE_WIDTH")
    return width

def unary(expr,var):
    if expr in ("^"+var,"(^"+var+")"):return 0
    if expr in ("~(^"+var+")","~^"+var,"!(^"+var+")"):return 1
    fail("EXPRESSION_NOT_PARITY")

def scalar(name,params,ports,body):
    p=re.fullmatch(
       r"input(?:wire|logic)\[(?P<upper>"+IDENT+r"-1|\d+):0\](?P<data>"+IDENT+r"),"
       r"output(?:wire|logic)(?P<out>"+IDENT+r")",ports)
    if not p:fail("SCALAR_PORT_GRAMMAR_MISMATCH")
    w=width_of(p["upper"],params)
    inp,out=p["data"],p["out"]
    if inp==out:fail("ALIASED_PORTS")
    m=re.fullmatch(r"assign"+q(out)+r"=(?P<expr>[^;]+);",body)
    if not m:fail("EXTRA_RTL_OR_WRONG_ASSIGNMENT")
    expr=m["expr"]
    if "?" in expr:
        cond,arms=expr.split("?",1)
        if ":" not in arms:fail("MALFORMED_CONDITIONAL")
        yes,no=arms.split(":",1)
        if cond not in params or params[cond] not in (0,1):
            fail("UNKNOWN_PARITY_CONTROL")
        bit=unary(yes if params[cond] else no,inp)
    else:bit=unary(expr,inp)
    return {"class":"SCALAR_PARITY","module":name,"params":params,
            "input_order":[{"name":inp,"width":w}],
            "output_order":[{"name":out,"width":1}],
            "output_masks_hex":[hex((((1<<w)-1)<<1)|bit)],
            "affine_constant":bit,"data_width":w}

def chunks(name,params,ports,body):
    p=re.fullmatch(
        r"input(?:logic|wire)\[(?P<W>"+IDENT+r")-1:0\](?P<data>"+IDENT+r"),"
        r"input(?:logic|wire)\[(?P<C>"+IDENT+r")-1:0\](?P<pin>"+IDENT+r"),"
        r"input(?:logic|wire)(?P<type>"+IDENT+r"),"
        r"output(?:logic|wire)\[(?P=C)-1:0\](?P<out>"+IDENT+r"),"
        r"output(?:logic|wire)\[(?P=C)-1:0\](?P<err>"+IDENT+r")",ports)
    if not p:fail("CHUNK_PORT_GRAMMAR_MISMATCH")
    W,C=p["W"],p["C"]
    if W not in params or C not in params:fail("UNKNOWN_CHUNK_WIDTH_PARAMETER")
    width,count=params[W],params[C]
    if not 1<=count<=32 or not count<=width<=1024:
        fail("INVALID_CHUNK_DIMENSIONS")
    inp,pin,t,out,err=[p[z] for z in ("data","pin","type","out","err")]
    if len({inp,pin,t,out,err})!=5:fail("ALIASED_PORTS")
    grammar=(
      r"localparamint(?P<size>"+IDENT+r")="+q(W)+r"/"+q(C)+r";"
      r"localparamint(?P<extra>"+IDENT+r")="+q(W)+r"%"+q(C)+r";"
      r"genvar(?P<i>"+IDENT+r");generate"
      r"for\((?P=i)=0;(?P=i)<"+q(C)+r";(?P=i)\+\+\)"
      r"begin:(?P<label>"+IDENT+r")"
      r"localparamint(?P<lo>"+IDENT+r")=(?P=i)\*(?P=size);"
      r"localparamint(?P<hi>"+IDENT+r")=\((?P=i)<"+q(C)+r"-1\)\?"
      r"\(\((?P=i)\+1\)\*(?P=size)\)-1:"+q(W)+r"-1;"
      r"wire(?P<v>"+IDENT+r")="+q(t)+r"\?\^"+q(inp)+r"\[(?P=hi):(?P=lo)\]:"
      r"~\^"+q(inp)+r"\[(?P=hi):(?P=lo)\];"
      r"assign"+q(out)+r"\[(?P=i)\]=(?P=v);"
      r"assign"+q(err)+r"\[(?P=i)\]=\((?P=v)!="+q(pin)+r"\[(?P=i)\]\);"
      r"endendgenerate"
    )
    if not re.fullmatch(grammar,body):
        fail("CHUNK_BODY_OR_EXTRA_BEHAVIOR_NOT_RECOGNIZED")
    pmasks=[];emasks=[];bounds=[]
    size=width//count
    for j in range(count):
        low=j*size
        high=(j+1)*size-1 if j<count-1 else width-1
        if high<low:fail("EMPTY_CHUNK")
        data=((1<<(high-low+1))-1)<<low
        # parity_type=1 => even XOR, else inverted XOR:
        mask=(data<<1) ^ (1<<(1+width+count)) ^ 1
        pmasks.append(hex(mask))
        emasks.append(hex(mask^(1<<(1+width+j))))
        bounds.append({"chunk":j,"lower":low,"upper":high})
    return {"class":"CHUNKED_PARITY_CHECKER","module":name,"params":params,
            "input_order":[{"name":inp,"width":width},{"name":pin,"width":count},
                           {"name":t,"width":1}],
            "output_order":[{"name":out,"width":count},{"name":err,"width":count}],
            "output_masks_hex":pmasks+emasks,
            "data_width":width,"chunks":count,"bounds":bounds}

def classify(raw,overrides=None):
    name,decl,ports,body=parse_module(raw)
    params=parameters(decl)
    for name_override,value in (overrides or {}).items():
        if name_override not in params or not isinstance(value,int):
            fail("UNDECLARED_OR_INVALID_PARAMETER")
        params[name_override]=value
    failures=[]
    for fn in (scalar,chunks):
        try:
            obj=fn(name,params,ports,body)
            obj.update({"engine":"DRNAS_REAL3_UNSEEN_SOURCE_CLASS_v1",
                        "source_sha256":hashlib.sha256(raw).hexdigest(),
                        "scope":"recognized complete source grammar, two-state only"})
            return obj
        except Unknown as e:failures.append(str(e))
    fail("UNKNOWN_UNSUPPORTED "+";".join(failures))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--param",action="append",default=[])
    a=p.parse_args()
    opts={}
    for pair in a.param:
        m=re.fullmatch("("+IDENT+r")=(\d+)",pair)
        if not m:fail("BAD_OVERRIDE")
        opts[m[1]]=int(m[2])
    try:
        result=classify(a.source.read_bytes(),opts)
        result["status"]="RECOGNIZED_RESTRICTED_SOURCE"
    except (Unknown,ValueError) as e:
        result={"status":"UNKNOWN","reason":str(e)}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("REAL3_CLASSIFY",result.get("module"),result["status"],
          result.get("class"),flush=True)
    return 0 if result["status"]=="RECOGNIZED_RESTRICTED_SOURCE" else 2
if __name__=="__main__":raise SystemExit(main())
