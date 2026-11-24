"""Find source SAT models by conditioning on a small strong backdoor to 2-CNF."""
from collections import Counter
from hashlib import sha256
from time import monotonic

from research.implication_model import implication_model
from research.structure_atlas1.atlas import parse


def candidate(raw, deadline, max_cutset=12):
    info = {"mode": "BINARY_CUTSET", "valuations": 0, "scc_calls": 0}
    if len(raw) > 128_000:
        return {**info, "reason": "source size limit"}
    nv, rows = parse(raw)
    if nv > 256 or len(rows) > 512:
        return {**info, "reason": "input dimensions exceed cutset budget"}
    unique = {frozenset(row) for row in rows}
    clauses = sorted(tuple(sorted(c)) for c in unique if all(-x not in c for x in c))
    long_rows = [{abs(x) for x in row} for row in clauses if len(row) > 2]
    cutset = []
    while long_rows:
        if len(cutset) == max_cutset:
            return {**info, "reason": "cutset width limit"}
        counts = Counter(v for row in long_rows for v in row)
        pivot = min(counts, key=lambda v: (-counts[v], v))
        cutset.append(pivot)
        for row in long_rows:
            row.discard(pivot)
        long_rows = [row for row in long_rows if len(row) > 2]
    info["cutset"] = cutset
    masks = {v: 1 << i for i, v in enumerate(cutset)}
    templates = []
    for row in clauses:
        positive = sum(masks[x] for x in row if x in masks)
        negative = sum(masks[-x] for x in row if -x in masks)
        remaining = tuple(x for x in row if abs(x) not in masks)
        assert len(remaining) <= 2
        templates.append((remaining, positive, negative))
    templates.sort(key=lambda t: len(t[0]))  # Reject empty residuals before calling SCC.
    for bits in range(1 << len(cutset)):
        if monotonic() >= deadline:
            return {**info, "reason": "cutset time limit"}
        info["valuations"] += 1
        binary = []
        for remaining, positive, negative in templates:
            if bits & positive or ~bits & negative:
                continue
            if not remaining:
                break
            binary.append(remaining)
        else:
            info["scc_calls"] += 1
            model = implication_model(nv, binary)
            if model is None:
                continue
            for v in cutset:
                model[v - 1] = bool(bits & masks[v])
            return {**info, "model": {"source_sha256": sha256(raw).hexdigest(),
                                      "assignment": [None] + model}}
    return {**info, "reason": "no model found; no UNSAT certificate"}
