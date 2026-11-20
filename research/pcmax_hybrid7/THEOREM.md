# DRNAS MATH-HYBRID7 — sparse-group product on archived PCMAX CNFs

**Research status:** An isolated, source-clause-audited attempt to transfer
HYBRID6 from toy equal-choice exact covers to original published
PCMAX scheduling CNFs. This is a retrospective transfer audit, NOT a
prospectively selected blind holdout and NOT a general SAT method.

## Why HYBRID6 alone cannot operate on original PCMAX m14

The archived m14 certificate has 14 machines, 20 selected job
groups, 193 selected variables, 260 total local machine selectors
and thus 67 auxiliary selectors. Each selected group permits
only 6--12 of the 14 machines, not one selector per machine.
The source-checked ordered BDDs admit auxiliary selectors
unrelated to the chosen groups. HYBRID6 assumed all groups
had exactly one selector on each machine and a common order.

## H7 algorithm and soundness

The selected groups must have source clauses proving EXACTLY ONE:
a positive at-least-one clause and all negative pairwise exclusions.
Machine-BDD source implications and root/terminal units are checked
against the byte-identical original CNF. Each selected literal must
appear on exactly one machine. For a given machine, the restricted
order of selected group selectors must be monotonically increasing,
while some groups may be absent and other auxiliary selectors
may appear between selected-group selectors.

Before each selected group, compute a non-deterministic ε-closure
of local BDD states over arbitrary auxiliary selector branches.
On assigning the next selected group to one of its permitted
machines, advance each machine BDD on its own corresponding
selected selector (true at the chosen machine and false on
every other eligible machine). All other machine paths are
existentially overapproximated, and duplicate local state sets
and global state tuples are merged.

**Theorem H7 (soundness).** If every projected product frontier
becomes empty, the original source CNF is UNSAT.

Proof: Any satisfying assignment gives exactly one true selector
per chosen group. Each source-backed machine BDD must follow
a path ending in its true terminal. Its actual auxiliary selector
values choose one branch inside the existential closure, so its
states are retained by induction through every selected group.
A satisfying assignment cannot disappear from all product states.
An empty projected product is therefore a contradiction.

The contrapositive does not hold: a surviving projected state
does NOT imply SAT, because local auxiliary choices across
machines and the other source CNF clauses may be incompatible.
For this reason the recognizer never announces SAT. It returns
UNKNOWN_ABSTRACT_COMPATIBLE. State/time limits return
UNKNOWN_RESOURCE_LIMIT; unsupported/invalid source evidence is
rejected, not optimistically interpreted.

## Limitations

- Product state tuples can still grow exponentially.
- ε-closure may create exponentially many subsets of BDD nodes.
- Selected group ordering must be monotone per machine. General
  BDD reordering may be exponentially expensive.
- When UNSAT is found, this implementation currently produces a
  SOURCE-STRUCTURAL certificate, **not an externally accepted RUP
  or VeriPB proof**. Old original m14 weighted proofs are a
  separate existing proof route.
- No fresh real holdout, standard solver comparison or general
  P=NP/P=coNP conclusion follows from this archive test.

## Reproduce

    python3 research/pcmax_hybrid7/test.py

The script rechecks original SHA and weighted source-capacity proofs
on all eleven PCMAX archival cases, then runs a capped new sparse
symbolic product. It also exercises auxiliary selectors, unavailable
machines, HYBRID5 and Fano UNSAT/SAT controls, extra source clauses,
and malicious input digests. The CI artifact contains per-original
outcomes and honest UNKNOWN statuses.

    python3 research/pcmax_hybrid7/sparse.py \
      --cnf evidence/pcmax-weighted2/05/original.cnf \
      --certificate evidence/pcmax-weighted2/05/capacity.json \
      --max-states 1000 --max-seconds 3

**Important:** These eleven original UNSAT cases are already known
UNSAT and VeriPB verified from previous weighted certificates.
Any result here is method-transfer evidence, not a new UNSAT
discovery and not prospective generalization.
