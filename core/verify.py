"""Independent acceptance gate. RUP+symbolic and capacity are labelled explicitly."""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'vendor/general/base'))
from symbolic_audit import verify_symbolic, AuditLimit


def parse_cnf(path):
    n = declared = None
    clauses, current = [], []
    for line in pathlib.Path(path).read_text().splitlines():
        tokens = line.split()
        if not tokens or tokens[0] == 'c':
            continue
        if tokens[0] == '%':
            break
        if tokens[0] == 'p':
            if n is not None or len(tokens) != 4 or tokens[1] != 'cnf':
                raise ValueError('DIMACS header')
            n, declared = map(int, tokens[2:])
            if n < 0 or declared < 0:
                raise ValueError('negative DIMACS size')
            continue
        if n is None:
            raise ValueError('missing header')
        for token in tokens:
            literal = int(token)
            if abs(literal) > n:
                raise ValueError('literal range')
            if literal:
                current.append(literal)
            else:
                clauses.append(tuple(current))
                current = []
    if n is None or current or len(clauses) != declared:
        raise ValueError('incomplete DIMACS')
    return n, clauses


def clause(line, n):
    xs = list(map(int, line.split()))
    if not xs or xs[-1] != 0 or any(not x or abs(x) > n for x in xs[:-1]):
        raise ValueError('malformed evidence clause')
    return tuple(xs[:-1])


def check_model(n, cs, text):
    tokens = text.split()
    if not tokens or tokens[0] != 'v':
        raise ValueError('model header')
    values = clause(' '.join(tokens[1:]), n)
    if len(values) != n or {abs(x) for x in values} != set(range(1, n + 1)):
        raise ValueError('incomplete or repeated model variable')
    selected = set(values)
    if not all(any(x in selected for x in c) for c in cs):
        raise ValueError('model does not satisfy original CNF')


def check_capacity(n, cs, lines):
    source = {frozenset(c) for c in cs}
    evidence = [frozenset(clause(line, n)) for line in lines]
    if not evidence or any(c not in source for c in evidence):
        raise ValueError('capacity source provenance')
    demands = [c for c in evidence if len(c) >= 3 and all(x > 0 for x in c)]
    used = set()
    for c in demands:
        if used.intersection(c):
            raise ValueError('overlapping capacity demands')
        used.update(c)
    if not used:
        raise ValueError('missing demands')
    adjacency = {v: set() for v in used}
    for c in evidence:
        if len(c) == 2 and all(x < 0 and -x in used for x in c):
            a, b = [-x for x in c]
            adjacency[a].add(b)
            adjacency[b].add(a)
    unseen, capacity = set(used), 0
    while unseen:
        first = unseen.pop()
        component, queue = {first}, [first]
        for v in queue:
            for w in adjacency[v]:
                if w not in component:
                    component.add(w)
                    unseen.discard(w)
                    queue.append(w)
        if any(adjacency[v] != component - {v} for v in component):
            raise ValueError('capacity component is not an at-most-one clique')
        capacity += 1
    if len(demands) <= capacity:
        raise ValueError('no capacity contradiction')


def verify(source, evidence, status, seconds=5):
    started = time.monotonic()
    n, cs = parse_cnf(source)
    path = pathlib.Path(evidence)
    text = path.read_text()
    if status == 10:
        check_model(n, cs, text)
        return 'SAT', 'MODEL'
    if status != 20:
        return 'UNKNOWN', 'NONE'
    lines = text.splitlines()
    if not lines:
        raise ValueError('empty evidence')
    if lines[0].startswith('{'):
        sys.path.insert(0, str(ROOT/'vendor/structural/research/pcmax_capacity'))
        sys.path.insert(0, str(ROOT/'vendor/structural/research/math4'))
        from check_clause_hall import check as check_hall
        from check_xor_units import verify as check_xor
        obj=json.loads(text)
        if obj.get('format')=='drnas-math4-xor-unit-v1':
            check_xor(pathlib.Path(source).read_bytes(),obj)
            return 'UNSAT','GF2'
        check_hall(pathlib.Path(source).read_bytes(),obj)
        return 'UNSAT','HALL'
    if lines[0] == 'drnas-capacity-v1':
        check_capacity(n, cs, lines[1:])
        return 'UNSAT', 'CAPACITY'
    if n > 10000:
        raise AuditLimit('RUP auditor variable limit')
    checked = subprocess.run([ROOT / 'bin/check-rup', source, evidence], capture_output=True,
                             text=True, timeout=seconds)
    if checked.returncode == 3:
        raise AuditLimit(checked.stderr)
    if checked.returncode:
        raise ValueError(checked.stderr.strip() or 'RUP checker rejected evidence')
    if lines[0] != 'g11-symbolic-v1':
        return 'UNSAT', 'DRUP'
    marker = lines.index('r')
    residual = [clause(line, n) for line in lines[marker + 1:-1]]
    with tempfile.TemporaryDirectory() as directory:
        order = pathlib.Path(directory) / 'order.cert'
        order.write_text('symbolic-elimination-v1\n' + lines[-1][2:] + '\n')
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise AuditLimit('audit deadline')
        if not verify_symbolic(n, residual, order, seconds=remaining, max_nodes=800000):
            raise ValueError('symbolic replay did not prove UNSAT')
    return 'UNSAT', 'RUP+SYMBOLIC'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('evidence')
    parser.add_argument('status', type=int, choices=[10, 20])
    parser.add_argument('--seconds', type=float, default=5)
    args = parser.parse_args()
    try:
        status, kind = verify(args.input, args.evidence, args.status, args.seconds)
        print(json.dumps(dict(status=status, certificate=kind)))
        return 0
    except (AuditLimit, subprocess.TimeoutExpired):
        print(json.dumps(dict(status='AUDIT_LIMIT')))
        return 3
    except Exception as error:
        print(json.dumps(dict(status='REJECTED', error=str(error))))
        return 1


if __name__ == '__main__':
    sys.exit(main())
