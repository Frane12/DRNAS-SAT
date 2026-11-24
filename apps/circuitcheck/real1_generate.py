#!/usr/bin/env python3
"""Frozen external FPGA RTL sources and real design-style equivalence fixtures.

No third-party DUT is rewritten. Download the pinned original Verilog bytes
from public upstream commits and verify Git blob SHA-1 with git hash-object.
The generated verification WRAPPERS instantiate two different real upstream
implementation styles (LOOP / REDUCTION), sharing the same input and state.
A deliberately faulty output bit is used only in the separate test wrapper.

This checks *implementation style equivalence*, not algorithmic correctness
against an independently established mathematical specification.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess,urllib.request
from pathlib import Path

SOURCES=[
 {"id":"alex_lfsr","repo":"alexforencich/verilog-lfsr",
  "commit":"c1f86d036745935f3812ec6ddc7821c70ef4c9de",
  "path":"rtl/lfsr.v","blob_sha1":"e3a472e3f280f3a697dee718b0416f2667181c00",
  "license":"MIT","role":"real parametric combinational Ethernet/CRC/PRBS core"},
 {"id":"zipcpu_uart","repo":"ZipCPU/wbuart32",
  "commit":"f43a6b83c3a70fb2ac0696a45c5545b233fb860b",
  "path":"rtl/rxuart.v","blob_sha1":"1506e563944a2da1c1b01be6c1a953ad92fdff7d",
  "license":"GPL-3.0-or-later (check upstream file)","role":"real sequential UART, expected unsupported"},
 {"id":"secworks_sha256","repo":"secworks/sha256",
  "commit":"837c5cc396f001d18f2c765721c585716eb439ae",
  "path":"src/rtl/sha256_core.v","blob_sha1":"ac25f8b492905a4a5c956e4ddfdfadf702dfda91",
  "license":"BSD-2-Clause","role":"real sequential/nonlinear SHA-256, expected unsupported"}
]
# Each case uses real unchanged implementation source, not a generated CRC DUT.
CASES=[
 {"id":"crc16_ccitt8","state_width":16,"data_width":8,"poly":"16'h1021",
  "config":"GALOIS","reverse":0},
 {"id":"crc32_ethernet32","state_width":32,"data_width":32,"poly":"32'h04c11db7",
  "config":"GALOIS","reverse":1},
 {"id":"crc32c_iscsi32","state_width":32,"data_width":32,"poly":"32'h1edc6f41",
  "config":"GALOIS","reverse":1},
 {"id":"prbs31_64","state_width":31,"data_width":64,"poly":"31'h10000001",
  "config":"FIBONACCI","reverse":0},
 {"id":"scrambler_64b66b","state_width":58,"data_width":64,"poly":"58'h8000000001",
  "config":"FIBONACCI","reverse":1},
 {"id":"crc32_ethernet128","state_width":32,"data_width":128,"poly":"32'h04c11db7",
  "config":"GALOIS","reverse":1}
]

def git_blob_sha(data):
    p=subprocess.run(["git","hash-object","--stdin"],input=data,capture_output=True,check=True)
    return p.stdout.decode().strip()

def get_source(source, dest:Path):
    url=("https://raw.githubusercontent.com/"+source["repo"]+"/"+
         source["commit"]+"/"+source["path"])
    req=urllib.request.Request(url,headers={"User-Agent":"DRNAS-RealRTL-Holdout/1.0"})
    with urllib.request.urlopen(req,timeout=35) as response:
        data=response.read()
    blob=git_blob_sha(data)
    if blob!=source["blob_sha1"]:
        raise RuntimeError("UPSTREAM_SOURCE_CHANGED_OR_BAD_SHA "+source["id"]+" "+blob)
    target=dest/(source["id"]+".v")
    target.write_bytes(data)
    return {"id":source["id"],"repo":source["repo"],"commit":source["commit"],
            "path":source["path"],"blob_sha1":blob,
            "sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data),
            "license":source["license"],"role":source["role"],
            "url":url,"local_path":str(target)}

def wrapper(case:dict,fault:bool)->str:
    w=case["state_width"];n=case["data_width"]
    poly=case["poly"];config=case["config"];reverse=case["reverse"]
    def instance(name,style):
        return (
        f"wire [{w-1}:0] {name}_state;\n"
        f"wire [{n-1}:0] {name}_data;\n"
        f"lfsr #(.LFSR_WIDTH({w}), .LFSR_POLY({poly}), "
        f".LFSR_CONFIG(\"{config}\"), .DATA_WIDTH({n}), "
        f".REVERSE({reverse}), .STYLE(\"{style}\")) "
        f"block_{name}(.data_in(data),.state_in(state),"
        f".data_out({name}_data),.state_out({name}_state));\n"
        )
    return (
    f"// Verification wrapper only. DUT is unmodified upstream alexforencich lfsr.v\n"
    f"module reference(input wire [{n-1}:0] data,"
    f"input wire [{w-1}:0] state,output wire [{n+w-1}:0] out);\n"
    +instance("ref","LOOP")+
    "assign out={ref_data,ref_state};\nendmodule\n"
    f"module candidate(input wire [{n-1}:0] data,"
    f"input wire [{w-1}:0] state,output wire [{n+w-1}:0] out);\n"
    +instance("impl","REDUCTION")+
    "assign out={impl_data,impl_state}"+(" ^ "+str(n+w)+"'h1" if fault else "")+";\nendmodule\n"
    f"module miter(input wire [{n-1}:0] data,"
    f"input wire [{w-1}:0] state,output wire mismatch);\n"
    f"wire [{n+w-1}:0] a,b;\n"
    "reference r(.data(data),.state(state),.out(a));\n"
    "candidate c(.data(data),.state(state),.out(b));\n"
    "assign mismatch=|(a^b);\nendmodule\n"
    )

def scan_outside_scope(source:dict,path:Path):
    text=path.read_text(errors="replace")
    # This is a structural negative control, not a full RTL compiler.
    clocked=bool(__import__("re").search(r"always\s*@\s*\(\s*(?:posedge|negedge)\b",text))
    return {"id":source["id"],"clocked":clocked,
            "classification":"OUTSIDE_COMBINATIONAL_AFFINE_STEP_SCOPE" if clocked else "NOT_CLASSIFIED",
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();root=a.out.resolve()
    root.mkdir(exist_ok=True,parents=True)
    upstream=root/"upstream";upstream.mkdir(exist_ok=True)
    originals=[get_source(src,upstream) for src in SOURCES]
    data={x["id"]:x for x in originals}
    cases=[]
    for base in CASES:
        for fault in (False,True):
            name=base["id"]+("_fault" if fault else "_equal")
            raw=wrapper(base,fault)
            target=root/(name+".v")
            target.write_text(raw)
            cases.append({"id":name,"family":base["id"],"fault":fault,
               "source_id":"alex_lfsr",
               "primary_input_bits":base["state_width"]+base["data_width"],
               "data_bits":base["data_width"],"state_bits":base["state_width"],
               "expected":"DIFFERENT_NETLIST" if fault else "EQUIVALENT_NETLIST",
               "sha256":hashlib.sha256(raw.encode()).hexdigest(),
               "path":str(target)})
    controls=[scan_outside_scope(data[x["id"]],upstream/(x["id"]+".v"))
              for x in SOURCES if x["id"]!="alex_lfsr"]
    if not all(x["clocked"] for x in controls):
        raise RuntimeError("unsupported-state control did not expose clocked logic")
    result={"protocol":"DELTA_REAL1_UPSTREAM_VERILOG_20261124",
        "claim":"Public unchanged third-party core, two native implementation styles; not independent specification equivalence",
        "upstream":originals,"cases":cases,"negative_controls":controls}
    (root/"manifest.json").write_text(json.dumps(result,indent=2)+"\n")
    print("FROZEN_REAL_RTL_PASS",len(cases),"style comparisons; external files",len(originals))
    print("NEGATIVE_CONTROLS",json.dumps(controls),flush=True)
if __name__=="__main__":main()
