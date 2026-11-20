#!/usr/bin/env python3
"""HYBRID6: exhaustive cross-family correctness and symbolic-scaling tests.

The symbolic solver NEVER enumerates 2^n local patterns. Its work
depends on reachable product BDD states and validates all source clauses.
"""
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from symbolic import symbolic_product

ROOT=Path(__file__).resolve().parents[2]

def run(script,*args):
    subprocess.run([sys.executable,str(script),*map(str,args)],
                   stdout=subprocess.DEVNULL,check=True)

def reject(fn,label):
    try:
        fn()
    except (ValueError,KeyError,IndexError,TypeError):
        print('INVALID_INPUT_REJECTED',label)
        return
    raise AssertionError('invalid CNF or certificate was accepted: '+label)

def emit_atmost(folder,n,capacity):
    """Independent parametric test generator, not part of the recognizer."""
    m=3
    groups=[[j*n+i+1 for j in range(m)] for i in range(n)]
    clauses=[]
    for g in groups:
        clauses.append(tuple(g))
        for i in range(m):
            for j in range(i+1,m):
                clauses.append((-g[i],-g[j]))
    nextv=m*n+1
    machines=[]
    for j in range(m):
        nodes={}
        for i in range(n):
            for rem in range(capacity+1):
                nodes[(i,rem)]=nextv
                nextv+=1
        t,f=nextv,nextv+1
        nextv+=2
        root=nodes[(0,capacity)]
        clauses.extend(((root,),(t,),(-f,)))
        transitions=[]
        for (i,rem),q in sorted(nodes.items()):
            x=groups[i][j]
            lo=t if i==n-1 else nodes[(i+1,rem)]
            hi=(f if rem==0 else
                (t if i==n-1 else nodes[(i+1,rem-1)]))
            clauses.append((-q,x,lo))
            clauses.append((-q,-x,hi))
            transitions.append([q,x,lo,hi])
        machines.append({'root':root,
                         'true_terminal':t,
                         'false_terminal':f,
                         'variable_order':[groups[i][j] for i in range(n)],
                         'transitions':transitions})
    source=(f'c New symbolic-product regression, 3 machines cap={capacity}, '
            f'jobs={n}; NOT original PCMAX\n'
            f'p cnf {nextv-1} {len(clauses)}\n'
            +''.join(' '.join(map(str,c))+' 0\n' for c in clauses)
    blob=source.encode('ascii')
    cert={'source_sha256':hashlib.sha256(blob).hexdigest(),
          'groups':groups,'machines':machines,
          'provenance':'synthetic symbolic scaling control'}
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'source.cnf').write_bytes(blob)
    (folder/'certificate.json').write_text(json.dumps(cert))
    return blob,cert

def add_empty_clause(blob,cert):
    lines=blob.decode('ascii').splitlines()
    rows=[i for i,t in enumerate(lines) if t.startswith('p cnf ')]
    assert len(rows)==1
    i=rows[0]
    hd=lines[i].split()
    hd[-1]=str(int(hd[-1])+1)
    lines[i]=' '.join(hd)
    lines.append('0')
    newblob=('\n'.join(lines)+'\n').encode()
    newcert=deepcopy(cert)
    newcert['source_sha256']=hashlib.sha256(newblob).hexdigest()
    return newblob,newcert

with TemporaryDirectory() as temp:
    root=Path(temp)
    h5=ROOT/'research/pcmax_hybrid5/emit.py'
    h3=ROOT/'research/pcmax_hybrid3/emit.py'
    for name,emitter,args,expected in (
        ('hybrid5_unsat',h5,(),
         'UNSAT_SOURCE_SYMBOLIC_PRODUCT'),
        ('hybrid5_sat',h5,('--control',),
         'SAT_SOURCE_MODEL_VERIFIED'),
        ('fano_unsat',h3,('--kind','fano'),
         'UNSAT_SOURCE_SYMBOLIC_PRODUCT'),
        ('fano_sat',h3,('--kind','sat-control'),
         'SAT_SOURCE_MODEL_VERIFIED'),
    ):
        folder=root/name
        run(emitter,'--out',folder,*args)
        data=(folder/'source.cnf').read_bytes()
        cert=json.loads((folder/'certificate.json').read_text())
        answer=symbolic_product(data,cert)
        assert answer['status']==expected, (name,answer)
        assert answer['product_states_reached'] < 500
        print('CROSS_FAMILY_SYMBOLIC_PASS',name,answer['status'],
              'states',answer['product_states_reached'],
              'transitions',answer['product_transitions_tried'])
        if name=='hybrid5_sat':
            contaminated,altered=add_empty_clause(data,cert)
            cautious=symbolic_product(contaminated,altered)
            assert cautious['status']=='UNKNOWN_EXTRA_SOURCE_CONSTRAINTS',cautious
            print('EXTRA_CLAUSE_UNKNOWN_PASS')
            reject(lambda:symbolic_product(data,altered),'SHA change')
            wrong=deepcopy(cert)
            wrong['machines'][0]['variable_order'][0],wrong['machines'][0]['variable_order'][1]=(
                wrong['machines'][0]['variable_order'][1],wrong['machines'][0]['variable_order'][0])
            reject(lambda:symbolic_product(data,wrong),'unmatched selector ordering')
            wrong=deepcopy(cert)
            wrong['machines'][0]['transitions'][0][2]=wrong['machines'][0]['false_terminal']
            reject(lambda:symbolic_product(data,wrong),'fake transition source clause')
            limited=symbolic_product(data,cert,max_states=1)
            assert limited['status']=='UNKNOWN_RESOURCE_LIMIT',limited
            print('RESOURCE_CAP_UNKNOWN_PASS')

    blob,cert=emit_atmost(root/'large_unsat',80,1)
    ans=symbolic_product(blob,cert)
    assert ans['status']=='UNSAT_SOURCE_SYMBOLIC_PRODUCT',ans
    assert ans['processed_jobs']==4
    assert ans['product_states_reached']<100
    print('LARGE_SYMBOLIC_80_JOB_UNSAT_PASS',
          ans['product_states_reached'],ans['processed_jobs'],
          'old_local_assignment_space',f'2^{80}')

    blob,cert=emit_atmost(root/'large_sat',36,12)
    ans=symbolic_product(blob,cert)
    assert ans['status']=='SAT_SOURCE_MODEL_VERIFIED',ans
    assert ans['complete_source_model_passed']
    assert ans['product_states_reached']<40000
    print('LARGE_SYMBOLIC_36_JOB_SAT_PASS',ans['product_states_reached'],
          ans['product_transitions_tried'],ans['max_frontier'])
    print('ALL_SYMBOLIC_TESTS_PASS')
