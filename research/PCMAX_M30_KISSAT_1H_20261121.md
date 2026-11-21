# PCMAX m30 · Kissat 3600-second one-core benchmark

- Target: unchanged `evidence/pcmax-weighted2/15/original.cnf`
- SHA256: `7cc73d81dbac7c8680cb7c5f6805e6e4d6aa101e5466771d5ce7aacee78d6472`
- Formula: original PCMAX m30, 14,113 variables and 167,638 clauses.
- Already validated mathematical capacity contradiction: `998 > 990`, with externally accepted VeriPB 3.0.2 proof at `evidence/pcmax-weighted2/15/weighted.pbp`.
- Solver: pinned upstream Kissat 4.0.4, default heuristics, one logical CPU.
- Main comparison: run at most 3600 wall seconds, on original CNF (no transformations and no proof-writing interference).
- Record solver result, exit code, wall/process time, CPU, peak RSS, statistics and version/source pins.
- If UNSAT, optionally rerun with proof output and independently verify DRAT, with separate time budget. An aborted proof rerun does *not* invalidate the measured solver result, but must not count as proof verified.
- An UNSAT result is a solver claim until its own proof is checked; the exact input's UNSAT status already has independent VeriPB evidence.
- No solver outcome should be extrapolated to arbitrary CNFs, and timeouts are not estimates of eventual completion time.

Branch-only experiment, no changes to `main`. Source is provenances and academic benchmarking; do not treat a missing solver result as a failure of logical correctness.
