#!/usr/bin/env python3
"""DRNAS ATLAS1 reproducibility audit on five ORIGINAL unchanged CNFs.

One-copy source classification only. Controlled bijective transforms are
certified equivalent by exact inverse mapping of every ORIGINAL clause.
The invariants are coarse feature hashes; do NOT confuse hash match with
a proof that arbitrary two unrelated CNFs are isomorphic/equisatisfiable.
"""
import csv,hashlib,json,os,statistics,sys,time
from pathlib import Path
from atlas import parse,encoded,scan,transform

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"structure_atlas1_audit"
OUT.mkdir(parents=True,exist_ok=True)
SOURCES=[
 ("graph-color-k11","evidence/graph-k11/original.cnf"),
 ("petersen-ipg","evidence/ipg7b-petersen/original.cnf"),
 ("xor234-grid","evidence/xor234-grid5/original.cnf"),
 ("pcmax-m14","evidence/pcmax-weighted2/05/original.cnf"),
 ("pcmax-m30","evidence/pcmax-weighted2/15/original.cnf"),
]
# Variants specified before scanning, no selection by results.
VARIANTS=[
 ("rename-clause-shuffle",11001,True,False,True),
 ("rename2-clause-shuffle",22002,True,False,True),
 ("sign-flip-rename",33003,True,True,True),
 ("sign-flip-rename2",44004,True,True,True),
]
rows=[];originals={}
for family,path in SOURCES:
    raw=(ROOT/path).read_bytes()
    t=time.perf_counter();initial=scan(raw);elapsed=time.perf_counter()-t
    nvar,clauses=parse(raw)
    originals[family]=initial
    (OUT/(family+"-original.json")).write_text(json.dumps({
        "label_for_reporting_only":family,"file_path_for_repro_only":path,
        "scan_s":elapsed,"analysis":initial},indent=2,sort_keys=True)+"\n")
    print("ORIGINAL "+json.dumps({"family":family,"vars":nvar,"clauses":len(clauses),
          "sha":initial["raw_source_sha256"],"coarse":initial["coarse_invariant_sha256"],
          "motifs":initial["motifs"],"scan_s":round(elapsed,5)},sort_keys=True),flush=True)
    for variant,seed,rename,flip,shuffle in VARIANTS:
        started=time.perf_counter()
        changed,exact,how=transform(nvar,clauses,seed,rename,flip,shuffle)
        assert exact,("inverse_clause_equivalence_failed",family,variant)
        transformed=scan(changed)
        sec=time.perf_counter()-started
        same=(transformed["coarse_invariant_sha256"]==initial["coarse_invariant_sha256"])
        assert same,("coarse_fingerprint_not_invariant",family,variant)
        assert transformed["raw_source_sha256"]!=initial["raw_source_sha256"]
        assert transformed["variable_count"]==initial["variable_count"]
        assert transformed["clause_count"]==initial["clause_count"]
        # Renaming/reordering only must preserve positive syntactic motifs.
        if not flip:
            assert transformed["motifs"]==initial["motifs"],("recognizer_not_permutation_invariant",family,variant)
        rows.append({"family":family,"source":path,"variant":variant,
           "original_source_sha256":initial["raw_source_sha256"],
           "transformed_source_sha256":transformed["raw_source_sha256"],
           "coarse_original":initial["coarse_invariant_sha256"],
           "coarse_transformed":transformed["coarse_invariant_sha256"],
           "exact_inverse_clause_equivalent":exact,
           "coarse_fingerprint_same":same,
           "syntactic_motifs_same":transformed["motifs"]==initial["motifs"],
           "sign_flip":flip,"flipped_vars":how["flipped_vars"],
           "scan_and_transform_wall_s":round(sec,6)})
        (OUT/(family+"-"+variant+".json")).write_text(json.dumps({
            "variant":how,"analysis":transformed,
            "exact_inverse_clause_equivalent":exact,
            "motifs_stable":transformed["motifs"]==initial["motifs"]},sort_keys=True,indent=2)+"\n")
        print("VARIANT "+json.dumps({"family":family,"variant":variant,"equivalent":exact,
            "fingerprint_same":same,"motifs_same":rows[-1]["syntactic_motifs_same"],
            "seconds":round(sec,5)},sort_keys=True),flush=True)

# Negative control: change SOURCE by adding a clause, preserving original
# variables. This is not a bijective renaming of input.
for family,path in SOURCES:
    raw=(ROOT/path).read_bytes();nv,cs=parse(raw)
    altered=encoded(nv,cs+[(1,)])
    altered_scan=scan(altered)
    assert altered_scan["coarse_invariant_sha256"]!=originals[family]["coarse_invariant_sha256"]
    assert altered_scan["clause_count"]==originals[family]["clause_count"]+1
    print("TAMPER_REJECT "+json.dumps({"family":family,
         "changed_source_sha256":altered_scan["raw_source_sha256"],
         "coarse_changed":True},sort_keys=True),flush=True)
# The family labels are NOT used as predictor input; check whether coarse
# hashes distinguish these five originals in this preselected sample.
unique_fingerprints=len({item["coarse_invariant_sha256"] for item in originals.values()})
assert unique_fingerprints==len(SOURCES)

with (OUT/"paired-invariance.csv").open("w",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows)
summary={
 "status":"PASS","original_sources":len(SOURCES),
 "sources":[{"reporting_label":family,
             "exact_source_path":path,
             "source_sha256":originals[family]["raw_source_sha256"],
             "num_vars":originals[family]["variable_count"],
             "num_clauses":originals[family]["clause_count"],
             "coarse_fingerprint":originals[family]["coarse_invariant_sha256"],
             "motifs":originals[family]["motifs"]} for family,path in SOURCES],
 "controlled_bijection_transforms":len(rows),
 "exact_inverse_equivalences":sum(x["exact_inverse_clause_equivalent"] for x in rows),
 "coarse_fingerprint_invariant":sum(x["coarse_fingerprint_same"] for x in rows),
 "rename_only_motifs_preserved":sum(x["syntactic_motifs_same"] for x in rows if not x["sign_flip"]),
 "rename_only_trials":sum(not x["sign_flip"] for x in rows),
 "sign_flip_motifs_preserved":sum(x["syntactic_motifs_same"] for x in rows if x["sign_flip"]),
 "sign_flip_trials":sum(x["sign_flip"] for x in rows),
 "source_mutation_negative_controls":len(SOURCES),
 "different_fingerprint_original_sources":unique_fingerprints,
 "mean_transform_and_scan_s":statistics.mean(x["scan_and_transform_wall_s"] for x in rows),
 "assertion_limits":["coarse structural fingerprint collisions possible",
   "syntactic motif detector may fail after polarity flips",
   "inverse exact equivalence holds only for transformations with known mapping",
   "no SAT status used for source recognition",
   "no claim of semantic decoding across Tseitin/cardinality/BDD alternative encodings",
   "no solver output or new UNSAT verified by this feature census"],
 "scope":"original SAT/PCMAX evidence already present in repository, not new blind holdout",
}
(OUT/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
print("ATLAS1_AUDIT_PASS "+json.dumps({k:v for k,v in summary.items() if k!="sources"},sort_keys=True),flush=True)
