#!/usr/bin/env python3
"""Freeze three exact ORIGINAL SAT05 camouflaged-XOR GBD sources before tests.

IDs are fixed in committed prespec.json, no outcomes used to replace sources.
Raw SHA-256 is computed and sealed before any candidate detector runs.
"""
import pathlib,hashlib,json,sys,os
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
PRE=json.loads((HERE/"prespec.json").read_text())
OUT=ROOT/"atlas7_two_sources"
sys.path.insert(0,str(ROOT/"research/graph_family_disjoint25"))
from freeze import download_original,syntax_only
def sha(v):return hashlib.sha256(v).hexdigest()
def main():
    assert PRE["protocol"]=="DRNAS-ATLAS7B-TWO-ACCESSIBLE-SAT-SOURCES-20261121"
    assert PRE["separately_fixed_before_ANY_ATLAS7B_detector_evaluation"]
    assert len(PRE["sources"])==2
    OUT.mkdir(exist_ok=True,parents=True)
    frozen=[]
    for source in PRE["sources"]:
        raw,archive_sha,archive_bytes,url=download_original(source["gbd_hash"])
        if sha(raw)!=source["expected_source_sha256"]:raise RuntimeError("SOURCE_SHA_CHANGED_FAIL_CLOSED "+source["id"])
        if len(raw)>PRE["resource_cap_bytes_per_raw_source"]:
            raise RuntimeError("SOURCE_OVER_PREDECLARED_RESOURCE_CAP "+source["id"])
        dims=syntax_only(raw)
        path=OUT/(source["id"]+".cnf")
        if path.exists():raise RuntimeError("REFUSE_TO_OVERWRITE_FROZEN_SOURCE")
        path.write_bytes(raw)
        item={k:v for k,v in source.items() if k!="catalog_status_for_posthoc_report_only"}
        item.update({"id":source["id"],"path":str(path.relative_to(ROOT)),
                    "source_sha256":sha(raw),"archive_sha256":archive_sha,
                    "source_bytes":len(raw),"archive_bytes":archive_bytes,
                    "dimension":dims,"original_download":url})
        frozen.append(item)
        print("ATLAS7B_FROZEN_SOURCE "+json.dumps({
            "id":item["id"],"source_sha256":item["source_sha256"],
            "original_variables":dims["variables"],"original_clauses":dims["clauses"],
            "source_bytes":item["source_bytes"]},sort_keys=True),flush=True)
    result={"format":"ATLAS7B-FROZEN-ORIGINAL-CNF-v1",
      "prespec_sha256":sha((HERE/"prespec.json").read_bytes()),
      "source_count":len(frozen),"sources":frozen,
      "status":"FROZEN_SOURCE_ONLY_BEFORE_DETECTOR",
      "no_substitution_or_outcome_selection":True}
    (OUT/"manifest.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("ATLAS7B_SOURCE_FREEZE_COMPLETE "+json.dumps({
       "sources":len(frozen),"sha256":sha((OUT/"manifest.json").read_bytes())},sort_keys=True))
if __name__=="__main__":main()
