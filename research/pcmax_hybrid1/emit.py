#!/usr/bin/env python3
"""Generate an isolated PCMAX-HYBRID1 benchmark from explicit jobs.
The output CNF is newly constructed; it is NOT the original SAT2024 PCMAX CNF.
The checker in this folder independently reads source clauses and the certificate.
"""
import argparse, hashlib, json
from pathlib import Path

DEMO_JOBS=(7,8,8,9,10,10,11,11,11,13,13,17,22,23,25)
FRACTIONAL_PATTERNS=((14,1),(14,2),(13,4),(13,5),(12,6),(12,7),
                     (11,0,3),(11,1,2),(0,9,10),(3,8,9),(4,5,10),(6,7,8))

def emit(folder,control=False):
    jobs=(1,1,2) if control else DEMO_JOBS
    machines=2 if control else 6
    limit=2 if control else 33
    parity=(0,) if control else (1,2,14)
    n=len(jobs)
    clauses=[]
    def add(*lits):
        assert all(type(x)==int and x for x in lits)
        clauses.append(tuple(lits))
    def x(j,i): return j*n+i+1

    groups=[[x(j,i) for j in range(machines)] for i in range(n)]
    for g in groups:
        add(*g)
        for a in range(machines):
            for b in range(a+1,machines):
                add(-g[a],-g[b])

    nextvar=machines*n+1
    structures=[]
    for j in range(machines):
        # The state (i, remaining) is reachable after i jobs, before testing job i.
        layers=[set() for _ in jobs]
        layers[0].add(limit)
        for i in range(n-1):
            for rem in layers[i]:
                layers[i+1].add(rem)
                if rem>=jobs[i]:
                    layers[i+1].add(rem-jobs[i])
        nodes={(i,rem):nextvar+k for k,(i,rem) in
               enumerate((i,rem) for i in range(n) for rem in sorted(layers[i]))}
        nextvar+=len(nodes)
        t,f=nextvar,nextvar+1
        nextvar+=2
        root=nodes[(0,limit)]
        add(root)
        add(t)
        add(-f)
        transitions=[]
        for (i,rem),q in sorted(nodes.items()):
            lo=t if i==n-1 else nodes[(i+1,rem)]
            if rem<jobs[i]:
                hi=f
            else:
                hi=t if i==n-1 else nodes[(i+1,rem-jobs[i])]
            add(-q,x(j,i),lo)
            add(-q,-x(j,i),hi)
            transitions.append([q,x(j,i),lo,hi])
        structures.append({
            "root":root,"true_terminal":t,"false_terminal":f,
            "variable_order":[x(j,i) for i in range(n)],
            "transitions":transitions,
            "claimed_parity_capacities":[limit,limit] if control else [33,32]
        })
    folder.mkdir(parents=True,exist_ok=True)
    cnf=folder/"source_atmost.cnf"
    cnf.write_text(
        "c DRNAS HYBRID1 original-to-this-experiment at-most-capacity CNF\n"
        "c NOT a historical PCMAX benchmark; exact-one job assignment + BDD at-most caps\n"
        +f"p cnf {nextvar-1} {len(clauses)}\n"
        +''.join(' '.join(map(str,c))+' 0\n' for c in clauses)
    )
    certificate={
        "format":"pcmax-hybrid1-source-bdd-v1",
        "source_sha256":hashlib.sha256(cnf.read_bytes()).hexdigest(),
        "description":"Source-clause-checkable parity-conditioned weighted capacity contradiction",
        "jobs":list(jobs),"machine_count":machines,"limit":limit,
        "selected_groups":groups,"group_weights":list(jobs),
        "parity_group_indices":list(parity),"machines":structures,
        "claimed_demand":sum(jobs),
        "claimed_naive_capacity":machines*limit,
        "claimed_parity_capacity":4 if control else 197,
        "fractional_half_cover":[list(p) for p in FRACTIONAL_PATTERNS] if not control else [],
        "provenance":"Newly generated at-most BDD CNF, not official SAT competition original",
        "external_veripb_status":"NOT_EMITTED"
    }
    (folder/"certificate.json").write_text(json.dumps(certificate,indent=2)+"\n")
    print(json.dumps({"mode":"control" if control else "hybrid","cnf_vars":nextvar-1,
        "cnf_clauses":len(clauses),"sha256":certificate["source_sha256"],
        "certificate":str(folder/"certificate.json")},sort_keys=True))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--control",action="store_true")
    a=p.parse_args()
    emit(a.out,a.control)
