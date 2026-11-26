# ELEMENT-03 — charge-profile frontier

Standalone research module, not integrated into the CORE SAT solver or YM.
Run:
```
pip install numpy scipy sympy mpmath
OPENBLAS_NUM_THREADS=1 python research/element03/drnas_element03.py > results.json
python research/element03/drnas_element03_proof.py > proof.json
```

Executed locally: 51 model calculations, 205 candidate formula structures,
154 accepted by grid-based admissibility tests. Training 14 rows (shell/uniform),
validation 5 (p=1), holdout 10 (p=2,4), audit 12, stress 10. Data are synthetic
solutions of the prescribed one-electron Dirac model, NOT experiments.
Selected formula: sqrt((Z alpha)^2-1) ≈ 3.428224336326247/L -
1.9993352709346592/L^2, L=ln(reduced electron Compton wavelength / RMS charge radius).
RMSE Z: training 0.1037974, validation 0.1600771, holdout 0.3500131,
stress 0.6277463; largest root difference under tolerance/check changes 1.045e-7.
At radius 8 fm the six-profile threshold spread is 8.22982 for outer radius,
0.32417 for RMS radius. RMS was a researcher-supplied coordinate, not discovered
automatically. The formula is empirical and its leading log coefficient differs
from the known pi asymptotic.

Exact identity for p integer >=0: phi_p(x)=sum_{k=0}^{p+1} binomial(2k,k)/4^k
(1-x^2)^k. The researcher generalized a pattern of symbolic differences;
21 exact polynomial checks, and a general proof using the Poisson recurrence.
Not a claim of novelty. See Popov/Zeldovich (1972)
https://www.ufn.ru/en/articles/1972/6/a/citedby.html and Kuleshov et al. (2015)
https://www.ufn.ru/en/articles/2015/8/d/.

The numerical spectral threshold of a bare ion is not the maximum atomic number
of a chemically realizable or nuclear-stable element. No nuclear dynamics,
QED screening, or many-electron chemistry. No claim of new element.
