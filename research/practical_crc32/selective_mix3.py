#!/usr/bin/env python3
"""DRNAS SELECTIVE-MIX3: budgeted Kissat -> R28-MIX2 -> Kissat.

Research wrapper around the SHA-pinned *unmodified* Kissat and experimental
MIX2, all invoked as separate single-core subprocesses on the same original
DIMACS. No training/ground-truth labels or instance names are used for routing.

Provisional MIX2 UNSAT is NOT a standard certificate; the CI harness checks
each such verdict independently against the original CNF *after* timed solve.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

STATUS_RE = re.compile(r"(?m)^s\s+(SATISFIABLE|UNSATISFIABLE|UNKNOWN)\s*$")
STATUS_VALUES = {"SATISFIABLE": "SAT", "UNSATISFIABLE": "UNSAT", "UNKNOWN": "UNKNOWN"}

def run_stage(command: list[str], timeout: float) -> dict:
    start = time.perf_counter()
    if timeout <= 0:
        return {"status": "TIMEOUT", "seconds": 0.0, "stdout": "",
                "stderr": "", "return_code": None}
    try:
        p = subprocess.run(command, capture_output=True, text=True,
                           timeout=timeout, check=False)
        status_m = STATUS_RE.findall(p.stdout)
        status = STATUS_VALUES[status_m[-1]] if status_m else "UNKNOWN"
        # Never trust a success verdict without an expected exit code.
        if status == "SAT" and p.returncode != 10:
            status = "ERROR"
        if status == "UNSAT" and p.returncode != 20:
            status = "ERROR"
        return {"status": status, "seconds": time.perf_counter()-start,
                "stdout": p.stdout, "stderr": p.stderr,
                "return_code": p.returncode}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "seconds": time.perf_counter()-start,
                "stdout": "", "stderr": "", "return_code": None}

def print_verdict(kind: str, route: str, elapsed: float, output: str = "") -> int:
    print("c DRNAS_MIX3_ROUTE via="+route+" elapsed_s="+format(elapsed, ".6f"))
    print("c DRNAS_MIX3_CERT status=project_check_required_if_mix2_unsat;standard_proof=none")
    if kind in ("SAT", "UNSAT"):
        if output:
            # Preserve the SAT model for the original-CNF witness verifier.
            for line in output.splitlines():
                if line.startswith(("s ", "v ")):
                    print(line)
        else:
            print("s "+("SATISFIABLE" if kind=="SAT" else "UNSATISFIABLE"))
        return 10 if kind == "SAT" else 20
    print("s UNKNOWN")
    return 0

def solve(cnf: Path, kissat: Path, mix2: Path, cap: float,
          probe: float, mix_budget: float) -> int:
    start = time.perf_counter()
    limit = start + cap
    def available() -> float:
        return max(0.0, limit - time.perf_counter())
    print(f"c DRNAS_MIX3_CONFIG total_cap_s={cap:.3f} probe_s={probe:.3f} mix_budget_s={mix_budget:.3f}")
    # 1. Catch cheap SAT (faulty CRC) and cheap UNSAT before structural overhead.
    first = run_stage([str(kissat), str(cnf)], min(probe, available()))
    print(f"c DRNAS_MIX3_STAGE name=kissat_probe status={first['status']} secs={first['seconds']:.6f}")
    if first["status"] in ("SAT", "UNSAT"):
        return print_verdict(first["status"], "kissat_probe",
                             time.perf_counter()-start, first["stdout"])
    # 2. Give the specialized structural detector a *bounded*, useful interval.
    # Reserve some time for a complete fallback, not just indefinite UNKNOWN.
    portion = min(mix_budget, max(0.0, available()-0.05))
    second = run_stage([str(mix2), str(cnf)], portion)
    print(f"c DRNAS_MIX3_STAGE name=mix2 status={second['status']} secs={second['seconds']:.6f}")
    if second["status"] == "UNSAT":
        # Expected external project-level check, not timed here. The workflow
        # fails hard if the independently implemented checker disagrees.
        return print_verdict("UNSAT", "mix2_project_check_required",
                             time.perf_counter()-start, second["stdout"])
    if second["status"] == "SAT":
        # MIX2 currently does not emit SAT assignments: never accept without
        # a witness. A complete backend must confirm on the source formula.
        print("c DRNAS_MIX3_REJECT reason=mix2_sat_without_source_witness")
    # 3. Use a *fresh* unmodified Kissat with whatever wall-time remains.
    third = run_stage([str(kissat), str(cnf)], available())
    print(f"c DRNAS_MIX3_STAGE name=kissat_fallback status={third['status']} secs={third['seconds']:.6f}")
    if third["status"] in ("SAT", "UNSAT"):
        return print_verdict(third["status"], "kissat_fallback",
                             time.perf_counter()-start, third["stdout"])
    return print_verdict("UNKNOWN", "budget_exhausted",
                         time.perf_counter()-start)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cnf", type=Path)
    ap.add_argument("--kissat", type=Path, required=True)
    ap.add_argument("--mix2", type=Path, required=True)
    ap.add_argument("--total-cap", type=float, default=11.8)
    ap.add_argument("--probe", type=float, default=0.25)
    ap.add_argument("--mix-budget", type=float, default=6.5)
    args = ap.parse_args()
    if args.total_cap <= 0 or args.probe < 0 or args.mix_budget <= 0:
        ap.error("positive total cap and mix budget required; probe nonnegative")
    sys.exit(solve(args.cnf, args.kissat, args.mix2,
                   args.total_cap, args.probe, args.mix_budget))
