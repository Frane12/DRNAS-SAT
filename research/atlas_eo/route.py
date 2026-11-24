"""Consume shared, source-checked EO facts in the ATLAS proof router."""
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from research.atlas_eo import check, decode
from research.atlas12_graph_hall.bridge import discover as graph_partition, graph_module
from research.atlas15_exchange.witness import verify_full_original_sat_model
from research.pcmax_capacity.source_php_real26 import discover as hall_partition
from research.pcmax_capacity.check_php_partition import check as check_partition
from research.pcmax_capacity.emit_veripb_source_clique import Proof, write_capacity_steps
from research.structure_atlas1.atlas import encoded
from research.structure_atlas3.source_facts import find_xor


def rup_line(row):
    terms = " ".join("1 " + ("~" if x < 0 else "") + f"x{abs(x)}" for x in row)
    return "rup " + (terms + " " if terms else "") + ">= 1 ;\n"


def clauses_proof(path, count, steps):
    with path.open("w") as out:
        out.write(f"pseudo-Boolean proof version 3.0\nf {count} ;\n")
        for row in steps:
            out.write(rup_line(row))
        out.write("output NONE ;\nconclusion UNSAT ;\nend pseudo-Boolean proof ;\n")


def parity_contradiction(formula, groups):
    # Exactly one true signed literal implies odd parity. Match an independently
    # reconstructed complete XOR table on the same variables with opposite RHS.
    rows = set(find_xor(formula.index))
    for group in groups:
        if len(group) > 4:
            continue
        variables = tuple(sorted(abs(x) for x in group))
        odd_rhs = 1 ^ (sum(x < 0 for x in group) % 2)
        if (variables, 1 - odd_rhs) in rows:
            return group
    return None


def disjoint_views(groups):
    # Capacity discovery needs disjoint demand rows. Exact-cover/model search
    # below retains overlapping domains (e.g. row and column choices).
    batches = [groups]
    widths = Counter(map(len, groups))
    if len(widths) > 1:
        batches.extend([g for g in groups if len(g) == k] for k in sorted(widths, reverse=True)
                       if widths[k] >= 3)
    seen = set()
    for batch in batches:
        used, selected = set(), []
        for row in batch:
            variables = set(map(abs, row))
            if used.isdisjoint(variables):
                used.update(variables)
                selected.append(tuple(row))
        key = tuple(selected)
        if 3 <= len(selected) <= 128 and len(used) <= 512 and key not in seen:
            seen.add(key)
            yield selected


def capacity_proof(formula, groups, path, budget):
    with TemporaryDirectory(prefix="atlas-eo-view-") as tmp:
        view = Path(tmp) / "view.cnf"
        cert_path = Path(tmp) / "partition.json"
        implied = {}
        for selected in disjoint_views(groups):
            source_lit = [0] + [lit for group in selected for lit in group]
            alias = {lit: i for i, lit in enumerate(source_lit) if i}
            choices = [tuple(alias[lit] for lit in group) for group in selected]
            # Each view clause will be re-grounded on the original CNF before
            # emitting any arithmetic step. No auxiliary variables are removed.
            exclusions = {tuple(sorted((-a, -b))) for group in choices
                          for a, b in combinations(group, 2)}
            for lit, a in alias.items():
                if lit not in implied:
                    assigned, _, conflict = formula.propagate([lit], budget)
                    implied[lit] = () if conflict else assigned
                for true in implied[lit]:
                    b = alias.get(-true)
                    if b is not None and a != b:
                        exclusions.add(tuple(sorted((-a, -b))))
                # Keep direct mutexes even if a singleton assumption conflicts.
                for cid in formula.occ.get(-lit, ()):
                    pair = formula.rows[cid - 1]
                    if len(pair) == 2:
                        other = pair[0] if pair[1] == -lit else pair[1]
                        b = alias.get(-other)
                        if b is not None and a != b:
                            exclusions.add(tuple(sorted((-a, -b))))
            view.write_bytes(encoded(len(alias), choices + sorted(exclusions)))
            try:
                cert, _ = graph_partition(view, budget=3000)
                mode = "EO_GRAPH"
            except graph_module.Unsupported:
                hall = hall_partition(view)
                if hall.get("status") != "CERTIFICATE_EMITTED_UNCHECKED":
                    continue
                cert, mode = hall["certificate"], "EO_HALL"
            cert_path.write_text(json.dumps(cert))
            check_partition(view, cert_path)
            demand_ids, pair_ids = {}, {}
            with path.open("w") as stream:
                proof = Proof(stream, len(formula.rows))

                def premise(row):
                    cid = formula.index.get(frozenset(row))
                    if cid is None:
                        if formula.rup(row, budget) is None:
                            raise AssertionError("unjustified capacity premise")
                        stream.write(rup_line(row))
                        proof.last += 1
                        cid = proof.last
                    return cid

                for group in cert["selected_groups"]:
                    demand_ids[tuple(sorted(group))] = premise([source_lit[x] for x in group])
                for resource in cert["capacity_cliques"]:
                    for a, b in combinations(sorted(resource), 2):
                        pair_ids[a, b] = premise([-source_lit[a], -source_lit[b]])
                write_capacity_steps(proof, cert, demand_ids, pair_ids)
            return mode, {"demand": cert["demand"], "capacity": cert["capacity"]}
    return None


