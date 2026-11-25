# DRNAS UNIFIED1: shared mathematical inference

Experimental only; main and frozen TOOLBOX20 are untouched. Native C++20, no reference solver or CDCL fallback in the candidate. Input is anonymous DIMACS. Baseline code and its original source-hash-bound Hall/GF(2) certificates remain intact.

## Integration

- TOOLBOX20: root propagation, Hall capacity, GF(2) extraction/candidate model, short resolution, guarded case reasoning, exact existential projection, SAT-only model repair and reverse reconstruction.
- GENERAL6/7-inspired: sparse bounded exact local truth-table joins. A relation is its support and a forbidden-assignment mask. Combining two relations eliminates their common variables; a boundary assignment is forbidden only if every internal assignment violates a parent. The same operation handles parity and nonlinear relations. New clauses are DRUP-lifted by local resolution and enter the shared active CNF.
- ATLAS40-inspired: bounded RUP probing of strict subclauses. All accepted consequences are visible to all subsequent stages.
- Cost-aware controller: each epoch explores four deductions; productive methods get priority next epoch. An exact relation-version pair cache suppresses redundant joins. No new consequences means stop; projection may expose a new residual and trigger another reasoning epoch. Bounds protect time and memory.
- Every SAT model is checked against original input, then checked independently by the harness. Clausal UNSAT outputs use drat-trim. Existing early structural certificates use independent Hall/GF(2) validators (not claimed as standard DRAT unless separately exported). UNKNOWN never counts as solved.

This is a new shared-state implementation inspired by GENERAL6/7 and ATLAS40, not a byte-for-byte port of every algorithm from those branches. Global sparse affine elimination, BDD/LP engines and persistent cross-instance learning are not newly integrated. Large inputs bypass the new relation tables under the explicit memory policy.

## Prospective validation

The push workflow first compares 160 tiny formulas with exhaustive truth and independent proof/model verification. It then draws 50 new generated inputs after the code is frozen (10 each of Tseitin, random 3-SAT, graph colouring, circuit equivalence, and mixed affine/nonlinear circuits). These are new seeds from previously known families, not external unseen industrial benchmarks. Four arms run on one logical CPU with identical 10 s caps and independent checks: UNIFIED1, frozen TOOLBOX20, Kissat, CaDiCaL. One repetition is a pilot, not a final speed claim. Record all per-case failures and method telemetry. No automatic promotion.

Build: c++ -std=c++20 -O3 -DNDEBUG research/toolbox20_native/unified.cpp -lcrypto -o drnas-unified1

Run: ./drnas-unified1 input.cnf evidence 10
