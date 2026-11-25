# UNIFIED3 — discovery of global consequences

This isolated native C++20 candidate preserves the UNIFIED2 path, invoking a new proof-producing discovery tail only on its unresolved formulas, within the same deadline. No CDCL or reference solver call is allowed in the candidate.

## New methods

- Proof-bound working memory: import normalized short clauses from the solver's own emitted DRUP stream and residual. Compact by subsumption, favor short facts, retain original constraints or a stronger entailed subclause. Proof parents are never deleted from the certificate.
- Conditional consistency closure: select small assumption contexts (empty, one literal, and pairs selected using source adjacency and propagation impact). Under a fixed context, test both polarities of another symbol and infer a guarded fact when one polarity is inconsistent or both imply it. Iteratively share consequences within the context. Only impossible pair contexts are committed globally; all emitted facts have explicit local RUP derivations. No recursive global decision tree, conflict analysis, backjumping or branching search for SAT witnesses.
- Discover connected regions of up to twelve variables from the original clause hypergraph. Compute the exact local relation table, project its allowed patterns onto one to three boundary variables, and prove any new forbidden pattern by local case resolution. Region enumeration is bounded, not a global SAT enumeration.
- Revisit conditional closure after regional facts and compact between methods. Explicit limits: 512 variables, 12,000 original clauses, up to 18,000 active clauses at entry to a method, 260,000 new proof lines, finite five-epoch escalation, single CPU and the caller's deadline. UNKNOWN remains a legitimate outcome.

The mechanism is heuristic in choosing regions and contexts; only the deductions are exact. It is not a completeness or polynomial-time claim. Random 3-SAT may remain unresolved.

## Validation

Four direct kernel tests with independent RUP prefix replay and exhaustive local truth audit. 160 exhaustive small CNF checks. Paired single-logical-CPU 10-second experiment against frozen UNIFIED2, Kissat, and CaDiCaL: 110 exact replays of the previous corpus, including all eight prior UNSAT misses, and 50 new generated instances (30 uniform random 3-SAT across sizes and densities, 20 other-family transfer controls). No selection by SAT status. Replay is development evidence, not holdout. Independent model and DRAT verification; inherited structural Hall/GF2 certificates retain their independent format-specific checks. The fresh corpus is synthetic, not a real industrial holdout. One repetition is a pilot. No automatic promotion or main modification.
