"""Replay source-local entailments using full Boolean columns as Python integers."""
import hashlib
import pathlib
import time

from symbolic_audit import AuditLimit


def indices(line, marker, maximum, limit):
    tokens = line.split()
    if len(tokens) < 2 or len(tokens) > limit + 2 or tokens[0] != marker or tokens[-1] != '0':
        raise ValueError('malformed table record')
    values = tuple(map(int, tokens[1:-1]))
    if len(set(map(abs, values))) != len(values) or any(not 0 < abs(x) <= maximum for x in values):
        raise ValueError('invalid table index')
    return values


def columns_for(premises):
    scope = sorted({abs(lit) for premise in premises for lit in premise})
    if len(scope) > 16:
        raise ValueError('table scope exceeds 16 variables')
    rows = 1 << len(scope)
    full = (1 << rows) - 1
    columns = {}
    for idx, var in enumerate(scope):
        block = 1 << idx
        # Across rows numbered 0..2^width-1: block zeros, block ones.
        positive = (full // ((1 << block) + 1)) << block
        columns[var] = positive
        columns[-var] = full ^ positive
    return full, columns


def satisfying_column(clause, columns):
    result = 0
    for literal in clause:
        if literal not in columns:
            raise ValueError('claim outside premise scope')
        result |= columns[literal]
    return result


def verify_tables(source, clauses, n, lines, deadline):
    digest = hashlib.sha256(pathlib.Path(source).read_bytes()).hexdigest()
    if lines[0] != 'drnas-table-v1 ' + digest:
        raise ValueError('table source digest mismatch')
    # Match native DIMACS numbering: retain duplicate clauses, normalize repeated
    # literals within a clause and omit tautologies. Source order is significant.
    original = []
    for c in clauses:
        literals = frozenset(c)
        if not any(-lit in literals for lit in literals):
            original.append(literals)
    claims = []
    group_claims = None
    for pos, line in enumerate(lines[1:], 1):
        if time.monotonic() >= deadline:
            raise AuditLimit('table replay deadline')
        if line == 'suffix':
            if not group_claims or pos + 1 >= len(lines):
                raise ValueError('missing table claim or suffix')
            return claims, lines[pos + 1:]
        if line.startswith('i '):
            if group_claims == 0:
                raise ValueError('unused table premises')
            ids = indices(line, 'i', len(original), 700)
            if not ids or min(ids) < 1:
                raise ValueError('invalid table premise')
            premises = [original[i - 1] for i in ids]
            allowed, columns = columns_for(premises)
            for premise in premises:
                allowed &= satisfying_column(premise, columns)
            group_claims = 0
        elif line.startswith('t ') and group_claims is not None and len(claims) < 24:
            claim = indices(line, 't', n, 8)
            if allowed & ~satisfying_column(claim, columns):
                raise ValueError('source table admits a counterexample')
            claims.append(claim)
            group_claims += 1
        else:
            raise ValueError('unexpected table step')
    raise ValueError('missing clausal suffix')
