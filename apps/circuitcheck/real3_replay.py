#!/usr/bin/env python3
"""REAL3 independent mathematical certificate check against frozen *separate*
UART/parity domain specification. Does not import source classifier.

This checker validates inputs, output coefficient basis, SHA, exact
explicit parity/spec equations and the claimed verdict. Source-to-mask
translation still depends on the narrow REAL3 parser; a separate Yosys
CNF check crossvalidates source semantics on the third-party original.
"""
import argparse,hashlib,json
from pathlib import Path
from real3_harness import expected_masks,configuration

def sha(data):return hashlib.sha256(data).hexdigest()

def replay(certificate,source,entry):
    c=json.loads(Path(certificate).read_text())
    if c.get("source_sha256")!=sha(Path(source).read_bytes()):
        raise ValueError("SOURCE_HASH_CHANGED")
    if c.get("class") not in ("SCALAR_PARITY","CHUNKED_PARITY_CHECKER"):
        raise ValueError("UNKNOWN_CLASS")
    if c.get("params")!={**c.get("params",{}),**configuration(entry)}:
        raise ValueError("SPEC_PARAMETER_MISMATCH")
    required=expected_masks(entry)
    masks=[int(x,16) for x in c["output_masks_hex"]]
    inputs=sum(x["width"] for x in c["input_order"])
    outputs=sum(x["width"] for x in c["output_order"])
    if inputs<=0 or len(required)!=outputs or masks!=required:
        raise ValueError("INDEPENDENT_PARITY_SPEC_MISMATCH")
    if any(m >= (1<<(inputs+1)) or m<0 for m in masks):
        raise ValueError("BAD_AFFINE_VARIABLE_BASIS")
    # No output is checked solely because the external file is from a
    # known repository: any source with the accepted grammar is admitted.
    return {"status":"REPLAYED_AFFINE_SPEC_COEFFICIENTS",
            "input_bits":inputs,"output_bits":outputs,
            "validated_coefficients":len(masks),
            "source_proof_scope":"restricted complete-source grammar only"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--certificate",type=Path,required=True)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--entry",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:r=replay(a.certificate,a.source,json.loads(a.entry.read_text()))
    except (ValueError,KeyError,TypeError,OSError,IndexError) as exc:
        r={"status":"REJECTED","why":str(exc)}
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("REAL3_REPLAY",r["status"],flush=True)
    return 0 if r["status"]=="REPLAYED_AFFINE_SPEC_COEFFICIENTS" else 2
if __name__=="__main__":raise SystemExit(main())
