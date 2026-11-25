"""Reproduce the YM32 tori, the volume sweep, and the singular Wilson control."""
from fractions import Fraction as Q

from flat_words_tests import grid, permute
from flat_words_verify import I, inv, mul
from ym33_torus_gap import bounds


def curvature_control(mesh, width, height, hx, hy, parallel=False):
    # Rational SU(2) rotations tending to identity along perpendicular axes.
    cx, sx = (1 - hx*hx)/(1 + hx*hx), 2*hx/(1 + hx*hx)
    cy, sy = (1 - hy*hy)/(1 + hy*hy), 2*hy/(1 + hy*hy)
    horizontal = (cx, sx, 0, 0)
    vertical = (cy, sy, 0, 0) if parallel else (cy, 0, sy, 0)
    transport = {}
    for x in range(width):
        for y in range(height):
            a = x*height + y
            for b, value in [(((x+1) % width)*height+y, horizontal),
                             (x*height+(y+1) % height, vertical)]:
                transport[a, b], transport[b, a] = value, inv(value)
    defect = Q(0)
    for face in mesh["faces"]:
        walk = I
        for a, b in zip(face, face[1:] + face[:1]):
            walk = mul(walk, transport[a, b])
        defect += 1 - walk[0]
    expected = 0 if parallel else 2 * sx**2 * sy**2
    assert defect == len(mesh["faces"]) * expected
    return defect / len(mesh["faces"])


def main():
    for width, height in [(4, 4), (5, 4), (6, 6), (8, 8), (12, 12)]:
        mesh = grid(width, height, True, True)
        # Match the two archived YM32 test seeds exactly.
        seed = {(4, 4): 325, (5, 4): 326}.get((width, height), 33 + width)
        relabelled = permute(mesh, seed)
        exact = bounds(mesh, 1, 0)
        assert exact["lower"] == exact["upper"] == 3
        for ratio in [Q(1, 32), Q(1, 8), Q(1)]:
            result = bounds(mesh, 1, ratio)
            assert result == bounds(relabelled, 1, ratio)
            assert 0 < result["lower"] <= result["upper"]
            scaled = bounds(mesh, 3, 3 * ratio)
            assert all(scaled[p] == 3 * result[p] for p in ("lower", "upper"))
            lower = (str(result["lower"]) if result["variational_lower"] >= result["lower"]
                     else f'3*2^(-{result["heat_exponent"]})')
            print(f'{width}x{height} k/alpha={ratio} lower={lower} upper={result["upper"]}')
        if (width, height) in [(4, 4), (5, 4)]:
            for h in [Q(0), Q(1, 32), Q(1, 16), Q(1, 8)]:
                curvature_control(mesh, width, height, h, h)
                curvature_control(mesh, width, height, Q(1, 3), h)
                assert curvature_control(mesh, width, height, Q(1, 3), h, parallel=True) == 0
    # A triangle changes the electric threshold, a boundary changes the parity proof.
    for invalid in [grid(3, 4, True, True), grid(4, 4, False, False)]:
        try:
            bounds(invalid, 1, Q(1, 32))
        except ValueError:
            continue
        raise AssertionError("geometry outside proof accepted")
    print("YM33 controls passed")


if __name__ == "__main__":
    main()
