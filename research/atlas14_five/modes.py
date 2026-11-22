#!/usr/bin/env python3
"""ATLAS14 proof generator: only sees original CNF, mode, output paths.

Output is never a verdict; only an external checker grants UNSAT.
Source-only mode ablations:
 GRAPH_ONLY: original original-CNF graph clique proof
 HALL_ONLY: original ALO/full-resource clique proof
 EXCHANGE_ONLY: 2SAT implication graph -> Hall proof (both original modes UNKNOWN)
 BRIDGE_FULL: fixed sequence GRAPH_ONLY -> HALL_ONLY -> EXCHANGE_ONLY
No source metadata, labels or historical proof supplied.
"""
import argparse,hashlib,importlib.util,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
sys.path.insert(0,str(ROOT/"research/atlas13_exchange"))
sys.path.insert(0,str(ROOT/"research/atlas12_graph_hall"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
from source_php_real26 import discover as hall_facts
from check_php_partition import check as check_hall
from emit_veripb_source_clique import emit as emit_hall
from witness_checker import Invalid as InvalidGraph
from bridge import compile_original as emit_exchange,Unknown as UnknownExchange
_graph=importlib.util.spec_from_file_location("atlas14_graph_frozen",
           ROOT/"research/graphclique/emit_veripb.py")
graph=importlib.util.module_from_spec(_graph)
_graph.loader.exec_module(graph)
class Unknown(ValueError):pass
def sha(raw):return hashlib.sha256(raw).hexdigest()
def issue(mode,source,proof,meta):
    raw=source.read_bytes()
    t=time.perf_counter()
    proof.unlink(missing_ok=True);meta.unlink(missing_ok=True)
    if mode=="GRAPH_ONLY":
        candidate,info=graph.compile_source(raw,max_trials=50000)
        proof.write_text(candidate)
        details={"source_sha256":sha(raw),"mode":"GRAPH_ONLY",
                 "graph_meta":info,"proof_bytes":len(candidate.encode())}
    elif mode=="HALL_ONLY":
        result=hall_facts(source)
        if result.get("status")!="CERTIFICATE_EMITTED_UNCHECKED":
            raise Unknown(result.get("reason","UNKNOWN_HALL"))
        certificate=meta.with_suffix(".hall.json")
        certificate.write_text(json.dumps(result["certificate"],sort_keys=True)+"\n")
        checked=check_hall(source,certificate)
        if checked["status"]!="UNSAT_SOURCE_CLIQUE_VERIFIED":
            raise Unknown("HALL_INDEPENDENT_CHECK_NOT_VERIFIED")
        emitted=emit_hall(source,certificate,proof)
        details={"source_sha256":sha(raw),"mode":"HALL_ONLY",
                 "hall_checker":checked,"hall_emitter":emitted,
                 "proof_bytes":proof.stat().st_size}
    elif mode=="EXCHANGE_ONLY":
        certificate=meta.with_suffix(".exchange.json")
        result=emit_exchange(source,certificate,proof,meta)
        details={"source_sha256":sha(raw),"mode":"EXCHANGE_ONLY",
                 "exchange":result,"proof_bytes":proof.stat().st_size}
    else:raise Unknown("UNRECOGNIZED_MODE")
    details["proof_emitted_not_accepted"]=True
    details["elapsed_producer_s"]=round(time.perf_counter()-t,6)
    meta.write_text(json.dumps(details,sort_keys=True,indent=2)+"\n")
    return details

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",required=True,choices=("GRAPH_ONLY","HALL_ONLY","EXCHANGE_ONLY","BRIDGE_FULL"))
    ap.add_argument("--cnf",type=Path,required=True)
    ap.add_argument("--proof",type=Path,required=True)
    ap.add_argument("--meta",type=Path,required=True)
    args=ap.parse_args()
    attempt=[args.mode] if args.mode!="BRIDGE_FULL" else ["GRAPH_ONLY","HALL_ONLY","EXCHANGE_ONLY"]
    errors=[]
    for mode in attempt:
        try:
            result=issue(mode,args.cnf,args.proof,args.meta)
            result["requested_arm"]=args.mode
            result["prior_failed_modes"]=errors
            args.meta.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
            print("ATLAS14_EMITTED "+json.dumps({
              "requested_arm":args.mode,"selected":mode,
              "proof_bytes":result["proof_bytes"],"source_sha256":result["source_sha256"]},sort_keys=True),flush=True)
            return 0
        except (Unknown,graph.Unsupported,UnknownExchange,ValueError,
                TypeError,IndexError,KeyError,OSError,AssertionError,MemoryError) as e:
            args.proof.unlink(missing_ok=True)
            errors.append({"mode":mode,"reason":str(e)[:220]})
    args.meta.write_text(json.dumps({"status":"UNKNOWN","source_sha256":sha(args.cnf.read_bytes()),
                                     "requested_arm":args.mode,"attempts":errors},sort_keys=True,indent=2)+"\n")
    print("ATLAS14_UNKNOWN "+json.dumps({"mode":args.mode,"attempts":errors},sort_keys=True),flush=True)
    return 2
if __name__=="__main__":sys.exit(main())
