# ATLAS20 — XOR-shift original CNF SAT model (source-backed circuit)

**24 November 2026.** Original source: public SAT Competition 2026 benchmark
xorshift_r16_110.sanitized.cnf, previously reported by our ATLAS17/18/19
source-only methods as UNKNOWN. The public catalog recorded an unknown status
at the time of selection. This note does not claim the SAT result was unknown
to the benchmark authors, or that the method is asymptotically efficient.

## Exact source and independent model

Original input: 2,430 Boolean variables, 8,868 clauses.

Original CNF SHA-256:

450b963e0ebebe3c08049067e2c954304712b1601711223bbfff1807c74b236e

The source-specific gate grammar was verified **clause by clause** without
using the filename, presumed status or a saved model. Exactly 2,398 output
variables are *defined* by complete original CNF gate constraints:

- 1,642 three-input-variable, four-CNF-clause XOR gates;
- 378 AND gates, each certified by one ternary plus two binary clauses;
- 378 OR gates, each certified by one ternary plus two binary clauses.

Every gate output has a larger variable index than its two inputs, so the
circuit can be evaluated in increasing gate-output order. Its source is a
bounded topologically ordered gate encoding; arbitrary variable-permutation
invariance is NOT established for this extractor.

The original CNF also contains 32 single-literal output constraints. These
account for **all 8,868 clauses**:
1642*4 + (378+378)*3 + 32 = 8868.

Precisely 32 independent primary-input variables remain. The earlier pure
GF(2) rank analysis found 1,642 independent XOR rows; adjoining the 32
output units remained GF(2)-consistent with rank 1,674. That is why the
standalone XOR-only module could not certify UNSAT: the residual AND/OR
gate constraints are non-linear in GF(2).

The source-reconstructed Boolean circuit is evaluated 64 candidate input
assignments at a time with 64-bit Boolean words. This native bit-sliced search
is exhaustive over a bounded 32-bit input domain, **not CDCL**. This is
exponential enumeration in the input count, not polynomial general SAT.

A satisfying input found locally was:

    unsigned 32-bit primary input = 896596199 = 0x3570F8E7

Forward evaluation generated a **complete model of all 2,430 original
variables**. A separate independent checker which imports neither the gate
producer nor the search implementation verified every one of the 8,868
original input clauses. The independently validated local model SHA-256 was:

cd274c27ce06cf6d2e6a48efdc93c29f889c65f587a350a1e5f5f865faa5a4c4

This is a SAT witness, so it requires neither DRAT nor VeriPB UNSAT proof.
Rechecking the full original CNF is sufficient to verify the claimed SAT
status.

## Reproduction

The ATLAS20 branch includes an independent proof-checking boundary.

    python3 research/atlas17_probe/freeze.py
    python3 research/atlas20_circuit/run.py --cnf atlas17_original_inputs/xor-shift-2026.cnf --out atlas20_test
    python3 research/atlas20_circuit/check_model.py --cnf atlas17_original_inputs/xor-shift-2026.cnf --model atlas20_test/full_model.dimacs --output atlas20_test/replay.json

For the source-frozen CI test and paired reference runs use
.github/workflows/atlas20-xorshift-sat.yml.

The source-model verification process reads all original CNF clauses and
requires exactly one truth value for every source variable. No reported SAT
status is accepted solely on the basis of the source-specific gate evaluator.

## Limits and significance

The demonstrated advance is **structural dimensionality reduction** from a
2,430-variable fully defined gate encoding to 32 primary inputs, followed by
bounded bit-parallel enumeration and complete-model checking. This does not
mean generic CDCL algorithms must explore 2^2430 assignments, nor does it
prove a superior asymptotic SAT algorithm.

The 32-input enumeration is finite and feasible for this source. A larger
input domain could be intractable. The method is specialized and not currently
renaming invariant. It should be tested prospectively on source-disjoint
circuit encodings, with equal CPU and end-to-end budgets, complete SAT witness
verification, explicit UNKNOWN outcomes, and no automatic main promotion.
