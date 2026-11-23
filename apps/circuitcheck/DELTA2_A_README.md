# DRNAS DELTA2-A — automatic structural discovery on CRC RTL

**Research author:** Frane Drnas  
**Branch:** `experiment/circuitcheck-delta2-transition`  
**Important:** Experimental, proof-first research; `main` unchanged.

## What is automatically detected

The frontend inspects the *reference Verilog module* without knowing the name
"CRC", its feedback polynomial, or the number of iterations in advance.
Within a **strict supported RTL subset** it:

1. Finds a single static, ascending combinational `for` loop.
2. Identifies the multi-bit variable feeding back into itself across steps.
3. Determines the primary-input vector and loop-indexed input bit.
4. Infers the cutpoints **between iterations in the RTL**, and abstracts one
   iteration as a new one-step Verilog module (`drnas_delta2_step.v`).
5. Synthesizes this step with Yosys and derives exact GF(2) affine equations
   for every next-state bit, reporting A, B and c in
   `s_(k+1) = A*s_k XOR B*x_k XOR c`.
6. Independently replays the step and final-output gate-netlist proofs, then
   composes the inferred law over the original number of iterations.
7. Synthesizes the independently supplied RTL candidate, checks its affine
   coefficients, and reports whether the *derived model* matches.
8. With `--full-rtl-audit`, also generates a Verilog parallel model and runs
   **the existing DELTA1 original-reference-vs-generated-model equivalence
   checker** on the original reference RTL, with an independent certificate
   replay. This last guard is mandatory for an original-RTL-comparison claim.

For the frozen generated CRC-32 design, the feedback law is identified as
`SHIFT_RIGHT_FEEDBACK` and the feedback tap mask reconstructed from the
**synthesized one-step circuit** is `0xEDB88320`. The detector does not embed
this number. The frozen experimental controls check it after the fact.

## Reproduction

`python3 apps/circuitcheck/delta2_auto.py --rtl frozen/crc_2048_equal.v --reference reference --candidate candidate --out results/delta2_2048_eq --full-rtl-audit`

`python3 apps/circuitcheck/delta2_auto.py --rtl frozen/crc_2048_fault.v --reference reference --candidate candidate --out results/delta2_2048_fault --full-rtl-audit`

The reference RTL files above are available as GitHub Actions artifacts in
run `45245092918`, generated from pinned sources in
`apps/circuitcheck/stress_generate.py`. The original file must be supplied;
the tool will not infer the truth from an instance label.

**Outputs:** `drnas_delta2_step.v`, `drnas_delta2_finish.v`,
`drnas_delta2_model.v`, local synthesized `*.json` netlists,
`cert_*/delta1_certificate.json` and independent replay records,
`full_original_audit/` with the full RTL/reference-model gate proof,
`delta2_model.json` and `delta2_report.json`.

## Mandatory caveats

- Stage cuts are **inferred from RTL loop structure**, not discovered from an
  arbitrary already-flattened gate graph. Other HDL representations, nested
  loops, conditional per-step transitions, more than one loop-carried vector,
  extra output assignments, variable loop bounds, or nonlinear stage gates
  return **UNKNOWN** rather than receiving a fabricated linear proof.
- The restricted RTL-to-one-step parser is part of the trusted extraction
  boundary. With `--full-rtl-audit`, its *result* is independently compared
  to the original RTL **as synthesized by Yosys**, mitigating a mistaken
  extraction. Yosys source translation itself is still trusted.
- The proof is exact for two-state synthesized combinational netlists. This
  is **not** DRAT/LRAT/VeriPB on the SAT tool's original CNF, not a general
  sequential FPGA verification workflow, not vendor timing signoff, and not
  general polynomial-time SAT.
- The current CRC examples are deterministic **generated engineering
  workloads**, not third-party source projects. Times from separate CI runs
  need repetition before speed-up factors are asserted.
- `DELTA2-A` discovers the transition law; optimizing the entire synthesis
  and certificate pipeline is a separate subsequent objective.

## Tested instances (first GitHub CI study)

- 8, 64, 256, 2048 input-bit **loop-boundary unit tests**; automatically
  rejects an artificial step law that depends on the loop index.
- Random GF(2) transition-composition algebra tests.
- 2048-bit equal and deliberately faulty original CRC: end-to-end Yosys
  netlist full-reference-vs-derived-model proof replay.

Inspect the CI run itself for any later test results, including failures.
