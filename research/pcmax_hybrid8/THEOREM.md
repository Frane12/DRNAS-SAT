# DRNAS MATH-HYBRID8 — symmetry-quotiented machine BDD product

Scope: source-checked experimental exact-cover recognizer, NOT a
general SAT solver and NOT a proof of P=NP/P=coNP.

## 1. Why this experiment follows the ORIGINAL PCMAX transfer

HYBRID7 successfully validated all 11 archived original PCMAX
source CNFs and their sparse group/auxiliary BDD structures.
Nevertheless, with a 1000-state cap, all 11 new product attempts
returned UNKNOWN_RESOURCE_LIMIT after only 4--12 groups.

Some machines have identical SOURCE-BDD transition structures up
to consistent renaming of internal state IDs and machine-private
auxiliary selector IDs, while preserving the selected group IDs.
For example, the original m11 archive has 11 machines but only
six such canonical transition structures.

## 2. Theorem H8: quotient product soundness

Input: exact-one selected job groups (checked from original CNF
positive and pairwise negative clauses), independently checked
machine BDD transition clauses, root/terminal source units,
monotonically ordered selected-group variables per machine.

Normalize each machine DAG recursively, replacing its variable
names with group index g or local auxiliary index a; preserve
low and high child links and the true/false terminals. Two
machines are in the same *structural class* only if their
canonical normalized root DAG and eligible selected-group set
are identical. This is a sufficient, conservative condition
for identical local allowed-language overapproximations.

Within each class, keep a multiset of nondeterministic BDD
frontier sets, NOT a tuple of machine identities. For a chosen
job group g, explore the possible structural class of its
unique selected machine and, within that class, which current
frontier-state type is chosen. Evolve the chosen member with
its g-selector true and all other members with the g-selector
false. Merge identical resulting class multisets. Auxiliary
selectors are existentially projected by BDD epsilon-closure.

**Theorem (soundness).** If this quotient-product frontier becomes
empty, the source CNF is UNSAT.

Proof sketch: Every source satisfying assignment induces a
sequence of unique machine choices for each selected group
(the source clauses force exact-one). Every machine follows
a source-BDD accepted path, and existential auxiliary
projection includes that path. By induction, the assignment
induces a state in HYBRID7's labeled product. Replacing a
labeled collection of machines with a multiset of identical
verified structural local automata preserves the existence
of every possible assignment trace. HYBRID8 explores every
possible choice of a structural class and source frontier
type for the next selected job. Hence every satisfiable trace
is represented in the quotient. An empty quotient implies
no model, contradiction.

**Crucial:** Other CNF clauses may distinguish machine identities
even when their local BDDs are isomorphic. This quotient ignores
those additional clauses, yielding an *overapproximation*.
Therefore a compatible final quotient state cannot certify SAT.
It returns UNKNOWN_ABSTRACT_COMPATIBLE, never a false SAT.

State/time caps return UNKNOWN_RESOURCE_LIMIT. Invalid source
clauses or non-monotone group orders are rejected.

## 3. Complexity and remaining hard part

If there are c structural classes and machine class h has t_h
machines, and the reachable local (projected) frontier-state
universe has Q_h distinct states, the possible multisets for
that class are at most

   binomial(Q_h+t_h-1,t_h).

Thus a crude layer bound is the product of these binomial
values over classes rather than the full labeled product of
individual machine states. This can be a large reduction when
many machines are identical, but can still be exponential
in input size or machine count. The canonical graph itself is
source-checked; the product and symmetry procedure do NOT
guarantee polynomial complexity in arbitrary CNF size.

The current module emits **structural results only**: a
VeriPB proof compiler for general multiset/product-count cuts
is NOT implemented. In particular, it must not present
retrospective archive labels as newly externally verified
outcomes from this method.

## 4. Tests

- 10 identical at-most-one machine BDDs, 11 selected jobs:
  source UNSAT, quotient should need only a few multiset states.
- 10 identical machines, 10 jobs: SAT-possible control MUST
  return UNKNOWN, not UNSAT or SAT.
- Compare HYBRID7 unquotiented explosion with the new quotient.
- Re-check Fano and HYBRID5 UNSAT and SAT controls using
  original-to-the-experiment CNFs.
- Reject corrupted original source SHA and BDD source transitions.
- Run the bounded quotient on six archived, independently
  weighted-VeriPB-proven PCMAX originals. Report UNKNOWN honestly.
- Do not touch main or existing frozen evidence.

## 5. Next

If the symmetry quotient works, it should be coupled with the
independently checked weighted PCMAX bounds to prune high-cost
global states. That hybrid is still a restricted structural
algorithm, and original CNF-size asymptotics remain open.
