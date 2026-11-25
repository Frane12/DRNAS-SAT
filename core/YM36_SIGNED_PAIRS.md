# YM36 · Signed adjacent squares in the three-dimensional SU(2) torus

We test the second-order defect D of [YM35](YM35_3D_VOLUME_AND_LIMIT.md) on pairs of plaquettes sharing one link. The configuration-space estimate improves the bound on the second derivative of D. The coefficient-space calculation identifies an obstruction to the current fixed-point proof at u=|k|/α=1/8. We use all link representations, periods at least four, and the YM35 Hamiltonian and units. The exact Fourier obstruction below is for even periods and the alternating link orientation.

## Signed pair in configuration space

Start both square walks at the same oriented link U and write their unit-quaternion holonomies as x=UA and y=UB. The Fourier channels from [YM22](YM22_VACUUM2.md) are P0=x·y and P1=4x₀y₀−P0, where the dot is Euclidean in four real coordinates. With t=k/(3α), the unordered-pair contribution to D/t² is

    f = P0/3 − P1/13 = (4 x₀y₀ + 16 x_vec·y_vec)/39.

The operator norm of this diagonal bilinear form is 16/39, attained for x=y a purely imaginary unit quaternion. Such a pair is realizable by adjusting a private link on either square. The separate suprema are 1 for |P0| and 3 for |P1| (the latter bilinear form has diagonal 3,−1,−1,−1). Their separate absolute bound is 22/39. The signed estimate works identically on coplanar and folded pairs.

Along a product geodesic let S_p be the sum of the speeds of the links in square p. In the radius-two metric each link's quaternion speed is |v_e|/2 and its Euclidean acceleration norm is |v_e|²/4. Inverse links have the same bounds. Differentiating the ordered word and using multiplicativity of quaternion length gives |x'|≤S_p/2, |x''|≤S_p²/4. Applying the product rule to f gives

    |f''| ≤ (4/39)(S_p+S_q)²
          ≤ (32/39)(2 |v_shared|² + Σ_outer |v_e|²).

The second inequality is Cauchy–Schwarz for the eight link occurrences. Charge each link using YM35's six shared and 36 outer pairs, with the shared speed counted twice. The four self terms still contribute at most 8 in total. Consequently the volume-independent Hessian coefficient is

    |Hess D| ≤ [8 + (32/39)(2·6+36)] t² = (616/13)t².

YM35 used (1112/13)t². This comparison applies to both link orientations.

## Exact Fourier-norm obstruction on even tori

In alternating orientation each of the four endpoint indices on either side of a fundamental Wilson coefficient is paired with one other index at a vertex. The coefficient matrix is rank one: a product of two unnormalized maximally entangled two-dimensional tensors at each side (up to local unitaries and permutations). Its sole singular value is four. The two-plaquette tensor product has singular value 16 before recoupling. At each side its two indices for the common link belong to different square factors, each with marginal I/2. The pair therefore has marginal I/4. Projecting those indices onto the spin-zero and spin-one subspaces retains respectively 1/4 and 3/4 of the squared length, independently at each side. A diagonal compression of a rank-one matrix has trace norm equal to the product of its projected vector lengths. The exact block norms are accordingly 4 and 12. Each irrep occurs once on the common link.

The P0 block has six spin-half edges. Its perimeter determines the adjacent pair uniquely. Among its six vertices the removed shared edge is the only lattice chord. For a flat 1 by 2 rectangle the only chord joins the middle two vertices. For a folded pair the vertices can be translated and rotated to 0, x, y, x+y, z, x+z, with chord (0,x). These descriptions include wraparound by translation and sign choice for periods at least four. The P1 block also records spin one on the shared edge. A self term instead has four spin-one links. Thus distinct contributing spin tuples of D never combine in this norm. The signs of different tuples disappear when the norm takes their individual trace norms.

For each root edge, the cost divided by t² is exactly

    4·9 + 6·(12/2) + 36·(3·4/2 + 12/2) = 504.

The self coefficient uses the alternating square in spin one, of trace norm 9. The factors 3/2 and 1/2 for the pair are the absolute channel coefficients times the output Casimirs. Hence N(D)=56u², attaining the previous upper estimate. At u=1/8 this equals 7/8. Even setting the linear contribution to zero, the old ball majorant with b=2/3 would require 7/8≤R−(2/3)R²≤3/8. This rules out success by reducing this defect estimate within the existing scalar majorant. It does not determine the actual gap at that coupling or rule out other norms or another vacuum approximation.

## Consequence for the original physical excitation

Use the same exact fixed-point and weighted curvature premises as YM35. On even tori set l=56u/3, b=2/3, h=(616/13)(u/3)², and rest=lR+bR². If 56u²+rest≤R and l+2bR<1, then the bound for the physical gap in units of α is

    1/2 − 16u/3 − 2 min(R,h+rest).

| u | R | Lower bound for Δ/α |
|---|---|---|
| 1/32 | 3/16 | 215/3744 ≈ 0.05743 |
| 2/63 | 17/80 | 850783/106142400 ≈ 0.00802 |
| 1/8 | — | UNKNOWN |

The second row is a rational test point chosen after inspecting the estimates, not a phase boundary. All smaller couplings satisfy the same inequalities with its radius. At 2/63 the old Hessian majorant fails even if its radius is allowed to vary. To check this exactly, split the radius at 21223/100000. Up to that point R−rest is increasing but still below the required defect there. Above that point the old gap lower bound is decreasing and is already negative at the split. The exact two inequalities are in the tests.

## Verification and limits

Run `python3 core/ym36_pair_tests.py` from the repository root. On 4×4×4, 4×4×6 and 6×6×6 it enumerates all pairs; the exact fundamental coefficients include the adjugate signs of reversed SU(2) links. The spin projectors are implemented through the two-index swap; their norms are measured from both tensor factors. The checks count unique supports and the cost at every root. A separate rational group-word test differentiates actual link geodesics twice for all six pairs touching a chosen link. These are algebraic tests of a supplied derivation. The all-size result still depends on the analytic premises of YM35 and awaits independent mathematical review. No independently calibrated lattice spacing or continuum mass is extracted in this experiment.
