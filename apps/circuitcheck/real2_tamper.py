#!/usr/bin/env python3
"""REAL2 adversarial source, harness and certificate controls."""
from __future__ import annotations
import argparse,copy,json
from pathlib import Path
from real2_prove import prove,Unknown
from real2_verify import replay,Invalid
from real1_generate import CASES,wrapper

def expected_rejection(name,fn):
    try:
        fn()
    except (Unknown,Invalid,ValueError):
        print("REAL2_TAMPER_REJECTED",name,flush=True)
        return
    raise AssertionError("UNSOUND_TAMPER_ACCEPTED "+name)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--external",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    source=(a.external/"upstream/alex_lfsr.v").read_bytes()
    byname={c["id"]:c for c in CASES}
    base=byname["crc16_ccitt8"]
    for broken in (False,True):
        name=base["id"]+("_fault" if broken else "_equal")
        raw=wrapper(base,broken).encode()
        certificate=prove(source,raw,name)
        sourcefile=a.out/"source.v";sourcefile.write_bytes(source)
        wrapperfile=a.out/"wrapper.v";wrapperfile.write_bytes(raw)
        certfile=a.out/"proof.json"
        certfile.write_text(json.dumps(certificate))
        assert replay(certfile,sourcefile,wrapperfile,name)["status"]=="CHECKED_RESTRICTED_PARITY_SOURCE"
        # Explicitly corrupt the proof's claimed result, preserving bytes.
        changed=copy.deepcopy(certificate)
        changed["status"]=("EQUIVALENT_RESTRICTED_SOURCE" if broken
                            else "DIFFERENT_RESTRICTED_SOURCE")
        certfile.write_text(json.dumps(changed))
        expected_rejection("FALSE_VERDICT",lambda:replay(certfile,sourcefile,wrapperfile,name))
        changed=copy.deepcopy(certificate);changed["wrapper_sha256"]="0"*64
        certfile.write_text(json.dumps(changed))
        expected_rejection("FALSE_HARNESS_SHA",lambda:replay(certfile,sourcefile,wrapperfile,name))
        certfile.write_text(json.dumps(certificate))
        altered=bytearray(raw)
        altered+=b"\nassign out[0]=1'b0;\n"
        expected_rejection("ADDED_OUTPUT_DRIVER",lambda:prove(source,bytes(altered),name))
        faulty_param=raw.replace(b'16\\'h1021',b'16\\'h1023',1)
        expected_rejection("CHANGED_POLYNOMIAL",lambda:prove(source,faulty_param,name))
        faulty_signal=raw.replace(b".state_in(state)",b".state_in(data)",1)
        expected_rejection("CHANGED_PORT_WIRING",lambda:prove(source,faulty_signal,name))
        modified=source.replace(b"state_reg = state_reg ^ state_in[i];",
                                b"state_reg = state_reg & state_in[i];",1)
        expected_rejection("MODIFIED_UPSTREAM_PARITY",lambda:prove(modified,raw,name))
        checker_source=a.out/"mutated.v";checker_source.write_bytes(modified)
        expected_rejection("SOURCE_HASH_NOT_ACCEPTED",lambda:replay(certfile,checker_source,wrapperfile,name))
        # Restore and replay to show the checker didn't silently learn
        # the adversarial changes.
        assert replay(certfile,sourcefile,wrapperfile,name)["status"]=="CHECKED_RESTRICTED_PARITY_SOURCE"
    print("REAL2_TAMPER_SUITE_PASS",flush=True)
if __name__=="__main__":main()
