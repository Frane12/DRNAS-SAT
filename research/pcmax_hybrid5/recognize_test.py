#!/usr/bin/env python3
"""Cross-family test of generic three-machine source-CNF recognizer."""
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from recognize import recognize

ROOT=Path(__file__).resolve().parents[2]

def call(script,*args):
    subprocess.run([sys.executable,str(script),*map(str,args)],
                   check=True,stdout=subprocess.DEVNULL)

def reject(fn):
    try: fn()
    except (KeyError,ValueError,TypeError):
        return
    raise AssertionError('invalid source/certificate was accepted')

with TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    emitter=ROOT/'research'/'pcmax_hybrid5'/'emit.py'
    for name,extra,expected in (
        ('hybrid5_unsat',(), 'UNSAT_SOURCE_CONFIGURATION_OBSTRUCTION'),
        ('hybrid5_sat',('--control',),'SAT_SOURCE_MODEL_VERIFIED'),
    ):
        dest=tmp/name
        call(emitter,'--out',dest,*extra)
        data=(dest/'source.cnf').read_bytes()
        cert=json.loads((dest/'certificate.json').read_text())
        answer=recognize(data,cert)
        assert answer['status']==expected,(name,answer)
        print('GENERIC_RECOGNIZER_PASS',name,answer['status'],
              answer['accepted_local_counts'],answer['compatible_pattern_triples'])
        if name=='hybrid5_sat':
            # A full-source empty clause invalidates any SAT model while
            # leaving every checked BDD/group implication unchanged.
            # Correct answer must be UNKNOWN, not a made-up SAT model.
            text=data.decode('ascii')
            header=[l for l in text.splitlines() if l.startswith('p cnf ')]
            assert len(header)==1
            head=header[0].split()
            updated=' '.join(head[:3]+[str(int(head[3])+1)])
            contaminated=text.replace(header[0],updated,1)+'0\n'
            extra_data=contaminated.encode('ascii')
            altered=deepcopy(cert)
            altered['source_sha256']=hashlib.sha256(extra_data).hexdigest()
            cautious=recognize(extra_data,altered)
            assert cautious['status']=='UNKNOWN_EXTRA_SOURCE_CONSTRAINTS',cautious
            print('EXTRA_SOURCE_CLAUSE_CONTROL_PASS',cautious['status'])
            reject(lambda:recognize(data,altered))

    # DIFFERENT STRUCTURAL FAMILY: 7-job Fano MOD-3 and its 6-job
    # SAT control; no hardcoded Fano or HYBRID5 patterns in recognize.py.
    h3=ROOT/'research'/'pcmax_hybrid3'/'emit.py'
    for family,expected in (
        ('fano','UNSAT_SOURCE_CONFIGURATION_OBSTRUCTION'),
        ('sat-control','SAT_SOURCE_MODEL_VERIFIED'),
    ):
        dest=tmp/family
        call(h3,'--kind',family,'--out',dest)
        answer=recognize((dest/'source.cnf').read_bytes(),
                         json.loads((dest/'certificate.json').read_text()))
        assert answer['status']==expected,(family,answer)
        print('CROSS_FAMILY_PASS',family,answer['status'],
              answer['accepted_local_counts'])

    print('ALL_RECOGNIZER_TESTS_PASS')
