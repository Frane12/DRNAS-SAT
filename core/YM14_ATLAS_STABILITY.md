# ATLAS / DRNAS CORE — YM14: volume-uniform strong-coupling regime

Scope: regular periodic hypercubic spatial lattices of dimension d=2,3,4 (in
particular d=3 for a 3+1-dimensional Hamiltonian). Fix alpha>0. All outgoing
links of a cell are grouped into one site with Hilbert space L2(SU(2)^d).
For side length L>=3, define
H_L = alpha sum_e C_e - k sum_p Tr U_p.
The constant-function site vacuum is unique; each site Casimir sum has
gap 3/4. It is diagonal in the Peter–Weyl representation and has an
infinite-dimensional local Hilbert space.

## Application of an existing theorem

Let S={0,e_1,...,e_d}. Define local unperturbed block
h_x = alpha/(d+1) sum_(y in x+S) sum_i C_(y,i).
Each link occurs in exactly d+1 translated blocks, so sum_x h_x is
the original electric Hamiltonian. Each block has a simple product
vacuum and gap at least s=3 alpha/[4(d+1)].
The magnetic operator phi_x is the sum of the binom(d,2) plaquettes
anchored at x. All four links of each such plaquette belong to cells
in x+S. Its operator norm is at most 2 binom(d,2)|k|.

Divide both block terms by s. Yarotsky's Theorem 1 applies to
translation-invariant possibly infinite-dimensional local Hilbert spaces,
periodic cubes, and classical gapped local blocks with sufficiently
small local relative-form perturbations. Here the relative part is
zero, and the additive bound is beta <= B|k|, with
B=8(d+1)binom(d,2)/(3 alpha).
Consequently there exists beta_*(d,S)>0 such that B|k| <= beta_*
implies a unique ground state and a positive spectral gap independent
of L for the normalized model. Multiply the gap by s to return to the
original normalization. No numerical value of beta_* or of the gap is
asserted by this certificate.

The full-link Hamiltonian commutes with the local gauge action of
SU(2)^{vertices}. Its unique ground state transforms by a continuous
one-dimensional unitary representation of this product group.
Such a representation is trivial, so the ground state is physical.
Restriction to the invariant subspace cannot reduce the gap above
that ground state. No electric representation cutoff is needed.

Primary source: D. A. Yarotsky, Ground states in relatively bounded
quantum perturbations of classical lattice systems, Theorem 1,
arXiv:math-ph/0412040, https://arxiv.org/abs/math-ph/0412040
(2004 preprint, published 2006). This is an application of a known
theorem, not a claimed original gap-stability theorem.

## CORE contract

Input: p op gauge-stability D ALPHA
Output: THEOREM_APPLIED (distinct from a numerical PROVED status).
Native code computes s and B; Python auditor checks them and source hash.
The theorem and the analytic mapping above are trusted mathematical
premises, not a machine-formalized proof in a proof assistant.
The ATLAS workflow may propose this theorem schema; no separate ATLAS
executable is invoked by this implementation.

Tests cover the normalization, actual periodic incidence structure,
tampered coefficients and invalid inputs. No numeric coupling is
accepted by the task, to avoid implying that an unknown threshold
was verified. The coupling condition is existential/qualitative.

## Limits and next problem

This closes the volume-dependence obstacle only in the sufficiently
electric-dominated regime at fixed lattice spacing. In the conventional
Hamiltonian normalization, k/alpha scales like g^{-4} (up to constants).
The asymptotically free continuum limit g->0 lies outside this argument.
The remaining tasks are a quantitative threshold, stability or
renormalization toward weak coupling, construction of the continuum
theory, and a positive physical gap in that limit. No Clay solution.
