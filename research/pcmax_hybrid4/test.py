#!/usr/bin/env python3
"""Source-bound positive, SAT, RUP and malicious-certificate regression."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from emit import emit
from check import validate, check_rup, verify_sat_model

def reject(fn,label):
    try:fn()
    except (KeyError,TypeError,ValueError):
        print('TAMPER_REJECTED',label)
        return
    raise AssertionError('bad object was accepted: '+label)

with TemporaryDirectory() as tmp:
    root=Path(tmp)
    unsat=root/'unsat'; control=root/'sat'
    a=emit(unsat)
    b=emit(control,control=True)
    source=(unsat/'source.cnf').read_bytes()
    cert=json.loads((unsat/'certificate.json').read_text())
    result=validate(source,cert)
    assert result['status']=='UNSAT_STRUCTURAL_EXACT_COVER_CONFIRMED'
    assert result['exact_covers']==0
    assert result['vars']==74 and result['clauses']==134
    assert result['fractional_cover_checked'] and result['integer_lattice_witness_checked']
    assert result['scalar_subset_supports_checked']==63
    assert result['one_parity_projections_tested']==63
    assert result['two_parity_projection_pairs_tested']==1953
    assert result['three_parity_witness']==[4,11,33]
    proof=check_rup(source,(unsat/'proof.drup').read_bytes())
    assert proof['rup_steps']==31
    print('UNSAT_HOLE_SOURCE_AND_RUP_PASS',json.dumps(result,sort_keys=True))

    satdata=(control/'source.cnf').read_bytes()
    satcert=json.loads((control/'certificate.json').read_text())
    res=validate(satdata,satcert)
    assert res['status']=='SAT_CONTROL_HAS_EXACT_COVER'
    sat=verify_sat_model(satdata,satcert)
    assert sat['status']=='SAT_MODEL_VERIFIED'
    print('SAT_CONTROL_SOURCE_MODEL_PASS',json.dumps(sat,sort_keys=True))

    reject(lambda:validate(source+b'c changed\n',cert),'CNF SHA mismatch')
    x=deepcopy(cert);x['groups'][0][0]=x['groups'][1][0]
    reject(lambda:validate(source,x),'overlapping source group')
    x=deepcopy(cert);x['machines'][0]['transitions'][0][2]=x['machines'][0]['false_terminal']
    reject(lambda:validate(source,x),'altered BDD transition')
    x=deepcopy(cert);x['claimed_patterns']=[0]
    reject(lambda:validate(source,x),'falsified local language')
    x=deepcopy(cert);x['fractional_patterns'][0]=0
    reject(lambda:validate(source,x),'falsified fractional witness')
    x=deepcopy(cert);x['signed_coefficients'][1]=0
    reject(lambda:validate(source,x),'falsified lattice witness')
    text=(unsat/'proof.drup').read_text().splitlines()
    text[-1]='1 0'
    reject(lambda:check_rup(source,('\n'.join(text)+'\n').encode()),'invalid RUP conclusion')
    print('ALL_TESTS_PASS')
