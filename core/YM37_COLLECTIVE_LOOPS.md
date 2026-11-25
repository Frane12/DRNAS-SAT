# YM37 · Can spreading a physical excitation drive its energy down?

Use the full SU(2) Hamiltonian H/α=T−uS from YM35, where T is the link Casimir sum, S the sum of fundamental square traces, and u=k/α. Take periodic three-dimensional rectangular tori with all periods ≥5. This excludes length-four winding loops. This note addresses superpositions of square excitations and their coupling to all intermediate states at second order. The question about the continuum concerns the full theory and all orders.

## Unperturbed subspaces

The constant Haar vacuum has energy zero. Each square trace W_p is normalized, orthogonal to the vacuum and to the other squares, and has energy 3. Gauge invariance forbids support leaves; thus a nontrivial support contains a cycle. On these lattices the only cycles of length four are elementary squares. Achieving energy 3 requires four fundamental links with unique bivalent intertwiners. This spans the entire eigenspace at 3. Other non-vacuum energy levels are at least 15/4: five occupied links cost at least this much, and any higher spin on a four-link support costs even more. At any finite size T has compact resolvent. Bounded multiplication by S preserves discreteness. A product of three elementary square traces has zero mean by central sign flips on links: with three distinct squares each of the other two shares at most one edge of the first. Repetitions also leave an odd link. First-order shifts of both clusters vanish.

## Relative second-order matrix

Let P be the number of squares. For a normalized plaquette vector with real coefficients c_p, multiplication by S has the following orthogonal channels. The same quadratic formula applies to complex coefficients with modulus squares. The energy denominators below belong to the excited cluster at 3.

| Intermediate state | Squared amplitude, before the denominator | Free energy |
|---|---:|---:|
| Constant | (Σ c_p)² | 0 |
| Spin-one square p from W_p²=1+χ₁ | c_p² | 8 |
| Two distinct edge-disjoint squares p,q | (c_p+c_q)² | 6 |
| Shared-edge pair, common link in spin zero | (c_p+c_q)²/4 | 9/2 |
| Shared-edge pair, common link in spin one | 3(c_p+c_q)²/4 | 13/2 |

In the shared pair, the zero component is half the simple merged trace and has squared Haar norm 1/4. The product has squared norm one, by integrating one private link of each square, even after fixing the common link. Spin orthogonality gives 3/4 in the other channel. For neighbors the sum of the two squared weights divided by 3−E is −8/21. For nonneighbors it is −1/3. Intermediate tuples from distinct unordered pairs are orthogonal. For shared squares the six-edge boundary has a unique interior chord. Edge-disjoint squares share at most one vertex, and the union graph recovers the two simple cycles. The self-spin-one case and vacuum are distinct from these. This calculation retains cancellation between different placements leading to the same intermediate state.

The vacuum's second-order shift is −P/3, from S applied to the constant. Subtract this shift when forming the excitation energy. The contribution 1/3 from the constant intermediate cancels the off-diagonal −1/3 for distant pairs. For adjacent pairs the remaining coefficient is −1/21. The diagonal equals

    1/3 − 1/5 − (P−13)/3 − 12·8/21 + P/3 = −11/105.

Thus the relative matrix is M=−(11/105)I−A/21 where A is the plaquette adjacency matrix for sharing one edge. Every row of A has 12 neighbors, so its largest eigenvalue is exactly 12, attained by equal coefficients. This proves that optimization over every linear combination of the entire free first excited eigenspace gives the same lowest second-order coefficient −71/105 for every stated size. On even tori an xy-plane checkerboard with zero coefficients on the two other orientations has eigenvalue −4 for A because the incidence matrix with unsigned face boundaries annihilates this vector and A=BᵀB−4I. Its relative coefficient is +3/35.

Consequently at each fixed finite size the physical gap satisfies

    Δ/α = 3 − (71/105) u² + O_size(|u|³) as u→0.

The connected terms have a volume-independent second-order coefficient. The analysis does not bound the full remainder uniformly under refinement or at u=1/8. Inserting 1/8 gives approximately 2.98943 for the lowest mode, or 3.00134 for the checkerboard excitation, at second order only. The degeneracy splitting refers to perturbed eigenvalue branches, not to the bare trial vectors remaining exact eigenstates.

## Full-gap error control at sufficiently small nonzero u

For completeness, consider the ground and first excited clusters separately at E=0 and 3. Set d=3 and 3/4 respectively as lower separation bounds from the complementary free spectrum. Write h=2P|u|, since the norm of the perturbation is at most h. Assume 2h<3/4. Min–max bounds place each perturbed cluster within h of E. Let Π be its free projection and Q=I−Π. For a cluster eigenvalue z, the eliminated block is invertible and the exact effective operator is

    K(z)=EΠ + u² ΠS Q (z−QHQ/α)⁻¹ Q SΠ

where the inverse acts only on the Q space and the linear compression vanishes. By the resolvent identity its distance in operator norm from the second-order effective operator with the free resolvent at E is at most

    ε(d)=2 h³/[d(d−2h)].

Here |z−E|≤h and the compressed perturbation also has norm at most h. At the lowest eigenvalue of either cluster, K(z) has smallest eigenvalue z. Indeed the complement already accounts for all the eigenvalues strictly below this cluster (zero for the vacuum, one for the excited cluster), and the Schur-complement inertia identity leaves no negative directions of K(z)−z. This justifies taking the minimum, including in the degenerate case. Weyl's bound and subtraction of the ground energy give an error at most ε(3)+ε(3/4) for the physical gap. This intentionally loose global estimate certifies a decrease at u=1/(1000P³) for each tested size. Those tiny couplings are a proof control, not the target coupling or a matched continuum trajectory. The bound becomes unavailable at 1/8 on these lattices.

## Reproduction and interpretation

Run `python3 core/ym37_collective_tests.py` and `python3 core/ym37_collective_loops.py 6 6 6 1/8`. Tests use the YM36 periodic meshes and independently assemble the quadratic form through intermediate states. They exercise signs, normalization, support collisions, vacuum subtraction, winding exclusions, zero coupling, and the finite-volume error check. The analytic premises are supplied above and have not been independently reviewed or formalized.

The official [Jaffe–Witten problem statement, p. 6](https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf) distinguishes the vacuum energy normalization, the definition of a gap and the demand to prove existence and a positive gap in the continuum. This experiment provides neither a proof of that statement nor a counterexample.
