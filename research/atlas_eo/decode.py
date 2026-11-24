"""Recover exactly-one consequences from source DIMACS and retain ordered RUP hints."""
from collections import defaultdict
from hashlib import sha256
from itertools import combinations

from research.structure_atlas1.atlas import parse


class Limit(Exception):
    """A search limit produces partial facts, never a logical conclusion."""


class Budget:
    def __init__(self, visits):
        self.remaining = visits

    def spend(self, count=1):
        self.remaining -= count
        if self.remaining < 0:
            raise Limit("propagation visit limit")


class CNF:
    def __init__(self, rows):
        self.rows = []
        self.index = {}
        self.occ = defaultdict(list)
        self.units = []
        for cid, source_row in enumerate(rows, 1):
            row = tuple(dict.fromkeys(source_row))
            self.rows.append(row)
            key = frozenset(row)
            if any(-lit in key for lit in key) or key in self.index:
                continue
            self.index[key] = cid
            if len(row) <= 1:
                self.units.append(cid)
            for lit in row:
                self.occ[lit].append(cid)

    def propagate(self, assumptions, budget):
        """Return assigned literals, ordered reasons, and a conflicting clause ID or zero."""
        assigned = set(assumptions)
        queue = list(assigned)
        reasons = []
        for cid in self.units:
            row = self.rows[cid - 1]
            budget.spend()
            if not row or -row[0] in assigned:
                return assigned, reasons, cid
            if row[0] not in assigned:
                queue.append(row[0])
                assigned.add(row[0])
                reasons.append((row[0], cid))
        for lit in queue:
            for cid in self.occ.get(-lit, ()):
                row = self.rows[cid - 1]
                budget.spend(len(row))
                if any(x in assigned for x in row):
                    continue
                free = [x for x in row if -x not in assigned]
                if not free:
                    return assigned, reasons, cid
                if len(free) == 1:
                    unit = free[0]
                    assigned.add(unit)
                    queue.append(unit)
                    reasons.append((unit, cid))
        return assigned, reasons, 0

    def rup(self, clause, budget):
        cid = self.index.get(frozenset(clause))
        if cid is not None:
            return [cid]
        _, reasons, conflict = self.propagate([-lit for lit in clause], budget)
        if not conflict:
            return None
        # Keep the implication cone ending at the conflict. Every hint names
        # an original clause, including after clause shuffles and sign flips.
        needed = {-x for x in self.rows[conflict - 1]}
        proof = [conflict]
        for lit, cid in reversed(reasons):
            if lit in needed:
                proof.append(cid)
                needed.remove(lit)
                needed.update(-x for x in self.rows[cid - 1] if x != lit)
        return proof[::-1]

    def asserted_disjunctions(self, max_width):
        # Source unit u and a fully defined u <-> (a OR b). Signs may be mixed.
        gates = defaultdict(set)
        for key in self.index:
            if len(key) != 3:
                continue
            for root in key:
                u = -root
                a, b = sorted(key - {root})
                if (frozenset((u, -a)) in self.index and
                        frozenset((u, -b)) in self.index):
                    gates[u].add((a, b))
        for cid in self.units:
            row = self.rows[cid - 1]
            if not row:
                continue
            leaves = list(row)
            expanded = set()
            while 1 <= len(leaves) <= max_width:
                u = next((x for x in leaves if len(gates.get(x, ())) == 1), None)
                if u is None or u in expanded:
                    break
                expanded.add(u)
                leaves.remove(u)
                leaves.extend(next(iter(gates[u])))
                if len({abs(x) for x in leaves}) != len(leaves):
                    break
                if 2 <= len(leaves) <= max_width:
                    yield tuple(sorted(leaves))


def decode(raw, *, max_width=32, max_candidates=4096, max_queries=24000,
           max_groups=512, visits=2_000_000):
    nv, rows = parse(raw)
    formula = CNF(rows)
    budget = Budget(visits)
    groups, proofs = [], {}
    tested = queries = 0
    stop = "complete"
    try:
        if formula.propagate([], budget)[2]:
            raise Limit("root propagation conflict; no domain interpretation")
        inferred = set(formula.asserted_disjunctions(max_width))
        candidates = set(inferred)
        candidates.update(tuple(sorted(key)) for key in formula.index
                          if 2 <= len(key) <= max_width and len({abs(x) for x in key}) == len(key))
        # Prefer larger selector groups over the short gates inside an encoder.
        for group in sorted(candidates, key=lambda g: (-len(g), g not in inferred, g)):
            if tested >= max_candidates or len(groups) >= max_groups:
                raise Limit("candidate or group limit")
            tested += 1
            local = {}
            for clause in (group, *(tuple(sorted((-a, -b))) for a, b in combinations(group, 2))):
                if clause in proofs:
                    continue
                if queries >= max_queries:
                    raise Limit("RUP query limit")
                queries += 1
                hints = formula.rup(clause, budget)
                if hints is None:
                    break
                local[clause] = hints
            else:
                groups.append(list(group))
                proofs.update(local)
    except Limit as exc:
        stop = str(exc)
    facts = {"format": "DRNAS-EO-RUP-v1", "source_sha256": sha256(raw).hexdigest(),
             "groups": groups,
             "premises": [{"clause": list(c), "hints": h} for c, h in proofs.items()],
             "scan": {"stop": stop, "tested_candidates": tested, "queries": queries,
                      "visits": visits - max(0, budget.remaining)}}
    return nv, formula, facts
