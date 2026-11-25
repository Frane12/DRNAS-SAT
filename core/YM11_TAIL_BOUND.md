# YM11 — exact one-loop SU(2) tail bound

This is a model-specific proof for the infinite Jacobi operator H on
l2(N0) with diagonal d_j=j(j+2) and off-diagonals -1. It is not a new
Yang–Mills mass-gap theorem and not a proof for coupled lattices.

The diagonal grows to infinity; the hopping is bounded by 2 in operator
norm. Thus H is self-adjoint on the diagonal domain, bounded below,
and has compact resolvent (bounded perturbation of the diagonal).

1. The trial vector (1,1/3,0,...) gives E0 <= -3/10 by Rayleigh–Ritz.
2. Split off j=0,1,2,3. The remaining tail T is bounded below by
   4(4+2)-2=22. At t=31/10, T-tI is strictly positive.
3. The only head-tail coupling has magnitude 1 between j=3 and j=4.
   Hence the Schur complement S at t is bounded below by
   B=A-tI-(22-t)^(-1) e_3 e_3^T, where A is the four-state principal
   block. The Schur factorization is a bounded invertible triangular
   congruence on the corresponding form domain; the negative index
   of H-tI is the negative index of S.
4. The exact LDL pivots of B are
   -31/10, 69/310, 281/690, 4987771/531090.
   Exactly one is negative. Since S>=B, at most one eigenvalue of H
   is strictly below t.
5. E0 <= -3/10 < t, so E1 >= 31/10, with multiplicity counted.
   The gap is at least 17/5 = 3.4.

A local independent floating-point calculation of the 12-state principal
matrix gives a gap near 3.426288565734; it is not used in the proof.

This analytic bound includes the entire infinite tail at the fixed
coupling k=1 and specified normalization. It does not establish
uniformity in lattice volume or lattice spacing, nor construct a
continuum quantum field theory. The generic CORE interval-gap input
currently handles finite matrices only; automating the tail comparison
is a distinct next task.

Reproduce the exact arithmetic using Python 3:
```python
from fractions import Fraction as Q
t = Q(31,10)
tail = Q(22)
d = [Q(j*(j+2))-t for j in range(4)]
d[-1] -= 1/(tail-t)
p = []
for x in d:
    p.append(x if not p else x-1/p[-1])
assert p == [Q(-31,10),Q(69,310),Q(281,690),Q(4987771,531090)]
assert sum(x<0 for x in p)==1
u=(3*Q(1,9)-2*Q(1,3))/(1+Q(1,9))
assert u==Q(-3,10) and t-u==Q(17,5)
```
