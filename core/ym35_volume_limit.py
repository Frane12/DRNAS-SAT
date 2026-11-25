"""YM35 analytic certificate for the SU(2) Hamiltonian on 3D spatial tori."""
from fractions import Fraction as Q


def certificate(periods, coupling):
    if len(periods) != 3 or any(type(n) is not int or n < 4 for n in periods):
        raise ValueError("three integer periods of at least four required")
    if not isinstance(coupling, (int, Q)):
        raise TypeError("use an exact rational k/alpha")
    u = abs(Q(coupling))
    alternating = all(n % 2 == 0 for n in periods)
    w = 4 if alternating else 8
    self_term = 9 if alternating else 27
    merged_max = 4 if alternating else 16
    merged_min = 4
    shared_cost = (w*w - merged_min) / Q(2)
    outer_cost = w*w / Q(2) + merged_max
    defect = (u/3)**2 * (4 * self_term + 36 * outer_cost + 6 * shared_cost)
    hessian_defect = (u/3)**2 * (8 + 42 * Q(24, 13))
    radius = Q(3, 16)
    linear = Q(7, 6) * 4 * w * u
    nonlinear = Q(2, 3) * radius**2
    rest = linear * radius + nonlinear
    slack = radius - defect - rest
    lipschitz = linear + Q(4, 3) * radius
    lower = Q(1, 2) - Q(16, 3) * u - 2 * min(radius, hessian_defect + rest)
    # The local Wilson trial uses 4 exp(4 pi K); 4 pi K <= 1 gives <12.
    derivative = 4*u/3 + radius/6
    upper_ok = 4 * Q(22, 7) * derivative <= 1
    passed = slack >= 0 and lipschitz < 1 and lower > 0 and upper_ok
    return dict(status="BOUNDED" if passed else "UNKNOWN",
                orientation="alternating" if alternating else "coordinate",
                defect=defect, hessian_defect=hessian_defect, slack=slack,
                linear=linear, lipschitz=lipschitz,
                lower_over_alpha=lower if passed else None,
                upper_over_alpha=Q(12) if passed else None)


def physical_interval(periods, spacing, g_squared):
    if not all(isinstance(v, (int, Q)) for v in (spacing, g_squared)):
        raise TypeError("use exact rationals for spacing and g squared")
    a, g2 = Q(spacing), Q(g_squared)
    if min(a, g2) <= 0:
        raise ValueError("spacing and g squared must be positive")
    c = certificate(periods, 4/g2**2)
    if c["status"] == "UNKNOWN":
        return None
    alpha = g2/(2*a)
    return (alpha*c["lower_over_alpha"], alpha*c["upper_over_alpha"])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("periods", nargs=3, type=int)
    parser.add_argument("u", type=Q, help="k/alpha")
    args = parser.parse_args()
    for key, value in certificate(args.periods, args.u).items():
        print(f"{key}={value}")
