"""Physical excitation energy through second order in u=|k|/alpha."""
from fractions import Fraction as Q


def channels():
    # Each contribution is the Haar squared norm divided by 3-E_intermediate.
    vacuum = Q(1, 3)
    single_spin_one = -Q(1, 5)
    disjoint = -Q(1, 3)
    shared = Q(1,4)/(3-Q(9,2)) + Q(3,4)/(3-Q(13,2))
    return vacuum, single_spin_one, disjoint, shared


def coefficients(periods):
    if len(periods) != 3 or any(type(n) is not int or n < 5 for n in periods):
        raise ValueError("three periods >= 5 required to exclude length-four winding loops")
    count = 3 * periods[0]*periods[1]*periods[2]
    vacuum, self_term, disjoint, shared = channels()
    ground_shift = -Q(count,3)
    neighbors = 12
    diagonal = vacuum+self_term+(count-1-neighbors)*disjoint+neighbors*shared-ground_shift
    hopping = vacuum+shared
    return count, diagonal, hopping


def gap_test(periods, coupling):
    """Return an expansion and, when separated, a rigorous finite-volume enclosure."""
    if not isinstance(coupling, (int,Q)):
        raise TypeError("use an exact rational coupling")
    u = abs(Q(coupling))
    count, diagonal, hopping = coefficients(periods)
    minimum = diagonal + 12*hopping
    prediction = 3 + u*u*minimum
    h = 2*count*u
    interval = None
    if 2*h < Q(3,4):
        error = sum(2*h**3/(d*(d-2*h)) for d in (Q(3), Q(3,4)))
        interval = (prediction-error, prediction+error)
    return dict(second_order_coefficient=minimum, second_order_gap=prediction,
                full_gap_interval=interval)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("periods", nargs=3, type=int)
    parser.add_argument("u", type=Q)
    args = parser.parse_args()
    print(gap_test(args.periods, args.u))
