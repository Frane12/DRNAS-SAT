#!/usr/bin/env python3
"""DRNAS HYBRID5 independent positive, negative, SAT and proof regression."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from emit import emit
from check import validate, check_rup, verify_sat_model

def reject(fn,label):
    try:
        fn()
    except (KeyError,TypeError,ValueError):
        print('TAMPER_REJECTED',label)
        return
    raise AssertionError('Corrupt artifact accepted: '+label)

with TemporaryDirectory() as tmp:
    root=Path(tmp)
    unsat=root/'global3_unsat'
    control=root/'sat'
    generated=emit(unsat)
    emit(control,control=True)
    original=(unsat/'source.cnf').read_bytes()
    cert=json.loads((unsat/'certificate.json').read_text())
    result=validate(original,cert)
    assert result['status']=='UNSAT_GLOBAL3_COMPATIBILITY_CONFIRMED'
    assert result['jobs']==9 and result['machines']==3
    assert result['disjoint_pairs']==16
    assert result['disjoint_triples']==0
    assert result['fractional_cover_checked'] and result['integer_lattice_witness_checked']
    assert result['one_dimensional_gf2_tested']==511
    assert result['two_dimensional_gf2_tested']==130305
    assert result['rup_steps_claimed']==301
    trace=check_rup(original,(unsat/'proof.drup').read_bytes())
    assert trace['status']=='ALL_RUP_STEPS_CHECKED'
    assert trace['rup_steps']==301
    print('UNSAT_SOURCE_AND_RUP_PASS',json.dumps(result,sort_keys=True))

    satcnf=(control/'source.cnf').read_bytes()
    satcert=json.loads((control/'certificate.json').read_text())
    sat_result=validate(satcnf,satcert)
    assert sat_result['status']=='SAT_CONTROL_HAS_EXACT_COVER'
    assert sat_result['disjoint_triples']>0
    sat_model=verify_sat_model(satcnf,satcert)
    assert sat_model['status']=='SAT_MODEL_VERIFIED'
    print('SAT_CONTROL_SOURCE_MODEL_PASS',json.dumps(sat_model,sort_keys=True))

    reject(lambda:validate(original+b'c changed\n',cert),'source SHA mismatch')
    c=deepcopy(cert);c['groups'][0][0]=c['groups'][1][0]
    reject(lambda:validate(original,c),'overlapping group selectors')
    c=deepcopy(cert);c['machines'][0]['transitions'][0][2]=c['machines'][0]['false_terminal']
    reject(lambda:validate(original,c),'wrong BDD edge')
    c=deepcopy(cert);c['claimed_patterns']=[0]
    reject(lambda:validate(original,c),'fabricated local language')
    c=deepcopy(cert);c['fractional_patterns'][0]=0
    reject(lambda:validate(original,c),'invalid fractional witness')
    c=deepcopy(cert);c['signed_coefficients'][9]=0
    reject(lambda:validate(original,c),'invalid signed lattice witness')
    c=deepcopy(cert);c['pairwise_disjoint_witnesses']=[]
    reject(lambda:validate(original,c),'incomplete pair witness')
    bad=(unsat/'proof.drup').read_text().splitlines()
    bad[-1]='1 0'
    reject(lambda:check_rup(original,('\n'.join(bad)+'\n').encode()),
           'missing RUP empty conclusion')
    print('ALL_TESTS_PASS')
