#!/usr/bin/env python3
"""ATLAS20 proof-first model-producing circuit solver (no CDCL fallback).

Reads original DIMACS bytes; validates EVERY clause as a source-supported
XOR/XNOR/AND/OR gate or unit. Constructs a reproducible native C++ bit-sliced
enumerator of *only the independently identified primary inputs*. Native
search receives no known answer or expected SAT status. If a candidate is
found, evaluate ALL original variables and ask a separate independent DIMACS
checker to accept the complete original-source SAT model.
Even exhaustive non-discovery is UNKNOWN unless a standard UNSAT proof exists.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import time
from extract import recover,write_model
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

def require(ok,reason):
    if not ok:raise RuntimeError(reason)

def hash_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<17),b""):h.update(b)
    return h.hexdigest()

def produce_cpp(circuit):
    n=circuit["variables"]
    inputs=circuit["inputs"]
    units=circuit["unit_literals"]
    m=len(inputs)
    need=["#include <cstdint>","#include <cstdio>","#include <cstdlib>",
          "#include <cinttypes>",
          "int main(){",
          f"  std::uint64_t x[{n+1}] = {{0}};",
          "  const std::uint64_t pattern[6]={",
          "    0xaaaaaaaaaaaaaaaaULL, 0xccccccccccccccccULL,",
          "    0xf0f0f0f0f0f0f0f0ULL, 0xff00ff00ff00ff00ULL,",
          "    0xffff0000ffff0000ULL, 0xffffffff00000000ULL};"]
    for i,v in enumerate(inputs[:6]):
        need.append(f"  x[{v}]=pattern[{i}];")
    need.extend([f"  const std::uint64_t count=(1ULL<<{m});",
                 "  const std::uint64_t blocks=(count+63ULL)/64ULL;",
                 "  for(std::uint64_t chunk=0;chunk<blocks;chunk++){"])
    for i,v in enumerate(inputs[6:],6):
        need.append(f"    x[{v}]=0ULL-((chunk>>{i-6})&1ULL);")
    for g in circuit["gates"]:
        op={"XOR":"^","XNOR":"^","AND":"&","OR":"|"}[g["op"]]
        expr=f"x[{g['a']}]{op}x[{g['b']}]"
        if g["op"]=="XNOR":expr="~("+expr+")"
        need.append(f"    x[{g['z']}]={expr};")
    need.append("    std::uint64_t valid=~std::uint64_t(0);")
    for lit in units:
        expr=f"x[{abs(lit)}]" if lit>0 else f"~x[{abs(lit)}]"
        need.append(f"    valid &= {expr};")
    need.extend(["    if(valid){",
                 "      const unsigned lane=__builtin_ctzll(valid);",
                 "      const std::uint64_t key=chunk*64ULL+lane;",
                 "      if(key<count){",
                 '        std::printf("FOUND input32=%" PRIu64 " tested=%" PRIu64 "\\n", key, chunk*64ULL+lane+1);',
                 "        return 0;",
                 "      }",
                 "    }",
                 "  }",
                 '  std::printf("EXHAUSTED_UNCERTIFIED count=%" PRIu64 "\\n",count);',
                 "  return 2;",
                 "}"])
    return "\n".join(need)+"\n"

def set_cpu():
    if hasattr(os,"sched_setaffinity"):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})

def limits():
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(80*1024**2,)*2)

def run(cmd,timeout):
    started=time.perf_counter()
    try:
        result=subprocess.run(list(map(str,cmd)),capture_output=True,
                              text=True,errors="replace",timeout=timeout,
                              preexec_fn=limits)
        return result.returncode,round(time.perf_counter()-started,6),result.stdout+result.stderr
    except subprocess.TimeoutExpired:
        return 124,round(time.perf_counter()-started,6),"TIMEOUT"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--maximum-search-seconds",type=float,default=90.0)
    a=p.parse_args()
    set_cpu()
    start=time.perf_counter()
    a.out.mkdir(parents=True,exist_ok=True)
    raw=a.cnf.read_bytes()
    circuit=recover(raw)
    meta={k:v for k,v in circuit.items() if k!="gates"}
    (a.out/"source_structure.json").write_text(json.dumps(meta,sort_keys=True,indent=2)+"\n")
    code=produce_cpp(circuit)
    source=a.out/"native_search.cpp";source.write_text(code)
    require(hash_file(a.cnf)==circuit["source_sha256"],"SOURCE_SHA_CHANGED")
    executable=a.out/"native_search"
    rc,compile_time,compile_output=run(["g++","-O3","-std=c++20","-march=x86-64",
                  str(source),"-o",str(executable)],50)
    (a.out/"compiler.log").write_text(compile_output)
    require(rc==0 and executable.is_file(),"NATIVE_COMPILER_FAILED:"+compile_output[-900:])
    rc,search_time,output=run([str(executable)],a.maximum_search_seconds)
    (a.out/"search.log").write_text(output)
    found=re.search(r"^FOUND input32=(\d+) tested=(\d+)\s*$",output,re.M)
    result={"status":"UNKNOWN","reason":"NO_VERIFIED_SAT_MODEL_YET",
        "source_sha256":circuit["source_sha256"],
        "source_variables":circuit["variables"],
        "source_clauses":circuit["clauses"],
        "source_gate_counts":circuit["gate_kinds"],
        "primary_inputs":circuit["input_count"],
        "fixed_output_units":len(circuit["unit_literals"]),
        "source_grammar_exact":True,
        "native_search_returncode":rc,
        "native_compile_s":compile_time,"native_search_s":search_time,
        "whole_E2E_s":None,"CDCL_fallback":False,
        "proof_kind":"SAT_COMPLETE_ORIGINAL_DIMACS_MODEL_ONLY"}
    if found and rc==0:
        key=int(found.group(1))
        require(0<=key<(1<<circuit["input_count"]),"SEARCH_RETURNED_INVALID_KEY")
        witness=a.out/"full_model.dimacs"
        write_model(circuit,key,witness)
        checker_report=a.out/"independent_checker.json"
        check_rc,check_time,check_log=run([sys.executable,
            HERE/"check_model.py","--cnf",a.cnf,
            "--model",witness,"--output",checker_report],20)
        (a.out/"checker.log").write_text(check_log)
        require(check_rc==0 and checker_report.is_file(),
                "INDEPENDENT_SOURCE_MODEL_REJECTED:"+check_log[-800:])
        checked=json.loads(checker_report.read_text())
        require(checked["status"]=="SAT_MODEL_VERIFIED","INDEPENDENT_CHECKER_NO_SAT")
        require(checked["source_sha256"]==circuit["source_sha256"],
                "MODEL_CHECKER_SOURCE_SHA_MISMATCH")
        result.update(status="SAT_MODEL_VERIFIED",reason="INDEPENDENT_ORIGINAL_CNF_ACCEPTED",
                      input_key=key,input_hex=f"0x{key:08x}",
                      native_keys_tested=int(found.group(2)),
                      model_sha256=hash_file(witness),
                      model_bytes=witness.stat().st_size,
                      independent_checker_s=check_time,
                      full_source_clauses_checked=checked["original_clauses_verified"])
    elif rc==2:
        result["reason"]="EXHAUSTED_ONLY_NO_STANDARD_UNSAT_PROOF"
    elif rc==124:
        result["reason"]="SEARCH_TIMEOUT_SAFELY_UNKNOWN"
    else:
        raise RuntimeError("NATIVE_SEARCH_ERROR:"+output[-900:])
    result["whole_E2E_s"]=round(time.perf_counter()-start,6)
    require(hash_file(a.cnf)==circuit["source_sha256"],"SOURCE_CHANGED_DURING_TRIAL")
    (a.out/"result.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS20_RESULT "+json.dumps(result,sort_keys=True),flush=True)
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except (RuntimeError,ValueError,TypeError,KeyError,OSError,AssertionError) as exc:
        print("ATLAS20_FATAL_AUDIT_FAILURE "+str(exc),flush=True)
        raise SystemExit(1)
