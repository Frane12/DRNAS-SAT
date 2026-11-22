#!/usr/bin/env python3
"""Freeze precisely two original SAT05 contest CNFs from publisher's archive.

The source archive and filename stems were precommitted before downloading.
Every extracted source is raw hashed, DIMACS validated and frozen in a
manifest BEFORE any ATLAS detection or solver call. No substitutions.
"""
import argparse,hashlib,json,tarfile,re,bz2,gzip,lzma
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"atlas11_frozen";OUT.mkdir(parents=True,exist_ok=True)
P=json.loads((HERE/"prespec.json").read_text())
def sha(x):return hashlib.sha256(x).hexdigest()
def validate(raw):
    n=nc=None;count=0;maxwidth=0;pending=0
    for line in raw.decode("ascii").splitlines():
        fields=line.split()
        if not fields or fields[0]=="c":continue
        if fields[0]=="p":
            assert n is None and len(fields)==4 and fields[1]=="cnf"
            n,nc=map(int,fields[2:]);assert 1<=n<=50000 and 1<=nc<=100000
            continue
        assert n is not None
        for part in fields:
            lit=int(part)
            assert abs(lit)<=n
            if lit:pending+=1
            else:
                maxwidth=max(maxwidth,pending);pending=0;count+=1
    assert n is not None and not pending and count==nc
    return {"variables":n,"clauses":nc,"max_clause_width":maxwidth}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("archive",type=Path)
    a=ap.parse_args()
    assert P["protocol"]=="DRNAS-ATLAS11-SAT05-ARCHIVE-INDEPENDENT-120-135-20261122"
    assert P["selected_before_ATLAS11_source_download"]
    assert P["no_replacement_after_outcomes"]
    assert len(P["sources"])==2
    archive=a.archive
    actual_md5=hashlib.md5(archive.read_bytes()).hexdigest()
    if actual_md5!=P["source_archive_md5"]:
        raise RuntimeError("ARCHIVE_MD5_MISMATCH_EXPECTED_"+P["source_archive_md5"]+"_GOT_"+actual_md5)
    selected={s["id"]:[] for s in P["sources"]}
    names_matching=[]
    with tarfile.open(archive,"r:bz2") as f:
        for entry in f:
            if not entry.isfile():continue
            base=Path(entry.name).name
            if "rand3bip" in base.lower():names_matching.append(entry.name)
            for spec in P["sources"]:
                if spec["filename_regex"] in base and base.endswith((".cnf",".cnf.bz2",".cnf.gz",".cnf.xz")):
                    if len(entry.name)>350:raise RuntimeError("unsafe_tar_name")
                    file=f.extractfile(entry)
                    if file is None:raise RuntimeError("missing_tar_member")
                    payload=file.read(2000001)
                    if len(payload)>2000000:raise RuntimeError("member_exceeds_2MB")
                    if base.endswith(".bz2"):raw=bz2.decompress(payload)
                    elif base.endswith(".gz"):raw=gzip.decompress(payload)
                    elif base.endswith(".xz"):raw=lzma.decompress(payload)
                    else:raw=payload
                    if len(raw)>2000000:raise RuntimeError("source_exceeds_2MB")
                    selected[spec["id"]].append((entry.name,raw))
    print("ATLAS11_ARCHIVE_MEMBER_DIAGNOSTIC "+json.dumps({"rand3bip_entries":len(names_matching),"matching_examples":names_matching[:35]},sort_keys=True),flush=True)
    frozen=[]
    for spec in P["sources"]:
        entries=selected[spec["id"]]
        if len(entries)!=1:
            raise RuntimeError("EXPECTED_EXACT_ONE_SOURCE_FOR_"+spec["id"]+"_FOUND_"+str(len(entries)))
        member,raw=entries[0]
        dims=validate(raw)
        path=OUT/(spec["id"]+".cnf")
        if path.exists():raise RuntimeError("source_cannot_overwrite")
        path.write_bytes(raw)
        row={"id":spec["id"],"archive_member_name":member,
             "filename_stem":spec["filename_regex"],
             "historical_sat05_id":spec["original_historical_sat05_id"],
             "source_sha256":sha(raw),"source_bytes":len(raw),
             "path":str(path.relative_to(ROOT)),**dims}
        frozen.append(row)
        print("ATLAS11_SOURCE_FROZEN "+json.dumps(row,sort_keys=True),flush=True)
    manifest={
        "format":"DRNAS-ATLAS11-SOURCE-FREEZE-v1",
        "source_archive_MD5":actual_md5,"source_archive_SHA256":sha(archive.read_bytes()),
        "source_prespec_SHA256":sha((HERE/"prespec.json").read_bytes()),
        "status":"FROZEN_ALL_TWO_BEFORE_ANY_SOLVER",
        "source_count":len(frozen),
        "independent_originals":2,
        "sources":frozen}
    (OUT/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    print("ATLAS11_FREEZE_SUCCESS "+json.dumps({
       "originals":len(frozen),"manifest_sha256":sha((OUT/"manifest.json").read_bytes())},sort_keys=True),flush=True)
if __name__=="__main__":main()
