"""Regression and adversarial tests for source-bound EO facts (standard library)."""
from copy import deepcopy
from itertools import combinations, product
import random
import unittest
from time import monotonic

from research.atlas_eo.binary_cutset import candidate as cutset_candidate

from research.atlas_eo import check, decode
from research.atlas16_pilot import run
from research.atlas_eo.route import domain_search
from research.structure_atlas1.semantic_eo import construct, unit_conflict
from research.structure_atlas1.atlas import encoded


def rename(nv, rows, seed):
    rng = random.Random(seed)
    slots = list(range(1, nv + 1))
    rng.shuffle(slots)
    mapping = [0] + [v * rng.choice([-1, 1]) for v in slots]

    def mapped(lit):
        return mapping[abs(lit)] if lit > 0 else -mapping[-lit]

    result = []
    for row in rows:
        changed = [mapped(x) for x in row]
        rng.shuffle(changed)
        result.append(changed)
    rng.shuffle(result)
    return encoded(nv, result), mapped


class RecoveryTests(unittest.TestCase):
    def test_signed_direct_and_sequential(self):
        for kind in ("pairwise", "sequential"):
            nv, rows = construct(6, kind)
            for seed in range(8):
                raw, mapped = rename(nv, rows, seed)
                _, _, facts = decode.decode(raw)
                self.assertIn(sorted(mapped(i) for i in range(1, 7)), facts["groups"])
                check.verify(raw, facts)

    def test_hidden_alo_and_damaged_controls(self):
        group = [1, 2, 3, 4]
        mutex = [(-a, -b) for a,b in combinations(group, 2)]
        # Unit output and three bidirectionally defined OR gates.
        tree = [(7,)]
        for u,a,b in [(5, 1, 2), (6, 3, 4), (7, 5, 6)]:
            tree += [(-u, a, b), (u, -a), (u, -b)]
        for rows, want in [(tree + mutex, True), (tree + mutex[1:], False),
                           (tree[1:] + mutex, False), (mutex, False),
                           ([tuple(group)], False), ([tuple(group)] + mutex + [(1, -1), (-1,-2,-2)], True)]:
            raw = encoded(7, rows)
            _, _, facts = decode.decode(raw)
            self.assertEqual(group in facts["groups"], want)
            check.verify(raw, facts)

    def test_unary_and_width_boundary(self):
        for k in (1, 2, 32):
            xs = list(range(1,k+1))
            raw = encoded(k, [xs] + [(-a,-b) for a,b in combinations(xs,2)])
            _, _, facts = decode.decode(raw)
            self.assertIn(xs,facts["groups"])
            check.verify(raw,facts)

    def test_original_and_recoded_petersen_within_domain_budget(self):
        from research.structure_atlas3.source_facts import reencode_amo
        raw = (run.ROOT/"evidence/ipg7b-petersen/original.cnf").read_bytes()
        _, _, initial = decode.decode(raw)
        recoded = raw
        for group in initial["groups"]:
            recoded, _ = reencode_amo(recoded,group)
        n, rows = run.parse(recoded)
        for data in (raw, rename(n,rows,2307)[0]):
            nv, cnf, facts = decode.decode(data)
            extra = [r["clause"] for r in facts["premises"] if frozenset(r["clause"]) not in cnf.index]
            status, _, steps, _ = domain_search(data,nv,cnf,facts["groups"],extra,decode.Budget(2_000_000))
            self.assertEqual(status,"UNSAT")
            self.assertEqual(steps[-1],[])
            prior = list(cnf.rows)+extra
            for clause in steps:
                self.assertTrue(unit_conflict(prior,[-x for x in clause]))
                prior.append(clause)

    def test_binary_cutset_models_and_limits(self):
        raw = (run.ROOT/"research/structure1_corpus/uf20-01.cnf").read_bytes()
        nv, rows = run.parse(raw)
        for data in [raw] + [rename(nv,rows,seed)[0] for seed in (1,10,101)]:
            result = cutset_candidate(data, monotonic()+3)
            run.verify_full_original_sat_model(data, result["model"])
            self.assertLessEqual(len(result["cutset"]), 12)
        self.assertNotIn("model", cutset_candidate(raw, monotonic()+3, max_cutset=0))
        self.assertNotIn("model", cutset_candidate(raw, monotonic()-1))
        # Every ternary assignment is excluded. No negative result bypasses proof checking.
        impossible = encoded(3, [tuple(i*s for i,s in zip((1,2,3),signs))
                                  for signs in product((1,-1), repeat=3)])
        result = cutset_candidate(impossible, monotonic()+3)
        self.assertNotIn("proof", result)
        self.assertNotIn("model", result)
        mixed = encoded(5, [(1,1), (-1,2), (4,-4), (2,2,3)])
        model = cutset_candidate(mixed, monotonic()+3)["model"]
        run.verify_full_original_sat_model(mixed, model)
        model["assignment"][1] = False
        with self.assertRaises(ValueError):
            run.verify_full_original_sat_model(mixed, model)

    def test_invalid_transport(self):
        raw = encoded(*construct(4, "sequential"))
        _, _, facts = decode.decode(raw)
        original = set(range(1, 5))
        self.assertTrue(any(set(g) == original for g in facts["groups"]))
        for problem in ("source", "truncation", "false_hint", "bad_id", "extra_selector"):
            bad = deepcopy(facts)
            if problem == "source": bad["source_sha256"] = "0" * 64
            elif problem == "truncation": bad["premises"][0]["hints"] = []
            elif problem == "false_hint": bad["premises"][0]["hints"] = [2]
            elif problem == "bad_id": bad["premises"][0]["hints"] = [0]
            else: bad["groups"][0].append(7)
            with self.assertRaises(ValueError):
                check.verify(raw, bad)

    def test_budget_and_random_oracle(self):
        rng = random.Random(73251)
        saw_groups = 0
        for trial in range(120):
            nv = 6
            rows = [[v * rng.choice((-1,1)) for v in rng.sample(range(1,nv+1), rng.randint(1,4))]
                    for _ in range(rng.randint(3,14))]
            if trial % 3 == 0:
                rows += [(1,2,3), (-1,-2),(-1,-3),(-2,-3)]
            raw = encoded(nv, rows)
            _, cnf, facts = decode.decode(raw, max_queries=40 if trial%4==0 else 5000)
            check.verify(raw, facts)
            saw_groups += len(facts["groups"])
            models = []
            for b in product((False,True), repeat=nv):
                if all(any(b[abs(x)-1] == (x>0) for x in row) for row in rows):
                    models.append(b)
            for g in facts["groups"]:
                self.assertTrue(all(sum(b[abs(x)-1] == (x>0) for x in g)==1 for b in models))
            for rec in facts["premises"]:
                c = rec["clause"]
                self.assertTrue(unit_conflict(rows, [-v for v in c]))
            if facts["groups"]:
                extra = [r["clause"] for r in facts["premises"] if frozenset(r["clause"]) not in cnf.index]
                status, _, steps, _ = domain_search(raw,nv,cnf,facts["groups"],extra,decode.Budget(500000))
                if status != "UNKNOWN":
                    self.assertEqual(status == "SAT", bool(models))
                if status == "UNSAT":
                    prior = list(rows) + extra
                    for row in steps:
                        self.assertTrue(unit_conflict(prior, [-x for x in row]))
                        prior.append(row)
        self.assertGreater(saw_groups, 30)
        raw = encoded(*construct(6,"sequential"))
        _, _, limited = decode.decode(raw, max_queries=2)
        check.verify(raw,limited)
        self.assertNotEqual(limited["scan"]["stop"], "complete")
