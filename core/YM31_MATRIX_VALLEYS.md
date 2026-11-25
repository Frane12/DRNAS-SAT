# YM31 — transverse quantum energy closes classical SU(2) valleys

This is a finite-dimensional bosonic matrix model (spatially constant
SU(2) reduction when the interaction graph is complete), not the full
lattice or continuum Yang–Mills Hamiltonian. The quantum confinement
mechanism is known in mathematical physics; no novelty claim. See
Barry Simon, Annals of Physics 146 (1983), 209–220,
https://doi.org/10.1016/0003-4916(83)90057-X.

## Exact classical obstruction

Identify SU(2) with unit quaternions (s,u). Direct multiplication gives
1 - Re(U V U^-1 V^-1) = 2 |u cross v|^2.
Thus commuting configurations (collinear imaginary parts) have zero
commutator plaquette energy. In the Lie algebra reduction the potential
sum w_ij |X_i cross X_j|^2 has unbounded flat valleys along collinear X_i.
No classical lower bound by a positive multiple of sum |X_i|^2 exists.
This is not a quantum spectral upper bound.

## Quantum lower bound without perturbation

H = sum a_i (-Delta_i) + sum_edges w_ij |X_i cross X_j|^2,
X_i in R^3, a_i,w_ij>0. For fixed X_i, the X_j variable splits into
one longitudinal direction and two transverse directions. Each
transverse operator -t d^2/dx^2+v |X_i|^2 x^2 has lower bound
sqrt(t v)|X_i| by completing the square. The full conditional form
therefore satisfies

 t (-Delta_j) + v |X_i cross X_j|^2 >= 2 sqrt(t v)|X_i|.

Integrate over X_i; no derivative of the coordinate choice is needed
since only X_j derivatives are used. Allocate kinetic and potential
budgets to directed pairs, preserving at least half the original
kinetic form and never spending any potential coefficient twice.
If each vertex receives positive slope c_i from these inequalities,

 H >= (1/2) sum a_i (-Delta_i) + sum c_i |X_i|.

The comparison form has compact resolvent by local Rellich compactness
and tightness at infinity; hence H has compact resolvent. The
Schrodinger heat semigroup is positivity improving on connected
R^(3n), so its ground state is simple. Thus a positive gap above the
ground state exists for this fixed finite model. Global simultaneous
SO(3) rotations commute with H; the unique positive ground state
is invariant, and restricting to invariant states preserves a positive
lower gap (without specifying its numerical value).
No lower bound on E1-E0 follows merely from the linear confinement
coefficient; do not confuse them.

An isolated vertex instead supplies a free R^3 coordinate and
destroys compact resolvent. The free radial sector is also available
among simultaneous rotation-invariant states. This is a control,
not a statement about a true Yang-Mills spatial gauge constraint.

## ATLAS and independent certificates

Pinned ATLAS chooses one partner for each vertex with incoming
load constraints. Solver allocates at most half of each kinetic
budget and half of each undirected potential per orientation.
For each allocation rational k>0 with k^2<=4tv is an exact
lower slope. Independent auditor checks all budgets, coverage,
source hash and slopes. The Python prototype does not execute
a native CORE spectral solver in this phase. The compactness
and positivity arguments are trusted analytic premises, not
machine-formalized proofs.

## Remaining spatial obstruction

In the full spatial theory F_ij=d_i A_j-d_j A_i+[A_i,A_j].
The commutator square cannot be retained as a separate positive
lower bound on the full curvature square: derivative and commutator
can cancel, including in pure gauge configurations. Local gauge
constraints also differ from the global matrix-model constraint.
Even a spatially extended form with compact resolvent at each
finite size does not prove a uniform excitation gap after subtraction
of extensive ground-state energy. Transfer would need a gauge-invariant
local conditional inequality for the FULL curvature and a comparison
of excitation energies across volume and cutoff. No continuum claim.
