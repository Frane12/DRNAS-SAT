# Bounded proof after projection

The new default first tries the projected model. If clauses remain violated, it probes both signs of up to 128 residual variables and records proved units. A bounded binary case tree then examines up to four candidates from short active clauses at each node. The tree has at most six decisions per path and 512 propagation calls. The two stages have soft budgets of 20 and 25 ms within the solver deadline. Completing a propagation or building a watch index can take the stage past its soft limit. Temporary units feed the tree. The original witness repair receives its original residual and seed when the tree remains open. The proof log contains the projection prefix and RUP steps through the empty clause. There is no CDCL backend.

## Frozen transfer protocol

Use the published candidate commit as the seed. Draw four original CNFs from each of six SATLIB archives in `corpus.TRANSFER`. All six are outside the two circuit fault families used to develop this step. Exclude names and available CNF fingerprints from the parent development audit, the previous 36 cases and the six additional fault controls. No filename, family, seed, baseline result or target truth enters either solver. Restore the exact set from its published manifest. Keep the previous 36 cases and the other six fault controls separate from the new transfer score.

Use the same serial one-CPU, three-repetition, 3-second protocol as the parent. Rotate all four arms across cases and repetitions. Run the integrated solver, the exact parent executable, Kissat 4.0.3 and CaDiCaL 2.2.0 with proof output. Count coverage only for three verified answers. PAR-2 charges six seconds to each unresolved or unverified trial. Record solving and checking separately. The primary comparison includes the cost of the new stage and its interaction with the remaining time for witness repair. This experiment measures the pre-repair proof step. Adaptive mid-repair switching is a separate hypothesis.

```sh
T=research/toolbox20_native
python3 "$T/corpus.py" --restore "$T/postprojection_results/manifest.json" --out transfer-inputs
python3 "$T/bench.py" --manifest "$T/postprojection_results/manifest.json" --corpus transfer-inputs --out transfer-run \
  --drnas ./drnas-new --parent ./drnas-parent --kissat ./kissat --cadical ./cadical --checker ./drat-trim
```

Compile the parent at `9fd4539e47fca1b7dd76615740023ec3a60fc0c9` and the new source with the same compiler flags described in [the solver README](README.md).

## Results and replay

The [results report](postprojection_results/REPORT_HR.md) includes per-instance timings and the independent proof archives. To reproduce the previous 36 and six BF/SSA controls on this branch, first restore the parent corpus, then replay the integrated binary.

```sh
T=research/toolbox20_native
python3 "$T/corpus.py" --restore "$T/results/manifest.json" --out parent-inputs
python3 "$T/replay_postprojection.py" --previous "$T/results/manifest.json" --corpus parent-inputs --drnas ./drnas-new --checker ./drat-trim --out check-replay
```
