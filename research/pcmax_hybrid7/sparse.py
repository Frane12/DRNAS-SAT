#!/usr/bin/env python3
"""MATH-HYBRID7: sparse source-backed synchronous product on ORIGINAL PCMAX CNFs.

Supports:
  - groups with fewer than m eligible machines;
  - auxiliary BDD selectors not in selected groups (existentially projected);
  - 2..64 distinct source-backed machine BDDs;
  - source-valid exact-one group clauses and rank-monotone group order.

UNSAT is a sound structural consequence of ORIGINAL CNF clauses.
A compatible projected path is only UNKNOWN, NEVER SAT: existential
auxiliary choices and omitted source clauses may be globally incompatible.
This module emits no standard RUP/VeriPB proof; its outputs must not be
mistaken for external proof-system acceptance.

Complexity can still be exponential in original CNF size, machine count,
and subset-state expansion. Budget caps return UNKNOWN, never UNSAT.
"""
import argparse
import hashlib
import json
import time
from functools import lru_cache
from itertools import combinations
from pathlib import Path

class Unsupported(ValueError):
    pass

def require(condition,message):
    if not condition:
        raise Unsupported(message)

def parse_cnf(data):
    nvars=declared=None
    pending=[]
    clauses=[]
    for line in data.decode("ascii").splitlines():
        fields=line.split()
        if not fields or fields[0]=="c":
            continue
        if fields[0]=="p":
            require(nvars is None and len(fields)==4 and fields[1]=="cnf",
                    "invalid DIMACS header")
            nvars,declared=map(int,fields[2:])
            require(nvars>0 and declared>=0,"invalid DIMACS dimensions")
            continue
        require(nvars is not None,"missing DIMACS header")
        for v in map(int,fields):
            if v:
                require(abs(v)<=nvars,"literal outside header")
                pending.append(v)
            else:
                clauses.append(frozenset(pending))
                pending=[]
    require(nvars is not None and not pending and len(clauses)==declared,
            "invalid DIMACS clause count")
    return nvars,set(clauses),len(clauses)

