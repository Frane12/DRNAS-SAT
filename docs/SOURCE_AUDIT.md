# Source and evidence audit · 19 November 2026

The comparison starts from the published DRNAS-SAT tree at `8040855b2a3073122f6f852c69498f71af6b41ce`. The earlier migration used one baseline and seven overlays. Important graph, IPG, XOR and PCMAX implementations were already present. Their final experiment data and several companion implementations were distributed across different branches and Actions artifacts. [Original source refs](SOURCE_REFS.csv) · [Original migration script](../scripts/import_from_androidgametest.sh)

## What was compared

| Inventory | Method and coverage |
|---|---|
| AndroidGameTest | Enumerated all 1,426 advertised branch heads, covering 1,415 distinct head commits. Compared every head's recursive Git tree. The union contained 5,357 distinct paths across the repository. |
| DRNAS-SAT | The starting tree had 749 tracked files. Compared the same repository-relative path and Git blob ID, so a different revision of an existing file is distinguishable from an exact duplicate. |
| Research-path comparison | 3,620 distinct legacy paths under `research/`, `src/`, `tests/`, `experiments/`, `mi_ltm*`, `third_party/`, `docs/`, plus `CMakeLists.txt` and the PCMAX/X-series root READMEs. Of these, 2,928 paths were absent at the start and 2,854 remain archive-only after the selected import. |
| Depth of review | Tree comparison covers branch tips. Source, dependencies, result files and checker output were examined for the work listed below. Historical commits reachable only behind those tips, earlier binary variants, and every historical benchmark were outside the replay. |

The coverage CSV has one row per branch and its immutable commit. In each row, `identical_after + same_path_other_blob_after + absent_path_after = in_scope_paths`. Counts describe paths at that branch tip and overlap across branches. The “after” columns measure source imports against the starting tree. [Per-branch comparison](BRANCH_COVERAGE_2026-11-19.csv) · [Earlier SAT branch index](LEGACY_SAT_BRANCHES.md)

## What was added

74 source, test, data and protocol files were copied byte-for-byte at previously absent paths. The manifest gives the full source commit and Git blob for each file. To retrieve a historical version, use its commit and path in `https://github.com/Frane12/AndroidGameTest/blob/<source_commit>/<path>`. Historical workflows and their input-restoration steps are available in the same pinned commit. [Per-file import manifest](IMPORTS_2026-11-19.csv)

| Research line | Material added or recovered | How to inspect it |
|---|---|---|
| Graph coloring | Eight fixed-graph results, paired real67 results, the first ten-source pilot, its extension-proof replay and a separate family-disjoint trial. One complete K₁₁/ten-color proof pair is packaged for offline use. Existing graph emitters were byte-identical to their selected branch versions. | [CNF and certificate](../evidence/graph-k11) · [All result files](../evidence/ci) |
| HALL3, MATH4 and MATH5 | Native HALL3/CF7 sources, XOR certificate code, frozen input selection, source checker, MATH5 builder, blind dataset harness and compact proof I/O experiment. | [MATH4 findings](../research/math4/EVIDENCE_REAL24_UNSEEN15.md) · [MATH5 build](../research/math5/README.md) · [Proof I/O](../research/math5_proofio) |
| Matching and standard proofs | MATCH4 source-parity producer, separate checker and benchmark. The clique/PHP code and native C++ bridge recover routes from restricted Hall/XOR evidence to standard certificates. | [MATCH4 method](../research/MATCH4_SOURCE_WEIGHTED_PARITY.md) · [DRAT bridge and requirements](../research/structural_drat_bridge/NATIVE_CPP_README.md) |
| TSP-SAT1–3 | Decision encoding, optimizer, 1-tree lower bound, independent Kruskal check and optimality audit. The historical final records cover five seeded small instances and 50 trials across five arms. | [Decision encoding](../research/tsp_sat1/encoding.py) · [Lower bound](../research/tsp_sat3/one_tree.py) · [Final results](../evidence/ci/tsp-sat3.json) |
| IPG7-B and XOR234 | Complete original-CNF proof examples for the weighted Petersen fixture and the first Tseitin grid, plus final records for both experiment series. | [Petersen pair](../evidence/ipg7b-petersen) · [Grid pair](../evidence/xor234-grid5) |
| PCMAX | All eleven published original/proof pairs were already present. The replay command now checks them alongside the three new examples. | [PCMAX registry](VERIFIED_PROOF_REGISTRY.md) · [Replay script](../scripts/replay_certificates.py) |

## Evidence checked for this edition

