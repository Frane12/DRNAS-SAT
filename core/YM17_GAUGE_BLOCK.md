# YM17 — exact spatial suppression of degree-two SU(2) vertices

Consider a finite simple graph with pure gauge Hilbert space
L2(SU(2)^E)^G, normalized Haar measure, electric Hamiltonian
alpha sum C_e and a sum of simple Wilson-loop traces. At a degree-two
vertex v orient the incident links u->v->w (inversion of a link is a
unitary coordinate change preserving its Casimir). Gauge invariance at v
forces dependence on the two links only through W=U_uv U_vw: the
transformation (U,V)->(U h^-1,h V) leaves W fixed and is transitive on
each fiber. Haar invariance makes pullback f(W)->f(UV) a unitary
identification of the invariant spaces. Endpoint gauge actions intertwine.

Each incident Casimir acts on that pullback as the Casimir of W, by
left/right invariance of the bi-invariant Laplacian. Thus a path of
length r with original coefficient alpha becomes one link of
coefficient r alpha. A simple closed Wilson path either passes through
both links or neither, so its holonomy is exactly preserved.
Iterating the unitary maps gives an equivalence of self-adjoint
Hamiltonians (first on the smooth invariant core, then by closure).
The entire spectrum, multiplicities and gap are unchanged; no spin cutoff.

The implementation uses actual pinned ATLAS30 to choose independent
sets of degree-two vertices. It excludes loops/parallel edges in the
reduced simple graph and stops when no safe suppression exists.
A separate Python checker reconstructs maximal original paths,
checks the oriented Wilson loops, exact weights and source digest,
and obtains the shortest weighted cycle via Dijkstra. For the
electric gap the weighted length replaces unweighted girth in YM13.
The same lower bound for the magnetic Hamiltonian is independently
checked against the original graph by the native CORE gauge-gap
task. Negative requested gaps are not certified just because the
blocking is valid. The structural certificate is an analytic theorem
application with checked finite combinatorics, not a formal proof
assistant certificate.

This is exact spatial blocking of subdivided edges, not a physical
renormalization step on a regular cubic lattice (degree six in d=3).
It does not eliminate independent plaquette degrees of freedom,
control generated interactions, or prove the continuum mass gap.
The next obstacle is elimination of vertices with degree >2 and
control of the induced nonlocal operators.
