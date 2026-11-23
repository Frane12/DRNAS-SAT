# DRNAS CircuitCheck stress 64–2048 (23 Nov 2026)

This study increases **actual RTL primary-input width**, not merely the advertised SAT variable count. It also records the **generated original Yosys DIMACS variable/constraint counts** for every case. Branch: `experiment/circuitcheck-stress64-2048-20261123`, no updates to main.

## Fixed cohort and exact workloads

- CRC-32: 64, 128, 256, 512, 1024, 2048 input bits, output is always 32 bits.
- LFSR scrambler (internal 16-bit register): 64, 128, 256, 512 input bits with one output per step.
- Per width: serial shift-register/reference and independently derived parallel GF(2) candidate; one equal pair, one deliberate XOR fault in output 0.
- **20 original RTL cases × 2 repeats × 3 arms = 120 attempts**.
- SHA-256 on raw RTL and frozen manifest prevents changing sources after seeing outcomes. Repeats rotate solver order.
- One logical CPU per arm, sequential paired runs on each CI shard. Each arm has a 30-second wall cap.
- GitHub Actions uses four independent shards: treat each shard's paired comparisons as matched, not four cores of speedup.

## Three comparisons

1. **DRNAS CircuitCheck:** trusted Yosys translation to a gate netlist; exact GF(2)/ANF proof against the synthesized combinational netlist; **separate implementation replays every accepted netlist certificate**. End-to-end time includes RTL parsing, mapping, ANF and replay. If replay exceeds the cap, result is TIMEOUT, not a verified proof.
2. **Kissat:** frozen source original Yosys miter DIMACS (mismatch forced true), no specially rewritten CNF and no known SAT/UNSAT label hint. Solver time alone is reported. SAT models must satisfy every clause of the original DIMACS. Bare UNSAT solver status is not externally certified.
3. **CaDiCaL:** same original CNF and requirements as Kissat.

**Important:** DRNAS and SAT baselines are **not given the identical representation**: DRNAS operates on the synthesis gate netlist, Kissat/CaDiCaL on a CNF derived from the same source RTL. Thus even a very large runtime gap is an **application-path** gap, not a same-DIMACS speedup of a novel SAT solver. CNF export time and memory are recorded separately and excluded from the solver-only baseline (favorable to the baseline).

## Strict evidence and cost accounting

- Record: source SHA, source width, original DIMACS SHA, raw variable count, raw clause count, CNF export cost, outcome and timeout, wall runtime, max RSS, separate certificate replay, SAT model checks.
- 30-second cap, PAR-2 timeout penalty 60 seconds. A timed-out solver establishes only a lower bound on its unknown full solve runtime.
- If CNF export fails for a large source, mark `CNF_EXPORT_FAILED`, report it and exclude it from head-to-head aggregate; never manufacture solver timings.
- If ANF resources grow too large, say UNKNOWN. If CircuitCheck emits a certificate but replay fails, do not score it as solved.
- A Verilog-to-netlist trust boundary remains. This is not a source-Verilog proof, FPGA signoff, or a measured clock-speed gain.
- This is a **synthetic stress family**, not a prospective third-party RTL holdout nor an industrial workload ranking.

## Reproduce

`python3 apps/circuitcheck/stress_generate.py --out frozen`

`python3 apps/circuitcheck/stress_run.py shard --manifest frozen/manifest.json --out results --shard 0 --shards 4 --kissat /path/to/kissat --cadical /path/to/cadical`

Run under Linux with Python 3.10+, Yosys, time, taskset, Kissat and CaDiCaL. Inspect `results/rows.json` and `*.log`. GitHub workflow `drnas-circuitcheck-stress-2048.yml` freezes sources, runs all arms and attempts strict aggregation in `STRESS_REPORT.md` and `stress-results.json`.