| Check | Result |
|---|---|
| PCMAX originals | Matched all 11 input and proof SHA-256 pairs to the existing manifest. VeriPB 3.0.2 accepted each original CNF with its archived proof. |
| Fixed-graph originals | Recovered all eight exact sources from the frozen real67 archive and all eight proofs from the graph artifact. Matched input and proof digests to the original eight-source final record. VeriPB accepted all eight. |
| Clique-versus-coloring originals | Regenerated a proof from each of the ten frozen original 2025 CNFs with the checked-in extension emitter. VeriPB accepted all ten. This was a correctness replay. The capped two-repeat numbers on the front page come from the historical CI final. |
| Two graph safety tests | Each ran 80 constructed UNSAT examples and 80 satisfiable controls. Each required ten accepted VeriPB proofs. Both passed, including missing-clause tests. |
| XOR grids and weighted Petersen | Replayed the first archived proof for each grid against its hash-matched original. Regenerated the Petersen fixture from the published generator, checked its original SHA-256 and replayed the archived 150-step proof. All three were accepted. |
| Native and optimization code | Built the MATH4/MATH5 pair and ran the designed/fuzz bridge test. The one-tree self-test checked five bounds independently by Kruskal against the exact small-case audit. Built the C++ structural DRAT bridge with Boost headers and OpenSSL. It produced drat-trim-accepted proofs on all eight SHA-pinned synthetic Hall/PHP and XOR/Tseitin fixtures. |
| TSP decision proofs | Matched the source and proof SHA-256 in each of 76 archived bound records, then reran drat-trim on each decision CNF and DRAT proof. All 76 were accepted. These include intermediate bounds and repeats from five small instances. |
| Imported summaries | Preserved 11 final JSON records byte-for-byte. Matched each downloaded ZIP's SHA-256 to the GitHub artifact digest. The provenance index gives the run URL, artifact ID, archive hash, member name and member hash. |

The local checker reported version 3.0.2. Its frozen executable SHA-256 was `d21a8d18e8842732fed9049ec16ade60cf5f5f6e64d468e8fbefda810b2b5144`. Install the external verifier separately for an independent replay. Correctness replays here carry no competitive time limit. [Original and proof hashes](../evidence/structural-replay.json) · [CI artifact provenance](../evidence/ci/provenance.json) · [VeriPB](https://veripb.org/)

## Interpreting the scores

- **Checked model** means the returned Boolean assignment satisfies all original clauses.
- **Standard UNSAT proof** means the named external verifier accepted the certificate against the specified original CNF. A proof checked only against a derived master has that narrower target.
- **Project-checked witness** names the restricted source checker. For example, MATH4 accepted eight structural attempts on unseen15, while that arm had zero accepted attempts in the strict DRAT column. [Scoring data](../evidence/ci/math4-unseen15.json)
- **Strict PAR2** in the cited mixed12 run charges a checked completion its end-to-end time and an unsuccessful attempt twice the cap. The published chart uses the sum. Repetitions, permutations and overlapping datasets do not add independent formulas.
- **Prospective versus retrospective** describes when inputs and solver choices were fixed. The ten clique-color proofs were obtained after the original zero-solve holdout informed development. The subsequent test on seven different graph families produced zero strict solves. An earlier eight-family attempt ended before a complete result. [Earlier incomplete run](https://github.com/Frane12/AndroidGameTest/actions/runs/43912555637) · [Completed seven-family test](../evidence/ci/graph-disjoint10.json)

## Other research lines in the archive

| Direction | What a reader can investigate |
|---|---|
| Early R-series structural solving | Source extraction of GF(2) units and the R160 combination of earlier structural routes. These branch links pin implementations. [R153](https://github.com/Frane12/AndroidGameTest/tree/3d4428de2f76aa7896b8fa8fe9a8b79f83fa4281) · [R160](https://github.com/Frane12/AndroidGameTest/tree/b14abe967589f0dc9941fa76d553c320480101a5) |
| Adaptive decisions | ATLAS ablations, persistent LTM profiles, LTM12 progressive testing, MATH14 mixed testing and BCP propagation experiments. [ATLAS39](../research/DRNAS_ATLAS39_FINDINGS_20261111.md) · [LTM12](https://github.com/Frane12/AndroidGameTest/tree/9d864235668ead9aa38e3d45f3bb65943c0cc19c) · [MATH14](https://github.com/Frane12/AndroidGameTest/tree/efe79e4009cb253e3c89ee58deb0ca3cad31f14c) · [BCP1](https://github.com/Frane12/AndroidGameTest/tree/ed1dc3c7b7649dc402a4e45ddfb3c628e38cacda) |
| Cooperation and search cost | Gate activation, budgeted structural probes and component-level audits of CDCL. [COOP5](DRNAS_COOP5_PROBE_BUDGET.md) · [CDCL component audit](../research/drnas_contract/CDCL_COMPONENT_AUDIT_20261114.md) |
| Integer covers, odd wheels and matching | IPG5C/D documents nine source-recognized odd-wheel cases. MATCH3 uses a source-checked Hall cut. Each report states the target and certificate format. [IPG5C/D](../research/IPG5C_D_VERIFIED_SOURCE_PB_RESULTS.md) · [MATCH3](../research/MATCH3_FLOW_HALL_POLY1.md) |

Branch-specific solver revisions, alternative configurations, old workflow files and frozen runner binaries remain retrievable from the legacy repository or its Actions artifacts while those artifacts are available. Installing benchmark dependencies and restoring the corresponding original input bundle is necessary for a full historical timing run. The checked-in proof examples can be verified from a clone with the external checker alone.