def validate(source, cert):
    require(cert["source_sha256"]==hashlib.sha256(source).hexdigest(),
            "SOURCE_SHA_MISMATCH")
    nvars,clauses,nclauses=parse_cnf(source)
    groups=cert.get("selected_groups",cert.get("groups"))
    machines=cert["machines"]
    require(isinstance(groups,list) and groups and
            isinstance(machines,list) and 2<=len(machines)<=64,
            "unsupported group/machine dimensions")
    n=len(groups)
    m=len(machines)
    require(n<=150,"too many selected groups")
    owner_of={}
    for i,g in enumerate(groups):
        require(len(g)>=1 and len(g)==len(set(g)) and
                all(type(v)==int and 1<=v<=nvars for v in g),
                "bad group variable")
        require(frozenset(g) in clauses,"missing source group at-least-one")
        for a,b in combinations(g,2):
            require(frozenset((-a,-b)) in clauses,
                    "EXACT_ONE_NOT_PROVED: missing source pairwise exclusion")
        for v in g:
            require(v not in owner_of,"selected selector appears in two groups")
            owner_of[v]=i

    # Distinct machine selector orders and original BDD state transitions.
    selected_map=[{} for _ in range(m)]
    machine_data=[]
    all_state_vars=set()
    all_machine_selectors=set()
    for j,raw in enumerate(machines):
        order=raw["variable_order"]
        require(order and len(order)==len(set(order)) and
                all(type(v)==int and 1<=v<=nvars for v in order),
                "invalid BDD selector order")
        require(not (all_machine_selectors & set(order)),
                "machines share selector variables")
        all_machine_selectors.update(order)
        ranks={v:k for k,v in enumerate(order)}
        seen_groups=[]
        for v in order:
            if v in owner_of:
                i=owner_of[v]
                require(i not in selected_map[j],
                        "two variables of one group on one machine")
                selected_map[j][i]=v
                seen_groups.append(i)
        require(seen_groups==sorted(seen_groups),
                "UNSUPPORTED_GROUP_ORDER: selected groups not monotone")
        nodes={}
        for row in raw["transitions"]:
            require(len(row)==4 and all(type(v)==int and 1<=v<=nvars for v in row),
                    "invalid BDD transition")
            q,x,lo,hi=row
            require(q not in nodes and x in ranks and
                    len({q,x,lo})==3 and len({q,x,hi})==3,
                    "duplicate or aliased BDD transition")
            require(frozenset((-q,x,lo)) in clauses and
                    frozenset((-q,-x,hi)) in clauses,
                    "SOURCE_BDD_EDGE_MISSING")
            nodes[q]=(x,lo,hi)
        root,t,f=(raw[k] for k in
                  ("root","true_terminal","false_terminal"))
        require(root in nodes and t!=f and
                t not in nodes and f not in nodes,
                "invalid source-backed BDD root/terminals")
        require(frozenset((root,)) in clauses and
                frozenset((t,)) in clauses and
                frozenset((-f,)) in clauses,
                "missing source root/terminal units")
        states=set(nodes)|{t,f}
        require(not(states & set(order)) and
                not(states & all_state_vars),
                "BDD state aliases selector/another machine")
        all_state_vars.update(states)
        qrank={q:ranks[row[0]] for q,row in nodes.items()}
        qrank[t]=qrank[f]=len(order)
        for q,(x,lo,hi) in nodes.items():
            require(lo in states and hi in states and
                    qrank[lo]>ranks[x] and qrank[hi]>ranks[x],
                    "BDD dangling child or invalid rank")
        machine_data.append({
            "root":root,"t":t,"f":f,
            "nodes":nodes,"selected":selected_map[j],
            "states":len(states),
            "aux_count":len(order)-len(seen_groups),
        })
    require(not (all_state_vars & all_machine_selectors),
            "BDD machine state aliases another machine selector")
    require(set(owner_of)<=all_machine_selectors,
            "selected variable has no machine BDD")
    choices=[]
    for i,g in enumerate(groups):
        js=[j for j in range(m) if i in selected_map[j]]
        require(len(js)==len(g) and js,
                "group selector-machine mapping mismatch")
        choices.append(js)
    return {
        "nvars":nvars,"nclauses":nclauses,
        "groups":groups,"machines":machine_data,"choices":choices,
        "aux_selectors":sum(x["aux_count"] for x in machine_data),
        "selected_vars":len(owner_of)
    }

