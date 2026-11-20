#!/usr/bin/env python3
"""DRNAS HYBRID6 — symbolic synchronous product of source-checked BDDs.

Eliminates 2^n per-machine pattern enumeration for *aligned* BDDs.
UNSAT is a sound source-CNF structural consequence. SAT is emitted only
after checking a complete Boolean assignment against EVERY source clause.
UNKNOWN is mandatory for extra constraints, unsupported order, or limits.
No general polynomial-time SAT claim: original BDDs may be exponential.

Only Python 3 standard library is needed.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

def require(condition, message):
    if not condition:
        raise ValueError(message)

def parse_dimacs(blob):
    nv=nc=None
    clauses=[]
    current=[]
    for line in blob.decode("ascii").splitlines():
        t=line.split()
        if not t or t[0]=="c":
            continue
        if t[0]=="p":
            require(nv is None and len(t)==4 and t[1]=="cnf",
                    "invalid DIMACS header")
            nv,nc=map(int,t[2:])
            require(nv>=1 and nc>=0, "invalid CNF dimensions")
            continue
        require(nv is not None,"missing header")
        for field in t:
            lit=int(field)
            if lit==0:
                clauses.append(tuple(current))
                current=[]
            else:
                require(0<abs(lit)<=nv,"out-of-range literal")
                current.append(lit)
    require(nv is not None and not current and len(clauses)==nc,
            "CNF clause count mismatch")
    return nv,clauses

def verify_structure(source,certificate):
    require(hashlib.sha256(source).hexdigest()==certificate["source_sha256"],
            "byte-exact source SHA256 mismatch")
    nv,clauses=parse_dimacs(source)
    clause_set={frozenset(cl) for cl in clauses}
    groups=certificate["groups"]
    machines=certificate["machines"]
    n=len(groups)
    m=len(machines)
    require(1<=n<=5000 and 2<=m<=8,
            "unsupported number of groups or machines")
    used_selectors=set()
    for i,g in enumerate(groups):
        require(len(g)==m and len(set(g))==m and
                all(type(v)==int and 1<=v<=nv for v in g),
                "invalid exact-one group")
        require(not(used_selectors & set(g)),
                "groups share a selector")
        require(frozenset(g) in clause_set,
                "missing source at-least-one group clause")
        for a,b in itertools.combinations(g,2):
            require(frozenset((-a,-b)) in clause_set,
                    "missing source at-most-one group clause")
        used_selectors.update(g)

    all_states=set()
    out=[]
    for j,record in enumerate(machines):
        order=record["variable_order"]
        required_order=[g[j] for g in groups]
        require(order==required_order,
                "UNSUPPORTED_SELECTOR_ORDER: require common group ordering")
        root=record["root"]
        t=record["true_terminal"]
        f=record["false_terminal"]
        require(len({root,t,f})==3,
                "root and terminals must be distinct")
        require(frozenset((root,)) in clause_set and
                frozenset((t,)) in clause_set and
                frozenset((-f,)) in clause_set,
                "missing root/terminal source unit")
        rank={x:i for i,x in enumerate(order)}
        nodes={}
        for row in record["transitions"]:
            require(len(row)==4 and
                    all(type(v)==int and 1<=v<=nv for v in row),
                    "invalid BDD transition")
            q,x,lo,hi=row
            require(q not in nodes and x in rank,
                    "repeated BDD state or unknown selector")
            require(len({q,x,lo})==3 and len({q,x,hi})==3,
                    "aliased BDD node")
            require(frozenset((-q,x,lo)) in clause_set and
                    frozenset((-q,-x,hi)) in clause_set,
                    "BDD transition is not a source implication")
            nodes[q]=(rank[x],x,lo,hi)
        require(root in nodes and t not in nodes and f not in nodes,
                "BDD root or terminals not well formed")
        states=set(nodes)|{t,f}
        require(not(states & used_selectors),
                "BDD state aliases a selected variable")
        require(not(states & all_states),
                "machines share BDD state variables")
        all_states.update(states)
        r={q:info[0] for q,info in nodes.items()}
        r[t]=r[f]=n
        for q,(_,x,lo,hi) in nodes.items():
            require(lo in states and hi in states,
                    "BDD child not included in this machine")
            require(r[lo]>rank[x] and r[hi]>rank[x],
                    "BDD has backward or cyclic edge")
        out.append({"root":root,"t":t,"f":f,
                    "nodes":nodes,"ranks":r,"states":len(states)})
    return nv,clauses,groups,out

def complete_model_ok(assignment,groups,machines,clauses):
    """Set each selected job and every active BDD path state true;
    set other variables false, then test every ORIGINAL source clause."""
    n=len(groups)
    m=len(machines)
    positive=set()
    for i,j in enumerate(assignment):
        positive.add(groups[i][j])
    for j,graph in enumerate(machines):
        q=graph["root"]
        positive.add(graph["t"])
        while q in graph["nodes"]:
            positive.add(q)
            _,selector,lo,hi=graph["nodes"][q]
            q=hi if selector in positive else lo
        if q!=graph["t"]:
            return False,0
    correct=all(any((abs(lit) in positive)==(lit>0)
                    for lit in clause) for clause in clauses)
    return correct,len(positive)

def symbolic_product(source,certificate,max_states=250000):
    """O(n*m*product_j |Q_j|) for fixed m, with aligned group order.

    A failed necessary structural condition proves UNSAT.
    A surviving path yields SAT only if all original clauses pass.
    Resource caps / non-extendible candidates produce UNKNOWN.
    """
    nv,clauses,groups,machines=verify_structure(source,certificate)
    n=len(groups)
    m=len(machines)
    require(type(max_states)==int and max_states>=1,
            "invalid max_states")
    root=tuple(g["root"] for g in machines)
    current={root}
    parents=[]
    processed=0
    visited=1
    attempted=0
    pruned_false=0
    max_frontier=1
    for i in range(n):
        next_layer={}
        for state in current:
            for chosen in range(m):
                attempted+=1
                nxt=[]
                bad=False
                for j,q in enumerate(state):
                    g=machines[j]
                    if q==g["f"]:
                        bad=True
                        break
                    if q==g["t"]:
                        nxt.append(q)
                        continue
                    node=g["nodes"][q]
                    rank,selector,lo,hi=node
                    require(rank>=i,"BDD state rank lagged global job index")
                    new_q=(hi if chosen==j else lo) if rank==i else q
                    if new_q==g["f"]:
                        bad=True
                        break
                    nxt.append(new_q)
                if bad:
                    pruned_false+=1
                    continue
                tup=tuple(nxt)
                if tup not in next_layer:
                    next_layer[tup]=(state,chosen)
        processed+=1
        # Exact no-accepting-path is a source-backed UNSAT.
        if not next_layer:
            return {"status":"UNSAT_SOURCE_SYMBOLIC_PRODUCT",
                    "jobs":n,"machines":m,"source_vars":nv,
                    "source_clauses":len(clauses),
                    "processed_jobs":processed,
                    "product_states_reached":visited,
                    "product_transitions_tried":attempted,
                    "false_branches_pruned":pruned_false,
                    "max_frontier":max_frontier,
                    "complete_source_model_checked":False,
                    "standard_veripb_proof":"NOT_EMITTED"}
        visited+=len(next_layer)
        max_frontier=max(max_frontier,len(next_layer))
        if visited>max_states:
            return {"status":"UNKNOWN_RESOURCE_LIMIT",
                    "jobs":n,"machines":m,"processed_jobs":processed,
                    "product_states_reached":visited,
                    "product_transitions_tried":attempted,
                    "max_frontier":max_frontier}
        parents.append(next_layer)
        current=set(next_layer)

    final=tuple(g["t"] for g in machines)
    require(current=={final},"unexpected nonterminal reachable at final job")
    route=[]
    q=final
    for layer in reversed(parents):
        predecessor,chosen=layer[q]
        route.append(chosen)
        q=predecessor
    route.reverse()
    require(q==root and len(route)==n,
            "internal product path reconstruction error")
    valid,ones=complete_model_ok(route,groups,machines,clauses)
    return {"status":("SAT_SOURCE_MODEL_VERIFIED" if valid else
                      "UNKNOWN_EXTRA_SOURCE_CONSTRAINTS"),
            "jobs":n,"machines":m,"source_vars":nv,
            "source_clauses":len(clauses),
            "processed_jobs":processed,
            "product_states_reached":visited,
            "product_transitions_tried":attempted,
            "false_branches_pruned":pruned_false,
            "max_frontier":max_frontier,
            "complete_source_model_checked":True,
            "complete_source_model_passed":valid,
            "true_literal_count":ones,
            "witness_machine_choices":route if valid else None,
            "standard_veripb_proof":"NOT_EMITTED"}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cnf",type=Path,required=True)
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--max-states",type=int,default=250000)
    a=p.parse_args()
    try:
        result=symbolic_product(a.cnf.read_bytes(),
                                json.loads(a.certificate.read_text()),
                                a.max_states)
        print(json.dumps(result,indent=2,sort_keys=True))
    except (ValueError,KeyError,IndexError,TypeError) as err:
        print(json.dumps({"status":"INVALID_OR_UNSUPPORTED_SOURCE",
                          "reason":str(err)}))
        raise SystemExit(1)
