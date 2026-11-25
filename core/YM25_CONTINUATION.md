# YM25 — recentered vacuum contraction in a gauge-invariant Fourier norm

Research derivation; independently peer review the analytic premises.
Same Hamiltonian and metric as YM24. Scope: open cubic grids or periodic
grids with side >=4 (no triangles), d=2,3,4; fixed lattice spacing.

## Improved norm

Every nontrivial gauge-invariant Fourier spin tuple has support with no
degree-one vertex: the gauge action at that vertex would be a lone
nontrivial irreducible representation and its invariant projection zero.
The support therefore contains a cycle of length at least four, and
J=sum_e j_e>=2. Use the closed gauge-invariant mean-zero space with norm
max_e sum_{j:e in S_j} E_j J_j ||A_j||_1.
Gauge projection commutes with Fourier tuple projection. Products of
derivatives contracted in the metric, and inverse C on mean-zero
functions, preserve gauge invariance and reality.

For any pair of nonconstant input tuples, J_out<=J_1+J_2<=J_1 J_2.
Consequently the YM24 charged-edge trace-norm argument applies with
weight J instead of 1+J, and bilinear constant b=8/3. The Hessian
bound remains (2/3)||F|| by J j_e <=(2/3) E_j J_j.
The plaquette drive A=C^-1 sum W_p now has norm <=a=32q, q=2(d-1).

## Actual second-order defect of the first iterate

Let u=|k|/alpha and F1=(k/alpha)A. The defect of F1 in the fixed-point
equation is B(F1,F1). Use the explicit YM22 formula (t=k/(3alpha)).
For the self term -(W_p^2-1)/8, the four spin-one edges give E=8,
J=4 and Fourier trace norm <=3^4=81 (trace expansion). Cost <=324 t^2.
For a pair sharing one edge write P0=W_merged/2 and P1=W_p W_q-P0.
These are the spin-zero and spin-one projections on the shared edge.
The six other links carry spin half. The P0 cost from coefficient
1/3 is <=(9/2)*3*32/3=144, and the P1 cost from coefficient -1/13
is <=(13/2)*4*256/13=512, using the contractive Fourier block
projection of W_p W_q. Their sum is <=656 t^2.
At most q self terms and 4q(q-1) pair terms have support touching
any given link (for periodic grids side>=4, elementary plaquette
pairs share at most one link). Hence defect eta<=c u^2, where
c=(324q+656*4q(q-1))/9 <= (2624/9)q^2.

## Recentered contraction

Seek F=F1+X with ||X||<=r=10q u. The correction map is
X -> B(F1,F1)+2B(F1,X)+B(X,X).
Its norm on this ball is <=eta+2b a u r+b r^2.
For q u<=1/240 this is <=r, since
(2624/9+2*(8/3)*32*10+(8/3)*100)/240 < 10.
The Lipschitz constant <=2b(32+10)q u<=14/15<1.
At u=0 the zero solution is immediate. Picard starting at X=0 has
tail after n iterations <=eta L^n/(1-L), with L=224q u.
This controls hypothetical exact Picard iterates; the full lattice
coefficient generator has NOT yet been implemented. It is not a
claim that the Taylor series converges outside the earlier radius.

The solution has ||F||<=42q u. The same ground-state transform and
Bakry-Emery argument as YM24 gives the ORIGINAL KS Hamiltonian
gap >= alpha(1/2-56q u) >= 4alpha/15. All bounds are independent of
volume; no spin cutoff. This improves the sufficient ratio from
1/(576q) to 1/(240q), a factor 12/5. No novelty claim.

## What is still blocking the continuum

In the convention alpha=g^2/(2a), k=2/(ag^2), the ratio u=4/(g^2)^2.
For d=3 this certificate requires g^2 >= sqrt(3840), whereas the
asymptotically free trajectory has g^2 tending to zero. The bound
does not approach this limit and cannot establish a physical gap.
For further continuation about a computed approximate F*, let
eta=||lambda A+B(F*,F*)-F*|| and suppose a bounded inverse M of
I-2B(F*,.) is available, with norm <=m. Then a Newton correction
map is contractive if m eta+m b r^2<=r and 2m b r<1.
A volume-uniform inverse estimate beyond the small-norm regime
and an appropriate weighted Poincare bound are the next obligations.
These are conditional criteria, not established weak-coupling results.

Input p op gauge-vacuum-continue D ALPHA K GAMMA STEPS.
CORE audits rational constants; proof assumptions are not machine
formalized. Existing YM22 quaternion controls are reused; no separate
ATLAS execution because this step is analytic, not CNF planning.
