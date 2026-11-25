"""Audit Haar channel overlaps, the collective modes and the remainder test."""
from fractions import Fraction as Q
from itertools import combinations

from ym36_pair_tests import plaquettes
from ym37_collective_loops import channels, coefficients, gap_test


def graph_audit(periods, all_pairs=False):
    faces, fans = plaquettes(periods)
    count, diagonal, hopping = coefficients(periods)
    assert len(faces) == count
    supports = [frozenset(tuple(sorted(e)) for e in p) for p in faces]
    neighbors = [set() for _ in faces]
    for near in fans.values():
        for i,j in combinations(near, 2):
            assert j not in neighbors[i]
            neighbors[i].add(j)
            neighbors[j].add(i)
    assert all(len(row) == 12 for row in neighbors)
    # Verify uniqueness of intermediate spin tuples for all shared pairs and,
    # on the smallest torus, exhaustively for all disjoint pairs as well.
    zero_supports, disjoint_supports = set(), set()
    for i,left in enumerate(supports):
        partners = range(i+1,count) if all_pairs else (j for j in neighbors[i] if j>i)
        for j in partners:
            right = supports[j]
            if left & right:
                key = left ^ right
                assert len(key) == 6 and key not in zero_supports and j in neighbors[i]
                zero_supports.add(key)
            else:
                key = left | right
                assert len(key) == 8 and key not in disjoint_supports and j not in neighbors[i]
                disjoint_supports.add(key)
    assert len(zero_supports) == 6*count
    vac, one, far, near = channels()
    assert vac+far == 0 and vac+near == hopping == -Q(1,21)
    assert diagonal == -Q(11,105)

    def rayleigh(values):
        norm = sum(x*x for x in values)
        cross = sum(values[i]*sum(values[j] for j in row) for i,row in enumerate(neighbors))
        # Independent sum over normalized intermediate states, including the vacuum.
        total = sum(values)
        adjacent_squares = sum((values[i]+values[j])**2 for i,row in enumerate(neighbors) for j in row if j>i)
        all_squares = (count-2)*norm + total**2
        channel_sum = vac*total**2 + one*norm + near*adjacent_squares + far*(all_squares-adjacent_squares)
        assert channel_sum + Q(count,3)*norm == diagonal*norm + hopping*cross
        return diagonal + hopping*Q(cross,norm)

    assert rayleigh([1]*count) == -Q(71,105)
    sample = [(i*19 % 11)-5 for i in range(count)]
    assert rayleigh(sample) >= -Q(71,105)
    if all(n%2 == 0 for n in periods):
        staggered = []
        for face in faces:
            a,b = face[0]
            _,c = face[1]
            xy = a[2] == b[2] == c[2]
            staggered.append((-1)**(a[0]+a[1]) if xy else 0)
        assert rayleigh(staggered) == Q(3,35)
    print("YM37", periods, count, "minimum quadratic coefficient", -Q(71,105))


def main():
    for n in (5,6,8):
        graph_audit((n,)*3, all_pairs=n==5)
        count = 3*n**3
        tiny = Q(1,1000*count**3)
        interval = gap_test((n,)*3,tiny)["full_gap_interval"]
        assert 0 < interval[0] <= interval[1] < 3
        scaled = tuple((x-3)/tiny**2 for x in interval)
        print("YM37 finite full-gap control", n, "u", tiny,
              "interval for (gap-3)/u^2", *(float(x) for x in scaled))
        target = gap_test((n,)*3,Q(1,8))
        assert target["second_order_gap"] == 3-Q(71,105*64)
        assert target["full_gap_interval"] is None
    assert gap_test((5,5,5),0)["full_gap_interval"] == (3,3)
    try:
        gap_test((4,6,6),Q(1,8))
    except ValueError:
        pass
    else:
        raise AssertionError("winding control failed")
    print("YM37 collective controls passed")


if __name__ == "__main__":
    main()
