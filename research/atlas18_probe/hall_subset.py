#!/usr/bin/env python3
"""ATLAS18 original-source disjoint-demand subset Hall proof.

Unlike REAL26, does NOT require selected positive at-least-one groups to cover
all declared variables. Ignored clauses and variables cannot invalidate an
UNSAT proof built from a source-supported subset. Complement-graph DSATUR
partitions selector literals into capacity-one cliques. Optional proof-carrying
binary-implication GRAPH and complete-XOR3+unit lemmas supply missing mutexes.
Every new lemma is inserted as a standard PBP RUP line BEFORE CP derivations.
Only external VeriPB on the exact unchanged original CNF grants UNSAT.
"""
import argparse
import hashlib
import itertools
import json
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/pcmax_capacity"))
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
from atlas import parse, encoded
from check_php_partition import check as independent_hall_check
from emit_veripb_source_clique import emit as hall_emitter

MAX_BYTES=7_000_000
MAX_VARS=15000
MAX_CLAUSES=250000
MAX_OPTIONS=360
MAX_FACTS=1400
MAX_CANDIDATES=600
MAX_UCP_CLAUSES=20000
MAX_UCP_SELECTORS=360

class Unknown(ValueError): pass

def need(cond, reason):
    if not cond:raise Unknown(reason)

def sha(data):return hashlib.sha256(data).hexdigest()

def read_source(raw):
    need(len(raw)<=MAX_BYTES,"SOURCE_BYTES_GATE")
    n,cs=parse(raw)
    need(n<=MAX_VARS and len(cs)<=MAX_CLAUSES,"DIMACS_SIZE_GATE")
    positive=set()
    direct=set()
    index=set()
    binary=defaultdict(set)
    triples=defaultdict(set)
    units=set()
    for clause in cs:
        index.add(frozenset(clause))
        if 2<=len(clause)<=64 and all(lit>0 for lit in clause) and len(set(clause))==len(clause):
            positive.add(tuple(sorted(clause)))
        if len(clause)==1:units.add(clause[0])
        if len(clause)==2 and len(set(clause))==2:
            x,y=clause
            binary[-x].add(y)
            binary[-y].add(x)
            if x<0 and y<0:
                direct.add(tuple(sorted((-x,-y))))
        if len(clause)==3 and len(set(map(abs,clause)))==3:
            triples[tuple(sorted(map(abs,clause)))].add(frozenset(clause))
    return n,cs,positive,direct,index,binary,triples,units

def candidate_groups(positive):
    positive=sorted(positive)
    frequency=Counter(map(len,positive))
    orders=[
        ("frequency",sorted(positive,key=lambda g:(-frequency[len(g)],-len(g),g))),
        ("wide",sorted(positive,key=lambda g:(-len(g),g))),
        ("narrow",sorted(positive,key=lambda g:(len(g),g))),
    ]
    options=[];seen=set()
    for strategy,rows in orders:
        chosen=[];used=set()
        for group in rows:
            if len(used)+len(group)>MAX_OPTIONS:
                continue
            if not used.intersection(group):
                used.update(group);chosen.append(group)
        fingerprint=tuple(sorted(chosen))
        if len(chosen)<3 or fingerprint in seen:continue
        seen.add(fingerprint)
        options.append((strategy,sorted(chosen),used))
    return options

def graph_lemmata(selected,owners,binary,direct):
    result={}
    # Any 2-hop source implication -a|t, -t|-b derives -a|-b by RUP.
    for first in sorted(selected):
        for middle in binary.get(first,()):
            if abs(middle) in selected:continue
            for terminal in binary.get(middle,()):
                b=-terminal
                if b not in selected or b==first or owners[b]==owners[first]:continue
                a,c=sorted((first,b))
                if (a,c) in direct:continue
                result.setdefault((a,c),{"a":a,"b":c,"kind":"GRAPH_RUP",
                   "source_premises":[[-first,middle],[-middle,-b]]})
                if len(result)>MAX_FACTS:raise Unknown("GRAPH_FACT_BUDGET")
    return result

