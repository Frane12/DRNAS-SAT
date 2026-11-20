#!/usr/bin/env python3
"""Positive, negative, tamper and exhaustive audits for source-CNF hybrid1."""
import hashlib, json, tempfile
from pathlib import Path
from copy import deepcopy
from emit import emit
from check import read_cnf, check, Invalid

def reject(fn,label):
    try: fn()
    except (Invalid, ValueError, KeyError, TypeError, IndexError):
        print("REJECTED_TAMPER",label)
        return
    raise AssertionError("undetected tamper: "+label)

with tempfile.TemporaryDirectory() as tmp:
    demo=Path(tmp)/"demo"
    control=Path(tmp)/"sat_control"
    emit(demo)
    data=(demo/"source_atmost.cnf").read_bytes()
    cert=json.loads((demo/"certificate.json").read_text())
    result=check(data,cert)
    assert result["status"]=="STRUCTURAL_HYBRID_UNSAT_CHECKED",result
    assert result["demand"]==198 and result["ordinary_capacity"]==198
    assert result["parity_conditioned_capacity"]==197
    assert result["fractional_cover_verified"]
    assert all(c==[33,32] for c in result["machine_capacities"])
    print("HYBRID_DEMO_VERIFIED",json.dumps(result,sort_keys=True))

    # Direct brute-force local audit, independent of the BDD recurrence.
    jobs=cert['jobs']
    pari=set(cert['parity_group_indices'])
    values=[[],[]]
    full_count=0
    for mask in range(1<<len(jobs)):
        load=sum(jobs[i] for i in range(len(jobs)) if mask>>i&1)
        if load>cert['limit']:continue
        p=sum((mask>>i)&1 for i in pari)%2
        values[p].append(load)
        full_count+=(load==cert['limit'])
    assert [len(a) for a in values]==[146,100]
    assert [max(a) for a in values]==[33,32]
    assert full_count==21
    print("LOCAL_ENUMERATION_PASS",len(values[0]),len(values[1]),full_count)

    d=deepcopy(cert);d['machines'][0]['claimed_parity_capacities'][1]+=1
    reject(lambda:check(data,d),"false local parity capacity")
    d=deepcopy(cert);d['group_weights'][0]+=1
    reject(lambda:check(data,d),"false job weight certificate")
    d=deepcopy(cert);d['machines'][0]['transitions'][0][2]=d['machines'][0]['false_terminal']
    reject(lambda:check(data,d),"missing source BDD clause")
    d=deepcopy(cert);d['fractional_half_cover'][0]=[0,1,2]
    reject(lambda:check(data,d),"incorrect fractional covering configuration")
    reject(lambda:check(data+b'\nc mutated\n',cert),"changed CNF bytes")

    emit(control,control=True)
    data_c=(control/"source_atmost.cnf").read_bytes()
    cert_c=json.loads((control/"certificate.json").read_text())
    verdict=check(data_c,cert_c)
    assert verdict['status']=='INCONCLUSIVE'
    assert verdict['demand']==4 and verdict['parity_conditioned_capacity']==4
    # Independently exhibit and evaluate a model: machine 0 takes job 2,
    # machine 1 takes jobs 0 and 1.
    assignments=((2,),(0,1))
    true_vars=set()
    for j,taskset in enumerate(assignments):
        machine=cert_c['machines'][j]
        for i in taskset:true_vars.add(cert_c['selected_groups'][i][j])
        true_vars.add(machine['true_terminal'])
        rows={q:(x,l,h) for q,x,l,h in machine['transitions']}
        q=machine['root']
        while q in rows:
            true_vars.add(q)
            x,lo,hi=rows[q]
            q=hi if x in true_vars else lo
        assert q==machine['true_terminal']
    _,clauses,_=read_cnf(data_c)
    assert all(any((abs(l) in true_vars)==(l>0) for l in c) for c in clauses)
    print("SAT_CONTROL_MODEL_VERIFIED",len(clauses))
    print("ALL_TESTS_PASS")
