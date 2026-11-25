# YM21 — explicit reference vacuum, local residual and curvature gap

On a finite open d-dimensional cubic lattice, d=2 or 3, use the product
bi-invariant SU(2) metric of round S^3 radius 2. Then -Delta on each
link has Casimir eigenvalues j(j+1) and Ricci=1/2 times the metric.
Let W_p=Tr(U_p) for elementary squares, H=-alpha Delta-k sum W_p,
F=lambda sum W_p with lambda=k/(3 alpha), and psi=exp(F).
The gauge-invariant psi is everywhere positive, and Delta W_p=-3 W_p
because the plaquette uses four distinct links in the fundamental
representation.

Define the reference parent H_ref=H+alpha |grad F|^2. The identity
Delta exp(F)=exp(F)(Delta F+|grad F|^2) gives H_ref psi=0.
Conjugation by psi identifies H_ref with -alpha(Delta+2 grad F dot
grad) on L2(exp(2F) dHaar). Integration by parts gives its nonnegative
Dirichlet form; the constant is its unique zero mode on the connected
product. The gauge-invariant subspace contains this ground state.

For a product geodesic of link speeds v_e, differentiating the
quaternion product for W_p twice gives
|Hess W_p(v,v)| <= (sum_{e in p}|v_e|)^2/2
<= 2 sum_{e in p}|v_e|^2. Each link occurs in at most q=2(d-1) squares.
Thus Ric-2 Hess F >= (1/2-4q|lambda|) metric. The Bakry-Emery
curvature/Poincare criterion gives

    gap(H_ref) >= alpha/2 - 4q|k|/3,

when the right side is positive, uniformly in lattice volume.
Restriction to physical gauge-invariant functions cannot decrease it.
The proof uses the full compact group manifold, no spin truncation.

The residual R=alpha|grad F|^2 is a sum over links of nonnegative local
multiplication operators R_e. Since |grad_e W_p|<=1,
0<=R_e<=alpha lambda^2 n_e^2 where n_e is plaquette incidence.
In particular R_e<=alpha lambda^2 q^2. This is a quantitative local
O(k^2/alpha) bound. However sum_e R_e is extensive. Min-max gives only
gap(H)>=gap(H_ref)-alpha lambda^2 sum_e n_e^2, using H<=H_ref and
E0(H)<=0. This finite-volume lower bound may become negative.
It is NOT valid to subtract only the per-link maximum from the gap.

The native certificate is explicitly for H_ref, not H; the original
finite gap bound is reported separately and may be negative. The
independent checker computes incidence by boundary-coordinate counts
rather than the native enumeration. The analytic curvature theorem
and metric estimates are mathematical premises, not a formal proof
assistant certificate. Standard curvature criterion: Cheng and
Thalmaier, JFA 274 (2018), pp. 959-984, introduction (Ric^Z>=K).
The product ground state here is not a claim about the actual KS vacuum.

Input p op gauge-parent-volume D L ALPHA K GAMMA. Tests include an actual
pinned ATLAS forest at matching small-grid parameters; its original
CORE gap and its structural certificate are independent of the parent
certificate. This is not a new stability theorem or a continuum
solution. Next: prove stability against the sum of local residuals
with an explicit volume-independent threshold, and then address
the weak-coupling continuum regime.
