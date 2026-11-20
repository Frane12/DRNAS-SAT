# DRNAS MATH-HYBRID3: a mod-3 obstruction invisible to weighted GF(2) capacity cuts

**Status:** Standalone generated CNF, source-checked BDD modular certificate,
source-level RUP proof, and independent VeriPB CI. The source is newly
constructed, NOT an unchanged PCMAX SAT Competition benchmark.
Nothing here implies P=NP or P=coNP. Related modular and hypergraph
reasoning is established mathematics; this experiment claims no novelty
for the Fano plane or divisibility reasoning themselves.

## Instance: Fano-plane exact cover by three local patterns

There are seven jobs indexed 0,...,6, and three machines.
Each job must be assigned to EXACTLY one machine.
Each machine accepts either no jobs or one of the seven lines
of the Fano plane (all indices zero-based):

  {0,1,2}, {0,3,4}, {0,5,6}, {1,3,5},
  {1,4,6}, {2,3,6}, {2,4,5}.

These seven triples are the nonzero vectors of GF(2)^3, written as
points 1,...,7, with a line {a,b,a XOR b}; each point is incident
with exactly three lines and any two lines meet at exactly one point.

CNF F has, for every job i, the at-least-one assignment clause
(x_i,0 OR x_i,1 OR x_i,2) and pairwise negative exclusions.
Each machine's local allowed subsets are represented by an
ordered binary decision tree. For every internal state q testing
selector x with low child l and high child h, actual source clauses
(¬q OR x OR l) and (¬q OR ¬x OR h) are present. A root and
true terminal have positive unit clauses, the false terminal a
negative unit clause. Each asserted root forces an accepting
path for any satisfying assignment. The independent checker
verifies these source implications and enumerates all 2^7
local selector assignments to establish exact allowed languages.

## Theorem H3 (MOD-q soundness)

Let the selected group constraints force exactly one true selector
per group. Choose nonnegative integer group weights w_g and an
integer modulus q>=2. Let R_j be the set of residues modulo q
attainable as sum of selected weights on accepting machine-j
BDD paths. If

    (sum_g w_g mod q) NOT IN R_1 + ... + R_m (mod q),

then the original CNF is UNSAT.

Proof: In a model, each group contributes exactly w_g overall, so
the global residue is sum_g w_g mod q. Each machine follows an
accepting source-enforced path, hence its residue is in R_j.
Adding machine residues must produce the global residue, which
contradicts the displayed condition. QED.

For fixed modulus q and a *supplied* source-checked ordered
BDD, R_j can be computed by a simple dynamic program in
O(q*(number of BDD edges + skipped selector levels)) per machine,
up to bit complexity, and the global residue convolution costs
O(m q^2). This is polynomial in BDD size for fixed q.
It is NOT a polynomial bound in the original arbitrary CNF size:
the BDD and successful recognition may be exponentially expensive.

## Fano mod-3 contradiction

Each machine accepts either 0 or 3 jobs. Consequently each
machine's number of jobs is 0 mod 3, and the global sum
of all machine jobs is 0 mod 3.

The seven disjoint exact-one job groups force seven total jobs:

    7 = 1 (mod 3).

Contradiction. No assignment satisfies F.

This is a short source-backed structural proof; an independent
VeriPB v3 checker also checks a separate source-level refutation.
Our source-level RUP generator uses exhaustive branching on the
three machine choices of seven jobs, so its emitted proof size
is exponential with job count, despite the short mod-3 argument.
Do not confuse short human proof with a polynomial certificate
generation theorem or a short modular-to-VeriPB compilation.

## Strong separation from *all* GF(2)-conditioned weighted bounds

Choose any positive integer (or nonnegative real) job weights w_i,
and any number k of GF(2)-linear support signatures a_i in GF(2)^k.
A model would have global total weight D=sum_i w_i and signature
T=XOR_i a_i.

Pick ANY Fano point p. Exactly three Fano lines pass through p.
Assign these three distinct lines to our three local machines.
Each machine's BDD accepts the chosen local line, so this
three-machine tuple is locally feasible. The point p occurs
three times while every other point occurs exactly once.

Its incidence parity is the all-ones vector because
3 = 1 mod 2. Thus for EVERY choice of GF(2)-linear signatures,
the XOR of these three line signatures equals T. Its total
weight is

    sum_j weight(line_j) = D + 2*w_p >= D.

Therefore any GF(2)-signature-conditioned scalar upper bound
C*(w,a) obtained by taking the maximum over locally accepted
machine configurations with matching global GF(2) signature
necessarily obeys

    C*(w,a) >= D + 2*w_p >= D.

It cannot supply the strict inequality D > C* on this CNF,
even with arbitrarily many GF(2) signatures and arbitrary
nonnegative per-group weights. This is a universal
*restricted-criterion* counterexample, not a lower bound
against CDCL, cutting planes, RUP, VeriPB, or arbitrary SAT
proof systems, all of which may refute it.

Ordinary weighted machine capacity inequalities also cannot
separate. A fractional local mixture assigning each machine
the empty pattern with probability 2/9 and each of the seven
lines with probability 1/9 covers each job with total expected
multiplicity 3*(3/9)=1. A linear weighted sum of any such local
mixture equals total demand D while each local maximum is
at least its average. This shows no strict weighted
capacity gap for nonnegative weights.

## The canonical source-CNF and external certificate

- emit.py creates source.cnf and certificate.json from a fresh
  constructed BDD tree, and for Fano also proof.drup and proof.pbp.
- check.py parses source.cnf independently and checks the SHA,
  every exact-one group clause, BDD transition, terminals,
  disjoint state sets, accepted patterns, mod-3 residue DP,
  and seven independent three-line GF(2) witnesses.
- test.py verifies a positive Fano case, six-job SAT control
  with explicit satisfying CNF model, and rejects deliberately
  corrupted certificates/source bytes.
- The RUP proof emitted by emit.py is a *separate proof route*.
  Its leaves are 3^7 job-to-machine assignments, each excluded
  by RUP against the original generated source CNF. Internal
  clauses combine all three children of the next exact-one
  job group by RUP, ending with the empty clause. Total steps

      sum_{i=0}^7 3^i = 3280.

  VeriPB 3.x must independently accept proof.pbp against
  source.cnf; the checker status in certificate.json is not
  equivalent to official VeriPB acceptance.

## Open: real generalization and complexity

1. Find MOD-q witnesses automatically on frozen unseen real PCMAX CNFs
   and never conflate the newly generated Fano source with those originals.
2. Minimize modular proofs and compile direct MOD-q reasoning to
   standard externally checked proof systems without 3^n DPLL expansion.
3. Find genuinely non-congruential global incompatibilities such as
   hypergraph exact-cover obstructions with feasible modular relaxations.
4. Establish how the recognition, BDD construction and search for
   useful moduli/weights grow in original CNF size, not BDD size.
5. A polynomial-time complete general SAT method is not established.
