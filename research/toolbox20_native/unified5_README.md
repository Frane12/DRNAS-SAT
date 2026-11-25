# UNIFIED5 — proof-bound mathematical compression

An isolated native C++20 experiment branching directly from successful UNIFIED3. UNIFIED4's unproductive deeper context enumeration is deliberately not included. The new tail activates only on UNKNOWN and only with remaining time.

## New inference mechanisms
- Signed equivalence classes from SCCs of the binary implication graph. Certify both directions in RUP, then replace equivalent variables by canonical representatives.
- Exact subsumption and self-subsuming resolution: shorten constraints and remove redundant ones from working memory; never delete proof parents from the certificate.
- Cost-aware existential elimination: assess actual non-tautological, non-subsumed resolvents on candidate pivots, not just occurrence counts. Commit a complete pivot only if all necessary resolvents fit the current policy. Escalate bounded fill/width policies. Preserve alternate views with short consequences to reduce overcrowding of the working state.
- Small counting invariant: disjoint demand clauses require at least D true literals; a clique cover in the binary mutex graph permits at most K true literals. A detected D>K deficit is refuted with a bounded standard RUP expansion over the demand groups. This is not a general linear-programming engine, and there is no guarantee the greedy cover will find a deficit.
- No CDCL or external solver in the candidate. No formula name, family or truth labels passed to it. New tail is UNSAT-only, up to 512 variables, 12,000 original clauses, finite width/growth limits and a single wall-clock deadline. It does not reconstruct models after its own elimination. UNKNOWN is allowed.

## Validation
68 direct kernel cases (signed equivalences, self-subsuming resolution, exact elimination, capacity, 64 random tiny formulas) with exhaustive semantic checks and independent RUP replay. Inherited 160-case exhaustive oracle. Paired 10-second single-CPU test on 210 exact UNIFIED4 replay inputs, plus 50 fresh synthetic inputs (40 random 3-SAT, 64–256 variables, across eight densities; ten other-family transfer controls). Compare frozen UNIFIED3, UNIFIED5, Kissat and CaDiCaL. Hash all source inputs and independently verify results. All previous cases are replay/development, not fresh holdout. Inherited structural certificate formats remain independently verified; new refutations require DRAT. No main modification, no automatic promotion. One repetition only, not external industrial validation.
