#!/usr/bin/env python3
"""Source-only freeze of ONE public SAT Competition 2005-derived original.

No detector/proof emitter has access to source catalog metadata or outcome.
The GBD ID is fixed in prespec.json before this script is run; failures
abort without replacement. Raw SHA is recorded before any solving.
"""
import hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas9_original105_source"
SPEC=json.loads((HERE/"prespec.json").read_text())
sys.path.insert(0,str(ROOT/"research/graph_family_disjoint25"))
from freeze import download_original,syntax_only

def digest(data):return hashlib.sha256(data).hexdigest()

def main():
    assert SPEC["protocol"]=="DRNAS-ATLAS9-GBD-ORIGINAL-UNSAT105-3-20261121"
    assert SPEC["no_source_substitution"]
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"original.cnf"
    if path.exists():raise RuntimeError("REFUSE_SOURCE_OVERWRITE")
    raw,archive_sha,archive_bytes,url=download_original(SPEC["source_id"])
    if len(raw)>SPEC["original_source_max_bytes"]:raise RuntimeError("SOURCE_BYTES_LIMIT")
    dims=syntax_only(raw)
    path.write_bytes(raw)
    frozen={
      "format":"DRNAS-ATLAS9-SINGLE-ORIGINAL-FROZEN-v1",
      "source_gbd_id":SPEC["source_id"],
      "source_isohash":SPEC["isohash"],
      "source_original_raw_sha256":digest(raw),
      "source_original_bytes":len(raw),
      "source_archive_sha256":archive_sha,
      "source_archive_bytes":archive_bytes,
      "source_url":url,
      "source_dimensions":dims,
      "selection_prespec_sha256":digest((HERE/"prespec.json").read_bytes()),
      "source_only_no_solver_executed_yet":True,
      "no_substitution":True
    }
    (OUT/"source-frozen.json").write_text(json.dumps(frozen,sort_keys=True,indent=2)+"\n")
    print("ATLAS9_ORIGINAL_FROZEN "+json.dumps(frozen,sort_keys=True),flush=True)

if __name__=="__main__":main()
