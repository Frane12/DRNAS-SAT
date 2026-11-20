# DRNAS MATH-HYBRID6 — Source-checked synchronous BDD product

**Scope:** Structural and executable improvement to the DRNAS exact-cover
recognizer. This DOES eliminate the explicit enumeration of all 2^n
local assignments for already-supplied, source-checked, *aligned*
ordered machine BDDs. This does NOT establish polynomial-time SAT
decisions in the size of arbitrary source CNFs: BDDs themselves can
be exponentially larger than the input. No P=NP or P=coNP claim.

## 1. Theorem: sound product construction

Let F be a source CNF, and let G_0,...,G_(n-1) be pairwise disjoint
exact-one groups each of size m, with the clauses

   OR_{j=0}^{m-1} x_(i,j)
   and   (not x_(i,j)) OR (not x_(i,k)) for j!=k

present verbatim in F. Let B_j be a CNF-backed *ordered* machine
BDD with one selector x_(i,j) at group position i, checked against
source implications

   not q OR x_(i,j) OR low(q)
   not q OR not x_(i,j) OR high(q)

and with source-unit true root and accepted true terminal, and
source-unit false terminal. The selector orders must agree on the
common group indices i=0,..,n-1. Skipped selectors are allowed.

At layer i keep only tuples of BDD nodes (q_0,..,q_(m-1))
reachable by choosing exactly one machine for each of the first
i groups. For each tuple and a machine choice j:

- on BDD k at a node that tests group i, follow high when k=j,
  low otherwise;
- on BDD k at a node testing a later group, retain its node
  (the current group was skipped by that BDD);
- terminals retain their state.

Discard successor tuples that contain any machine's false
terminal. Merge equal product tuples (hash-consing). Let R_i
be the remaining set at layer i.

**THEOREM H6.** If R_i is empty at any layer, F is UNSAT.

**Proof.** Suppose a satisfying assignment to F exists. Each
source exact-one group fixes exactly one machine choice.
For each source BDD, the asserted root and checked implication
clauses force the corresponding successor state to true,
including through skipped selector layers. Since the false
terminal has a negative source unit, no chosen successor on
the satisfying run can be false. Inductively, after every
group i the model's product tuple must belong to R_i.
Thus R_i cannot be empty, contradiction. QED.

If a tuple survives all n groups, a complete assignment must
still be tested against *every source clause* before returning
SAT. When extra source clauses block the candidate, report
UNKNOWN rather than SAT or UNSAT (the product is a necessary,
not sufficient, abstraction). When the resource limit is
reached, report UNKNOWN_RESOURCE_LIMIT. Reject unverified
source edge claims and inconsistent variable orders.

## 2. Complexity

Let Q_j be the number of BDD states including terminals,
n the number of group indices and m the number of machines.
There are at most product_j Q_j different tuples per layer.
Each tuple has at most m children, each costing O(m) to
construct naively. Thus the reference implementation has
a conservative time bound

   O(n * m^2 * product_j Q_j)

and space O(n*product_j Q_j) when retaining predecessor
layers to reconstruct a candidate SAT model. A more optimized
implementation can reduce the per-transition constant.
For FIXED m (e.g., m=3), this is polynomial in the sizes
of the SUPPLIED BDDs. For variable m this product is itself
exponential in m; there is no general polynomial-time claim
even in the total BDD size when m is part of the input.

The source-CNF verification overhead is polynomial in CNF
size and supplied BDD encoding, with an added m^2 check
per exact-one group.

**Essential limitation:** source CNFs may not have compact
aligned BDDs. Finding/building them can take exponential time
or space. For arbitrary CNFs a sound recognizer may return
UNKNOWN or exhaust its resource cap.

## 3. Evidence protocol

- Use the previously VeriPB-accepted MATH-HYBRID5 and
  MATH-HYBRID3 Fano *synthetic* CNFs.
- Regenerate exact source bytes, verify every original
  group and BDD source clause without enumerating 2^n
  local assignments.
- Compare UNSAT/SAT verdicts against established proof
  results and explicit SAT controls.
- Add an extra empty source clause to an otherwise SAT
  input, refresh the digest, and require UNKNOWN.
- Tamper with source SHA, selector order and BDD
  implication clauses. The validator must reject them.
- Force a very low state cap and require UNKNOWN.
- Test a new 80-job 3-machine capacity-1 CNF
  (source-backed ordered BDD, UNSAT) and a new 36-job
  capacity-12 SAT control. These are performance and
  soundness probes, not frozen competition holdouts.

## 4. A proof-producing product: Theorem H6-RUP

An additional source-only proof generator is implemented in
`proof.py`. For each source-verified reachable product state
(q_0,...,q_(m-1)) at job index i, process states in reverse job
order, so all live successor states have already been blocked.

For each potential machine choice j, derive by RUP the guarded clause

    (not q_0 OR ... OR not q_(m-1) OR not x_(i,j)).

Under the negation of this clause, all q states are true and
x_(i,j) is true. Source exact-one at-most-one clauses force
every other group selector false. The source BDD edge implications
then force all the child states. If any child is the false
terminal, the negative false-terminal source unit contradicts
the assignment; otherwise the already-derived blocking clause
for the live child tuple contradicts it. Therefore each guard
is valid RUP relative to the original source CNF and earlier
proof steps.

Having derived the m guarded clauses, derive the parent clause

    not q_0 OR ... OR not q_(m-1)

by RUP: under its negation every selector x_(i,j) is forced
false, contradicting the original at-least-one source clause.
Finally, when the root tuple is blocked, the original positive
root units force a contradiction and the empty clause is RUP.

This constructs at most

    (m+1) * sum_i |R_i| + 1

RUP steps, where R_i are the reachable nonfalse joint BDD
states before the first empty layer. For fixed m this
is polynomial in the sizes of the supplied aligned BDDs.
It does NOT imply the BDD can be built in polynomial time
from an arbitrary original CNF.

**Independently checked results (20 Nov 2026):**

| Source family | Product states | Product RUP steps | External VeriPB |
|---|---:|---:|---|
| MATH-HYBRID5, generated 9-job source | 100 | 401 | VERIFIED UNSAT |
| Fano / MATH-HYBRID3, generated 7-job source | 58 | 233 | VERIFIED UNSAT |

Both RUP proofs were accepted directly against the byte-exact
unchanged original-to-the-experiment CNFs by VeriPB 3.0.2.
A separate Python RUP checker checked every line as well.

The existing hand-pruned HYBRID5 proof had 301 steps, so
the general product proof was *longer* on that small case.
The original unpruned Fano proof had 3280 steps, but the
older prefix-pruned Fano proof had only 175 steps. These
numbers measure proof SIZE on fixed synthetic cases, not
the runtime of a standard solver on diverse benchmarks.

GitHub verification run:
https://github.com/Frane12/DRNAS-SAT/actions/runs/44706409863

## 5. Next research obstacle

The unnecessary enumeration of all 2^n local assignments
is removed in this recognized class, **and a generic
source-backed proof compiler is now implemented**.

The remaining hard tasks are:

1. Find/reconstruct small aligned BDD representations from
   arbitrary CNFs with a provable bound in ORIGINAL CNF size.
2. Avoid exponential product growth when the machine count
   m is part of the input, or the source BDDs are large.
3. Measure this automated RUP route on source-frozen
   genuinely unseen real-world CNFs and prove the detector
   does not overfit a hand-picked encoding.
4. Improve proof cost and coverage on structurally mixed
   CNFs while preserving standard external checking.

Existing product-automaton constructions and BDD symbolic
reasoning are well-known; the experiment does not claim to
have discovered their mathematical principles.
