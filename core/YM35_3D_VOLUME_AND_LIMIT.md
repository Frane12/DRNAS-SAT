# YM35 · Three spatial dimensions and the refinement limit

## Result in the normalization of YM14 and YM33

Let H=αC−kΣ W_p act on all SU(2) links of a three-dimensional rectangular periodic cubic lattice, with each period at least four and α>0. Energies refer to the physical gauge-invariant sector. Write u=|k|/α, and Δ=E1−E0. The argument yields the following bounds independently of all three periods.

| Family | Range | Lower bound for Δ/α | Upper bound for Δ/α |
|---|---:|---:|---:|
| All periods even | u≤1/32 | 23/468 | 12 |
| Arbitrary periods | u≤1/64 | 4385/29952 | 12 |

The second lower bound is larger because it is evaluated in a smaller interval. Coordinate orientation applies even when all periods are even. On the narrower interval the code's alternating constants are at least as favorable. These sufficient bounds follow from an analytic research argument extending [YM34](YM34_LOCAL_TORUS_GAP.md); independent mathematical review is outstanding. No diagonalization or extrapolation of measured eigenvalues enters.

## Local geometry in dimension three

A link belongs to q=4 plaquettes. A single plaquette has 4(q−1)=12 distinct adjacent plaquettes sharing one edge. Of the unordered neighboring pairs whose union contains a fixed root link, six share that root (two coplanar and four folded). If the root is on the outer boundary, choose the unique member containing it, one of its three other edges, and one of the three other plaquettes at that edge. This gives 4·3·3=36 outer pairs. Each neighboring pair bounds a simple six-edge perimeter after removing the common edge, including folded pairs. Periods of at least four prevent identifications within these patches.

Retain YM34's gauge-invariant Fourier norm N, its bound b=2/3 for B=C⁻¹P(∇f·∇h), and the one-link estimate j_e≤E_s/6. Their proofs use a triangle-free simple graph independently of dimension. Let w be the trace norm of a fundamental square and s that of its spin-one character. Alternating orientation gives (w,s)=(4,9); positive coordinate orientation gives (8,27). For a merged perimeter the norm z of half the fundamental trace equals 2^(6−m)/2, where m counts cyclic forward-to-reversed transitions. Alternating orientation gives z=4. In coordinate orientation the closed contractible walk lifts to zero net displacement, hence contains both signs and 1≤m≤3. Thus 4≤z≤16, including the folded geometries.

## Two improvements needed by the three-dimensional estimate

Set t=k/(3α), F1=tΣ W_p, F=F1+X, D=B(F1,F1), L=2B(F1,·). The logarithmic vacuum equation is X=D+LX+B(X,X). For a fixed output link r bound the two contributions to B(F1,G) disjointly.

* If the input spin tuple of G contains r, sum the plaquettes at every derivative link e in that tuple. Three frame derivatives, spin 1/2 on the square and Σ_e j_e≤2E_s/3 give cost ≤qw|t|N(G).
* If the input tuple omits r, the square must contain r. Only its other three links can carry the common derivative. At each of them j_e≤E_s/6. This costs at most (3/2)·3·(1/6)qw|t|N(G).

The factor two in L gives l=(7/6)qwu. This refines the previous double charge.

For each pair the exact YM22 components of D/t² are P0/3−P1/13, with Casimirs 9/2 and 13/2. P0 has coefficient norm z and omits the common edge. The spin-one block has norm ≤w²−z by joint pinching. Therefore a shared pair costs ≤(w²−z_min)/2, and an outer pair costs ≤w²/2+z_max. The self term costs s. Consequently

    N(D) ≤ η = t²[4s + 6(w²−z_min)/2 + 36(w²/2+z_max)].

The second improvement retains the explicit Hessian of D. In position space D/t² contains −(W_p²−1)/8 per self term and (8/39)Tr(U_merged)−W_p W_q/13 per unordered pair. The length-m trace obeys |Hess W|≤(m/2)Σ_support |v_e|² and for m=4 its directional first derivative has absolute value ≤Σ_support |v_e|. Thus the self-term Hessian costs at most 2 times its support metric. For a neighboring pair the merged term costs at most (8/39)·3 and the product at most 16/13. The pair costs at most 24/13, even when folded. This gives |Hess D|≤h_D g, with h_D=t²(8+42·24/13).

