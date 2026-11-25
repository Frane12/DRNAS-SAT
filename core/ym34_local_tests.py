"""Check proof constants against actual YM32 meshes and exact trace tensors."""
from collections import Counter, defaultdict
from fractions import Fraction as Q
from itertools import product
from math import isqrt

from flat_words_tests import grid
from ym34_local_gap import certificate


def trace_norm(signs, dimension):
    # Coefficient of Tr(M1 ... Mn) with selected matrix variables transposed.
    # Passing from transpose to inverse on SU(2) only changes local unitaries.
    rows, cols = defaultdict(set), defaultdict(set)
    for indices in product(range(dimension), repeat=len(signs)):
        shifted = indices[1:] + indices[:1]
        row = tuple(a if pos else b for a, b, pos in zip(indices, shifted, signs))
        col = tuple(b if pos else a for a, b, pos in zip(indices, shifted, signs))
        assert col not in rows[row]
        rows[row].add(col)
        cols[col].add(row)
    total = 0
    remaining = set(rows)
    while remaining:
        row = next(iter(remaining))
        right = rows[row]
        left = cols[next(iter(right))]
        assert all(rows[i] == right for i in left)
        assert all(cols[j] == left for j in right)
        singular = isqrt(len(left) * len(right))
        assert singular**2 == len(left) * len(right)
        total += singular
        remaining.difference_update(left)
    return total


def audit_gauss_weights(edges):
    # Verify the coefficient identity for 2(J - 4 j_e) before assigning spins.
    incident = defaultdict(set)
    for e in edges:
        for v in e:
            incident[v].add(e)
    for root in edges:
        lhs = Counter({e: 2 if e != root else -6 for e in edges})
        rhs = Counter()
        spokes = (incident[root[0]] | incident[root[1]]) - {root}
        rim = set()
        for endpoint in root:
            rhs[root] -= 3
            for spoke in incident[endpoint] - {root}:
                rhs[spoke] += 3
                outside, = set(spoke) - {endpoint}
                assert outside not in rim
                rim.add(outside)
                rhs[spoke] -= 1
                rhs.update(incident[outside] - {spoke})
        for edge in edges - spokes - {root}:
            rhs[edge] += 2 - len(set(edge) & rim)
        assert rhs == lhs


def audit_geometry(width, height):
    mesh = grid(width, height, True, True)
    alt = not (width % 2 or height % 2)
    forward = set()
    for x, y in product(range(width), range(height)):
        a = x * height + y
        for b in [((x+1) % width)*height+y, x*height+(y+1) % height]:
            forward.add((b, a) if alt and (x+y) % 2 else (a, b))
    def edge(a, b):
        return tuple(sorted((a, b)))
    faces = []
    directed = []
    incidence = defaultdict(list)
    for i, f in enumerate(mesh["faces"]):
        walk = list(zip(f, f[1:] + f[:1]))
        directed.append(walk)
        faces.append({edge(a, b) for a, b in walk})
        signs = tuple((a, b) in forward for a, b in walk)
        assert trace_norm(signs, 2) == (4 if alt else 8)
        assert trace_norm(signs, 3) == (9 if alt else 27)
        for e in faces[i]:
            incidence[e].append(i)
    assert set(incidence) == set(mesh["edges"])
    audit_gauss_weights(set(incidence))
    counts = {e: Counter() for e in incidence}
    patterns = set()
    for common, (i, j) in incidence.items():
        assert faces[i] & faces[j] == {common}
        perimeter = {a: b for a, b in directed[i] + directed[j] if edge(a, b) != common}
        assert len(perimeter) == 6
        a = next(iter(perimeter))
        start, signs = a, []
        while perimeter:
            b = perimeter.pop(a)
            signs.append((a, b) in forward)
            a = b
        assert a == start
        patterns.add(tuple(signs))
        for e in faces[i] | faces[j]:
            counts[e]["shared" if e == common else "outer"] += 1
    assert all(c == {"shared": 1, "outer": 6} for c in counts.values())
    for signs in patterns:
        assert trace_norm(signs, 2) / Q(2) == (4 if alt else 16)


def main():
    for width, height in [(4, 4), (5, 4), (5, 5), (4, 7), (6, 6), (8, 8), (12, 12)]:
        audit_geometry(width, height)
        c = certificate(width, height, Q(1, 32))
        alt = c["orientation"] == "alternating"
        expected = ((Q(1,96), Q(11,21600), Q(16,45), Q(23,60)) if alt else
                    (Q(61,1536), Q(11,38400), Q(14,15), Q(1,60)))
        assert tuple(c[k] for k in ("defect", "slack", "lipschitz", "gap_lower")) == expected
        assert certificate(width, height, Q(-1,32)) == c
        assert certificate(width, height, Q(1,8))["gap_lower"] is None
        print(f"YM34 {width}x{height} gap/alpha >= {c['gap_lower']}")
    for bad in [(3, 4), (8, 0)]:
        try:
            certificate(*bad, Q(1,32))
        except ValueError:
            continue
        raise AssertionError("short period accepted")
    print("YM34 local controls passed")


if __name__ == "__main__":
    main()
