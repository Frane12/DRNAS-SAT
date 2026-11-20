# DRNAS MATH-HYBRID10 — source-audited weighted Hall subset cuts

**Research status:** isolated experiment. The method is a sound
necessary-condition recognizer on source-backed BDD and exact-one CNF.
New structural UNSAT outcomes are NOT independently VeriPB-proved
until a separate proof compiler emits source-valid clauses.
No general P=NP/P=coNP or polynomial CNF complexity claim.

## Theorem H10: subset-demand residual capacity cut

In a source CNF, let G be disjoint exact-one job groups checked
against their original positive and pairwise negative clauses.
Every group g has a positive integer weight lambda_g.
Every source-checked machine BDD j has a local state frontier
F_j after the first i groups have been decided, with unselected
BDD variables existentially projected as in HYBRID7/8.

For any subset S of groups still requiring assignments, define

  D_i(S) = sum_{g in S, g>=i} lambda_g

and let U_j(F_j,i,S) upper-bound the weight of future selected
selectors from S which machine j could set true on any
source-BDD-accepted completion, including all skipped untested
selectors optimistically.

**THEOREM H10.** If
    sum_j U_j(F_j,i,S) < D_i(S)
for ANY group subset S, the current global product state has
no source-CNF satisfying completion and may be discarded.

PROOF. A satisfying CNF extension sets exactly one variable
from each remaining group. Consequently groups in S
contribute D_i(S) across all machines. By source-backed
BDD soundness, the contribution on each machine cannot
exceed U_j(F_j,i,S). Summing gives the opposite inequality.
QED.

This generalizes the full-demand H9 inequality (S=all
remaining groups). It is a weighted form of a Hall-style
restriction: groups eligible for too few machines cannot
be assigned elsewhere. The independent upper maxima are
optimistic, so missing other CNF constraints cannot cause
a false UNSAT verdict.

## Candidate generation

Searching all 2^n group subsets would recreate the
exponential problem. The current implementation generates
a bounded deterministic collection using the machine-class
eligibility signatures of each group:

- every distinct eligible-machine-class mask M;
- every pairwise union M1 union M2;
- for each such M include all groups whose eligible-class
  set is a subset of M.

Duplicate and vacuous candidates are discarded, and at
most 96 candidates are retained. Failing to include a
useful set only reduces completeness, NEVER soundness.

Each candidate gets its own source-verified BDD suffix
capacity DP with zero weights outside the subset; the
weights must be positive on included groups. A product
state is removed only when an exact integer strict
capacity contradiction is established.

For a FIXED number of machines, a bounded candidate
family and supplied BDDs this adds polynomial work to
HYBRID8/HYBRID9. This does not bound the size of the
source BDD or the quotient state graph in arbitrary CNF
size, and does not resolve the NP-complete exact-cover
problem in general.

## A nontrivial synthetic test

Ten machines, each accepting at most one job; ten
exact-one job groups. The first seven groups can go to
any machine, the final three are eligible ONLY for the
first two machines. Ordinary root capacity is ten,
equal to total demand ten. Therefore the full H9
weighted root cut cannot certify UNSAT.

Choose S={7,8,9}. The two eligible machines can accept
at most two jobs, whereas three groups must be covered:

    D(S)=3 > C(S)=2.

H10 detects this at the initial product state (one state).

A SAT-POSSIBLE negative control instead restricts only
the final TWO groups to those two machines, making all ten
jobs schedulable. The root Hall bound is tight. H10
must never return UNSAT; its conditional cuts should
prune early choices that fill restricted machines with
flexible jobs. The source-backed H8 solver is a baseline.

Source SHA tampering and invalid group weights are rejected.
A few already verified original PCMAX witnesses are retested
only for regression, NOT as new real-world solves.

## Proof-system status and next step

This experiment emits only a structural cut certificate.
To claim a new RUP/VeriPB result for its Hall synthetic,
the inequality must be expanded into source-CNF-derived
machine bounds or a independently checked proof.
A short mathematical proof alone is not a substitute.

Next step: compile source-verified local weighted
subset bounds into standard VeriPB inequalities and
test on frozen prospective, family-disjoint CNFs where
ordinary root capacity cannot already prove UNSAT.


## Verified GitHub evidence — 20 November 2026

GitHub Actions:
https://github.com/Frane12/DRNAS-SAT/actions/runs/44713058817

All source-level checks and SAT-safe tests passed. The **same untouched
generated source CNF** has SHA256

    a0a88d2f80a5500e882604e2fc3de3a1bac629d209363dc628e6a212e001d409

and contains **272 variables and 662 original clauses**. The selected
restricted-job subset consists of 3 exact-one groups, 6 selectors,
two eligible capacity-one machines and eight other machines.
The capacity structural checker verifies demand 3 and
machine bounds (1,1,0,0,0,0,0,0,0,0), summing to 2.

The existing source-based weighted PB compiler generated a 5742-byte
VeriPB 3.0 proof with 38 state lemmas and 113 cutting-planes steps
(emitter accounting). An independent VeriPB 3.0.2 invocation returned
the exact line

    s VERIFIED UNSATISFIABLE

against this **original generated source CNF**, without rewriting
the DIMACS input for validation. This is a standard proof of UNSAT
for the new SYNTHETIC Hall instance, NOT a previously unseen real
PCMAX benchmark or a new standard proof for any archived original.

The simultaneously checked SAT-possible counterpart has only
two restricted jobs. On this case the baseline symmetry product
visits 27 states, while the Hall-enhanced product visits 11
and discards 7 branches using conditional capacity cuts.
Both return UNKNOWN rather than a false UNSAT.

Additional original-CNF regression checks 00, 05, 09, 14 preserve
their already-known weighted source capacities and UNSAT results.
The experiment does not establish new correctness or speed
against Kissat/CaDiCaL on unseen benchmarks, nor solve
the worst-case exponential state-space problem.

**Next proof research:** standard-proof compilation of dynamically
derived Hall cuts on cases where the *root* Hall condition is
insufficient; then prospective blind family-disjoint validation.
