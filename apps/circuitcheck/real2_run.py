#!/usr/bin/env python3
"""Run REAL2 on 12 original upstream-style cases with SHA-256 provenance.

Two repeats, exact pinned upstream files, original immutable harnesses.
No Yosys expansion, no hidden fallback to CDCL. Fails closed if any
source template, wrapper, algebra proof or independent replay is rejected.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys,time
from real2_prove import prove,Unknown
from real2_verify import replay,Invalid

def sha(raw):return hashlib.sha256(raw).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--external",type=pathlib.Path,required=True)
    ap.add_argument("--out",type=pathlib.Path,required=True)
    x=ap.parse_args()
    root=x.external.resolve()
    out=x.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((root/"manifest.json").read_text())
    assert manifest["protocol"]=="DELTA_REAL1_UPSTREAM_VERILOG_20261124"
    pins={v["id"]:v for v in manifest["upstream"]}
    recorded={"protocol":"DRNAS_REAL2_PROOF_FIRST_PUBLISHED_FPGA","original_manifest_sha256":sha((root/"manifest.json").read_bytes()),
             "upstream":pins,"source_cases":[],"independent_proofs":0,
             "intentional_fault_controls":0}
    for entry in manifest["cases"]:
        case=entry["id"]
        src=root/"upstream"/(entry["source_id"]+".v")
        wrapper=root/(case+".v")
        if not src.is_file() or not wrapper.is_file():
            raise RuntimeError("MISSING_FROZEN_FILE "+case)
        if sha(src.read_bytes())!=pins[entry["source_id"]]["sha256"]:
            raise RuntimeError("UPSTREAM_SHA_MISMATCH "+case)
        if sha(wrapper.read_bytes())!=entry["sha256"]:
            raise RuntimeError("HARNESS_SHA_MISMATCH "+case)
        case_data={"id":case,"family":entry["family"],"fault":entry["fault"],
                   "primary_input_bits":entry["primary_input_bits"],
                   "source_sha256":entry["sha256"],"attempts":[]}
        recorded["source_cases"].append(case_data)
        for rep in range(2):
            stamp=time.perf_counter()
            result=prove(src.read_bytes(),wrapper.read_bytes(),case)
            folder=out/case/f"r{rep}"
            folder.mkdir(parents=True,exist_ok=True)
            cert=folder/"real2_certificate.json"
            cert.write_text(json.dumps(result,indent=2)+"\n")
            check=replay(cert,src,wrapper,case)
            if check["status"]!="CHECKED_RESTRICTED_PARITY_SOURCE":
                raise RuntimeError("CERT_NOT_VERIFIED "+case)
            e2e=time.perf_counter()-stamp
            expected="DIFFERENT_RESTRICTED_SOURCE" if entry["fault"] else "EQUIVALENT_RESTRICTED_SOURCE"
            if result["status"]!=expected or check["verdict"]!=expected:
                raise RuntimeError("INCORRECT_PARITY_VERDICT "+case)
            (folder/"real2_replay.json").write_text(json.dumps(check,indent=2)+"\n")
            trial={"repeat":rep,"status":result["status"],
                   "e2e_seconds":round(e2e,6),
                   "source_proof_seconds":result["elapsed_seconds"],
                   "independent_replay_seconds":check["verification_seconds"],
                   "independent_replay":True,
                   "certificate_sha256":sha(cert.read_bytes())}
            case_data["attempts"].append(trial)
            recorded["independent_proofs"]+=1
            if entry["fault"]:recorded["intentional_fault_controls"]+=1
            (out/"REAL2_RESULTS.json").write_text(json.dumps(recorded,indent=2)+"\n")
            print("REAL2_TRIAL",case,rep,result["status"],round(e2e,5),
                  "s proof replay OK",flush=True)
    assert len(recorded["source_cases"])==12 and recorded["independent_proofs"]==24
    print("REAL2_12_EXTERNAL_CASES_24_REPLAYED_PROOFS_PASS")
if __name__=="__main__":main()
