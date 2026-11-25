"""Signed adjacent-plaquette estimate for the YM35 physical gap certificate."""
from fractions import Fraction as Q
from ym35_volume_limit import certificate as ym35


def signed_pair(x, y):
    """Second-order unordered-pair contribution divided by t², based at one link."""
    return (4*x[0]*y[0] + 16*sum(a*b for a, b in zip(x[1:], y[1:]))) / Q(39)


def gap_certificate(periods, coupling):
    base = ym35(periods, coupling)
    u = abs(Q(coupling))
    hessian = Q(616,13) * (u/3)**2
    for radius in (Q(3,16), Q(17,80)):
        rest = base["linear"]*radius + Q(2,3)*radius**2
        slack = radius - base["defect"] - rest
        lip = base["linear"] + Q(4,3)*radius
        floor = Q(1,2) - 16*u/3 - 2*min(radius, hessian+rest)
        if slack >= 0 and lip < 1 and floor > 0:
            return dict(status="BOUNDED", lower_over_alpha=floor, radius=radius,
                        hessian_defect=hessian, defect=base["defect"], contraction=lip)
    return dict(status="UNKNOWN", lower_over_alpha=None, hessian_defect=hessian,
                defect=base["defect"], linear_majorant=base["linear"])


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("periods", nargs=3, type=int)
    parser.add_argument("u", type=Q)
    args = parser.parse_args()
    print(gap_certificate(args.periods, args.u))
