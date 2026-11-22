#!/usr/bin/env python3
"""ATLAS15 proof-carrying source mathematics: GRAPH + XOR3 -> Hall.

No competition labels, no source filename hints. Reads ORIGINAL source CNF:
- GRAPH: source [-a,t],[-t,-b] -> RUP mutex [-a,-b].
- XOR: FULL 4-row forbidden table for a xor b xor t = 0 and original unit
       [+t] -> RUP mutex [-a,-b]. This is stronger than bare mutex.
- HALL: original positive ALO clauses plus proven mutex resources.

All proposed facts are SHA-bound and independently checked by witness.py.
Source-only module results are always *candidate* facts, not UNSAT.
"""
from pathlib import Path
import hashlib,itertools,json,sys
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
from atlas import parse

MAX_GROUPS=32
MAX_FACTS=16
MAX_INPUT_BYTES=2_000_000

class Unknown(ValueError):pass
def demand(x,s):
    if not x:raise Unknown(s)
def digest(raw):return hashlib.sha256(raw).hexdigest()

def premise_data(raw):
    demand(len(raw)<=MAX_INPUT_BYTES,"SOURCE_SIZE_GATE")
    n,cs=parse(raw)
    demand(len(cs)<=100000,"CLAUSE_COUNT_GATE")
    index={frozenset(c) for c in cs}
    groups=sorted({tuple(sorted(c)) for c in cs if 3<=len(c)<=8 and
                   len(set(c))==len(c) and all(v>0 for v in c)})
    demand(3<=len(groups)<=MAX_GROUPS,"ALO_SOURCE_GROUP_COUNT")
    owners={}
    for g,group in enumerate(groups):
        for v in group:
            demand(v not in owners,"OVERLAPPING_SOURCE_GROUPS")
            owners[v]=g
    aux=set(range(1,n+1))-set(owners)
    existing=set()
    for clause in cs:
        if len(clause)==2 and all(v<0 for v in clause):
            a,b=sorted((-clause[0],-clause[1]))
            if a in owners and b in owners and owners[a]!=owners[b]:
                existing.add((a,b))
    return n,cs,index,groups,owners,aux,existing

def graph_facts(raw):
    n,cs,index,groups,owners,aux,existing=premise_data(raw)
    outgoing=defaultdict(set)
    for clause in cs:
        if len(clause)==2 and len(set(clause))==2:
            a,b=clause
            outgoing[-a].add(b)
            outgoing[-b].add(a)
    result={}
    for first in sorted(owners):
        for middle in sorted(outgoing[first]):
            if abs(middle) not in aux:continue
            for target in sorted(outgoing[middle]):
                end=-target
                if end not in owners or owners[first]==owners[end] or end==first:
                    continue
                a,b=sorted((first,end))
                if (a,b) in existing:continue
                c1=frozenset((-first,middle))
                c2=frozenset((-middle,-end))
                if c1 not in index or c2 not in index:continue
                result.setdefault((a,b),{"kind":"GRAPH_PATH_MUTEX","a":a,"b":b,
                    "path":[first,middle,-end],
                    "source_clauses":[sorted(c1),sorted(c2)]})
    demand(len(result)<=MAX_FACTS,"GRAPH_LEMMA_BUDGET")
    return [result[k] for k in sorted(result)]

def xor_facts(raw):
    n,cs,index,groups,owners,aux,existing=premise_data(raw)
    units={row[0] for row in cs if len(row)==1}
    sources=defaultdict(set)
    for clause in cs:
        if len(clause)!=3 or len(set(map(abs,clause)))!=3:continue
        v=tuple(sorted(map(abs,clause)))
        sources[v].add(frozenset(clause))
    result={}
    for vs,listed in sorted(sources.items()):
        sels=[v for v in vs if v in owners]
        extras=[v for v in vs if v in aux]
        if len(sels)!=2 or len(extras)!=1:continue
        a,b=sorted(sels)
        t=extras[0]
        if owners[a]==owners[b] or (a,b) in existing or t not in units:continue
        # Source XOR3 equality a XOR b XOR t = 0; complete four
        # forbidden odd-parity input assignments must literally exist.
        forbidden=[
            frozenset(-v if bit else v for v,bit in zip((a,b,t),bits))
            for bits in itertools.product((0,1),repeat=3)
            if sum(bits)%2==1]
        if not all(clause in index for clause in forbidden):continue
        claim={"kind":"XOR3_UNIT_MUTEX","a":a,"b":b,"aux":t,
               "rhs":0,"unit":t,
               "source_xor_clauses":[sorted(row) for row in forbidden]}
        result.setdefault((a,b),claim)
    demand(len(result)<=MAX_FACTS,"XOR_LEMMA_BUDGET")
    return [result[k] for k in sorted(result)]

def candidates(raw,mode):
    demand(mode in ("XOR_HALL","GRAPH_HALL","TRIPLE_HALL"),"MODE_UNSUPPORTED")
    graph=graph_facts(raw) if mode!="XOR_HALL" else []
    xor=xor_facts(raw) if mode!="GRAPH_HALL" else []
    no_duplicate={}
    for fact in graph+xor:
        pair=(fact["a"],fact["b"])
        demand(pair not in no_duplicate,"AMBIGUOUS_DUPLICATE_MUTEX_FACT")
        no_duplicate[pair]=fact
    result=[no_duplicate[k] for k in sorted(no_duplicate)]
    demand(len(result)<=MAX_FACTS,"TOO_MANY_TRANSFERRED_FACTS")
    return {"format":"DRNAS-ATLAS15-FACT-TRANSFER-v1",
      "source_sha256":digest(raw),
      "source_variables":parse(raw)[0],
      "source_clauses":len(parse(raw)[1]),
      "mode":mode,
      "facts":result,
      "graph_fact_count":len(graph),"xor_fact_count":len(xor),
      "not_an_unsat_verdict":True}
