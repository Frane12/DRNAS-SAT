#!/usr/bin/env python3
"""Tamper DELTA2-C completed original CRC-64 fault proof archive.

Uses immutable generated artifacts from successful run 45286501965.
Each damaged proof must fail replay; no Yosys or SAT solver required.
"""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"apps/circuitcheck"))
from delta2c_verify import replay, Rejected
from delta2c_source_guard import RejectedSource
from delta2b_verify import VerificationError
from delta1_verify import Invalid


def expect_reject(name, func):
    try:
        func()
    except (Rejected,RejectedSource,VerificationError,Invalid,KeyError,ValueError,TypeError):
        print("DELTA2C_TAMPER_REJECTED",name,flush=True)
    else:
        raise RuntimeError("TAMPERED_CERT_ACCEPTED "+name)

def main():
    proof=Path(sys.argv[1]).resolve()
    orig=Path(sys.argv[2]).resolve()
    outcome=replay(proof,orig,"reference")
    assert outcome["status"]=="CHECKED_RESTRICTED_INDUCTION"

    cert=proof/"delta2c_certificate.json"
    original=cert.read_bytes()
    obj=json.loads(original)
    def altered(name, mutate):
        changed=copy.deepcopy(obj)
        mutate(changed)
        cert.write_text(json.dumps(changed))
        try:
            expect_reject(name,lambda:replay(proof,orig,"reference"))
        finally:
            cert.write_bytes(original)
    altered("FALSE_INDUCTION_STATUS",lambda d:d.update(status="CHECKED_RESTRICTED_INDUCTION"))
    altered("INVALID_K1_COEFFICIENT",lambda d:d["groups"]["1"]["output_rows_hex"].__setitem__(
        0,hex(int(d["groups"]["1"]["output_rows_hex"][0],16)^1)))
    altered("INCOMPLETE_K_LIST",lambda d:d["groups"].pop("8"))
    altered("DIFFERENT_INITIAL_STATE",lambda d:d.update(iterations=7))
    files=[
        (proof/"k2/block.v","RAW_RTL_MODIFICATION",b"\n// mutated"),
        (proof/"k8/proof/netlist.json","GATE_NETLIST_MODIFICATION",b"\n"),
    ]
    for path,name,mutation in files:
        raw=path.read_bytes()
        path.write_bytes(raw+mutation)
        try:expect_reject(name,lambda:replay(proof,orig,"reference"))
        finally:path.write_bytes(raw)
    # A JSON whitespace append is not semantic tampering. Mutate values,
    # not harmless serialization, to check logical proof integrity.
    metapath=proof/"k4/block_meta.json"
    basepath=proof/"base/delta2b_composition.json"
    for path,name,field in [(metapath,"BLOCK_META_COEFFICIENT_TAMPERING","output_rows_hex"),
                            (basepath,"BASE_MATRIX_TAMPERING","A_rows_hex")]:
        raw=path.read_bytes()
        data=json.loads(raw)
        data[field][0]=hex(int(data[field][0],16)^1)
        path.write_text(json.dumps(data))
        try:expect_reject(name,lambda:replay(proof,orig,"reference"))
        finally:path.write_bytes(raw)
    changed=orig.with_name("altered_source.v")
    raw=orig.read_bytes()
    assert b"32'hEDB88320" in raw
    changed.write_bytes(raw.replace(b"32'hEDB88320",b"32'h82F63B78",1))
    expect_reject("ALTERNATE_SOURCE_NOT_ORIGINAL",lambda:replay(proof,changed,"reference"))
    result=replay(proof,orig,"reference")
    assert result["status"]=="CHECKED_RESTRICTED_INDUCTION"
    print("DELTA2C_TAMPER_AND_RESTORATION_PASS",flush=True)


if __name__=="__main__":
    main()
