#!/usr/bin/env python3
"""Recover exact ten preselected SAT Competition 2025 original CNF bytes.

Selection comes from the earlier, separately frozen Graph-disjoint study.
This is a NEW ATLAS detector evaluation on PREVIOUSLY TESTED sources, not
a new untouched blind set. Requiring both GBD hash/isohash and previously
recorded raw-source SHA prevents silent source substitution.
"""
import hashlib, json, pathlib, sys, os
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PRE=ROOT/"research/graph_family_disjoint25/prespec.json"
OLD=ROOT/"evidence/ci/graph-disjoint10.json"
OUT=ROOT/"atlas4_real10"
sys.path.insert(0,str(ROOT/"research/graph_family_disjoint25"))
from freeze import download_original, syntax_only

def main():
    specs=json.loads(PRE.read_text())["records"]
    historical=json.loads(OLD.read_text())["provenance"]
    assert len(specs)==len(historical)==10
    assert {x["id"] for x in specs}==set(range(10))
    m={x["id"]:x for x in historical}
    OUT.mkdir(exist_ok=True)
    frozen=[]
    for s in sorted(specs,key=lambda x:x["id"]):
        old=m[s["id"]]
        assert all(s[k]==old[k] for k in ("family","gbd_hash","isohash"))
        raw,archive_sha,archive_bytes,url=download_original(s["gbd_hash"])
        sha=hashlib.sha256(raw).hexdigest()
        if sha!=old["source_sha256"]:
            raise RuntimeError("SOURCE_CHANGED_FAIL_CLOSED "+str(s["id"])+" "+sha)
        bounds=syntax_only(raw)
        path=OUT/(f'{s["id"]:02d}.cnf')
        path.write_bytes(raw)
        row={
            "id":s["id"],"gbd_hash":s["gbd_hash"],
            "isohash":s["isohash"],"family":s["family"],
            "original_source_sha256":sha,"archive_sha256":archive_sha,
            "archive_bytes":archive_bytes,"source_bytes":len(raw),
            "source_url":url,**bounds,
            "path":str(path.relative_to(ROOT)),
            "previous_benchmark_result_visibility":"previously evaluated in 2026-11-16 graph-family-disjoint25"
        }
        frozen.append(row)
        print("ATLAS4_FROZEN_ORIGINAL "+json.dumps({
            "id":s["id"],"gbd":s["gbd_hash"],"raw_sha256":sha,
            "bytes":len(raw),"vars":bounds["variables"],
            "clauses":bounds["clauses"]},sort_keys=True),flush=True)
    data={
        "status":"FROZEN_ALL_10_EXISTING_ORIGINALS",
        "count":len(frozen),"families":len({x["family"] for x in frozen}),
        "catalog_prespec_sha256":hashlib.sha256(PRE.read_bytes()).hexdigest(),
        "prior_source_sha256_manifest_sha256":hashlib.sha256(OLD.read_bytes()).hexdigest(),
        "not_a_new_blind_source_set":True,"sources":frozen,
        "no_outcome_based_source_replacement":True
    }
    tmp=OUT/"manifest.tmp.json"
    tmp.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
    os.replace(tmp,OUT/"manifest.json")
    print("ATLAS4_FREEZE_PASS "+json.dumps({
      "sources":len(frozen),"families":data["families"],
      "total_original_bytes":sum(x["source_bytes"] for x in frozen),
      "manifest_sha256":hashlib.sha256((OUT/"manifest.json").read_bytes()).hexdigest()
      },sort_keys=True),flush=True)

if __name__=="__main__":main()
