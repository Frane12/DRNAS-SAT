#!/usr/bin/env python3
"""Deterministic connected synthetic PCMAX-style CNF. Not a rescaled original m30."""
import functools, random, hashlib, json, argparse
from pathlib import Path

def build(half=43, cap=3, seed=20261121):
    num_machines=2*half
    restricted=half*cap+2
    jobs=2*half*cap-2
    assert restricted < jobs
    options=[list(range(half)) for _ in range(restricted)]+[list(range(num_machines)) for _ in range(jobs-restricted)]
    current=0
    selectors={}
    clauses=[]
    for j, allowed in enumerate(options):
        group=[]
        for m in allowed:
            current+=1
            selectors[j,m]=current
            group.append(current)
        clauses.append(tuple(group))
        for idx,a in enumerate(group):
            for b in group[idx+1:]:
                clauses.append((-a,-b))
    stats=[]
    for machine in range(num_machines):
        xs=[selectors[j,machine] for j in range(jobs) if (j,machine) in selectors]
        current+=1; true=current
        current+=1; false=current
        unique={}
        transitions=[]
        @functools.lru_cache(None)
        def node(j, load):
            nonlocal current
            if load>cap:
                return false
            if j==len(xs):
                return true
            lo=node(j+1,load)
            hi=node(j+1,load+1)
            if lo==hi:
                return lo
            var=xs[j]
            key=(var,lo,hi)
            if key not in unique:
                current+=1
                q=current
                unique[key]=q
                clauses.append((var,-q,lo))
                clauses.append((-var,-q,hi))
                transitions.append((q,var,lo,hi))
            return unique[key]
        root=node(0,0)
        clauses.extend(((root,),(true,),(-false,)))
        stats.append({'machine':machine,'selectors':len(xs),'bdd_nodes':len(transitions)})
    rng=random.Random(seed)
    perm=list(range(1,current+1));rng.shuffle(perm);perm=[0]+perm
    shuffled=[]
    for clause in clauses:
        shuffled.append(tuple(perm[x] if x>0 else -perm[-x] for x in clause))
    rng.shuffle(shuffled)
    return current,shuffled,{'seed':seed,'half_machines':half,'machine_cap':cap,
        'jobs':jobs,'restricted_jobs':restricted,'machines':num_machines,
        'global_capacity':num_machines*cap,'restricted_capacity':half*cap,
        'hidden_hall_deficit':restricted-half*cap,
        'selectors':len(selectors),'bdd_states':sum(s['bdd_nodes'] for s in stats),
        'cnf_variables':current,'cnf_clauses':len(shuffled),
        'generator_kind':'synthetic connected PCMAX-style BDD + ALO/AMO',
        'not_original_m30':True}

def write(target, half=43, cap=3, seed=20261121):
    n,clauses,meta=build(half,cap,seed)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='ascii') as f:
        f.write(f'p cnf {n} {len(clauses)}\n')
        for c in clauses:f.write(' '.join(map(str,c))+' 0\n')
    meta['source_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
    meta['source_bytes']=target.stat().st_size
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    p.add_argument('--half',type=int,default=43);p.add_argument('--cap',type=int,default=3)
    p.add_argument('--seed',type=int,default=20261121)
    args=p.parse_args()
    print(json.dumps(write(args.output,args.half,args.cap,args.seed),sort_keys=True,indent=2))
