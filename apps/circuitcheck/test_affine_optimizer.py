#!/usr/bin/env python3
"""Independent exhaustive truth-table checks of v0.2 pair-sharing algebra.

No Yosys or SAT dependency; this checks the RTL generator's XOR-rewrite logic
on deterministic random small circuits, including repeated, constant and
cancellation cases. The real RTL proof still requires separate Yosys CI.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from optimize import parity_common_subexpressions,render_verilog

def evaluate(outputs, nodes, original, bits):
    values={f"x{i}":(bits>>i)&1 for i in range(8)}
    values["CONST"]=1
    for node in nodes:
        values[node["name"]]=values[node["left"]]^values[node["right"]]
    for key, terms in original.items():
        expected=0
        for t in terms:expected^=values[t]
        actual=0
        for t in outputs[key]:actual^=values[t]
        assert actual==expected, (key,bits,expected,actual)

def main():
    rng=random.Random(278119)
    tests=0
    for width in (2,4,6,8):
        for trial in range(25):
            source={}
            for out in range(10):
                ts={f"x{i}" for i in range(width) if rng.random()<.6}
                if rng.random()<.2:ts.add("CONST")
                source[("out",out)]=ts
            nodes,optimized,info=parity_common_subexpressions(source)
            assert info["estimated_xor_savings"]>=0
            assert info["shared_estimated_xor_count"]<=info["naive_xor_count"]
            for state in range(1<<width):
                evaluate(optimized,nodes,source,state)
            tests+=1
    shared={("out",0):{"x0","x1","x2"},("out",1):{"x0","x1","x3"}}
    nodes,optimized,info=parity_common_subexpressions(shared)
    assert info["estimated_xor_savings"]>=1 and len(nodes)>=1
    for state in range(16):evaluate(optimized,nodes,shared,state)
    ports={"data":{"bits":list(range(8)),"direction":"input"},
           "out":{"bits":[20,21],"direction":"output"}}
    variables=[{"port":"data","position":i,"bit_index":i} for i in range(8)]
    rtl=render_verilog(ports,variables,nodes,optimized)
    assert "module drnas_optimized" in rtl and "_drnas_shared" in rtl
    print("DRNAS_AFFINE_REWRITE_EXHAUSTIVE_PASS",tests,"small circuits + shared pair check")
if __name__=="__main__":main()
