"""Paired replay of two bounded visits, with stay and permanent-switch controls."""
import json
import os
from pathlib import Path
import sys

from stagnation import CORE, HERE, digest, replay

POLICIES = ('mean', 'patience', 'visit-cycle', 'visit-third')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main(previous, stagnation, out):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    out.mkdir(parents=True, exist_ok=False)
    files = [HERE/name for name in ('temporary.py', 'stagnation.py', 'trial.cpp', 'build.py')]
    files.extend(CORE/'bin'/name for name in ('priority-order', 'divergence-trial'))
    (out/'freeze.json').write_text(json.dumps(dict(budget=2160000, patience=10000,
        quotas=[60000, 720000], repetitions=3, policies=POLICIES,
        files={str(p.relative_to(CORE)):digest(p) for p in files}), indent=2))
    historic = rows(stagnation/'diagnostic.jsonl') + rows(stagnation/'fresh.jsonl')
    reference = {(r['id'], r['policy']):r for r in historic if r['rep']==1}
    inputs = [(CORE/'regression/F26.cnf', previous/'priority-fixed/F26'),
              (previous/'priority-fresh/H09.cnf', previous/'priority-fixed/H09'),
              (stagnation/'N00/N00.cnf', stagnation/'N00')]
    with (out/'runs.jsonl').open('x') as log:
        for src, state in inputs:
            ref = reference[(src.stem, 'mean')]
            assert digest(src)==ref['cnf_sha256'] and digest(state/'active.rows')==ref['active_sha256']
            replay(src, state, out, 3, log, POLICIES)
    runs = rows(out/'runs.jsonl')
    assert len(runs)==len({(r['id'],r['policy'],r['rep']) for r in runs})==36
    for row in runs:
        control = row['policy'] in ('mean', 'patience')
        ref = reference[(row['id'], row['policy'] if control else 'patience')]
        common = ('split', 'samples', 'sums', 'selected', 'switch_at', 'switch_after')
        assert all(row[k]==ref[k] for k in common)
        if control:
            assert all(row.get(k)==ref.get(k) for k in ('status','charged','lane_flips','model_sha256'))
        else:
            switch, quota = row['switch_at'], row['visit_limit']
            assert switch and quota in (60000,720000)
            if row['charged'] > switch + quota:
                assert row['return_at']==switch + quota
                alternate = 1 - row['selected']
                assert row['lane_flips'][alternate]==row['split'] + row['samples'] - 1 + quota
            else:
                assert row['return_at']==0
            if row['status']=='SAT':
                lane_control = 'mean' if row['winner']==row['selected'] else 'patience'
                assert row['model_sha256']==reference[(row['id'],lane_control)]['model_sha256']


if __name__ == '__main__':
    main(*(Path(p).resolve() for p in sys.argv[1:]))
