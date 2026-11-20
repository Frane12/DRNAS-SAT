#!/usr/bin/env python3
"""Isolated HYBRID10 Hall subset: emit the UNCHANGED synthetic source CNF
and a separately checkable PCMAX weighted capacity certificate.
Does not silently strengthen or replace the original source CNF.
"""
import hashlib
import json
from pathlib import Path
import argparse

def generate(folder,n=10,m=10,special_jobs=2,restricted_machines=2):
    assert n>=special_jobs+1 and 1<=restricted_machines<m
    clauses=[]
    def add(*xs): clauses.append(tuple(xs))
    groups=[]
    for i in range(n):
        group=[j*n+i+1 for j in
               (range(m) if i<n-special_jobs else range(restricted_machines))]
        add(*group)
        for a in range(len(group)):
            for b in range(a+1,len(group)):
                add(-group[a],-group[b])
        groups.append(group)
    nxt=n*m+1
    machines=[]
    for j in range(m):
        order=[j*n+i+1 for i,g in enumerate(groups)
               if j*n+i+1 in g]
        nodes={}
        for p in range(len(order)):
            for rem in range(2):
                nodes[(p,rem)]=nxt
                nxt+=1
        t,f=nxt,nxt+1
        nxt+=2
        root=nodes[(0,1)]
        add(root);add(t);add(-f)
        tr=[]
        for (p,rem),q in sorted(nodes.items()):
            x=order[p]
            lo=t if p==len(order)-1 else nodes[(p+1,rem)]
            hi=f if rem==0 else (t if p==len(order)-1 else nodes[(p+1,rem-1)])
            add(-q,x,lo)
            add(-q,-x,hi)
            tr.append([q,x,lo,hi])
        machines.append({'root':root,'true_terminal':t,
                         'false_terminal':f,
                         'variable_order':order,'transitions':tr})
    source=('c NEW sparse cardinality special-set Hall test, NOT archived PCMAX\n'
            +f'p cnf {nxt-1} {len(clauses)}\n'
            +''.join(' '.join(map(str,c))+' 0\n' for c in clauses)).encode()
    cert={'selected_groups':groups,
          'group_weights':[1]*n,
          'machines':machines,
          'source_sha256':hashlib.sha256(source).hexdigest()}
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'source.cnf').write_bytes(source)
    (folder/'certificate.json').write_text(json.dumps(cert,indent=2)+'\n')
    return source,cert


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--special-jobs',type=int,choices=[2,3],default=3)
    args=ap.parse_args()
    source,original=generate(args.out,special_jobs=args.special_jobs)
    # Selected groups S are only the restricted final jobs.
    # The exact-one clauses for S already occur in the original CNF.
    support=original['selected_groups'][-args.special_jobs:]
    machines=json.loads(json.dumps(original['machines']))
    chosen_vars={v for group in support for v in group}
    for machine in machines:
        # Every source BDD accepts at most one job.
        # Non-special machines have no selector in the restricted subset.
        machine['capacity']=int(any(v in chosen_vars
                                    for v in machine['variable_order']))
    witness={
        'format':'pcmax-capacity-v1',
        'provenance':'synthetic DRNAS Hall example, no source-CNF changes',
        'source_sha256':hashlib.sha256(source).hexdigest(),
        'selected_groups':support,
        'group_weights':[1]*args.special_jobs,
        'required':args.special_jobs,
        'capacity_sum':sum(m['capacity'] for m in machines),
        'machines':machines,
        'external_veripb_status':'NOT_YET_CHECKED'
    }
    (args.out/'hall_witness.json').write_text(json.dumps(witness,indent=2)+'\n')
    print(json.dumps({'source_sha256':witness['source_sha256'],
          'selected_groups':len(support),'demand':witness['required'],
          'capacity':witness['capacity_sum'],
          'source_bytes':len(source)},sort_keys=True))

if __name__=='__main__':
    main()
