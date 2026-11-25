# YM34 · A local gap estimate at the YM33 test coupling

## Statement and scope

Consider the original SU(2) link Hamiltonian on an L by H rectangular periodic square grid with both periods at least four. Use the full link Hilbert space with product Haar measure and its physical gauge-invariant subspace. Write H_KS=αC−k Σ_p W_p, where C is the positive product Casimir, W_p is the fundamental trace around an elementary square, and u=|k|/α. Use the radius-two SU(2) metric with single-link eigenvalues j(j+1).

The derivation below gives Δ_phys ≥ α/60 for every such finite torus at u ≤ 1/32. If both periods are even it gives Δ_phys ≥ 23α/60. These constants concern the excitation energy E1−E0, with fixed lattice spacing. The proof uses small coupling in its contraction argument. The two spatial directions and the coupling range are essential. The estimates do not construct an infinite-volume vacuum or control the continuum scaling of the parameters.

This is a project research derivation extending YM22, YM24 and YM29. The checks in Python verify finite combinatorics, coefficient norms and strict rational inequalities. Independent mathematical review of the analytic argument remains outstanding.

## 1 · Fourier norm and a stronger Gauss-law estimate

For a mean-zero, gauge-invariant Fourier polynomial use the YM29 norm

    N(f) = max_r Σ_{s:r∈supp(s)} E_s ||A_s||₁,
    E_s = Σ_e j_e(j_e+1),   J_s = Σ_e j_e.

A_s is the trace coefficient of the product representation with dimension factors absorbed. In a gauge-invariant tuple every nonzero vertex intertwiner obeys j_e ≤ Σ_{f incident at v, f≠e} j_f at either end of e. This follows from the SU(2) tensor-product rule. Terms of a gauge-invariant function can be projected to individual spin tuples while preserving invariance.

Fix e=(v,w). Let S denote the sum of spins on the other links incident to v or w. The two vertex inequalities give S≥2j_e. Each of these spokes ends at a different outer vertex, since the graph is simple and triangle-free. Apply the vertex inequality there with the spoke as the distinguished link. All the other links counted there are outside the central edge and its spokes, each counted at most twice. Their total spin O therefore satisfies 2O≥S. Thus J_s=j_e+S+O≥4j_e. Since E_s≥3J_s/2, we have both j_e≤E_s/6 and J_s≤2E_s/3. A spin-half square saturates the first bound.

Put B(f,g)=C⁻¹P(∇f·∇g), with P subtracting the Haar mean. In the norm N the inverse cancels the output Casimir. A product of trace coefficients decomposes with total trace norm at most the product of the input norms, by tensoring, unitary decomposition, diagonal-block pinching and partial trace over multiplicities. Derivatives in a unit left frame cost at most j_e per generator. Each output support lies in the union of the input supports. For a fixed output link r, charge the pair first to f when its tuple contains r. Its cost is at most

    3 Σ_{s:r∈supp(s)} ||A_s||₁ Σ_e j_e(s) Σ_{h:e∈supp(h)} j_e(h)||A_h||₁
    ≤ 3 · (2/3) · (1/6) N(f)N(g).

Charging also to g covers every possible output, yielding N(B(f,g))≤(2/3)N(f)N(g). The bound holds on the gauge-invariant subspace and extends to its completion. Summed gradients, C⁻¹ and mean projection preserve invariance. The factor 3 counts the three unit generators on each link.

## 2 · Orientation and local trace norms

Orient every link in the positive coordinate direction. When both periods are even one can instead orient all links from the black to the white vertices of the checkerboard. Changing orientation acts by link inversion and preserves the Hamiltonian spectrum. Choose one fixed orientation throughout the proof for a given grid.

On a simple n-link loop in an SU(2) representation of dimension d, the trace coefficient has trace norm d^(n−m), with m the number of transitions from forward to reversed along the cyclic walk. To see this, express every inverse representation matrix as a transpose conjugated by fixed unitaries using SU(2) self-duality. At each vertex the two neighboring matrix indices are identified in the cyclic trace. In the flattened coefficient matrix there are m pairs of row indices contracted with each other, m corresponding pairs of column indices, and n−2m indices passed from row to column. Up to unitary factors and permutations the latter form an identity of rank d^(n−2m). Each contracted pair has Euclidean norm √d, so each nonzero singular value is d^m. This proves the formula including the normalization. A coordinate-oriented square and a merged 1 by 2 rectangle each have one forward-to-reversed transition. In the alternating orientation half the vertices are transitions of that type.

| Exact quantity | Both periods even, alternating | Coordinate orientation |
|---|---:|---:|
| A single fundamental square, w | 4 | 8 |
| Spin-one character of a square, s | 9 | 27 |
| Half a fundamental trace on the six-edge merged rectangle, z | 4 | 16 |

