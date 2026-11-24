#!/usr/bin/env python3
"""Freeze independent real third-party RTL source corpus before benchmarking.

Pin complete source files with Git SHA1 blob and Git commit.
No source identities are consulted by REAL3 source grammar recognizer.
"""
import argparse,hashlib,json,urllib.request
from pathlib import Path

SOURCES=[
 ("uart","code002-nova/uart-systemverilog","106e1eb3f21aea962b1b5645fcfe7fea2e594f50",
  "rtl/common/parity_gen.sv","c081323460e5e1b96c0a55d961667a28ffb6a356"),
 ("even","Supreethm2004/Basics-of-Verilog-Coding","aedfd3c6de9b653884f242e9a075f7f4428aa69f",
  "even parity generator.v","e7a815fcc87330b9a5347e811b172c4ae63c2d14"),
 ("chunks","sean-galloway/RTLDesignSherpa","41dee14400747515c92ed5869e76b5ebc6f07284",
  "rtl/common/dataint_parity.sv","7c4406987eaa31b42557c0af4f01676022f0609e"),
 ("clocked","Kholoud-Ebrahim/UART_Protocol","24476deea6829340d68849d983a70c5516a34a69",
  "uart_tx/rtl/parity_calc.v","8b3981f39de2c715c628456dd58e25ea37dbbd6f")
]
# Configuration schedule frozen before solver results (includes odd/even,
# non-multiple width and a real sequential negative control).
CONFIGS=[
 {"id":"uart_even8","src":"uart","kind":"uart","width":8,"odd":0},
 {"id":"uart_odd8","src":"uart","kind":"uart","width":8,"odd":1},
 {"id":"uart_even16","src":"uart","kind":"uart","width":16,"odd":0},
 {"id":"uart_odd31","src":"uart","kind":"uart","width":31,"odd":1},
 {"id":"even8","src":"even","kind":"even","width":8},
 {"id":"chunks32x4","src":"chunks","kind":"chunk","width":32,"chunks":4},
 {"id":"chunks33x4","src":"chunks","kind":"chunk","width":33,"chunks":4},
 {"id":"chunks65x7","src":"chunks","kind":"chunk","width":65,"chunks":7},
 {"id":"chunks128x8","src":"chunks","kind":"chunk","width":128,"chunks":8}
]
def gitblob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\x00"+b).hexdigest()
def sha(b):return hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    root=a.out.resolve();(root/"upstream").mkdir(parents=True,exist_ok=True)
    infos=[]
    for name,repo,commit,path,digest in SOURCES:
        url="https://raw.githubusercontent.com/"+repo+"/"+commit+"/"+path
        request=urllib.request.Request(url,headers={"User-Agent":"DRNAS-REAL3-ProofCorpus"})
        with urllib.request.urlopen(request,timeout=40) as f:data=f.read()
        if gitblob(data)!=digest:
            raise RuntimeError("EXTERNAL_UPSTREAM_BLOB_CHANGED "+name+" "+gitblob(data))
        dest=root/"upstream"/(name+(".sv" if path.endswith(".sv") else ".v"))
        dest.write_bytes(data)
        infos.append({"name":name,"repo":repo,"commit":commit,"path":path,
                      "sha1_git_blob":digest,"sha256":sha(data),
                      "location":str(dest),"url":url})
    cases=[{**c,"name":c["id"]+("_fault" if faulty else "_equal"),
            "fault":faulty,"expected":"DIFFERENT" if faulty else "EQUIVALENT"}
           for c in CONFIGS for faulty in (False,True)]
    doc={"protocol":"DRNAS_REAL3_UNSEEN_EXTERNAL_PARITY_20261124",
         "sources":infos,"cases":cases,
         "negative_controls":[{"source":"clocked","expected":"UNKNOWN"}],
         "original_sources_unmodified":True,
         "description":"3 independently authored public modules, separate original-spec harnesses and one clocked negative"}
    (root/"manifest.json").write_text(json.dumps(doc,indent=2)+"\n")
    print("REAL3_SOURCE_FREEZE_PASS",len(infos),"sources",len(cases),"cases",flush=True)
if __name__=="__main__":main()
