"""Bounds for the physical SU(2) link Hamiltonian on closed square complexes."""
from collections import defaultdict
from fractions import Fraction
from math import ceil


def connected(neighbors):
    seen = set()
    pending = [next(iter(neighbors))]
    while pending:
        vertex = pending.pop()
        if vertex not in seen:
            seen.add(vertex)
            pending.extend(neighbors[vertex] - seen)
    return len(seen) == len(neighbors)


def check_geometry(mesh):
    """Check the girth and face parity hypotheses used in the Haar moments."""
    n = mesh["n"]
    faces = mesh["faces"]
    edges = {tuple(sorted(edge)) for edge in mesh["edges"]}
    if n < 4 or len(faces) < 4 or len(edges) != len(mesh["edges"]):
        raise ValueError("insufficient faces or repeated edges")
    neighbors = {i: set() for i in range(n)}
    for a, b in edges:
        if not 0 <= a < b < n:
            raise ValueError("invalid edge")
        neighbors[a].add(b)
        neighbors[b].add(a)
    if not connected(neighbors) or any(neighbors[a] & neighbors[b] for a, b in edges):
        raise ValueError("connected triangle-free graph required")
    incidence = defaultdict(list)
    for index, face in enumerate(faces):
        if len(face) != 4 or len(set(face)) != 4:
            raise ValueError("simple square required")
        for a, b in zip(face, face[1:] + face[:1]):
            incidence[tuple(sorted((a, b)))].append(index)
    if incidence.keys() != edges or any(len(indices) != 2 for indices in incidence.values()):
        raise ValueError("each link must have exactly two incident faces")
    dual = {i: set() for i in range(len(faces))}
    for i, j in incidence.values():
        dual[i].add(j)
        dual[j].add(i)
    if not connected(dual):
        raise ValueError("face dual must be connected")
    return len(edges), len(faces)


def bounds(mesh, alpha, k):
    """Exact rational endpoints. See YM33_TORUS_GAP.md for analytic premises."""
    if not isinstance(alpha, (int, Fraction)) or not isinstance(k, (int, Fraction)):
        raise TypeError("use rational coefficients")
    alpha, k = Fraction(alpha), Fraction(k)
    if alpha <= 0 or k < 0:
        raise ValueError("require alpha > 0 and k >= 0")
    edges, faces = check_geometry(mesh)
    electric_gap = 3 * alpha
    shift = 2 * k * faces
    excited_lower = electric_gap - shift
    variance = k**2 * faces
    vacuum_upper = -variance * electric_gap / (electric_gap**2 + variance)
    vacuum_lower = -shift
    if excited_lower > 0:
        vacuum_lower = max(vacuum_lower, -variance / excited_lower)
    # Round the exponent upward to keep this endpoint rational.
    exponent = 4 * edges + ceil(32 * k * faces / alpha)
    heat_lower = electric_gap / (1 << exponent)
    return {
        "edges": edges,
        "faces": faces,
        "variational_lower": excited_lower - vacuum_upper,
        "heat_exponent": exponent,
        "lower": max(excited_lower - vacuum_upper, heat_lower),
        "upper": electric_gap - vacuum_lower,
    }
