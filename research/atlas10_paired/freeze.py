#!/usr/bin/env python3
"""ATLAS10 fixed-source original CNFs, reproducible transformations before trial.

The catalog metadata query in preceding GitHub CI could not reach external
listing, so this experiment is deliberately limited to a previously
SHA-pinned public original. There is NO replacement, outcome-driven selection,
nor claim of 3 independent original formulas.
"""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas10_frozen"
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/"research/graph_family_disjoint25"))
sys.path.insert(0,str(ROOT/"research/structure_atlas1"))
from freeze import download_original,syntax_only
from atlas import parse,transform
def sha(raw):return hashlib.sha256(raw).hexdigest()
p=json.loads((HERE/"prespec.json").read_text())
assert p["protocol"]=="DRNAS-ATLAS10-PINNED-ONE-ORIGINAL-3x-PAIRED-20261122"
assert len(p["selected_origins"])==1
selected=p["selected_origins"][0]
raw,archive_sha,archive_bytes,url=download_original(selected["gbd_id"])
if sha(raw)!=selected["previous_raw_sha256"]:
    raise RuntimeError("ORIGINAL_SOURCE_SHA_CHANGED")
details=syntax_only(raw)
n,clauses=parse(raw)
assert n==details["variables"] and len(clauses)==details["clauses"]
inputs=[]
for variation in p["known_exact_equivalence_variations"]:
    seed=variation.get("seed")
    if seed is None:
        data=raw
        label="original"
        identity=True
    else:
        data,identity,_=transform(n,clauses,seed,rename=True,
                                   flip=variation["type"]=="bijective-rename-signflip-clause-order",
                                   shuffle=True)
        assert identity
        label="permutation-"+str(seed)
    name=OUT/(label+".cnf")
    if name.exists():raise RuntimeError("REFUSE_REWRITE_FROZEN_INPUT")
    name.write_bytes(data)
    record={"label":label,"path":str(name.relative_to(ROOT)),"raw_sha256":sha(data),
            "variables":n,"clauses":len(clauses),
            "known_exact_inverse_bijection":identity,
            "same_underlying_original":True}
    inputs.append(record)
    print("ATLAS10_FROZEN_CNF "+json.dumps(record,sort_keys=True),flush=True)
m={"protocol":p["protocol"],"prespec_sha256":sha((HERE/"prespec.json").read_bytes()),
   "source_gbd_id":selected["gbd_id"],"source_original_sha256":sha(raw),
   "source_original_url":url,"source_archive_sha256":archive_sha,
   "source_archive_bytes":archive_bytes,
   "sources_are_correlated_variants":True,
   "distinct_original_sources":1,"variant_input_count":len(inputs),
   "inputs":inputs,"status":"FROZEN_BEFORE_SOLVER_TESTS"}
(OUT/"manifest.json").write_text(json.dumps(m,sort_keys=True,indent=2)+"\n")
print("ATLAS10_FROZEN_BEFORE_SOLVERS "+json.dumps({
   "original_sources":1,"variant_inputs":len(inputs),
   "source_sha256":sha(raw)},sort_keys=True),flush=True)
