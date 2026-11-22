#!/usr/bin/env python3
"""ATLAS12B: independent source-only structural inference mode selector.

Two complementary *existing sound* source inference modules:
  GRAPH_CLIQUE: find k+1 full matched graph-clique with k choices
  HALL_RESOURCE_GRAPH: recover source ALO groups and resource mutex cliques
    whose capacities violate demand, even without a k+1 GRAPH clique.

Both output the SAME source-bound Hall certificate, rechecked by an
independently coded verifier, then a shared existing VeriPB CP compiler.
External VeriPB acceptance on exact unchanged original is mandatory.

This mode combination does not assert new mathematical theorems or solving
cases neither of these two individual modules could solve.
"""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
sys.path.insert(0,str(ROOT/"research/graphclique"))
from source_php_real26 import discover as resource_hall_discover
from check_php_partition import check as independently_check
from emit_veripb_source_clique import emit as source_veripb_emit
from bridge import discover as clique_graph_discover
import emit_veripb as graph
def sha(raw):return hashlib.sha256(raw).hexdigest()

def discover_modes(source, budget=20000):
    started=time.perf_counter()
    source=Path(source)
    modes=[]
    try:
        cert,meta=clique_graph_discover(source,budget)
        modes.append({"mode":"GRAPH_CLIQUE","status":"CERTIFICATE_FOUND",
                      "reason":None})
        return cert,{"inference_mode":"GRAPH_CLIQUE",
                      "graph_clique":meta["GRAPH_aligned_clique"],
                      "alo_demand":meta["ALO_source_groups"],
                      "hall_capacity":meta["HALL_resources"],
                      "direct_source_EO_groups":meta["direct_source_exact_one_groups"],
                      "mode_attempts":modes,
                      "inference_s":round(time.perf_counter()-started,6)}
    except graph.Unsupported as exc:
        modes.append({"mode":"GRAPH_CLIQUE","status":"UNKNOWN",
                      "reason":str(exc)[:170]})
    recovered=resource_hall_discover(source)
    if recovered.get("status")!="CERTIFICATE_EMITTED_UNCHECKED":
        modes.append({"mode":"HALL_RESOURCE_GRAPH","status":"UNKNOWN",
                      "reason":recovered.get("reason","UNSUPPORTED")[:170]})
        raise graph.Unsupported("BOTH_SOURCE_INFERENCE_MODES_UNKNOWN "+str(modes))
    cert=recovered["certificate"]
    modes.append({"mode":"HALL_RESOURCE_GRAPH","status":"CERTIFICATE_FOUND",
                  "reason":None})
    return cert,{"inference_mode":"HALL_RESOURCE_GRAPH",
       "graph_clique":None,"alo_demand":cert["demand"],
       "hall_capacity":cert["capacity"],"mode_attempts":modes,
       "inference_s":round(time.perf_counter()-started,6)}

def run(source,cert_path,proof_path,meta_path):
    source=Path(source);cert_path=Path(cert_path);proof_path=Path(proof_path);meta_path=Path(meta_path)
    begin=time.perf_counter()
    cert,tele=discover_modes(source)
    cert_path.parent.mkdir(parents=True,exist_ok=True)
    cert_path.write_text(json.dumps(cert,indent=2,sort_keys=True)+"\n")
    independent=independently_check(source,cert_path)
    assert independent["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED"
    proof=source_veripb_emit(source,cert_path,proof_path)
    assert proof["status"]=="EMITTED_UNCHECKED"
    assert independent["sha256"]==proof["source_sha256"]==sha(source.read_bytes())
    result={**tele,"status":"UNSAT_PROOF_EMITTED_NOT_EXTERNALLY_CHECKED",
        "original_source_sha256":sha(source.read_bytes()),
        "independent_hall_source_verified":True,
        "source_evidence":independent,"proof_bytes":proof["proof_bytes"],
        "proof_sha256":proof["proof_sha256"],
        "end_to_end_without_veripb_s":round(time.perf_counter()-begin,6)}
    meta_path.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS12B_UNIFIED "+json.dumps({k:result[k] for k in (
        "inference_mode","status","original_source_sha256","alo_demand",
        "hall_capacity","proof_bytes","end_to_end_without_veripb_s")},sort_keys=True),flush=True)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--proof",type=Path,required=True)
    p.add_argument("--meta",type=Path,required=True)
    a=p.parse_args()
    try:run(a.cnf,a.certificate,a.proof,a.meta)
    except (ValueError,IndexError,KeyError,OSError,AssertionError,
            TypeError,graph.Unsupported) as exc:
        a.proof.unlink(missing_ok=True)
        a.certificate.unlink(missing_ok=True)
        a.meta.unlink(missing_ok=True)
        print("ATLAS12B_SAFE_UNKNOWN "+str(exc)[:450],flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
