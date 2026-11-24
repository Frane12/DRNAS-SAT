#!/usr/bin/env python3
"""REAL6.3/32: source-bound prepend of a verified LSB half-adder to 31 full-adder SUM bits.

Do NOT hardcode module names, signal IDs or filenames. Require the source's
original 32-bit *output port* to contain, in the exact bit order, an XOR(a,b)
LSB and the 31 connected full-adder SUM bits already proven by REAL6.3.
Require first full-adder carry input to be an *original* AND(a,b) physical
gate. The independent verifier replays all original-gate arithmetic.
No SAT/CDCL fallback and no claim about clocked or whole-module semantics.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from real6_1_carry import gate_graph

def sh(data):return hashlib.sha256(data).hexdigest()

def detect(netlist,base_certificate,previous_paths):
    raw=Path(netlist).read_bytes()
    cert_raw=Path(base_certificate).read_bytes()
    old_raw=Path(previous_paths).read_bytes()
    doc=json.loads(raw);base=json.loads(cert_raw);old=json.loads(old_raw)
    if old.get("original_netlist_sha256")!=sh(raw):raise ValueError("ORIGINAL_GATE_SOURCE_CHANGED")
    if old.get("source_real6_1_certificate_sha256")!=sh(cert_raw):
        raise ValueError("ORIGINAL_CERT_CHANGED")
    top,prod,users,unsupported=gate_graph(doc,base["top"])
    modules=doc["modules"][top]
    options=[]
    for output_name,p in modules.get("ports",{}).items():
        if p.get("direction")!="output" or len(p.get("bits",[]))!=32:continue
        bits=p["bits"]
        sum0=bits[0]
        if sum0 not in prod or prod[sum0][0]!="$_XOR_":continue
        left,right=prod[sum0][1]
        if left==right or not isinstance(left,int) or not isinstance(right,int):continue
        for pos,path in enumerate(old.get("paths",[])):
            if len(path)!=31:continue
            if [s["sum_bit"] for s in path]!=bits[1:]:continue
            first=path[0]
            if not isinstance(first.get("inputs"),list) or len(first["inputs"])!=3:
                continue
            for carry in first["inputs"]:
                if carry not in prod or prod[carry][0]!="$_AND_":continue
                if set(prod[carry][1])!=set((left,right)):continue
                other=sorted(x for x in first["inputs"] if x!=carry)
                if len(other)!=2 or carry in other or any(x in (left,right) for x in other):
                    continue
                options.append({
                    "output_port_name":output_name,"output_port_bits":bits,
                    "lsb_half_adder":{"sum_bit":sum0,"carry_bit":carry,
                                      "operands":sorted([left,right])},
                    "previous_full_adder_path_index":pos,
                    "full_adder_bits":len(path),
                    "complete_modular_sum_bits":1+len(path),
                    "scope":"ORIGINAL_32_OUTPUT_BITS_FREE_GATE_CUT"})
    # Stable de-duplication
    options.sort(key=lambda x:(x["output_port_name"],x["previous_full_adder_path_index"]))
    unique={}
    for x in options:
        unique.setdefault(x["output_port_name"],x)
    options=list(unique.values())
    return {"protocol":"DRNAS_REAL6_3_32BIT_LSB_HALF_PLUS_FULL_CHAIN_V1",
            "source_gate_sha256":sh(raw),
            "source_real6_1_certificate_sha256":sh(cert_raw),
            "source_previous_independent_fulladder_report_sha256":sh(old_raw),
            "top":top,"proposals":options,
            "scope":"Retrospective original 2-state Yosys gate-cut arithmetic; not complete RTL/HDL temporal circuit or SAT complexity",
            "metrics":{"32_bit_candidates":len(options),
                       "previous_report_max_full_adder_bits":
                           max((len(x) for x in old.get("paths",[])),default=0),
                       "candidate_32bit_status":"PROPOSED_PENDING_INDEPENDENT_SOURCE_PROOF" if options else "UNKNOWN_NO_SOURCE_MATCH"}}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--netlist",required=True)
    p.add_argument("--base-certificate",required=True)
    p.add_argument("--previous-paths",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=detect(a.netlist,a.base_certificate,a.previous_paths)
    Path(a.out).write_text(json.dumps(report,indent=2)+"\n")
    print("REAL6_3_32BIT_LSB_CANDIDATES",json.dumps(report["metrics"]),flush=True)

if __name__=="__main__":main()