Use R=3/16. If η+lR+bR²≤R and l+2bR<1, the fixed point exists with N(X)≤R. As X−D=LX+B(X,X), the YM29 direct Hessian bound applied to the remainder yields |Hess X|≤min(R,h_D+lR+bR²). In the product metric of radius two, Ric=g/2 and |Hess F1|≤2qu/3. The same exact ground-state transform and weighted Poincaré criterion as YM34 therefore yield

    Δ/α ≥ 1/2 − 4qu/3 − 2 min(R,h_D+lR+bR²).

At the two stated endpoints η=7/128, l=7/12, the closed ball has zero invariance slack, and its Lipschitz bound is strictly below one (5/6). A closed ball mapped into itself suffices. All required upper estimates decrease with u. At u=1/8 the even-torus linear majorant alone is 7/3, so adjusting the radius in this particular majorant cannot reach the target.

## Upper bound on the excitation energy

Take one physical plaquette trace W as a trial observable in the exact vacuum-weighted Dirichlet form. Its energy numerator divided by α is ≤4 because |∇W|²=4−W². Condition on all links except one in that square. The Haar variance of W as a function of the remaining link equals one (the fundamental character has mean zero and norm one). Along that link, |∇_e F1|≤qu/3 and |∇_e X|≤R/6 by j_e≤E_s/6 applied to each unit tangent direction. Put K=qu/3+R/6. The group diameter is 2π. Hence the conditional density proportional to exp(2F) is bounded below by exp(−4πK) relative to normalized Haar, uniformly in the frozen links. By the infimum-over-constants variance formula and total variance, Var_vac(W)≥exp(−4πK). At the larger endpoint K=7/96 and 4πK<1. This gives Δ/α≤4e^(4πK)<12. The argument uses an actual gauge-invariant excitation trial observable and is volume independent.

## Three limits with distinct conclusions

1. **Large volume with fixed a and fixed bare coupling.** In the certified range every finite-volume physical gap lies in [cα,12α] with c>0 as above. Hence the liminf over growing tori is positive. Boundedness gives convergent subsequences. A unique thermodynamic limit for the excitation energy or a construction of the infinite-volume Hamiltonian requires a separate argument.
2. **Refinement with fixed bare coupling.** Use α=g²/(2a), k=2/(ag²), u=4/g⁴. Hold a certified bare g fixed and let a→0, for instance with each physical period N_i a fixed (or tending to infinity). Then c g²/(2a) ≤ Δ ≤ 6g²/a, so Δ→+∞ in fixed physical units. Also aΔ is bounded between positive constants, without a claim that it converges. This is an actual limit for the excitation energy along this chosen refinement, conditional on the analytic bounds. It rules out a finite mass along this path in the stated energy normalization.
3. **Continuum scaling with running coupling.** In the asymptotically free 3+1-dimensional target g²(a) tends to zero. Consequently u(a)=4/g⁴(a) tends to infinity, while the proven intervals stop at 1/32 and 1/64. Write δ(N,u)=Δ/α. A finite, nonzero mass m along a volume-and-cutoff trajectory requires δ(N(a),u(a)) ∼ 2ma/g²(a). This is a necessary matching condition, not an estimate of δ at weak coupling. If a physical box is kept fixed during refinement, one must subsequently control the large physical volume limit. Identifying a continuum theory and the spectral gap of its Hamiltonian also requires convergence of the relevant dynamics or observables.

## Reproduction

Run `python3 core/ym35_volume_tests.py`. The local audit uses actual cubical incidence and enumerates tensor contractions on coplanar and folded six-link loops. Five torus shapes include even, odd and mixed periods. The exact-arithmetic control at fixed g²=16 uses a=1/N, N=4 to 128, in a unit box. The reported endpoints scale linearly with N. A second control uses N=2^(n+2) and g²=16/n to exercise a decreasing coupling with logarithmic rate; its coefficient is illustrative, independent of any matching to a physical scale. Failed bounds produce UNKNOWN rather than an energy value. The code checks the finite identities, coefficients and inequalities. It does not construct a continuum measure or formally verify the functional analysis.

Background: [Jaffe and Witten, Quantum Yang–Mills Theory](https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf), [García Vera and Sommer, continuum scaling in SU(N) Yang–Mills theory](https://doi.org/10.1140/epjc/s10052-019-6539-4).
