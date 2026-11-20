#!/usr/bin/env python3
"""HYBRID6: source-level RUP/VeriPB refutation from reachable BDD product states.

For source-checked aligned BDDs with NO compatible accepting product,
derive a small blocking clause for each reachable product state backwards.
At every group, derive one RUP guard for each machine choice, then the
joint-state blocking clause, using the source exact-one clause.

No 2^n or m^n assignment enumeration occurs in this generator.
Proofs MUST be checked separately with VeriPB; generator status is never
a proof acceptance claim. Runtime/proof length is polynomial only in
SUPPLIED aligned BDD sizes for fixed machine count m.
"""
import argparse
import hashlib
import json
from pathlib import Path

from symbolic import verify_structure

def product_layers(source,cert,max_states):
    _,_,groups,graphs=verify_structure(source,cert)
    n=len(groups); m=len(graphs)
    layers=[{tuple(g['root'] for g in graphs)}]
    attempts=0
    for i in range(n):
        nxt=set()
        for state in layers[-1]:
            for chosen in range(m):
                attempts+=1
                child=[]
                for j,q in enumerate(state):
                    g=graphs[j]
                    if q==g['t']:
                        child.append(q)
                        continue
                    if q==g['f']:
                        raise AssertionError('false terminal was already reachable')
                    rank,selector,lo,hi=g['nodes'][q]
                    if rank<i:
                        raise AssertionError('BDD lost selector synchronization')
                    q2=(hi if chosen==j else lo) if rank==i else q
                    if q2==g['f']:
                        break
                    child.append(q2)
                else:
                    nxt.add(tuple(child))
        if sum(map(len,layers))+len(nxt)>max_states:
            raise RuntimeError('PRODUCT_RESOURCE_LIMIT')
        layers.append(nxt)
        if not nxt:
            return groups,graphs,layers,attempts
    return groups,graphs,layers,attempts

def generate(source,cert,out,max_states=250000):
    if type(max_states)!=int or max_states<1:
        raise ValueError('max_states must be a positive integer')
    groups,graphs,layers,attempted=product_layers(source,cert,max_states)
    if layers[-1]:
        raise ValueError('NO_UNSAT_PROOF: BDD product admits a full assignment')
    n=len(groups)
    m=len(graphs)
    finish_level=len(layers)-1
    rows=[]
    guards=0
    blocks=0
    for i in range(finish_level-1,-1,-1):
        for state in sorted(layers[i]):
            blocker=tuple(-q for q in state)
            for chosen in range(m):
                # RUP: with all q states and x_i,chosen true,
                # source exact-one clauses and BDD edges force the
                # already-blocked child state (or false terminal).
                rows.append(blocker+(-groups[i][chosen],))
                guards+=1
            # RUP: under all q states, every machine choice
            # x_i,j must be false; source at-least-one gives conflict.
            rows.append(blocker)
            blocks+=1
    # The root states are positive source units. After their
    # blocking clause is learned, the empty clause is RUP.
    rows.append(())
    out.mkdir(parents=True,exist_ok=True)
    drup=out/'proof.drup'
    pbp=out/'proof.pbp'
    drup.write_text(''.join(
        ' '.join(map(str,c))+' 0\n' for c in rows))
    # Source clause count read from original, checked DIMACS header.
    header=[line for line in source.decode('ascii').splitlines()
            if line.startswith('p cnf ')]
    if len(header)!=1:
        raise ValueError('missing or ambiguous CNF header')
    nclauses=int(header[0].split()[3])
    with pbp.open('w') as fp:
        fp.write('pseudo-Boolean proof version 3.0\n')
        fp.write(f'f {nclauses} ;\n')
        for clause in rows:
            terms=' '.join('1 ~x'+str(-v) for v in clause)
            fp.write('rup '+(terms+' ' if terms else '')+'>= 1 ;\n')
        fp.write('output NONE ;\n')
        fp.write('conclusion UNSAT ;\n')
        fp.write('end pseudo-Boolean proof ;\n')
    manifest={
        'status':'EMITTED_UNCHECKED',
        'method':'reverse reachable synchronous-BDD-product RUP',
        'source_sha256':hashlib.sha256(source).hexdigest(),
        'number_of_jobs':n,'machines':m,
        'source_bdd_states_per_machine':[g['states'] for g in graphs],
        'layers_before_empty':finish_level,
        'reachable_product_states':sum(map(len,layers)),
        'reachable_product_layer_widths':list(map(len,layers)),
        'product_attempts':attempted,
        'rup_steps':len(rows),
        'guard_steps':guards,'product_block_steps':blocks,
        'drup_sha256':hashlib.sha256(drup.read_bytes()).hexdigest(),
        'pbp_sha256':hashlib.sha256(pbp.read_bytes()).hexdigest(),
        'external_veripb_status':'REQUIRES_SEPARATE_VERIFICATION',
        'complexity_scope':'polynomial in supplied BDD size for fixed m; not in arbitrary original CNF'
    }
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--cnf',type=Path,required=True)
    p.add_argument('--certificate',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-states',type=int,default=250000)
    a=p.parse_args()
    try:
        obj=generate(a.cnf.read_bytes(),
                     json.loads(a.certificate.read_text()),
                     a.out,a.max_states)
        print(json.dumps(obj,indent=2,sort_keys=True))
    except (ValueError,RuntimeError,KeyError,IndexError) as error:
        print(json.dumps({'status':'NO_PROOF_EMITTED','reason':str(error)}))
        raise SystemExit(1)