def sparse_product(source, cert, max_states=2500, max_seconds=15.0):
    now=time.perf_counter()
    meta=validate(source,cert)
    machines=meta["machines"]
    n=len(meta["groups"])
    m=len(machines)
    require(type(max_states)==int and max_states>0 and
            type(max_seconds) in (float,int) and max_seconds>0,
            "invalid product budgets")
    # The closure of a state q existentially branches over every
    # auxiliary selector until a selected group selector/terminal.
    # Any model's actual source BDD path remains represented.
    normalized=[]
    def make_closure(nodes,stop,false_terminal):
        @lru_cache(maxsize=None)
        def work(q):
            if q==false_terminal:
                return frozenset()
            if q not in nodes:
                return frozenset((q,))
            x,lo,hi=nodes[q]
            if x in stop:
                return frozenset((q,))
            return work(lo) | work(hi)
        return work
    for g in machines:
        normalized.append(make_closure(g["nodes"],
                                       set(g["selected"].values()),g["f"]))

    @lru_cache(maxsize=300000)
    def advance(j,front,i,chosen):
        g=machines[j]
        nodes=g["nodes"]
        selected_v=g["selected"].get(i)
        updated=set()
        for q in front:
            if q==g["t"]:
                updated.add(q)
                continue
            x,lo,hi=nodes[q]
            group_index=group_of_machine[j].get(x)
            if group_index is None:
                raise AssertionError("nonselected selector left unprojected")
            if group_index<i:
                raise AssertionError("processed group selector reachable")
            if group_index>i:
                updated.add(q)
            else:
                require(x==selected_v,"selected-group mapping invalid")
                updated.add(hi if chosen==j else lo)
        result=set()
        for q in updated:
            result.update(normalized[j](q))
        return frozenset(result)

    group_of_machine=[
        {v:i for i,v in machine["selected"].items()}
        for machine in machines
    ]
    root=tuple(normalized[j](g["root"]) for j,g in enumerate(machines))
    if any(not v for v in root):
        return {"status":"UNSAT_SOURCE_SPARSE_PRODUCT",
                "processed_groups":0,
                "product_states":1,
                "reason":"source BDD root cannot reach any accepting path",
                "external_veripb_proof":"NOT_EMITTED"}
    layer={root}
    total=1
    maximum=1
    transitions=0
    auxiliary_choices=meta["aux_selectors"]
    for i in range(n):
        next_layer=set()
        for state in layer:
            for chosen in meta["choices"][i]:
                transitions+=1
                nxt=tuple(advance(j,state[j],i,chosen)
                          for j in range(m))
                if all(nxt):
                    next_layer.add(nxt)
                if (total+len(next_layer)>max_states or
                    time.perf_counter()-now>max_seconds):
                    return {
                        "status":"UNKNOWN_RESOURCE_LIMIT",
                        "processed_groups":i+1,
                        "product_states":total+len(next_layer),
                        "attempted_transitions":transitions,
                        "max_states":max_states,
                        "aux_selectors":auxiliary_choices,
                    }
        if not next_layer:
            return {
                "status":"UNSAT_SOURCE_SPARSE_PRODUCT",
                "processed_groups":i+1,
                "product_states":total,
                "attempted_transitions":transitions,
                "max_frontier":maximum,
                "groups":n,"machines":m,
                "aux_selectors":auxiliary_choices,
                "source_sha256":cert["source_sha256"],
                "external_veripb_proof":"NOT_EMITTED",
                "complexity_note":"poly in fixed BDD product only; not CNF"
            }
        total+=len(next_layer)
        maximum=max(maximum,len(next_layer))
        layer=next_layer
    # Complete all remaining projected auxiliary transitions
    # and ask whether each machine has an accepting terminal.
    complete=[state for state in layer if all(
        g["t"] in state[j] for j,g in enumerate(machines))]
    if not complete:
        return {
            "status":"UNSAT_SOURCE_SPARSE_PRODUCT",
            "processed_groups":n,
            "product_states":total,
            "attempted_transitions":transitions,
            "groups":n,"machines":m,
            "aux_selectors":auxiliary_choices,
            "source_sha256":cert["source_sha256"],
            "external_veripb_proof":"NOT_EMITTED",
        }
    return {
        "status":"UNKNOWN_ABSTRACT_COMPATIBLE",
        "processed_groups":n,
        "product_states":total,
        "attempted_transitions":transitions,
        "abstract_accepting_states":len(complete),
        "groups":n,"machines":m,
        "aux_selectors":auxiliary_choices,
        "source_sha256":cert["source_sha256"],
        "reason":"projected BDD paths need not satisfy all CNF clauses"
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--max-states",type=int,default=2500)
    p.add_argument("--max-seconds",type=float,default=15.0)
    args=p.parse_args()
    try:
        result=sparse_product(args.cnf.read_bytes(),
                              json.loads(args.certificate.read_text()),
                              args.max_states,args.max_seconds)
        print(json.dumps(result,sort_keys=True))
    except (Unsupported,KeyError,TypeError,IndexError,RecursionError) as err:
        print(json.dumps({"status":"UNSUPPORTED_OR_INVALID_SOURCE",
                          "reason":str(err)}))
        raise SystemExit(2)