def domain_search(raw, nv, source, groups, extra, budget, max_nodes=384):
    # Branch only on a certified finite domain. Unexplained residual clauses
    # can stop this procedure. Every positive return carries a whole-source model.
    formula = decode.CNF(source.rows + extra)
    stack_proof = []
    nodes = 0

    def visit(decisions):
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise decode.Limit("domain search node limit")
        assigned, _, conflict = formula.propagate(decisions, budget)
        if not conflict:
            options = None
            for group in groups:
                if any(lit in assigned for lit in group):
                    continue
                free = [lit for lit in group if -lit not in assigned]
                if options is None or len(free) < len(options):
                    options = free
            if options is None:
                for default in (False, True):
                    bits = [None] + [True if v in assigned else False if -v in assigned else default
                                     for v in range(1, nv + 1)]
                    if all(any(bits[abs(x)] == (x > 0) for x in row) for row in source.rows):
                        model = {"source_sha256": sha256(raw).hexdigest(), "assignment": bits}
                        verify_full_original_sat_model(raw, model)
                        return "SAT", model
                return "UNKNOWN", None
            unresolved = False
            for lit in options:
                status, model = visit(decisions + [lit])
                if status == "SAT":
                    return status, model
                unresolved |= status == "UNKNOWN"
            if unresolved:
                return "UNKNOWN", None
        # Child blocking clauses plus the source-supported ALO imply this
        # blocking clause by RUP. At the root it is the empty clause.
        stack_proof.append([-x for x in decisions])
        return "UNSAT", None

    status, model = visit([])
    return status, model, stack_proof, nodes


def candidate(raw, folder):
    """Returned UNSAT proofs still require external checking on the exact source."""
    if len(raw) > 2_000_000:
        return {"mode": "EO", "reason": "source size limit"}
    nv, formula, facts = decode.decode(raw)
    verified = check.verify(raw, facts)
    (folder / "eo-facts.json").write_text(json.dumps(facts, separators=(",", ":")) + "\n")
    groups = facts["groups"]
    info = {"groups": verified["groups_verified"], "scan": facts["scan"]["stop"]}
    if not groups:
        return {**info, "mode": "EO", "reason": "no checked domain"}
    extra = [r["clause"] for r in facts["premises"] if frozenset(r["clause"]) not in formula.index]
    path = folder / "eo.pbp"
    path.unlink(missing_ok=True)
    parity = parity_contradiction(formula, groups)
    if parity:
        clauses_proof(path, len(formula.rows), extra + [[-lit] for lit in parity] + [[]])
        return {**info, "mode": "EO_XOR", "proof": path}
    try:
        result = capacity_proof(formula, groups, path, decode.Budget(1_200_000))
    except decode.Limit:
        path.unlink(missing_ok=True)
        result = None
    if result:
        mode, details = result
        return {**info, **details, "mode": mode, "proof": path}
    try:
        status, model, steps, nodes = domain_search(raw, nv, formula, groups, extra, decode.Budget(2_000_000))
    except decode.Limit as exc:
        return {**info, "mode": "EO_DOMAINS", "reason": str(exc)}
    if status == "UNSAT":
        clauses_proof(path, len(formula.rows), extra + steps)
        return {**info, "nodes": nodes, "mode": "EO_DOMAINS", "proof": path}
    if status == "SAT":
        return {**info, "nodes": nodes, "mode": "EO_DOMAINS", "model": model}
    return {**info, "nodes": nodes, "mode": "EO_DOMAINS", "reason": "unexplained residual clauses"}
