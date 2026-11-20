#!/usr/bin/env python3
"""Generic source-CNF-backed 3-machine exact-cover compatibility recognizer.

NO hardcoded Fano/HYBRID4/HYBRID5 allowed pattern list or problem family.
The algorithm validates original CNF group and BDD clauses, enumerates
all BDD-accepted local assignments, tests exact 3-way compatibility,
and checks a complete SAT model before reporting SAT.

The enumeration can take exponential time in the number of jobs.
UNSAT is structural (a source-clause-valid necessary condition);
this code does not itself produce a VeriPB proof.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

def need(ok,why):
    if not ok: raise ValueError(why)

def parse_dimacs(data):
    nv=nc=None
    clauses=[]
    cur=[]
    for row in data.decode('ascii').splitlines():
        fields=row.split()
        if not fields or fields[0]=='c': continue
        if fields[0]=='p':
            need(nv is None and len(fields)==4 and fields[1]=='cnf',
                 'invalid DIMACS header')
            nv,nc=map(int,fields[2:])
            need(nv>=1 and nc>=0,'negative DIMACS dimensions')
            continue
        need(nv is not None,'missing DIMACS header')
        for raw in fields:
            lit=int(raw)
            if lit:
                need(1<=abs(lit)<=nv,'CNF literal out of range')
                cur.append(lit)
            else:
                clauses.append(tuple(cur))
                cur=[]
    need(nv is not None and not cur and len(clauses)==nc,
         'source clause count mismatch')
    return nv,clauses

def check_machine(machine,groups,source,nvars,group_of):
    n=len(groups)
    order=machine['variable_order']
    need(len(order)==n and len(set(order))==n,
         'machine selector order invalid')
    need(all(v in group_of for v in order),
         'machine references unknown selector')
    need({group_of[v] for v in order}==set(range(n)),
         'machine does not represent exactly one selector per group')
    ranks={v:i for i,v in enumerate(order)}
    root,t,f=(machine[key] for key in ('root','true_terminal','false_terminal'))
    need(len({root,t,f})==3,'aliased BDD root/terminals')
    need(frozenset((root,)) in source and frozenset((t,)) in source
         and frozenset((-f,)) in source,
         'asserted root or BDD terminal source unit missing')
    nodes={}
    for row in machine['transitions']:
        need(len(row)==4 and all(type(v)==int and 1<=v<=nvars for v in row),
             'invalid/out-of-range BDD transition')
        q,x,lo,hi=row
        need(q not in nodes and x in ranks,
             'repeated state or unknown selector')
        need(len({q,x,lo})==3 and len({q,x,hi})==3,
             'state/selector alias')
        need(frozenset((-q,x,lo)) in source
             and frozenset((-q,-x,hi)) in source,
             'source CNF missing a BDD edge implication')
        nodes[q]=(x,lo,hi)
    need(root in nodes and t not in nodes and f not in nodes,
         'root/terminal misuse in BDD graph')
    states=set(nodes)|{t,f}
    need(not(states & set(order)),'BDD state aliases a selector')
    node_rank={q:ranks[x] for q,(x,_,_) in nodes.items()}
    node_rank[t]=node_rank[f]=n
    for q,(x,lo,hi) in nodes.items():
        need(lo in states and hi in states,
             'BDD has dangling child')
        need(node_rank[lo]>ranks[x] and node_rank[hi]>ranks[x],
             'BDD is unordered or cyclic')
    def route(mask):
        q=root
        while q in nodes:
            x,lo,hi=nodes[q]
            q=hi if mask & (1<<group_of[x]) else lo
        return q
    accepted={mask for mask in range(1<<n) if route(mask)==t}
    return {'accepted':accepted,'states':states,'selectors':set(order),
            'route':route,'nodes':nodes,'true_terminal':t,'root':root}

def model_from_triple(triple,groups,machines,clauses):
    n=len(groups)
    selected=set()
    for i in range(n):
        chosen=[j for j,p in enumerate(triple) if (p>>i)&1]
        need(len(chosen)==1,'invalid exact-cover triple')
        selected.add(groups[i][chosen[0]])
    for j,m in enumerate(machines):
        selected.add(m['true_terminal'])
        q=m['root']
        while q in m['nodes']:
            selected.add(q)
            x,lo,hi=m['nodes'][q]
            q=hi if x in selected else lo
        need(q==m['true_terminal'],'candidate triple does not follow true terminal')
    return all(any((abs(v) in selected)==(v>0) for v in c) for c in clauses)

def recognize(cnf_bytes,cert):
    need(hashlib.sha256(cnf_bytes).hexdigest()==cert['source_sha256'],
         'input SHA256 does not match source CNF')
    nvars,clauses=parse_dimacs(cnf_bytes)
    src={frozenset(c) for c in clauses}
    groups=cert['groups']
    n=len(groups)
    need(1<=n<=16,'bounded recognizer accepts 1..16 jobs')
    need(len(cert['machines'])==3,'this recognizer requires three machines')
    selectors=set()
    group_of={}
    for i,group in enumerate(groups):
        need(len(group)==3 and len(set(group))==3
             and all(type(v)==int and 1<=v<=nvars for v in group),
             'invalid exact-one group')
        need(frozenset(group) in src,'source missing at-least-one group')
        for a,b in itertools.combinations(group,2):
            need(frozenset((-a,-b)) in src,'source missing at-most-one group')
        need(not selectors.intersection(group),'overlapping selected groups')
        for v in group: group_of[v]=i
        selectors.update(group)

    machines=[]
    states=set()
    orders=set()
    for machine in cert['machines']:
        verified=check_machine(machine,groups,src,nvars,group_of)
        need(not states.intersection(verified['states']),
             'machine state variables overlap')
        need(not orders.intersection(verified['selectors']),
             'machine selector variables overlap')
        states.update(verified['states'])
        orders.update(verified['selectors'])
        machines.append(verified)
    need(not(states & selectors) and orders==selectors,
         'state-selector overlap or missing machine partition')

    full=(1<<n)-1
    missing=[]
    compatible=[]
    checked_pairs=0
    for a in sorted(machines[0]['accepted']):
        for b in sorted(machines[1]['accepted']):
            if a&b:continue
            checked_pairs+=1
            c=full^(a|b)
            if c in machines[2]['accepted']:
                compatible.append((a,b,c))
            else:
                missing.append((a,b,c))

    if not compatible:
        status='UNSAT_SOURCE_CONFIGURATION_OBSTRUCTION'
        sat_verified=False
    else:
        sat_verified=any(model_from_triple(w,groups,machines,clauses)
                         for w in compatible)
        status=('SAT_SOURCE_MODEL_VERIFIED' if sat_verified
                else 'UNKNOWN_EXTRA_SOURCE_CONSTRAINTS')
    return {
        'status':status,
        'source_sha256':cert['source_sha256'],
        'jobs':n,'machines':3,'vars':nvars,'clauses':len(clauses),
        'accepted_local_counts':[len(m['accepted']) for m in machines],
        'disjoint_cross_machine_pairs':checked_pairs,
        'missing_complements':len(missing),
        'compatible_pattern_triples':len(compatible),
        'example_compatible_triple':list(compatible[0]) if compatible else None,
        'model_verified_against_every_clause':sat_verified,
        'source_level_result_only':True,
        'standard_unsat_proof':'REQUIRES_INDEPENDENT_VERIPB_OR_OTHER_CHECKER',
        'complexity_note':'Enumerates up to 2^n patterns per machine; not polynomial in arbitrary CNF size'
    }

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--cnf',type=Path,required=True)
    p.add_argument('--certificate',type=Path,required=True)
    a=p.parse_args()
    try:
        result=recognize(a.cnf.read_bytes(),json.loads(a.certificate.read_text()))
        print(json.dumps(result,sort_keys=True,indent=2))
    except (ValueError,TypeError,KeyError) as error:
        print(json.dumps({'status':'INVALID_SOURCE_OR_CERTIFICATE','reason':str(error)}))
        raise SystemExit(1)
