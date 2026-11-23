#!/usr/bin/env python3
"""DRNAS CircuitCheck Optimize v0.2: proof-gated FPGA RTL rewrite.

Extract exact affine GF(2) ANFs from Yosys flattened reference logic; create a
shared-XOR candidate using common-pair elimination. Compile reference and
candidate with the SAME Yosys gate mapping, compare logic-cell counts,
then *require* an independent CircuitCheck certificate replay before
describing a candidate as equivalent. Keep the original RTL untouched.

This optimizes combinational bitwise parity networks only. A verified smaller
mapped gate count is not equivalent to fewer FPGA LUTs, better timing or lower
power. No extrapolation to arbitrary nonlinear/sequential circuits.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import itertools
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time

from proof_engine import Unsupported, analyze

APP = pathlib.Path(__file__).resolve().parent
MAX_INPUT_BITS = 256
MAX_OUTPUT_BITS = 512
MAX_SHARED_NODES = 500

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(command:list[str], cwd:pathlib.Path, timeout:int=120):
    return subprocess.run([str(x) for x in command],cwd=cwd,
                          capture_output=True,text=True,timeout=timeout,
                          check=False)

def yosys(work:pathlib.Path,script:str,log:str,timeout=120):
    p=work/"work.ys"
    p.write_text(script+"\n")
    r=run(["yosys","-s",p.name],work,timeout)
    (work/log).write_text(r.stdout+"\n"+r.stderr)
    if r.returncode:
        raise Unsupported("Yosys synth failed; see "+log)
    return r

def synth(work:pathlib.Path,files:list[str],top:str,outname:str):
    # A single frozen mapping recipe for both circuits. This is NOT a timing
    # model, and different FPGA vendors may map very differently.
    f=" ".join(files)
    yosys(work,
          f"read_verilog -sv {f}; hierarchy -check -top {top}; "
          f"proc; flatten; opt; techmap; opt; write_json {outname}",
          f"yosys-{top}.log")
    data=json.loads((work/outname).read_text())
    if top not in data.get("modules",{}):
        raise Unsupported("missing synthesized module "+top)
    return data

def extract_affine(doc:dict,top:str):
    ports=doc["modules"][top]["ports"]
    inputs=sorted(n for n,p in ports.items() if p["direction"]=="input")
    outputs=sorted(n for n,p in ports.items() if p["direction"]=="output")
    if not inputs or not outputs:
        raise Unsupported("need combinational input and output ports")
    if any(p["direction"] not in ("input","output") for p in ports.values()):
        raise Unsupported("inout not supported")
    if sum(len(ports[x]["bits"]) for x in inputs)>MAX_INPUT_BITS:
        raise Unsupported("too many input bits")
    if sum(len(ports[x]["bits"]) for x in outputs)>MAX_OUTPUT_BITS:
        raise Unsupported("too many output bits")
    iface={"top":top,"pairs":[{"port":name,"reference":name,"candidate":name}
                              for name in outputs]}
    evidence=analyze(doc,iface)
    if evidence.get("unknown"):
        raise Unsupported("unsupported gate/output: "+json.dumps(evidence["unknown"][:3]))
    expected={(v["port"],v["position"]):v["bit_index"]
              for v in evidence["variables"]}
    terms={}
    for o in evidence["output_polynomials"]:
        key=(o["port"],o["position"])
        bitset=set()
        for code in o["ref_terms"]:
            m=int(code,16)
            if m==0:token="CONST"
            elif m.bit_count()==1:
                i=m.bit_length()-1
                if not any(v["bit_index"]==i for v in evidence["variables"]):
                    raise Unsupported("unmapped input basis")
                token="x"+str(i)
            else:
                raise Unsupported("NONLINEAR_ANF monomial degree="+str(m.bit_count())+
                                  " at "+str(key))
            bitset.add(token)
        terms[key]=bitset
    return ports,evidence["variables"],terms

def parity_common_subexpressions(terms):
    # Single-output baseline: XOR of all terms. Pair-sharing across
    # output sets cannot change parity due to replacing a+b with one wire.
    outputs={key:set(value) for key,value in terms.items()}
    before=sum(max(len(x)-1,0) for x in outputs.values())
    nodes=[]
    for node_idx in range(MAX_SHARED_NODES):
        counts=collections.Counter()
        for values in outputs.values():
            for pair in itertools.combinations(sorted(values),2):
                # Don't share the constant - avoid presenting NOT as XOR win.
                if "CONST" in pair:continue
                counts[pair]+=1
        useful=[(count,pair) for pair,count in counts.items() if count>1]
        if not useful:break
        count,pair=sorted(useful,key=lambda a:(-a[0],a[1]))[0]
        name="t"+str(node_idx)
        nodes.append({"name":name,"left":pair[0],"right":pair[1],"uses":count})
        for values in outputs.values():
            if pair[0] in values and pair[1] in values:
                values.remove(pair[0]);values.remove(pair[1]);values.add(name)
    after=len(nodes)+sum(max(len(x)-1,0) for x in outputs.values())
    assert after<=before
    return nodes,outputs,{"naive_xor_count":before,
                          "shared_estimated_xor_count":after,
                          "estimated_xor_savings":before-after}

def render_verilog(ports,variables,nodes,outputs):
    portnames=sorted(ports)
    declarations=[]
    for name in portnames:
        p=ports[name]
        width=len(p["bits"])
        role=p["direction"]
        declarations.append(f"  {role} wire [{width-1}:0] {name}")
    varnames={v["bit_index"]:f"{v['port']}[{v['position']}]"
              for v in variables}
    def sig(s):
        if s=="CONST":return "1'b1"
        if s.startswith("x"):return varnames[int(s[1:])]
        if s.startswith("t"):return "_drnas_shared_"+s[1:]
        raise Unsupported("unexpected token "+s)
    lines=[
        "// DRNAS CircuitCheck v0.2, generated from source-derived affine GF(2) ANF.",
        "// Only use after independent certificate replay.",
        "module drnas_optimized(",
        ",\n".join(declarations),
        ");",
    ]
    for n in nodes:
        lines.append(f"  wire {sig(n['name'])} = {sig(n['left'])} ^ {sig(n['right'])};")
    for name in portnames:
        if ports[name]["direction"]!="output":continue
        for position in range(len(ports[name]["bits"])):
            seq=sorted(outputs[(name,position)])
            expr=" ^ ".join(sig(t) for t in seq) if seq else "1'b0"
            lines.append(f"  assign {name}[{position}] = {expr};")
    lines.append("endmodule")
    return "\n".join(lines)+"\n"

def logic_metrics(doc:dict,top:str)->dict:
    mod=doc["modules"][top]
    cells=mod.get("cells",{})
    types=collections.Counter(x["type"] for x in cells.values())
    gate_n=sum(types.values())
    inputs={v for p in mod["ports"].values() if p["direction"]=="input"
            for v in p["bits"] if isinstance(v,int)}
    drivers={}
    for cell in cells.values():
        for port,direction in cell.get("port_directions",{}).items():
            if direction=="output":
                for bit in cell["connections"][port]:
                    if isinstance(bit,int):
                        if bit in drivers:raise Unsupported("multiple drivers in metric graph")
                        drivers[bit]=cell
    visiting=set(); memo={"0":0,"1":0}
    def depth(bit):
        if bit in memo:return memo[bit]
        if bit in inputs:return 0
        if bit in ("x","z") or not isinstance(bit,int):
            raise Unsupported("unknown output in gate-depth metric")
        if bit not in drivers:raise Unsupported("unmapped output in gate-depth metric")
        if bit in visiting:raise Unsupported("cycle in gate-depth metric")
        cell=drivers[bit]
        if not cell.get("port_directions",{}):
            raise Unsupported("cannot classify gate for depth")
        visiting.add(bit)
        try:
            feed=[p for p,dir in cell["port_directions"].items() if dir=="input"]
            ans=1+max((depth(x) for p in feed for x in cell["connections"][p]),default=0)
        finally:visiting.remove(bit)
        memo[bit]=ans;return ans
    outbits=[x for p in mod["ports"].values() if p["direction"]=="output"
             for x in p["bits"]]
    return {"gate_count":gate_n,"xor_count":types.get("$_XOR_",0)+types.get("$_XNOR_",0),
            "by_type":dict(sorted(types.items())),
            "max_gate_depth":max((depth(x) for x in outbits),default=0)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--rtl",nargs="+",type=pathlib.Path,required=True)
    ap.add_argument("--reference",default="reference")
    ap.add_argument("--out",type=pathlib.Path,required=True)
    args=ap.parse_args()
    start=time.perf_counter()
    work=args.out.resolve();work.mkdir(parents=True,exist_ok=True)
    report={"tool":"DRNAS CircuitCheck Optimize v0.2",
            "status":"UNKNOWN","reference":args.reference,
            "scope":"two-state combinational gate netlist; Yosys mapping trusted",
            "timing_warning":"Gate count and depth are NOT FPGA LUT count, timing, power or hardware validation"}
    try:
        files=[]
        for i,src in enumerate(args.rtl):
            src=src.resolve()
            if not src.is_file():raise Unsupported("missing RTL: "+str(src))
            target=work/f"input_{i}.v";shutil.copyfile(src,target)
            files.append(target.name)
        report["sources"]={f:sha(work/f) for f in files}
        if not re.fullmatch("[A-Za-z_][A-Za-z_0-9]*",args.reference):
            raise Unsupported("invalid reference module name")
        orig=synth(work,files,args.reference,"reference_gates.json")
        ports,variables,terms=extract_affine(orig,args.reference)
        nodes,out_expr,math_estimate=parity_common_subexpressions(terms)
        (work/"optimized.v").write_text(render_verilog(ports,variables,nodes,out_expr))
        cand=synth(work,["optimized.v"],"drnas_optimized","optimized_gates.json")
        original_metrics=logic_metrics(orig,args.reference)
        candidate_metrics=logic_metrics(cand,"drnas_optimized")
        report["math"]={**math_estimate,"input_bits":len(variables),
                        "output_bits":len(terms),"shared_nodes":len(nodes)}
        report["original"]=original_metrics
        report["candidate"]=candidate_metrics
        # This is the decisive proof gate. A faster-looking candidate is never
        # approved just because synthesis reports fewer mapped cells.
        check=run([sys.executable,APP/"circuitcheck.py","--rtl",
                   *(work/f for f in files),work/"optimized.v",
                   "--reference",args.reference,
                   "--candidate","drnas_optimized",
                   "--out",work/"proof"],work,200)
        (work/"proof_stdout.log").write_text(check.stdout+"\n"+check.stderr)
        if check.returncode!=0:
            raise Unsupported("generated candidate NOT equivalence-proved; see proof_stdout.log")
        replay=run([sys.executable,APP/"verify_certificate.py",work/"proof"],work,120)
        (work/"replay_stdout.log").write_text(replay.stdout+"\n"+replay.stderr)
        if replay.returncode or "CHECKED_EQUIVALENT_NETLIST" not in replay.stdout:
            raise Unsupported("independent proof replay failed")
        report["proof"]="CHECKED_EQUIVALENT_NETLIST"
        report["proof_netlist_sha256"]=sha(work/"proof"/"netlist.json")
        report["candidate_rtl_sha256"]=sha(work/"optimized.v")
        report["status"]=("PROVED_LOWER_GATE_COUNT"
                          if candidate_metrics["gate_count"]<original_metrics["gate_count"]
                          else "PROVED_NO_GATE_COUNT_GAIN")
    except (Unsupported, ValueError,KeyError,RuntimeError,
            subprocess.TimeoutExpired,RecursionError) as e:
        report["status"]="UNKNOWN"
        report["reason"]=str(e)
        report["proof"]="NOT_ESTABLISHED"
    report["end_to_end_seconds"]=round(time.perf_counter()-start,6)
    (work/"optimization.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report["status"].startswith("PROVED_") else 2

if __name__=="__main__":
    sys.exit(main())
