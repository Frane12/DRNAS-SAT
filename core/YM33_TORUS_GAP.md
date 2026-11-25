# YM33 · Physical excitation bounds on the YM32 tori

Use all original links, all square plaquettes and the infinite SU(2) representation tower. In the YM14 normalization the Hamiltonian on the gauge-invariant subspace of product Haar space is

    H = T + V,    T = α Σ_e C_e,    V = −k S,    S = Σ_p χ_p,

where χ_p = Tr_fund U_p, α>0, k≥0 and C_e has eigenvalues j(j+1). E0 and E1 are the two lowest physical energies, counting multiplicity. The dimensionless output is obtained by setting α=1. The unshifted Wilson convention here differs from the nonnegative magnetic energy by a scalar. The following analytic comparisons use the full configuration space, including all flat strata. Their constants apply to the specified finite graphs. None of the derivations uses an identification of the quantum dynamics with motion on the moduli of flat connections.

## Electric spectrum and exact Haar moments

A nonconstant physical spin network needs a cycle of links with nonzero spin. A support with a leaf cannot carry an invariant intertwiner there. A simple graph without triangles needs at least four links on a cycle. Each costs at least 3α/4. The trace around any square attains the electric threshold D=3α. The constant is the unique free vacuum.

Write F for the number of faces and M for the number of links. Each square uses four distinct links, hence its product is Haar and its character has squared norm one. Haar invariance under an independent central sign flip on a link kills a product of characters if that link occurs an odd number of times. In a closed quadrangulation with connected face dual, the only face subsets with even boundary are the empty subset and the set of all faces. The tests check these hypotheses and F>3. Thus distinct plaquette traces are orthogonal and every product of three plaquette traces has zero mean, also for repeated labels. In particular ⟨S²⟩=F and ⟨S³⟩=0.

## Two-sided physical excitation bound

1. The min–max principle and |V|≤2kF give E1≥B=D−2kF.
2. Put v=k²F. In the trial state 1+(k/D)S the Rayleigh quotient equals U0=−vD/(D²+v). This supplies E0≤U0.
3. On span{1, χ_p−χ_q} for distinct faces, the compressed magnetic operator vanishes by the moment identities. The maximum trial Rayleigh quotient is D, giving E1≤D.
4. A global lower bound for E0 is −2kF. If B>0, Temple's inequality with the constant trial vector of mean energy zero and energy variance v gives E0≥−v/B. This also follows by taking the vacuum expectation of (H−E0)(H−B)≥0.
5. Set L0 to the best lower bound from step 4. Then B−U0 ≤ E1−E0 ≤ D−L0. No single plaquette trial is assumed to be the first physical excited state.

## An explicit finite-volume lower bound for every finite coupling

The following conservative estimate covers cases where B−U0 loses its sign. For time s=4 log(2)/α the single-link free heat kernel differs pointwise from 1 by at most

    δ = Σ_{n≥1} (n+1)² 2^{−n(n+2)} < 3/5.

This uses the SU(2) character expansion, n=2j, and |χ_j|≤2j+1. The n=1 term is 1/2, the n=2 term is 9/256 and subsequent term ratios from n=2 onward are at most 1/64. The minimum-to-maximum ratio of the M-link free heat kernel is therefore at least 4^(−M). Feynman–Kac comparison with the bounded real potential V gives, for its strictly positive ground function ψ, min ψ/max ψ ≥ exp(−s osc V) 4^(−M), with osc V ≤4kF. Compactness, ellipticity and positivity improvement on the connected product ensure a unique smooth positive ground state. Gauge symmetry makes this state invariant.

In the ground-state transform, the energy form on a physical test observable is the electric gradient form weighted by ψ². Its denominator is the ψ²-weighted variance. Comparing numerator from below with min ψ² and variance from above with max ψ², then applying the free physical Poincaré inequality gives

    Δ ≥ D (min ψ / max ψ)² ≥ D · 2^{−4M−ceil(32 k F/α)}.

All code endpoints use rational arithmetic. The finite-volume positivity mechanism is classical spectral theory. This bound deteriorates exponentially with volume. The collapse of a lower estimate provides no upper witness for softening.

## Control at singular and regular flat backgrounds

Assign every positive horizontal link exp(iθσ₁) and every positive vertical link exp(iησ₂). Compute the ordered plaquette products on the actual periodic mesh. Quaternion multiplication gives exactly 1−Tr(U_p)/2 = 2 sin²θ sin²η. Orienting both rotations along the same axis instead gives zero identically. Rational half-angle parameters allow exact arithmetic. At fixed noncentral horizontal holonomy in the tested examples the transverse magnetic cost along this family is quadratic in η. At θ=η→0 it is quartic. These are classical potential controls on selected directions. The spectral bounds above remain global and do not determine the first excited wavefunction or its localization near a stratum.

## Reproduction and limitations

Run `python3 core/ym33_torus_tests.py` from the repository root. The tests reuse YM32's mesh builder, its two relabelling seeds, and quaternion operations. The comparisons are analytically supplied to a Python prototype. No native CORE search or new ATLAS planning step is invoked. The automated checks cover geometry, rational evaluations, scaling, relabelling, and Wilson products. They do not machine-formalize the spectral theorems.

The two spatial directions match the YM32 tori. Varying the number of sites at fixed α and k tests volume dependence in lattice units. A continuum trajectory would additionally require control as a→0 with physically matched couplings and, for the Clay problem, three spatial dimensions. YM14 separately invokes a qualitative volume-uniform strong-coupling theorem. Here the quantitative loss enters through the global bound 2kF and the product heat-kernel comparison. Replacing these by local comparisons of excitation energy relative to the correlated vacuum is the outstanding step.

Background on the electric Casimir and Wilson Hamiltonian: Rahman et al., [Phys. Rev. D 104, 034501](https://doi.org/10.1103/PhysRevD.104.034501).