A representation orientation matters for these trace norms. They are computed directly here.

## 3 · Recenter around the explicit first-order logarithmic vacuum

Write F1=(k/(3α)) Σ_p W_p, t=k/(3α). The equation for a mean-zero logarithmic vacuum is F=(k/α)C⁻¹Σ_p W_p + B(F,F). Set F=F1+X and D=B(F1,F1). There are two squares per link, so N(F1)≤2wu. With b=2/3 the linear map X↦2B(F1,X) has norm l≤4bwu.

For the self term in D the Fourier polynomial is −t²(W_p²−1)/8, a spin-one character with Casimir 8. Its norm cost is s t². For a pair sharing one link put P0=half the trace of the merged rectangle and P1=W_p W_q−P0. These are precisely the spin-zero and spin-one components on the common link. The two components in D for this unordered pair are t²(P0/3−P1/13), with Casimirs 9/2 and 13/2 respectively. These coefficients follow from the Casimir product rule applied to W_p W_q, as in [YM22](YM22_VACUUM2.md). The trace norm of P0 equals z, including its factor one half. Diagonal-block pinching of the two-square tensor product gives ||A(P0)||₁+||A(P1)||₁≤w², so the second block costs at most w²−z before Casimir weighting.

At a fixed link exactly two self terms, six pairs with this link on the outer boundary, and one pair with this link as the shared edge can contribute. In the last pair P0 has zero spin on the selected link and is absent from its norm sum. This yields

    η = t² [2s + 6(3z/2 + (w²−z)/2) + (w²−z)/2] ≥ N(D).

All coefficients in this bound depend only on the rooted neighborhood. Sizes four and five also have six distinct edges on the boundary of every neighboring plaquette pair.

## 4 · Contraction, ground state and excitation energy

For a radius R check η+lR+bR²≤R and β=l+2bR<1. The map X↦D+2B(F1,X)+B(X,X) then has a fixed point with N(X)≤R. The invariant Fourier space is complete on each finite graph. As in [YM29](YM29_DIRECT_HESSIAN.md), N bounds the absolute Hessian as a quadratic form: for a coefficient evaluated on a product geodesic, (Σ_e j_e |v_e|)²≤E_s Σ_{e∈supp(s)}|v_e|². Summing and charging to the tangent link gives |Hess X|≤R. Finite-volume summability also gives C² convergence. The fixed point is real by iteration from zero. Its exact logarithmic equation makes exp(F) a positive eigenfunction of the original H_KS. The ground-state transform gives the gradient Dirichlet form with weight exp(2F), and shows uniqueness of the ground state. It is gauge invariant.

Differentiating a length-four trace twice along a product geodesic gives |Hess W_p(v,v)|≤(Σ_{e∈p}|v_e|)²/2≤2 Σ_{e∈p}|v_e|². Thus |Hess F1|≤4u/3. The product metric has Ric=g/2. Applying the Bakry–Émery Poincaré criterion to the exact ground-state transform gives the physical lower bound α(1/2−8u/3−2R). Restriction to invariant states retains the ground state. The curvature criterion is stated in the introduction of [Cheng and Thalmaier, JFA 274 (2018)](https://doi.org/10.1016/j.jfa.2017.12.004).

| At u=1/32 | R | η | l | R−η−lR−bR² | β | Δ_phys/α at least |
|---|---:|---:|---:|---:|---:|---:|
| Alternating | 1/60 | 1/96 | 1/3 | 11/21600 | 16/45 | 23/60 |
| Coordinate | 1/5 | 61/1536 | 2/3 | 11/38400 | 14/15 | 1/60 |

For smaller u the same radii satisfy the inequalities monotonically. At u=0 the separate YM33 free physical gap is exactly 3α. The two orientation bounds are sufficient estimates. They do not predict a physical even/odd splitting.

## Reproduction and boundary

Run `python3 core/ym34_local_tests.py`. A single exact certificate can be obtained with `python3 core/ym34_local_gap.py 5 4 1/32`. Mesh tests reuse the YM32 grid generator, check the local spin inequality coefficient by coefficient, build the square and merged trace tensors explicitly, and count the contributions link by link. At u=1/8 both chosen radii fail and the prototype returns no gap certificate. Automated validation covers these algebraic and numerical components. The fixed-point proof and its functional-analytic premises are supplied in this note, without proof-assistant verification or autonomous discovery by CORE.

The remaining transfer is to control the local vacuum or relative excitation energy at larger |k|/α and on three-dimensional spatial lattices. The second-order geometry changes in three dimensions because a link can belong to four plaquettes and adjacent plaquettes can lie in different planes. Neither counting nor the numerical threshold should be carried over without a new bound. The fixed-spacing uniform estimate also leaves the continuum construction open.
