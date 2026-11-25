"""Public command: bounded native solve followed by independent evidence checking."""
import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent


def run(source, evidence, seconds=5, mode='default', audit_seconds=5):
    started = time.monotonic()
    result = dict(status='UNKNOWN', mode=mode, budget_s=seconds)
    try:
        proc = subprocess.run([ROOT / 'bin/drnas-core', source, evidence, str(seconds), mode],
                              capture_output=True, text=True, timeout=seconds + .1)
    except subprocess.TimeoutExpired:
        result.update(status='TIMEOUT', solve_s=time.monotonic()-started)
        return result
    result['solve_s'] = time.monotonic() - started
    result['returncode'] = proc.returncode
    for line in proc.stdout.splitlines():
        if line.startswith('c {'):
            result['telemetry'] = json.loads(line[2:])
    if result['solve_s'] > seconds + .05:
        result['status'] = 'TIMEOUT'
        return result
    if proc.returncode not in (0, 10, 20):
        result.update(status='ERROR', error=proc.stderr.strip())
        return result
    if not proc.returncode:
        return result
    started = time.monotonic()
    try:
        audit = subprocess.run([sys.executable, ROOT / 'verify.py', source, evidence,
                                str(proc.returncode), '--seconds', str(audit_seconds)],
                               capture_output=True, text=True, timeout=audit_seconds + .1)
        result.update(json.loads(audit.stdout))
    except subprocess.TimeoutExpired:
        result['status'] = 'AUDIT_LIMIT'
    except Exception as error:
        result.update(status='REJECTED', error=str(error))
    result['audit_s'] = time.monotonic() - started
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('evidence', help='new evidence path; existing files are protected')
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--mode', choices=['default', 'memory', 'no-share', 'table-first', 'table-fallback', 'table-rank', 'table-pick-first'], default='default')
    parser.add_argument('--audit-seconds', type=float, default=5)
    args = parser.parse_args()
    answer = run(args.input, args.evidence, args.seconds, args.mode, args.audit_seconds)
    print(json.dumps(answer, ensure_ascii=False))
    sys.exit(0 if answer['status'] in ('SAT', 'UNSAT', 'UNKNOWN', 'TIMEOUT', 'AUDIT_LIMIT') else 1)
