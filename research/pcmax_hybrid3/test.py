#!/usr/bin/env python3
"""Positive Fano, SAT control, tampering, and arithmetic regressions."""
from pathlib import Path
from copy import deepcopy
import json, tempfile
from emit import generate
from check import check, verify_explicit_model, InvalidCertificate

def reject(fn,name):
    try:fn()
    except (InvalidCertificate,ValueError,KeyError,TypeError,AssertionError):
        print("TAMPER_REJECTED",name)
        return
    raise AssertionError("checker accepted malicious change: "+name)

with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp)
    fano=temp/"fano"
    control=temp/"control"
    generate(fano,"fano")
    data=(fano/"source.cnf").read_bytes()
    cert=json.loads((fano/"certificate.json").read_text())
    result=check(data,cert)
    assert result["status"]=="UNSAT_MODULAR_STRUCTURAL_CERTIFICATE_VERIFIED",result
    assert result["jobs"]==7 and result["machines"]==3
    assert result["required_residue"]==1 and result["global_residues"]==[0]
    assert result["accepted_local_configs"]==8
    assert all(x==[0,1] for x in result["per_machine_mod2"])
    assert all(x==[0] for x in result["per_machine_mod3"])
    assert result["all_positive_weight_GF2_obstruction"].startswith("VERIFIED_")
    assert cert['rup_steps']==sum(3**i for i in range(8))
    print("FANO_MOD3_STRUCTURAL_PASS",json.dumps({
        'vars':result['source_vars'],'clauses':result['source_clauses'],
        'rup_steps':cert['rup_steps'],'mod3_global':result['global_residues'],
        'gf2_witnesses':len(result['three_line_witnesses'])},sort_keys=True))

    generate(control,"sat-control")
    ctrl_data=(control/"source.cnf").read_bytes()
    ctrl_cert=json.loads((control/"certificate.json").read_text())
    answer=check(ctrl_data,ctrl_cert)
    assert answer["status"]=="INCONCLUSIVE",answer
    sat=verify_explicit_model(ctrl_data,ctrl_cert,[0,0,1,1,2,2])
    assert sat["status"]=="SAT_SOURCE_MODEL_VERIFIED"
    print("SAT_CONTROL_PASS",json.dumps(sat,sort_keys=True))

    def tampered(mod):
        copy=deepcopy(cert)
        mod(copy)
        return check(data,copy)
    reject(lambda:check(data+b'c hash changed\n',cert),"CNF byte hash")
    reject(lambda:tampered(lambda x:x["groups"][0].append(x["groups"][1][0])),
           "overlapping job groups")
    reject(lambda:tampered(lambda x:x["machines"][0]["transitions"][0].__setitem__(2,x["machines"][0]["false_terminal"])),
           "BDD source edge alteration")
    reject(lambda:tampered(lambda x:x["machines"][0].__setitem__("root",x["machines"][0]["true_terminal"])),
           "BDD invalid root")
    reject(lambda:tampered(lambda x:x.__setitem__("claimed_local_patterns",[0])),
           "fabricated local language")
    reject(lambda:tampered(lambda x:x.__setitem__("modulus",1)),
           "invalid modular arithmetic")

    print("ALL_TESTS_PASS")
