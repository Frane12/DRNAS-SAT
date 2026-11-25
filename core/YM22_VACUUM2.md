# YM22 — second-order SU(2) logarithmic vacuum correction

Open elementary square grids in d=2,3. Set t=k/(3 alpha), F1=t sum Wp.
Every plaquette trace is a fundamental character; distinct elementary
squares share either no edge or one edge. With the radius-2 SU(2) metric
Delta Wp=-3 Wp and |grad Wp|^2=4-Wp^2=3-(Wp^2-1).
The spin-one character Wp^2-1 has Laplacian eigenvalue -8.

For an unordered pair sharing one edge, orient both traces so that
Wp=Tr(U A), Wq=Tr(U B). The tensor product on the shared edge splits
into spin zero and one. Define P0=Tr(A B^-1)/2, P1=Wp Wq-P0.
The six other links carry spin 1/2; hence Delta P0=-(9/2) P0,
Delta P1=-(13/2) P1. The product rule, or the quaternion dot product,
gives grad Wp dot grad Wq=(3/4)P0-(1/4)P1.
The merged trace uses the six-link boundary of the adjacent squares.
For disjoint edge sets the gradient inner product vanishes.

Consequently the exact second-order correction is

 F2=t^2[-sum_p (Wp^2-1)/8
          +sum_{p~q} (8 Tr(A B^-1)/39 - Wp Wq/13)].

It obeys Delta F2= -|grad F1|^2+3 P t^2 where P is the plaquette count.
With F=F1+F2, the parent operator alpha[-Delta+Delta F+|grad F|^2]
has the exact positive gauge-invariant ground state exp(F). Up to
the additive constant 3 alpha P t^2 it equals H_KS plus a signed
residual sum alpha(2 grad F1 dot grad F2+|grad F2|^2).
This is an exact identity, not a convergent perturbation expansion.

Local estimates: q=2(d-1), A=4q(q-1). At most q self terms and A
adjacent-pair terms touch a given edge. For unit link tangent,
|d W|<=1, |W|<=2. A self term has gradient bound 1/2;
a pair term has gradient bound 8/39+4/13=20/39. The corresponding
Hessian bounds, as quadratic forms on the union of supports, are
2 and 24/13 respectively: a length-six trace has Hessian bounded
by 3 times its support metric; a product of two plaquette traces
has Hessian bounded by 16 times the union metric. Thus
B=q/2+20 A/39 and C=2q+24 A/13 give
|grad_e F2|<=B t^2 and |Hess F2|<= C t^2 metric.

Bakry-Emery gives a volume-uniform reference gap at least
alpha(1/2-4q|t|-2 C t^2), if positive. The absolute residual per edge
is bounded by alpha(2q B |t|^3+B^2 t^4), with no volume factor.
The total residual can still grow with volume. There is no uniform
original KS gap derived from this bound, and no convergence proof
for higher-order corrections or continuum result.

CORE checks exact rational coefficients, based on these analytic
premises (not a proof-assistant formalization). The test verifies
216 local quaternion identities, checks negative and tamper controls,
and executes actual pinned ATLAS local forest at matching parameters.
ATLAS does not autonomously derive F2; this mathematical schema was
supplied explicitly. Input p op gauge-vacuum2 D ALPHA K GAMMA.
