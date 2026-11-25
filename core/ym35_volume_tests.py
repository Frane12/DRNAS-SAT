"""Audit local 3D counts and trace norms, plus scale and rejection controls."""
from collections import Counter, defaultdict
from fractions import Fraction as Q
from functools import lru_cache
from itertools import combinations, product

from ym34_local_tests import audit_gauss_weights, trace_norm
from ym35_volume_limit import certificate, physical_interval

tensor_norm = lru_cache(None)(trace_norm)


def mesh_audit(periods):
    alternating = all(n % 2 == 0 for n in periods)
    forward = set()
    faces = []
    incidence = defaultdict(list)

    def shift(point, axis):
        end = list(point)
        end[axis] = (end[axis] + 1) % periods[axis]
        return tuple(end)

    for a in product(*map(range, periods)):
        for axis in range(3):
            b = shift(a, axis)
            forward.add((b, a) if alternating and sum(a) % 2 else (a, b))
        for x, y in combinations(range(3), 2):
            b, d = shift(a, x), shift(a, y)
            c = shift(b, y)
            face = [(a, b), (b, c), (c, d), (d, a)]
            for e in face:
                incidence[tuple(sorted(e))].append(len(faces))
            faces.append((face, (x, y)))

    assert len(incidence) == len(forward) == len(faces) and all(len(v) == 4 for v in incidence.values())
    audit_gauss_weights(set(incidence))
    w, self_term = (4, 9) if alternating else (8, 27)
    for walk, _ in faces:
        signs = tuple(e in forward for e in walk)
        assert tensor_norm(signs, 2) == w
        assert tensor_norm(signs, 3) == self_term
    counts = defaultdict(Counter)
    shapes = Counter()
    for common, near in incidence.items():
        for i, j in combinations(near, 2):
            (first, plane1), (second, plane2) = faces[i], faces[j]
            first_edges = {tuple(sorted(e)) for e in first}
            second_edges = {tuple(sorted(e)) for e in second}
            assert first_edges & second_edges == {common}
            for e in first_edges | second_edges:
                counts[e]["shared" if e == common else "outer"] += 1
            oriented = next(e for e in first if tuple(sorted(e)) == common)
            if oriented in second:
                second = [(b, a) for a, b in reversed(second)]
            perimeter = {a: b for a, b in first + second if tuple(sorted((a,b))) != common}
            assert len(perimeter) == 6
            start = a = next(iter(perimeter))
            signs = []
            while perimeter:
                b = perimeter.pop(a)
                signs.append((a,b) in forward)
                a = b
            assert a == start and len(signs) == 6
            z = tensor_norm(tuple(signs), 2)/Q(2)
            assert 4 <= z <= (4 if alternating else 16)
            shapes["coplanar" if plane1 == plane2 else "bent"] += 1
    assert all(c == {"shared": 6, "outer": 36} for c in counts.values())
    assert shapes == {"coplanar": 2*len(incidence), "bent": 4*len(incidence)}


def main():
    for sizes in [(4,4,4), (5,4,4), (4,5,6), (5,5,5), (6,6,6)]:
        mesh_audit(sizes)
        even = all(n%2 == 0 for n in sizes)
        u = Q(1,32) if even else Q(1,64)
        c = certificate(sizes, u)
        assert c["status"] == "BOUNDED" and c["slack"] == 0
        assert c["lipschitz"] == Q(5,6)
        assert c["lower_over_alpha"] == (Q(23,468) if even else Q(4385,29952))
        assert c["upper_over_alpha"] == 12
        failure = certificate(sizes, Q(1,8))
        assert failure["status"] == "UNKNOWN" and failure["linear"] > 1
        print("YM35", sizes, u, c["lower_over_alpha"], c["upper_over_alpha"])

    # A fixed unit box with a=1/N. The actual energies are not diagonalized.
    base = physical_interval((4,)*3, Q(1,4), 16)
    assert base is not None
    for n in (4,8,16,32,64,128):
        interval = physical_interval((n,)*3, Q(1,n), 16)
        assert interval == tuple(v * n/4 for v in base)
        print("YM35_FIXED_BARE", n, *interval)
    # A rational path with g² falling like 1/log(1/a). Its coefficient is illustrative.
    for step in (1,2,4,8,16):
        n = 2**(step+2)
        interval = physical_interval((n,)*3, Q(1,n), Q(16,step))
        assert (interval is None) == (step >= 2)
        print("YM35_LOG_CONTROL", step, "UNKNOWN" if interval is None else "BOUNDED")
    print("YM35 volume and scale controls passed")


if __name__ == "__main__":
    main()
