# DRNAS DELTA1 — Affine-first proof and early-difference detection

Author and research: Frane Drnas. Experimental branch
`experiment/circuitcheck-delta1-affine-20261123`, separate from `main`.

## Research question

What happens if a gate-level equivalence checker **recognizes affine GF(2)
structure as it evaluates the circuit**, rather than first constructing
large algebraic-normal-form polynomial sets on each output?

For inputs `x_0..x_(n-1)`, store each recognized affine signal as:

`F(x) = c XOR (a_0 AND x_0) XOR ... XOR (a_(n-1) AND x_(n-1))`.

Store all coefficients as **one arbitrary-precision integer** with the low
bit as constant. XOR becomes one bitwise operation. AND, OR and MUX are
accepted only when the operands make an affine identity demonstrable;
otherwise the result is **UNKNOWN**, never a guess.

For two outputs, compute `D(x)=F_reference(x) XOR F_candidate(x)`.

- `D=0`: those output bits agree for all 2-state inputs.
- `D≠0`: one bit alone suffices to disprove module equivalence.
  Produce a concrete Boolean input assignment.
- For module equality, **every output must have a full checked proof**.
  Unsupported gates, stateful cells, non-affine expressions, X/Z and failed
  independent replay are not accepted as equivalence.

This is a form of affine dataflow analysis, not a claimed new theorem,
not a general SAT/SMT replacement, and not a polynomial-time solution for
arbitrary Boolean circuits.

## CLI

`python3 apps/circuitcheck/delta1.py --rtl my_design.v --reference reference --candidate candidate --out build/delta1`

`python3 apps/circuitcheck/delta1_verify.py build/delta1`

The first command produces a Yosys-mapped `netlist.json`, `interface.json`,
`delta1_certificate.json`, and `delta1_report.json`. The second program
is independently implemented and reconstructs the affine coefficients in
a different representation (constant bit at the *highest* position), checks
all certified outputs and simulates concrete witness gates.

Exit statuses: `0` equivalent (subject to replay), `10` different (subject
to replay), `2` UNKNOWN/unavailable. Do not publish the first command's
claim without the independent replay result.

## Stress methodology

The workflow `drnas-delta1-affine-stress.yml` retrieves the **20 original
SHA-frozen RTL cases** and source manifest from the previous stress study,
GitHub Actions run `45245092918` (rather than generating a new easier cohort),
and reruns DELTA1 twice per case under a single-logical-CPU 30-second cap
including Yosys synthesis, compact affine evaluation, and replay.

The original CircuitCheck/Kissat/CaDiCaL results are imported unchanged from
audit `45247995613`, with SHA-256 matching the exact same source files. These
baselines were **not re-executed** in the DELTA1 run; CI-machine variability
can affect direct wall-clock comparisons.

**Important scientific limits**:

- DELTA1 receives Yosys gate-level JSON. Kissat and CaDiCaL receive a
  Yosys-generated CNF of the **same source**, not the identical data structure.
  Therefore, any ratios are *application-path comparisons*, not same-DIMACS
  SAT-solver superiority.
- The certificate is exact **relative to the synthesized two-state
  combinational netlist**, with the Yosys RTL translation trusted.
  No standard DRAT/LRAT/VeriPB certificate, arbitrary SystemVerilog assertion,
  formal source-RTL proof or physical FPGA timing signoff is claimed.
- The benchmark is synthetic CRC/LFSR, not blind third-party designs.
- Both correct and intentionally faulty designs, UNKNOWN, TIMEOUT, memory,
  source hashes and all unsuccessful results remain in the final report.
