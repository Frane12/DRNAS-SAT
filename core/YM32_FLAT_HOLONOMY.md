# YM32 — exact elimination of gauge-redundant flat directions

Finite SU(2) cell complexes only; not a quantum mass-gap result.

## Distinguish redundancy and genuine flat holonomy

Tree gauge sets every link of a spanning tree to identity using
vertex gauge transformations. This is exact, leaving simultaneous
conjugation at the root. Each chord is an independent SU(2)
variable, and each oriented face gives a group-word equation w=1
for a zero Wilson magnetic energy (Tr U=2 iff U=1).
The equations are exact for the original curvature, not an
inequality discarding derivative/commutator cross terms.

A word A g^eps B=1 in which generator g occurs exactly once gives
g^eps=A^-1 B^-1. Substitute in all remaining words and delete that
equation and generator. This is an exact bijection of solution
sets, equivariant under simultaneous conjugation. If all
generators are eliminated the flat connection is pure gauge.
If not, test actual nonidentity SU(2) values. A nonidentity
chord holonomy in tree gauge cannot be conjugate to identity.
A witness is verified against EVERY original face, not just
the reduced words. This is a restricted Tietze elimination,
not a general algorithm for deciding finitely presented groups.

## Linearized directions and nonlinear obstruction

At a flat assignment take left variations exp(epsilon X_e) U_e.
The differential of a word is a sum of adjoint transports by
prefixes, with a negative inverse letter contributing
-Ad(U_e^-1) X_e before prefix transport. A residual simultaneous
conjugation contributes (I-Ad(U_e)) X at every chord.
The difference dim ker Dword - rank orbit gives an infinitesimal
quotient dimension, not necessarily a smooth moduli dimension
at a singular point. Rational unit quaternions yield exact
rational adjoint matrices, and Gaussian elimination gives exact
ranks. The auditor computes these on original tree-gauge words.

For a disk the face relations eliminate every chord. For a
puncture or cylinder one global generator remains; at identity
there are three infinitesimal coordinates and at a noncentral
holonomy the conjugation quotient has one. For a torus the
remaining relation is a commutator, so all commuting pairs
are flat. At identity the commutator derivative vanishes, giving
six infinitesimal coordinates; at a generic commuting pair
(one noncentral generator suffices) the quotient dimension is
two. The identity tangent includes obstructed directions:
exp(eps X), exp(eps Y) has commutator 1+eps^2[X,Y]+O(eps^3),
so noncommuting tangent vectors are not tangent to an actual
curve of flat pairs. A zero eigenvalue of a linearized
curvature Hessian is therefore not automatically a physical
massless excitation.

## Automation and scope

Pinned ATLAS chooses a spanning tree by a CNF with independent
model check. A separate Python CORE research prototype chooses
word eliminations and searches commuting rational flat
witnesses. The verifier checks the tree, each elimination,
all original face equations, a nontrivial Wilson trace and
infinitesimal ranks. Prepared cases use permuted labels,
face order and orientation. No native spectral solver is run
in this phase; no autonomous general mathematical discovery
claim. This is classical geometry: flat moduli need quantization,
and nontrivial topology need not cause a vanishing physical gap.
No inference about volume-uniform or continuum quantum gaps.

Next: control transverse quantum energy near the actual flat
moduli, including singular strata and nontrivial holonomies,
then compare excitation energies at increasing spatial scale.
Do not identify an absolute ground-energy lower bound with
an excitation gap.
