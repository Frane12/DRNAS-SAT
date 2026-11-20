#!/usr/bin/env python3
"""Independent RUP audit of reachability-state proof compilation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys
from proof import generate
from symbolic import symbolic_product

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research'/'pcmax_hybrid5'))
from check import check_rup

def emit_script(script,*args):
    subprocess.run([sys.executable,str(script),*map(str,args)],
                   check=True,stdout=subprocess.DEVNULL)

with TemporaryDirectory() as temp:
    temp=Path(temp)
    for name,script,args in (
        ('hybrid5',ROOT/'research/pcmax_hybrid5/emit.py',()),
        ('fano',ROOT/'research/pcmax_hybrid3/emit.py',('--kind','fano')),
    ):
        src=temp/name
        emit_script(script,'--out',src,*args)
        cnf=(src/'source.cnf').read_bytes()
        cert=json.loads((src/'certificate.json').read_text())
        result=symbolic_product(cnf,cert)
        assert result['status']=='UNSAT_SOURCE_SYMBOLIC_PRODUCT',result
        out=temp/(name+'_proof')
        manifest=generate(cnf,cert,out)
        audited=check_rup(cnf,(out/'proof.drup').read_bytes())
        assert audited['status']=='ALL_RUP_STEPS_CHECKED',audited
        assert audited['rup_steps']==manifest['rup_steps']
        assert manifest['rup_steps']<=4*result['product_states_reached']+1
        assert manifest['status']=='EMITTED_UNCHECKED'
        print('PRODUCT_RUP_INDEPENDENT_AUDIT_PASS',name,
              'product_states',result['product_states_reached'],
              'proof_steps',manifest['rup_steps'],
              'baseline_steps',cert['rup_steps'])

    source=temp/'sat_control'
    emit_script(ROOT/'research/pcmax_hybrid5/emit.py','--out',source,'--control')
    cnf=(source/'source.cnf').read_bytes()
    cert=json.loads((source/'certificate.json').read_text())
    try:
        generate(cnf,cert,temp/'unsafe_proof')
    except ValueError as e:
        assert 'NO_UNSAT_PROOF' in str(e)
        print('PRODUCT_RUP_SAT_REFUSAL_PASS')
    else:
        raise AssertionError('generator attempted to refute satisfiable source')

    print('ALL_PRODUCT_RUP_TESTS_PASS')
