# ATLAS-SEPARATOR3 — independent proof audit (23 Nov 2026)

**Experimental branch only; no change to main.**

This subdirectory contains a 7-variable, 15-clause original *generated* GRAPH+XOR+PCMAX mixed UNSAT CNF, a 27-line addition-only RUP/DRUP certificate, and a 27-step ASCII LRAT conversion with positive unit-propagation hints.

Standard third-party proof validation is performed in a GitHub Actions job using unmodified upstream `marijnheule/drat-trim`: `drat-trim` and `lrat-check`. Both verifiers must print VERIFIED, and their output must be retained as an artifact. The CI run is the only basis for claiming *external* proof validation.

Scope: one purpose-built generated problem; not 100 fresh source CNFs, not a performance claim, and not a new general SAT method. Local ATLAS3 pilot and its Python source are distributed separately as an archived package.
