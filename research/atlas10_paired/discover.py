#!/usr/bin/env python3
"""Metadata-only discovery of more public original masked-XOR UNSAT CNFs.

This stage runs BEFORE any ATLAS10 detector/solver or benchmark.
No SAT/UNSAT outcome from our new solver is used for source selection.
The fixed policy chooses up to three distinct sizes in prespecified bands,
favoring original GBD sources with successful HTTP HEAD for resource access.
All generated selections, even missing sources, remain in the manifest;
never substitute on a solver result.
"""
import json,hashlib,re,urllib.request,urllib.error,time
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"atlas10_metadata";OUT.mkdir(exist_ok=True)
URLS=[
 "https://benchmark-database.de/?context=cnf&family=random-graph-xorsat&result=unsat",
 "https://benchmark-database.de/?query=family%3Drandom-graph-xorsat",
 "https://benchmark-database.de/?context=cnf&track=crafted_2005"
]
BANDS=[(60,100,90),(110,160,135),(170,300,200)]
class Rows(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.curr=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.curr=[]
        elif tag in ("td","th") and self.curr is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.curr is not None and self.cell is not None:
            self.curr.append(" ".join(" ".join(self.cell).split()));self.cell=None
        elif tag=="tr" and self.curr is not None:
            if len(self.curr)>=9:self.rows.append(self.curr)
            self.curr=None
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"DRNAS-Atlas10-metadata-only/2026-11-22"})
    with urllib.request.urlopen(req,timeout=30) as resp:
        raw=resp.read(4_000_000)
        return raw,resp.geturl()
raw=source=None
for url in URLS:
    try:
        candidate,canonical=fetch(url)
        parsed=Rows();parsed.feed(candidate.decode("utf8","replace"))
        hits=[r for r in parsed.rows if len(r)>=9 and
              "mod2c-rand3bip-unsat-" in r[8] and r[2]=="random-graph-xorsat"
              and r[4]=="unsat"]
        print("ATLAS10_METADATA_QUERY",json.dumps({"url":url,
            "rows":len(parsed.rows),"unsat_masked":len(hits),"size_bytes":len(candidate)}),flush=True)
        if hits:raw=candidate;source=canonical;break
    except Exception as exc:
        print("ATLAS10_METADATA_QUERY_ERROR",json.dumps({"url":url,"error":str(exc)[:250]}),flush=True)
if raw is None:
    print("ATLAS10_CATALOG_UNAVAILABLE; freeze only existing original ID105; NO_SUBSTITUTION")
    raw=b"";source="UNKNOWN"
    hits=[]
bykey={}
for r in hits:
    m=re.search(r"mod2c-rand3bip-unsat-(\d+)-(\d+)",r[8])
    if not m:continue
    k=(int(m.group(1)),int(m.group(2)))
    gbd=r[0].strip()
    if not re.fullmatch("[0-9a-f]{32}",gbd):continue
    bykey[(gbd,k[0],k[1])]={"gbd_hash":gbd,"isohash":r[1],
            "family":r[2],"catalog_result":r[4],
            "filename":r[8],"size_param":k[0],"seed_param":k[1]}
candidates=sorted(bykey.values(),key=lambda r:(r["size_param"],r["seed_param"],r["gbd_hash"]))
# Existing Atlas9 original is always selected, and its raw SHA already pinned.
previous={"gbd_hash":"07f5f3ca046261c3819c5c888ac837e5",
"isohash":"c76cc643e32004f5840c305a217d58de",
"filename":"mod2c-rand3bip-unsat-105-3.shuffled-as.sat05-2325.cnf.xz",
"size_param":105,"seed_param":3,
"previously_frozen_raw_SHA":"828a649666ddc6cd3bd9085821eb5058737f6a9e55c8904eff0681720e5938eb"}
selected=[previous];chosen={105}
# Only HEAD availability, before opening any CNF contents.
for low,high,target in BANDS:
    ranked=sorted((x for x in candidates if low<=x["size_param"]<=high and
                   x["size_param"] not in chosen),
                   key=lambda x:(abs(x["size_param"]-target),x["gbd_hash"]))
    for r in ranked[:10]:
        link="https://benchmark-database.de/file/"+r["gbd_hash"]+"?context=cnf"
        try:
            request=urllib.request.Request(link,method="HEAD",
                        headers={"User-Agent":"DRNAS-Atlas10-metadata-size-audit"})
            with urllib.request.urlopen(request,timeout=15) as response:
                length=response.headers.get("Content-Length")
                length=int(length) if length and length.isdigit() else None
                status=response.status
            if status==200 and (length is None or length<=8_000_000):
                selected.append(dict(r,archive_HEAD_bytes=length,
                                   selection_band=[low,high],target_size=target))
                chosen.add(r["size_param"])
                print("ATLAS10_META_SELECTED",json.dumps(selected[-1],sort_keys=True),flush=True)
                break
        except Exception as error:
            print("ATLAS10_META_HEAD_MISSING",json.dumps({"gbd":r["gbd_hash"],
                   "reason":str(error)[:95]}),flush=True)
assert len({r["gbd_hash"] for r in selected})==len(selected)
manifest={
 "protocol":"DRNAS-ATLAS10-FIXED-METADATA-AND-PAIRED-20261122",
 "catalog_url":source,"catalog_snapshot_SHA256":hashlib.sha256(raw).hexdigest(),
 "no_solver_or_ATLAS10_detector_run_before_metadata_selection":True,
 "selection_algorithm":"One pre-known original plus up to 3 new accessible originals in frozen size bands 60..100, 110..160, 170..300 by pre-fixed target closeness and sorted GBD hash. No substitution after freeze.",
 "bands":BANDS,"source_candidates":len(candidates),
 "selection":selected,"expected_count":len(selected),
 "originals_known_historically":"UNSAT labels in catalog, not blind outcomes",
 "no_outcome_guided_replacements":True,
 "repetitions":3,"arms":["ATLAS9_VERIPB","Kissat4.0.4","CaDiCaL2.1.3"],
 "cap_e2e_seconds":30,"PAR2_timeout_seconds":60,
 "one_logical_cpu_each_serial":True,
 "strict_only_independent_standard_proofs":True
}
(OUT/"catalog.html").write_bytes(raw)
(OUT/"candidate-metadata.json").write_text(json.dumps(candidates,sort_keys=True,indent=2)+"\n")
(OUT/"selection.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
print("ATLAS10_METADATA_FROZEN",json.dumps({"candidates":len(candidates),
      "selected":len(selected),"selected_sizes":[s["size_param"] for s in selected],
      "catalog_sha":manifest["catalog_snapshot_SHA256"]},sort_keys=True),flush=True)
