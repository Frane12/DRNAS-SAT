# DRNAS REAL3 — multi-project, no-known-SHA GF(2) parity class discovery

**Author:** Frane Drnas  
**Branch:** experiment/real3-unseen-rtl-parity-20261124  
**Main:** unchanged.

## Research goal

Automatically identify algebraic structure in **previously unseen external FPGA
RTL projects** and prove useful results without falling back to the full CDCL
search on every formula.

REAL2 proved a narrowly defined shared-mask XOR identity inside one pinned
public module. REAL3 removes the known-module-name and known-source-SHA
condition from the **recognizer**. For now it accepts two explicitly defined
complete-source two-state grammatical forms:

1. Single-output combinational even/odd reduction parity, with a
   compile-time selector and a variable-width payload.
2. Chunked combinational parity *plus* parity-error checking, including
   nonuniform last-chunk width and a dynamic even/odd control bit.

A complete unknown source that does not match one accepted grammar returns
UNKNOWN, without claiming an UNSAT proof, inventing a witness or silently
falling back to CDCL. Sequential UART reset/clock logic is a negative control.

This is grammar-based discovery with a narrow pattern vocabulary, **not yet
a generic Verilog AST engine or arbitrary SAT structural understanding**.

## Three independent original source projects

Unmodified source bytes are frozen by original public Git commit, Git blob
SHA-1, SHA-256 and full name, but the detector is never given these IDs.

- [UART parity generator, code002-nova/uart-systemverilog](https://github.com/code002-nova/uart-systemverilog/blob/106e1eb3f21aea962b1b5645fcfe7fea2e594f50/rtl/common/parity_gen.sv), MIT
- [Even parity generator, Supreethm2004/Basics-of-Verilog-Coding](https://github.com/Supreethm2004/Basics-of-Verilog-Coding/blob/aedfd3c6de9b653884f242e9a075f7f4428aa69f/even%20parity%20generator.v), MIT
- [Chunked parity/checker, sean-galloway/RTLDesignSherpa](https://github.com/sean-galloway/RTLDesignSherpa/blob/41dee14400747515c92ed5869e76b5ebc6f07284/rtl/common/dataint_parity.sv), MIT
- Negative [Clocked parity_calc, Kholoud-Ebrahim/UART_Protocol](https://github.com/Kholoud-Ebrahim/UART_Protocol/blob/24476deea6829340d68849d983a70c5516a34a69/uart_tx/rtl/parity_calc.v): beyond scope, no verified full-circuit claim

The 9 fixed source configurations are evaluated twice each: correct miter
and deliberately input-dependent fault miter. There are therefore **18 cases**.
The input-dependent fault flips mismatch via input bit 0 rather than forcing
an always-true SAT formula.

## GF(2) representation

For an N-bit vector d,

    even_parity(d) = XOR_i d_i
    odd_parity(d)  = 1 XOR (XOR_i d_i)

For chunk c from lower L_c to upper U_c, and a dynamic even-parity flag t,

    parity[c] = 1 XOR t XOR XOR_{i=L_c..U_c} d_i
    error[c]  = parity[c] XOR received_parity[c]

All output functions are affine over GF(2) and represented as arbitrary-size
integer bit masks: constant in bit 0, coefficients in bit 1..N. No polynomial
or variable number is pre-configured in the detector for any project.

The recognizer requires **the entire active module** to match one of its
explicitly supported forms. Unrecognized statements, widened vector
semantics, altered control-flow or clocked constructs are never silently
interpreted as an affine proof.

## Independent proof boundary and SAT controls

1. REAL3 source-grammar classifier derives the output masks.
2. A separately authored UART/parity mathematical specification is kept
   independent of the source classifier. A separate certificate checker
   replays mask/spec consistency and source SHA-256.
3. Yosys independently translates the ORIGINAL public RTL and a separately
   written mathematical spec into a miter. For expected-equal examples, it
   additionally runs its own combinational SAT verification of mismatch=0.
4. The exact same Yosys-exported CNF goes to **Kissat and CaDiCaL**,
   one CPU per attempt, two repeats with reversed order and 15s timeout.
   CNF generation time is reported separately.
5. SAT witnesses are checked against every clause of the DIMACS CNF.
   Unless an external proof is supplied, UNSAT statuses from Kissat
   and CaDiCaL are *reported solver verdicts*, not DRAT/LRAT certified.

REAL3 *does not itself receive that same CNF*: speed differences are
end-to-end representation/path comparisons and must not be described as
same-DIMACS improvements over the SAT algorithms.

## Tests and limitations

- Formal fixture freeze:
  GitHub Actions run [45301658957](https://github.com/Frane12/DRNAS-SAT/actions/runs/45301658957)
- 18 initial source grammar cases recognized, including 33/4 and 65/7
  uneven chunk boundaries and variable even/odd control.
- Arbitrary renamings of module, input, output and parameter identifiers
  leave the discovered coefficient masks unchanged.
- Deliberately modified extra assignments, non-XOR expressions, erroneous
  compare operators and clocked UART are not accepted as the old theorem.
- No inference of sequential behavior, third-party protocol conformance,
  independent CRC mathematical specifications, four-state X/Z behavior,
  FPGA LUT/timing/power measurements, or general P-vs-NP conclusions.
- Currently only two explicitly supported source grammar families;
  a generalized AST/RTLIL pattern matcher with independent language-level
  checking and wider families is the next genuine research milestone.

## Files

- real3_classifier.py — independent-of-repository source grammar recognition.
- real3_freeze.py — upstream public exact commit and immutable corpus.
- real3_harness.py — separately authored external parity specification.
- real3_smoke.py — rename and mutation tests.
- real3_bench.py — original RTL → Yosys CNF → Kissat/CaDiCaL control.
- real3_replay.py — independently checks coefficients against specification.
- real3_audit.py — final complete cohort audit, retaining all UNKNOWN results.
- .github/workflows/drnas-real3-smoke.yml
- .github/workflows/drnas-real3-bench.yml

**Research rule:** fallback to CDCL remains a diagnostic research-gap signal,
not a successful final mathematical structural solution.