def ucp_lemmata(n,clauses,selected,direct):
    """Original-source unit propagation derives proof-carrying binary mutexes.

    For selector a, propagation of original F and assumption a to ~b is a
    RUP witness of (-a or -b). No decisions beyond the single source
    assumption, no clause learning, no external SAT/CDCL oracle.
    """
    need(len(clauses)<=MAX_UCP_CLAUSES and len(selected)<=MAX_UCP_SELECTORS,
         "UCP_STRUCTURAL_SCAN_BUDGET")
    occurrence=defaultdict(list)
    roots=[]
    for i,clause in enumerate(clauses):
        if not clause:raise Unknown("EMPTY_INPUT_CLAUSE_NEEDS_SEPARATE_PROOF")
        if len(clause)==1:roots.append(clause[0])
        for lit in clause: occurrence[-lit].append(i)
    def propagate(assumption):
        assigned=[0]*(n+1)
        q=deque([*roots,assumption])
        while q:
            lit=q.popleft()
            v=abs(lit);value=1 if lit>0 else -1
            if assigned[v]:
                if assigned[v]!=value:return True,assigned
                continue
            assigned[v]=value
            for clause_id in occurrence[lit]:
                clause=clauses[clause_id]
                remaining=0;unit=0;satisfied=False
                for x in clause:
                    val=assigned[abs(x)]
                    if val==0:remaining+=1;unit=x
                    elif val==(1 if x>0 else -1):
                        satisfied=True
                        break
                if satisfied:continue
                if remaining==0:return True,assigned
                if remaining==1:q.append(unit)
        return False,assigned
    result={}
    for a in sorted(selected):
        contradiction,forced=propagate(a)
        if contradiction:
            raise Unknown("UCP_SINGLE_SELECTOR_ALREADY_CONTRADICTS_SOURCE")
        for b in selected:
            if b==a or forced[b]!=-1:continue
            pair=tuple(sorted((a,b)))
            if pair not in direct:
                result.setdefault(pair,{"a":pair[0],"b":pair[1],
                    "kind":"UCP_RUP","source_premises":["unit-propagation-original"]})
                need(len(result)<=MAX_FACTS,"UCP_FACT_BUDGET")
    return result

def xor_lemmata(selected,owners,triples,units,index,direct):
    result={}
    for vs,rows in triples.items():
        sels=sorted(v for v in vs if v in selected)
        others=[v for v in vs if v not in selected]
        if len(sels)!=2 or len(others)!=1:continue
        a,b=sels;t=others[0]
        if owners[a]==owners[b] or (a,b) in direct:continue
        # a XOR b XOR t = 0, with t=1, entails NOT(a AND b).
        if t not in units:continue
        full={
            frozenset(-v if bit else v for v,bit in zip((a,b,t),bits))
            for bits in itertools.product((0,1),repeat=3)
            if sum(bits)%2==1}
        if full<=index:
            result[(a,b)]={"a":a,"b":b,"kind":"XOR_RUP","source_premises":[
                sorted(r) for r in sorted(full,key=lambda f:tuple(sorted(f)))]}
        if len(result)>MAX_FACTS:raise Unknown("XOR_FACT_BUDGET")
    return result

def coloring(selected,pairs):
    # Each color class is a clique of mutually exclusive positive selectors.
    # This is graph coloring of the *complement* of proven mutex graph.
    ids=sorted(selected)
    nonconf={v:set(ids)-{v} for v in ids}
    for a,b in pairs:
        if a in nonconf and b in nonconf:
            nonconf[a].discard(b);nonconf[b].discard(a)
    sat={v:set() for v in ids}
    colors={}
    available=set(ids)
    while available:
        v=max(available,key=lambda x:(len(sat[x]),len(nonconf[x]),-x))
        color=0
        while color in sat[v]:color+=1
        colors[v]=color;available.remove(v)
        for w in nonconf[v] & available:sat[w].add(color)
    groups=defaultdict(list)
    for v,c in colors.items():groups[c].append(v)
    resources=[sorted(x) for x in groups.values()]
    # Defensive check: independent of the color selection code.
    for resource in resources:
        for a,b in itertools.combinations(resource,2):
            assert (min(a,b),max(a,b)) in pairs
    resources.sort(key=lambda x:(x[0],len(x)))
    return resources

