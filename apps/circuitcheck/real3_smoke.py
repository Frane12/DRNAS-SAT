#!/usr/bin/env python3
"""REAL3 source-independent type recognition, mutation and renaming checks.

No Yosys or SAT needed here. Only the separate formal miter run can
substantiate independent original RTL vs external mathematical spec.
"""
import argparse,json,re
from pathlib import Path
from real3_classifier import classify,Unknown
from real3_harness import configuration,expected_masks

def rewrite_tokens(text, pairs):
    for old,new in pairs.items():
        text=re.sub(r"\b"+re.escape(old)+r"\b",new,text)
    return text

def negative_expected(raw):
    try:classify(raw)
    except Unknown:return True
    return False

def main():
    p=argparse.ArgumentParser();p.add_argument("--external",required=True,type=Path)
    a=p.parse_args();root=a.external.resolve()
    manifest=json.loads((root/"manifest.json").read_text())
    sources={}
    for rec in manifest["sources"]:
        p=root/"upstream"/(rec["name"]+(".sv" if rec["path"].endswith(".sv") else ".v"))
        assert p.is_file()
        sources[rec["name"]]=p.read_bytes()
    recognized=0
    for entry in manifest["cases"]:
        raw=sources[entry["src"]]
        result=classify(raw,configuration(entry))
        actual=[int(m,16) for m in result["output_masks_hex"]]
        expected=expected_masks(entry)
        if actual!=expected:
            raise RuntimeError("SOURCE_NOT_MATCHING_INDEPENDENT_SPEC "+entry["name"])
        if result["status"] if "status" in result else False:
            raise RuntimeError("unexpected classifier run report")
        recognized+=1
        print("REAL3_UNSEEN_CLASS_RECOGNIZED",entry["name"],result["class"],
              result["data_width"],"inputs",sum(x["width"] for x in result["input_order"]),flush=True)
    assert recognized==18
    # Arbitrary design and wire renaming should not break source recognition.
    renames=[
      ("uart",{"parity_gen":"derived_parity_unit","data":"bus_payload",
               "parity_bit":"flag_signal","BITS_NUM":"PAYLOAD_BITS",
               "ODD_PARITY":"IS_ODD"}),
      ("even",{"even_parity_generator":"device_check","data_in":"bits",
               "parity":"result_bit"}),
      ("chunks",{"dataint_parity":"stream_check","data_in":"payload",
                 "parity_in":"received","parity_type":"mode",
                 "parity":"computed","parity_err":"bad",
                 "WIDTH":"BUS_BITS","CHUNKS":"BANKS"})
    ]
    for name,mapping in renames:
        old=next(x for x in manifest["cases"] if x["src"]==name and not x["fault"])
        changed=rewrite_tokens(sources[name].decode(),mapping).encode()
        overrides={mapping.get(k,k):v for k,v in configuration(old).items()}
        verified=classify(changed,overrides)
        masks=[int(v,16) for v in verified["output_masks_hex"]]
        if masks!=expected_masks(old):
            raise RuntimeError("RENAMING_CHANGED_MEANING "+name)
        print("REAL3_RENAMED_UNSEEN_SOURCE_PASS",name,flush=True)
    # Tampering with the actual source grammar MUST NOT silently inherit the
    # known-good theorem or the expected external contract.
    actual=sources["uart"].decode()
    modified=actual.replace("~(^data)","^data")
    assert modified!=actual
    params={"BITS_NUM":8,"ODD_PARITY":1}
    try:
        result=classify(modified.encode(),params)
    except Unknown:pass
    else:
        # The source itself changed meaning; the independent frozen contract
        # expects odd parity and hence must be rejected.
        odd=next(x for x in manifest["cases"] if x["id"]=="uart_odd8" and not x["fault"])
        if [int(x,16) for x in result["output_masks_hex"]]==expected_masks(odd):
            raise RuntimeError("ALTERED_PARITY_ACCEPTED_AS_ORIGINAL")
    assert negative_expected(sources["even"]+b"\nassign parity=1'b1;\n")
    assert negative_expected(sources["even"].replace(b"^data_in",b"&data_in"))
    assert negative_expected(sources["chunks"].replace(b"!= parity_in[i]",b"== parity_in[i]"))
    assert negative_expected(sources["clocked"])
    print("REAL3_ALL_18_HOLDOUT_CLASSIFICATIONS_AND_ADVERSARIAL_TESTS_PASS",flush=True)
if __name__=="__main__":main()
