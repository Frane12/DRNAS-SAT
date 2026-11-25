# UNIFIED2 — adaptive structural reasoning

This isolated C++20 candidate preserves the UNIFIED1 successful path. Only when UNIFIED1 would return UNKNOWN and the remaining budget and input size permit, it opens a new reasoning stage on the original formula plus provable residual clauses.

- Recover deterministic binary gate truth tables directly from width-2/3 source clauses, canonicalize functions under signed equivalences, transfer equalities between gates. Every equality is admitted only after all local leaf cases pass unit propagation; the proof records the leaf clauses and their resolutions.
- Wider source-independent pair/triple RUP queries, ordered by propagation impact and incidence. There is no recursive assignment search or conflict-driven clause learning.
- Indexed short resolution saturation, with staged width limits and work caps.
- Larger exact existential projections with reconstruction and bounded clause growth. Short entailed residuals can return to the shared state; original clauses are retained for subsequent attempts.
- Reallocate priority by observed new consequences; widen finite budgets even if a round makes no progress. Report UNKNOWN when the finite escalation ladder ends or the resource bound is reached.
- No CDCL fallback or reference solver invocation from the candidate. No external truth labels, family name or instance identity supplied to the solver. Native SAT results are checked against the original input and independently verified; clausal UNSAT uses drat-trim. Inherited GF2/Hall certificates keep their independent format-specific checks. The wider tail is currently limited to at most 2,000 variables, 18,000 original clauses and 24,000 active clauses.

## Evaluation

Three targeted kernel tests and independent RUP prefix replay, then 160 exhaustive small-CNF truth comparisons. A paired 10 s, one-logical-CPU pilot compares frozen UNIFIED1, UNIFIED2, Kissat and CaDiCaL on 50 exact replay cases (including all prior failures), 50 new seeds across the original five generated families and 10 new synthetic reconvergent circuit cases. Replay is development data, never counted as new holdout. All original/fresh inputs are recorded with source hashes. A single repetition is a capability pilot, not an industrial or speed claim. Main is untouched. No automatic promotion.
