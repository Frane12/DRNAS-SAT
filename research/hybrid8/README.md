# DRNAS HYBRID-8 — direct source-CNF XOR + 2-SAT to DRUP

**Experimental research branch; main unchanged.**

This is a *restricted* proof-first conversion. It reads the complete source CNF, detects full XOR2/3 clause encodings and 2-CNF implication SCCs, and derives congruence lemmas as RUP clauses. It does **not** use DPLL to find the proof.

For a deliberately constructed paired-XOR-chain family, the generated DRUP proof has exactly

[
L(k) = 16k - 25 	ext{ clauses for } kge3.
]

The original source has (6k-4) variables and (12k-12) clauses. These bounds are **not general SAT bounds**, not a P=NP proof, and not a benchmark against production CDCL solvers.

## Independent verification

[GitHub Actions HYBRID-8 run 44723512475](https://github.com/Frane12/DRNAS-SAT/actions/runs/44723512475) returned **SUCCESS**. A pinned upstream DRAT-trim verified proofs for `k=3,4,8,12,32,64`, plus four renumbered `k=12` cases, all showing `s VERIFIED`. The `k=12` and `k=64` proof SHA256 values were checked against local generated files. `sat` and `broken` controls returned `UNKNOWN` and attempts to verify UNSAT refutations on them were rejected.

Run from the repository root:

```bash
python3 research/hybrid8/generate.py --k 12 --prefix /tmp/h8-k12
# Verify with a separately installed DRAT-trim:
drat-trim /tmp/h8-k12.cnf /tmp/h8-k12.drup -f
```

The generator reports `EMITTED_UNCHECKED` until the independent checker accepts the proof.

**Limits:** Known synthetic family, not a blind holdout; the same detector returned `UNKNOWN` on previously studied original Petersen, Quinn and uf20-01 CNFs. The experiments do not establish a general polynomial algorithm or an exponential lower bound for standard resolution proofs.
