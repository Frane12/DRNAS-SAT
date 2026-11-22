#!/usr/bin/env python3
"""ATLAS12: GRAPH source-discovery -> demand/capacity Hall fact -> original VeriPB.

A deliberately SMALL modular bridge, not an integrated universal SAT solver:
GRAPH produces source-backed k-color graph clique candidate; HALL/PCMAX
translates the selected k+1 vertex ALO groups into demand and each color's
complete source mutex clique into capacity k; the *independent* PCMAX source
checker verifies ALL original clauses required by the certificate; then the
EXISTING PCMAX cutting-planes emitter compiles the standard original-source
PBP proof. External VeriPB alone may accept strict UNSAT.

Negative gate cannot prove anything: source-only facts -> UNKNOWN. No
family labels, expected SAT statuses, reference proof content or file path
enter the candidate discovery algorithm.
"""
import hashlib,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/graphclique"))
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
from emit_veripb import compile_source as _graph_baseline
from emit_veripb import parse as _graph_parse
from emit_veripb import collect as _graph_collect
from emit_veripb import graph as _graph_edges
from emit_veripb import clique_search as _graph_search
from emit_veripb import clique_alignment as _align
from emit_veripb import Unsupported as _graph_unsupported
# The PCMAX independently source-checked capacity certificate format is shared
# with graph coloring: selected disjoint ALO groups and a complete partition
# into input-proven AMO cliques with a strict deficit.
from check_php_partition import check as check_pcmax_original_source
from source_php_real26 import discover as discover_pcmax_source

def graph_to_hall(raw,max_nodes=40000):
    start=time.perf_counter()
    nv,clauses=_graph_parse(raw)
    groups,k,source_index=_graph_collect(clauses)
    adjacency,matches=_graph_edges(groups,k,clauses)
    clique,aligned,attempts=_graph_search(adjacency,k+1,
        lambda vertices:_align(vertices,groups,source_index,matches),
        max_trials=max_nodes)
    if clique is None:
        return None,{"status":"UNKNOWN_NO_GRAPH_CLIQUE","search_nodes":attempts}
    demands=[list(groups[v]) for v in clique]
    # Source-backed perfect color alignment is reverified from the original
    # binary clauses, not from a filename or graph metadata.
    capacities=[[aligned[v][color] for v in clique] for color in range(k)]
    assert len(demands)==k+1
    assert len(capacities)==k
    certificate={
        "format":"DRNAS-source-clique-capacity-v1",
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "source_variables":nv,"source_clauses":len(clauses),
        "selected_groups":demands,
        "capacity_cliques":capacities,
        "demand":len(demands),"capacity":len(capacities)}
    details={
        "status":"GRAPH_FACT_TO_HALL_CERTIFICATE_NEEDS_INDEPENDENT_CHECK",
        "source_sha256":certificate["source_sha256"],
        "graph_candidate_clique_size":len(clique),
        "EO_or_ALO_demand_groups":len(demands),
        "independently_checkable_capacity_cliques":len(capacities),
        "capacity_deficit":len(demands)-len(capacities),
        "source_aligned_pair_mutex_required":k*len(clique)*(len(clique)-1)//2,
        "source_graph_clique_search_nodes":attempts,
        "source_only_detect_s":round(time.perf_counter()-start,6),
        "mathematical_rule":"required ALO count > complete AMO resource partition",
        "does_not_use_source_family":True}
    return certificate,details

def pcmax_direct(path):
    # A separate existing source-first PCMAX detector, not merged into
    # the GRAPH facts or trusted without independent source rechecking.
    result=discover_pcmax_source(Path(path))
    if result.get("status")!="CERTIFICATE_EMITTED_UNCHECKED":
        return None,{"status":"UNKNOWN_PCMAX",**result}
    cert=result["certificate"]
    return cert,{k:v for k,v in result.items() if k!="certificate"}

def choose(raw,path,mode):
    if mode=="GRAPH_HALL_EO":
        return graph_to_hall(raw)
    if mode=="PCMAX_DIRECT":
        return pcmax_direct(path)
    raise ValueError("bad_mode")
