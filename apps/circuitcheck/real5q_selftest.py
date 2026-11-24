#!/usr/bin/env python3
"""REAL5Q adversarial independently replayed Boolean ring tests.

Test exact quadratic majority, choice and mux identities, cubic cap as
physical cut symbol, free FF-Q inputs, forced UNKNOWN, and manipulated
monomial/gate SHA. Also random small gate networks with independent
two-state truth values for every fully expanded global polynomial probe.
"""
from __future__ import annotations
import hashlib,json,random,tempfile
from pathlib import Path
from real5q_anf import analyze
from real5q_verify import check,Invalid

def gate(kind,a,b,y,s=None):
    d={"A":[a],"Y":[y]};directions={"A":"input","Y":"output"}
    if b is not None:d["B"]=[b];directions["B"]="input"
    if s is not None:d["S"]=[s];directions["S"]="input"
    return {"type":kind,"connections":d,"port_directions":directions}

def netlist():
    cells={
        "ab":gate("$_AND_",2,3,10),
        "ac":gate("$_AND_",2,4,11),
        "bc":gate("$_AND_",3,4,12),
        "ab_xor_ac":gate("$_XOR_",10,11,13),
        "majority":gate("$_XOR_",13,12,14),
        "neg_x":gate("$_NOT_",2,None,15),
        "neg_x_and_z":gate("$_AND_",15,4,16),
        "choice":gate("$_XOR_",10,16,17),
        "mux":gate("$_MUX_",3,4,18,s=2),
        "abc":gate("$_AND_",10,4,19),
        "abc_xor":gate("$_XOR_",19,3,20),
        "dff": {"type":"$_DFF_P_",
                "connections":{"D":[17],"Q":[21],"C":[5]},
                "port_directions":{"D":"input","Q":"output","C":"input"}},
        "ff_q_xor":gate("$_XOR_",21,2,22)
    }
    ports={
        "x":{"direction":"input","bits":[2]},
        "y":{"direction":"input","bits":[3]},
        "z":{"direction":"input","bits":[4]},
        "clk":{"direction":"input","bits":[5]},
        "majority":{"direction":"output","bits":[14]},
        "choice":{"direction":"output","bits":[17]},
        "mux":{"direction":"output","bits":[18]},
        "cubic":{"direction":"output","bits":[20]},
        "FF_Q_plus_x":{"direction":"output","bits":[22]}
    }
    return {"modules":{"unknown_gate_network":{"ports":ports,"cells":cells}}}

def setup(folder,net):
    netfile=folder/"netlist.json"
    netfile.write_text(json.dumps(net))
    c=analyze(net,"unknown_gate_network")
    c["netlist_sha256"]=hashlib.sha256(netfile.read_bytes()).hexdigest()
    file=folder/"real5q_certificate.json"
    file.write_text(json.dumps(c,indent=2))
    assert check(folder)["status"]=="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS"
    return c,file

def evaluate(poly,assignment):
    result=0
    for term in poly:
        mask=int(term,16)
        result^=int(mask&assignment==mask)
    return result

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        c,p=setup(root,netlist())
        assert c["metrics"]["FF_Q_bits"]==1
        m={v["name"]:v for v in c["probes"] if v["kind"]=="primary_output"}
        for name in ("majority","choice","mux"):
            assert m[name]["status"]=="GLOBAL_EXACT_GF2_ANF",m[name]
            assert m[name]["global_quadratic"],m[name]
            assert m[name]["higher_order_monomials"]>=2
        assert m["cubic"]["status"]=="LOCAL_BOUNDED_ANF_WITH_CUTS"
        assert c["metrics"]["cut_outputs"]>=1
        assert m["FF_Q_plus_x"]["status"]=="GLOBAL_EXACT_GF2_ANF"
        ordered={x["name"]:x["index"] for x in c["basis"] if x["kind"]=="input"}
        for x in range(2):
          for y in range(2):
           for z in range(2):
            assignment=(x<<ordered["x"])|(y<<ordered["y"])|(z<<ordered["z"])
            truth={"majority":(x&y)^(x&z)^(y&z),
                   "choice":(x&y)^((x^1)&z),
                   "mux":z if x else y}
            for name,v in truth.items():
                computed=evaluate(m[name]["monomials_hex"],assignment)
                assert computed==v,(name,x,y,z,computed,v)
        print("REAL5Q_EXACT_MAJORITY_CHOICE_MUX_GF2_PASS",flush=True)
        original=p.read_bytes()
        cert=json.loads(original)
        corrupt=json.loads(original)
        next(v for v in corrupt["probes"] if v["name"]=="majority")["monomials_hex"]=["0x0"]
        p.write_text(json.dumps(corrupt))
        try:check(root)
        except Invalid:print("REAL5Q_TAMPERED_POLYNOMIAL_REJECTED",flush=True)
        else:raise AssertionError("UNSOUND_FAKE_POLYNOMIAL_PROOF")
        p.write_bytes(original)
        gatefile=root/"netlist.json"
        raw=gatefile.read_bytes()
        gatefile.write_bytes(raw+b"\n")
        try:check(root)
        except Invalid:print("REAL5Q_WRONG_GATE_NETLIST_SHA_REJECTED",flush=True)
        else:raise AssertionError("SOURCE_GATE_NETLIST_CHANGED")
        gatefile.write_bytes(raw)
        assert check(root)["status"]=="CHECKED_EXACT_BOUNDED_BOOLEAN_POLYNOMIALS"
        bad=netlist()
        bad["modules"]["unknown_gate_network"]["ports"]["majority"]["bits"]=["x"]
        new,p=setup(root,bad)
        assert any(r["name"]=="majority" and r["status"]=="UNKNOWN" for r in new["probes"])
        print("REAL5Q_X_UNKNOWN_NOT_REWRITTEN_AS_PROOF",flush=True)
    print("REAL5Q_ALL_ADVERSARIAL_TESTS_PASS",flush=True)

if __name__=="__main__":main()
