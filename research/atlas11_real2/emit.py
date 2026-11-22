#!/usr/bin/env python3
"""ATLAS10 source-only known-rule proof emitter for equal-resource benchmark.

Output is a PBP proof of UNSAT, NOT an accepted verdict. External VeriPB
must check it on unchanged original. No instance filename, family,
catalog status or benchmark label is passed to this emitter.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"research/atlas6_camouflage"))
sys.path.insert(0,str(ROOT/"research/atlas8_masked_unsat"))
from semantic_and_xor import extract,gauss_model
from check_semantic import verify,Invalid
from proof import build_standard_original_proof

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cnf",type=Path,required=True)
    ap.add_argument("--proof",type=Path,required=True)
    ap.add_argument("--meta",type=Path,required=True)
    args=ap.parse_args()
    try:
        raw=args.cnf.read_bytes()
        quotient,relation=extract(raw)
        checked=verify(raw,quotient,relation)
        if checked.get("status")!="FULL_SOURCE_AND_GF2_EQUIVALENCE_VERIFIED":
            raise ValueError("INDEPENDENT_SOURCE_SEMANTICS_REJECTED")
        if gauss_model(relation["rows"],relation["quotient_variables"]) is not None:
            print("ATLAS10_NO_GF2_CONTRADICTION",flush=True)
            return 2
        pbp,meta=build_standard_original_proof(raw,quotient,relation)
        assert meta["source_sha256"]==hashlib.sha256(raw).hexdigest()
        args.proof.write_text(pbp)
        args.meta.write_text(json.dumps({**meta,
            "independent_source_truth_table_checks":checked["source_truth_tables_checked"],
            "masked_AND_tokens":checked["masked_pairs_verified"],
            "virtual_xor_rows":len(relation["rows"]),
            "requires_external_Veripb":True},sort_keys=True,indent=2)+"\n")
        print("ATLAS10_PROOF_EMITTED "+json.dumps(meta,sort_keys=True),flush=True)
        return 0
    except (ValueError,KeyError,TypeError,MemoryError,OverflowError,UnicodeError,Invalid) as error:
        args.proof.unlink(missing_ok=True)
        args.meta.unlink(missing_ok=True)
        print("ATLAS10_SAFE_UNKNOWN "+str(error)[:300],flush=True)
        return 2
if __name__=="__main__":sys.exit(main())
