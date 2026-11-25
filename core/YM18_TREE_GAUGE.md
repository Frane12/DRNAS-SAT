# YM18 — maximal-tree loop coordinates, including mixed electric operators

For a connected finite graph choose a rooted spanning tree T. Orient its
edges away from the root; orient the remaining links arbitrarily. Write
P_v for the ordered product along the root-to-v tree path. The chord
variable X_e=P_u U_e P_v^{-1}, e=(u,v), transforms by simultaneous
conjugation at the root. Normalized Haar measure gives a unitary
identification of the physical link Hilbert space with L2(SU(2)^r)
invariant under simultaneous conjugation, r=E-V+1. This follows by
iterated Haar-preserving changes of variables, or by fixing all tree
links to the identity. There is no representation truncation.

For a closed Wilson path, take its cyclic word of oriented chord
variables with tree links replaced by identity. Its trace is unchanged.

For a Lie algebra generator X_a normalized to give Casimir j(j+1),
define L_{c,a} f as differentiation of f(exp(t X_a) U_c) and R_{c,a}
as differentiation of f(U_c exp(t X_a)). At the tree-gauge section,
varying a chord gives L_{c,a}; varying a tree link oriented toward
child v changes all chord coordinates whose source/target lies below v:
the differential is
D_{e,a}=sum_{source below v} L_{c,a} - sum_{target below v} R_{c,a}.
Indeed, varying the tree link by exp(t X_a) acts by these left and
right multiplications for all t on the section. Hence the electric
Casimir is -sum_a D_{e,a}^2, including all cross terms, not merely
the sum of chord Casimirs. This holds on smooth invariant functions,
and the unitary identification transfers the self-adjoint operator.
The full reduced operator uses those squares plus the Wilson words.
The remaining global gauge constraint must not be discarded.

This is a known maximal-tree gauge construction, not a new theorem:
Mathur and Sreeraj, Phys. Rev. D 92, 125018 (2015),
https://doi.org/10.1103/PhysRevD.92.125018 ;
Grabowska, Kane and Bauer, Phys. Rev. D 111, 114516 (2025),
https://arxiv.org/abs/2409.10610 .

ATLAS30 receives a CNF selecting one parent per nonroot vertex from
the preceding BFS level. A separately checked SAT assignment yields
a spanning tree. The verifier reconstructs paths, Wilson words and
each signed electric row independently. The tests also compare
Wilson traces and finite group actions using exact rational unit
quaternions at the gauge section, and reject tampered electric rows.
CORE gauge-gap still certifies the original graph bound; the new
structural audit is not a numerical solution of the reduced operator.
BFS-tree selection is not a claim of optimal locality or compression.

The transformation removes redundant gauge coordinates, not physical
degrees of freedom. Mixed electric interactions can be nonlocal and
grow with volume. This is not Wilsonian renormalization, and there
is no new uniform weak-coupling or continuum mass-gap claim.
