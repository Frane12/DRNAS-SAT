#!/usr/bin/env python3
"""Freeze every prespecified external CNF before ATLAS17 ever runs a solver.

No labels, expected outcomes, or old proof artifacts are passed to solvers.
Unavailable/oversize sources stay in the manifest as failures: no substitutions.
"""
import hashlib, io, json, lzma, pathlib, time, urllib.request, urllib.error

ROOT=pathlib.Path(__file__).resolve().parents[2]
HOME=ROOT/"research/atlas17_probe"
OUTPUT=ROOT/"atlas17_original_inputs"
PRESPEC=HOME/"prespec.json"
P=json.loads(PRESPEC.read_text())
assert P["protocol"]=="DRNAS-ATLAS17-PROSPECTIVE-SOURCE-FROZEN-CROSS-MODULE-PROBE-20261124"
OUTPUT.mkdir(exist_ok=True)
assert not (OUTPUT/"manifest.json").exists(),"refuse to overwrite frozen catalog"
MAX_ARCH=P["cpu_soft_limits"]["max_public_compressed_bytes"]
MAX_RAW=P["cpu_soft_limits"]["max_public_original_bytes"]
def sha(b):return hashlib.sha256(b).hexdigest()
def syntax(data):
    vars_=nclauses=None;seen=0;unfinished=0
    for raw in io.BytesIO(data):
        cols=raw.split()
        if not cols or cols[0]==b"c":continue
        if cols[0]==b"p":
            if vars_ is not None or len(cols)!=4 or cols[1]!=b"cnf":raise ValueError("bad DIMACS header")
            vars_,nclauses=map(int,cols[2:])
            if not (0<vars_<=5_000_000 and 0<=nclauses<=5_000_000):raise ValueError("DIMACS budget exceeded")
            continue
        if vars_ is None:raise ValueError("header missing")
        for token in cols:
            l=int(token)
            if abs(l)>vars_:raise ValueError("bad literal")
            if l==0:
                seen+=1;unfinished=0
            else: unfinished+=1
    if vars_ is None or unfinished or seen!=nclauses:raise ValueError("wrong DIMACS clause count")
    return vars_,seen
def download(gbd):
    url=f"https://benchmark-database.de/file/{gbd}?context=cnf"
    req=urllib.request.Request(url,headers={"User-Agent":"DRNAS-ATLAS17/1.0 (source-only public CNF corpus)","Accept":"application/x-xz,application/octet-stream,*/*"})
    with urllib.request.urlopen(req,timeout=P["cpu_soft_limits"]["source_download_timeout_s"]) as resp:
        chunks=[];count=0
        while True:
            c=resp.read(min(1<<20,MAX_ARCH-count+1))
            if not c:break
            count+=len(c)
            if count>MAX_ARCH:raise ValueError("ARCHIVE_OVER_BUDGET")
            chunks.append(c)
    archive=b"".join(chunks)
    if archive.startswith(b"\xfd7zXZ\x00"):
        with lzma.LZMAFile(io.BytesIO(archive)) as f:
            parts=[];sofar=0
            while True:
                data=f.read(min(1<<20,MAX_RAW-sofar+1))
                if not data:break
                sofar+=len(data)
                if sofar>MAX_RAW:raise ValueError("DECOMPRESSED_OVER_BUDGET")
                parts.append(data)
            raw=b"".join(parts)
    else: raw=archive
    if len(raw)>MAX_RAW:raise ValueError("RAW_OVER_BUDGET")
    return raw,url,sha(archive),len(archive)
records=[];failed=[]
for s in P["public_originals"]:
    key=s["id"]
    try:
        raw,url,archive_hash,archive_bytes=download(s["gbd_hash"])
        n,m=syntax(raw)
        path=OUTPUT/f"{key}.cnf"
        path.write_bytes(raw)
        item={"name":key,"cohort":"public_preselected","path":str(path.relative_to(ROOT)),
              "sha256":sha(raw),"gbd_hash":s["gbd_hash"],"original_url":url,
              "raw_bytes":len(raw),"archive_sha256":archive_hash,
              "archive_bytes":archive_bytes,"variables":n,"clauses":m,
              "family_for_reporting_only":s["family_for_reporting_only"],
              "no_outcome_prelabel_used":True}
        records.append(item)
        print("ATLAS17_PUBLIC_FROZEN "+json.dumps({k:item[k] for k in
              ("name","sha256","variables","clauses","raw_bytes","gbd_hash")},sort_keys=True),flush=True)
    except Exception as error:
        fail={"name":key,"cohort":"public_preselected","gbd_hash":s["gbd_hash"],
              "error_type":type(error).__name__,"reason":str(error)[:220],
              "cannot_replace":True}
        failed.append(fail)
        print("ATLAS17_PUBLIC_UNAVAILABLE "+json.dumps(fail,sort_keys=True),flush=True)
for s in P["retrospective_originals"]:
    path=ROOT/s["path"]
    if not path.exists():raise FileNotFoundError(path)
    raw=path.read_bytes()
    if sha(raw)!=s["sha256"]:raise AssertionError("RETROSPECTIVE_HASH_MISMATCH "+s["id"])
    n,m=syntax(raw)
    item={"name":s["id"],"cohort":"retrospective_known","path":s["path"],
          "sha256":s["sha256"],"variables":n,"clauses":m,
          "raw_bytes":len(raw),"no_outcome_prelabel_used":True}
    records.append(item)
    print("ATLAS17_RETROSPECTIVE_FROZEN "+json.dumps(
        {k:item[k] for k in ("name","sha256","variables","clauses")},sort_keys=True),flush=True)
if len({x["sha256"] for x in records})!=len(records):raise AssertionError("DUPLICATE_ORIGINAL_SHA")
assert len(records)+len(failed)==len(P["public_originals"])+len(P["retrospective_originals"])
manifest={"status":"FROZEN_BEFORE_ANY_SOLVER",
          "protocol":P["protocol"],
          "prespec_sha256":sha(PRESPEC.read_bytes()),
          "prespec_commit_sha":__import__("os").environ.get("GITHUB_SHA"),
          "selected_public_count":len(P["public_originals"]),
          "public_downloaded":sum(x["cohort"]=="public_preselected" for x in records),
          "known_retrospective":sum(x["cohort"]=="retrospective_known" for x in records),
          "no_source_substitution":True,"failures":failed,"sources":records}
(OUTPUT/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
print("ATLAS17_SOURCE_FREEZE_FINAL "+json.dumps(
    {k:v for k,v in manifest.items() if k not in ("sources","failures")},sort_keys=True),flush=True)
