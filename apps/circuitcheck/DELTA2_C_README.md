# DRNAS CircuitCheck DELTA2-C — one-step and block induction

**Autor istraživanja:** Frane Drnas  
**Branch:** `experiment/circuitcheck-delta2c-inductive-blocks-20261124`  
`main` unchanged.

## Question

Can we prove an N-step CRC/LFSR-style source loop from **one
formally checked step**, small **K-step blocks** and an **induction
argument**, instead of synthesizing all N repeated gates?

For one affine step:

`s_(k+1) = A s_k XOR B x_k XOR c`, all over GF(2).

For any K:

`s_(k+K) = A^K s_k XOR Σ_(j=0)^(K-1) A^(K-1-j) B x_(k+j) XOR c_K`.

Induction invariant: for all k from 0 to N, the original RTL loop
state after k iterations equals the k-fold composition of the extracted
step. Base: the source initializes the state literal. Step: the small
source grammar's loop body has exactly the same semantics on *every*
iteration, and the synthesized one-step gate law matches it. The
composition is independently replayed.

**No specific feedback taps or CRC polynomial are hardcoded into the
general affine algebra.**

## What was implemented

- `delta2c_source_guard.py`: independent **fail-closed** parser and
  source-to-transition semantics for one narrow, explicitly supported
  two-state Verilog loop grammar: reflected-feedback state recurrence
  with one scalar input per iteration and constant initial/final XOR.
  Other syntax is rejected rather than silently treated as equivalent.
  It derives A, B, c directly from a supplied source expression.
- `delta2c.py`: gates the source-derived law against DELTA2-B's
  independently checked Yosys one-step gate coefficients; generates
  raw and matrix-composed K=1, 2, 4, 8 blocks; obtains an independent
  DELTA1 synthesized-gate equivalence certificate for *each* block;
  and derives the N-step output from the compact transition.
- `delta2c_verify.py`: recomputes K-block coefficients by **direct
  symbolic substitution** without importing DELTA2-C matrix code,
  re-verifies each gate certificate and SHA-256, strictly matches
  the raw block's source grammar, and checks the original N-step
  composition and candidate comparison.
- `delta2c_selftest.py`: deterministic 500 independent A/B/c group
  comparisons plus rejected source mutations in 8, 64, 256 and 2048
  input-bit generated RTL.
- `delta2c_baselines.py`: **Kissat and CaDiCaL always-on controls**
  on CNF derived from the same original frozen RTL, plus K-block
  miter CNFs (1, 2, 4, 8 steps).

### Reproduction

After downloading the original SHA-frozen sample Verilog from GitHub
Actions run `45245092918`:

`python3 apps/circuitcheck/delta2c.py --rtl frozen/crc_2048_equal.v --reference reference --candidate candidate --out proof2048`

For an additional expensive original Yosys RTL/gate-level audit:

`python3 apps/circuitcheck/delta2c.py --rtl frozen/crc_2048_equal.v --reference reference --candidate candidate --out proof2048-full --full-rtl-audit`

Independent check:

`python3 apps/circuitcheck/delta2c_verify.py proof2048 frozen/crc_2048_equal.v reference`

## Evidence levels: explicitly separate

1. **Restricted source + local induction:** the special source grammar
   checker is trusted as a definition of this narrow HDL subset.
   The one-step gate proof is independently replayed; every K-block
   is separately checked for any initial register state and any local
   input bits, and the full N-step algebra is recomputed independently.
   This does *not* translate to arbitrary SystemVerilog or four-valued
   simulation semantics.
2. **Optional full original RTL Yosys audit:** additional DELTA1
   verification over the **entire** original RTL vs derived model,
   with separate gate-level certificate replay. This additionally
   depends on correct Yosys synthesis of the original source and
   is more expensive.
3. **SAT baseline controls:** Kissat and CaDiCaL receive a Yosys
   exported DIMACS *from the same unchanged original RTL*; they do
   **not** receive the same data structure used by DELTA2-C. Each
   solver is limited to **one logical CPU**, 30s per original CNF
   attempt, two repetitions with reversed order; local K-block CNFs
   have a 10s limit. SAT assignments are evaluated against all
   clauses; solver-reported UNSAT lacks independent DRAT/LRAT in this
   study. CNF generation is timed separately.

## Scientific limits

- The RTL syntax checker is narrow and specifically accepts one
  reflected-feedback loop form; general variable renaming of that
  grammar is allowed but other recurrence grammars are NOT covered.
- Proof uses two-valued synthesized combinational semantics; no
  FPGA clocks, four-valued X/Z, sequential state-machine properties,
  property checking, vendor mapping/timing, or general formal
  signoff is claimed.
- The 1/2/4/8 gate proofs provide **additional local crosschecks**.
  The induction step for arbitrary N depends primarily on correct
  complete source grammar recognition and the independently verified
  one-step mapping, not on extrapolating from just four tested Ks.
- No novelty or performance claim beyond the actual measured
  restricted workload. This does not establish a universal SAT
  advantage, nor a P-versus-NP result.
