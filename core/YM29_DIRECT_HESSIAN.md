# YM29 — direct Hessian control in the contraction norm

Research derivation; independent mathematical review is required.
Scope and normalization as YM28: finite open cubic or periodic L>=4
SU(2) lattices, spatial dimensions 2–4, fixed spacing. No continuum claim.

## 1. The stronger norm is not necessary for C^2 regularity

Use N0(F)=max_e sum_{j:e in S_j} E_j ||A_j||_1 from YM28.
For a product geodesic with tangent v, the second derivative of one
Fourier coefficient satisfies

 |d^2 Tr(A_j pi_j)/dt^2| <= ||A_j||_1 (sum_e j_e |v_e|)^2
 <= ||A_j||_1 E_j sum_{e in S_j}|v_e|^2,

by Cauchy-Schwarz and sum j_e^2<=E_j. Summing and charging each
tangent component to its own edge gives |Hess F(v,v)|<=N0(F)|v|^2.
On each finite graph sum_j E_j ||A_j||_1 <= |E| N0(F), ensuring
uniform convergence of functions and first/second derivatives of
the Fourier series in the finite graph. Mixed Hessian components
follow by polarization. The bound on the Hessian as a quadratic
form is independent of total volume. This is sharper for the
purpose of curvature than the indirect N1 bootstrap of YM28.

## 2. Sharpen the second-order defect

Use x=q|k|/alpha, q=2(d-1), t=k/(3alpha), F1=t sum Wp.
The YM28 weak bilinear bound b=8/3 and linear bound l=(160/3)x
are unchanged. Improve only the adjacent-pair defect estimate.
A Wilson trace of four distinct fundamental links is a Fourier
coefficient with coefficient matrix a cyclic permutation of the
four tensor factors, up to transpose and unitary identifications
of dual fundamental representations. In particular its operator
norm is one. For two adjacent plaquettes, before decomposing the
shared link, the coefficient is a tensor product of two such
unitaries, up to reordering factors. Decompose the shared tensor
product 1/2 tensor 1/2 into spin 0 and 1 by a unitary change of basis.
The spin-1 diagonal block is a compression of a unitary and hence
has operator norm <=1. Its dimension is 3*2^6=192, since six other
links carry spin 1/2. Therefore ||A(P1)||_1<=192, improving the
bound of 256 used in YM28. The spin-zero coefficient P0=Wmerged/2
has trace norm <=32 as before. Weighted N0 defect cost per
adjacent pair is <= (3/2)*32+(1/2)*192=144 (previously 160).
The self-term estimate 81 and pair-incidence bound 4q(q-1)
remain unchanged. Thus eta=N0(D) upper bound is
[(81/q)+576(1-1/q)]x^2/9.

## 3. Actual gap and certificate

Solve X=D+2B(F1,X)+B(X,X) by contraction in N0. A radius r is
sufficient when eta+l*r+b*r^2<=r and beta=l+2*b*r<1.
The direct Hessian estimate above applies to the resulting X.
The explicit Wilson Hessian of F1 is bounded by (2/3)x.
The exact ground-state transform and weighted Ricci/Poincare
criterion of YM24 therefore give

 gap(H_KS) >= alpha*(1/2 - 4*x/3 - 2*r).

This concerns the original finite-lattice Hamiltonian, uniformly
in volume, conditional on the analytic derivation. Native code
uses the existing rational radius search; independent auditor
checks the inequalities, not the search. The analytic premises
and mathematical theorem are not proof-assistant formalized.
The certificate does not compute explicit vacuum coefficients.
For 3D, x=1/77 yields r=4567296/100000000 and a gap bound
greater than 0.3913 alpha. YM28 fails the requested 0.39 alpha
at that coupling.

## 4. Remaining obstruction and spectral inverse route

The scalar sufficient discriminant still requires
(1-l)^2>4*b*eta and l<1 for nonzero coupling. It does not
prove gap closure when it fails. A distinct exact identity
for the actual linearization is
 C(I-2B(F,.))h=P L_F h, L_F=C-2 grad F dot grad,
on mean-zero smooth functions. In the weighted measure exp(2F),
L_F is self-adjoint and has inverse on weighted-mean-zero
functions when the weighted Poincare gap is positive. To solve
(I-2B(F,.))h=g, solve L_F h=Cg-mean_weighted(Cg), then subtract
the Haar mean of h. This identity uses the physical ground-state
transform, not a small Neumann series. It gives an inverse bound
in weighted L2 in terms of the spectral gap; it does NOT give
a volume-uniform inverse in N0 without further estimates.
Obtaining that local resolvent estimate and a nonperturbative
gap remains open. The continuum trajectory requires |k|/alpha
to grow rather than stay in this small interval.

Input p op gauge-direct-hessian D ALPHA K GAMMA.
No novelty claim, no ATLAS invocation, no weak-coupling or
continuum result.
