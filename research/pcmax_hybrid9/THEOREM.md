# DRNAS MATH-HYBRID9 — source-bound weighted cuts inside a BDD symmetry quotient

**Experimental, retrospective.** The method is sound for the source-checked
PCMAX/BDD family. It does not imply P=NP or P=coNP and it does not promise
polynomial complexity in the size of arbitrary CNFs.

## Theorem H9 (sound remaining-demand bound)

Let exact-one source-CNF clauses define disjoint selected groups G.
Each selected group g has positive integer proof weight lambda_g.
Let the machine BDD transition clauses, roots and true/false terminal
units be independently source-verified as in HYBRID7/HYBRID8.
Let R_i be the remaining selected groups after the first i groups have
been assigned, and let D_i=sum_{g in R_i} lambda_g.

For any reachable HYBRID8 quotient state S at level i, let
U_j(S,i) be a VALID UPPER BOUND on the remaining weighted
selectors which machine j could set true along any accepted
completion of its local, source-backed BDD (the current local
frontier may have multiple possible states).

**Theorem H9.** If sum_j U_j(S,i) < D_i, no satisfying assignment of the
original CNF can extend the quotient state S. Consequently the state
may be discarded.

Proof: In any satisfying extension, every remaining selected group
is assigned to exactly one machine and contributes lambda_g to the
global total, giving exactly D_i. Each source-backed local BDD
forces an accepted path. The weighted contribution of each
machine along that path is <= U_j(S,i) by the construction of the
optimistic local bound. Summing yields D_i <= sum_j U_j(S,i), which
contradicts the proposed strict inequality. QED.

## How the integer upper bound is computed

For each class of canonically isomorphic BDDs, use one representative
with its original selector order. Assign variable weight lambda_g to
each selected selector belonging to group g, and zero weight to
auxiliary selectors. For each canonical BDD state q calculate B(q),
the maximum total selected weight on ANY accepting suffix, including
all selected selector positions skipped by edges. Set B(true)=0,
B(false)=-infinity and propagate maxima backwards on the DAG.

For a quotient local frontier F at level i, calculate

  U(F,i)=max_{q in F} [B(q) +
       sum(weight of selected variables at positions before q,
           with group_index >= i)].

The second term is necessary: a BDD can skip a selected group entirely;
its value is then *unconstrained by that BDD edge*. Assuming all such
unprocessed skipped selectors are true produces a safe upper bound.
Already-processed groups contribute no remaining demand and are
not counted. Auxiliary selectors have weight zero. A class multiset
with k copies of local frontier F contributes at most k*U(F,i).

All additions and comparisons use exact Python integers. The checker
reads all exact-one clauses and BDD implications from the original CNF
and verifies the SHA-256, group partition and canonical isomorphisms
before permitting a cut.

## What a result means

- UNSAT_SOURCE_WEIGHTED_ROOT_CUT: the original source-based
  weighted-capacity theorem already proves UNSAT at level zero.
  This is a valid re-derivation of known PCMAX certificates, NOT a
  new discovery or superiority claim.
- UNSAT_SOURCE_WEIGHTED_SYMMETRY_PRODUCT: root bound did not
  separate; after product transitions, unreachable or upper-bound
  violating quotient states were eliminated. Valid structural
  UNSAT for this checked source-backed family.
- UNKNOWN_ABSTRACT_COMPATIBLE: the quotient admits projected
  assignments but other CNF clauses may block them. Never SAT.
- UNKNOWN_RESOURCE_LIMIT: no verdict, cap respected.

This prototype emits NO NEW VeriPB/RUP proof; the old original
PCMAX evidence already contains independently accepted VeriPB proofs.
To claim externally checked hybrid proofs one must implement a
source-level proof compiler that emits the weighted cuts themselves.

## Retrospective protocol

The experiment regenerates simple synthetics and checks SAT controls,
and runs against all 11 ARCHIVED original PCMAX source CNFs for which
weighted2 already produced externally accepted proofs. For each
original, it independently calculates the root capacity and compares
it to the existing source-checked machine capacities and demand.

Because these 11 cases are already known UNSAT with weighted witnesses,
they provide an integration check rather than a blind test of new
reasoning. All eleven produced an immediate root cut; no generalization
to new instances is established by this result. The next useful experiment needs source-frozen
new cases where the root gap is non-positive but conditional cuts can
eliminate product states without proof leakage.

## Complexity barrier

This is an upper-bound pruning method, not a general polynomial SAT
algorithm. The number of BDD nodes and reachable quotient multisets
can be exponential in the original CNF input size or number of
machines. Detecting the right structure and weights can also be hard.
Constant-size BDD classes are a limited, structured tractable regime.


## Verified implementation results (20 November 2026)

GitHub Actions:
https://github.com/Frane12/DRNAS-SAT/actions/runs/44711793978

The original archived source-CNF/check-capacity checker and the
new independent class-wise weighted BDD DP agreed EXACTLY on
the combined machine bound in all 11 frozen cases:

| Case | Weighted demand D | Machine capacity C | States examined |
|---|---:|---:|---:|
| 00 | 16 | 15 | 1 |
| 02 | 105 | 104 | 1 |
| 03 | 10000 | 9945 | 1 |
| 04 | 10000 | 9971 | 1 |
| 05 | 31 | 30 | 1 |
| 07 | 1002 | 997 | 1 |
| 08 | 9996 | 9895 | 1 |
| 09 | 1002 | 988 | 1 |
| 10 | 42 | 41 | 1 |
| 14 | 10001 | 9927 | 1 |
| 15 | 998 | 990 | 1 |

The old proofs were already independently accepted by VeriPB 3.0.2,
and this test rechecked their source-backed structural certificates.
NO NEW standard proof file was emitted by HYBRID9.

Additional synthetic source-backed controls:
- 10 machines capacity 1, 11 jobs: immediate root cut
  with capacity 10 < demand 11 (one state rather than 11 in HYBRID8).
- Same 10 machines, 10 jobs: returns UNKNOWN_ABSTRACT_COMPATIBLE.
- HYBRID5 UNSAT: 19 states, root weighted bound = demand, so
  UNSAT from the product (not a root cut).
- Fano UNSAT: 11 states and 1 conditional capacity cut, versus
  12 states in the HYBRID8 reference.
- HYBRID5 and Fano SAT controls: both UNKNOWN without false UNSAT.
- Source-edge tampering and zero/invalid weights: rejected.

The Fano reduction 12 to 11 states is a valid but small
practical gain, not a claim of asymptotic superiority.
The main remaining challenge is to find source-frozen
nontrivial formulas where the root does NOT separate but
conditional weighted cuts noticeably shrink the state space.
