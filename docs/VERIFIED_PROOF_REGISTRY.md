# DRNAS SAT — independently checked proof registry

This register lists the eleven PCMAX certificates. The repository also includes replayable original-CNF examples for graph coloring, XOR grids and weighted Petersen. [Additional proof hashes](../evidence/structural-replay.json) · [Full replay command](../README.md#verify-a-proof)

**Evidence migration:** 19 November 2026  
**Verifier:** external VeriPB 3.0.2, original CNF input, accepted UNSAT in each case.  
**Source experiment:** [PCMAX Weighted VeriPB2, run 43719601339](https://github.com/Frane12/AndroidGameTest/actions/runs/43719601339)  
**Re-verification in this repository:** [run 44479216787](https://github.com/Frane12/DRNAS-SAT/actions/runs/44479216787)

These are exact source-bound, independently checked proof certificates, not merely DRNAS solver output. Each accepted case has its original CNF, weighted.pbp, capacity.json and verifier log under [evidence/pcmax-weighted2](../evidence/pcmax-weighted2).

## Accepted original PCMAX cases

| Case | Weighted demand | Machine capacity | VeriPB proof bytes | Evidence |
|---|---:|---:|---:|---|
| m11-1517-6802 | 16 | 15 | 181,816 | [00](../evidence/pcmax-weighted2/00) |
| m13-1655-9604 | 105 | 104 | 323,657 | [02](../evidence/pcmax-weighted2/02) |
| m13-2011-12813 | 10,000 | 9,945 | 468,252 | [03](../evidence/pcmax-weighted2/03) |
| m13-2826-11437 | 10,000 | 9,971 | 761,975 | [04](../evidence/pcmax-weighted2/04) |
| m14-3640-14524 | 31 | 30 | 557,597 | [05](../evidence/pcmax-weighted2/05) |
| m19-10199-62102 | 1,002 | 997 | 2,586,374 | [07](../evidence/pcmax-weighted2/07) |
| m19-2974-16501 | 9,996 | 9,895 | 754,483 | [08](../evidence/pcmax-weighted2/08) |
| m20-3726-23254 | 1,002 | 988 | 1,008,699 | [09](../evidence/pcmax-weighted2/09) |
| m20-4135-27005 | 42 | 41 | 929,189 | [10](../evidence/pcmax-weighted2/10) |
| m26-6398-62377 | 10,001 | 9,927 | 1,902,153 | [14](../evidence/pcmax-weighted2/14) |
| m30-14113-167638 | 998 | 990 | 2,465,305 | [15](../evidence/pcmax-weighted2/15) |

The original retrospective dataset contains 20 distinct PCMAX CNFs. The other nine cases did not produce UNSAT certificates and remain recorded as UNKNOWN in the experiment. This result is not a general SAT speed comparison.

## Reproduce m14 verification

Install the same external checker and run it on the immutable CNF with the standard proof:

~~~bash
cargo install veripb --version 3.0.2 --locked
veripb --cnf evidence/pcmax-weighted2/05/original.cnf \
  evidence/pcmax-weighted2/05/weighted.pbp
~~~

Expected checker statement: **s VERIFIED UNSATISFIABLE**

Original CNF SHA-256:

~~~text
a540b7d1aa098217bde5145b56f1f8e4898e9fedd73ea1ad99259ed43fa1e275
~~~

VeriPB proof SHA-256:

~~~text
d52972eae8f2fee8ccc0d9397c31c28e7cd77cac858e3a9ef2187823e7b2741e
~~~

The bounds 31 > 30 are *weighted demand and weighted capacity*, not a literal count of 31 jobs. The standard proof derives the contradiction from original CNF clauses. The experiment measured approximately 0.04261 s native detection, 0.07839 s proof production and 0.02339 s external checking for m14, exclusive of input download. These are different timings and must not be compared to a previously published multi-CPU execution without matching hardware and measurement methodology.

**Priority clarification:** The PCMAX m14 instance was previously reported as UNSAT in 2024. This repository's achievement is an independently verified, source-bound proof through the DRNAS mathematical method, not the first-ever UNSAT status claim.

## Proof provenance

The [verified manifest](../evidence/pcmax-weighted2/verified_manifest.json) pins each original SHA-256, proof SHA-256, size and arithmetic bound. The [summary](../evidence/pcmax-weighted2/summary.json) retains all 20 original trial results. The evidence mirror was created only after all 11 original proofs were rechecked by external VeriPB 3.0.2 in the new repository.
