# YM19 — exact residual-gauge locality and an obstruction

Use the YM18 maximal-tree coordinates. Let G_a=sum_c(L_{c,a}-R_{c,a})
generate simultaneous conjugation. Physical functions satisfy G_a f=0.
For a tree cut with subtree S, D_S,a is the sum of signed endpoint
derivations in S. The complementary row D_Sc,a=G_a-D_S,a. For each fixed
a the endpoint vector fields in these sums commute, so on the common
smooth invariant core D_S,a^2 f = (D_S,a-G_a)^2 f. Therefore replacing
any such squared row by its opposite signed complement preserves the
Hamiltonian on the physical space. The equality is of squared rows on
the invariant core; individual D_S need not preserve the invariant
space for arbitrary a. The magnetic words are unchanged. The equality
extends to the associated self-adjoint realization by the original
unitary coordinate map and core closure.

The implementation independently checks the full signed relation
D_new=D_old-G for a replaced row. Each candidate tree is produced by
the pinned ATLAS30 planner; CORE audits the original finite graph
gap. Choose a candidate minimizing max row width, then cross-pair
count, then total terms. This is a bounded root sweep, not global
optimization over every spanning tree. Row counts are symbolic cost
proxies, not bounds on operator norm.

## An unavoidable growth bound in this representation

For an open d-dimensional L^d Cartesian grid (N=L^d, L>=2), any
spanning tree has a centroid with each component size <=N/2. Since
the maximum degree is 2d, one component has size s>=ceil((N-1)/(2d)).
For any vertex subset S of size s, route every ordered pair from S
to its complement by changing coordinate axes in a fixed order.
A grid edge in direction i at coordinate t can be used by at most
2(t+1)(L-t-1)L^(d-1) <= L^(d+1)/2 ordered pairs. Each crossing pair
uses at least one cut edge, so |boundary S|>=ceil(2s(N-s)/L^(d+1)).
The centroid component cut contains precisely one tree edge; all
other crossing edges are chords. Each crossing chord contributes
one endpoint derivation in either signed row (on each side).
Consequently the largest row, even after complement shortening,
has at least

ceil(2 s0 (N-s0)/L^(d+1))-1, s0=ceil((N-1)/(2d)).

This is Omega(L^(d-1)) for fixed d. It rules out a uniform bound on
these explicit endpoint row widths by choosing a different tree
alone. It does NOT rule out operator cancellations, other coordinate
choices, local block methods, or a uniform mass gap. No claim of
novelty of the graph inequality, and no continuum proof.

Next target: retain local gauge blocks and their boundary variables
rather than one global tree, and control interblock couplings through
relative form bounds.
