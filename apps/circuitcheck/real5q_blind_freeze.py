#!/usr/bin/env python3
"""REAL5-Q *prospective* original RTL source cohort, pinned AFTER prelock.

The engine and independent checker have been fixed at green run 45344568141
before selecting these external sources. No new source-specific condition or
formula is installed in the engine. All modules must remain in the report,
including unsupported library dependencies, parser errors, and TIMEOUT.
"""
import argparse,hashlib,json,urllib.parse,urllib.request
from pathlib import Path

PRELOCK_RUN=45344568141
ORIGINALS=[
 {"id":"sha512_w_mem","repo":"secworks/sha512",
  "commit":"e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd",
  "path":"src/rtl/sha512_w_mem.v",
  "blob":"78f6d6eb51a9acbc8ee912d41563411adc3cc28f",
  "top":"sha512_w_mem","role":"sequential SHA512 data schedule"},
 {"id":"chacha_core","repo":"secworks/chacha",
  "commit":"7eaba360df9fed9fc2db98d5f3df81cf01e5b604",
  "path":"src/rtl/chacha_core.v",
  "blob":"735abf4fcb6057bf91808736e0413ca4e8379766",
  "top":"chacha_core","role":"ChaCha crypto datapath and control"},
 {"id":"axis_register","repo":"alexforencich/verilog-axis",
  "commit":"48ff7a7e2ef782cf778d47910cf85835c64b1bce",
  "path":"rtl/axis_register.v",
  "blob":"93fe0bee6ff1f50d1e2236f5babc283bada2f1a2",
  "top":"axis_register","role":"AXI stream pipelining"},
 {"id":"eth_mac_1g","repo":"alexforencich/verilog-ethernet",
  "commit":"77320a9471d19c7dd383914bc049e02d9f4f1ffb",
  "path":"rtl/eth_mac_1g.v",
  "blob":"0e1b9a12f66b24e104733a3e00975dbf78f98459",
  "top":"eth_mac_1g","role":"Ethernet MAC logic"},
 {"id":"ibex_alu","repo":"lowRISC/ibex",
  "commit":"041098fe2380124dea536a0985cb85469fb206c4",
  "path":"rtl/ibex_alu.sv",
  "blob":"635506cad77967f273f497691bbbf34a5651da28",
  "top":"ibex_alu","role":"RISC-V arithmetic logic"}
]
def gitblob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def sha(b):return hashlib.sha256(b).hexdigest()
def freeze(root):
    root.mkdir(parents=True,exist_ok=True)
    stored=[]
    for x in ORIGINALS:
        url="https://raw.githubusercontent.com/"+x["repo"]+"/"+x["commit"]+"/"+urllib.parse.quote(x["path"],safe="/")
        req=urllib.request.Request(url,headers={"User-Agent":"DRNAS-REAL5Q-Prospective-External-RTL"})
        with urllib.request.urlopen(req,timeout=45) as r:
            data=r.read()
        if gitblob(data)!=x["blob"]:
            raise RuntimeError("PINNED_EXTERNAL_SOURCE_SHA_INVALID "+x["id"])
        where=root/(x["id"]+".sv")
        where.write_bytes(data)
        record={**x,"sha256":sha(data),"bytes":len(data),"source_filename":where.name,"source_url":url}
        stored.append(record)
        print("REAL5Q_BLIND_SOURCE_PINNED",x["id"],record["sha256"],flush=True)
    manifest={
        "protocol":"DRNAS_REAL5Q_PROSPECTIVE_5_NEW_UNCHANGED_RTL_20261124",
        "prelock_run":PRELOCK_RUN,
        "mathematical_engine_sha256":"fc0ed0b1a57bd5b0df75ba3f307faccef7a763edb39408e20e278cd09d40d35a",
        "independent_checker_sha256":"a7203de8c48148dc24a9bb37f593e1b924b5e3d24c8cdf767e6bbd91c117738b",
        "source_cohort_chosen_after_prelock":True,
        "allow_any_outcome":True,
        "cases":stored
    }
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("REAL5Q_NEW_HOLDOUT_FIVE_SOURCE_COHORT_LOCKED",flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    freeze(a.out.resolve())
