"""Fixed protocol for a one-time handover after the common two-lane probe."""
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[1]
sys.path.insert(0, str(CORE))
from verify import parse_cnf, verify
from table_verify import verify_tables

POLICIES = ('mean', 'clock', 'patience')
SEED = 69835217


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(src, state, dest, repetitions, log, policies=POLICIES):
    n, clauses = parse_cnf(src)
    messages = state / 'messages.txt'
    lines = messages.read_text().splitlines()
    claims, _ = verify_tables(src, clauses, n, lines + ['suffix', '0'], time.monotonic() + 5)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        orders = [tmp / 'table-first', tmp / 'table-rank']
        for order in orders:
            subprocess.run([CORE/'bin/priority-order', src, state/'active.rows', messages,
                            order.name, order], check=True, stdout=subprocess.DEVNULL)
        for rep in range(repetitions):
            for policy in policies[rep % len(policies):] + policies[:rep % len(policies)]:
                model = dest / f'{src.stem}-{rep + 1}-{policy}.model'
                trial = subprocess.run([CORE/'bin/divergence-trial', str(n), *orders, tmp/'trace',
                                        policy, model], check=True, capture_output=True, text=True, timeout=20)
                row = json.loads(trial.stdout)
                assert row['charged'] == sum(row['lane_flips']) <= 2160000
                if row['status'] == 'SAT':
                    assert verify(src, model, 10) == ('SAT', 'MODEL')
                    row['model_sha256'] = digest(model)
                else:
                    assert row['status'] == 'UNKNOWN' and not model.exists()
                print(json.dumps(dict(id=src.stem, rep=rep + 1, policy=policy, claims=len(claims),
                                      cnf_sha256=digest(src), active_sha256=digest(state/'active.rows'),
                                      **row)), file=log, flush=True)


def generate(path, family, rng):
    hidden = [rng.randrange(2) for _ in range(501)]
    with path.open('x') as out:
        print('p cnf 500 2130', file=out)
        for _ in range(2130):
            variables = rng.sample(range(1, 501), 3)
            if family == 'uniform':
                clause = [v * rng.choice((-1, 1)) for v in variables]
            else:
                if family == 'planted':
                    mask = rng.randrange(1, 8)
                else:
                    hits = rng.choices([1, 2, 3], weights=[6, 3, 1])[0]
                    mask = sum(1 << j for j in rng.sample(range(3), hits))
                clause = [v if hidden[v] == ((mask >> j) & 1) else -v for j, v in enumerate(variables)]
                assert any((lit > 0) == hidden[abs(lit)] for lit in clause)
            print(*clause, 0, file=out)


def main(previous, dest):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    dest.mkdir(parents=True, exist_ok=False)
    files = [HERE/'stagnation.py', HERE/'trial.cpp', HERE/'build.py',
             *(CORE/'bin'/name for name in ('divergence-trial', 'priority-order', 'f26-replay'))]
    (dest/'freeze.json').write_text(json.dumps(dict(seed=SEED, patience=10000, fresh=12,
        files={str(p.relative_to(CORE)): digest(p) for p in files}), indent=2))
    manifest = json.loads((previous/'priority-fresh/manifest.json').read_text())
    with (dest/'diagnostic.jsonl').open('x') as log:
        for src in (CORE/'regression/F26.cnf', previous/'priority-fresh/H09.cnf'):
            assert digest(src) == manifest[src.stem]['sha256']
            replay(src, previous/'priority-fixed'/src.stem, dest, 3, log)
    gate = [json.loads(s) for s in (dest/'diagnostic.jsonl').read_text().splitlines()]
    gate = [r for r in gate if r['policy'] == 'patience']
    if len(gate) != 6 or any(r['status'] != 'SAT' for r in gate):
        return
    rng = random.Random(SEED)
    families = ('uniform', 'planted', 'balanced-planted')
    with (dest/'panel.jsonl').open('x') as log, (dest/'fresh.jsonl').open('x') as runs:
        for i in range(12):
            state = dest / f'N{i:02}'
            state.mkdir()
            src = state / (state.name + '.cnf')
            family = families[i % len(families)]
            generate(src, family, rng)
            cert = state/'native.cert'
            capture = subprocess.run([CORE/'bin/f26-replay', src, cert, '5', 'table-first'],
                env={**os.environ, 'DRNAS_CAPTURE_STATE': str(state)}, capture_output=True, text=True, timeout=10)
            assert capture.returncode in (0, 10, 20), capture.stderr
            native = verify(src, cert, capture.returncode)[0] if capture.returncode else 'UNKNOWN'
            (state/'native.log').write_text(capture.stdout)
            witness = state/'messages.txt'
            eligible = witness.exists() and any(s.startswith('t ') for s in witness.read_text().splitlines())
            print(json.dumps(dict(id=state.name, family=family, sha256=digest(src), native=native,
                                  reached_repair=(state/'active.rows').exists(), eligible=eligible)), file=log, flush=True)
            if eligible:
                replay(src, state, dest, 1, runs)


if __name__ == '__main__':
    main(*(Path(a).resolve() for a in sys.argv[1:]))
