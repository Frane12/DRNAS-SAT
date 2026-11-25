"""Independent result validation. The candidate never imports this file."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "pcmax_capacity"), str(ROOT / "math4")]
from check_capacity import parse_cnf
from check_clause_hall import check as verify_hall
from check_xor_units import verify as verify_xor


def check_model(raw, output):
    n, clauses = parse_cnf(raw)
    values = {}
    terminated = False
    for line in output.splitlines():
        fields = line.split()
        if not fields or fields[0] != "v":
            continue
        for literal in map(int, fields[1:]):
            if terminated:
                raise ValueError("model data after 0")
            if literal == 0:
                terminated = True
                continue
            var = abs(literal)
            if var > n or (var in values and values[var] != (literal > 0)):
                raise ValueError("invalid model literal")
            values[var] = literal > 0
    if not terminated or len(values) != n:
        raise ValueError("expected a terminated, total model")
    if not all(any(values[abs(l)] == (l > 0) for l in c) for c in clauses):
        raise ValueError("model falsifies an input clause")
    return "MODEL"


def check_unsat(path, proof, checker):
    with proof.open("rb") as stream:
        first = stream.read(1)
    if first == b"{":
        cert = json.loads(proof.read_bytes())
        if cert.get("format") == "drnas-math4-xor-unit-v1":
            verify_xor(path.read_bytes(), cert)
            return "GF2"
        verify_hall(path.read_bytes(), cert)
        return "HALL"
    result = subprocess.run([checker, str(path), str(proof)], capture_output=True, timeout=45)
    if result.returncode != 0 or b"s VERIFIED" not in result.stdout.splitlines():
        raise ValueError("DRAT rejected: " + result.stdout[-400:].decode(errors="replace"))
    return "DRAT"
