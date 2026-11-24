#!/usr/bin/env python3
"""REAL6 prospective external RTL source freeze AFTER green motif prelock.

Each original source is an exact unedited public Git blob at a fixed commit.
Five modules were NOT part of REAL4 or REAL5-Q study, and are all kept,
including any missing submodule or unsupported Yosys frontend. No
source-specific detector rules or cherry-picking after results.
"""
from __future__ import annotations
import argparse,hashlib,json,urllib.parse,urllib.request
from pathlib import Path

ENGINE_LOCK=45347547028
ENGINE_SHA="f27a4a3f2efc73d0c8aa35fcca8092acf5d973a8b46004de2c1d90706ebb4365"
VERIFY_SHA="28d660b8486f8590ea3fa2091a18e6df9cec7cd95c76b59d8315ecf5956ab803"
TARGETS=[
 {"id":"chacha_qr","repo":"secworks/chacha",
  "commit":"7eaba360df9fed9fc2db98d5f3df81cf01e5b604",
  "file":"src/rtl/chacha_qr.v","top":"chacha_qr",
  "blob":"cc7c2c687a6ea8e30a1cb6b0e688912ea42d6956",
  "domain":"ChaCha quarter round, nonlinear integer additions"},
 {"id":"aes_key_mem","repo":"secworks/aes",
  "commit":"83cc2709e01690e30afe5ddc13f90c63edee7c28",
  "file":"src/rtl/aes_key_mem.v","top":"aes_key_mem",
  "blob":"a6f684dbb4174697d997dca3983676218dcd4e00",
  "domain":"AES key expansion, state and nonlinear substitution"},
 {"id":"uart_ufifo","repo":"ZipCPU/wbuart32",
  "commit":"f43a6b83c3a70fb2ac0696a45c5545b233fb860b",
  "file":"rtl/ufifo.v","top":"ufifo",
  "blob":"cfab5573997111d03b51e30743fa34145951b5ea",
  "domain":"Clocked UART FIFO"},
 {"id":"axis_adapter","repo":"alexforencich/verilog-axis",
  "commit":"48ff7a7e2ef782cf778d47910cf85835c64b1bce",
  "file":"rtl/axis_adapter.v","top":"axis_adapter",
  "blob":"9a8ad5d2aba98ef82ce785a8217de4d47c500300",
  "domain":"AXI streaming width adapter"},
 {"id":"sha512_core","repo":"secworks/sha512",
  "commit":"e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd",
  "file":"src/rtl/sha512_core.v","top":"sha512_core",
  "blob":"44e26177624d30561f68327757a208927dd96d35",
  "domain":"SHA512 core and round functions"}
]
def git_blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    root=args.out.resolve();root.mkdir(parents=True,exist_ok=True)
    records=[]
    for info in TARGETS:
        url="https://raw.githubusercontent.com/"+info["repo"]+"/"+info["commit"]+"/"+urllib.parse.quote(info["file"],safe="/")
        request=urllib.request.Request(url,headers={"User-Agent":"DRNAS-REAL6-HOLDOUT"})
        with urllib.request.urlopen(request,timeout=40) as response:
            raw=response.read()
        if git_blob(raw)!=info["blob"]:
            raise RuntimeError("UPSTREAM_ORIGINAL_GIT_BLOB_CHANGED "+info["id"])
        path=root/(info["id"]+".v")
        path.write_bytes(raw)
        records.append({**info,"sha256":sha(raw),"filename":path.name,
                        "download_url":url,"size_bytes":len(raw)})
        print("REAL6_PROSPECTIVE_SOURCE_FROZEN",info["id"],sha(raw),flush=True)
    frozen={"protocol":"DRNAS_REAL6_PROSPECTIVE_FIVE_UNKNOWN_ORIGINAL_RTL",
            "engine_prelock_run":ENGINE_LOCK,
            "motif_engine_sha256":ENGINE_SHA,
            "motif_verifier_sha256":VERIFY_SHA,
            "fixed_sources_selected_after_engine_prelock":True,
            "cases":records,
            "all_outcomes_kept":True}
    (root/"manifest.json").write_text(json.dumps(frozen,indent=2)+"\n")
    print("REAL6_ORIGINAL_FIVE_SOURCE_COHORT_LOCKED",len(records),flush=True)
if __name__=="__main__":main()
