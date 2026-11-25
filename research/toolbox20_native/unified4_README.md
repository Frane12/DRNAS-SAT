# UNIFIED4 — compositional conditional reasoning

This isolated native C++20 experiment preserves the UNIFIED3 path and adds a new tail only if it returns UNKNOWN with enough time. It reads the original CNF and its own previously emitted proof; the original proof parents remain available. No CDCL, external reference call, formula name or truth label is supplied to the candidate.

## New capability

- Compose conditional derivations: for a fixed outer context C, examine each polarity of a chosen symbol x by running the existing bounded conditional closure under C AND x and C AND NOT x. If one child context is impossible, its proof supplies the opposite guarded literal. If both derive the same literal q, resolve their guarded implications to infer C => q. These are proof-producing bounded nested lookahead operations, not a complete or polynomial-time algorithm. No recursive global assignment search or CDCL conflict analysis is used.
- Rank candidate symbols by propagation impact inside the current context. Rotate the less productive tail of the ordering across epochs.
- Versioned context agenda over empty, single-symbol and selected connected pair contexts. Revisit after a new shared consequence or a new rank policy. Prioritize new root units.
- Keep the explicit limits: at most 512 variables and 12,000 original clauses; bounded proof lines, local trials, child pivots and six epochs; one CPU and the caller deadline. A remaining UNKNOWN is legitimate. The new tail does not attempt to construct SAT models, and it may have little time left after earlier stages.

## Test protocol

Directly exercise the new inference layer on a complete three-variable forbidden cube (old shallow closure must fail), a guarded version of the same contradiction, a SAT negative control and 64 randomly generated tiny contexts. Exhaustive semantic verification plus independent RUP replay of all emitted kernel clauses. Then run the inherited 160-case exhaustive oracle.

Paired 10 s, one-logical-CPU comparison: frozen UNIFIED3, UNIFIED4, Kissat, CaDiCaL. 160 exact prior cases, including all three old misses, and 50 prospective synthetic cases: 40 uniform random 3-SAT across 80–256 variables and eight densities, plus 10 transfer controls from other families. Every generated formula retained, no verdict filtering. Manifest hashes and independently verified answers stored. Replay is development evidence, not fresh holdout. One repetition. Hall/GF2 structural certificates retain existing independent format-specific checks; the new refutations require standard DRAT verification. No automatic promotion; main untouched.
