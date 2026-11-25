"""Paired CORE boundary experiment. Use a new output directory for every run."""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import platform
import random
import secrets
import subprocess
import sys
import time

P = pathlib.Path
HERE = P(__file__).resolve().parent
ARMS = ('boundary', 'boundary-repair', 'adaptive-repair')
SOLVED = {'SAT', 'UNSAT'}
CAP = 5.0


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def trial(core, source, out, case, arm, rep):
    cert = out / 'evidence' / f'{case["id"]}.{arm}.{rep}.cert'
    env = dict(os.environ, DRNAS_PROFILE='1', DRNAS_SCHEDULE=arm,
               DRNAS_BOUNDARY_EVIDENCE=str(cert))
    row = dict(id=case['id'], family=case['family'], cohort=case['cohort'],
               rep=rep, arm=arm, status='UNKNOWN', certificate=None)
    started = time.monotonic()
    try:
        native = subprocess.run([core/'bin/drnas-core', source, cert, '5', 'default'],
                                capture_output=True, timeout=5.1, env=env)
        rc, stdout, stderr = native.returncode, native.stdout, native.stderr
    except subprocess.TimeoutExpired as exc:
        rc, stdout, stderr = None, exc.stdout or b'', exc.stderr or b''
    row['solve_s'] = time.monotonic() - started
    logs = stdout + b'\n' + stderr
    (out/'logs'/cert.stem).write_bytes(logs)
    lines = logs.decode(errors='replace').splitlines()
    row['immediate'] = [line for line in lines if line.startswith('IMMEDIATE ')]
    row['adaptive'] = [line for line in lines if line.startswith('ADAPTIVE ')]
    row['method'] = next((json.loads(line[2:]).get('method') for line in lines if line.startswith('c {')), None)
    proof, messages = (P(str(cert) + suffix) for suffix in ('.boundary.rup', '.boundary.messages'))
    if proof.exists() or messages.exists():
        try:
            check = subprocess.run([core/'bin/check-rup', source, proof, '--prefix', messages],
                                   capture_output=True, timeout=5.1)
            row['prefix'] = {0:'VERIFIED', 3:'AUDIT_LIMIT'}.get(check.returncode, 'REJECTED')
        except subprocess.TimeoutExpired:
            row['prefix'] = 'AUDIT_LIMIT'
    if (any('attempt=1' in line for line in row['immediate']) or row['adaptive']) and 'prefix' not in row:
        raise RuntimeError('Immediate repair missing boundary proof prefix')
    if rc is None or row['solve_s'] > CAP + .05:
        row['status'] = 'TIMEOUT'
    elif rc in (10, 20):
        try:
            audit = subprocess.run([sys.executable, core/'verify.py', source, cert, str(rc), '--seconds', '5'],
                                   capture_output=True, timeout=5.1)
            verdict = json.loads(audit.stdout)
            row['status'], row['certificate'] = verdict['status'], verdict.get('certificate')
            if row['status'] in SOLVED and row['status'] != {10:'SAT',20:'UNSAT'}[rc]:
                row['status'] = 'REJECTED'
        except subprocess.TimeoutExpired:
            row['status'] = 'AUDIT_LIMIT'
    elif rc != 0:
        row['status'] = 'ERROR'
    if row.get('prefix') in ('AUDIT_LIMIT', 'REJECTED'):
        row['status'] = row['prefix']
    row['e2e_s'] = time.monotonic() - started
    return row


