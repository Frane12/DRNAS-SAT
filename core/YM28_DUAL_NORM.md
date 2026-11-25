# YM28 — break the previous norm barrier by a two-norm bootstrap

Research derivation, requires independent mathematical review. Uses the
YM24–27 SU(2) Fourier framework on finite open cubic or periodic L>=4
grids in spatial dimensions 2–4, at fixed lattice spacing.
Let q=2(d-1), u=|k|/alpha, x=q u, C=-Delta, and F1=(k/3alpha) sum Wp.

## Separate contraction and regularity

For mean-zero invariant Fourier functions define two norms
N0(F)=max_e sum_{j:e in S_j} E_j ||A_j||_1,
N1(F)=max_e sum_{j:e in S_j} E_j J_j ||A_j||_1.
E_j=sum j_e(j_e+1), J_j=sum j_e. The Fourier coefficients absorb
dimension factors as before. The weak norm N0 suffices for existence
by Banach contraction. The stronger N1 controls the Hessian.
For B=C^-1 P(grad F dot grad G), the same charged-edge argument,
now with no J weight, gives N0(B)<=b N0(F)N0(G), b=8/3.
Using J_out<=J_in1+J_in2 and the identical support charging argument
with each summand separately gives
N1(B)<=b[N1(F)N0(G)+N0(F)N1(G)].
The multiplication and derivative estimates follow from unitary
Clebsch-Gordan decomposition, trace-norm pinching, and
j_e<=2 j_e(j_e+1)/3; see YM24. Each finite graph has complete
weighted Fourier l1 spaces. The weak contraction is not asserted in N1.

The plaquette-specific linear map L=2B(F1,.), with no extra J factor,
has N0(LG)<=ell*x*N0(G), ell=160/3, by the two support charges
3*16*(4/2)*(2/3) and 3*16*(1/2)*(2/3), times 2x/3.
Because the plaquette spin sum is 2, J_out<=J_G+2 gives
N1(LG)<=l[N1(G)+2 N0(G)], l=ell*x.

The second-order defect D=B(F1,F1) is explicit (YM22).
In N0 the self coefficient costs at most 81 per t^2.
For adjacent plaquettes the spin-zero block costs 3/2 per unit
trace norm, and spin-one block 1/2. The joint norm <=256 and
spin-zero norm <=32 imply pair cost <=160.
In N1 the corresponding costs are 324 and 592 (YM27).
Thus N_i(D)<=eta_i=c_i*x^2, where
c0=[81/q+640(1-1/q)]/9 and c1=[324/q+2368(1-1/q)]/9.

## Weak fixed point, then strong regularity

Write F=F1+X and iterate X_{n+1}=D+L X_n+B(X_n,X_n), X_0=0.
A weak radius r0 is valid if eta0+l*r0+b*r0^2<=r0 and
beta=l+2b*r0<1. Therefore the iterates converge in N0.
All finite iterates are Fourier polynomials. The mixed estimate gives
N1(X_{n+1})<=eta1+2*l*r0+beta*N1(X_n).
Consequently they are uniformly bounded in N1 by
r1=(eta1+2*l*r0)/(1-beta). Coefficient convergence in N0 and
Fatou's lemma on the countable nonnegative norm sum give N1(X)<=r1
for the actual limit. In each finite graph N1 is sufficient for
uniform convergence of second derivatives, as in YM24; hence this
limit is C^2 and solves the original log-vacuum equation, with
smoothness following from elliptic regularity. Reality and gauge
invariance are preserved at each iterate. No truncation or numerical
wavefunction is required in this analytic argument.

Direct Wilson Hessian control and the N1 remainder estimate give
Hess F <= (2/3)(x+r1)g. The weighted ground-state transform and
Bakry-Emery criterion then yield the original KS gap at least
alpha*[1/2-4(x+r1)/3] when positive, uniformly in finite volume.
Also the linearization at the exact F has inverse in N0 bounded by
1/(1-beta); this is NOT an inverse bound in N1.

For d=3, x=1/85 (u=1/340), exact rational radii give a lower
gap >0.1474 alpha. YM27's stronger-norm estimate cannot reach this
ratio. The improvement is a sufficient bound, not a physical phase
boundary. The weak contraction can itself fail at larger coupling,
and curvature positivity can fail even before contraction fails.
Neither failure proves a physical gap closure.

## Implementation and scope

Input p op gauge-dual-norm D ALPHA K GAMMA. Native CORE searches
rational weak radii; independent audit checks the two inequalities,
curvature and source hash, without replaying the radius search.
The analytic premises are not proof-assistant formalized.
No full lattice coefficient generator, ATLAS execution, continuum
construction, or weak-coupling solution is claimed. The next
mathematical obligation is to exploit the inverse of the weighted
ground-state generator with a local norm estimate that is not based
on perturbative Neumann smallness. Positivity in weighted L2 alone
does not establish that locality estimate.