def build(source,mode,output,metadata):
    start=time.perf_counter()
    need(mode in ("DIRECT","GRAPH","XOR","JOINT","UCP","JOINT_UCP"),"UNKNOWN_MODE")
    raw=Path(source).read_bytes()
    n,cs,positive,direct,index,binary,triples,units=read_source(raw)
    candidates=candidate_groups(positive)
    need(bool(candidates),"NO_DISJOINT_ALO_SUBSET_WITHIN_BUDGET")
    attempts=[];accepted=None
    for strategy,groups,selected in candidates:
        owners={v:i for i,row in enumerate(groups) for v in row}
        asserted=set((a,b) for a,b in direct if a in selected and b in selected)
        graph={};xor={};ucp={}
        if mode in ("GRAPH","JOINT","JOINT_UCP"):
            try:graph=graph_lemmata(selected,owners,binary,direct)
            except Unknown as e:
                attempts.append({"strategy":strategy,"reason":str(e)})
                continue
        if mode in ("XOR","JOINT","JOINT_UCP"):
            try:xor=xor_lemmata(selected,owners,triples,units,index,direct)
            except Unknown as e:
                attempts.append({"strategy":strategy,"reason":str(e)})
                continue
        if mode in ("UCP","JOINT_UCP"):
            try:ucp=ucp_lemmata(n,cs,selected,direct)
            except Unknown as e:
                attempts.append({"strategy":strategy,"reason":str(e)})
                continue
        facts={**ucp,**graph,**xor}
        # If both producers claim the same lemma, either one suffices.
        # Preserve proof origin and do not treat a duplicate as a new fact.
        if len(asserted)+len(facts)>MAX_CANDIDATES*12:
            attempts.append({"strategy":strategy,"reason":"FACT_MATRIX_GATE"});continue
        pairs=asserted|set(facts)
        resources=coloring(selected,pairs)
        detail={"strategy":strategy,"groups":len(groups),"selectors":len(selected),
                "resources":len(resources),"original_pairs":len(asserted),
                "graph_new":len(graph),"xor_new":len(xor),"ucp_new":len(ucp)}
        if len(resources)>=len(groups):
            attempts.append({**detail,"reason":"NO_CAPACITY_DEFICIT"});continue
        if any(len(resource)<2 for resource in resources):
            attempts.append({**detail,"reason":"SINGLETON_RESOURCE_NOT_SUPPORTED"});continue
        missing={}
        for clique in resources:
            for a,b in itertools.combinations(clique,2):
                pair=(min(a,b),max(a,b))
                if pair not in asserted:missing[pair]=facts[pair]
        if len(missing)>MAX_FACTS:
            attempts.append({**detail,"reason":"TOO_MANY_PROOF_LEMMAS"});continue
        accepted=(strategy,groups,resources,missing,detail)
        break
    need(accepted is not None,"NO_BOUNDED_HALL_CERTIFICATE:"+json.dumps(attempts)[:700])
    strategy,groups,resources,missing,detail=accepted
    # Prove against augmented CNF, then replace each extra input axiom by an
    # externally checked RUP lemma in the proof of the UNCHANGED original.
    lemmas=[(-a,-b) for a,b in sorted(missing)]
    with tempfile.TemporaryDirectory(prefix="atlas18-proofbus-") as temp:
        p=Path(temp)
        src=p/"augmented.cnf"
        src.write_bytes(encoded(n,cs+lemmas))
        cert={"format":"DRNAS-source-clique-capacity-v1",
            "source_sha256":sha(src.read_bytes()),"source_variables":n,
            "source_clauses":len(cs)+len(lemmas),
            "selected_groups":[list(g) for g in groups],
            "capacity_cliques":resources,
            "demand":len(groups),"capacity":len(resources)}
        certfile=p/"certificate.json"
        certfile.write_text(json.dumps(cert,sort_keys=True)+"\n")
        checked=independent_hall_check(src,certfile)
        need(checked["status"]=="UNSAT_SOURCE_CLIQUE_VERIFIED","INDEPENDENT_HALL_CHECK_REJECTED")
        pbp=p/"augmented.pbp"
        emitted=hall_emitter(src,certfile,pbp)
        need(emitted["status"]=="EMITTED_UNCHECKED","EMITTER_FAILED")
        lines=pbp.read_text().splitlines()
        need(lines[:2]==["pseudo-Boolean proof version 3.0",
                          f"f {len(cs)+len(lemmas)} ;"],"PBP_HEADER_WRONG")
        lifted=["pseudo-Boolean proof version 3.0",f"f {len(cs)} ;"]
        for a,b in sorted(missing):
            lifted.append(f"rup 1 ~x{a} 1 ~x{b} >= 1 ;")
        lifted.extend(lines[2:])
        complete="\n".join(lifted)+"\n"
    output=Path(output);metadata=Path(metadata)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(complete)
    result={"status":"EMITTED_UNCHECKED","mode":mode,
       "source_sha256":sha(raw),"source_variables":n,"source_clauses":len(cs),
       "required_groups":len(groups),"capacity_resources":len(resources),
       "capacity_deficit":len(groups)-len(resources),
       "selected_selectors":len({v for group in groups for v in group}),
       "derived_RUP_lemmata":len(missing),
       "graph_RUP_used":sum(x["kind"]=="GRAPH_RUP" for x in missing.values()),
       "xor_RUP_used":sum(x["kind"]=="XOR_RUP" for x in missing.values()),
       "ucp_RUP_used":sum(x["kind"]=="UCP_RUP" for x in missing.values()),
       "direct_source_mutex_pairs":detail["original_pairs"],
       "source_sha_unchanged":True,
       "proof_sha256":sha(complete.encode()),"proof_bytes":len(complete),
       "elapsed_producer_s":round(time.perf_counter()-start,6),
       "external_original_Veripb_required":True,
       "attempts":attempts}
    metadata.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--cnf",required=True,type=Path)
    a.add_argument("--mode",required=True,choices=("DIRECT","GRAPH","XOR","JOINT","UCP","JOINT_UCP"))
    a.add_argument("--proof",required=True,type=Path)
    a.add_argument("--meta",required=True,type=Path)
    p=a.parse_args()
    try:
        result=build(p.cnf,p.mode,p.proof,p.meta)
        print("ATLAS18_PROOF_EMITTED "+json.dumps(result,sort_keys=True),flush=True)
    except (Unknown,ValueError,KeyError,TypeError,OSError,AssertionError,
            OverflowError,MemoryError,IndexError) as error:
        p.proof.unlink(missing_ok=True);p.meta.unlink(missing_ok=True)
        print("ATLAS18_SAFE_UNKNOWN "+str(error)[:900],flush=True)
        raise SystemExit(2)
if __name__=="__main__":main()
