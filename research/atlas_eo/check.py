"""Independent exactly-one witness replay. No imports from the discovery module."""
import argparse
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.structure_atlas1.atlas import parse


def verify(raw, facts):
    if facts.get("format") != "DRNAS-EO-RUP-v1" or facts.get("source_sha256") != sha256(raw).hexdigest():
        raise ValueError("EO certificate/source mismatch")
    nv, original = parse(raw)
    rows = [set(row) for row in original]
    proven = set()
    for record in facts["premises"]:
        clause = record["clause"]
        if (not clause or any(type(x) is not int or not 1 <= abs(x) <= nv for x in clause)
                or len({abs(x) for x in clause}) != len(clause)):
            raise ValueError("invalid signed premise")
        hints = record["hints"]
        true = {-lit for lit in clause}
        for pos, cid in enumerate(hints):
            if type(cid) is not int or not 1 <= cid <= len(rows):
                raise ValueError("invalid source premise ID")
            row = rows[cid - 1]
            if row & true:
                raise ValueError("satisfied hint")
            left = [x for x in row if -x not in true]
            if len(left) == 1 and pos != len(hints) - 1:
                true.add(left[0])
            elif left or pos != len(hints) - 1:
                raise ValueError("hints do not replay to a final conflict")
        if not hints:
            raise ValueError("missing conflict")
        proven.add(frozenset(clause))
    for group in facts["groups"]:
        if (len(group) < 1 or any(type(x) is not int or not 1 <= abs(x) <= nv for x in group)
                or len({abs(x) for x in group}) != len(group)):
            raise ValueError("invalid selector group")
        if frozenset(group) not in proven:
            raise ValueError("unverified at-least-one")
        if any(frozenset((-a, -b)) not in proven for a, b in combinations(group, 2)):
            raise ValueError("unverified pair exclusion")
    return {"groups_verified": len(facts["groups"]), "premises_verified": len(proven)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cnf", type=Path)
    parser.add_argument("facts", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.cnf.read_bytes(), json.loads(args.facts.read_text()))))
