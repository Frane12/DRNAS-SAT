# DRNAS REAL2 — proof of shared-mask parity on real external FPGA code

**Research:** Frane Drnas  
**Branch:** `experiment/real2-parity-proof-thirdparty-20261124`  
**Main:** unchanged.

## Exact engineering question

An actual publicly published FPGA IP core, Alex Forencich's
[verilog-lfsr / rtl/lfsr.v](https://github.com/alexforencich/verilog-lfsr/blob/c1f86d036745935f3812ec6ddc7821c70ef4c9de/rtl/lfsr.v),
offers `STYLE="REDUCTION"` and `STYLE="LOOP"`, using the same
`lfsr_mask(index)` function but calculating the output parity in two
different ways. The original source is unmodified, frozen to commit
`c1f86d036745935f3812ec6ddc7821c70ef4c9de` and verified Git
blob SHA1 `e3a472e3f280f3a697dee718b0416f2667181c00`.

**The universal identity:**

`reduction = ^({data_in, state_in} & mask)`

`loop = XOR of every state_in[i] where mask[i] is true, XOR of every data_in[i] where mask[i+LFSR_WIDTH] is true`.

For arbitrary 0/1 values `X_i` and `M_i`, both expressions are
`⊕_i (X_i ∧ M_i)`. The algorithm uses the SAME `lfsr_mask` for
both styles and every output bit. Therefore **both published styles
are equivalent regardless of how the mask is generated**, provided
the recognized source and harness use exactly the asserted grammar.

## Why the observed execution can be so short

REAL1's Yosys full elaboration of some parameterized masks exceeded
120s for CNF export; the old DELTA1 gate-netlist pipeline timed out
at 30s for 10 of 12 examples. REAL2 does **not** compute the actual
LFSR masks, generate the expanded circuit, or perform independent
gate-level comparison. It checks that a known, immutable source
matches a **strict complete pair of implementation templates**;
the proof then applies the universal XOR identity. This is
strong within this specific syntax scope and **not evidence of a
fast general SAT solver**.

The test cases are the **same 12 frozen third-party style comparisons**
from run `45296825639`, each tested twice, comprising CRC16-CCITT,
Ethernet CRC32, CRC32C, PRBS31, a 58-bit-state 64b/66b scrambler
and 128-bit-data CRC32. Six equal and six deliberately faulty
(harness output flips the LSB; upstream source never changes).

A separate verifier, `real2_verify.py`, reconstructs the frozen
harness, checks source and certificate hashes, validates the exact
output relation and replays the binary parity identity by an
independent bitwise algorithm. Adversarial tests require rejection
of changed source logic, parameters, port wiring, output assignment
and certificate verdict. This is **not proof-checking arbitrary
user-supplied Verilog**, not a full syntax tree for general Verilog,
and not formal equivalence to Ethernet/iSCSI CRC protocol specifications.

## Running the pinned external source tests

First obtain the original public RTL artifact from GitHub Actions
REAL1 run `45296825639` (file `real1-pinned-external-rtl`).

`python3 apps/circuitcheck/real2_run.py --external external --out real2-results`

`python3 apps/circuitcheck/real2_tamper.py --external external --out real2-tamper`

GitHub workflow: `drnas-real2-parity.yml`. Output:
`REAL2_RESULTS.json`, `REAL2_REPORT.md` and every proof/replay JSON.

Timing `e2e_seconds` includes source and harness checking plus
a second verifier in the **same Python interpreter**, excluding Python
process startup, CI setup and downloading sources. The old DELTA1
comparison includes Yosys synthesis/verification processes. Their
times are **not apples-to-apples algorithmic performance**.

## Kissat + CaDiCaL controls

The pinned REAL1 results on the original external RTL were imported
from run `45296825639` without rerunning the baseline in the REAL2
source job. These baseline constraints remain visible, including
10 cases where original-CNF export timed out.

The separate workflow `drnas-real2-theorem-sat.yml` freshly runs
Kissat and CaDiCaL on *small symbolic theorem CNFs* for
arbitrary data/mask vectors at 8, 16, 32, 64 and 128 bits,
including intentional SAT faults. These are **different CNFs**
from the original public RTL and cannot be presented as
same-input solver speedups or original-source UNSAT certificates.

## Limitations and next actual research milestone

- The current checker is bound to one vetted public source SHA and a
  narrow pair of syntactic styles. It does not *discover*
  corresponding patterns in unseen arbitrary third-party RTL.
- It does not independently compute/verify the CRC/LFSR polynomial
  or check protocol conformance against an external reference.
- It does not check sequential circuitry. The acquired UART RX and
  SHA-256 examples are explicitly not supported; no fake SAT/UNSAT.
- The algebra proves two-valued parity identity. Source semantics
  of general SystemVerilog, X/Z behavior, vendor implementation,
  physical FPGA LUTs, power and timing remain out of scope.
- Crucial next step: AST-guided structural class recognition on
  different untouched FPGA sources with independent specifications,
  and a trusted external formal equivalence tool (`yosys-eq`,
  `eqy`/`sby` where available) for sound source-to-logic binding.
