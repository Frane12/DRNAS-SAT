# Direct source-table certificates in DRNAS CORE

Experimental CNF modes based on the published 0.1.2 SAT release
`012315d0a62443667aad69fe0dd42c72dd375630`. All three arms use the same
binary, factor discovery, ordinary solve schedule and source CNF. No CDCL
solver is invoked. The default continues to emit the original certificate types.

Run from the repository root:

```sh
bash core/build.sh
python3 core/tests.py
python3 core/experiments/direct-table/test_certificate.py
python3 core/run.py input.cnf new.cert --mode table-first --seconds 1
python3 core/experiments/direct-table/benchmark.py new-results
python3 core/experiments/direct-table/summarize.py new-results
```

## Evidence and limits

The factor stage already enumerates at most 16 variables and projects onto
at most eight boundary variables. A message may use a group of at most 700
original clauses. The producer checks the candidate on every satisfying row
of the source group. If discovery used derived premises or globally forbidden
rows, a claim must still follow from the source premises alone. If the
source-only table cannot be completed within the time slice, the table message
is unavailable. At most 24 claims are recorded per solve. In table-first mode
an ineligible claim can still take the existing RUP route. In table-fallback
mode a failed attempted trace can take the direct route if time remains.

An UNSAT envelope begins with `drnas-table-v1 SHA256` for the exact DIMACS
bytes. Each `i ... 0` selects 1-based source clause IDs after skipping
tautologies; duplicates retain their places. Each following `t ... 0` claims a
clause entailed by that group. Its variables identify the boundary needed for
the claim. The Python auditor rebuilds truth columns over **all** variables
in the premises, retains every satisfying extension, and rejects any allowed
row falsifying the claim. All premises come from the source, so the checked
lemmas may be installed before replay of the suffix, regardless of discovery
order. After the `suffix` marker the existing checker must accept a complete
DRUP or RUP+symbolic refutation against the source plus those lemmas. A SAT
answer still requires a complete model of the original CNF. TABLE+DRUP and
TABLE+RUP+SYMBOLIC are project certificate formats.

The focused end-to-end test uses two guarded blocks and a binary implication
chain. One block forces x1 and the other forces not x32. CORE emits nonempty
table lemmas, and the independent verifier accepts the full proof and rejects
the same suffix with the table premises removed. This isolates actual use of
a lemma in a proof. The baseline also solves the example.

## Paired test

88 archived source-pinned release inputs, three repetitions, one logical CPU,
rotated arm order, one second per solve and a separate five-second audit.
All 88 are replay data for this experiment, including the 50 historically
labelled fresh. `runs.jsonl` inside the results archive contains error/status,
timings and available telemetry for every attempt. Trace failure counts cover
calls that actually entered the bounded trace builder; candidates skipped
before entry and processes killed before reporting are outside that count.
Table messages count recorded exports, not causally necessary lemmas. The
suffix ablation in `summary.json` tests necessity for the recorded terminal
UNSAT proof only. It does not test whether the solver could find another proof.

| Mode | Solved of 88 by repetition | Same cases solved all three times | Recorded direct exports |
|---|---|---:|---:|
| default | 76 / 75 / 75 | 75 | 0 |
| table-fallback | 76 / 75 / 76 | 75 | 0 |
| table-first | 76 / 75 / 76 | 75 | 293 on 22 inputs |

All three modes solved the same 75 stable cases. All 2,696 measured baseline
trace attempts succeeded. Direct-first produced six accepted TABLE+DRUP
refutations (F09 and F11 in three repetitions). All six archived suffixes
also passed on the original CNFs without the table lemmas. On this small
retrospective panel, direct tables changed proof construction without
establishing a repeatable gain in solved inputs. The positive chain diagnostic
shows a proof which actually needs the direct step.

[Machine-readable counts and ablations](summary.json) ·
[Per-attempt log, certificates, environment and chain example](evidence.zip).
