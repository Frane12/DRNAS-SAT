# DRNAS SAT

**Structural Mathematics & Proof-Certified SAT Research**

Independent SAT research project led by **Frane Drnas**, Croatia.

DRNAS SAT explores proof-first Boolean satisfiability (SAT): detect mathematical structure in an original CNF, derive sound bounds and contradictions, and generate independently checkable SAT/UNSAT evidence. Native C++ solvers, mathematical modules, and benchmarks are kept together with reproduction protocols.

## Research directions

- **Native CDCL:** C++ core, propagation, learning, guarded mathematical inference.
- **PCMAX / scheduling:** weighted capacities, source-checked BDD implications, VeriPB UNSAT proofs.
- **Graph structure:** clique, coloring, matching, Hall/max-flow and integer-cover reasoning.
- **XOR / GF(2):** parity extraction, linear algebra and hybrid certification.
- **Module communication:** exchange proof-carrying structural lemmas.
- **Reproducibility:** source hashes, one logical CPU, holdouts, independent checkers.

## Selected verified experiments

| Experiment | Result and limitations | Original evidence |
|---|---|---|
| PCMAX Weighted VeriPB2, 2026-11-15 | 11 independently VeriPB-verified UNSAT cases among 20 retrospective source CNFs; 9 SAT-labeled controls returned UNKNOWN | [Run 43719601339](https://github.com/Frane12/AndroidGameTest/actions/runs/43719601339) |
| PCMAX m14-3640-14524 | A 557,597-byte proof was accepted by VeriPB 3.0.2; weighted demand 31 > capacity 30 | [Local standard proof](evidence/pcmax-weighted2/05/weighted.pbp) |
| GRAPH-CLIQUE real67, 2026-11-16 | Graph plus MATH5: 22 verified outcomes in 134 attempts on 67 original CNFs × 2; retrospective, no secure general speedup | [Run 43886450488](https://github.com/Frane12/AndroidGameTest/actions/runs/43886450488) |
| IPG5D | 9 source-recognized odd-wheel UNSAT cases with short standard cutting-plane VeriPB certificates | [Run 43868313721](https://github.com/Frane12/AndroidGameTest/actions/runs/43868313721) |
| MATCH3 | 18 restricted Hall witnesses on generated original CNFs, independently project-checked; **not** standard VeriPB/DRAT | [Run 43862296099](https://github.com/Frane12/AndroidGameTest/actions/runs/43862296099) |

**Scientific scope.** These are results on restricted or retrospective families. They do not prove P = NP, a general polynomial-time SAT algorithm, or first discovery of PCMAX m14 UNSAT. The instance had already been reported UNSAT in a 2024 paper. The DRNAS contribution under study is the independent structural proof and its generalization.

## Repository map

- **src/** — native C++ solvers and mathematical guards.
- **research/** — mathematical methods, producers, checkers and protocols.
- **tests/** — regression and contract tests.
- **experiments/** and **mi_ltm*/** — experimental sources.
- **docs/** — mathematics, experiment results and original branch manifest.
- **evidence/** — selected proof references and source provenance.
- **third_party/** — dependencies retained with attribution.

See [PCMAX documentation](README_PCMAX.md), the [independent proof registry](docs/VERIFIED_PROOF_REGISTRY.md) and the [source branch inventory](docs/SOURCE_REFS.csv).

## Verification policy

An UNSAT result must be tied to the exact CNF and either accepted by an independent standard checker, or explicitly identified as a restricted project-checker certificate. A successful CI run and a solver exit code alone do not imply proof acceptance. SAT requires a checked model. Report all timeouts and failures, keep training distinct from validation and holdout, and compare end-to-end execution with a single logical CPU per solver.

## Provenance

Research began in experimental branches of [Frane12/AndroidGameTest](https://github.com/Frane12/AndroidGameTest). This independent repository is the SAT-only home. Initial migration uses a documented 2026-11-17 baseline and overlays missing modules from other branches. Old GitHub Actions logs and artifacts remain at their original URLs; historic runs cannot be moved with Git commits. Exact old source commits remain linked in the migration inventory.

[Migration script](scripts/import_from_androidgametest.sh) · [Original project](https://github.com/Frane12/AndroidGameTest)

## Attribution

DRNAS SAT project: **Frane Drnas**. External SAT solvers, mathematical techniques, proof-checking systems, and third-party code remain credited to their respective authors. Research in progress: transparent evidence takes priority over promotional claims.
