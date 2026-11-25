# DRNAS CORE 0.1.2 — validation, 25 November 2026

The merged automaton solved **50/50 fresh instances and 27/38 archived regression cases** in the final local paired pilot. All accepted answers passed a separate checker. There were no incorrect/rejected terminal answers or solver errors across 528 attempts.

## Final paired pilot

One repetition; 1 second solve budget; one logical CPU per solver; serial execution with rotating solver order. The 50 fresh instances were generated after freezing source and harness, from ten prespecified **known families**. The 38 archived instances are regression tests, not blind data. Duplicate normalized archived formulas were removed. External wall tolerance: 50 ms; process kill tolerance: 100 ms. Auditing has a separate five-second budget and is excluded from solve-time PAR2. Runtime noise and the short cap limit timing conclusions.

| Solver | Fresh 50 | Replay 38 | Total 88 | Total PAR2, seconds |
|---|---:|---:|---:|---:|
| **DRNAS CORE 0.1.2** | **50** | **27** | **77** | 0.3044 |
| FUSION1 | 49 | 28 | 77 | 0.2816 |
| UNIFIED3 | 50 | 24 | 74 | 0.3506 |
| GENERAL14 contract | 39 | 16 | 55 | 0.7757 |
| Kissat | 50 | 30 | 80 | 0.2221 |
| CaDiCaL | 50 | 28 | 78 | 0.2478 |

CORE's 77 accepted results consist of 42 independently checked SAT models, 24 DRUP UNSAT proofs, four GF(2) certificates and seven Hall certificates. GF(2)/Hall are independently checked structural certificates, not standard DRAT/LRAT. The integrated symbolic engine also supports a separate RUP+symbolic certificate type; it was not needed for an accepted CORE result in this panel.

Relative to FUSION1, CORE gains N24 and loses F03 at the one-second cap. Relative to UNIFIED3, it gains F01/F11/F21/F22 and loses F26. CORE therefore does **not** yet preserve the union of all predecessors' individual wins at the same short budget. Kissat remains ahead on this mixed panel. The next development target is method selection and budget allocation within CORE, especially F03 and F26.

Raw measurements: [release summary](validation/release/summary.json), [per-attempt CSV](validation/release/runs.csv), [source freeze](validation/release/freeze.json), [input manifest](validation/release/manifest.json). [Fresh/regression inputs and accepted CORE evidence](validation/core-evidence-0.1.2.zip) include the original hashes and logs. The full external-reference proof traces are produced by the benchmark workflow; the repository archive contains CORE evidence only.

## Public-source WORDLIFT integration replay

The **merged CORE 0.1.2 itself solved 23/23 selected public original CNFs**, all SAT with independently checked complete models. This is a local end-to-end replay of the previously tested WORDLIFT23 corpus, with fresh downloads checked by SHA256. It is **not blind** and covers only the selected linear-equations/xor-shifting families. No external reference solver was rerun concurrently for this replay, so the older reference timings are not a new paired comparison with CORE.

One logical CPU, serial, 15-second solve cap per input and separate five-second audit cap. Total solver wall time was 39.257 s; separate acceptance checks took 0.864 s. [Summary](validation/public23/summary.json), [per-instance results](validation/public23/runs.jsonl), [source URLs and hashes](validation/public23/manifest.json), [accepted models](validation/public23/models.zip).

```bash
python3 core/public_replay.py download
python3 core/public_replay.py run
```

## Soundness and integration checks

- 420 formulas checked against complete truth-table enumeration, including all 256 subsets of the eight full-width clauses on three variables and randomized/adversarial small formulas.
- 484 accepted native invocations, including mode checks, 16 signed/permuted GF(3) instances and two end-to-end word circuits with distinct carry constructions. Every answer separately checked.
- 81 exhaustive local-factor projection/equivalence checks; 398 generated RUP lines independently validated.
- 12 negative input/evidence checks rejected, including malformed DIMACS, invalid models/proofs, unsupported capacity claims and input/output alias protection.
- A separately replayed symbolic contradiction checks the custom symbolic acceptance path.

Tests support soundness of these bounded experiments; they are not a formal proof of every implementation path or a guarantee on arbitrary inputs. The symbolic auditor and RUP checker have explicit resource bounds. Timeouts and audit exhaustion remain unresolved.

## Earlier integration panels

The first frozen 0.1.0 panel gave CORE 49/50 fresh and 26/38 replay, versus FUSION1 49/50 and 28/38. It exposed the cost of promoting intermediate proof-helper clauses into active constraints. Version 0.1.1 separates the proof ledger from selected active consequences, restores the broader Hall/GF(2) recognizers and the UNIFIED projection/repair path. Its separate fresh panel yielded 50/50 and 27/38.

Version 0.1.2 then imports the latest WORDLIFT23 kernel and repeats the final paired pilot on another freshly generated 50 instances. Earlier panels are retained as development diagnostics and are **not** presented as blind tests of later revisions. Their measured results appear under `validation/pilot/` and `validation/final/`.

## Module selection evidence

- [WORDLIFT23](https://github.com/Frane12/DRNAS-SAT/actions/runs/45593083523): source-pinned predecessor comparison on 23 selected public formulas from linear-equations/xor-shifting. WORDLIFT solved 23/23 SAT with checked models; its prior variant solved 14/23. This is narrow family-specific evidence, not a general competition ranking.
- [UNIFIED8](https://github.com/Frane12/DRNAS-SAT/actions/runs/45593877409): the hybrid factor method solved 45/50 fresh versus 44/50 for the baseline, while all arms remained at 0/8 on old failures. Its exact factor/proof machinery is included; this does not establish general autonomous learning.
- GENERAL14 delayed memory tied the value/store controls on the combined earlier 200-case test. Memory remains optional and local to one solve.

The native solver never invokes a reference solver. Bounded case splitting, local truth-table enumeration and ROBDD elimination are present; “no CDCL” does not mean “no search” or polynomial-time general SAT.
