# YM21 — quantitative volume-uniform interacting parent gap

This is an auxiliary Hamiltonian, NOT the original Kogut-Susskind (KS)
Hamiltonian. On a finite open cubic grid (or periodic side length >=3),
use the product link manifold SU(2)^E, with metric normalized so that
-Casimir Laplacian has eigenvalues j(j+1). SU(2) is a round 3-sphere
of radius 2 in this metric, hence Ric=1/2 times the metric. The
product Ricci tensor has the same lower bound.

Write W_p=Tr U_p, C=-Delta, F=t sum_p W_p, t=k/(3 alpha).
Every plaquette uses four distinct edges and Delta W_p=-3 W_p.
Define

 H_parent=alpha[-Delta+Delta F+|grad F|^2]
         =H_KS+alpha |grad F|^2,
 H_KS=alpha C-k sum_p W_p.

The normalized positive function psi proportional to exp(F) is exactly
annihilated by H_parent. The ground-state transform identifies its
quadratic form with alpha int |grad f|^2 exp(2F) dHaar, and its
ground state is unique since the link manifold is connected.
The vacuum is gauge invariant, as is the whole parent operator.

For a product geodesic with tangent v, each varied link generator has
matrix operator norm |v_e|/2 (also for inverse link factors).
Differentiating a four-factor Wilson trace twice bounds the magnitude
by (1/2)(sum_{e in p}|v_e|)^2 <=2 sum_{e in p}|v_e|^2.
Each link belongs to at most q=2(d-1) plaquettes. Thus
Hess F <= 2 q |t| g. The weighted measure exp(2F) has Bakry-Emery
Ricci lower bound rho=1/2-4q|t|. The Bakry-Emery Poincare inequality
gives gap(H_parent) >= alpha rho when rho>0. Restriction to the
gauge-invariant subspace preserves this lower bound (ground is physical).
This applies uniformly to every finite grid with these local incidences
and includes the full infinite representation spaces.
Reference for the weighted curvature criterion:
Cheng and Thalmaier, J. Functional Analysis 274 (2018), 959-984,
https://math.uni.lu/thalmaier/PAPERS/2018_JFA_spectral_gap.pdf .
The criterion and the analytic derivation are trusted premises, not
a proof-assistant certificate. CORE checks exact arithmetic only.

The difference R=alpha |grad F|^2 is a sum over links, each term
bounded by alpha q^2 t^2, since the derivative of one Wilson trace
along a unit link vector is at most 1. The per-link bound is independent
of volume, but the total bound is extensive. Subtracting R from the
parent Hamiltonian does NOT automatically preserve its uniform gap.
For nonzero k, the parent is generally not the original KS operator.
A stability result that controls this perturbation around the
interacting parent is a separate mathematical obligation. Also the
curvature condition only covers sufficiently small |k|/alpha and
does not follow the weak-coupling continuum trajectory.

Input: p op gauge-parent-gap D ALPHA K GAMMA.
Output: PROVED refers exclusively to H_parent. If the conservative
bound fails the requested target, return UNKNOWN, not a counterexample.
Tests check rational coefficients, sign changes, excessive targets,
local incidence and tampering. ATLAS is not invoked in this arithmetic
certificate; the rule is available for later local-block reasoning.
No claimed new mass-gap theorem or solution of the Clay problem.
