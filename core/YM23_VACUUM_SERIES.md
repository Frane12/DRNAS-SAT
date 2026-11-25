# YM23 — automatic all-order log-vacuum correction and convergence

General finite graph, formal identity only: put lambda=k/alpha, F=sum
lambda^n f_n and choose f_n to have zero Haar mean. With C=-Delta,
C f_1=sum W_p and C f_n=P sum_(i+j=n) grad f_i dot grad f_j for n>=2,
where P subtracts Haar mean. Products of finite Peter-Weyl polynomials
and inversion on nonconstant representations are well-defined at each
finite order. A nonzero gradient contraction requires overlapping link
support. This does not yet furnish a volume-independent convergence
bound or an implementation of general spin-network recoupling.

## Implemented single-cycle specialization

On a single simple cycle of length l, after gauge fixing, the physical
space consists of class functions on SU(2). Use x=Tr(U)/2 and the unit
S^3 radial Laplacian D=(1-x^2)d^2/dx^2-3x d/dx. The original cycle
Hamiltonian, including all representations, is H=e(-D)-2k x with
e=alpha*l/4. Work also on the full unit S^3 for the curvature estimate.
Let lambda=k/e. For v=F' (constant of F irrelevant), the exact equation
is v=T[2lambda x+(1-x^2)v^2], T=d/dx (-D)^(-1)P, with P subtracting
Haar mean. The recurrence is v_1=2/3 and
v_n=T[(1-x^2)sum_(i+j=n) v_i v_j].
The solver constructs rational coefficients by descending monomial
degree, and the independent auditor checks the differential equation
order by order rather than using that inversion algorithm.

## Convergence proof (not just numerical evidence)

Use the Banach algebra of power series with norm ||g||_2=sum |g_j|2^j.
For the monomial x^m, m>=1, the polynomial solution of -D f=x^m-mean
has nonnegative nonconstant coefficients, by descending degree:
f_m=1/[m(m+2)] and all lower terms are induced by the positive
m(m-1) contribution. Thus f' has nonnegative coefficients, degree
<=m-1, and 3f'(1)=1-mean(x^m)<=1 (mean is nonnegative by symmetry).
It follows ||T x^m||_2<=2^(m-1)/3, and T annihilates constants.
By density T extends with norm <=1/6. The algebra is closed under
multiplication and ||1-x^2||_2=5.

On the ball ||v||_2<=1/4, the map has norm at most
2|lambda|/3+5||v||_2^2/6 <=1/4 for |lambda|<=19/64, and Lipschitz
constant <=5/12. Banach's theorem gives the unique fixed point
in this ball. The formal series coefficients are majorized by the
Catalan recurrence a_1=2/3, a_n=(5/6)sum a_i a_j, so
||v_n||_2 <=(2/3)(20/9)^(n-1). For q=(20/9)|lambda|<1,
the derivative truncation tail is bounded by (2/3)|lambda| q^N/(1-q).
Convergence of the coefficient series on the stated interval gives
the fixed point (the scalar Catalan majorant's smaller root is <=1/4).
Analyticity around [-1,1] justifies the differential equation,
including the endpoints. The integrated F yields an everywhere
positive ground state exp(F), after normalization. The eigenvalue
is the constant left by P; the ground-state transform proves it
is the actual unique ground state, not an auxiliary parent model.

On unit S^3, Ric=2g, Hess x=-x g and |grad x|<=1.
The norm bound gives sup|v|<=1/4 and sup|v'|<=1/8
(using m/2^m<=1/2 for integers m>=1). Hence Hess F<=3g/8.
The weighted curvature Ric-2Hess F>=5g/4 implies the original
single-cycle Hamiltonian gap >=5e/4, also after restricting to
class functions. The metric here is unit radius, with e=alpha*l/4
absorbing the Casimir normalization. Standard weighted Poincare
criterion: Cheng/Thalmaier, JFA 274 (2018), introduction.
This analytic proof is a trusted premise, not proof-assistant formalization.

Input JSON: electric, ratio, target as rational strings and order
1..24. The Python CORE research prototype emits a source-bound
coefficient certificate and checks it independently. Native CORE
ks-loop-gap is cross-checked separately on the same physical cycle.
ATLAS is not executed in this test: the recurrence is algebraic and
does not need a CNF planner. No claim that ATLAS discovered the proof.
The finite graph generalization needs a local support norm with
a volume-uniform nonlinear inverse estimate; no continuum claim.
