"""Volume-independent SU(2) gap certificates for rectangular square tori."""
from fractions import Fraction as Q


def certificate(width, height, coupling):
    """Normalize energies by alpha and use u=abs(k)/alpha."""
    if type(width) is not int or type(height) is not int or min(width, height) < 4:
        raise ValueError("periods must be integers >= 4")
    if not isinstance(coupling, (int, Q)):
        raise TypeError("use an exact rational coupling")
    u = abs(Q(coupling))
    alternating = width % 2 == height % 2 == 0
    if alternating:
        wilson, self_term, merged, radius = 4, 9, 4, Q(1, 60)
    else:
        wilson, self_term, merged, radius = 8, 27, 16, Q(1, 5)
    spin_one = wilson**2 - merged
    shared = spin_one / Q(2)
    other = (3 * merged + spin_one) / Q(2)
    defect = (u / 3)**2 * (2 * self_term + 6 * other + shared)
    bilinear = Q(2, 3)
    linear = 2 * bilinear * 2 * wilson * u
    slack = radius - (defect + linear * radius + bilinear * radius**2)
    lipschitz = linear + 2 * bilinear * radius
    lower = Q(1, 2) - 8 * u / 3 - 2 * radius
    accepted = slack >= 0 and lipschitz < 1 and lower > 0
    return dict(orientation="alternating" if alternating else "coordinate",
                radius=radius, defect=defect, linear=linear, slack=slack,
                lipschitz=lipschitz, gap_lower=lower if accepted else None)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("width", type=int)
    parser.add_argument("height", type=int)
    parser.add_argument("coupling", type=Q, help="k/alpha, e.g. 1/32")
    args = parser.parse_args()
    for key, value in certificate(args.width, args.height, args.coupling).items():
        print(f"{key}={value}")
