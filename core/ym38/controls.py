"""Deterministic analysis controls and checks on the archived block counts."""
import math

from analyze import analyze, cosh_energy, T, SAMPLES


def main():
    for energy in (0.15,0.7,2.1):
        c=[math.exp(-energy*t)+math.exp(-energy*(T-t)) for t in range(6)]
        for t in (1,2,3):
            assert abs(cosh_energy(c[t],c[t+1],t)-energy)<1e-12
    assert cosh_energy(1.,-0.5,2) is None
    assert cosh_energy(1.,1.1,2) is None
    for stage in SAMPLES:
        for n in SAMPLES[stage]:
            row=analyze(n,stage)
            assert row["block32"]["mean"][1]>0
            assert row["status"]=="UNRESOLVED" or not row["flags"]
            print(stage,n,row["status"],row["block32"]["effective"],row["flags"])
    print("YM38 analysis controls passed")


if __name__=="__main__":
    main()
