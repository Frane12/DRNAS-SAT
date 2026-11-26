# YM38 · Does doubling the wavelength halve the excitation energy?

Measured a moving scalar Wilson-loop channel in pure SU(2), using a four-dimensional Wilson-action simulation at β=2.35. Each periodic box has the same action, lattice spacing in lattice units, and temporal extent 16. The Fourier mode makes one full oscillation across each box. The Euclidean decay gives a finite-time estimate of energy above the vacuum. Spatial sizes change from 4 to 8 to 16; no continuum extrapolation or physical scale calibration was performed.

| Spatial size | a times momentum | Measurements used in final estimate | aE from separations 1 and 2 | aE from separations 2 and 3 |
|---|---:|---:|---:|---:|
| 4³ | 1.571 | 131072 | 2.165 ± 0.032 | 1.898 ± 0.206 |
| 8³ | 0.785 | 8192 | 1.322 ± 0.028 | 1.217 ± 0.103 |
| 16³ | 0.393 | 3072 | 1.216 ± 0.041 | 1.165 ± 0.131 |

Errors in this table are one standard error from nonoverlapping 32-sweep blocks and delete-one-block jackknife. A 64-sweep block gives late-window errors 0.206, 0.103, 0.127. The cold/hot series and the two neighboring effective-energy windows pass the checks in the [protocol](protocol.md). The final sizes use independent data; ratios by first-order error propagation are 0.641 ± 0.088 (8/4) and 0.957 ± 0.135 (16/8). Successive halvings would produce ratios near 0.5 in a linear, small-momentum dispersion regime. The first box is particularly small; lattice dispersion and finite-volume effects can be large there.

All earlier stages are included. The pilot produced late-window effective energies of 0.594 ± 0.367, 1.291 ± 0.323 and 1.210 ± 0.240 for L=4,8,16; only the last passed the plateau screen. The independent confirmation at L=4 gave 1.416 ± 0.373 and also failed. The longer separate L=4 run in the table was chosen because this correlator lost signal particularly quickly. No pooling of passed and failed estimates.

**Interpretation.** Doubling the longest wavelength between the two larger boxes gave energies compatible with one another at this temporal resolution. No repeated halving was observed in this channel. A scalar loop has limited spectral overlap, and the effective energy can exceed the lightest physical energy with that momentum. The C(4) signal is approximately 0.6, 3.0 and 1.1 standard errors from zero on the final samples. The data cannot establish a stable asymptotic plateau at later times across all three boxes, exclude a weakly coupled lighter mode, or prove a mass gap. The displayed errors quantify sampling, not those systematic uncertainties. With no repeated downward scaling signal, the conditional matched-spacing refinement stage was not triggered.

The three compressed CSVs hold per-chain block means. From this directory run `python3 controls.py` to recompute the results. The [protocol](protocol.md) gives seed, action, operator, source code and rerun details. A direct Monte Carlo update generated these measurements; the SAT solver and YM37 series did not supply configurations or set the dispersion. The [Morningstar–Peardon paper](https://arxiv.org/abs/hep-lat/9901004) gives background on Wilson-loop energies in pure gauge theory. Its SU(3) measurements are separate from this SU(2) pilot.
