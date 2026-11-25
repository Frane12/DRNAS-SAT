# YM20 — local gauge forests and uniform electric form comparison

Partition an open d-dimensional Cartesian grid into boxes of side at
most b. Choose a tree in each box and fix its links to identity. There
remains one independent gauge action per root, not merely a global action.
A retained oriented edge e=(u,v) has X_e=P_u U_e P_v^{-1}, with P_u
the path from the root of u's box. Haar invariance gives a unitary
identification of physical spaces, with independent root constraints.
Wilson words retain every nonforest edge in the original orientation.

For an original tree edge, its electric derivative row contains +L for
each retained source endpoint and -R for each retained target endpoint
below that edge in its own tree. For a retained edge it contains only L.
As in YM18 the electric form is alpha times the sum over all original
rows and Lie algebra directions of the squared derivative norms.

Let C=sum over retained edges of their SU(2) Casimirs, and E denote the
transformed electric operator. For each row of width w, Cauchy-Schwarz
gives ||sum D_i f||^2 <= w sum ||D_i f||^2. The left and right Casimir
forms agree, so counting contributions to each retained coordinate
gives alpha C <= E <= alpha K C, where K is the maximum over coordinates
of the sum of row widths over its appearances (including the chord row).
These are quadratic-form inequalities, not a bound on the difference
of interacting Hamiltonian ground energies. They hold on smooth
physical functions and extend by form closure. In fact the comparison
also holds on all smooth functions of the retained coordinates.

Each box has at most B=b^d vertices and degree <=2d. A nonroot subtree
has at most B-1 vertices, so its row has width <=2d(B-1). Each endpoint
of a retained edge contributes on at most B-1 ancestor edges. Hence

    K <= 1+4d(B-1)^2.

Both constants are independent of total L for fixed b,d. The estimate
is conservative; the checked instance-specific K can be smaller.
No representation truncation is used. The proof does not show that
E-C is small; nor does it imply a gap for E+V from a gap for C+V,
because their ground energies need not agree. A uniform positive
magnetic gap or continuum limit does not follow from this comparison.

ATLAS30 selects local forest parents via a verified SAT model. The
independent checker reconstructs paths, all root actions, Wilson
words and K. Existing CORE gauge-gap checks the original finite graph
separately. The analytic form inequality is a mathematical premise
checked combinatorially, not a formal proof assistant derivation.
The fixed-coupling finite volume sweep is a control, not evidence of
a volume-uniform magnetic bound. Next target: compare interacting
block ground energies and boundary couplings with uniform residuals.
