#!/usr/bin/env python3
"""MATH-HYBRID9: source-backed weighted cut, original PCMAX, and SAT controls.

Compare weighted root bounds with an EXISTING, independently source-
checked PCMAX certificate on EVERY archived original UNSAT instance.
The 11 originals are retrospective and already solved by the old method.
No novel real-world UNSAT claim is made.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research'/'pcmax_hybrid8'))
sys.path.insert(0,str(ROOT/'research'/'pcmax_hybrid7'))
sys.path.insert(0,str(ROOT/'research'/'pcmax_capacity'))
from hybrid9 import quotient
from quotient import quotient as baseline
from sparse import Unsupported
from check_capacity import check as verify_existing_source_capacity

ARCHIVE_IDS=('00','02','03','04','05','07','08','09','10','14','15')

def produce(script,*args):
    subprocess.run([sys.executable,str(script),*map(str,args)],
                   check=True,stdout=subprocess.DEVNULL)

def generate_cardinality(folder,n,m,capacity):
    # Brand-new synthetic source CNF with exact-one job groups and
    # independent capacity-limited machine BDDs.
    clauses=[]
    groups=[[j*n+i+1 for j in range(m)] for i in range(n)]
    for g in groups:
        clauses.append(tuple(g))
        for j in range(m):
            for k in range(j+1,m):
                clauses.append((-g[j],-g[k]))
    nextv=m*n+1
    machines=[]
    for j in range(m):
        nodes={}
        for i in range(n):
            for remaining in range(capacity+1):
                nodes[(i,remaining)]=nextv
                nextv+=1
        t,f=nextv,nextv+1
        nextv+=2
        root=nodes[(0,capacity)]
        clauses.extend(((root,),(t,),(-f,)))
        rows=[]
        for (i,remaining),q in sorted(nodes.items()):
            x=groups[i][j]
            lo=t if i==n-1 else nodes[(i+1,remaining)]
            hi=f if remaining==0 else (
                t if i==n-1 else nodes[(i+1,remaining-1)])
            clauses.append((-q,x,lo))
            clauses.append((-q,-x,hi))
            rows.append([q,x,lo,hi])
        machines.append({
            'root':root,'true_terminal':t,'false_terminal':f,
            'variable_order':[groups[i][j] for i in range(n)],
            'transitions':rows})
    cnf=(f'c hybrid9 capacity controls {n} jobs {m} machines cap={capacity}\n'
         +f'p cnf {nextv-1} {len(clauses)}\n'
         +''.join(' '.join(map(str,c))+' 0\n' for c in clauses)).encode()
    cert={'selected_groups':groups,'group_weights':[1]*n,
          'machines':machines,
          'source_sha256':hashlib.sha256(cnf).hexdigest()}
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'source.cnf').write_bytes(cnf)
    (folder/'capacity.json').write_text(json.dumps(cert))
    return cnf,cert

def reject(f,description):
    try:f()
    except (Unsupported,ValueError,KeyError,TypeError):
        print('CORRUPTION_REJECTED',description)
        return
    raise AssertionError('corrupt witness accepted: '+description)

with TemporaryDirectory() as tmp:
    temp=Path(tmp)
    for n,expected in (
        (11,'UNSAT_SOURCE_WEIGHTED_ROOT_CUT'),
        (10,'UNKNOWN_ABSTRACT_COMPATIBLE')):
        cnf,cert=generate_cardinality(temp/f'cardinality_{n}',n,10,1)
        result=quotient(cnf,cert,max_states=500,max_seconds=8)
        assert result['status']==expected,(n,result)
        if n==11:
            assert result['root_capacity']==10
            assert result['required_demand']==11
            assert result['product_states']==1
            old=baseline(cnf,cert,max_states=500,max_seconds=8)
            assert old['status']=='UNSAT_SOURCE_SYMMETRY_PRODUCT' and old['product_states']==11
        print('CARDINALITY_WEIGHTED_PASS',n,result['status'],
              'states',result['product_states'],
              'root_capacity',result['root_capacity'])

    for family,emitter,args,expected in (
        ('hybrid5_unsat',ROOT/'research/pcmax_hybrid5/emit.py',(),
         'UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT'),
        ('hybrid5_sat',ROOT/'research/pcmax_hybrid5/emit.py',('--control',),
         'UNKNOWN_ABSTRACT_COMPATIBLE'),
        ('fano_unsat',ROOT/'research/pcmax_hybrid3/emit.py',('--kind','fano'),
         'UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT'),
        ('fano_sat',ROOT/'research/pcmax_hybrid3/emit.py',('--kind','sat-control'),
         'UNKNOWN_ABSTRACT_COMPATIBLE')):
        folder=temp/family
        produce(emitter,'--out',folder,*args)
        data=(folder/'source.cnf').read_bytes()
        cert=json.loads((folder/'certificate.json').read_text())
        result=quotient(data,cert,max_states=3000,max_seconds=8)
        assert result['status']==expected,(family,result)
        print('CROSS_FAMILY_WEIGHTED_PASS',family,result['status'],
              'visited',result['product_states'],
              'cuts',result.get('cut_states'),
              'root_cap',result.get('root_capacity'))
        if family=='hybrid5_sat':
            corrupt=json.loads(json.dumps(cert))
            corrupt['group_weights']=[0]*len(cert['groups'])
            reject(lambda:quotient(data,corrupt),'zero weight vector')
            corrupt=json.loads(json.dumps(cert))
            corrupt['machines'][0]['transitions'][0][2]=corrupt['machines'][0]['false_terminal']
            reject(lambda:quotient(data,corrupt),'fake source BDD implication')

records=[]
for case in ARCHIVE_IDS:
    folder=ROOT/'evidence'/'pcmax-weighted2'/case
    data=(folder/'original.cnf').read_bytes()
    cert=json.loads((folder/'capacity.json').read_text())
    checked=verify_existing_source_capacity(data,cert)
    assert checked['status']=='UNSAT_STRUCTURAL_CERTIFICATE_VERIFIED',case
    result=quotient(data,cert,max_states=1000,max_seconds=5)
    assert result['status'] in (
        'UNSAT_SOURCE_WEIGHTED_ROOT_CUT',
        'UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT',
        'UNKNOWN_RESOURCE_LIMIT',
        'UNKNOWN_ABSTRACT_COMPATIBLE'),(case,result)
    if result.get('root_capacity') is not None:
        assert result['root_capacity']>=checked['capacity_sum'],(case,result,checked)
    if result.get('required_demand') is not None:
        assert result['required_demand']==checked['required']
    obj={'case':case,'status':result['status'],
         'original_sha256':cert['source_sha256'],
         'root_upper':result.get('root_capacity'),
         'known_original_exact_capacity':checked['capacity_sum'],
         'demand':checked['required'],
         'known_weighted_gap':checked['required']-checked['capacity_sum'],
         'product_states':result.get('product_states',result.get('states')),
         'cut_states':result.get('cut_states'),
         'source_accepted':True,
         'external_new_proof':'NOT_EMITTED'}
    records.append(obj)
    print('ORIGINAL_PCMAX_WEIGHTED_TRANSFER',json.dumps(obj,sort_keys=True))

report={'status':'ALL_HYBRID9_TESTS_PASS',
        'source_dataset':'11 retrospective original PCMAX CNFs',
        'new_root_cuts':sum(x['status']=='UNSAT_SOURCE_WEIGHTED_ROOT_CUT' for x in records),
        'new_conditional_cuts':sum(x['status']=='UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT' for x in records),
        'new_unknown':sum(x['status'].startswith('UNKNOWN_') for x in records),
        'new_standard_proofs_emitted':0,
        'original_cases':records}
Path('hybrid9-transfer.json').write_text(json.dumps(report,indent=2)+'\n')
print('ALL_HYBRID9_TESTS_PASS')
