# YM27 — validated continuation in coupling space

Research derivation building on YM24–26; independent mathematical
review remains necessary. Scope: finite open cubic or periodic L>=4
lattices in spatial d=2,3,4; no regulator removal.

## Joint spin-sector budget

Retain YM25's norm and bilinear constant b=8/3, and YM26's linear
bound ||2B(F1,.)||<=ell*x with ell=320/3, x=q|k|/alpha,
q=2(d-1). For adjacent plaquettes, the spin-zero and spin-one
projections P0,P1 of Wp Wq have total Fourier trace norm <=256:
the original tensor coefficient has trace norm <=256, and the
two blocks arise by unitary decomposition and contractive pinching.
P0=Wmerged/2 has trace norm <=32. The F2 costs per unit trace norm
are (9/2)*3/3=9/2 and (13/2)*4/13=2 respectively. Hence the joint
cost is <=2*256+(9/2-2)*32=592, not the previous separate sum 656.
No lower estimate of either trace norm is required. With the
same self and incidence estimates as YM25, write
||B(F1,F1)||<=c*x^2, c=[324/q+2368(1-1/q)]/9.

## Continuation of the exact solution, not a guessed vacuum

Write F(x)=F1(x)+X(x), with fixed sign of k along the path. Start
at x0=min(goal,1/160). An anchor radius r>=0 is certified by
(1-ell*x0)r-b*r^2>=c*x0^2 and 1-ell*x0-2br>0. The
preconditioned contraction of YM26 constructs the actual solution.

Suppose ||X(x)||<=r is already proved. Put y=x+delta and seek
X(y)=X(x)+Y. Subtract the exact fixed-point equations:
(I-2B(F1(y)+X(x),.))Y
 = (B(F1(y),F1(y))-B(F1(x),F1(x)))
   +2B(F1(y)-F1(x),X(x))+B(Y,Y).

The right side before its quadratic part has norm at most
eta=c(y^2-x^2)+ell*delta*r. The inverse is bounded by 1/p for
p=1-ell*y-2br>0. A radius s proves the next step if
p*s-b*s^2>=eta and p>2bs. Thus ||X(y)||<=r+s and the actual
new linearization inverse is bounded by 1/(1-ell*y-2b(r+s)).
This proves an existential continuation of the actual solutions;
the actual coefficients of X(x) are not computed by this task.
The Hessian estimate of YM26 gives gap>=alpha*(1/2-4(x+r)/3)
at each certified endpoint with positive RHS.

The native routine searches for the smallest admissible rational
radius on a 1e-8 grid by integer binary search. It starts each
step at delta<=1/10000, halves it on failure, and stops at the
budget or endpoint. The independent auditor does NOT replay the
search: it verifies every supplied rational radius and transition
against the above inequalities and exact source hash.
There is no guarantee of success for all goal couplings. The
scalar estimate still loses invertibility near its discriminant
barrier; a failure says nothing about the actual spectrum.

Input p op gauge-vacuum-path D ALPHA K GAMMA MAX_NODES.
The certificate is for the analytic sufficient inequalities,
not proof assistant validation of the Fourier/curvature premises.
No ATLAS invocation or full-lattice coefficient generator here.
No weak-coupling continuation, infinite-volume construction,
or continuum mass-gap solution is claimed.
