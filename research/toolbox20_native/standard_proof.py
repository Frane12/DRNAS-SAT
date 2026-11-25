"""Offline DRUP export from a checked native GF(2) or small Hall certificate.

This program is outside the benchmark and is never called by the candidate.
Each output proof can be replayed with an unmodified DRAT checker.
"""
import argparse
import itertools
import json
import random
from pathlib import Path
from verify import verify_hall, verify_xor


def plan_merges(equations, seed):
    rng = random.Random(seed)
    rows = list(equations)
    plan = []
    cost = 0
    while len(rows) >= 2:
        options = []
        for i, (a, _) in enumerate(rows):
            for j, (b, _) in enumerate(rows[:i]):
                intersection = a & b
                if intersection:
                    options.append((len(a ^ b), len(a | b), rng.random(), i, j))
        if not options:
            return None
        _, _, _, i, j = min(options)
        a, ar = rows.pop(i)
        b, br = rows.pop(j)
        remaining = sorted(a ^ b)
        shared = sorted(a & b)
        rhs = ar ^ br
        # Under a forbidden assignment to the remaining variables, assigning
        # all but one shared variable makes the two parent equations opposite units.
        guards = shared[:-1]
        cost += (1 << max(0, len(remaining)-1)) * ((1 << (len(guards)+1)) - 1)
        plan.append((remaining, rhs, guards))
        if not remaining and rhs:
            return cost, plan
        if remaining:
            rows.append((frozenset(remaining), rhs))
    return None


def blockers(variables):
    for bits in itertools.product((0,1), repeat=len(variables)):
        yield sum(bits) % 2, tuple(-v if b else v for v,b in zip(variables,bits))


def write_proof(cnf, cert, output, limit=300000):
    if output.exists() and output.samefile(cnf):
        raise ValueError("proof output must differ from the input CNF")
    raw = cnf.read_bytes()
    steps = 0
    if cert.get("format") == "drnas-math4-xor-unit-v1":
        verify_xor(raw,cert)
        eqs = [(frozenset(r["vars"]), 1-r["forbidden_parity"]) for r in cert["xor_rows"]]
        eqs.extend((frozenset([abs(l)]),int(l>0)) for l in cert["root_units"])
        if len(eqs)>192:
            raise ValueError("parity export supports at most 192 equations")
        plans = (plan_merges(eqs, seed) for seed in range(64))
        best = min((p for p in plans if p), key=lambda p:p[0], default=None)
        if not best or best[0]+len(cert["root_units"]) > limit:
            raise ValueError("bounded parity export exhausted")
        def lines():
            for lit in cert["root_units"]:
                yield (lit,)
            for remaining, rhs, guards in best[1]:
                for parity, main in blockers(remaining):
                    if parity == rhs:
                        continue
                    for width in range(len(guards),-1,-1):
                        for _, prefix in blockers(guards[:width]):
                            yield main+prefix
    else:
        verify_hall(raw,cert)
        groups = cert["alo_groups"][:len(cert["resource_cliques"])+1]
        prefixes = 1; total = 1
        for group in groups:
            prefixes *= len(group); total += prefixes
            if total > limit: raise ValueError("bounded Hall export exhausted")
        # Every full selection violates at least one source mutex. At each
        # parent, its original ALO and all child blockers refute that prefix.
        def lines():
            for width in range(len(groups),-1,-1):
                for chosen in itertools.product(*groups[:width]):
                    yield tuple(-l for l in chosen)
    try:
        with output.open("w",encoding="ascii") as stream:
            for c in lines():
                if steps >= limit: raise ValueError("proof output bound reached")
                stream.write("".join(f"{l} " for l in c)+"0\n")
                steps += 1
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return steps


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cnf",type=Path);p.add_argument("certificate",type=Path);p.add_argument("drup",type=Path)
    a = p.parse_args()
    if a.drup.exists() and a.drup.samefile(a.certificate):
        p.error("proof output must differ from the certificate")
    print(write_proof(a.cnf,json.loads(a.certificate.read_bytes()),a.drup))
