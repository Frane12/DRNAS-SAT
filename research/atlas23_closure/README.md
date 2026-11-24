# ATLAS23 — GF(2) × PCMAX × ARITH2 proof closure (2026-11-24)

**Scope:** controlled, synthetic, explicitly structured CNF. This is a *communication/proof-bus prototype*, **not** automatic recognition of arithmetic or arbitrary structures from unseen DIMACS. The repository `main` remains unchanged.

## Three-way witness

- **GF2:** `x XOR y0 = 0`.
- **PCMAX:** `x + z0 <= 0` (two binary capacity demands).
- **ARITH2:** `(z1 z0)_2 = ((y1 y0)_2 + 1) modulo 4`.

Every **individual constraint** and every **pair of modules** is satisfiable. All three together are UNSAT:

1. PCMAX derives `x=0` and `z0=0`.
2. GF2 derives `y0=0` from `x=0`.
3. ARITH2 forbids `y0=0, z0=0` because adding 1 flips the least significant bit. A conflict is proven without CDCL.

The original CNF contains **5 variables, 17 clauses and no initial unit clauses**. This makes ordinary *initial* unit propagation unable to begin, but it does not establish an advantage over other SAT solvers.

## What is implemented

- `closure.py`: exhaustive local truth tables for the three *identified* mathematical relations; monotone fact exchange; guarded natural join for SAT witnesses; `UNKNOWN` on insufficient budget.
- `independent.py`: separate implementation of source semantics, exhaustive truth-table CNF equivalence check (32 global assignments), all 1/2/3-module SAT checks, replay of each local proof event against its premises, independently checked SAT models.
- CI checks a 12-case capacity/addition grid, a low-budget `UNKNOWN` guard and five negative controls that corrupt source/proof/model.
- No CDCL fallback. No solver-reported UNSAT is promoted to a proof.

Run from the repository root:

```bash
python3 research/atlas23_closure/closure.py --out atlas23_artifacts
python3 research/atlas23_closure/independent.py --cnf atlas23_artifacts/source.cnf --trace atlas23_artifacts/trace.json --out atlas23_artifacts/audit.json
python3 research/atlas23_closure/independent.py --selftest
```

## Scientific boundary and next steps

The custom replay trace is mathematically verified for this 5-variable family but **is not DRAT/LRAT/VeriPB**; the global exhaustive audit is feasible precisely because the instance is small. It is not evidence of a speedup or a solved industrial instance. Next: detect the same relations directly from unseen raw CNF, preserve mapping to original clauses, emit an independently checkable standard UNSAT certificate, add harder mutually necessary modules and compare end-to-end against Kissat/CaDiCaL on blinded holdouts.
