# YM30 — distinguish coercivity from collective soft modes

This is a deliberately restricted nonperturbative structural diagnostic,
not a Yang-Mills Hamiltonian. Input is a real sparse symmetric matrix A
with nonpositive off-diagonal entries and nonnegative row sums. Recover
w_ij=-A_ij and p_i=sum_j A_ij. The exact quadratic form is

    v^T A v = sum_edges w_ij (v_i-v_j)^2 + sum_i p_i v_i^2.

No ground-state energy, perturbation expansion, or family label is used.
For a harmonic oscillator network with unit masses and stiffness A,
the positive normal-mode frequencies are sqrt(eigenvalues of A).
A zero eigenvalue is a zero-frequency mode (an unconfined free coordinate
does not have a normalizable oscillator ground state).

## Two independent mathematical directions

Lower: for every vertex i select a path to an anchor r with p_r>0.
Weighted Cauchy-Schwarz along the telescoping identity for v_i gives
v_i^2 <= R_i [p_r v_r^2 + sum_path w_e (v_a-v_b)^2],
where R_i=1/p_r+sum_path 1/w_e. Sum over i. If K is the maximum
load (sum of R_i over uses) of any edge or anchor term, then
A >= I/K. This is a uniform result whenever the load is uniformly
bounded, not merely when all local springs are positive.

Upper: a nonzero trial vector v supplies lambda_min<=v^T A v/||v||^2.
Distance from anchored vertices produces a collective ramp; an
unanchored component produces an exact zero mode. The verifier
recomputes the Rayleigh quotient from the original matrix entries.

The pinned ATLAS30 solver chooses one predecessor on a shortest path
to an anchor, by a CNF whose model is checked independently. The
lower certificate stores all paths; independent audit reconstructs
weighted loads. Upper certificates do not require ATLAS. The solver
may return UNKNOWN if neither test meets the requested cut; no
false conclusion is drawn. The exact rational prototype is Python,
and small lower examples are separately checked using the existing
native CORE PSD routine and its independent characteristic audit.

## Analytic scaling control

Consider unit-weight paths of even length N=2m, with m unit anchors.
Spread: anchor every other vertex. Every unanchored vertex has a
one-edge path to an anchor. Each anchor has at most two such paths;
its load is <=1+2*2=5, each path edge load <=2. Thus lambda_min>=1/5
for all N and oscillator gap>=1/sqrt(5).

Clustered: anchor the first m consecutive vertices. Set the anchored
part to zero and the unanchored tail to v_j=j, j=1,...,m. The
energy is m and the squared norm m(m+1)(2m+1)/6. Thus
lambda_min<=6/[(m+1)(2m+1)] -> 0. The oscillator frequency upper
bound is the square root of this expression. The number and strength
of local terms match, but anchor coverage differs. This is a rigorous
family result, not extrapolation from finite tests.

Prepared paired cases use permuted variable labels, same operator
format, no family label in input, fixed rational targets and size
sweep. Also weighted, grid and disconnected controls. They are
designed synthetic families, not a blind external benchmark or a
general autonomous discovery claim.

## Transfer question, not a solved transfer

Yang-Mills ground-state transformed quadratic forms have vector-valued
derivatives and an unknown correlated measure. The anchor inequality
does not transfer automatically. A candidate analogue would need
a measure-dependent conditional variance/Dirichlet comparison that
covers all gauge-invariant collective observables, including large
Wilson-loop combinations, with physical-scale constants. Establish
the corresponding lower bound independently of an assumed mass gap,
and use variational upper witnesses to falsify bad candidate
inequalities. This experiment cannot establish such a bound.
