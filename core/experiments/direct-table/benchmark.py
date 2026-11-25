"""Paired replay of the 88 source-pinned CORE release inputs; no external solver."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import zipfile

CORE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE))
from run import run

MODES = ('default', 'table-fallback', 'table-first')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--repetitions', type=int, default=3)
    args = parser.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    args.output.mkdir(parents=True, exist_ok=False)
    corpus = CORE / 'validation/core-evidence-0.1.2.zip'
    truth = {}
    with zipfile.ZipFile(corpus) as archive, tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        manifest = json.loads(archive.read('manifest.json'))
        # Accepted historical answers serve only as post-solve checks.
        for row in csv.DictReader(archive.read('runs.csv').decode().splitlines()):
            if row['status'] in ('SAT', 'UNSAT'):
                assert truth.setdefault(row['id'], row['status']) == row['status']
        for item in manifest:
            raw = archive.read(item['path'])
            assert hashlib.sha256(raw).hexdigest() == item['sha256']
            (work / (item['id'] + '.cnf')).write_bytes(raw)
        with (args.output / 'runs.jsonl').open('x', buffering=1) as log:
            for rep in range(args.repetitions):
                cases = sorted(manifest, key=lambda x: x['id'])
                random.Random(41803 + rep).shuffle(cases)
                for idx, item in enumerate(cases):
                    ident = item['id']
                    source = work / (ident + '.cnf')
                    start = (idx + rep) % len(MODES)
                    for mode in MODES[start:] + MODES[:start]:
                        cert = work / 'candidate.cert'
                        cert.unlink(missing_ok=True)
                        ans = run(source, cert, 1.0, mode, 5)
                        ans.update(id=ident, cohort=item['cohort'], rep=rep+1)
                        log.write(json.dumps(ans, separators=(',', ':')) + '\n')
                        if ans['status'] not in ('SAT','UNSAT','TIMEOUT','UNKNOWN','AUDIT_LIMIT'):
                            raise ValueError(ans)
                        if ans['status'] in ('SAT','UNSAT'):
                            assert truth.setdefault(ident, ans['status']) == ans['status']
                        if ans.get('certificate','').startswith('TABLE+'):
                            path = args.output / f'{ident}-{mode}-{rep+1}.cert'
                            path.write_bytes(cert.read_bytes())
                print('Finished repetition', rep+1, flush=True)


if __name__ == '__main__':
    main()
