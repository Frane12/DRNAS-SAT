#!/usr/bin/env python3
"""Controlled encoding-equivalence audit: source EO decoder, 3 sizes x 2
distinct CNF representations x 3 renaming/polarity variants + negative controls.
Only projected semantics of generator-made controls are independently
exhaustively checked; never claim equivalence of unrelated real CNFs.
"""
from pathlib import Path
import csv,json,hashlib
from atlas import transform,scan
from semantic_eo import construct,projection_exactly_one,recover

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"structure_atlas1_semantic"
OUT.mkdir(exist_ok=True)
rows=[]
for n in (4,6,7):
    for kind in ("pairwise","sequential"):
        nv,clauses=construct(n,kind)
        assert projection_exactly_one(n,nv,clauses),("non-equivalent generator",n,kind)
        for variant,seed,flip in (("rename",101,False),
                                  ("sign-flip",202,True),
                                  ("sign-flip2",303,True)):
            raw,eq,how=transform(nv,clauses,seed,rename=True,flip=flip,shuffle=True)
            assert eq
            facts=recover(raw)
            assert facts["status"]=="EXACTLY_ONE_SOURCE_PROVEN_PAIR_RUP",(n,kind,variant,facts)
            assert any(c["selector_count"]==n for c in facts["source_supported_exactly_one"])
            row={"n":n,"encoding":kind,"variant":variant,"seed":seed,
                "source_sha256":hashlib.sha256(raw).hexdigest(),
                "variables":nv,"clauses":len(clauses),
                "renamed_and_signed":flip,"exact_inverse_equivalent":eq,
                "recovered_exactly_one_n":n,"rup_pair_checks":facts["tested_pairs"],
                "status":facts["status"]}
            rows.append(row)
            print("SEMANTIC_RECOGNIZED "+json.dumps(row,sort_keys=True),flush=True)
        bad_nv,bad_cs=construct(n,kind,broken=True)
        assert not projection_exactly_one(n,bad_nv,bad_cs),(n,kind,"negative not actually broken")
        bad,eq,_=transform(bad_nv,bad_cs,505,rename=True,flip=True,shuffle=True)
        assert eq
        facts=recover(bad)
        assert facts["status"]=="UNKNOWN",(n,kind,facts)
        print("SEMANTIC_NEGATIVE_UNKNOWN "+json.dumps({"n":n,"kind":kind,
             "sha256":hashlib.sha256(bad).hexdigest()},sort_keys=True),flush=True)

with (OUT/"semantic-trials.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]))
    w.writeheader();w.writerows(rows)
summary={
    "status":"PASS",
    "two_encodings":["pairwise AMO","Sinz sequential auxiliary AMO"],
    "distinct_encoding_sizes":[4,6,7],
    "generated_source_transform_trials":len(rows),
    "source_supported_exactly_one_recovered":len(rows),
    "proof_rule":"Original ALO + per-pair unit propagation conflict -> original-source RUP",
    "projected_exact_one_generator_checks":6,
    "separate_satisfiable_negative_controls":6,
    "negative_controls_correctly_returned_unknown":6,
    "known_bijection_exact_clause_equivalences":len(rows),
    "inferences_are_unsat_claims":False,
    "qualification":"Small constructed encoding variants only, no new real-CNF cross-encoding coverage",
    "scope":"pilot tests different CNF encodings with auxiliary variables and arbitrary sign flips"
}
(OUT/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
print("ATLAS1_SEMANTIC_CROSS_ENCODING_PASS "+json.dumps(summary,sort_keys=True),flush=True)
