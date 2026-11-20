# DRNAS MATH-HYBRID2: exact source-BDD k-parity theorem

Status: mathematical derivation and independently executable structural test.
NOT a VeriPB certificate for the at-most-capacity CNF. Not a proof of P=NP.

## Theorem H2: Parity-conditioned capacity

Let F be a source CNF with disjoint, exact-one job groups g and
source-clause-checked ordered machine BDDs partitioning the selectors.
Fix positive integer job weights w_g and k subsets P_0,...,P_(k-1)
of the groups. The k-bit signature a_g records membership of g in
each P_l. A true job selector contributes w_g and a_g.

Let C_j(s) be the maximum total weight of an accepted local machine
BDD path with signature s in GF(2)^k, accounting for all skipped
selector levels. Let D=sum_g w_g and t=XOR_g a_g.

Define C*=max_{s_1 XOR ... XOR s_m=t} sum_j C_j(s_j), with C*=-infinity
when no compatible signature tuple is reachable.

THEOREM. If C*<D then F is UNSAT.

PROOF. Any satisfying assignment chooses exactly one selector per
job group. Its global selected weight is D and the XOR of its
local signatures equals t. The source BDD clauses and asserted
root/terminal units force every local selection onto an accepting
BDD path. Hence its weight is at most C_j(s_j) on machine j.
Summation gives D<=sum_j C_j(s_j)<=C*, contradiction. QED.

With k specified parity supports and an already-verified BDD, local
max-plus dynamic programming has at most 2^k entries per node.
Accounting for skipped selectors takes O(n |E| 2^k) in the simple
implementation; combining machines takes O(m 4^k). Thus constant
k is polynomial in the size of the SUPPLIED BDD; the BDD itself
may grow exponentially in original CNF size. Finding useful
supports is a separate potentially difficult search problem.

## Theorem H2a: Affine saturation

For m identical full-capacity machines, let S be their nonempty
set of attainable k-bit signatures when fully loaded.
Choose s0 in S, let V=span{s XOR s0:s in S} and r=dim(V).

If m>=r, then the m-fold XOR sumset of S equals

    mS = ((m mod 2)*s0) XOR V.

PROOF. Every choice of m signatures is m copies of s0 plus a
sum of differences in V. Conversely any v in V can be written as
an XOR of at most r basis differences d_i=s_i XOR s0.
Select these s_i and fill the remaining m-t machine slots with s0
(t<=r<=m). The XOR is ((m mod 2)*s0) XOR v. QED.

Therefore when m>=r, exclusion of a target signature from mS
has a ONE-DIMENSIONAL linear parity separator: a linear
functional annihilating V and disagreeing on the target coset.
A k-dimensional full-load parity obstruction can then be
compressed into one XOR combination of support sets.

The restriction is essential: for k=3, S={000,001,010,100} has
difference-span rank r=3. With m=2, the target 111 is missing
from 2S even though the affine hull of 2S is all GF(2)^3.
Every nonzero linear projection of target 111 matches a member
of 2S, so no one-dimensional parity can separate. This is a
genuine signature-logic distinction, not evidence of hardness
for arbitrary weighted CNF formulas.

## Our 15-job at-most CNF test

The generated source CNF encodes 15 jobs with durations
[7,8,8,9,10,10,11,11,11,13,13,17,22,23,25] on six machines
of capacity 33. Every job is assigned exactly once. Total demand
D=198, ordinary machine capacity sum=198 (no strict gap).

1D parity support X={1,2,14} (ZERO-BASED indices) yields per-machine
caps (even 33, odd 32) and global bound 197.

Two candidate supports A and B, represented as group-index
bitmasks A=12142 and B=28520, each independently yield bound 198.
Joint 2D caps are {00:33,01:32,10:32,11:33} and target 10,
yielding global bound 197. But A XOR B is exactly X: this
joint example reduces to the one-dimensional parity proof and
MUST NOT be claimed as a stronger irreducible witness.

The executable analyze.py regenerates this NEW CNF from the existing
hybrid1 generator, re-checks the source structure, evaluates BDD
capacities in 2^k signatures, cross-checks local enumeration, tests
the theorem exhaustively on all GF(2)^k subsets with k<=3, and
checks the rank-exceeding example above.

Provenance: generated CNF, NOT the original archived PCMAX m14 CNF.
The m14 original has a separate published 31>30 weighted proof and
VeriPB acceptance; no new parity witness was found for that archive.

## Barriers to P=coNP

- Fixed-k DP being polynomial in BDD SIZE does not imply polynomial
  complexity in the ORIGINAL arbitrary CNF size.
- No completeness theorem covers arbitrary UNSAT 3-CNFs.
- No new VeriPB conversion of the hybrid1 at-most-source proof has
  been independently confirmed.
- GF(2) affine limitations do not solve integrality or arbitrary
  global compatibility; finding a general polynomial complete
  construction would be required for P=NP (equivalently P=coNP).
