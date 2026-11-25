# DRNAS TOOLBOX20 native experiment

This standalone C++20 solver reads an anonymous DIMACS input and returns a checked model, a refutation, or UNKNOWN. The executable links OpenSSL for source digests. It never calls a reference solver. The archived Python TOOLBOX20 used guarded proof by cases and closed 14 of 66 earlier residuals. This implementation starts from the original formula and can reconstruct models after projecting a residual.

* TOOLBOX16/17 inspired the exchange of proved units and binary implications. The repository's MATH4 extracts complete original parity half-cubes and independently checkable contradictions. A consistent triangular system now also supplies a candidate model. The existing signed clause-Hall rule can certify a capacity deficit.
* TOOLBOX18/19 inspired bounded short resolution with reuse of prior conclusions. TOOLBOX20 supplies the covering-disjunction proof: under a guard, each live alternative must imply the conclusion. Auxiliary clauses make the derivation replayable as DRUP. Native watches persist across probes. The candidate does not train a rule bank during evaluation.
* TOOLBOX02/07 inspired exact existential elimination with reverse model reconstruction. A bounded pair product, maximum resolvent width and limited growth control elimination. At the first remaining hard residual, an incremental single-flip witness constructor works on that residual. Reverse substitution then restores all eliminated variables. Every reported SAT assignment is checked against the input. The archive's LP, ROBDD and Python memory bank are outside this port.

## Build and run

From the repository root:

```sh
c++ -std=c++20 -O3 -DNDEBUG research/toolbox20_native/solver.cpp -lcrypto -o drnas-toolbox20
./drnas-toolbox20 input.cnf evidence 3
```

The optional CMake target is `drnas-toolbox20`. CLI exit codes are 10, 20, 0 and 2 for SAT, UNSAT, UNKNOWN and error. Evidence for a clausal refutation is text DRUP. GF(2) and Hall certificates use existing source-hash-bound JSON formats and independent checkers. Verification is outside the timed solver for all three arms. Bounded deductions and model repair can leave either truth value unresolved.

## Prospective benchmark protocol

1. Publish the candidate and the draw algorithm before selecting instances. The published commit SHA seeds all member rankings, fresh generation and run order. The candidate sees a neutral filename and only the canonical DIMACS bytes. The generators and source family names are outside the executable.
2. Use three original members each from eight SATLIB collections. Rank by SHA-256 of the freeze, collection and archive member path. Exclude malformed input, duplicate CNF fingerprints, and explicit development-file overlap before running any solver. The comparison previously documented in DRNAS and the available TOOLBOX archives is limited to explicit filenames and recoverable CNFs. Public provenance is not evidence of global first use. Commit the raw member digests, exact solver-input digests and exclusions. Syntax normalization removes comments and archive trailers. Clause boundaries, order and literals are preserved.
3. Separately draw 12 new formulas from four generators: three sizes each of Tseitin parity, uniform random 3-SAT, graph 3-colouring and duplicated-circuit output constraints. Signs, variables, literals and clauses are shuffled. Previously tested families may recur. Generator parameters and verdicts are never supplied to the solver.
4. Run DRNAS, Kissat 4.0.3 and CaDiCaL 2.2.0 sequentially, pinned to the same logical CPU, three rotated repetitions per input, with a strict 3 s wall-clock cap including process launch, parsing, model and proof output. Default search options for both references, binary proof output. Count SAT only after independent model replay and UNSAT only after independent proof replay. Report mean PAR-2 over every run. UNKNOWN, timeout, errors and uncertified answers cost 6 s. Report per-formula coverage only if all three repetitions verify the same answer. Preserve individual solve and checker times.
5. A separate frozen ablation disables only residual witness repair. Its CPU, input, runs, cap and validation match the primary test. It measures the contribution of repair within this implementation. The archived Python replay is development data and is excluded from all holdout counts.

## Reproduction

The results commit supplies the exact manifest. Restore it and use native binaries built from the pinned commits below.

```sh
T=research/toolbox20_native
python3 "$T/corpus.py" --restore "$T/results/manifest.json" --out data
python3 "$T/bench.py" --manifest "$T/results/manifest.json" --corpus data --out results-local \
  --drnas ./drnas-toolbox20 --kissat /path/to/kissat --cadical /path/to/cadical --checker /path/to/drat-trim
```

Use a separate output directory with `--ablation` to repeat the diagnostic. The runner retains a first verified model or proof for each solver and instance and records the digest on every verified run. Source releases used in this experiment are Kissat `77bc7ea68afe80751a67df8561357f193e160fb1`, CaDiCaL `14593f819cb242082b127396218bd60889409737` and drat-trim `2e3b2dc0ecf938addbd779d42877b6ed69d9a985`. Configure and build the two solvers with their release defaults. Compile drat-trim with `cc -O2 -std=gnu99 drat-trim.c -o drat-trim`.

Public corpus: [SATLIB benchmark collection](https://www.cs.ubc.ca/~hoos/SATLIB/benchm.html).
