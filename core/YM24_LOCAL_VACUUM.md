# YM24 — local Fourier norm contraction for the original SU(2) Hamiltonian

Research derivation, requires independent mathematical review. It applies
to finite open cubic lattices, or periodic side >=3, spatial d=2,3,4,
with fixed alpha>0 and sufficiently small |k|/alpha. No continuum claim.

## 1. Representation norm

Use the product of round SU(2) metrics of radius 2, so the electric
operator C=-Delta has Casimir eigenvalues j(j+1), and Ric=1/2 g.
Write a mean-zero Fourier polynomial as sum over nontrivial spin tuples
j=(j_e) of Tr(A_j pi_j(U)), pi_j= tensor_e pi_{j_e}(U_e), using the
dimension factors absorbed in A_j. Let S_j={e:j_e>0}, J_j=sum_e j_e,
E_j=sum_e j_e(j_e+1). Define

    ||F||_* = max_e sum_{j:e in S_j} E_j(1+J_j)||A_j||_1.

Here ||A||_1 is the trace norm. On each finite graph the completion
is a Banach space (equivalent to a weighted l1 sum; all nontrivial
tuples have nonempty support). It controls the uniform sum of Fourier
coefficients and their first and second derivatives. Constants are
omitted by the projection P which subtracts Haar mean. C inverse
acts on each nontrivial tuple by 1/E_j.

## 2. Bilinear estimate

Define B(F,G)=C^-1 P (grad F dot grad G), with bilinear dot product.
For each unit Lie generator on edge e, ||d pi_j||op<=j_e.
The product of two coefficient functions is a coefficient of their
tensor representation, with trace norm product. Unitary Clebsch-Gordan
decomposition followed by diagonal-block compression and summing
identical irreps has total trace norm <= the original trace norm:
pinching is contractive and the triangle inequality applies.
Every output support is contained in the union of the input supports,
and every output spin l_e<=j_e+k_e. Thus 1+J_l <= (1+J_j)(1+J_k).
The E_l in the output norm cancels the inverse Casimir exactly.

For a fixed output edge r, charge each pair to one or both input
supports containing r. For the first input charged at r, its bound is

  3 sum_{j:r in S_j}(1+J_j)||A_j||_1
    sum_e j_e sum_{k:e in S_k} k_e(1+J_k)||B_k||_1.

There are three Lie generators on each SU(2) link. Since
j_e<= (2/3) j_e(j_e+1) and sum_e j_e<= (2/3) E_j, the inner
sum is <=(2/3)||G||_*, and the full displayed expression is
<= (4/3)||F||_*||G||_*. Adding the symmetric charge proves

    ||B(F,G)||_* <= (8/3)||F||_*||G||_*.

The finite-polynomial estimate extends by continuity. The norm uses
actual representation support, not a label for a connected cluster;
no inverse bound in terms of an assumed cluster size is used.

## 3. Drive, contraction, convergence

Each elementary Wilson trace contains four fundamental factors
on distinct links. Expanding the trace has at most 16 products
of matrix entries (inverted fundamental SU(2) entries are signed
entries of the equivalent representation). Hence its Fourier
trace norm is at most 16; J=2. Each link is in at most q=2(d-1)
plaquettes. For A=C^-1 sum_p W_p the drive satisfies
||A||_* <= a=48q. With lambda=k/alpha, the exact log-vacuum equation is

    F=lambda A+B(F,F).

For R=1/8 and b=8/3 the ball is invariant if
a|lambda|+b R^2<=R, i.e. |lambda|<=1/(576q).
The Lipschitz bound is 2bR=2/3. Banach's fixed point theorem gives
a unique solution in this ball, real and gauge invariant because
the map preserves both symmetries starting from zero.
The coefficients F_n of lambda^n satisfy F_1=A,
F_n=sum_(i+j=n) B(F_i,F_j). Their norms are majorized by
a^n b^(n-1) Catalan_(n-1), bounded by a(4ab)^(n-1).
Writing z=4ab|lambda|<=8/9, the tail after N terms is bounded
by a|lambda| z^N/(1-z). The Catalan sum is the smaller positive
root of y=a|lambda|+by^2 and is <=R on this interval, so the
series equals the Banach solution. This is a bound on all
corrections, not an implementation of the full coefficient generator.

## 4. Curvature and actual gap

For a tangent vector with link speeds v_e, a product geodesic gives
the second derivative of a coefficient bounded by
||A_j||_1 (sum_e j_e |v_e|)^2. Cauchy-Schwarz bounds this by
||A_j||_1 J_j sum_e j_e |v_e|^2. Since
J_j j_e <=(2/3) E_j(1+J_j), summing gives
|Hess F(v,v)| <= (2/3)||F||_* sum_e |v_e|^2.
The same estimate and finite-volume l1 summability justify C^2
regularity by uniform convergence of derivatives along geodesics.
The exact fixed point yields
C F=P[lambda sum W_p+|grad F|^2], so exp(F)>0 is an eigenfunction
of the ORIGINAL H=alpha C-k sum W_p, with constant energy
-alpha times the Haar mean of |grad F|^2 (the Wilson means vanish).
The ground-state transform gives a nonnegative weighted Dirichlet
form after subtracting this energy; connectedness implies a unique
ground state. Elliptic regularity makes the eigenfunction smooth.
The Bakry-Emery Ricci bound for weight exp(2F) is
Ric-2 Hess F >= (1/2-4R/3) g = (1/3)g.
The weighted Poincare inequality therefore gives gap(H)>=alpha/3.
Because the ground state is physical, restriction to the gauge-invariant
subspace cannot reduce the gap above it. Every bound is independent
of number of links. There is no truncation of representations.

Background: Eymard Fourier algebra (trace-norm tensor-product estimate,
derived above); Cheng and Thalmaier, JFA 274 (2018), 959-984,
https://math.uni.lu/thalmaier/PAPERS/2018_JFA_spectral_gap.pdf .
Strong-coupling expansions are established research; no novelty claim.
The derivation is not independently peer reviewed or machine-formalized.

## 5. Scope and CORE contract

Input p op gauge-local-vacuum D ALPHA K GAMMA ORDER. Native and
independent Python auditor check the exact rational sufficient
conditions, contraction factor, curvature gap and majorant tail.
They do not generate the spin-network coefficients on the full
lattice or verify the analytic premises in a proof assistant.
Actual ATLAS forest control checks the separate finite-grid structure.
The gap is an explicit sufficient bound for the original fixed-spacing
finite lattice family, not a construction of the infinite-volume
Hilbert space or continuum theory. The conservative strong-coupling
condition fails when k/alpha grows like g^{-4} on the asymptotically
free continuum trajectory. No Clay solution.
