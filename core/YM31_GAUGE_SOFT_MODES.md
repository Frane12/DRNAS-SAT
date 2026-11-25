# YM31 — gauge reduction alone cannot generate a mass

A diagnostic for the linearized/free gauge Hamiltonian, not a quantum
mass-gap proof or disproof for interacting SU(2). The finite periodic
cubic cochain complex has gradient G (vertex to oriented edge) and
curl C (edge to oriented face), with CG=0. Stiffness K=C^T C.
Pure gauge gradients are in ker C; flat harmonic modes may also be
in ker C. To avoid mistaking either for physical soft modes, construct
a nonzero v=C^T z. It is orthogonal to the entire ker C, and
G^T v=(CG)^T z=0. Its strictly positive Rayleigh quotient bounds the
smallest positive eigenvalue of K from above.

For periodic extent L=4h in x, let an edge field have only a y
component v_y(x)=min(x,L-x)-L/4, replicated in all transverse
coordinates. It has zero mean, and is coexact: choose a face
potential z_xy(x)=-sum_{s=0}^x v_y(s), periodic because the sum
vanishes. Discrete curl has only xy component, a difference of
successive values, with absolute value one. Per transverse slice
the numerator is L and denominator is (4 h^3+2 h)/3. Therefore

   0 < lambda_positive(K) <= 48/(L^2+8).

With unit kinetic coefficient, oscillator frequency is sqrt(lambda).
In physical units with lattice spacing a, the upper bound scales
as O(1/(La)). Thus at increasing physical spatial size, the free
transverse quadratic model has no uniform positive frequency gap.
This construction also works on full cubes, not just the rectangular
scale-sweep tests.

For the SU(2) Wilson magnetic potential expanded around trivial
holonomy, the quadratic term is a copy of this curl form for each
Lie-algebra color; the commutator enters at higher order. At the
classical level, embedding v into one commuting Cartan direction
gives exact link holonomies exp(epsilon v_e T); face products are
exp(epsilon (Cv)_p T) and the Wilson energy is bounded by a constant
times epsilon^2 ||Cv||^2 using 1-cos(s)<=s^2/2. This is an exact
classical potential observation, not a quantum Rayleigh witness
above the interacting vacuum. Local nonabelian Gauss constraints,
quantum kinetic energy, the vacuum measure and color-singlet
projection cannot be replaced by the free transverse calculation.
It neither proves nor disproves an interacting SU(2) mass gap.

CORE research prototype: input sparse signed incidences plus geometry,
without family label or expected answer. The candidate generator
tries triangular face potentials on every pair of axes, then picks
the smallest quotient. The independent verifier ignores geometry,
checks CG=0 face by face, v=C^T z, G^T v=0 and recomputes the
original sparse Rayleigh quotient in rational arithmetic. A failed
target is UNKNOWN, not a lower bound. No ATLAS invocation is needed
for this explicitly structured witness, no native C++ change.

Next obligation: a genuinely nonabelian, gauge-invariant quantum
coercivity estimate which controls long-wavelength collective
observables without assuming the gap. The free test is a negative
control for any proposed method claiming that gauge elimination or
local positive magnetic terms alone generate a mass. Compare
against compact U(1) with care: this calculation is for the free
noncompact quadratic approximation, not all compact U(1) regimes.

Reference for the actual target: Jaffe and Witten, Quantum Yang-Mills
Theory, https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf .
