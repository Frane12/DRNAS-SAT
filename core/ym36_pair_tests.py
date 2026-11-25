"""Exact checks of the signed pair, spin projections and rooted Fourier norm."""
from collections import Counter, defaultdict
from fractions import Fraction as Q
from itertools import combinations, product
from math import isqrt

from flat_words_verify import I, inv, mul
from ym35_volume_limit import certificate as ym35
from ym36_signed_pairs import gap_certificate, signed_pair


def plaquettes(periods):
    def step(v, axis):
        out = list(v)
        out[axis] = (v[axis]+1) % periods[axis]
        return tuple(out)

    fans = defaultdict(list)
    squares = []
    for v in product(*map(range, periods)):
        for a, b in combinations(range(3), 2):
            va, vb = step(v, a), step(v, b)
            corner = step(va, b)
            loop = [(v, va), (va, corner), (corner, vb), (vb, v)]
            for edge in loop:
                fans[tuple(sorted(edge))].append(len(squares))
            squares.append(loop)
    return squares, fans


def row_column_factors(walk, shared):
    # Extract the actual fundamental coefficient array, including the adjugate
    # signs of reversed SU(2) links. Place the shared-link bit first.
    offset = next(i for i, e in enumerate(walk) if tuple(sorted(e)) == shared)
    walk = walk[offset:] + walk[:offset]
    coeff = {}
    for bits in product(range(2), repeat=4):
        row, col, phase = [], [], 1
        for e, a, b in zip(walk, bits, bits[1:]+bits[:1]):
            if sum(e[0]) % 2:
                phase *= (-1)**(a+b)
                a, b = 1-b, 1-a
            row.append(a)
            col.append(b)
        coeff[tuple(row), tuple(col)] = phase
    r0, c0 = next(iter(coeff))
    left = {r: v for (r,c), v in coeff.items() if c == c0}
    right = {c: v*coeff[r0,c0] for (r,c), v in coeff.items() if r == r0}
    assert coeff == {(r,c): a*b for r,a in left.items() for c,b in right.items()}
    return left, right


def projected_squared_norms(a, b):
    tensor = {(r,s): x*y for r,x in a.items() for s,y in b.items()}
    norm = sum(x*x for x in tensor.values())
    exchange = sum(x*tensor.get(((s[0],)+r[1:], (r[0],)+s[1:]), 0)
                   for (r,s), x in tensor.items())
    return (Q(norm-exchange,2), Q(norm+exchange,2))


def exact_block_norms(p, q, e):
    left, right = row_column_factors(p, e)
    other_left, other_right = row_column_factors(q, e)
    squares = [a*b for a,b in zip(projected_squared_norms(left, other_left),
                                   projected_squared_norms(right, other_right))]
    roots = [isqrt(int(v)) for v in squares]
    assert all(r*r == v for r,v in zip(roots, squares))
    return tuple(roots)


def audit_torus(periods):
    faces, fans = plaquettes(periods)
    supports = [{tuple(sorted(e)) for e in p} for p in faces]
    assert len(set(map(frozenset, supports))) == len(faces)
    seen_zero, seen_one = set(), set()
    costs = Counter({e: 9*len(inc) for e,inc in fans.items()})
    for e, inc in fans.items():
        for i,j in combinations(inc, 2):
            z, one = exact_block_norms(faces[i], faces[j], e)
            assert (z,one) == (4,12)
            perimeter = frozenset(supports[i] ^ supports[j])
            assert len(perimeter) == 6 and perimeter not in seen_zero
            seen_zero.add(perimeter)
            key = (e,perimeter)
            assert key not in seen_one
            seen_one.add(key)
            for outer in perimeter:
                costs[outer] += (3*z+one)/Q(2)
            costs[e] += one/Q(2)
    assert set(costs.values()) == {504}
    print("YM36 Fourier", periods, "pairs", len(seen_zero), "root cost", 504)


def pair_controls():
    elements = [I, (0,1,0,0), (Q(3,5),0,Q(4,5),0), (Q(1,2),)*4]
    for shared, a, b in product(elements, repeat=3):
        x, y = mul(shared,a), mul(shared,b)
        zero = mul(a, inv(b))[0]
        one = 4*x[0]*y[0]-zero
        assert zero/Q(3)-one/Q(13) == signed_pair(x,y)
        assert abs(signed_pair(x,y)) <= Q(16,39)
    assert signed_pair(elements[1], elements[1]) == Q(16,39)
    assert signed_pair(I,I) == Q(4,39)


def second_derivative_controls():
    # Exact derivatives along product geodesics, on coplanar and folded pairs.
    faces, fans = plaquettes((4,4,4))
    common, near = next(iter(fans.items()))
    zero_quat = (0,0,0,0)
    elements = [I, (0,1,0,0), (Q(1,2),)*4, (Q(3,5),0,Q(4,5),0)]

    def add(*terms):
        return tuple(map(sum, zip(*terms)))

    def walk_derivatives(face, jets):
        if common not in face:
            face = [(b,a) for a,b in reversed(face)]
        offset = face.index(common)
        val, first, second = I, zero_quat, zero_quat
        for directed in face[offset:] + face[:offset]:
            key = tuple(sorted(directed))
            f, df, ddf = jets[key]
            if directed != key:
                f, df, ddf = inv(f), inv(df), inv(ddf)
            cross = mul(first,df)
            second = add(mul(second,f), cross, cross, mul(val,ddf))
            first = add(mul(first,f), mul(val,df))
            val = mul(val,f)
        return val, first, second

    for i,j in combinations(near,2):
        links = sorted({tuple(sorted(e)) for p in (faces[i],faces[j]) for e in p})
        for run in range(12):
            jets, speed2 = {}, {}
            for h,e in enumerate(links):
                base = elements[(h+run)%4]
                # Include shared-only, outer-only and mixed directions.
                speed = ((h+run)%5)-2
                if (run%3 == 0 and e != common) or (run%3 == 1 and e == common):
                    speed = 0
                axis = [0]*4
                axis[1+(h+run)%3] = Q(speed,2)
                first = mul(axis,base)
                jets[e] = base, first, mul(axis,first)
                speed2[e] = speed**2
            x, dx, ddx = walk_derivatives(faces[i], jets)
            y, dy, ddy = walk_derivatives(faces[j], jets)
            hessian = signed_pair(ddx,y) + 2*signed_pair(dx,dy) + signed_pair(x,ddy)
            merged_dd = add(mul(ddx,inv(y)), mul(dx,inv(dy)), mul(dx,inv(dy)),
                            mul(x,inv(ddy)))[0]
            traces_dd = 4*(ddx[0]*y[0] + 2*dx[0]*dy[0] + x[0]*ddy[0])
            assert hessian == (16*merged_dd-3*traces_dd)/Q(39)
            assert abs(hessian) <= Q(32,39)*(sum(speed2.values())+speed2[common])


def main():
    pair_controls()
    second_derivative_controls()
    for periods in [(4,4,4),(4,4,6),(6,6,6)]:
        audit_torus(periods)
        for u, expected in [(Q(1,32),Q(215,3744)), (Q(2,63),Q(850783,106142400))]:
            c = gap_certificate(periods,u)
            assert c["lower_over_alpha"] == expected
            print("YM36 floor", periods, u, expected)
        stopped = gap_certificate(periods,Q(1,8))
        assert stopped["status"] == "UNKNOWN" and stopped["defect"] == Q(7,8)
        assert ym35(periods,Q(1,32))["lower_over_alpha"] == Q(23,468)
    assert gap_certificate((5,4,4),Q(1,64))["lower_over_alpha"] > Q(4385,29952)
    # At 2/63 the old curvature and ball conditions exclude all radii.
    u, cut = Q(2,63), Q(21223,100000)
    old = ym35((4,4,4),u)
    rest = old["linear"]*cut + Q(2,3)*cut**2
    assert old["linear"] + Q(4,3)*cut < 1 and cut-rest < old["defect"]
    assert Q(1,2)-16*u/3-2*min(cut,old["hessian_defect"]+rest) < 0
    print("YM36 controls passed")


if __name__ == "__main__":
    main()
