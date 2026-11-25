"""Summarize paired runs and ablate source-table premises from recorded refutations."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from benchmark import CORE, MODES
from verify import verify


def summarize(out):
    rows = [json.loads(s) for s in (out/'runs.jsonl').read_text().splitlines()]
    reps = sorted({r['rep'] for r in rows})
    ids = {r['id'] for r in rows}
    keyed = {(r['mode'], r['rep'], r['id']): r for r in rows}
    if len(rows) != len(keyed) or len(rows) != len(MODES)*len(reps)*88 or len(ids) != 88:
        raise ValueError('incomplete paired panel')
    result = {}
    robust = {}
    for mode in MODES:
        arm = [r for r in rows if r['mode']==mode]
        accepted = lambda r:r['status'] in ('SAT', 'UNSAT')
        stable = {i for i in ids if all(accepted(keyed[mode,rep,i]) for rep in reps)}
        robust[mode] = stable
        by_rep = [sum(accepted(r) for r in arm if r['rep']==rep) for rep in reps]
        def total(field):
            return sum(r.get('telemetry',{}).get(field,0) for r in arm)
        result[mode] = dict(solved_per_rep=by_rep, solved_every_rep=len(stable),
            statuses=dict(Counter(r['status'] for r in arm)),
            missing_telemetry=sum('telemetry' not in r for r in arm),
            trace_attempts=total('factor_trace_attempts'),trace_failures=total('factor_trace_failures'),
            trace_deadlines=total('factor_trace_deadlines'),table_messages=total('table_messages'),
            inputs_with_table=sorted({r['id'] for r in arm if r.get('telemetry',{}).get('table_messages',0)}),
            final_certificates=dict(Counter(r['certificate'] for r in arm if accepted(r))),
            only_vs_default=sorted(stable-robust['default']),lost_vs_default=sorted(robust['default']-stable))
    expected = {f"{r['id']}-{r['mode']}-{r['rep']}.cert" for r in rows if r.get('certificate','').startswith('TABLE+')}
    proofs = sorted(out.glob('*.cert'))
    assert {p.name for p in proofs} == expected
    without = {}
    with zipfile.ZipFile(CORE/'validation/core-evidence-0.1.2.zip') as archive, tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        manifest = {x['id']: x for x in json.loads(archive.read('manifest.json'))}
        for cert in proofs:
            ident = cert.name.split('-')[0]
            source = work/(ident+'.cnf')
            source.write_bytes(archive.read(manifest[ident]['path']))
            assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest[ident]['sha256']
            assert verify(source, cert, 20)[0]=='UNSAT'
            suffix = work/'bare.cert'
            suffix.write_text(cert.read_text().split('\nsuffix\n',1)[1])
            try:
                verify(source,suffix,20)
                outcome = 'accepted_without_table'
            except ValueError:
                outcome = 'rejected_without_table'
            except (TimeoutError, subprocess.TimeoutExpired):
                outcome = 'audit_timeout'
            without[cert.name] = outcome
    return dict(inputs=len(ids),repetitions=len(reps),runs=len(rows),cap_s=1,audit_cap_s=5,
                arms=result,table_suffix_ablation=without)


if __name__ == '__main__':
    print(json.dumps(summarize(Path(sys.argv[1])),indent=2,sort_keys=True))
