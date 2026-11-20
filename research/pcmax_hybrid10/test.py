#!/usr/bin/env python3
"""MATH-HYBRID10 Hall-bound cuts: source-backed restricted-machine groups.

The generated family has a root full-weight capacity equal to demand,
so the old HYBRID9 total-weight root cut CANNOT detect its unsatisfiable
case. A restricted-group Hall cut CAN prove it, and conditional Hall
cuts prune otherwise valid but unsafe partial schedules.
"""
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research'/'pcmax_hybrid8'))
sys.path.insert(0,str(ROOT/'research'/'pcmax_hybrid9'))
sys.path.insert(0,str(ROOT/'research'/'pcmax_hybrid7'))
sys.path.insert(0,str(ROOT/'research'/'pcmax_capacity'))
from hybrid10 import quotient as hall
from hybrid9 import quotient as weighted
from quotient import quotient as symmetry
from sparse import Unsupported
from check_capacity import check as archived_capacity

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

with TemporaryDirectory() as tmp:
    temp=Path(tmp)
    # Three jobs only eligible to two one-capacity machines.
    unsat,cert=generate(temp/'unsat_special3',special_jobs=3)
    existing=weighted(unsat,cert,max_states=3000,max_seconds=5)
    # An unrestricted sum-capacity root cut cannot find this:
    assert existing['root_capacity']==10 and existing['required_demand']==10
    improvement=hall(unsat,cert,max_states=3000,max_seconds=5)
    assert improvement['status']=='UNSAT_SOURCE_HALL_ROOT_CUT',improvement
    assert set(improvement['hall_witness_groups'])=={7,8,9}
    assert improvement['product_states']==1
    print('HALL_ROOT_WITHOUT_GLOBAL_ROOT_GAP_PASS',
          json.dumps(improvement,sort_keys=True))

    # Two special jobs + two eligible machines DOES have a perfect
    # matching. Wrong early choices can lose the remaining capacity.
    sat,cert=generate(temp/'sat_special2',special_jobs=2)
    old=symmetry(sat,cert,max_states=3000,max_seconds=5)
    answer=hall(sat,cert,max_states=3000,max_seconds=5)
    assert old['status']=='UNKNOWN_ABSTRACT_COMPATIBLE',old
    assert answer['status']=='UNKNOWN_ABSTRACT_COMPATIBLE',answer
    assert answer['root_capacity']==10==answer['required_demand']
    assert answer['hall_cut_states']>0,answer
    assert answer['product_states']<old['product_states'],(answer,old)
    print('CONDITIONAL_HALL_PRUNING_SAT_SAFE_PASS',
          'old_states',old['product_states'],
          'new_states',answer['product_states'],
          'hall_prunes',answer['hall_cut_states'])

    broken=dict(cert)
    broken['group_weights']=[0]*10
    try:hall(sat,broken)
    except Unsupported: print('INVALID_WEIGHT_REJECTED')
    else: raise AssertionError('zero weights accepted')
    broken=dict(cert)
    broken['source_sha256']='0'*64
    try:hall(sat,broken)
    except Unsupported: print('INVALID_SOURCE_SHA_REJECTED')
    else: raise AssertionError('bad source hash accepted')

    # Old benchmark is independently source-capacity verified.
    originals=[]
    for case in ('00','05','09','14'):
        folder=ROOT/'evidence'/'pcmax-weighted2'/case
        data=(folder/'original.cnf').read_bytes()
        c=json.loads((folder/'capacity.json').read_text())
        witness=archived_capacity(data,c)
        result=hall(data,c,max_states=1000,max_seconds=5)
        assert witness['status']=='UNSAT_STRUCTURAL_CERTIFICATE_VERIFIED'
        assert result['status']=='UNSAT_SOURCE_WEIGHTED_ROOT_CUT',(case,result)
        assert result['root_capacity']==witness['capacity_sum']
        originals.append({'case':case,'status':result['status'],
                          'existing_demand':witness['required'],
                          'existing_capacity':witness['capacity_sum']})
        print('ARCHIVED_SOURCE_REGRESSION_PASS',
              case,result['root_capacity'],result['required_demand'])

    report={
        'status':'ALL_HYBRID10_TESTS_PASS',
        'synthetic_hall_root':improvement,
        'synthetic_sat_old_states':old['product_states'],
        'synthetic_sat_new_states':answer['product_states'],
        'synthetic_sat_hall_prunes':answer['hall_cut_states'],
        'archived_retrospective_controls':originals,
        'independent_external_proof':'NOT_EMITTED',
        'originals_newly_solved':0
    }
    Path('hybrid10-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('ALL_HYBRID10_TESTS_PASS')