def summarize(rows):
    summary = {}
    for cohort in ('diagnostic','fresh','transfer'):
        rr = [r for r in rows if r['cohort']==cohort]
        arms = {}
        for arm in ARMS:
            aa = [r for r in rr if r['arm']==arm]
            groups = collections.defaultdict(list)
            for r in aa:
                groups[r['id']].append(r)
            good = [r for r in aa if r['status'] in SOLVED]
            arms[arm] = dict(statuses=dict(collections.Counter(r['status'] for r in aa)),
                             solved_all_three=sorted(k for k,v in groups.items() if len(v)==3 and all(r['status'] in SOLVED for r in v)),
                             par2_s=sum(r['solve_s'] if r['status'] in SOLVED else 2*CAP for r in aa)/len(aa),
                             mean_e2e_accepted_s=sum(r['e2e_s'] for r in good)/len(good) if good else None,
                             total_e2e_s=sum(r['e2e_s'] for r in aa),
                             adaptive_events=sum(len(r['adaptive']) for r in aa),
                             adaptive_direct_models=sum(any('model=1' in l for l in r['adaptive']) and r['status']=='SAT' for r in aa))
        sets = {arm:{(r['id'],r['rep']) for r in rr if r['arm']==arm and r['status'] in SOLVED} for arm in ARMS}
        pairs = {}
        for control in ARMS[:2]:
            pairs[control] = dict(candidate_only=sorted(sets[ARMS[2]]-sets[control]),
                                  control_only=sorted(sets[control]-sets[ARMS[2]]))
        summary[cohort] = dict(arms=arms, paired=pairs)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('core','previous','output'):
        parser.add_argument('--'+arg,type=P,required=True)
    args=parser.parse_args()
    core, previous, out = (p.resolve() for p in (args.core,args.previous,args.output))
    out.mkdir(parents=True, exist_ok=False)
    for folder in ('cnf','evidence','logs'):
        (out/folder).mkdir()
    sys.path.insert(0,str(core))
    import benchmark as b
    from families import generate, FAMILIES, TRANSFER
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0,{cpu})
    inputs = [core/'bin/drnas-core',core/'bin/check-rup',core/'verify.py',core/'core.cpp',
              HERE/'adapt.py', HERE.parent/'boundary-repair'/'repair.patch', HERE/'families.py', P(__file__).resolve(), core/'benchmark.py',core/'tests.py']
    hashes = {str(p.relative_to(core)) if p.is_relative_to(core) else 'experiment/'+p.name:digest(p) for p in inputs}
    seed = secrets.randbits(128)
    dump(out/'freeze.json',dict(seed=str(seed),hashes=hashes,cpu=cpu,platform=platform.platform(),
         source='012315d0a62443667aad69fe0dd42c72dd375630', boundary_artifact=15021063034,
         boundary_patch_sha256='c5eecedb8e2f799ca8d8f296f9ea7dfa398519fd49dddcd055078e1e2256b8c9',
         version='0.1.2-adaptive-repair.1',arms=ARMS,cap_s=CAP,audit_s=5,repetitions=3))
    rng=random.Random(seed)
    cases=[]
    old=json.loads((previous/'boundary100/manifest.json').read_text())
    for c in old:
        if c['id'] in ('Q091','Q097'):
            path=out/'cnf'/(c['id']+'.cnf')
            path.write_bytes((previous/'boundary100'/c['path']).read_bytes())
            assert digest(path)==c['sha256']
            cases.append(dict(id=c['id'],family=c['family'],cohort='diagnostic',sha256=c['sha256']))
    assert len(cases)==2
    specs=[(f,i) for f in FAMILIES+TRANSFER for i in range(10)]
    rng.shuffle(specs)
    seen={c['normalized_sha256'] for c in old}
    for index,(family,size) in enumerate(specs):
        n,cs=b.hide(rng,*generate(rng,family,size))
        key=b.norm_digest(n,cs)
        if key in seen:
            raise ValueError('repeated formula')
        seen.add(key)
        cid=f'R{index:03}';path=out/'cnf'/(cid+'.cnf');b.write(path,n,cs)
        cases.append(dict(id=cid,family=family,cohort='transfer' if family in TRANSFER else 'fresh',sha256=digest(path),normalized_sha256=key))
    dump(out/'manifest.json',cases)
    rows=[]
    truth={}
    with (out/'runs.jsonl').open('w',buffering=1) as stream:
        for rep in range(3):
            order=list(enumerate(cases))
            rng.shuffle(order)
            for index,case in order:
                start=(index+rep)%len(ARMS)
                source=out/'cnf'/(case['id']+'.cnf')
                assert digest(source)==case['sha256']
                for arm in ARMS[start:]+ARMS[:start]:
                    row=trial(core,source,out,case,arm,rep+1)
                    rows.append(row);stream.write(json.dumps(row)+'\n')
                    if row['status'] in SOLVED:
                        assert truth.setdefault(case['id'],row['status'])==row['status'],row
                    if row['status'] in ('ERROR','REJECTED'):
                        raise RuntimeError(row)
            print('Completed repetition',rep+1,flush=True)
    assert len(rows)==1188
    summary=summarize(rows)
    dump(out/'summary.json',summary)
    print('CORE_ADAPTIVE_SUMMARY '+json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
