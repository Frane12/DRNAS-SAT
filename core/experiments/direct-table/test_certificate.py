"""Check the source entailment rule, projection over hidden bits, and its handoff."""
import hashlib
import itertools
from pathlib import Path
import random
import subprocess
import sys
import tempfile

CORE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CORE))
from run import run
from verify import verify
from table_verify import columns_for, satisfying_column


def truth_table_tests():
    rng = random.Random(41803)
    for n in range(1, 9):
        for _ in range(40):
            premises = [[rng.choice((-1, 1)) * v for v in rng.sample(range(1, n+1), rng.randint(1, n))]
                        for _ in range(1+rng.randrange(6))]
            full, cols = columns_for(premises)
            allowed = full
            for item in premises:
                allowed &= satisfying_column(item, cols)
            vs = sorted(v for v in cols if v > 0)
            claim = [rng.choice((-v, v)) for v in rng.sample(vs, rng.randrange(len(vs)+1))]
            actual = not (allowed & ~satisfying_column(claim, cols))
            def sat(c, true):
                return any((abs(lit) in true) == (lit > 0) for lit in c)
            expected = all(any(not sat(c, set(bits)) for c in premises) or sat(claim, set(bits))
                           for k in range(len(vs)+1) for bits in itertools.combinations(vs, k))
            assert actual == expected


def integration(tmp):
    source = tmp / 'example.cnf'
    cert = tmp / 'proof'
    # Tautologies disappear before indexing; a repeated literal must normalize.
    source.write_text('p cnf 3 6\n1 -1 0\n1 1 2 3 0\n1 2 -3 0\n1 -2 3 0\n1 -2 -3 0\n-1 0\n')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    prefix = f'drnas-table-v1 {digest}\ni 1 2 3 4 0\nt 1 0\nsuffix\n'
    cert.write_text(prefix + '0\n')
    assert verify(source, cert, 20) == ('UNSAT', 'TABLE+DRUP')
    assert subprocess.run([CORE/'bin/check-rup', source, cert], capture_output=True).returncode != 0
    cert.write_text(prefix + 'g11-symbolic-v1\nr\n1 0\n-1 0\no 1 2 3 0\n')
    assert verify(source, cert, 20) == ('UNSAT', 'TABLE+RUP+SYMBOLIC')
    original = prefix + '0\n'
    for bad in [original.replace('t 1 0','t -1 0'), original.replace('t 1 0','t 0'),
                original.replace(digest, '0'*64), original.replace('1 2 3 4 0','1 2 3 0'),
                original.replace('i 1','i 6'), original.replace('i 1','i -1'),
                original.replace('i 1','i 1 1'), original.replace('t 1 0','t 4 0'),
                prefix, '0\n']:
        cert.write_text(bad)
        try:
            verify(source, cert, 20)
        except ValueError:
            continue
        raise AssertionError('invalid certificate accepted')
    # A correct lemma without a contradiction cannot refute a SAT formula.
    source.write_text(source.read_text().replace('3 6','3 5').removesuffix('-1 0\n'))
    cert.write_text(original.replace(digest, hashlib.sha256(source.read_bytes()).hexdigest()))
    try:
        verify(source, cert, 20)
    except ValueError:
        return
    raise AssertionError('accepted UNSAT on a SAT formula')


def native_handoff(tmp):
    # Left block forces x1; each binary clause transmits it to the right.
    # The right block forces not x32 without an input unit on either end.
    source = tmp/'chain.cnf'
    cs = []
    for gate, start in [(1, 2), (-32, 28)]:
        for signs in itertools.product((-1, 1), repeat=4):
            cs.append([gate] + [sign * v for sign, v in zip(signs, range(start, start+4))])
    chain = [1] + list(range(6, 28)) + [32]
    cs.extend([[-a,b] for a,b in zip(chain,chain[1:])])
    source.write_text(f'p cnf 32 {len(cs)}\n' + ''.join(' '.join(map(str,c))+' 0\n' for c in cs))
    for mode in ('default', 'table-fallback', 'table-first'):
        cert = tmp/(mode+'.cert')
        result = run(source,cert,3,mode)
        assert result['status']=='UNSAT', result
        if mode=='table-first':
            assert result['certificate']=='TABLE+DRUP', result
            prefix,suffix = cert.read_text().split('\nsuffix\n',1)
            assert any(line.startswith('t ') and line!='t 0' for line in prefix.splitlines())
            path = tmp/'bare.cert'
            path.write_text(suffix)
            try:
                verify(source,path,20)
            except ValueError:
                continue
            raise AssertionError('diagnostic proof did not need the table prefix')


if __name__ == '__main__':
    truth_table_tests()
    with tempfile.TemporaryDirectory() as tmp:
        integration(Path(tmp))
        native_handoff(Path(tmp))
    print('320 truth-table comparisons, two positive formats and 11 rejection cases passed; native nonempty-lemma handoff verified')
