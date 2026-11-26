# DRNAS ELEMENT-02 — frontier research module

Standalone research extension on a branch of the canonical CORE repository.
It does not change CORE's SAT kernel, invoke CORE, or depend on an unverified YM API.
It uses the ELEMENT-01 coefficients as a fixed prior comparator.
No CDCL fallback; the empirical search is numerical, and the point-Dirac
derivative is checked symbolically with SymPy.

## Reproduce

```sh
python -m pip install numpy scipy sympy mpmath rdkit==2025.9.4
OPENBLAS_NUM_THREADS=1 python research/element02/frontier.py > frontier.json
OPENBLAS_NUM_THREADS=1 python research/element02/dirac.py > dirac.json
```

## Locally executed results (2026-11-27)

RDKit 2025.09.4 isotope table, 3029 records, 1983 training (Z 8–70),
637 validation (Z 71–88), 409 final holdout (Z 89–118).
462 shell features; 3180 candidate evaluations, sequential validation selection.
No predefined magic-number list. Selected Gaussian centers N=82, Z=28, N=68.
The coefficient sign for Z=28 is negative; no claim of rediscovering all shell physics.
RMSE of total binding energy (MeV):

| Set | ELEMENT-01 fixed | Fitted liquid drop | ELEMENT-02 |
|---|---:|---:|---:|
| Z 89–118 | 27.4623 | 16.6045 | 8.6985 |
| Z 104–118 (85 records, subset) | 28.7704 | 22.7594 | 12.2497 |

Finite-radius one-electron Dirac calculation: first matching root at E=-m_e c^2,
uniform spherical charge, radii 4,6,8,10,12 fm; critical Z respectively
161.59306891,165.23792725,168.29717950,170.99727928,173.44987520.
Two integration tolerances give differences below 5e-10 in these runs.
This is numerical convergence, not a physical uncertainty estimate.

## Limitations

RDKit masses were not individually audited against measured/extrapolated AME flags.
Atomic electron binding corrections were not applied. The model is not validated for
new nuclei or half-lives. The point-charge Dirac expression becomes non-real past
Z=1/alpha; finite-radius calculations concern the one-electron spectral threshold,
not existence of an atom or nucleus. No screening or QED effects included.
The approximately Z=170 threshold is known in the literature, not an original discovery:
https://doi.org/10.1016/j.physrep.2023.09.004

Future native integration: connect JSON rule candidates, evidence and domain failures
to a documented YM/CORE interface after locating and validating its actual source.
Never treat an empirical fit or a numerical residual as a formal physical proof.
