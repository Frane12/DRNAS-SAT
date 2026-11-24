#!/usr/bin/env python3
"""REAL4 registered blind holdout cohort: source selection AFTER engine prelock.

Only repository identifiers, module paths, independently recorded Git blob
hashes and exact upstream commits are recorded. Files are kept UNMODIFIED.
No per-project tuning of the already-locked REAL4 interpreter is permitted.
Any unsupported source, compile failure, timeout or lack of affine cones
stays in the cohort, not silently dropped. Third-party licenses are noted.
"""
import argparse,hashlib,json,urllib.parse,urllib.request
from pathlib import Path

CASES=[
 {"id":"aes_sbox","repo":"secworks/aes",
  "commit":"83cc2709e01690e30afe5ddc13f90c63edee7c28",
  "path":"src/rtl/aes_sbox.v","top":"aes_sbox",
  "blob":"21bdecdfae52a85fd2eb9524277bc6305ca0fa11",
  "domain":"cryptographic nonlinear S-box","license":"BSD-2-Clause"},
 {"id":"uart_tx","repo":"ZipCPU/wbuart32",
  "commit":"f43a6b83c3a70fb2ac0696a45c5545b233fb860b",
  "path":"rtl/txuart.v","top":"txuart",
  "blob":"2999bbfdbcacf83d4c34ed3cff749b7e40c6840d",
  "domain":"clocked UART transmitter","license":"GPL-3.0"},
 {"id":"axis_fifo","repo":"alexforencich/verilog-axis",
  "commit":"48ff7a7e2ef782cf778d47910cf85835c64b1bce",
  "path":"rtl/axis_fifo.v","top":"axis_fifo",
  "blob":"dfa465792f052486ac6f8d4c483318d4a338076d",
  "domain":"streaming FIFO controller","license":"MIT"},
 {"id":"picorv32","repo":"YosysHQ/picorv32",
  "commit":"ef203c2b0a3fb793280f5114941416c425c5b461",
  "path":"picorv32.v","top":"picorv32",
  "blob":"cc45fa998f1857b06a856ea59b931f6c37e06b34",
  "domain":"RISC-V CPU","license":"ISC"},
 {"id":"tmds_channel","repo":"hdl-util/hdmi",
  "commit":"517e21413d90affef34584c535e366be85a6b4cb",
  "path":"src/tmds_channel.sv","top":"tmds_channel",
  "blob":"9400c1652926f8ffb3a98844abbd19cf68a9d054",
  "domain":"HDMI TMDS encoder","license":"verify upstream"},
 {"id":"sha256_w_mem","repo":"secworks/sha256",
  "commit":"837c5cc396f001d18f2c765721c585716eb439ae",
  "path":"src/rtl/sha256_w_mem.v","top":"sha256_w_mem",
  "blob":"a332baa23ea183d5ec0fbff2829ac4f4a2be729d",
  "domain":"SHA-256 message schedule with state","license":"BSD-2-Clause"}
]
ENGINE_LOCK_RUN=45339922757
ENGINE_LOCK_BRANCH="experiment/real4-blind-gate-cuts-20261124"
GENERIC_MAX_CELLS=200000
YOSYS_CAP_SECONDS=100

def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def freeze(root:Path):
    root.mkdir(parents=True,exist_ok=True)
    records=[]
    for case in CASES:
        url=("https://raw.githubusercontent.com/"+case["repo"]+"/"+case["commit"]+
             "/"+urllib.parse.quote(case["path"],safe="/"))
        request=urllib.request.Request(url,headers={"User-Agent":"DRNAS-REAL4-BlindFrozen"})
        with urllib.request.urlopen(request,timeout=40) as response:
            raw=response.read()
        if blob(raw)!=case["blob"]:
            raise ValueError("UNPINNED_NEW_SOURCE "+case["id"])
        filepath=root/(case["id"]+".sv")
        filepath.write_bytes(raw)
        records.append({**case,"sha256":sha(raw),"bytes":len(raw),
                        "filename":filepath.name,"url":url})
        print("REAL4_FROZEN",case["id"],case["blob"],len(raw),flush=True)
    doc={"protocol":"DRNAS_REAL4_BLIND_EXTERNAL_6_V1",
         "prelock_run_id":ENGINE_LOCK_RUN,
         "engine_locked_before_external_selection":True,
         "claim":"six new untouched third-party original HDL modules, mixed Boolean and sequential, no cherry-picked success",
         "max_synthesis_seconds":YOSYS_CAP_SECONDS,
         "max_cells":GENERIC_MAX_CELLS,
         "cases":records}
    (root/"manifest.json").write_text(json.dumps(doc,indent=2)+"\n")
    print("REAL4_HOLDOUT_COHORT_LOCKED",len(records),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    freeze(a.out.resolve())
