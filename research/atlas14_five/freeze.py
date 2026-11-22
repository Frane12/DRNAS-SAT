#!/usr/bin/env python3
"""ATLAS14, five immutable original repository CNFs, SHA frozen before trials.

Labels, family and known historical proof paths live in the manifest but NEVER
enter the source-only discovery or proof emitter. The historical proofs are
not solver outputs; they can be checked in a separately labeled regression.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas14_frozen"
P=json.loads((HERE/"prespec.json").read_text())
def hash_of(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(131072),b""):h.update(chunk)
    return h.hexdigest()
def header(path):
    n=m=None;cl=0;pending=0;used=set()
    for line in Path(path).read_bytes().splitlines():
        z=line.split()
        if not z or z[0]==b'c':continue
        if z[0]==b'p':
            if n is not None or len(z)!=4 or z[1]!=b'cnf':raise ValueError("BAD_HEADER")
            n,m=int(z[2]),int(z[3]);continue
        for c in z:
            l=int(c)
            if l==0:cl+=1;pending=0
            else:
                if n is None or abs(l)>n:raise ValueError("BAD_LITERAL")
                used.add(abs(l));pending+=1
    if n is None or cl!=m or pending:raise ValueError("BAD_DIMACS")
    return {"variables":n,"clauses":m,"used_vars":len(used)}
def main():
    assert P["precommitted_before_any_new_atlas14_trial"]
    assert len(P["sources"])==5 and P["expected_trials"]==30
    OUT.mkdir(exist_ok=True)
    m=[]
    for record in P["sources"]:
        source=ROOT/record["path"];historical=ROOT/record["historical_standard_proof"]
        if not source.is_file() or not historical.is_file():
            raise RuntimeError("PINNED_SOURCE_OR_HISTORICAL_PROOF_MISSING_"+record["id"])
        size=source.stat().st_size
        assert size<2_000_000
        row=dict(record,source_sha256=hash_of(source),source_bytes=size,
                 historical_proof_sha256=hash_of(historical),
                 historical_proof_bytes=historical.stat().st_size,
                 **header(source))
        m.append(row)
        print("ATLAS14_SOURCE_FROZEN "+json.dumps(row,sort_keys=True),flush=True)
    result={"format":"DRNAS-ATLAS14-FIVE-ORIGINAL-FROZEN-v1",
      "status":"FROZEN_BEFORE_ANY_ATLAS14_TRIAL",
      "originals":5,"distinct_family_labels":len({x["family_for_reporting_only"] for x in m}),
      "source_prespec_sha256":hash_of(HERE/"prespec.json"),"sources":m,
      "labels_or_previous_verdicts_not_passed_to_solver":True,
      "historical_proofs_only_for_separate_provenance_audit":True}
    (OUT/"manifest.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("ATLAS14_SOURCE_FREEZE_COMPLETE "+json.dumps({
       "originals":5,"manifest_sha256":hash_of(OUT/"manifest.json")},sort_keys=True),flush=True)
if __name__=="__main__":main()
